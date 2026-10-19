#!/usr/bin/env python3
"""Dependency-free structural validator for Agent Skills.

The validator supports portable, Claude Code, Codex, ZCode, Pi, DSH, and
multi-platform source profiles. Relative symlinks are allowed only when their resolved targets
remain inside the containing Plugin root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Union

STANDARD_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
CLAUDE_EXTENSION_KEYS = {
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
}
RECOMMENDED_HEADINGS = (
    "# Outcome",
    "## Routing",
    "## Steps",
    "## Rules",
    "## References",
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$")
NESTED_KEY_RE = re.compile(r"^\s+([A-Za-z0-9_.-]+):(?:\s*(.*))?$")
LOCAL_REFERENCE_RE = re.compile(
    r"`((?:workflows|templates|examples|rules|scripts|checklists|prompts|references|assets|agents)/[^`\s]+)`"
)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
WORKFLOW_RE = re.compile(r"^§(\d{2})-[^/]+\.md$")
AGENT_PROMPT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.agent\.md$")
Scalar = Union[str, dict[str, str]]


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


@dataclass
class Report:
    skill_dir: str
    profile: str
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def infos(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "info"]

    def to_dict(self) -> dict[str, object]:
        return {
            "skill_dir": self.skill_dir,
            "profile": self.profile,
            "status": "pass" if not self.errors else "fail",
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.infos),
            "issues": [asdict(issue) for issue in self.issues],
        }


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[Mapping[str, Scalar], int, str | None]:
    """Parse top-level scalars, nested maps, and block scalars without PyYAML."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0, "缺少起始 Frontmatter 分隔符。"

    try:
        closing = next(
            index for index in range(1, len(lines)) if lines[index].strip() == "---"
        )
    except StopIteration:
        return {}, 0, "缺少结束 Frontmatter 分隔符。"

    data: dict[str, Scalar] = {}
    current_parent: str | None = None
    index = 1
    while index < closing:
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        top_match = TOP_LEVEL_KEY_RE.match(raw)
        if top_match and not raw.startswith((" ", "\t")):
            key, raw_value = top_match.groups()
            value = (raw_value or "").strip()
            current_parent = None

            if value in {"|", ">", "|-", ">-", "|+", ">+"}:
                block_lines: list[str] = []
                index += 1
                while index < closing and (
                    not lines[index].strip() or lines[index].startswith((" ", "\t"))
                ):
                    block_lines.append(lines[index].strip())
                    index += 1
                separator = "\n" if value.startswith("|") else " "
                data[key] = separator.join(block_lines).strip()
                continue

            if value == "":
                data[key] = {}
                current_parent = key
            else:
                data[key] = unquote(value)
            index += 1
            continue

        if raw.startswith((" ", "\t")) and current_parent is not None:
            nested_match = NESTED_KEY_RE.match(raw)
            if nested_match and isinstance(data.get(current_parent), dict):
                nested_key, nested_value = nested_match.groups()
                nested_map = data[current_parent]
                assert isinstance(nested_map, dict)
                if nested_value and nested_value.strip():
                    nested_map[nested_key] = unquote(nested_value.strip())
            index += 1
            continue

        return data, closing, f"无法解析 Frontmatter 第 {index + 1} 行：{raw!r}"

    return data, closing, None


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def discover_plugin_root(skill_dir: Path) -> Path:
    """Return the nearest ancestor containing a Claude or Codex plugin manifest."""
    current = skill_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".claude-plugin" / "plugin.json").is_file() or (
            candidate / ".codex-plugin" / "plugin.json"
        ).is_file():
            return candidate
    return current


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)) or "."
    except ValueError:
        return str(path)


def add_issue(
    issues: list[Issue],
    severity: str,
    code: str,
    path: Path,
    message: str,
    root: Path,
) -> None:
    issues.append(Issue(severity, code, display_path(path, root), message))


