"""Static behavior contracts for the adaptive developer-documentation skill."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "build-dev-docs"


class BuildDevDocsContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return SKILL_ROOT.joinpath(relative).read_text(encoding="utf-8")

    def contract(self) -> str:
        return "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(SKILL_ROOT.rglob("*.md"))
        )

    def test_routes_cover_build_update_and_review_without_code_work(self) -> None:
        entry = self.read("SKILL.md")
        for scenario in ("从零建立", "已有项目提取", "持续更新", "审查报告复核"):
            self.assertIn(scenario, entry)
        self.assertIn("不修改产品代码", entry)
        self.assertIn("仅审查时保持只读", entry)

    def test_document_catalog_is_optional_not_a_fixed_twelve_file_bundle(self) -> None:
        catalog = self.read("rules/documents.md")
        plan = self.read("workflows/§02-plan.md")
        validation = self.read("workflows/§04-validation.md")
        for phrase in (
            "不是必须创建的清单",
            "只有当前开发",
            "不创建占位",
            "没有选择的文档职责不视为缺失",
        ):
            self.assertIn(phrase, catalog + plan + validation)
        self.assertNotIn("全部 12", catalog + plan + validation)
        self.assertNotIn("为全部 12", catalog + plan + validation)

    def test_existing_paths_are_preserved_and_default_tree_is_not_forced(self) -> None:
        contract = self.contract()
        self.assertIn("沿用项目已有等价文档及路径", contract)
        self.assertIn("路径由现有项目结构决定", contract)
        self.assertIn("不能仅为匹配模板创建目录层级", contract)

    def test_brief_changelog_and_agents_entry_are_evidence_driven(self) -> None:
        entry = self.read("SKILL.md")
        plan = self.read("workflows/§02-plan.md")
        authoring = self.read("workflows/§03-authoring.md")
        combined = entry + plan + authoring
        self.assertIn("`AGENT_BRIEF.md` 与 `CHANGELOG.md`", combined)
        self.assertIn("仅在多份文档需要导航", combined)
        self.assertIn("项目已有该机制", combined)
        self.assertIn("可选 AGENTS.md 入口", combined)
        self.assertIn("不修改 CLAUDE.md", combined)

    def test_explicit_document_request_does_not_require_batch_confirmations(
        self,
    ) -> None:
        entry = self.read("SKILL.md")
        plan = self.read("workflows/§02-plan.md")
        authoring = self.read("workflows/§03-authoring.md")
        combined = entry + plan + authoring
        self.assertIn("直接进入编写", combined)
        self.assertIn("按明确请求直接写入", combined)
        self.assertIn("只确认一次", combined)
        self.assertNotIn("每批内容确认", combined)
        self.assertNotIn("逐批确认", combined)

    def test_review_only_is_read_only_and_revision_does_not_bundle_commit(self) -> None:
        review = self.read("workflows/§05-review.md")
        template = self.read("templates/review-summary.template.md")
        self.assertIn("用户只要求复核时", review)
        self.assertIn("保持只读", review)
        self.assertIn("明确要求复核并修订", review)
        self.assertIn("不自动 commit 或 push", review)
        self.assertIn("另行明确授权 commit", review)
        self.assertIn("提交和推送不包含在文档修订中", template)

    def test_review_verdicts_are_evidence_based(self) -> None:
        review = self.read("workflows/§05-review.md")
        template = self.read("templates/review-summary.template.md")
        for verdict in ("采纳", "部分采纳", "不采纳"):
            self.assertIn(verdict, review)
            self.assertIn(verdict, template)
        for evidence in ("报告原编号", "代码", "历史决策", "证据不足"):
            self.assertIn(evidence, review)

    def test_every_catalog_template_exists_and_is_reachable(self) -> None:
        catalog = self.read("rules/documents.md")
        references = set(re.findall(r"`(templates/[^`]+\.template\.md)`", catalog))
        expected = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.joinpath("templates").glob("*.template.md")
        }
        self.assertEqual(references, expected)
        for relative in references:
            self.assertTrue(SKILL_ROOT.joinpath(relative).is_file())

    def test_research_distinguishes_fact_design_and_verification(self) -> None:
        research = self.read("workflows/§01-research.md")
        for source in ("代码", "配置", "测试", "Git", "已有文档"):
            self.assertIn(source, research)
        for distinction in ("已实现", "已验证", "待确认", "不编造"):
            self.assertIn(distinction, research)

    def test_validation_is_scoped_to_selected_documents(self) -> None:
        validation = self.read("workflows/§04-validation.md")
        acceptance = self.read("checklists/acceptance.md")
        self.assertIn("按本次最小计划", validation)
        self.assertIn("本次实际选择或更新", acceptance)
        self.assertIn("模板占位符已清除", validation)
        self.assertIn("自动提交", validation)

    def test_all_local_markdown_references_resolve(self) -> None:
        pattern = re.compile(r"`((?:workflows|templates|rules|checklists)/[^`]+\.md)`")
        for source in SKILL_ROOT.rglob("*.md"):
            for relative in pattern.findall(source.read_text(encoding="utf-8")):
                with self.subTest(source=source.name, reference=relative):
                    self.assertTrue(SKILL_ROOT.joinpath(relative).is_file())


if __name__ == "__main__":
    unittest.main()
