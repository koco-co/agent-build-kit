from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_skill_evals.py"
EXPECTED_SKILLS = {
    "audit-agent-setup",
    "build-agents-md",
    "build-dev-docs",
    "build-plugin",
    "build-readme",
    "build-skill",
    "clarify-idea",
    "handoff",
    "rename-codex-sessions",
}


class SkillEvalTests(unittest.TestCase):
    def run_validator(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(root)],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def write_fixture(self, root: Path, name: str, data: dict[str, object]) -> None:
        skill = root / "skills" / name
        skill.mkdir(parents=True, exist_ok=True)
        skill.joinpath("SKILL.md").write_text(
            f"---\nname: {name}\n---\n", encoding="utf-8"
        )
        eval_root = root / "evals" / "skills"
        eval_root.mkdir(parents=True, exist_ok=True)
        eval_root.joinpath(f"{name}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    def test_repository_eval_assets_pass(self) -> None:
        result = self.run_validator(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: 9 Skill eval file(s)", result.stdout)

    def test_every_shipped_skill_has_exactly_one_eval_file(self) -> None:
        shipped = {path.parent.name for path in REPO_ROOT.glob("skills/*/SKILL.md")}
        evaluated = {path.stem for path in REPO_ROOT.glob("evals/skills/*.json")}
        self.assertEqual(shipped, EXPECTED_SKILLS)
        self.assertEqual(evaluated, EXPECTED_SKILLS)

    def test_each_eval_covers_trigger_exclusion_and_behavior(self) -> None:
        for path in REPO_ROOT.glob("evals/skills/*.json"):
            with self.subTest(skill=path.stem):
                data = json.loads(path.read_text(encoding="utf-8"))
                kinds = {case["kind"] for case in data["cases"]}
                self.assertEqual(
                    kinds, {"should_trigger", "should_not_trigger", "behavior"}
                )

    def test_missing_case_kind_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(
                root,
                "sample",
                {
                    "skill": "sample",
                    "cases": [
                        {
                            "id": "trigger",
                            "kind": "should_trigger",
                            "prompt": "Use it",
                            "expected": ["runs"],
                        }
                    ],
                },
            )
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("缺少用例类型", result.stdout)

    def test_extra_or_missing_skill_eval_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "skills" / "sample"
            skill.mkdir(parents=True)
            skill.joinpath("SKILL.md").write_text(
                "---\nname: sample\n---\n", encoding="utf-8"
            )
            eval_root = root / "evals" / "skills"
            eval_root.mkdir(parents=True)
            eval_root.joinpath("extra.json").write_text(
                '{"skill":"extra","cases":[]}', encoding="utf-8"
            )
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("缺少 sample.json", result.stdout)
            self.assertIn("未分发的 Skill", result.stdout)


if __name__ == "__main__":
    unittest.main()
