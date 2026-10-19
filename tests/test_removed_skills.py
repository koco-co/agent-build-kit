from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RemovedSkillTests(unittest.TestCase):
    def test_obsidian_learning_skill_is_completely_removed(self) -> None:
        self.assertFalse(REPO_ROOT.joinpath("skills", "obsidian-learn-topic").exists())
        self.assertFalse(
            REPO_ROOT.joinpath("tests", "test_obsidian_learn_topic.py").exists()
        )

        public_files = (
            REPO_ROOT / "README.md",
            REPO_ROOT / ".claude-plugin" / "plugin.json",
            REPO_ROOT / ".claude-plugin" / "marketplace.json",
            REPO_ROOT / ".codex-plugin" / "plugin.json",
        )
        for path in public_files:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("obsidian-learn-topic", text)
                self.assertNotIn("technical-learning", text)
                self.assertNotIn("technical learning", text.lower())


if __name__ == "__main__":
    unittest.main()