def validate_frontmatter(
    *,
    data: Mapping[str, Scalar],
    profile: str,
    skill_dir: Path,
    skill_md: Path,
    issues: list[Issue],
) -> None:
    # DSH tolerates unknown keys, so it does not reject source fields that
    # belong to another platform. The canonical invocation keys still have to
    # be spelled correctly, because DSH drops a Skill that uses legacy names.
    if profile != "dsh":
        allowed = set(STANDARD_KEYS)
        if profile in {"claude", "dual", "zcode", "pi"}:
            # Pi loads disable-model-invocation and ignores other unknown source
            # fields, so a shared multi-platform SKILL.md remains loadable.
            allowed.update(CLAUDE_EXTENSION_KEYS)

        for key in data:
            if key not in allowed:
                add_issue(
                    issues,
                    "error",
                    "FRONTMATTER_KEY",
                    skill_md,
                    f"{profile} 配置不允许 Frontmatter 字段 {key!r}。",
                    skill_dir,
                )
    else:
        for legacy, canonical in (
            ("disableModelInvocation", "disable-model-invocation"),
            ("modelInvocable", "disable-model-invocation"),
            ("userInvocable", "user-invocable"),
        ):
            if legacy in data:
                add_issue(
                    issues,
                    "error",
                    "LEGACY_INVOCATION_KEY",
                    skill_md,
                    f"DSH 不支持 {legacy!r}，请改用 {canonical!r}；否则整个 Skill 会被丢弃。",
                    skill_dir,
                )

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        add_issue(
            issues,
            "error",
            "NAME_REQUIRED",
            skill_md,
            "name 必须是非空字符串。",
            skill_dir,
        )
    else:
        if len(name) > 64 or not NAME_RE.fullmatch(name):
            add_issue(
                issues,
                "error",
                "NAME_FORMAT",
                skill_md,
                "name 长度必须为 1–64 个字符，只能包含小写字母、数字和连字符；连字符不能连续，也不能位于开头或结尾。",
                skill_dir,
            )
        if name != skill_dir.name:
            add_issue(
                issues,
                "error",
                "NAME_DIRECTORY_MISMATCH",
                skill_md,
                f"name {name!r} 必须与父目录 {skill_dir.name!r} 一致。",
                skill_dir,
            )

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        add_issue(
            issues,
            "error",
            "DESCRIPTION_REQUIRED",
            skill_md,
            "description 必须是非空字符串。",
            skill_dir,
        )
    elif len(description) > 1024:
        add_issue(
            issues,
            "error",
            "DESCRIPTION_LENGTH",
            skill_md,
            f"description 长度为 {len(description)}，超过 1024 字符。",
            skill_dir,
        )
    elif profile == "dsh" and len(description) > 500:
        add_issue(
            issues,
            "warning",
            "DESCRIPTION_DSH_LENGTH",
            skill_md,
            f"description 长度为 {len(description)}，超过 DSH 目录的 500 字符展示上限；触发条件可能被截断。",
            skill_dir,
        )

    if "compatibility" in data:
        compatibility = data.get("compatibility")
        if not isinstance(compatibility, str) or not compatibility.strip():
            add_issue(
                issues,
                "error",
                "COMPATIBILITY_EMPTY",
                skill_md,
                "compatibility 存在时必须描述非空的硬性环境要求；没有要求时应删除该字段。",
                skill_dir,
            )
        else:
            if len(compatibility) > 500:
                add_issue(
                    issues,
                    "error",
                    "COMPATIBILITY_LENGTH",
                    skill_md,
                    "compatibility 超过 500 字符。",
                    skill_dir,
                )
            if re.search(r"当前适配|目前(?:仅)?适配", compatibility):
                add_issue(
                    issues,
                    "warning",
                    "COMPATIBILITY_TEMPORAL",
                    skill_md,
                    "compatibility 不应使用容易过时的泛化适配声明；只保留硬性环境要求。",
                    skill_dir,
                )

    if profile in {"claude", "dual", "zcode", "pi", "dsh"}:
        manual = data.get("disable-model-invocation")
        if manual is not None and str(manual).lower() not in {"true", "false"}:
            add_issue(
                issues,
                "error",
                "CLAUDE_BOOLEAN",
                skill_md,
                "disable-model-invocation 必须是 true 或 false。",
                skill_dir,
            )


