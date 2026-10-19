#!/usr/bin/env python3
"""Install a source Skill into Claude Code, Codex, ZCode, Pi, or DeepSeek Harness.

The repository is distributed as a Plugin or package for the first four platforms.
DeepSeek Harness reads a user or project skills directory directly, so it gets a
standalone copy instead of a manifest-based package.
- Claude Code preserves the source frontmatter and removes Codex UI metadata.
- Codex removes Claude-only frontmatter and keeps agents/openai.yaml.
- ZCode, Pi, and DeepSeek Harness preserve the source frontmatter (unrecognized
  keys are ignored) and remove Codex UI metadata.
Repository-internal symlinks are dereferenced in the installed copy.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PORTABLE_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
FULL_PACKAGE_ONLY_SKILLS = {"audit-agent-setup"}


class InstallError(RuntimeError):
    """Raised when an installation cannot be completed safely."""


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int]:
    if not lines or lines[0].strip() != "---":
        raise InstallError("SKILL.md 缺少起始 Frontmatter 分隔符。")
    try:
        closing = next(
            index for index in range(1, len(lines)) if lines[index].strip() == "---"
        )
    except StopIteration as exc:
        raise InstallError("SKILL.md 缺少结束 Frontmatter 分隔符。") from exc
    return 0, closing


def strip_claude_frontmatter(skill_md: str) -> str:
    """Keep only portable frontmatter fields in Codex standalone copies."""
    lines = skill_md.splitlines()
    _opening, closing = _frontmatter_bounds(lines)
    output = [lines[0]]
    keep_current_block = True
    for line in lines[1:closing]:
        match = re.match(r"^([A-Za-z0-9_-]+):", line)
        if match:
            keep_current_block = match.group(1) in PORTABLE_FRONTMATTER_FIELDS
        if keep_current_block:
            output.append(line)
    output.extend(lines[closing:])
    suffix = "\n" if skill_md.endswith("\n") else ""
    return "\n".join(output) + suffix


def resolve_destination(
    *,
    skill_name: str,
    platform: str,
    scope: str,
    project_dir: Path | None = None,
    home_dir: Path | None = None,
) -> Path:
    if platform not in {"claude", "codex", "zcode", "pi", "dsh"}:
        raise InstallError(f"不支持的平台：{platform}")
    if scope not in {"user", "project"}:
        raise InstallError(f"不支持的安装范围：{scope}")

    platform_roots = {
        "claude": ".claude",
        "codex": ".agents",
        "zcode": ".zcode",
        "pi": ".pi/agent" if scope == "user" else ".pi",
        "dsh": ".dsh",
    }
    if scope == "user":
        if platform == "dsh" and home_dir is None and os.environ.get("DSH_HOME"):
            return (
                Path(os.environ["DSH_HOME"]).expanduser().resolve()
                / "skills"
                / skill_name
            )
        base = (home_dir or Path.home()).expanduser().resolve()
    else:
        base = (project_dir or Path.cwd()).expanduser().resolve()
    return base / platform_roots[platform] / "skills" / skill_name


def run_validator(
    validator: Path,
    skill_dir: Path,
    profile: str,
    *,
    plugin_root: Path | None = None,
) -> None:
    if not validator.is_file():
        raise InstallError(f"找不到校验脚本：{validator}")

    command = [
        sys.executable,
        str(validator),
        str(skill_dir),
        "--profile",
        profile,
        "--strict",
    ]
    if plugin_root is not None:
        command.extend(["--plugin-root", str(plugin_root)])

    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        details = "\n".join(
            part
            for part in (completed.stdout.strip(), completed.stderr.strip())
            if part
        )
        raise InstallError(f"Skill 校验失败：\n{details}")


def install_skill(
    *,
    repo_root: Path,
    skill_name: str,
    platform: str,
    scope: str,
    project_dir: Path | None = None,
    home_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> Path:
    if not NAME_PATTERN.fullmatch(skill_name):
        raise InstallError("Skill 名称只能包含小写字母、数字及分隔词组的单个连字符。")
    if skill_name in FULL_PACKAGE_ONLY_SKILLS:
        raise InstallError(
            f"{skill_name} 只能随 agent-build-kit 完整分发包使用，不能独立安装。"
        )

    repo_root = repo_root.expanduser().resolve()
    source = repo_root / "skills" / skill_name
    validator = repo_root / "skills" / "build-skill" / "scripts" / "validate_skill.py"

    if scope == "project":
        project_root = (project_dir or Path.cwd()).expanduser().resolve()
        if not project_root.is_dir():
            raise InstallError(f"项目目录不存在或不是目录：{project_root}")

    destination = resolve_destination(
        skill_name=skill_name,
        platform=platform,
        scope=scope,
        project_dir=project_dir,
        home_dir=home_dir,
    )

    if not source.is_dir():
        raise InstallError(f"找不到 Skill 源目录：{source}")
    if not (source / "SKILL.md").is_file():
        raise InstallError(f"源目录缺少 SKILL.md：{source}")
    if destination.is_symlink():
        raise InstallError(f"目标目录是符号链接，拒绝覆盖：{destination}")
    if destination.exists() and not force:
        raise InstallError(
            f"目标目录已存在：{destination}\n确认覆盖后重新执行并添加 --force。"
        )

    run_validator(validator, source, "dual", plugin_root=repo_root)

    temp_parent: Path | None = None
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_parent = destination.parent

    with tempfile.TemporaryDirectory(
        prefix=f".{skill_name}-install-",
        dir=temp_parent,
    ) as temp_root:
        stage = Path(temp_root) / skill_name
        # symlinks=False is intentional: shared repository files become a
        # self-contained standalone installation without duplicating source files.
        shutil.copytree(
            source,
            stage,
            symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )

        skill_md = stage / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        if platform == "codex":
            skill_md.write_text(
                strip_claude_frontmatter(text),
                encoding="utf-8",
            )
            profile = "codex"
        else:
            # Claude Code keeps the full frontmatter; ZCode, Pi, and DeepSeek
            # Harness ignore unsupported keys at load time. All drop Codex metadata.
            agents = stage / "agents"
            if agents.exists():
                shutil.rmtree(agents)
            profile = platform

        run_validator(validator, stage, profile, plugin_root=stage)

        if dry_run:
            return destination

        backup: Path | None = None
        if destination.exists():
            backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
            if backup.exists():
                shutil.rmtree(backup)
            destination.replace(backup)

        try:
            stage.replace(destination)
        except OSError:
            if backup is not None and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
        else:
            if backup is not None and backup.exists():
                shutil.rmtree(backup)

    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="为 Claude Code、Codex、ZCode、Pi 或 DeepSeek Harness 安装独立的 Skill 副本。"
    )
    parser.add_argument("skill", help="skills/ 下的 Skill 目录名")
    parser.add_argument(
        "--platform",
        choices=("claude", "codex", "zcode", "pi", "dsh"),
        required=True,
    )
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument(
        "--project-dir",
        type=Path,
        help="项目级安装的目标仓库；省略时使用当前目录",
    )
    parser.add_argument("--force", action="store_true", help="覆盖已有安装")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="校验并准备平台专用副本，但不写入目标目录",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    try:
        destination = install_skill(
            repo_root=repo_root,
            skill_name=args.skill,
            platform=args.platform,
            scope=args.scope,
            project_dir=args.project_dir,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (InstallError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    action = "校验通过，计划安装到" if args.dry_run else "安装完成"
    print(f"{action}：{destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
