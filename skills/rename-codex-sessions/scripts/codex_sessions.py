#!/usr/bin/env python3
"""Read and rename eligible Codex Desktop project threads.

The script deliberately exposes only the read operations needed to inspect
threads and the single name-setting operation needed to apply a confirmed
mapping. It does not write Codex's project state.
"""

from __future__ import annotations

import argparse
import json
import re
import select
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ALLOWED_SOURCE_KINDS = ("appServer", "cli", "vscode")
ALLOWED_TYPES = ("功能", "设计", "修复", "优化", "发布", "探索", "文档", "研究")
RENAME_STATUS_RENAMEABLE = "renameable"
RENAME_STATUS_NO_ROLLOUT = "no_rollout"
RENAME_STATUS_UNKNOWN = "unknown"
TITLE_PATTERN = re.compile(
    r"^(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])｜"
    r"(?:功能|设计|修复|优化|发布|探索|文档|研究)｜[^｜\r\n]+$"
)
PAGE_SIZE = 200
READ_TIMEOUT_SECONDS = 30.0


class CodexSessionError(RuntimeError):
    """A readable failure while querying or updating Codex App Server."""


def default_state_file() -> Path:
    return Path.home() / ".codex" / ".codex-global-state.json"


def created_at_mmdd(created_at: int | float) -> str:
    """Convert the App Server's Unix-second createdAt to Asia/Shanghai MMDD."""

    return datetime.fromtimestamp(
        created_at, tz=ZoneInfo("Asia/Shanghai")
    ).strftime("%m%d")


def is_valid_title(title: object) -> bool:
    return isinstance(title, str) and bool(TITLE_PATTERN.fullmatch(title))


def thread_list_params(archived: bool, cursor: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "archived": archived,
        "limit": PAGE_SIZE,
        "sortKey": "created_at",
        "sortDirection": "desc",
        "sourceKinds": list(ALLOWED_SOURCE_KINDS),
        "useStateDbOnly": True,
    }
    if cursor is not None:
        params["cursor"] = cursor
    return params


