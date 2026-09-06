#!/usr/bin/env python3
"""Validate, publish, and synchronize the four Agent Build Kit distributions."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import selectors
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "agent-build-kit@agent-build-kit"
PLUGIN_NAME = "agent-build-kit"
CLARIFY_SKILL = Path("skills/clarify-idea/SKILL.md")
VERSION_FILES = (
    Path(".claude-plugin/plugin.json"),
    Path(".claude-plugin/marketplace.json"),
    Path(".codex-plugin/plugin.json"),
    Path(".zcode-plugin/plugin.json"),
    Path("package.json"),
)
COMMAND_TIMEOUT = 900
ZCODE_TIMEOUT = 120


class SyncError(RuntimeError):
    """A predictable failure in validation, publishing, or client synchronization."""


CommandRunner = Callable[
    [Sequence[str], Path, int], subprocess.CompletedProcess[str]
]


def _tail(value: str, limit: int = 20) -> str:
    lines = [line for line in value.strip().splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


def run_command(
    args: Sequence[str], cwd: Path, timeout: int = COMMAND_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """Run a non-interactive command while keeping its output available to callers."""

    try:
        return subprocess.run(
            [str(arg) for arg in args],
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SyncError(f"找不到命令：{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SyncError(f"命令超时：{shlex.join(map(str, args))}") from exc


def run_checked(
    label: str,
    args: Sequence[str],
    cwd: Path,
    runner: CommandRunner = run_command,
    timeout: int = COMMAND_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    result = runner(args, cwd, timeout)
    if result.returncode != 0:
        details = _tail(result.stderr) or _tail(result.stdout)
        suffix = f"\n{details}" if details else ""
        raise SyncError(f"{label}失败（退出码 {result.returncode}）{suffix}")
    print(f"✓ {label}")
    return result


def read_version(root: Path) -> str:
    versions: dict[Path, str] = {}
    for relative in VERSION_FILES:
        path = root / relative
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if relative == Path(".claude-plugin/marketplace.json"):
                version = data["plugins"][0]["version"]
            else:
                version = data["version"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SyncError(f"无法读取版本文件：{relative}") from exc
        if not isinstance(version, str) or not version:
            raise SyncError(f"版本不是非空字符串：{relative}")
        versions[relative] = version

    unique = set(versions.values())
    if len(unique) != 1:
        detail = ", ".join(f"{path}={version}" for path, version in versions.items())
        raise SyncError(f"五个正式版本号不一致：{detail}")
    return next(iter(unique))


def run_preflight(root: Path, runner: CommandRunner = run_command) -> str:
    """Run the repository's complete local release gate once."""

    version = read_version(root)
    print(f"版本：{version}")

    run_checked(
        "共享文件镜像检查",
        [
            sys.executable,
            str(root / "skills/build-plugin/scripts/sync_shared_files.py"),
            "--root",
            str(root),
        ],
        root,
        runner,
    )
    run_checked(
        "全平台 Plugin 检查",
        [
            sys.executable,
            str(root / "skills/build-plugin/scripts/validate_plugin.py"),
            str(root),
            "--platform",
            "all",
            "--strict",
        ],
        root,
        runner,
    )
    run_checked(
        "Skill 评测资产检查",
        [sys.executable, str(root / "scripts/validate_skill_evals.py"), str(root)],
        root,
        runner,
    )
    run_checked(
        "完整回归测试",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-v",
        ],
        root,
        runner,
    )
    run_checked("工作树空白检查", ["git", "diff", "--check"], root, runner)
    run_checked(
        "暂存区空白检查", ["git", "diff", "--cached", "--check"], root, runner
    )
    return version


def _git_output(
    root: Path,
    args: Sequence[str],
    runner: CommandRunner = run_command,
) -> str:
    result = run_checked("Git 状态读取", ["git", *args], root, runner)
    return result.stdout.strip()


def _git_has_changes(
    root: Path,
    args: Sequence[str],
    runner: CommandRunner = run_command,
) -> bool:
    result = runner(["git", *args], root, COMMAND_TIMEOUT)
    if result.returncode not in (0, 1):
        details = _tail(result.stderr) or _tail(result.stdout)
        raise SyncError(f"Git 检查失败（退出码 {result.returncode}）：{details}")
    return result.returncode == 1


def _git_status(root: Path, runner: CommandRunner = run_command) -> str:
    result = runner(["git", "status", "--short"], root, COMMAND_TIMEOUT)
    if result.returncode != 0:
        details = _tail(result.stderr) or _tail(result.stdout)
        raise SyncError(f"读取 Git 工作树失败：{details}")
    return result.stdout