def validate_headings(
    text: str, skill_dir: Path, skill_md: Path, issues: list[Issue]
) -> None:
    """Treat the five-key skeleton as a recommendation, not a contract.

    The keys are a default skeleton authors may trim, rename, or restructure;
    omission rules live in the target skill's architecture rules when present.
    Duplicated top-level keys
    still warn (they almost always indicate confusion), and deviation from
    the default skeleton is reported as informational guidance that never
    fails strict validation.
    """
    positions: dict[str, int] = {}
    for heading in RECOMMENDED_HEADINGS:
        matches = [
            match.start()
            for match in re.finditer(rf"(?m)^{re.escape(heading)}\s*$", text)
        ]
        if len(matches) > 1:
            add_issue(
                issues,
                "warning",
                "HEADING_DUPLICATE",
                skill_md,
                f"章节标题重复：{heading}",
                skill_dir,
            )
        if matches:
            positions[heading] = matches[0]

    present = [heading for heading in RECOMMENDED_HEADINGS if heading in positions]
    complete = len(present) == len(RECOMMENDED_HEADINGS)
    ordered = positions and [positions[heading] for heading in present] == sorted(
        positions[heading] for heading in present
    )
    if not (complete and ordered):
        missing = "、".join(
            heading.lstrip("# ")
            for heading in RECOMMENDED_HEADINGS
            if heading not in positions
        )
        detail = f"未采用的推荐章节：{missing}" if missing else "顺序与推荐不同"
        add_issue(
            issues,
            "info",
            "HEADING_SKELETON",
            skill_md,
            f"未采用默认推荐章节结构（{detail}）；"
            "Outcome/Routing/Steps/Rules/References 为建议而非必需，"
            "确认结构满足内容需要即可；省略准则见该 Skill 的架构规则（若存在）。",
            skill_dir,
        )


def iter_local_references(text: str) -> Iterable[str]:
    yielded = set()
    for match in LOCAL_REFERENCE_RE.finditer(text):
        reference = match.group(1).strip()
        if reference not in yielded:
            yielded.add(reference)
            yield reference

    for match in MARKDOWN_LINK_RE.finditer(text):
        reference = match.group(1).strip().split(maxsplit=1)[0]
        if reference.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if reference not in yielded:
            yielded.add(reference)
            yield reference


def validate_references(
    text: str,
    skill_dir: Path,
    skill_md: Path,
    plugin_root: Path,
    issues: list[Issue],
) -> None:
    lexical_root = skill_dir.absolute()
    resolved_plugin_root = plugin_root.resolve()

    for reference in iter_local_references(text):
        normalized = reference.split("#", 1)[0]
        if not normalized:
            continue

        lexical_candidate = Path(os.path.abspath(skill_dir / normalized))
        if not is_within(lexical_candidate, lexical_root):
            add_issue(
                issues,
                "error",
                "REF_OUTSIDE_SKILL",
                skill_md,
                f"引用路径越过 Skill 根目录：{reference}",
                skill_dir,
            )
            continue

        try:
            resolved = (skill_dir / normalized).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            add_issue(
                issues,
                "error",
                "REF_RESOLVE",
                skill_md,
                f"无法解析引用 {reference}：{exc}",
                skill_dir,
            )
            continue

        if not is_within(resolved, resolved_plugin_root):
            add_issue(
                issues,
                "error",
                "REF_OUTSIDE_PLUGIN",
                skill_md,
                f"引用最终目标越过 Plugin 根目录：{reference}",
                skill_dir,
            )
            continue

        if not (skill_dir / normalized).exists():
            add_issue(
                issues,
                "error",
                "REF_NOT_FOUND",
                skill_md,
                f"引用的路径不存在：{reference}",
                skill_dir,
            )


