"""CI（.github/workflows/ci.yml）の約束のテスト.

後退: 公開（deploy）の needs に security（bandit・pip-audit）が無く、脆弱性の検査が落ちても公開されていた.
検査のジョブを足したときに入れ忘れないよう、
「deploy と起票以外のジョブはすべて deploy の needs にある」を確かめる.
ただし外部リンクの検査（links）は定期実行・手動実行だけのジョブなので、
deploy の needs には入れない（入れると push で公開が止まる）.
（テストのジョブは依存を入れないので、YAML は読まずに文字列で見る）
"""

import re
import unittest
from pathlib import Path

CI = Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml"
NOT_CHECKS = {"deploy", "report-scheduled-failure"}
SCHEDULE_ONLY = {"links"}  # 外部のサイトの都合で結果が変わる検査. push・PR では動かさない


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
        self.assertEqual(needs(self.jobs["deploy"]), checks - SCHEDULE_ONLY)

    def test_scheduled_failure_report_watches_every_check(self):
        self.assertEqual(needs(self.jobs["report-scheduled-failure"]), set(self.jobs) - NOT_CHECKS)

    def test_link_check_runs_only_on_schedule_and_manual_runs(self):
        for name in SCHEDULE_ONLY:
            job = self.jobs[name]
            m = re.search(r"(?m)^    if: (?P<cond>.+)$", job)
            self.assertIsNotNone(m, f"{name} に if がありません（push・PR でも動いてしまう）")
            expected = "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
            self.assertEqual(m.group("cond"), expected)
        self.assertIn("scripts/check_links.py site", self.jobs["links"])
        # 切れていたら Issue を起票する（本文に一覧を入れる）
        report = self.jobs["report-scheduled-failure"]
        self.assertIn("needs.links.outputs.report", report)
        self.assertIn("if: env.LINKS_RESULT == 'failure'", report)

    def test_java_examples_are_checked_on_every_run(self):
        # 「例:」などのコード例の構文検査は push・PR でも動く code-quotes で行う（定期実行だけにしない）
        job = self.jobs["code-quotes"]
        self.assertNotRegex(job, r"(?m)^    if:")
        self.assertIn("python scripts/check_java_examples.py", job)
        self.assertIn("actions/setup-java@", job)

    def test_deploy_runs_one_at_a_time_in_order(self):
        # 後退: 公開に concurrency が無く、続けて push すると古い実行の公開が新しい公開の後に終わることがあった
        deploy = self.jobs["deploy"]
        self.assertRegex(deploy, r"(?m)^    concurrency:\n      group: pages\n      cancel-in-progress: false$")

    def test_outdated_pull_request_runs_are_cancelled(self):
        top = CI.read_text(encoding="utf-8").split("\njobs:\n", 1)[0]
        m = re.search(r"(?m)^concurrency:\n  group: (?P<group>.+)\n  cancel-in-progress: (?P<cancel>.+)$", top)
        self.assertIsNotNone(m, "ワークフローに concurrency がありません")
        self.assertIn("github.event_name", m.group("group"))  # 定期実行が push の待ちを押し出さない
        self.assertIn("pull_request.number", m.group("group"))
        self.assertEqual(m.group("cancel"), "${{ github.event_name == 'pull_request' }}")

    def test_parser_sees_needs(self):
        self.assertEqual(needs("    needs: [a, b]\n"), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
