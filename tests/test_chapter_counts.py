"""トップページ（docs/index.md）と README の編の表に書いた章数が、実際の章ファイルの数と一致することのテスト.

後退: 60 設計品質に章を足したとき、docs/index.md の章数が 3 のまま残っていた。
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CHAPTER = re.compile(r"^\d{2}-\d{2}-.*\.md$")


def actual_counts():
    counts = {}
    for d in DOCS.iterdir():
        if d.is_dir() and re.match(r"^\d{2}-", d.name):
            counts[d.name[:2]] = sum(1 for f in d.iterdir() if CHAPTER.match(f.name))
    return counts


class ChapterCountsTest(unittest.TestCase):
    def test_index_table(self):
        text = (DOCS / "index.md").read_text(encoding="utf-8-sig")
        rows = re.findall(r"^\| \[(\d{2}) [^\]]*\]\([^)]*\) \| [^|]* \| (\d+) \|", text, re.M)
        self.assertTrue(rows, "docs/index.md に編の表が見つからない")
        actual = actual_counts()
        for part, n in rows:
            with self.subTest(part=part):
                self.assertEqual(int(n), actual[part], f"docs/index.md の {part} の章数")

    def test_readme_table(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8-sig")
        rows = re.findall(r"^\| (\d{2}) [^|]* \| (\d+)(?: \+ 解答)? \|", text, re.M)
        self.assertTrue(rows, "README.md に編の表が見つからない")
        actual = actual_counts()
        for part, n in rows:
            with self.subTest(part=part):
                self.assertEqual(int(n), actual[part], f"README.md の {part} の章数")


if __name__ == "__main__":
    unittest.main()
