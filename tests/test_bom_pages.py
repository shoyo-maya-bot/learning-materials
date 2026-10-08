"""BOM 付き（UTF-8 with BOM. Windows のエディタの保存形式）のページ・設定を検査スクリプトが正しく読むことのテスト.

後退: utf-8 で読んでいたので、先頭の BOM（U+FEFF）のせいで
- check_versions.py が先頭の front matter（render_macros: true）を見落とし、誤って「render_macros が無い」とした
- check_code_quotes.py が 1 行目の引用元コメント（src:）を引用元と認めず、引用の照合を黙って飛ばした
- dev-environment-pin.json が JSON として読めなかった
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_chapters as cc  # noqa: E402
import check_code_quotes as cq  # noqa: E402
import check_versions as cv  # noqa: E402
from _util import rmtree  # noqa: E402

BOM = "﻿"


class BomPagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / "docs"
        self.docs.mkdir()

    def tearDown(self):
        rmtree(self.tmp)

    def write(self, rel, text):
        p = self.docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(BOM + text, encoding="utf-8")
        return p

    def test_render_macros_front_matter_is_found(self):
        self.write("10-01.md", "---\nrender_macros: true\n---\n\n# 章\n\nGradle {{ versions.gradle }}\n")
        errs = cv.check_docs(self.docs, {"gradle": "8.14.3"})
        self.assertEqual(errs, [])

    def test_mkdocs_versions_are_read(self):
        mk = self.tmp / "mkdocs.yml"
        mk.write_text(BOM + 'extra:\n  versions:\n    gradle: "8.14.3"\n', encoding="utf-8")
        self.assertEqual(cv.load_versions(mk), {"gradle": "8.14.3"})

    def test_quote_marker_on_first_line_is_checked(self):
        repo = self.tmp / "dev-environment"
        f = repo / "local/.env.example"
        f.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        f.write_text("DB_PORT=15432\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "add", "-A"], check=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x"],
            check=True,
        )
        doc = self.write("ch.md", "<!-- src: local/.env.example @main -->\n```text\nDB_PORT=5432\n```\n")
        blocks = cq.parse_blocks(doc)
        self.assertEqual(len(blocks), 1)
        self.assertIsNotNone(blocks[0].marker, "1 行目の引用元コメントを引用元と認めていません")
        errs = cq.check_block(blocks[0], cq.Source(repo))
        self.assertTrue(errs and "部分がありません" in errs[0], errs)

    def test_exercise_note_and_prose_lines(self):
        doc = self.write("ch.md", cq.EXERCISE_NOTE + "\n\n本文\n")
        self.assertEqual(cq.default_ref(doc), "exercise-base")
        self.assertEqual(cq.prose_lines(doc)[0], (1, cq.EXERCISE_NOTE))

    def test_banned_term_on_first_line(self):
        doc = self.write("index.md", "株式会社サンプル\n")
        self.assertEqual(cc.check_banned(doc, ["株式会社"], self.docs), ["index.md:1: 禁止語「株式会社」があります"])

    def test_pin_file_with_bom(self):
        p = self.tmp / "pin.json"
        sha = "0" * 40
        p.write_text(BOM + json.dumps({"refs": {"main": sha, "exercise-base": sha}}), encoding="utf-8")
        self.assertEqual(cq.load_pins(p)[1], {"main": sha, "exercise-base": sha})


if __name__ == "__main__":
    unittest.main()
