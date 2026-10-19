#!/usr/bin/env python3
"""Validate factual, portable GitHub README structure and local resources."""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})([^\n]*)$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(
    r"<(?:a|img)\b[^>]*(?:href|src)=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE
)
PLACEHOLDER_RE = re.compile(
    r"\{\{[^{}\n]+\}\}|<TODO>|(?:^|\n)\s*(?:TODO|TBD)(?:\s*[:：].*)?\s*(?=\n|$)",
    re.IGNORECASE,
)
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SKIPPED_SCHEMES = ("mailto:", "tel:", "data:", "javascript:")
AUTOLINK_RE = re.compile(
    r"<(?:https?://[^<>\s]+|mailto:[^<>\s]+|[^<>\s@]+@[^<>\s]+\.[^<>\s]+)>",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    line: int
    message: str


@dataclass
class Report:
    path: str
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def to_dict(self, *, strict: bool = False) -> dict[str, object]:
        failed = bool(self.errors or (strict and self.warnings))
        return {
            "path": self.path,
            "status": "fail" if failed else "pass",
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [asdict(issue) for issue in self.issues],
        }


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def add_issue(
    issues: list[Issue], severity: str, code: str, path: Path, line: int, message: str
) -> None:
    issues.append(Issue(severity, code, str(path), line, message))


class BalancedHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.problems: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() not in VOID_TAGS:
            self.stack.append((tag.casefold(), self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in VOID_TAGS:
            return
        if not self.stack:
            self.problems.append((self.getpos()[0], f"多余的 </{tag}>"))
            return
        expected, start_line = self.stack.pop()
        if expected != normalized:
            self.problems.append(
                (
                    self.getpos()[0],
                    f"</{tag}> 与第 {start_line} 行的 <{expected}> 不匹配",
                )
            )

    def finish(self) -> None:
        for tag, start_line in reversed(self.stack):
            self.problems.append((start_line, f"<{tag}> 缺少结束标签"))


def mask_code(text: str) -> str:
    """Mask fenced and inline code while preserving offsets and line breaks."""
    chars = list(text)
    open_fence: tuple[str, int, int] | None = None
    for match in FENCE_RE.finditer(text):
        marker = match.group(1)
        if open_fence is None:
            open_fence = (marker[0], len(marker), match.start())
            continue
        if marker[0] == open_fence[0] and len(marker) >= open_fence[1]:
            for index in range(open_fence[2], match.end()):
                if chars[index] != "\n":
                    chars[index] = " "
            open_fence = None
    masked = "".join(chars)
    return re.sub(r"`[^`\n]+`", lambda match: " " * len(match.group(0)), masked)


def mask_autolinks(text: str) -> str:
    """Mask GFM autolinks so HTMLParser does not treat them as tags."""
    return AUTOLINK_RE.sub(lambda match: " " * len(match.group(0)), text)


def validate_structure(text: str, path: Path, issues: list[Issue]) -> None:
    headings = list(re.finditer(r"^(#{1,6})\s+\S.*$", mask_code(text), re.MULTILINE))
    if not headings:
        add_issue(
            issues,
            "error",
            "TITLE_REQUIRED",
            path,
            1,
            "README 必须包含 Markdown 标题。",
        )
        return
    first_content = next((line for line in text.splitlines() if line.strip()), "")
    if not first_content.startswith("# "):
        add_issue(
            issues,
            "error",
            "TITLE_REQUIRED",
            path,
            1,
            "README 的首个非空行必须是一级标题。",
        )
    h1 = [match for match in headings if len(match.group(1)) == 1]
    if len(h1) != 1:
        add_issue(
            issues,
            "error",
            "TITLE_COUNT",
            path,
            1,
            "README 必须且只能包含一个一级标题。",
        )


def validate_html(text: str, path: Path, issues: list[Issue]) -> None:
    parser = BalancedHTMLParser()
    try:
        parser.feed(mask_autolinks(mask_code(text)))
        parser.close()
        parser.finish()
    except Exception as exc:  # HTMLParser can surface malformed declarations.
        add_issue(issues, "error", "HTML_INVALID", path, 1, f"HTML 无法解析：{exc}")
        return
    for line, message in parser.problems:
        add_issue(issues, "error", "HTML_TAG_MISMATCH", path, line, message)


def validate_fences(text: str, path: Path, issues: list[Issue]) -> None:
    opened: tuple[str, int, int] | None = None
    for match in FENCE_RE.finditer(text):
        marker = match.group(1)
        info = match.group(2).strip()
        line = line_number(text, match.start())
        if opened is None:
            if not info:
                add_issue(
                    issues,
                    "error",
                    "FENCE_LANGUAGE_REQUIRED",
                    path,
                    line,
                    "代码围栏必须声明语言；纯文本使用 text。",
                )
            opened = (marker[0], len(marker), line)
        elif marker[0] == opened[0] and len(marker) >= opened[1] and not info:
            opened = None
    if opened is not None:
        add_issue(
            issues, "error", "FENCE_UNCLOSED", path, opened[2], "代码围栏没有闭合。"
        )


def discover_project_root(readme: Path, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    for candidate in (readme.parent, *readme.parents):
        if candidate.joinpath(".git").exists():
            return candidate.resolve()
    return readme.parent.resolve()


def split_reference(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    else:
        value = value.split(maxsplit=1)[0]
    return html.unescape(value)


def iter_references(text: str) -> Iterable[tuple[str, bool, str, int]]:
    masked = mask_code(text)
    for match in MARKDOWN_LINK_RE.finditer(masked):
        yield (
            split_reference(match.group(3)),
            bool(match.group(1)),
            match.group(2),
            match.start(),
        )
    for match in HTML_LINK_RE.finditer(masked):
        tag = match.group(0).lstrip().lower()
        yield html.unescape(match.group(1)), tag.startswith("<img"), "", match.start()


def local_target(reference: str, readme: Path) -> Path | None:
    if not reference or reference.startswith(
        ("#", "http://", "https://", *SKIPPED_SCHEMES)
    ):
        return None
    parsed = urllib.parse.urlsplit(reference)
    decoded = urllib.parse.unquote(parsed.path)
    if not decoded:
        return None
    return (readme.parent / decoded).resolve()


def validate_svg(target: Path, issues: list[Issue]) -> None:
    try:
        source = target.read_bytes()
        lowered = source.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise ET.ParseError("禁止 DTD 或实体声明")
        root = ET.fromstring(source)  # noqa: S314 — DTD/entity declarations are rejected above.
        if root.tag.rsplit("}", 1)[-1].casefold() != "svg":
            raise ET.ParseError("根元素不是 svg")
    except (ET.ParseError, OSError) as exc:
        add_issue(issues, "error", "SVG_INVALID", target, 1, f"SVG 无法解析：{exc}")
        return
    unsafe: list[str] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].casefold()
        if tag in {"script", "foreignobject"}:
            unsafe.append(f"禁止元素 <{tag}>")
        if tag == "style" and element.text:
            style = element.text.casefold()
            if re.search(r"@import\b", style) or re.search(
                r"url\s*\(\s*(?:https?:|//|javascript:)", style
            ):
                unsafe.append("禁止 <style> 中的 @import 或外部 URL")
        for raw_name, raw_value in element.attrib.items():
            name = raw_name.rsplit("}", 1)[-1].casefold()
            value = raw_value.strip().casefold()
            if name.startswith("on"):
                unsafe.append(f"禁止事件属性 {name}")
            if name in {"href", "src"} and value.startswith(
                ("http://", "https://", "//", "javascript:")
            ):
                unsafe.append(f"禁止外部或脚本引用 {raw_value}")
            if name == "style" and re.search(
                r"url\s*\(\s*(?:https?:|//|javascript:)", value
            ):
                unsafe.append("禁止 style 中的外部或脚本 URL")
    if unsafe:
        add_issue(
            issues,
            "error",
            "SVG_UNSAFE",
            target,
            1,
            "SVG 包含不安全内容：" + "；".join(dict.fromkeys(unsafe)),
        )


def validate_references(
    text: str, readme: Path, project_root: Path, issues: list[Issue]
) -> list[str]:
    remote_urls: list[str] = []
    seen: set[tuple[str, bool]] = set()
    for reference, is_image, alt, offset in iter_references(text):
        key = (reference, is_image)
        if key in seen:
            continue
        seen.add(key)
        line = line_number(text, offset)
        if is_image and not alt.strip():
            raw = (
                text[offset : text.find(">", offset) + 1]
                if text[offset:].lstrip().lower().startswith("<img")
                else ""
            )
            html_alt = re.search(r"\balt=[\"']([^\"']+)[\"']", raw, re.IGNORECASE)
            if html_alt is None:
                add_issue(
                    issues,
                    "error",
                    "IMAGE_ALT_REQUIRED",
                    readme,
                    line,
                    "图片必须提供非空替代文本。",
                )
        if reference.startswith(("http://", "https://")):
            remote_urls.append(reference)
            continue
        target = local_target(reference, readme)
        if target is None:
            continue
        try:
            target.relative_to(project_root)
        except ValueError:
            add_issue(
                issues,
                "error",
                "LOCAL_REF_OUTSIDE",
                readme,
                line,
                f"本地引用越过项目根目录：{reference}",
            )
            continue
        if not target.exists():
            add_issue(
                issues,
                "error",
                "LOCAL_REF_MISSING",
                readme,
                line,
                f"本地引用不存在：{reference}",
            )
        elif target.suffix.casefold() == ".svg" and target.is_file():
            validate_svg(target, issues)
    return remote_urls


def validate_mermaid(text: str, path: Path, issues: list[Issue]) -> None:
    for match in re.finditer(
        r"```mermaid\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE
    ):
        body = match.group(1).strip()
        if not body or not re.search(
            r"\b(?:flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph)\b",
            body,
        ):
            add_issue(
                issues,
                "error",
                "MERMAID_INVALID",
                path,
                line_number(text, match.start()),
                "Mermaid 围栏缺少受支持的图表声明。",
            )


def _is_public_http_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
        }
    except OSError:
        return False
    return bool(addresses) and all(
        ipaddress.ip_address(address).is_global for address in addresses
    )


class _PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if not _is_public_http_url(newurl):
            raise urllib.error.HTTPError(
                newurl, code, "redirect target is not public HTTP(S)", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_remote_urls(
    urls: Iterable[str], readme: Path, timeout: float, issues: list[Issue]
) -> None:
    for url in dict.fromkeys(urls):
        line = 1
        if not _is_public_http_url(url):
            add_issue(
                issues,
                "error",
                "REMOTE_URL_UNSAFE",
                readme,
                line,
                f"远程地址不是可验证的公网 HTTP(S) URL：{url}",
            )
            continue
        request = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "agent-build-kit-readme-validator/3"},
        )
        opener = urllib.request.build_opener(_PublicRedirectHandler())
        try:
            with opener.open(request, timeout=timeout) as response:  # noqa: S310 — scheme and resolved addresses are constrained above.
                if response.status >= 400:
                    raise urllib.error.HTTPError(
                        url, response.status, "HTTP error", response.headers, None
                    )
        except (OSError, urllib.error.URLError) as exc:
            add_issue(
                issues,
                "warning",
                "REMOTE_URL_UNREACHABLE",
                readme,
                line,
                f"远程地址验证失败：{url}（{exc}）",
            )


def validate_readme(
    readme: Path,
    *,
    project_root: Path | None = None,
    verify_remote: bool = False,
    timeout: float = 10.0,
) -> Report:
    path = readme.expanduser().resolve()
    issues: list[Issue] = []
    if not path.is_file():
        add_issue(issues, "error", "README_REQUIRED", path, 1, "README 文件不存在。")
        return Report(str(path), issues)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_issue(
            issues, "error", "README_READ", path, 1, f"无法读取 UTF-8 README：{exc}"
        )
        return Report(str(path), issues)
    if not text.strip():
        add_issue(issues, "error", "README_EMPTY", path, 1, "README 为空。")
        return Report(str(path), issues)

    validate_structure(text, path, issues)
    masked = mask_code(text)
    placeholder = PLACEHOLDER_RE.search(masked)
    if placeholder:
        add_issue(
            issues,
            "error",
            "UNRESOLVED_CONTENT",
            path,
            line_number(masked, placeholder.start()),
            f"README 包含未替换的占位内容：{placeholder.group(0).strip()}",
        )
    validate_html(text, path, issues)
    validate_fences(text, path, issues)
    remote_urls = validate_references(
        text, path, discover_project_root(path, project_root), issues
    )
    validate_mermaid(text, path, issues)
    if verify_remote:
        verify_remote_urls(remote_urls, path, timeout, issues)
    return Report(str(path), issues)


def print_human(report: Report, *, strict: bool = False) -> None:
    for issue in report.issues:
        print(
            f"{issue.severity.upper():7} {issue.code:24} {issue.path}:{issue.line}: {issue.message}"
        )
    failed = bool(report.errors or (strict and report.warnings))
    status = "FAIL" if failed else "PASS"
    print(
        f"{status}: {len(report.errors)} error(s), {len(report.warnings)} warning(s) — {report.path}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验 GitHub README 的结构、引用与资源安全。"
    )
    parser.add_argument("readme", type=Path, help="要校验的 README Markdown 文件")
    parser.add_argument(
        "--project-root", type=Path, help="项目根目录；省略时从 README 向上寻找 .git"
    )
    parser.add_argument("--verify-remote", action="store_true", help="联网验证远程链接")
    parser.add_argument("--timeout", type=float, default=10.0, help="远程请求超时秒数")
    parser.add_argument("--strict", action="store_true", help="将 warning 视为失败")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_readme(
        args.readme,
        project_root=args.project_root,
        verify_remote=args.verify_remote,
        timeout=args.timeout,
    )
    if args.json:
        print(
            json.dumps(report.to_dict(strict=args.strict), ensure_ascii=False, indent=2)
        )
    else:
        print_human(report, strict=args.strict)
    return 1 if report.errors or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