def load_project_state(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    if not path.is_file():
        raise CodexSessionError(
            f"找不到 Codex Desktop 项目状态：{path}；无法可靠确定项目归属，未执行改名。"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CodexSessionError(f"无法读取 Codex Desktop 项目状态：{exc}") from exc
    if not isinstance(data, dict):
        raise CodexSessionError("Codex Desktop 项目状态不是 JSON 对象，未执行改名。")

    raw_projects = data.get("local-projects")
    raw_assignments = data.get("thread-project-assignments")
    if not isinstance(raw_projects, dict) or not isinstance(raw_assignments, dict):
        raise CodexSessionError(
            "Codex Desktop 项目状态缺少 local-projects 或 thread-project-assignments，"
            "未执行改名。"
        )

    projects: dict[str, dict[str, str]] = {}
    for key, value in raw_projects.items():
        if not isinstance(value, dict):
            continue
        project_id = value.get("id", key)
        if not isinstance(project_id, str) or not project_id:
            continue
        name = value.get("name", "")
        projects[project_id] = {
            "id": project_id,
            "name": name if isinstance(name, str) else "",
        }
    return projects, raw_assignments


def source_kind(thread: dict[str, Any]) -> str:
    source = thread.get("source")
    if isinstance(source, str):
        return source
    if isinstance(source, dict):
        if "subAgent" in source:
            return "subAgent"
        if "custom" in source:
            return "unknown"
    return "unknown"


def is_project_main_thread(
    thread: dict[str, Any],
    assignments: dict[str, Any],
    projects: dict[str, dict[str, str]],
) -> bool:
    thread_id = thread.get("id")
    if not isinstance(thread_id, str) or not thread_id:
        return False
    assignment = assignments.get(thread_id)
    if not isinstance(assignment, dict):
        return False
    if assignment.get("projectKind") != "local":
        return False
    project_id = assignment.get("projectId")
    if not isinstance(project_id, str) or project_id not in projects:
        return False
    if thread.get("parentThreadId"):
        return False
    return source_kind(thread) in ALLOWED_SOURCE_KINDS


def rename_preflight(
    thread: dict[str, Any], archived: bool
) -> tuple[str, str]:
    """Classify rename capability without sending a write request."""

    if archived:
        return (
            RENAME_STATUS_NO_ROLLOUT,
            "当前 Codex App Server 对已归档线程的 thread/name/set 返回 no rollout found。",
        )

    path = thread.get("path")
    if not isinstance(path, str) or not path or not Path(path).is_absolute():
        return (
            RENAME_STATUS_UNKNOWN,
            "线程没有可核对的绝对 Rollout 路径，无法判断改名能力。",
        )
    if not Path(path).is_file():
        return (
            RENAME_STATUS_NO_ROLLOUT,
            "找不到线程对应的 Rollout 文件。",
        )
    return RENAME_STATUS_RENAMEABLE, ""


def display_name(thread: dict[str, Any]) -> str:
    name = thread.get("name")
    if isinstance(name, str) and name.strip():
        return name
    preview = thread.get("preview")
    if isinstance(preview, str):
        return preview
    return ""


def thread_record(
    thread: dict[str, Any],
    archived: bool,
    projects: dict[str, dict[str, str]],
    assignments: dict[str, Any],
) -> dict[str, Any]:
    thread_id = thread["id"]
    assignment = assignments[thread_id]
    project_id = assignment["projectId"]
    created_at = thread.get("createdAt")
    if not isinstance(created_at, (int, float)):
        raise CodexSessionError(f"线程 {thread_id} 缺少有效 createdAt，未纳入改名。")
    stored_name = thread.get("name")
    rename_status, rename_status_reason = rename_preflight(thread, archived)
    return {
        "threadId": thread_id,
        "originalName": display_name(thread),
        "storedName": stored_name if isinstance(stored_name, str) else None,
        "preview": thread.get("preview", ""),
        "createdAt": created_at,
        "dateMMDD": created_at_mmdd(created_at),
        "archived": archived,
        "renameStatus": rename_status,
        "renameStatusReason": rename_status_reason,
        "projectId": project_id,
        "projectName": projects[project_id]["name"],
    }


class AppServerClient:
    """Small JSONL JSON-RPC client for the current Codex App Server CLI."""

    def __init__(
        self,
        codex_binary: str = "codex",
        timeout: float = READ_TIMEOUT_SECONDS,
    ) -> None:
        try:
            self.process = subprocess.Popen(
                [codex_binary, "app-server", "--listen", "stdio://"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise CodexSessionError(
                f"无法启动 Codex App Server（{codex_binary}）：{exc}"
            ) from exc
        self.timeout = timeout
        self.next_id = 1
        try:
            self.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "rename-codex-sessions",
                        "version": "1.0.1",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.notify("initialized", {})
        except Exception:
            self.close()
            raise

    def notify(self, method: str, params: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise CodexSessionError("Codex App Server stdin 已关闭。")
        self.process.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "method": method, "params": params},
                ensure_ascii=False,
            )
            + "\n"
        )
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> Any:
        request_id = self.next_id
        self.next_id += 1
        if self.process.stdin is None:
            raise CodexSessionError("Codex App Server stdin 已关闭。")
        self.process.stdin.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        self.process.stdin.flush()

        if self.process.stdout is None:
            raise CodexSessionError("Codex App Server stdout 已关闭。")
        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], self.timeout)
            if not ready:
                raise CodexSessionError(
                    f"Codex App Server 请求 {method} 超时，未执行后续操作。"
                )
            line = self.process.stdout.readline()
            if not line:
                raise CodexSessionError(
                    f"Codex App Server 在请求 {method} 返回前退出。"
                )
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CodexSessionError(
                    f"Codex App Server 返回了无法解析的消息：{line.strip()}"
                ) from exc
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise CodexSessionError(
                    f"Codex App Server 请求 {method} 失败：{message['error']}"
                )
            return message.get("result")

    def close(self) -> None:
        if self.process.stdin is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        if self.process.poll() is not None:
            return
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def __enter__(self) -> "AppServerClient":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