def commit_and_push(
    root: Path,
    message: str,
    stage_all: bool,
    runner: CommandRunner = run_command,
) -> str:
    """Commit the intended worktree and push main; never pull or force-push."""

    branch = _git_output(root, ["rev-parse", "--abbrev-ref", "HEAD"], runner)
    if branch != "main":
        raise SyncError(f"发布只允许 main 分支，当前是：{branch}")

    remote = _git_output(root, ["remote", "get-url", "origin"], runner)
    if not remote:
        raise SyncError("未配置 origin 远程仓库")

    if not _git_status(root, runner).strip():
        raise SyncError("工作树没有可发布的改动")

    if stage_all:
        run_checked("暂存当前全部改动（--stage）", ["git", "add", "--all"], root, runner)
    else:
        untracked = _git_output(
            root, ["ls-files", "--others", "--exclude-standard"], runner
        )
        if _git_has_changes(root, ["diff", "--quiet"], runner) or untracked:
            raise SyncError("存在未暂存或未跟踪改动；明确添加 --stage，或先手动整理暂存区")

    if not _git_has_changes(root, ["diff", "--cached", "--quiet"], runner):
        raise SyncError("暂存区没有可提交的改动")

    run_checked(
        "提交前暂存区空白检查", ["git", "diff", "--cached", "--check"], root, runner
    )
    run_checked("创建提交", ["git", "commit", "-m", message], root, runner)
    run_checked("推送 origin/main", ["git", "push", "origin", "main"], root, runner)
    commit = _git_output(root, ["rev-parse", "HEAD"], runner)
    print(f"提交：{commit}")
    return commit


def _json_output(result: subprocess.CompletedProcess[str], label: str) -> Any:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SyncError(f"{label}没有返回有效 JSON") from exc


def _find_entry(entries: Any, plugin_id: str, label: str) -> dict[str, Any]:
    if isinstance(entries, dict):
        entries = entries.get("installed")
    if not isinstance(entries, list):
        raise SyncError(f"{label}返回的插件列表格式不正确")
    for entry in entries:
        if isinstance(entry, dict) and (
            entry.get("id") == plugin_id or entry.get("pluginId") == plugin_id
        ):
            return entry
    raise SyncError(f"{label}找不到 {plugin_id}")


def _verify_skill_path(path: Path, label: str) -> None:
    if not (path / CLARIFY_SKILL).is_file():
        raise SyncError(f"{label}缺少 {CLARIFY_SKILL}")


def sync_claude(
    root: Path, version: str, runner: CommandRunner = run_command
) -> None:
    run_checked(
        "Claude Code Marketplace 更新",
        ["claude", "plugin", "marketplace", "update", PLUGIN_NAME],
        root,
        runner,
    )
    run_checked(
        "Claude Code Plugin 更新",
        ["claude", "plugin", "update", PLUGIN_ID, "--scope", "user"],
        root,
        runner,
    )
    result = run_checked(
        "Claude Code 安装核验", ["claude", "plugin", "list", "--json"], root, runner
    )
    entry = _find_entry(_json_output(result, "Claude Code"), PLUGIN_ID, "Claude Code")
    if entry.get("version") != version:
        raise SyncError(f"Claude Code 版本为 {entry.get('version')}，预期 {version}")
    install_path = Path(str(entry.get("installPath", "")))
    _verify_skill_path(install_path, "Claude Code")


def _codex_cache_path(version: str, home: Path | None = None) -> Path:
    base = home or Path.home()
    return base / ".codex/plugins/cache/agent-build-kit/agent-build-kit" / version


def sync_codex(
    root: Path, version: str, runner: CommandRunner = run_command
) -> None:
    run_checked(
        "Codex Marketplace 升级",
        ["codex", "plugin", "marketplace", "upgrade", PLUGIN_NAME, "--json"],
        root,
        runner,
    )
    run_checked(
        "Codex Plugin 重新安装",
        ["codex", "plugin", "add", PLUGIN_ID, "--json"],
        root,
        runner,
    )
    result = run_checked(
        "Codex 安装核验", ["codex", "plugin", "list", "--json"], root, runner
    )
    entry = _find_entry(_json_output(result, "Codex"), PLUGIN_ID, "Codex")
    if entry.get("version") != version:
        raise SyncError(f"Codex 版本为 {entry.get('version')}，预期 {version}")

    cache_path = _codex_cache_path(version)
    _verify_skill_path(cache_path, "Codex 当前缓存")

    source = entry.get("source")
    if isinstance(source, dict) and source.get("path"):
        _verify_skill_path(Path(str(source["path"])), "Codex Marketplace 快照")


def _pi_package_path() -> Path:
    return Path.home() / ".pi/agent/git/github.com/koco-co/agent-build-kit"


