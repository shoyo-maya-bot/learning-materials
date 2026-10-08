"""scripts/check_chapters.py のテスト（仮の docs を作り、構成の誤りと禁止語を検知できるか）."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_chapters as cc  # noqa: E402
from _util import rmtree  # noqa: E402

HEADS = [
    "何か",
    "なぜ必要か",
    "どうやるか",
    "サンプルアプリでは",
    "なかったら？",
    "理解度チェック",
    "コードを読むときの確認観点",
]


def chapter(heads=HEADS, extra=""):
    body = '# 章\n\n!!! abstract "到達目標"\n    - 読める\n\n'
    return body + "".join(f"## {h}\n\n本文\n\n" for h in heads) + extra


class CheckChaptersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / "docs"
        (self.docs / "20-basics").mkdir(parents=True)
        self.banned = self.tmp / "banned-terms.txt"
        self.banned.write_text("# コメント\n株式会社\n@gmail.com  # 個人のメール\n", encoding="utf-8")

    def tearDown(self):
        rmtree(self.tmp)

    def write(self, rel, text):
        p = self.docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def run_check(self):
        return cc.run(self.docs, self.banned)

    def test_ok(self):
        self.write("20-basics/20-01-x.md", chapter())
        self.assertEqual(self.run_check(), (1, []))

    def test_missing_goal_and_heading_order(self):
        self.write("20-basics/20-01-x.md", chapter(HEADS[1:2] + HEADS[:1] + HEADS[2:]).replace("到達目標", "目標"))
        _, errs = self.run_check()
        self.assertTrue(any("到達目標" in e for e in errs), errs)
        self.assertTrue(any("「なぜ必要か」の順番" in e or "「何か」の順番" in e for e in errs), errs)

    def test_missing_heading(self):
        self.write("20-basics/20-01-x.md", chapter(HEADS[:-1]))
        _, errs = self.run_check()
        self.assertEqual(errs, ["20-basics/20-01-x.md: 見出し「コードを読むときの確認観点」がありません"])

    def test_reading_chapter_needs_exercise_and_answer(self):
        self.write("30-reading/30-01-x.md", chapter())
        _, errs = self.run_check()
        self.assertEqual(len(errs), 3, errs)  # 演習・解答へのリンク・解答ページ
        self.write("30-reading/30-01-x.md", chapter(HEADS + ["演習"], "[解答](answers/30-01.md)\n"))
        self.write("30-reading/answers/30-01.md", "# 30-01 解答\n")
        self.assertEqual(self.run_check(), (1, []))

    def test_banned_terms_anywhere_in_docs_case_insensitive(self):
        self.write("20-basics/20-01-x.md", chapter(extra="連絡先は someone@GMAIL.com です\n"))
        self.write("20-basics/index.md", "# 索引\n\n架空の株式会社サンプル\n")
        _, errs = self.run_check()
        line = len(chapter().split("\n"))  # 本文の最後に足した行
        self.assertIn(f"20-basics/20-01-x.md:{line}: 禁止語「@gmail.com」があります", errs)
        self.assertIn("20-basics/index.md:3: 禁止語「株式会社」があります", errs)

    def test_empty_or_missing_banned_list_fails(self):
        # 後退: 禁止語のリストが空（BANNED = []）だと、検査が黙って何もしなかった
        self.write("20-basics/20-01-x.md", chapter())
        self.banned.write_text("# コメントだけ\n\n", encoding="utf-8")
        _, errs = self.run_check()
        self.assertTrue(errs and "空です" in errs[0], errs)
        self.banned.unlink()
        _, errs = self.run_check()
        self.assertTrue(errs and "読めません" in errs[0], errs)

    def test_repository_banned_list_is_not_empty(self):
        self.assertGreaterEqual(len(cc.load_banned()), 5)

    def test_main_exit_code(self):
        self.write("20-basics/20-01-x.md", chapter(HEADS[:-1]))
        self.assertEqual(cc.main(["--docs", str(self.docs), "--banned", str(self.banned)]), 1)


if __name__ == "__main__":
    unittest.main()
