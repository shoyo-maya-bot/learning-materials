"""CI（.github/workflows/ci.yml）の約束のテスト.

後退: 公開（deploy）の needs に security（bandit・pip-audit）が無く、脆弱性の検査が落ちても公開されていた.
検査のジョブを足したときに入れ忘れないよう、
「deploy と起票以外のジョブはすべて deploy の needs にある」を確かめる.
（テストのジョブは依存を入れないので、YAML は読まずに文字列で見る）
"""

import re
import unittest
from pathlib import Path

CI = Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml"
NOT_CHECKS = {"deploy", "report-scheduled-failure"}


def jobs(text: str) -> dict[str, str]:
    """ジョブ名 → そのジョブの本文（jobs: の直下、2 字下げのキー）."""
    body = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([\w-]+):\s*$", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def needs(job: str) -> set[str]:
    m = re.search(r"^    needs:\s*\[(?P<list>[^\]]*)\]", job, re.M)
    return {x.strip() for x in m.group("list").split(",")} if m else set()


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.jobs = jobs(CI.read_text(encoding="utf-8"))

    def test_deploy_needs_every_check(self):
        checks = set(self.jobs) - NOT_CHECKS
        self.assertIn("security", checks)
        self.assertEqual(needs(self.jobs["deploy"]), checks)

    def test_scheduled_failure_report_watches_every_check(self):
        self.assertEqual(needs(self.jobs["report-scheduled-failure"]), set(self.jobs) - NOT_CHECKS)

    def test_parser_sees_needs(self):
        self.assertEqual(needs("    needs: [a, b]\n"), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