def sync_pi(root: Path, version: str, runner: CommandRunner = run_command) -> None:
    run_checked(
        "Pi Package 更新",
        ["pi", "update", "--extension", "git:github.com/koco-co/agent-build-kit"],
        root,
        runner,
    )
    package_path = _pi_package_path()
    try:
        package = json.loads((package_path / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"Pi Package 缺少或无法读取 {package_path / 'package.json'}") from exc
    if package.get("version") != version:
        raise SyncError(f"Pi 版本为 {package.get('version')}，预期 {version}")
    _verify_skill_path(package_path, "Pi Package")


def _find_node() -> str:
    node = os.environ.get("ZCODE_NODE") or shutil.which("node")
    if not node:
        raise SyncError("找不到 Node.js；可通过 ZCODE_NODE 指定")
    return node


def _find_zcode_cli() -> Path:
    configured = os.environ.get("ZCODE_CLI")
    candidates = [
        Path(configured) if configured else None,
        Path("/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise SyncError("找不到 ZCode app-server；可通过 ZCODE_CLI 指定 zcode.cjs")


def _zcode_app_version(cli: Path) -> str | None:
    configured = os.environ.get("ZCODE_APP_VERSION")
    if configured:
        return configured
    info = cli.parents[2] / "Info.plist"
    if not info.is_file():
        return None
    try:
        with info.open("rb") as stream:
            value = plistlib.load(stream).get("CFBundleShortVersionString")
    except (OSError, plistlib.InvalidFileException):
        return None
    return value if isinstance(value, str) else None


def zcode_request(
    root: Path,
    method: str,
    params: dict[str, Any],
    timeout: int = ZCODE_TIMEOUT,
) -> dict[str, Any]:
    """Call ZCode's shipped app-server over stdio without editing ZCode state files."""

    node = _find_node()
    cli = _find_zcode_cli()
    environment = os.environ.copy()
    app_version = _zcode_app_version(cli)
    if app_version:
        environment["ZCODE_APP_VERSION"] = app_version

    try:
        process = subprocess.Popen(
            [node, str(cli), "app-server", "--stdio"],
            cwd=str(root),
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise SyncError(f"无法启动 ZCode app-server：{exc}") from exc

    request_id = 1
    request = {"id": request_id, "method": method, "params": params}
    selector = selectors.DefaultSelector()
    try:
        if process.stdin is None or process.stdout is None:
            raise SyncError("ZCode app-server 未提供标准输入输出")
        process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        process.stdin.flush()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready = selector.select(remaining)
            if not ready:
                break
            line = process.stdout.readline()
            if not line:
                break
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") != request_id:
                continue
            if response.get("error"):
                raise SyncError(f"ZCode {method}失败：{response['error']}")
            result = response.get("result")
            if not isinstance(result, dict):
                raise SyncError(f"ZCode {method}返回格式不正确")
            return result
        raise SyncError(f"ZCode {method}超时或未返回结果")
    finally:
        selector.close()
        if process.stdin is not None:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def _zcode_workspace(root: Path) -> dict[str, str]:
    path = str(root)
    return {"workspacePath": path, "workspaceKey": path}


def sync_zcode(root: Path, version: str) -> None:
    workspace = _zcode_workspace(root)
    zcode_request(
        root,
        "plugins/marketplace/update",
        {"workspace": workspace, "marketplace": PLUGIN_NAME},
    )
    overview = zcode_request(
        root,
        "plugins/update",
        {"workspace": workspace, "pluginId": PLUGIN_ID},
    )
    overview = zcode_request(root, "plugins/overview", {"workspace": workspace})
    entry = _find_entry(overview.get("installedPlugins"), PLUGIN_ID, "ZCode")
    if entry.get("version") != version:
        raise SyncError(f"ZCode 版本为 {entry.get('version')}，预期 {version}")
    install_path = Path(str(entry.get("installPath", "")))
    _verify_skill_path(install_path, "ZCode")
    print("✓ ZCode Marketplace、Plugin 更新与安装核验")


def sync_clients(root: Path, version: str) -> None:
    actions = (
        ("Claude Code", sync_claude),
        ("Codex", sync_codex),
        ("ZCode", sync_zcode),
        ("Pi", sync_pi),
    )
    failures: list[str] = []
    for label, action in actions:
        try:
            action(root, version)
            print(f"✓ {label} 已同步到 {version}")
        except SyncError as exc:
            failures.append(f"{label}：{exc}")
            print(f"✗ {label} 同步失败：{exc}", file=sys.stderr)
    if failures:
        raise SyncError("；".join(failures))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="一次完成 Agent Build Kit 的发布前验证和四端同步。"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="仓库根目录（默认：当前脚本所在仓库）",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="验证后提交并推送 main，再更新 Claude Code、Codex、ZCode、Pi",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="发布时暂存当前全部改动；不指定时只接受已整理好的暂存区",
    )
    parser.add_argument("--message", help="发布提交信息（与 --publish 一起使用）")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.stage and not args.publish:
        print("--stage 只能与 --publish 一起使用", file=sys.stderr)
        return 2
    if args.publish and not args.message:
        print("--publish 需要 --message", file=sys.stderr)
        return 2

    try:
        version = run_preflight(root)
        if not args.publish:
            print("仅完成本地预检；需要提交、推送和四端更新时使用 --publish。")
            return 0
        commit_and_push(root, args.message, args.stage)
        sync_clients(root, version)
        print(f"完成：{version} 已提交、推送并同步到四个分发。")
        return 0
    except SyncError as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
