from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "skills" / "build-readme" / "scripts" / "validate_readme.py"

VALID_README = """
# Build Flow

Build Flow turns repository facts into verifiable documentation.

## Quick start

```bash
python3 validate.py README.md
```
"""


class ValidateReadmeTests(unittest.TestCase):
    def write_readme(self, root: Path, text: str = VALID_README) -> Path:
        path = root / "README.md"
        path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
        return path

    def run_validator(
        self, path: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(path), "--strict", *extra],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

    def assert_fails_with(self, text: str, code: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp), text))
            self.assertEqual(result.returncode, 1)
            self.assertIn(code, result.stdout)

    def test_standard_markdown_readme_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp)))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_plain_and_formatted_markdown_are_both_allowed(self) -> None:
        text = VALID_README + "\n**Important:** use *standard* Markdown.\n"
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp), text))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_forced_centering_and_unicode_decoration_are_not_required(self) -> None:
        self.assertNotIn("<div", VALID_README)
        self.assertNotRegex(VALID_README, r"[𝓐-𝔃]")
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp)))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_title_is_required_and_unique(self) -> None:
        self.assert_fails_with("No heading.\n", "TITLE_REQUIRED")
        self.assert_fails_with(VALID_README + "\n# Second title\n", "TITLE_COUNT")

    def test_unlabeled_and_unclosed_code_fences_fail(self) -> None:
        self.assert_fails_with(
            VALID_README.replace("```bash", "```", 1), "FENCE_LANGUAGE_REQUIRED"
        )
        self.assert_fails_with(VALID_README.rsplit("```", 1)[0], "FENCE_UNCLOSED")

    def test_placeholder_fails_but_todo_in_prose_or_code_is_allowed(self) -> None:
        self.assert_fails_with(
            VALID_README + "\nTBD: write this later\n", "UNRESOLVED_CONTENT"
        )
        text = (
            VALID_README
            + "\nThe validator rejects standalone TODO markers.\n\n```text\nTODO\n```\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp), text))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_malformed_html_fails(self) -> None:
        self.assert_fails_with(
            VALID_README + "\n<details><summary>More</summary>\n", "HTML_TAG_MISMATCH"
        )

    def test_gfm_autolinks_are_not_misread_as_html(self) -> None:
        text = VALID_README + "\nContact <user@example.com> or <https://example.com>.\n"
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(self.write_readme(Path(temp), text))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_existing_local_reference_passes_and_missing_reference_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("docs.md").write_text("# Docs\n", encoding="utf-8")
            result = self.run_validator(
                self.write_readme(root, VALID_README + "\n[Docs](docs.md)\n")
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_fails_with(
            VALID_README + "\n[Docs](missing.md)\n", "LOCAL_REF_MISSING"
        )

    def test_local_reference_cannot_escape_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root.parent / "outside-readme-test.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            try:
                result = self.run_validator(
                    self.write_readme(
                        root, VALID_README + "\n[Outside](../outside-readme-test.md)\n"
                    )
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("LOCAL_REF_OUTSIDE", result.stdout)
            finally:
                outside.unlink(missing_ok=True)

    def test_image_requires_alt_text(self) -> None:
        self.assert_fails_with(
            VALID_README + "\n![](https://example.com/image.png)\n",
            "IMAGE_ALT_REQUIRED",
        )

    def test_remote_images_are_allowed_with_alt_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self.write_readme(
                Path(temp),
                VALID_README + "\n![Screenshot](https://example.com/screenshot.png)\n",
            )
            result = self.run_validator(path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_and_unsafe_svg_fail(self) -> None:
        for body, code in (
            ("<svg><broken>", "SVG_INVALID"),
            (
                '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                "SVG_UNSAFE",
            ),
            (
                '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://evil.example/x.css);</style></svg>',
                "SVG_UNSAFE",
            ),
        ):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                asset = root / "asset.svg"
                asset.write_text(body, encoding="utf-8")
                result = self.run_validator(
                    self.write_readme(root, VALID_README + "\n![Diagram](asset.svg)\n")
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(code, result.stdout)

    def test_invalid_mermaid_fails(self) -> None:
        self.assert_fails_with(
            VALID_README + "\n```mermaid\nnot a diagram\n```\n", "MERMAID_INVALID"
        )

    def test_json_report_has_stable_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_validator(
                self.write_readme(Path(temp), "No heading.\n"), "--json"
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertGreater(report["error_count"], 0)
            self.assertEqual(report["status"], "fail")

    def test_repository_readme_passes(self) -> None:
        result = self.run_validator(REPO_ROOT / "README.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shipped_example_passes(self) -> None:
        example = (
            REPO_ROOT / "skills" / "build-readme" / "examples" / "readme.example.md"
        )
        result = self.run_validator(example)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
