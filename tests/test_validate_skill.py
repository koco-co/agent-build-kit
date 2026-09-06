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
            "clarify-idea",
            "rename-codex-sessions",
        }

        for skill_md in sorted(REPO_ROOT.glob("skills/*/SKILL.md")):
            name = skill_md.parent.name
            text = skill_md.read_text(encoding="utf-8")
            adapter = skill_md.parent.joinpath("agents", "openai.yaml").read_text(
                encoding="utf-8"
            )
            with self.subTest(skill=name, policy="confirmed"):
                self.assertIn("license: MIT", text.split("---", 2)[1])
                if name in {"build-dev-docs", "rename-codex-sessions"}:
                    self.assertIn("disable-model-invocation: true", text)
                    self.assertIn("allow_implicit_invocation: false", adapter)
                else:
                    self.assertIn(name, model_invocable)
                    self.assertNotIn("disable-model-invocation:", text)
                    self.assertIn("allow_implicit_invocation: true", adapter)
                self.assertIn("时使用", text.split("---", 2)[1])
                self.assertRegex(text.split("---", 2)[1], r"不用于|不使用")
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
            skill_root / "workflows" / "§03-design.md",
            skill_root / "workflows" / "§04-implementation.md",
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
            "MJS",
            "Shell",
            "Python",
            "第三方依赖",
            "验收命令",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

        self.assertIn(
            "node .agents/scripts/release-evidence.mjs",
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
            "build-skill": "需要访问互联网；内置静态校验脚本需要 Python 3.9+。",
            "handoff": None,
            "audit-agent-setup": None,
            "clarify-idea": None,
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
            "build-agents-md": 'version: "4.0.0"',
            "build-dev-docs": 'version: "3.0.0"',
            "build-plugin": 'version: "3.0.0"',
            "build-readme": 'version: "3.0.0"',
            "build-skill": 'version: "3.0.0"',
            "handoff": 'version: "2.1.2"',
            "audit-agent-setup": 'version: "3.0.0"',
            "clarify-idea": 'version: "3.1.0"',
            "rename-codex-sessions": 'version: "1.0.0"',
        }

        for name, version_line in expected.items():
            with self.subTest(skill=name):
                text = REPO_ROOT.joinpath("skills", name, "SKILL.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn(version_line, text)

    def test_clarify_idea_publishes_an_explicit_implementation_gate(self) -> None:
        clarify = REPO_ROOT.joinpath("skills", "clarify-idea", "SKILL.md").read_text(
            encoding="utf-8"
        )
        adapter = REPO_ROOT.joinpath(
            "skills", "clarify-idea", "agents", "openai.yaml"
        ).read_text(encoding="utf-8")
        ui_rule = REPO_ROOT.joinpath(
            "skills", "clarify-idea", "rules", "ui-interaction-preview.md"
        ).read_text(encoding="utf-8")

        for required in (
            "只有目标、范围、需求合理性和关键取舍均已明确",
            "每轮只提出一个需要用户决定、且会影响结果的问题",
            "等待用户回答",
            "共同理解得到最终确认前",
            "不得改动项目内容",
            "每次回答聚焦当前问题",
            "请用户确认是否开始实施",
            "得到用户最终确认后，才允许按照已确认的范围编辑项目内容",
            "出现新的待决策事项时，回到第 2 步",
            "rules/ui-interaction-preview.md",
        ):
            with self.subTest(required=required):
                self.assertIn(required, clarify)

        self.assertIn("确认前不得改动项目内容", adapter)
        self.assertIn("确认是否开始实施", adapter)
        self.assertIn("共同理解得到最终确认前", ui_rule)
        self.assertIn("不得改动项目内容", ui_rule)

    def test_clarify_idea_combines_research_and_reports_scope_before_confirmation(
        self,
    ) -> None:
        clarify = REPO_ROOT.joinpath("skills", "clarify-idea", "SKILL.md").read_text(
            encoding="utf-8"
        )
        steps = {
            line.split(". ", 1)[0]: line.split(". ", 1)[1]
            for line in clarify.splitlines()
            if line[:1].isdigit() and ". " in line
        }

        for required in (
            "了解项目现状",
            "模型已有知识",
            "查阅相关资料并开展市场调研",
            "同类产品、常见做法和可选方案",
            "综合比较后提出推荐方案",
            "推荐理由与主要取舍",
            "能够自行查明的信息，不再询问用户",
        ):
            with self.subTest(research=required):
                self.assertIn(required, steps["1"])

        summary, confirmation = steps["5"].split("随后", 1)
        for required in (
            "所有决策梳理清楚后",
            "总结共同理解",
            "目标、选定方案、选择依据和关键取舍",
            "结合项目实际内容",
            "哪些功能、模块或使用流程会受到影响",
            "计划修改哪些文件和具体内容",
        ):
            with self.subTest(summary=required):
                self.assertIn(required, summary)
        self.assertIn("请用户确认是否开始实施", confirmation)

    def test_clarify_idea_challenges_incomplete_or_unreasonable_scope(self) -> None:
        clarify = REPO_ROOT.joinpath("skills", "clarify-idea", "SKILL.md").read_text(
            encoding="utf-8"
        )
        adapter = REPO_ROOT.joinpath(
            "skills", "clarify-idea", "agents", "openai.yaml"
        ).read_text(encoding="utf-8")

        frontmatter = clarify.split("---", 2)[1]
        body = clarify.split("---", 2)[2]

        for required in (
            "目标、范围、需求合理性和关键取舍均已明确",
            "未发现会改变结果的重要遗漏或不合理需求",
        ):
            with self.subTest(frontmatter_exit=required):
                self.assertIn(required, frontmatter)
            with self.subTest(body_exit=required):
                self.assertIn(required, body)

        for required in (
            "开放范围描述",
            "其他可能影响结果的重要问题",
            "现有需求是否完整、合理",
            "说明依据、影响和推荐调整",
            "用户确认后才更新共同理解和改动范围",
            "确认纳入的其他重要问题和需求调整",
        ):
            with self.subTest(required=required):
                self.assertIn(required, clarify)

        self.assertIn("主动识别遗漏和不合理需求", adapter)

    def test_skill_template_keeps_implicit_invocation_boundaries(self) -> None:
        template = REPO_ROOT.joinpath(
            "skills", "build-skill", "templates", "skill.template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("触发场景、排除条件及与相邻 Skill 的边界", template)

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
            "无法说明具体用途就删除",
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
            ("build-plugin", "workflows/§03-design.md"): (
                "templates/claude-plugin.template.json",
                "templates/codex-plugin.template.json",
                "templates/plugin-design-proposal.template.md",
            ),
            ("build-plugin", "workflows/§04-skill-delegation.md"): (
                "rules/skill-architecture.md",
                "rules/skill-frontmatter.md",
                "rules/skill-quality-standard.md",
                "templates/skill.template.md",
            ),
            ("build-plugin", "workflows/§06-validation.md"): (
                "checklists/plugin-design-review.md",
                "checklists/plugin-semantic-acceptance.md",
            ),
            ("build-readme", "workflows/§02-preview.md"): (
                "templates/readme-preview.template.md",
            ),
            ("build-readme", "workflows/§03-authoring.md"): ("rules/github-style.md",),
            ("build-readme", "workflows/§04-validation.md"): (
                "checklists/semantic-acceptance.md",
            ),
            ("build-skill", "workflows/§03-design.md"): (
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
        clarification = root.joinpath("workflows", "§02-clarification.md").read_text(
            encoding="utf-8"
        )
        design_review = root.joinpath(
            "checklists", "plugin-design-review.md"
        ).read_text(encoding="utf-8")
        for phrase in ("`pi.skills`", "Git/npm/本地安装", "`pi list`", "交互会话验证"):
            self.assertIn(phrase, research)
        self.assertIn("Claude Code、Codex、ZCode、Pi", clarification)
        self.assertIn("Pi 的根 `package.json`", design_review)

    def test_build_agents_md_defines_nested_orchestration_contract(self) -> None:
        skill_root = REPO_ROOT / "skills" / "build-agents-md"
        contract = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                skill_root / "SKILL.md",
                skill_root / "workflows" / "§05-delivery.md",
            )
        )

        self.assertIn("由上层 Skill 统筹", contract)
        self.assertIn("不重复询问", contract)
        self.assertIn("确认依据", contract)
        self.assertIn("恢复条件", contract)

    def test_stateful_build_skills_define_independent_and_controlled_delivery(
        self,
    ) -> None:
        for name, workflow in (
            ("build-agents-md", "§05-delivery.md"),
            ("build-skill", "§06-delivery.md"),
            ("build-plugin", "§07-delivery.md"),
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
                self.assertIn("由上层 Skill 统筹", contract)
                self.assertIn("确认依据", contract)
                self.assertIn("验证", contract)
                self.assertIn("未验证", contract)
                self.assertIn("恢复条件", contract)


if __name__ == "__main__":
    unittest.main()
