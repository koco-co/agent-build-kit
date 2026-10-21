from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install_skill.py"
# MIT 要求在所有副本中保留原版权与许可声明；独立安装产生的也是副本。
ADAPTED_SKILLS = ("grill-me", "handoff")
UPSTREAM_COPYRIGHT = "Copyright (c) 2026 Matt Pocock"
MIT_CONDITION = (
    "The above copyright notice and this permission notice shall be included in all\n"
    "copies or substantial portions of the Software."
)
PLATFORM_ROOTS = {
    "claude": ".claude",
    "codex": ".agents",
    "zcode": ".zcode",
    "pi": ".pi/agent",
    "dsh": ".dsh",
}


class ThirdPartyNoticeTests(unittest.TestCase):
    def test_adapted_skills_ship_upstream_mit_notice(self) -> None:
        for skill in ADAPTED_SKILLS:
            with self.subTest(skill=skill):
                notice = REPO_ROOT.joinpath("skills", skill, "LICENSE.txt").read_text(
                    encoding="utf-8"
                )
                self.assertIn(UPSTREAM_COPYRIGHT, notice)
                self.assertIn(MIT_CONDITION, notice)

    def test_standalone_installs_keep_upstream_notice(self) -> None:
        for skill in ADAPTED_SKILLS:
            for platform, root in PLATFORM_ROOTS.items():
                with (
                    self.subTest(skill=skill, platform=platform),
                    tempfile.TemporaryDirectory() as temp,
                ):
                    home = Path(temp)
                    env = os.environ.copy()
                    env["HOME"] = str(home)
                    env.pop("DSH_HOME", None)
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(INSTALLER),
                            skill,
                            "--platform",
                            platform,
                            "--scope",
                            "user",
                        ],
                        cwd=REPO_ROOT,
                        env=env,
                        check=False,
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    notice = home.joinpath(root, "skills", skill, "LICENSE.txt")
                    self.assertIn(
                        UPSTREAM_COPYRIGHT, notice.read_text(encoding="utf-8")
                    )


if __name__ == "__main__":
    unittest.main()
