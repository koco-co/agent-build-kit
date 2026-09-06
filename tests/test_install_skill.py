from __future__ import annotations

import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.install_skill import (
    PORTABLE_FRONTMATTER_FIELDS,
    install_skill,
    strip_claude_frontmatter,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install_skill.py"


class InstallSkillTests(unittest.TestCase):
    def run_installer(
        self,
        home: Path,
        platform: str,
        skill: str = "build-skill",
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        return subprocess.run(
            [
                sys.executable,
                str(INSTALLER),
                skill,
                "--platform",
                platform,
                "--scope",
                "user",
                *extra,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_codex_install_strips_claude_field_and_keeps_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "codex")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            destination = home / ".agents" / "skills" / "build-skill"
            skill_md = destination.joinpath("SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("disable-model-invocation:", skill_md)
            self.assertTrue(destination.joinpath("agents", "openai.yaml").is_file())
            self.assertIn(
                "allow_implicit_invocation: true",
                destination.joinpath("agents", "openai.yaml").read_text(
                    encoding="utf-8"
                ),
            )

    def test_claude_install_keeps_model_invocable_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "claude")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            destination = home / ".claude" / "skills" / "build-skill"
            skill_md = destination.joinpath("SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("disable-model-invocation:", skill_md)
            self.assertFalse(destination.joinpath("agents").exists())

            second = self.run_installer(home, "claude")
            self.assertEqual(second.returncode, 1)
            self.assertIn("--force", second.stderr)

            forced = self.run_installer(home, "claude", "build-skill", "--force")
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)

    def test_claude_install_preserves_model_invocation_fields(self) -> None:
        variants = {
            "default": "",
            "explicit-false": "disable-model-invocation: false\n",
            "model-only": "user-invocable: false\n",
        }

        for name, invocation_fields in variants.items():
            with self.subTest(variant=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                repo = root / "repo"
                skill_name = f"fixture-{name}"
                skill = repo / "skills" / skill_name
                skill.mkdir(parents=True)
                skill.joinpath("SKILL.md").write_text(
                    (
                        "---\n"
                        f"name: {skill_name}\n"
                        "description: 用于验证 Claude 调用配置保持不变。\n"
                        f"{invocation_fields}"
                        "---\n\n"
                        "# Outcome\n\n完成目标。\n\n"
                        "## Routing\n\n- 处理输入。\n\n"
                        "## Steps\n\n1. 执行。\n\n"
                        "## Delivery\n\n- 输出结果。\n\n"
                        "## Guardrails\n\n- 保护数据。\n\n"
                        "## References\n\n- 无附加文件。\n"
                    ),
                    encoding="utf-8",
                )
                validator = (
                    repo / "skills" / "build-skill" / "scripts" / "validate_skill.py"
                )
                validator.parent.mkdir(parents=True)
                shutil.copy2(
                    REPO_ROOT
                    / "skills"
                    / "build-skill"
                    / "scripts"
                    / "validate_skill.py",
                    validator,
                )

                destination = install_skill(
                    repo_root=repo,
                    skill_name=skill_name,
                    platform="claude",
                    scope="user",
                    home_dir=root / "home",
                )
                installed = destination.joinpath("SKILL.md").read_text(encoding="utf-8")

                if invocation_fields:
                    self.assertIn(invocation_fields.strip(), installed)
                else:
                    self.assertNotIn("disable-model-invocation:", installed)
                    self.assertNotIn("user-invocable:", installed)

    def test_build_plugin_install_materializes_shared_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(
                home,
                "codex",
                "build-plugin",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            destination = home / ".agents" / "skills" / "build-plugin"
            shared = destination / "prompts" / "reviewer.agent.md"
            self.assertTrue(shared.is_file())
            self.assertFalse(shared.is_symlink())
            for shared_path in (
                "scripts/sync_shared_files.py",
                "scripts/validate_skill.py",
                "rules/skill-frontmatter.md",
                "checklists/skill-content-review.md",
                "checklists/skill-copy-review.md",
                "examples/skill-copy-review.example.md",
            ):
                with self.subTest(path=shared_path):
                    materialized = destination / shared_path
                    self.assertTrue(materialized.is_file())
                    self.assertFalse(materialized.is_symlink())

            for entrypoint in (
                "sync_shared_files.py",
                "validate_plugin.py",
                "validate_skill.py",
            ):
                with self.subTest(entrypoint=entrypoint):
                    help_result = subprocess.run(
                        [
                            sys.executable,
                            str(destination / "scripts" / entrypoint),
                            "--help",
                        ],
                        check=False,
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(
                        help_result.returncode,
                        0,
                        help_result.stdout + help_result.stderr,
                    )

    def test_handoff_codex_install_strips_claude_only_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "codex", "handoff")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            destination = home / ".agents" / "skills" / "handoff"
            skill_md = destination.joinpath("SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("argument-hint:", skill_md)
            self.assertNotIn("disable-model-invocation:", skill_md)

    def test_codex_copy_strips_all_claude_extensions_and_nested_blocks(self) -> None:
        validator = runpy.run_path(
            str(REPO_ROOT / "skills" / "build-skill" / "scripts" / "validate_skill.py")
        )
        claude_extensions = validator["CLAUDE_EXTENSION_KEYS"]
        scalar_extensions = sorted(claude_extensions - {"hooks"})
        extension_lines = "".join(f"{field}: fixture\n" for field in scalar_extensions)
        source = (
            "---\n"
            "name: fixture-skill\n"
            "description: Portable description.\n"
            "compatibility: Requires Python 3.9+.\n"
            "metadata:\n"
            "  author: fixture\n"
            f"{extension_lines}"
            "hooks:\n"
            "  PreToolUse:\n"
            "    - matcher: Bash\n"
            "      hooks:\n"
            "        - type: command\n"
            "          command: echo ok\n"
            "---\n\n"
            "# Outcome\n\n"
            "Complete fixture work.\n"
        )

        installed = strip_claude_frontmatter(source)

        for claude_only in sorted(claude_extensions):
            with self.subTest(field=claude_only):
                self.assertNotIn(f"{claude_only}:", installed)
        self.assertNotIn("PreToolUse:", installed)
        self.assertNotIn("command: echo ok", installed)
        self.assertIn("compatibility: Requires Python 3.9+.", installed)
        self.assertIn("metadata:\n  author: fixture", installed)
        self.assertIn("# Outcome", installed)

    def test_installer_portable_fields_match_skill_validator(self) -> None:
        validator = runpy.run_path(
            str(REPO_ROOT / "skills" / "build-skill" / "scripts" / "validate_skill.py")
        )
        self.assertEqual(
            PORTABLE_FRONTMATTER_FIELDS,
            validator["STANDARD_KEYS"],
        )

    def test_build_readme_installs_for_all_platforms(self) -> None:
        for platform, root_name in (
            ("claude", ".claude"),
            ("codex", ".agents"),
            ("zcode", ".zcode"),
            ("pi", ".pi/agent"),
        ):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                result = self.run_installer(home, platform, "build-readme")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

                destination = home / root_name / "skills" / "build-readme"
                self.assertTrue(destination.joinpath("SKILL.md").is_file())
                self.assertTrue(
                    destination.joinpath("scripts", "validate_readme.py").is_file()
                )
                if platform == "claude":
                    self.assertFalse(destination.joinpath("agents").exists())
                elif platform == "codex":
                    self.assertTrue(
                        destination.joinpath("agents", "openai.yaml").is_file()
                    )
                else:
                    self.assertFalse(destination.joinpath("agents").exists())

    def test_build_agents_md_installs_for_all_platforms(self) -> None:
        for platform, root_name in (
            ("claude", ".claude"),
            ("codex", ".agents"),
            ("zcode", ".zcode"),
            ("pi", ".pi/agent"),
        ):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as temp:
                home = Path(temp)
                result = self.run_installer(home, platform, "build-agents-md")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

                destination = home / root_name / "skills" / "build-agents-md"
                self.assertTrue(destination.joinpath("SKILL.md").is_file())
                self.assertTrue(
                    destination.joinpath("scripts", "validate_agents_md.py").is_file()
                )
                self.assertTrue(
                    destination.joinpath("examples", "monorepo.example.md").is_file()
                )
                if platform == "claude":
                    self.assertFalse(destination.joinpath("agents").exists())
                elif platform == "codex":
                    self.assertTrue(
                        destination.joinpath("agents", "openai.yaml").is_file()
                    )
                else:
                    self.assertFalse(destination.joinpath("agents").exists())

    def test_all_shipped_skills_install_for_all_platforms(self) -> None:
        skill_names = sorted(
            path.name
            for path in REPO_ROOT.joinpath("skills").iterdir()
            if path.name not in {"audit-agent-setup"}
        )

        for skill_name in skill_names:
            for platform, root_name in (
                ("claude", ".claude"),
                ("codex", ".agents"),
                ("zcode", ".zcode"),
                ("pi", ".pi/agent"),
            ):
                with (
                    self.subTest(skill=skill_name, platform=platform),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    home = Path(temp)
                    result = self.run_installer(home, platform, skill_name)
                    self.assertEqual(
                        result.returncode,
                        0,
                        result.stdout + result.stderr,
                    )
                    destination = home / root_name / "skills" / skill_name
                    skill_md = destination.joinpath("SKILL.md").read_text(
                        encoding="utf-8"
                    )
                    if platform == "claude":
                        self.assertFalse(destination.joinpath("agents").exists())
                        if skill_name in {"build-dev-docs", "rename-codex-sessions"}:
                            self.assertIn("disable-model-invocation: true", skill_md)
                        else:
                            self.assertNotIn("disable-model-invocation:", skill_md)
                    elif platform == "codex":
                        self.assertNotIn("disable-model-invocation:", skill_md)
                        adapter = destination.joinpath(
                            "agents", "openai.yaml"
                        ).read_text(encoding="utf-8")
                        self.assertIn(
                            "allow_implicit_invocation: "
                            + (
                                "false"
                                if skill_name in {"build-dev-docs", "rename-codex-sessions"}
                                else "true"
                            ),
                            adapter,
                        )
                    else:
                        self.assertFalse(destination.joinpath("agents").exists())
                        self.assertIn(f"name: {skill_name}", skill_md)
                        if skill_name in {"build-dev-docs", "rename-codex-sessions"}:
                            self.assertIn("disable-model-invocation: true", skill_md)

    def test_zcode_install_preserves_claude_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            result = self.run_installer(home, "zcode", "handoff")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            destination = home / ".zcode" / "skills" / "handoff"
            skill_md = destination.joinpath("SKILL.md").read_text(encoding="utf-8")
            self.assertIn("argument-hint:", skill_md)
            self.assertFalse(destination.joinpath("agents").exists())

    def test_full_package_only_skills_reject_standalone_installation(self) -> None:
        for skill_name in ("audit-agent-setup",):
            for platform in ("claude", "codex", "zcode", "pi"):
                with (
                    self.subTest(skill=skill_name, platform=platform),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    result = self.run_installer(Path(temp), platform, skill_name)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(
                        f"{skill_name} 只能随 agent-build-kit 完整分发包使用",
                        result.stderr,
                    )

    def test_dsh_is_not_a_standalone_installation_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_installer(Path(temp), "dsh")
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid choice: 'dsh'", result.stderr)

    def test_pi_project_install_uses_project_skill_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            destination = install_skill(
                repo_root=REPO_ROOT,
                skill_name="build-skill",
                platform="pi",
                scope="project",
                project_dir=project,
            )
            self.assertEqual(
                destination,
                project.resolve() / ".pi" / "skills" / "build-skill",
            )
            self.assertTrue(destination.joinpath("SKILL.md").is_file())

    def test_dry_run_does_not_create_target_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "new-home"
            result = self.run_installer(
                home,
                "codex",
                "build-skill",
                "--dry-run",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((home / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