def validate_workflows(
    skill_dir: Path, skill_md_text: str, issues: list[Issue]
) -> None:
    workflow_dir = skill_dir / "workflows"
    if not workflow_dir.exists():
        return
    if not workflow_dir.is_dir():
        add_issue(
            issues,
            "error",
            "WORKFLOW_NOT_DIR",
            workflow_dir,
            "workflows 必须是目录。",
            skill_dir,
        )
        return

    numbered: list[tuple[int, Path]] = []
    for path in sorted(workflow_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        match = WORKFLOW_RE.fullmatch(path.name)
        if not match:
            add_issue(
                issues,
                "error",
                "WORKFLOW_NAME",
                path,
                "工作流文件必须使用 §NN-name.md 格式。",
                skill_dir,
            )
            continue
        numbered.append((int(match.group(1)), path))
        relative = path.relative_to(skill_dir).as_posix()
        if f"`{relative}`" not in skill_md_text:
            add_issue(
                issues,
                "warning",
                "WORKFLOW_UNREFERENCED",
                path,
                "SKILL.md 未使用反引号包裹的路径引用该工作流。",
                skill_dir,
            )

    numbers = [number for number, _ in numbered]
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        add_issue(
            issues,
            "error",
            "WORKFLOW_SEQUENCE",
            workflow_dir,
            f"工作流编号必须从 01 连续递增；实际为 {numbers}。",
            skill_dir,
        )


def validate_symlink(
    path: Path, skill_dir: Path, plugin_root: Path, issues: list[Issue]
) -> None:
    try:
        target = os.readlink(path)
    except OSError as exc:
        add_issue(
            issues,
            "error",
            "SYMLINK_READ",
            path,
            f"无法读取软链接：{exc}",
            skill_dir,
        )
        return

    if Path(target).is_absolute():
        add_issue(
            issues,
            "error",
            "SYMLINK_ABSOLUTE",
            path,
            "软链接必须使用相对路径。",
            skill_dir,
        )
        return

    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        add_issue(
            issues,
            "error",
            "SYMLINK_RESOLVE",
            path,
            f"无法解析软链接：{exc}",
            skill_dir,
        )
        return

    if not is_within(resolved, plugin_root.resolve()):
        add_issue(
            issues,
            "error",
            "SYMLINK_OUTSIDE_PLUGIN",
            path,
            f"软链接目标越过 Plugin 根目录：{target}",
            skill_dir,
        )
        return

    if not path.exists():
        add_issue(
            issues,
            "error",
            "SYMLINK_BROKEN",
            path,
            f"软链接目标不存在：{target}",
            skill_dir,
        )


def validate_directory_conventions(
    skill_dir: Path,
    plugin_root: Path,
    issues: list[Issue],
) -> None:
    template_dir = skill_dir / "templates"
    if template_dir.is_dir():
        for path in template_dir.iterdir():
            if (path.is_file() or path.is_symlink()) and ".template." not in path.name:
                add_issue(
                    issues,
                    "error",
                    "TEMPLATE_NAME",
                    path,
                    "模板文件名必须包含 .template.。",
                    skill_dir,
                )

    example_dir = skill_dir / "examples"
    if example_dir.is_dir():
        for path in example_dir.iterdir():
            if (path.is_file() or path.is_symlink()) and ".example." not in path.name:
                add_issue(
                    issues,
                    "error",
                    "EXAMPLE_NAME",
                    path,
                    "示例文件名必须包含 .example.。",
                    skill_dir,
                )

    prompts_dir = skill_dir / "prompts"
    if prompts_dir.is_dir():
        for path in prompts_dir.iterdir():
            if path.is_file() or path.is_symlink():
                if not AGENT_PROMPT_RE.fullmatch(path.name):
                    add_issue(
                        issues,
                        "error",
                        "AGENT_PROMPT_NAME",
                        path,
                        "prompts/ 文件必须使用 <name>.agent.md 格式。",
                        skill_dir,
                    )

    for path in skill_dir.rglob("*"):
        if path.is_symlink():
            validate_symlink(path, skill_dir, plugin_root, issues)
            continue

        if path.is_file():
            try:
                size = path.stat().st_size
            except OSError as exc:
                add_issue(
                    issues,
                    "error",
                    "FILE_STAT",
                    path,
                    f"无法读取文件信息：{exc}",
                    skill_dir,
                )
                continue
            if size == 0:
                add_issue(issues, "error", "EMPTY_FILE", path, "文件为空。", skill_dir)
            if " " in path.name:
                add_issue(
                    issues,
                    "warning",
                    "FILENAME_SPACE",
                    path,
                    "文件名包含空格。",
                    skill_dir,
                )


def read_openai_policy(adapter: Path) -> str | None:
    if not adapter.exists():
        return None
    try:
        text = adapter.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = re.search(
        r"(?m)^\s*allow_implicit_invocation\s*:\s*(\S+)\s*$",
        text,
    )
    return match.group(1).lower() if match else None


def validate_openai_adapter(
    skill_dir: Path,
    profile: str,
    frontmatter: Mapping[str, Scalar],
    issues: list[Issue],
) -> None:
    adapter = skill_dir / "agents" / "openai.yaml"
    if not adapter.exists():
        if (
            profile == "dual"
            and str(frontmatter.get("disable-model-invocation", "")).lower() == "true"
        ):
            add_issue(
                issues,
                "error",
                "OPENAI_ADAPTER_REQUIRED",
                adapter,
                "双平台仅限用户调用的 Skill 必须提供 agents/openai.yaml。",
                skill_dir,
            )
        return

    try:
        text = adapter.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_issue(
            issues,
            "error",
            "OPENAI_ADAPTER_READ",
            adapter,
            f"无法读取适配文件：{exc}",
            skill_dir,
        )
        return

    matches = list(
        re.finditer(
            r"(?m)^\s*allow_implicit_invocation\s*:\s*(\S+)\s*$",
            text,
        )
    )
    for match in matches:
        if match.group(1).lower() not in {"true", "false"}:
            add_issue(
                issues,
                "error",
                "OPENAI_POLICY_BOOLEAN",
                adapter,
                "allow_implicit_invocation 必须是 true 或 false。",
                skill_dir,
            )

    if (
        profile == "dual"
        and str(frontmatter.get("disable-model-invocation", "")).lower() == "true"
        and read_openai_policy(adapter) != "false"
    ):
        add_issue(
            issues,
            "error",
            "MANUAL_POLICY_MISMATCH",
            adapter,
            "Claude Code 已设置仅限用户调用时，Codex 也必须设置 allow_implicit_invocation: false。",
            skill_dir,
        )


def validate_skill(
    skill_dir: Path,
    profile: str = "portable",
    plugin_root: Path | None = None,
) -> Report:
    skill_dir = skill_dir.expanduser().resolve()
    issues: list[Issue] = []

    if not skill_dir.is_dir():
        issues.append(
            Issue("error", "SKILL_DIR", str(skill_dir), "Skill 目录不存在或不是目录。")
        )
        return Report(str(skill_dir), profile, issues)

    effective_plugin_root = (
        plugin_root.expanduser().resolve()
        if plugin_root
        else discover_plugin_root(skill_dir)
    )
    if not is_within(skill_dir, effective_plugin_root):
        issues.append(
            Issue(
                "error",
                "SKILL_OUTSIDE_PLUGIN",
                str(skill_dir),
                f"Skill 不在 Plugin 根目录 {effective_plugin_root} 内。",
            )
        )
        return Report(str(skill_dir), profile, issues)

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        add_issue(issues, "error", "SKILL_MD", skill_md, "缺少 SKILL.md。", skill_dir)
        return Report(str(skill_dir), profile, issues)

    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_issue(
            issues,
            "error",
            "SKILL_MD_READ",
            skill_md,
            f"无法以 UTF-8 读取：{exc}",
            skill_dir,
        )
        return Report(str(skill_dir), profile, issues)

    line_count = len(text.splitlines())
    if line_count > 500:
        add_issue(
            issues,
            "warning",
            "SKILL_MD_LENGTH",
            skill_md,
            f"SKILL.md 共 {line_count} 行，建议保持在 500 行以内并拆分细节。",
            skill_dir,
        )

    frontmatter, _closing, parse_error = parse_frontmatter(text)
    if parse_error:
        add_issue(
            issues, "error", "FRONTMATTER_PARSE", skill_md, parse_error, skill_dir
        )
        frontmatter = {}
    else:
        validate_frontmatter(
            data=frontmatter,
            profile=profile,
            skill_dir=skill_dir,
            skill_md=skill_md,
            issues=issues,
        )

    validate_headings(text, skill_dir, skill_md, issues)
    validate_references(text, skill_dir, skill_md, effective_plugin_root, issues)
    validate_workflows(skill_dir, text, issues)
    validate_directory_conventions(skill_dir, effective_plugin_root, issues)
    validate_openai_adapter(skill_dir, profile, frontmatter, issues)

    return Report(str(skill_dir), profile, issues)


def print_human(report: Report) -> None:
    for issue in report.issues:
        print(
            f"{issue.severity.upper():7} {issue.code:28} {issue.path}: {issue.message}"
        )

    if report.errors:
        print(
            f"FAIL: {len(report.errors)} error(s), "
            f"{len(report.warnings)} warning(s) — {report.skill_dir}"
        )
    else:
        print(
            f"PASS: 0 error(s), {len(report.warnings)} warning(s) — {report.skill_dir}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 Agent Skill 的结构、Frontmatter、本地引用和软链接。"
    )
    parser.add_argument("skill_dir", type=Path, help="包含 SKILL.md 的 Skill 目录")
    parser.add_argument(
        "--profile",
        choices=("portable", "claude", "codex", "zcode", "pi", "dsh", "dual"),
        default="portable",
        help="选择目标平台，并按该平台规则检查 Frontmatter 和适配配置",
    )
    parser.add_argument(
        "--plugin-root",
        type=Path,
        help="允许软链接解析到的 Plugin 根目录；默认自动发现",
    )
    parser.add_argument("--strict", action="store_true", help="将 warning 视为失败")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_skill(args.skill_dir, args.profile, args.plugin_root)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_human(report)

    if report.errors or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
