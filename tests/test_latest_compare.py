"""週 1 回の定期検査で、固定した SHA ではなく dev-environment の各ブランチの最新と比べること（--latest）のテスト.

後退: 定期検査も dev-environment-pin.json で固定した SHA と比べていたので、dev-environment が進んでも
結果が変わらず、引用や版のずれに気づけなかった（「週 1 回検査して Issue を起票する」が働かない）.
"""

import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_code_quotes as cq  # noqa: E402
from _util import rmtree  # noqa: E402
from test_workflow import CI, jobs  # noqa: E402

DOC = "<!-- src: local/.env.example @main -->\n```text\nDB_PORT=5432\n```\n"


def git(repo, *args):
    r = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


class LatestRevsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "dev-environment"
        f = self.repo / "local/.env.example"
        f.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        f.write_text("DB_PORT=5432\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pinned")
        git(self.repo, "branch", "exercise-base")
        # 固定の後に main が進み、教材が引用した行が変わった
        f.write_text("DB_PORT=15432\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "newer")
        self.main_tip = git(self.repo, "rev-parse", "main")
        self.base_tip = git(self.repo, "rev-parse", "exercise-base")
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        (self.docs / "ch.md").write_text(DOC, encoding="utf-8")

    def tearDown(self):
        rmtree(self.tmp)

    def test_latest_revs_reads_branch_tips(self):
        revs = cq.latest_revs(self.repo.as_uri(), ["main", "exercise-base"])
        self.assertEqual(revs, {"main": self.main_tip, "exercise-base": self.base_tip})

    def test_latest_revs_missing_branch_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "feature-x"):
            cq.latest_revs(self.repo.as_uri(), ["main", "feature-x"])

    def test_latest_detects_change_after_pin(self):
        # リポジトリの dev-environment-pin.json の SHA はこの仮のリポジトリに無いが、--latest なら最新を取得して比べる
        with contextlib.redirect_stdout(io.StringIO()) as out:
            src, tmp = cq.open_source(None, self.repo.as_uri(), [], latest=True)
        try:
            self.assertEqual(src.pins, {"main": self.main_tip, "exercise-base": self.base_tip})
            self.assertIn(f"main の最新 {self.main_tip[:12]}", out.getvalue())
            errs = [e for b in cq.parse_blocks(self.docs / "ch.md") if b.marker for e in cq.check_block(b, src)]
            self.assertTrue(errs and "部分がありません" in errs[0], errs)
        finally:
            rmtree(tmp)

    def test_explicit_ref_wins_over_latest(self):
        with contextlib.redirect_stdout(io.StringIO()):
            src, tmp = cq.open_source(self.repo, self.repo.as_uri(), ["main=exercise-base"], latest=True)
        self.assertIsNone(tmp)
        self.assertEqual(src.pins["main"], "exercise-base")

    def test_main_accepts_latest_option(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = cq.main(["--latest", "--repo-url", self.repo.as_uri(), "--docs", str(self.docs)])
        self.assertEqual(rc, 1, out.getvalue())
        self.assertIn("部分がありません", out.getvalue())


class ScheduledWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.job = jobs(CI.read_text(encoding="utf-8"))["code-quotes"]

    def test_schedule_compares_with_latest(self):
        m = re.search(r"(?m)^      COMPARE_WITH: (.+)$", self.job)
        self.assertIsNotNone(m, "code-quotes に COMPARE_WITH がありません")
        self.assertEqual(m.group(1), "${{ github.event_name == 'schedule' && '--latest' || '' }}")

    def test_both_checks_use_the_comparison(self):
        self.assertIn("python scripts/check_code_quotes.py $COMPARE_WITH", self.job)
        self.assertIn("python scripts/check_versions.py $COMPARE_WITH", self.job)

    def test_issue_body_explains_latest_comparison(self):
        report = jobs(CI.read_text(encoding="utf-8"))["report-scheduled-failure"]
        self.assertIn("--latest", report)
        self.assertIn("最新と比べています", report)


if __name__ == "__main__":
    unittest.main()