def list_threads(client: AppServerClient, archived: bool) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        result = client.request("thread/list", thread_list_params(archived, cursor))
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise CodexSessionError("thread/list 返回格式不正确。")
        threads.extend(item for item in result["data"] if isinstance(item, dict))
        next_cursor = result.get("nextCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            return threads
        cursor = next_cursor


def collect_candidates(
    client: AppServerClient, state_file: Path
) -> list[dict[str, Any]]:
    projects, assignments = load_project_state(state_file)
    records: dict[str, dict[str, Any]] = {}
    for archived in (False, True):
        for thread in list_threads(client, archived):
            if not is_project_main_thread(thread, assignments, projects):
                continue
            thread_id = thread["id"]
            if thread_id not in records:
                records[thread_id] = thread_record(
                    thread, archived, projects, assignments
                )
    return sorted(
        records.values(),
        key=lambda record: (record["createdAt"], record["threadId"]),
        reverse=True,
    )


def user_input_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for fragment in content:
        if not isinstance(fragment, dict):
            continue
        if fragment.get("type") == "text" and isinstance(fragment.get("text"), str):
            parts.append(fragment["text"])
    return "\n".join(part for part in parts if part.strip()).strip()


def semantic_items(entries: object) -> list[dict[str, str]]:
    if not isinstance(entries, list):
        return []
    result: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "userMessage":
            text = user_input_text(item.get("content"))
        elif item_type == "agentMessage":
            text = item.get("text", "") if isinstance(item.get("text"), str) else ""
        else:
            continue
        if text:
            turn_id = entry.get("turnId", "")
            result.append(
                {
                    "turnId": turn_id if isinstance(turn_id, str) else "",
                    "type": item_type,
                    "text": text,
                }
            )
    return result


def list_items(client: AppServerClient, thread_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "limit": PAGE_SIZE,
            "sortDirection": "asc",
        }
        if cursor is not None:
            params["cursor"] = cursor
        result = client.request("thread/items/list", params)
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise CodexSessionError("thread/items/list 返回格式不正确。")
        entries.extend(item for item in result["data"] if isinstance(item, dict))
        next_cursor = result.get("nextCursor")
        if not isinstance(next_cursor, str) or not next_cursor:
            return entries
        cursor = next_cursor


def read_candidates(args: argparse.Namespace) -> None:
    with AppServerClient(args.codex, args.timeout) as client:
        candidates = collect_candidates(client, args.state_file)
        candidate = next(
            (item for item in candidates if item["threadId"] == args.thread_id),
            None,
        )
        if candidate is None:
            raise CodexSessionError(
                "目标线程不属于当前 Codex Desktop 本地项目中的主对话，未读取。"
            )
        items = semantic_items(list_items(client, args.thread_id))
    write_json({"thread": candidate, "items": items})


def write_json(value: object) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def load_mapping() -> dict[str, str]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CodexSessionError(f"stdin 不是有效 JSON 映射：{exc}") from exc
    if not isinstance(value, dict) or not value:
        raise CodexSessionError("stdin 必须是非空的 threadId 到新标题 JSON 对象。")
    mapping: dict[str, str] = {}
    for thread_id, title in value.items():
        if not isinstance(thread_id, str) or not thread_id:
            raise CodexSessionError("改名映射包含无效 threadId。")
        if not isinstance(title, str) or not is_valid_title(title):
            raise CodexSessionError(f"线程 {thread_id} 的新标题不符合固定格式：{title!r}")
        mapping[thread_id] = title
    return mapping


def apply_rename_mapping(
    client: AppServerClient,
    candidates: list[dict[str, Any]],
    mapping: dict[str, str],
) -> dict[str, list[dict[str, str]]]:
    by_id = {item["threadId"]: item for item in candidates}
    unknown = sorted(set(mapping) - set(by_id))
    if unknown:
        raise CodexSessionError(
            "改名映射包含当前项目主对话之外的线程，未执行任何改名："
            + ", ".join(unknown)
        )

    result: dict[str, list[dict[str, str]]] = {
        "changed": [],
        "unchanged": [],
        "skipped": [],
        "failed": [],
    }
    for thread_id, title in mapping.items():
        candidate = by_id[thread_id]
        if candidate["storedName"] == title:
            result["unchanged"].append({"threadId": thread_id, "name": title})
            continue
        rename_status = candidate["renameStatus"]
        if rename_status != RENAME_STATUS_RENAMEABLE:
            result["skipped"].append(
                {
                    "threadId": thread_id,
                    "name": title,
                    "status": rename_status,
                    "reason": candidate["renameStatusReason"],
                }
            )
            continue
        try:
            client.request("thread/name/set", {"threadId": thread_id, "name": title})
        except CodexSessionError as exc:
            result["failed"].append(
                {"threadId": thread_id, "name": title, "error": str(exc)}
            )
        else:
            result["changed"].append({"threadId": thread_id, "name": title})
    return result


def apply_mapping(args: argparse.Namespace) -> int:
    mapping = load_mapping()
    with AppServerClient(args.codex, args.timeout) as client:
        candidates = collect_candidates(client, args.state_file)
        result = apply_rename_mapping(client, candidates, mapping)
    write_json(result)
    return 1 if result["failed"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="读取或只通过 thread/name/set 修改 Codex Desktop 项目主对话标题。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--state-file", type=Path, default=default_state_file())
        subparser.add_argument("--codex", default="codex")
        subparser.add_argument("--timeout", type=float, default=READ_TIMEOUT_SECONDS)

    list_parser = subparsers.add_parser("list", help="列出符合范围的项目主对话")
    add_common(list_parser)

    content_parser = subparsers.add_parser("content", help="读取一条项目主对话的语义内容")
    add_common(content_parser)
    content_parser.add_argument("--thread-id", required=True)

    apply_parser = subparsers.add_parser("apply", help="应用确认后的标题映射")
    add_common(apply_parser)
    apply_parser.add_argument(
        "--confirmed",
        action="store_true",
        help="调用方已获得用户对候选表的明确确认",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            with AppServerClient(args.codex, args.timeout) as client:
                write_json({"threads": collect_candidates(client, args.state_file)})
            return 0
        if args.command == "content":
            read_candidates(args)
            return 0
        if args.command == "apply":
            if not args.confirmed:
                raise CodexSessionError(
                    "apply 必须在用户确认候选表后使用 --confirmed；未执行改名。"
                )
            return apply_mapping(args)
        parser.error(f"未知命令：{args.command}")
    except (CodexSessionError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
