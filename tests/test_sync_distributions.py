from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_distributions


REPO_ROOT = Path(__file__).resolve().parents[1]


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self, args: list[str] | tuple[str, ...], cwd: Path, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        del cwd, timeout
        normalized = tuple(str(arg) for arg in args)
        self.calls.append(normalized)
        stdout = ""
        returncode = 0
        if normalized[:3] == ("git", "rev-parse", "--abbrev-ref"):
            stdout = "main\n"
        elif normalized[:3] == ("git", "remote", "get-url"):
            stdout = "https://github.com/koco-co/agent-build-kit.git\n"
        elif normalized[:3] == ("git", "ls-files", "--others"):
            stdout = ""
        elif normalized == ("git", "status", "--short"):
            stdout = "M README.md\n"
        elif normalized == ("git", "diff", "--cached", "--quiet"):
            returncode = 1
        elif normalized[:3] == ("git", "rev-parse", "HEAD"):
            stdout = "abc123\n"
        return subprocess.CompletedProcess(normalized, returncode, stdout, "")


class SyncDistributionsTests(unittest.TestCase):
    def test_read_version_includes_nested_marketplace_version(self) -> None:
        self.assertEqual(sync_distributions.read_version(REPO_ROOT), "3.3.0")

    def test_preflight_runs_each_release_gate_once(self) -> None:
        runner = RecordingRunner()

        version = sync_distributions.run_preflight(REPO_ROOT, runner)

        self.assertEqual(version, "3.3.0")
        commands = [" ".join(call) for call in runner.calls]
        self.assertTrue(any("sync_shared_files.py --root" in call for call in commands))
        self.assertTrue(any("validate_plugin.py" in call and "--strict" in call for call in commands))
        self.assertTrue(any("validate_skill_evals.py" in call for call in commands))
        self.assertTrue(any("unittest discover" in call for call in commands))
        self.assertIn("git diff --check", commands)
        self.assertIn("git diff --cached --check", commands)

    def test_commit_without_stage_requires_a_clean_worktree(self) -> None:
        runner = RecordingRunner()

        sync_distributions.commit_and_push(
            REPO_ROOT, "test: publish", stage_all=False, runner=runner
        )

        commands = [" ".join(call) for call in runner.calls]
        self.assertNotIn("git add --all", commands)
        self.assertIn("git commit -m test: publish", commands)
        self.assertIn("git push origin main", commands)

    def test_client_sync_order_is_fixed(self) -> None:
        with (
            patch.object(sync_distributions, "run_preflight", return_value="3.3.0"),
            patch.object(sync_distributions, "commit_and_push"),
            patch.object(sync_distributions, "sync_clients") as sync_clients,
        ):
            result = sync_distributions.main(
                ["--publish", "--message", "feat: sync distributions"]
            )

        self.assertEqual(result, 0)
        sync_clients.assert_called_once_with(REPO_ROOT, "3.3.0")

    def test_zcode_workspace_uses_the_repository_identity(self) -> None:
        workspace = sync_distributions._zcode_workspace(REPO_ROOT)
        self.assertEqual(
            workspace,
            {
                "workspacePath": str(REPO_ROOT),
                "workspaceKey": str(REPO_ROOT),
            },
        )

    def test_find_entry_accepts_codex_installed_payload(self) -> None:
        entry = sync_distributions._find_entry(
            {
                "installed": [
                    {"pluginId": "agent-build-kit@agent-build-kit", "version": "3.3.0"}
                ]
            },
            "agent-build-kit@agent-build-kit",
            "Codex",
        )
        self.assertEqual(entry["version"], "3.3.0")

    def test_stage_requires_publish(self) -> None:
        self.assertEqual(sync_distributions.main(["--stage"]), 2)

    def test_publish_requires_message(self) -> None:
        self.assertEqual(sync_distributions.main(["--publish"]), 2)


if __name__ == "__main__":
    unittest.main()
