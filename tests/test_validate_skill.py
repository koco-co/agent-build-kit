from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "skills" / "build-skill" / "scripts" / "validate_skill.py"

VALID_BODY = """
# Outcome

完成目标。

## Routing

- 路由输入。

## Steps

1. 执行并验证。

## Delivery

- 输出结果。

## Guardrails

- 保护用户数据。

## References

- 无附加文件。
"""


class ValidateSkillTests(unittest.TestCase):
    def run_validator(
        self,
        skill_dir: Path,
        profile: str = "portable",
        plugin_root: Path | None = None,
        strict: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(VALIDATOR),
            str(skill_dir),
            "--profile",
            profile,
        ]
        if plugin_root is not None:
            command.extend(["--plugin-root", str(plugin_root)])
        if strict:
            command.append("--strict")
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )

    def write_skill(
        self,
        root: Path,
        name: str,
        frontmatter_extra: str = "",
    ) -> Path:
        skill_dir = root / name
        skill_dir.mkdir(parents=True)
        skill_dir.joinpath("SKILL.md").write_text(
            (
                "---\n"
                f"name: {name}\n"
                "description: 用于验证测试夹具，仅在测试中显式调用。\n"
                f"{frontmatter_extra}"
                "---\n\n"
                f"{textwrap.dedent(VALID_BODY).strip()}\n"
            ),
            encoding="utf-8",
        )
        return skill_dir

    def add_codex_adapter(self, skill_dir: Path, implicit: str = "false") -> None:
        adapter = skill_dir / "agents" / "openai.yaml"
        adapter.parent.mkdir(parents=True)
        adapter.write_text(
            (
                "interface:\n"
                '  display_name: "Fixture"\n'
                "policy:\n"
                f"  allow_implicit_invocation: {implicit}\n"
            ),
            encoding="utf-8",
        )

    def write_plugin_manifests(self, root: Path) -> None:
        for directory in (".claude-plugin", ".codex-plugin"):
            manifest = root / directory / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '{"name":"fixture-plugin","version":"1.0.0",'
                '"description":"fixture","skills":"./skills/"}\n',
                encoding="utf-8",
            )

    def test_valid_portable_skill_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(Path(temp), "valid-skill")
            result = self.run_validator(skill_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_pi_profile_accepts_supported_policy_and_ignored_source_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "pi-skill",
                'disable-model-invocation: true\nargument-hint: "target"\n',
            )
            result = self.run_validator(skill_dir, profile="pi")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dsh_profile_accepts_unknown_fields_and_canonical_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "dsh-skill",
                'disable-model-invocation: true\nargument-hint: "target"\n',
            )
            result = self.run_validator(skill_dir, profile="dsh")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dsh_profile_rejects_legacy_invocation_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "legacy-skill",
                "disableModelInvocation: true\n",
            )
            result = self.run_validator(skill_dir, profile="dsh")
            self.assertEqual(result.returncode, 1)
            self.assertIn("LEGACY_INVOCATION_KEY", result.stdout)
            self.assertIn("disableModelInvocation", result.stdout)

    def test_dsh_profile_warns_when_description_exceeds_catalog_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp) / "long-description"
            skill_dir.mkdir(parents=True)
            description = "a" * 501
            skill_dir.joinpath("SKILL.md").write_text(
                f"---\nname: long-description\ndescription: {description}\n---\n\n"
                + textwrap.dedent(VALID_BODY).strip()
                + "\n",
                encoding="utf-8",
            )
            result = self.run_validator(skill_dir, profile="dsh", strict=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("DESCRIPTION_DSH_LENGTH", result.stdout)

    def test_broken_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(Path(temp), "broken-skill")
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8").replace(
                    "- 无附加文件。",
                    "- 完整读取 `workflows/missing.md`。",
                ),
                encoding="utf-8",
            )
            result = self.run_validator(skill_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("REF_NOT_FOUND", result.stdout)

    def test_claude_extension_is_profile_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "manual-skill",
                "disable-model-invocation: true\n",
            )
            self.add_codex_adapter(skill_dir)
            portable = self.run_validator(skill_dir, "portable")
            codex = self.run_validator(skill_dir, "codex")
            claude = self.run_validator(skill_dir, "claude")
            dual = self.run_validator(skill_dir, "dual")
            self.assertEqual(portable.returncode, 1)
            self.assertIn("FRONTMATTER_KEY", portable.stdout)
            self.assertEqual(codex.returncode, 1)
            self.assertIn("FRONTMATTER_KEY", codex.stdout)
            self.assertEqual(claude.returncode, 0, claude.stdout + claude.stderr)
            self.assertEqual(dual.returncode, 0, dual.stdout + dual.stderr)

    def test_dual_manual_policy_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "manual-skill",
                "disable-model-invocation: true\n",
            )
            self.add_codex_adapter(skill_dir, "true")
            result = self.run_validator(skill_dir, "dual")
            self.assertEqual(result.returncode, 1)
            self.assertIn("MANUAL_POLICY_MISMATCH", result.stdout)

    def test_nested_frontmatter_is_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "nested-skill",
                (
                    "hooks:\n"
                    "  PreToolUse:\n"
                    "    - matcher: Bash\n"
                    "      hooks:\n"
                    "        - type: command\n"
                    "          command: echo ok\n"
                ),
            )
            result = self.run_validator(skill_dir, "claude")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_compatibility_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "empty-compatibility",
                "compatibility:\n",
            )
            result = self.run_validator(skill_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("COMPATIBILITY_EMPTY", result.stdout)

    def test_temporal_compatibility_claim_warns_and_fails_strict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(
                Path(temp),
                "generic-compatibility",
                "compatibility: 当前适配 Claude Code 与 Codex。\n",
            )
            normal = self.run_validator(skill_dir)
            strict = self.run_validator(skill_dir, strict=True)
            self.assertEqual(normal.returncode, 0, normal.stdout + normal.stderr)
            self.assertIn("COMPATIBILITY_TEMPORAL", normal.stdout)
            self.assertEqual(strict.returncode, 1)
            self.assertIn("COMPATIBILITY_TEMPORAL", strict.stdout)

    def test_prompt_name_must_end_with_agent_md(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = self.write_skill(Path(temp), "prompt-skill")
            prompts = skill_dir / "prompts"
            prompts.mkdir()
            prompts.joinpath("reviewer.prompt.md").write_text(
                "review", encoding="utf-8"
            )
            result = self.run_validator(skill_dir)
            self.assertEqual(result.returncode, 1)
            self.assertIn("AGENT_PROMPT_NAME", result.stdout)

    def test_internal_plugin_symlink_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = Path(temp) / "fixture-plugin"
            self.write_plugin_manifests(plugin_root)
            shared = plugin_root / "skills" / "shared" / "rules" / "quality.md"
            shared.parent.mkdir(parents=True)
            shared.write_text("quality", encoding="utf-8")

            skill_dir = self.write_skill(
                plugin_root / "skills",
                "linked-skill",
            )
            rules = skill_dir / "rules"
            rules.mkdir()
            (rules / "quality.md").symlink_to("../../shared/rules/quality.md")
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                skill_md.read_text(encoding="utf-8").replace(
                    "- 无附加文件。",
                    "- 读取 `rules/quality.md`。",
                ),
                encoding="utf-8",
            )

            result = self.run_validator(skill_dir, "portable", plugin_root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_symlink_outside_plugin_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plugin_root = base / "fixture-plugin"
            self.write_plugin_manifests(plugin_root)
            outside = base / "outside.md"
            outside.write_text("outside", encoding="utf-8")

            skill_dir = self.write_skill(plugin_root / "skills", "linked-skill")
            rules = skill_dir / "rules"
            rules.mkdir()
            (rules / "outside.md").symlink_to(os.path.relpath(outside, rules))

            result = self.run_validator(skill_dir, "portable", plugin_root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("SYMLINK_OUTSIDE_PLUGIN", result.stdout)

    def test_handoff_requires_copyable_next_agent_prompt(self) -> None:
        skill_md = REPO_ROOT.joinpath("skills", "handoff", "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("给下一个 Agent 的提示词", skill_md)
        self.assertIn("真实文件路径", skill_md)
        self.assertIn("可直接复制", skill_md)
        self.assertIn(
            "请读取 `<真实文件路径>` 并继续完成其中记录的任务；"
            "严格遵循文档中的目标、约束、已确认决策和后续步骤。",
            skill_md,
        )
        self.assertIn(
            "请调用 `skill-name`，读取 `<真实文件路径>` 并继续完成其中记录的任务；"
            "严格遵循文档中的目标、约束、已确认决策和后续步骤。",
            skill_md,
        )
        self.assertNotIn("# Codex", skill_md)
        self.assertNotIn("# Claude Code Plugin", skill_md)
        self.assertNotIn("/plugin-name:skill-name", skill_md)
        self.assertNotIn("`$skill-name`", skill_md)

    def test_shipped_skills_publish_the_confirmed_invocation_policy(self) -> None:
        redundant_phrases = (
            "用户明确调用",
            "普通请求不得自动触发",
            "普通问答、评审或实现请求不得自动触发",
            "无法确认是否为显式调用",
            "显式调用只授权",
        )
        model_invocable = {
            "build-agents-md",
            "build-plugin",
            "build-readme",
            "build-skill",
            "handoff",
            "audit-agent-setup",
            "grill-me",
            "rename-codex-sessions",
        }

        for skill_md in sorted(REPO_ROOT.glob("skills/*/SKILL.md")):
            name = skill_md.parent.name
            text = skill_md.read_text(encoding="utf-8")
            adapter = skill_md.parent.joinpath("agents", "openai.yaml").read_text(
                encoding="utf-8"
            )
            frontmatter = text.split("---", 2)[1]
            with self.subTest(skill=name, policy="confirmed"):
                self.assertIn("license: MIT", frontmatter)
                if name in {"build-dev-docs", "rename-codex-sessions"}:
                    self.assertIn("disable-model-invocation: true", text)
                    self.assertIn("allow_implicit_invocation: false", adapter)
                else:
                    self.assertIn(name, model_invocable)
                    self.assertNotIn("disable-model-invocation:", text)
                    self.assertIn("allow_implicit_invocation: true", adapter)
                if name == "grill-me":
                    self.assertIn("Use when", frontmatter)
                    self.assertIn("Not for", frontmatter)
                else:
                    self.assertIn("时使用", frontmatter)
                    self.assertRegex(frontmatter, r"不用于|不使用")
            for phrase in redundant_phrases:
                with self.subTest(skill=name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_build_skill_defines_conditional_invocation_copy_rules(self) -> None:
        quality = REPO_ROOT.joinpath(
            "skills", "build-skill", "rules", "quality-standard.md"
        ).read_text(encoding="utf-8")

        self.assertIn("仅限用户调用的 Skill", quality)
        self.assertIn("不在正文重复说明调用权限", quality)
        self.assertIn("允许模型调用的 Skill", quality)
        self.assertIn("跨平台 `description`", quality)
        self.assertIn("`when_to_use`", quality)
        self.assertIn("触发条件、排除条件", quality)

    def test_build_skill_defines_conditional_shared_script_policy(self) -> None:
        skill_root = REPO_ROOT / "skills" / "build-skill"
        paths = (
            skill_root / "SKILL.md",
            skill_root / "rules" / "architecture.md",
            skill_root / "rules" / "quality-standard.md",
            skill_root / "rules" / "platform-compatibility.md",
            skill_root / "workflows" / "§01-research.md",
            skill_root / "workflows" / "§02-design.md",
            skill_root / "workflows" / "§03-implementation.md",
            skill_root / "checklists" / "design-review.md",
            skill_root / "checklists" / "content-review.md",
            skill_root / "templates" / "design-proposal.template.md",
            skill_root / "examples" / "project-skill.example.md",
        )
        contract = "\n".join(path.read_text(encoding="utf-8") for path in paths)

        for required in (
            ".agents/scripts/",
            "至少两个",
            "随项目或整体安装包",
            "独立安装",
            "Skill 自有",
            "Node",
            "Shell",
            "Python",
            "第三方依赖",
            "验收命令",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

        self.assertIn(
            "python3 .agents/scripts/release-evidence.py <fixture>",
            (skill_root / "examples" / "project-skill.example.md").read_text(
                encoding="utf-8"
            ),
        )

    def test_build_skill_defines_frontmatter_decision_matrix(self) -> None:
        skill_root = REPO_ROOT / "skills" / "build-skill"
        frontmatter = skill_root.joinpath("rules", "frontmatter.md").read_text(
            encoding="utf-8"
        )
        template = skill_root.joinpath("templates", "skill.template.md").read_text(
            encoding="utf-8"
        )
        design = skill_root.joinpath(
            "templates", "design-proposal.template.md"
        ).read_text(encoding="utf-8")

        for required in (
            "字段决策矩阵",
            "disable-model-invocation",
            "user-invocable",
            "argument-hint",
            "arguments",
            "allowed-tools",
            "disallowed-tools",
            "paths",
            "context",
            "agent",
            "background",
            "model",
            "effort",
            "hooks",
            "shell",
            "compatibility",
            "agents/openai.yaml",
        ):
            with self.subTest(required=required):
                self.assertIn(required, frontmatter)
        self.assertNotIn("compatibility:", template.split("---", 2)[1])
        self.assertNotIn("metadata:", template.split("---", 2)[1])
        self.assertIn("Frontmatter 字段决策矩阵", design)

    def test_build_skill_separates_content_and_copy_review(self) -> None:
        skill_root = REPO_ROOT / "skills" / "build-skill"
        content_review = skill_root.joinpath(
            "checklists", "content-review.md"
        ).read_text(encoding="utf-8")
        copy_review = skill_root.joinpath("checklists", "copy-review.md").read_text(
            encoding="utf-8"
        )
        examples = skill_root.joinpath("examples", "copy-review.example.md").read_text(
            encoding="utf-8"
        )
        reviewer = skill_root.joinpath("prompts", "reviewer.agent.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("正确性和完整性", content_review)
        self.assertIn("措辞润色不属于本清单", content_review)
        self.assertNotIn("## 表达质量", content_review)
        self.assertIn("自然、清楚、简洁", copy_review)
        self.assertIn("不得改变", copy_review)
        self.assertGreaterEqual(examples.count("## 样本"), 6)
        self.assertIn("内容审查结果", reviewer)
        self.assertIn("文案审查结果", reviewer)
        self.assertIn("只审查，不修改", reviewer)

    def test_shipped_compatibility_describes_only_hard_requirements(self) -> None:
        expected = {
            "build-agents-md": "需要 Python 3.9+ 运行内置校验脚本。",
            "build-dev-docs": None,
            "build-plugin": "需要访问互联网；内置静态校验脚本需要 Python 3.9+。",
            "build-readme": "需要 Python 3.9+ 运行内置校验脚本。",
            "build-skill": "核对平台契约需要访问互联网；内置校验脚本需要 Python 3.9+。",
            "handoff": None,
            "audit-agent-setup": None,
            "grill-me": None,
            "rename-codex-sessions": (
                "需要 Python 3.9+、可调用 Codex App Server，以及 Codex Desktop 本地项目状态文件。"
            ),
        }
        prohibited = ("当前适配", "目前适配", "目前仅适配")

        for skill_md in sorted(REPO_ROOT.glob("skills/*/SKILL.md")):
            name = skill_md.parent.name
            frontmatter = skill_md.read_text(encoding="utf-8").split("---", 2)[1]
            for phrase in prohibited:
                with self.subTest(skill=name, phrase=phrase):
                    self.assertNotIn(phrase, frontmatter)
            compatibility = expected[name]
            with self.subTest(skill=name, expected=compatibility):
                if compatibility is None:
                    self.assertNotIn("compatibility:", frontmatter)
                else:
                    self.assertIn(f"compatibility: {compatibility}", frontmatter)

    def test_behavior_changed_skill_versions_are_updated(self) -> None:
        expected = {
            "build-agents-md": 'version: "4.1.0"',
            "build-dev-docs": 'version: "3.1.0"',
            "build-plugin": 'version: "3.1.0"',
            "build-readme": 'version: "3.1.0"',
            "build-skill": 'version: "3.1.1"',
            "handoff": 'version: "2.1.4"',
            "audit-agent-setup": 'version: "3.1.1"',
            "grill-me": 'version: "1.0.1"',
            "rename-codex-sessions": 'version: "1.1.0"',
        }

        for name, version_line in expected.items():
            with self.subTest(skill=name):
                text = REPO_ROOT.joinpath("skills", name, "SKILL.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn(version_line, text)

    def test_grill_me_publishes_design_tree_rounds_and_confirmation_gate(self) -> None:
        skill = REPO_ROOT.joinpath("skills", "grill-me", "SKILL.md").read_text(
            encoding="utf-8"
        )
        adapter = REPO_ROOT.joinpath(
            "skills", "grill-me", "agents", "openai.yaml"
        ).read_text(encoding="utf-8")

        for required in (
            "design tree",
            "Work the tree in **rounds**",
            "Ask the whole frontier in one round",
            "number each question and give your recommended answer",
            "wait for the user's answers before the next round",
            'Word each question so "yes" accepts your recommended answer',
            "Recompute the frontier and ask the next round",
            "belongs to a _later_ round, not this one",
        ):
            with self.subTest(required=required):
                self.assertIn(required, skill)

        for required in (
            "Finding _facts_ is your job, never the user's",
            "dispatch a sub-agent in read-only mode to find it",
            "Don't block on exploration",
            "ask the rest of the frontier now",
            "The _decisions_ are the user's",
        ):
            with self.subTest(facts=required):
                self.assertIn(required, skill)

        for required in (
            "The session is done when the frontier is empty",
            "Do not act on it until the user confirms you have reached a shared understanding",
        ):
            with self.subTest(confirmation=required):
                self.assertIn(required, skill)

        self.assertIn("design tree", adapter)
        self.assertIn("do not act until I confirm", adapter)

    def test_grill_me_describes_trigger_and_exclusion(self) -> None:
        frontmatter = (
            REPO_ROOT.joinpath("skills", "grill-me", "SKILL.md")
            .read_text(encoding="utf-8")
            .split("---", 2)[1]
        )

        self.assertIn("Use when the user wants to stress-test", frontmatter)
        self.assertIn("'grill' trigger phrases", frontmatter)
        self.assertIn("Not for ordinary questions", frontmatter)

    def test_grill_me_replaces_clarify_idea_resources(self) -> None:
        self.assertFalse(REPO_ROOT.joinpath("skills", "clarify-idea").exists())
        self.assertFalse(
            REPO_ROOT.joinpath("evals", "skills", "clarify-idea.json").exists()
        )
        self.assertFalse(REPO_ROOT.joinpath("skills", "grill-me", "rules").exists())
        self.assertFalse(
            REPO_ROOT.joinpath("skills", "grill-me", "templates").exists()
        )

    def test_skill_template_keeps_implicit_invocation_boundaries(self) -> None:
        template = REPO_ROOT.joinpath(
            "skills", "build-skill", "templates", "skill.template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("做什么；何时使用；何时不使用；与相邻 Skill 的边界", template)

    def test_build_skill_requires_minimum_sufficient_design(self) -> None:
        quality = REPO_ROOT.joinpath(
            "skills", "build-skill", "rules", "quality-standard.md"
        ).read_text(encoding="utf-8")

        for required in (
            "最小充分",
            "用户需求、仓库事实、可复现缺陷、平台契约或明确安全要求",
            "说不出具体依据就删除",
        ):
            with self.subTest(required=required):
                self.assertIn(required, quality)

    def test_reviewer_enforces_minimum_sufficient_content(self) -> None:
        reviewer = REPO_ROOT.joinpath(
            "skills", "build-skill", "prompts", "reviewer.agent.md"
        ).read_text(encoding="utf-8")

        for required in (
            "最小充分",
            "只保留目标、路由/退出、执行顺序和必要红线",
            "用户需求、仓库事实、平台契约、可复现缺陷或明确安全要求",
            "重复规范源",
            "说不清用途就删除",
        ):
            with self.subTest(required=required):
                self.assertIn(required, reviewer)

    def test_workflows_wire_referenced_resources_on_demand(self) -> None:
        references = {
            ("build-agents-md", "workflows/§01-research.md"): (
                "examples/library-or-cli.example.md",
                "examples/application.example.md",
                "examples/monorepo.example.md",
            ),
            ("build-plugin", "workflows/§02-design.md"): (
                "templates/claude-plugin.template.json",
                "templates/codex-plugin.template.json",
                "templates/plugin-design-proposal.template.md",
            ),
            ("build-plugin", "workflows/§03-skill-delegation.md"): (
                "rules/skill-architecture.md",
                "rules/skill-frontmatter.md",
                "rules/skill-quality-standard.md",
                "templates/skill.template.md",
            ),
            ("build-plugin", "workflows/§05-validation-delivery.md"): (
                "checklists/plugin-design-review.md",
                "checklists/plugin-semantic-acceptance.md",
            ),
            ("build-readme", "workflows/§02-preview.md"): (
                "templates/readme-preview.template.md",
            ),
            ("build-readme", "workflows/§03-authoring.md"): ("rules/github-style.md",),
            ("build-readme", "workflows/§04-validation-delivery.md"): (
                "checklists/semantic-acceptance.md",
            ),
            ("build-skill", "workflows/§02-design.md"): (
                "examples/global-skill.example.md",
                "examples/project-skill.example.md",
                "templates/design-proposal.template.md",
            ),
        }

        for (skill_name, workflow), paths in references.items():
            content = REPO_ROOT.joinpath("skills", skill_name, workflow).read_text(
                encoding="utf-8"
            )
            for path in paths:
                with self.subTest(skill=skill_name, workflow=workflow, path=path):
                    self.assertIn(path, content)

    def test_repository_quality_sources_publish_the_evidence_first_rule(self) -> None:
        agents = REPO_ROOT.joinpath("AGENTS.md").read_text(encoding="utf-8")
        quality = REPO_ROOT.joinpath(
            "skills", "build-skill", "rules", "quality-standard.md"
        ).read_text(encoding="utf-8")
        design_review = REPO_ROOT.joinpath(
            "skills", "build-skill", "checklists", "design-review.md"
        ).read_text(encoding="utf-8")
        content_review = REPO_ROOT.joinpath(
            "skills", "build-skill", "checklists", "content-review.md"
        ).read_text(encoding="utf-8")
        for text in (agents, quality, design_review, content_review):
            self.assertIn("用户需求", text)
            self.assertIn("仓库事实", text)
            self.assertIn("平台契约", text)
            self.assertIn("可复现缺陷", text)
            self.assertIn("明确安全要求", text)

    def test_explicit_build_requests_do_not_require_redundant_edit_confirmation(
        self,
    ) -> None:
        expected_phrases = {
            "build-agents-md": "直接实施",
            "build-plugin": "已授权对应分发文件的本地编辑",
            "build-readme": "已授权对应 README 文件的本地编辑",
            "build-skill": "已授权对应 Skill 文件的本地编辑",
            "build-dev-docs": "已授权对应文档的本地编辑",
        }
        for name, phrase in expected_phrases.items():
            with self.subTest(skill=name):
                contract = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in REPO_ROOT.joinpath("skills", name).rglob("*.md")
                )
                self.assertIn(phrase, contract)
                self.assertIn("未决", contract)
                self.assertIn("确认", contract)

    def test_build_plugin_research_covers_pi_as_a_first_class_platform(self) -> None:
        root = REPO_ROOT / "skills" / "build-plugin"
        research = root.joinpath("workflows", "§01-research.md").read_text(
            encoding="utf-8"
        )
        clarification = root.joinpath("workflows", "§02-design.md").read_text(
            encoding="utf-8"
        )
        design_review = root.joinpath(
            "checklists", "plugin-design-review.md"
        ).read_text(encoding="utf-8")
        entry = root.joinpath("SKILL.md").read_text(encoding="utf-8")
        for phrase in ("`pi.skills`", "Git/npm/本地安装", "`pi list`", "交互会话验证"):
            self.assertIn(phrase, research)
        self.assertIn("Claude Code、Codex、ZCode、Pi", entry + clarification)
        self.assertIn("Pi 的根 `package.json`", design_review)

    def test_build_agents_md_defines_nested_orchestration_contract(self) -> None:
        skill_root = REPO_ROOT / "skills" / "build-agents-md"
        contract = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                skill_root / "SKILL.md",
                skill_root / "workflows" / "§04-validation-delivery.md",
            )
        )

        self.assertIn("上层 Skill", contract)
        self.assertIn("不重复询问", contract)
        self.assertIn("确认依据", contract)
        self.assertIn("恢复条件", contract)

    def test_stateful_build_skills_define_independent_and_controlled_delivery(
        self,
    ) -> None:
        for name, workflow in (
            ("build-agents-md", "§04-validation-delivery.md"),
            ("build-skill", "§04-validation-delivery.md"),
            ("build-plugin", "§05-validation-delivery.md"),
        ):
            with self.subTest(skill=name):
                root = REPO_ROOT / "skills" / name
                contract = "\n".join(
                    path.read_text(encoding="utf-8")
                    for path in (root / "SKILL.md", root / "workflows" / workflow)
                )
                self.assertIn("独立调用", contract)
                self.assertIn("受控调用", contract)
                self.assertIn("不重复询问", contract)
                self.assertIn("上层 Skill", contract)
                self.assertIn("确认依据", contract)
                self.assertIn("验证", contract)
                self.assertIn("未验证", contract)
                self.assertIn("恢复条件", contract)


if __name__ == "__main__":
    unittest.main()
