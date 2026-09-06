"""Deterministic contracts for the Codex session-renaming Skill."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "skills"
    / "rename-codex-sessions"
    / "scripts"
    / "codex_sessions.py"
)
SPEC = importlib.util.spec_from_file_location("codex_sessions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
codex_sessions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codex_sessions)


class RenameCodexSessionsTests(unittest.TestCase):
    def test_created_at_is_converted_to_shanghai_without_using_updated_at(self) -> None:
        created_at = datetime(2026, 9, 5, 16, 30, tzinfo=timezone.utc).timestamp()
        self.assertEqual(codex_sessions.created_at_mmdd(created_at), "0906")

    def test_project_filter_keeps_assigned_main_threads_only(self) -> None:
        projects = {
            "local-a": {"id": "local-a", "name": "项目甲"},
            "local-b": {"id": "local-b", "name": "项目乙"},
        }
        assignments = {
            "main-cli": {"projectKind": "local", "projectId": "local-a"},
            "main-app": {"projectKind": "local", "projectId": "local-b"},
            "exec": {"projectKind": "local", "projectId": "local-a"},
            "subagent": {"projectKind": "local", "projectId": "local-a"},
            "remote": {"projectKind": "remote", "projectId": "remote-a"},
        }
        base = {
            "createdAt": 1,
            "name": "旧标题",
            "preview": "旧标题",
            "parentThreadId": None,
        }

        def thread(thread_id: str, source: object) -> dict[str, object]:
            return {**base, "id": thread_id, "source": source}

        self.assertTrue(
            codex_sessions.is_project_main_thread(
                thread("main-cli", "cli"), assignments, projects
            )
        )
        self.assertTrue(
            codex_sessions.is_project_main_thread(
                thread("main-app", "appServer"), assignments, projects
            )
        )
        for thread_id, source in (
            ("exec", "exec"),
            ("subagent", {"subAgent": {"kind": "review"}}),
            ("remote", "cli"),
            ("missing", "cli"),
        ):
            with self.subTest(thread_id=thread_id):
                self.assertFalse(
                    codex_sessions.is_project_main_thread(
                        thread(thread_id, source), assignments, projects
                    )
                )

        child = thread("main-cli", "cli")
        child["parentThreadId"] = "parent"
        self.assertFalse(
            codex_sessions.is_project_main_thread(child, assignments, projects)
        )

    def test_user_and_agent_items_are_reduced_to_semantic_text(self) -> None:
        entries = [
            {
                "turnId": "turn-1",
                "item": {
                    "type": "userMessage",
                    "content": [
                        {"type": "text", "text": "请修复批次文字显示"},
                        {"type": "image", "url": "data:image/png;base64,..."},
                    ],
                },
            },
            {
                "turnId": "turn-1",
                "item": {"type": "agentMessage", "text": "我会检查渲染逻辑。"},
            },
            {
                "turnId": "turn-1",
                "item": {"type": "commandExecution", "command": "pwd"},
            },
        ]
        self.assertEqual(
            codex_sessions.semantic_items(entries),
            [
                {
                    "turnId": "turn-1",
                    "type": "userMessage",
                    "text": "请修复批次文字显示",
                },
                {
                    "turnId": "turn-1",
                    "type": "agentMessage",
                    "text": "我会检查渲染逻辑。",
                },
            ],
        )

    def test_title_validation_is_strict_and_does_not_allow_unknown_types(self) -> None:
        self.assertTrue(codex_sessions.is_valid_title("0903｜优化｜批次文字显示"))
        self.assertTrue(codex_sessions.is_valid_title("0813｜发布｜提交代码到GitHub"))
        for title in (
            "2026-0903｜优化｜批次文字显示",
            "0903|优化|批次文字显示",
            "0903｜测试｜批次文字显示",
            "0903｜优化｜",
            "0903｜优化｜含｜分隔符",
        ):
            with self.subTest(title=title):
                self.assertFalse(codex_sessions.is_valid_title(title))

    def test_list_params_use_created_at_order_and_both_archive_partitions(self) -> None:
        active = codex_sessions.thread_list_params(False)
        archived = codex_sessions.thread_list_params(True)
        self.assertEqual(active["archived"], False)
        self.assertEqual(archived["archived"], True)
        for params in (active, archived):
            self.assertEqual(params["sortKey"], "created_at")
            self.assertEqual(params["sortDirection"], "desc")
            self.assertTrue(params["useStateDbOnly"])
            self.assertEqual(
                params["sourceKinds"], ["appServer", "cli", "vscode"]
            )
        self.assertNotIn("updatedAt", active)

    def test_rename_preflight_distinguishes_renameable_unavailable_and_unknown(self) -> None:
        existing_rollout = str(Path(__file__))
        self.assertEqual(
            codex_sessions.rename_preflight(
                {"id": "active", "path": existing_rollout}, archived=False
            )[0],
            "renameable",
        )
        self.assertEqual(
            codex_sessions.rename_preflight(
                {"id": "archived", "path": existing_rollout}, archived=True
            )[0],
            "no_rollout",
        )
        self.assertEqual(
            codex_sessions.rename_preflight(
                {"id": "missing-rollout", "path": "/does/not/exist.jsonl"},
                archived=False,
            )[0],
            "no_rollout",
        )
        self.assertEqual(
            codex_sessions.rename_preflight(
                {"id": "unknown", "path": None}, archived=False
            )[0],
            "unknown",
        )

    def test_apply_skips_preflight_unavailable_threads_and_reports_write_failures(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, str]]] = []

            def request(self, method: str, params: dict[str, str]) -> object:
                self.requests.append((method, params))
                if params["threadId"] == "write-fails":
                    raise codex_sessions.CodexSessionError("simulated write failure")
                return {}

        candidates = [
            {
                "threadId": "renameable",
                "storedName": "旧标题",
                "renameStatus": "renameable",
                "renameStatusReason": "",
            },
            {
                "threadId": "no-rollout",
                "storedName": "旧标题",
                "renameStatus": "no_rollout",
                "renameStatusReason": "没有可用 Rollout",
            },
            {
                "threadId": "unknown",
                "storedName": "旧标题",
                "renameStatus": "unknown",
                "renameStatusReason": "无法判断",
            },
            {
                "threadId": "write-fails",
                "storedName": "旧标题",
                "renameStatus": "renameable",
                "renameStatusReason": "",
            },
            {
                "threadId": "after-failure",
                "storedName": "旧标题",
                "renameStatus": "renameable",
                "renameStatusReason": "",
            },
        ]
        mapping = {
            "renameable": "0906｜功能｜可改名线程",
            "no-rollout": "0906｜功能｜无Rollout线程",
            "unknown": "0906｜功能｜未知线程",
            "write-fails": "0906｜修复｜写入失败线程",
            "after-failure": "0906｜优化｜失败后继续线程",
        }
        client = FakeClient()

        result = codex_sessions.apply_rename_mapping(client, candidates, mapping)

        self.assertEqual(
            [params["threadId"] for _, params in client.requests],
            ["renameable", "write-fails", "after-failure"],
        )
        self.assertEqual(
            [item["threadId"] for item in result["changed"]],
            ["renameable", "after-failure"],
        )
        self.assertEqual(
            [item["threadId"] for item in result["skipped"]],
            ["no-rollout", "unknown"],
        )
        self.assertEqual(
            [item["threadId"] for item in result["failed"]], ["write-fails"]
        )

    def test_skill_contract_preserves_runtime_gates_and_scope(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "rename-codex-sessions"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        for required in (
            "createdAt",
            "Asia/Shanghai",
            "thread/name/set",
            "renameStatus",
            "no_rollout",
            "skipped",
            "| 原名称 | 新名称 |",
            "确认后",
            "projectless",
            "subAgent",
            "不要修改项目名称",
            "无法判断主题时保留原名",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("updatedAt 作为日期", text)


if __name__ == "__main__":
    unittest.main()
