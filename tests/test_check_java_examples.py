"""scripts/check_java_examples.py のテスト.

Java と javaparser-core が無くても動く部分
（対象のブロックの選び方・skip の印・飛ばした印の扱い・出力の読み取り）を確かめる.
JAVAPARSER_JAR（jar のパス）が設定され java コマンドがあるときだけ、実際に構文の誤りを検出できるかも確かめる.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_java_examples as cj  # noqa: E402
from _util import rmtree  # noqa: E402

PAGE = """# 章

例:

```java
int x = 1;
```

<!-- src: sample-app/src/main/java/A.java#L1-L2 @main -->
```java title="sample-app/src/main/java/A.java"
class A {}
```

<!-- java-syntax: skip わざと誤ったコードを見せる -->
```java
int x = ;
```

<!-- java-syntax: skip -->
```java
int y = ;
```

```bash
echo java
```

!!! failure "悪い例"
    ```java
    if (a == "01") { /* ... */ }
    ```
"""


class ExamplesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.doc = self.tmp / "page.md"
        self.doc.write_text(PAGE, encoding="utf-8")

    def tearDown(self):
        rmtree(self.tmp)

    def test_selects_unquoted_java_blocks_only(self):
        exs, errors = cj.examples(self.doc)
        bodies = [ex.block.body[0] for ex in exs]
        # src コメントの付いた引用（check_code_quotes.py が見る）と bash は対象外
        self.assertEqual(bodies, ["int x = 1;", "int x = ;", "int y = ;", 'if (a == "01") { /* ... */ }'])
        self.assertEqual([ex.skip_reason for ex in exs], [None, "わざと誤ったコードを見せる", None, None])
        # 理由の無い skip は誤りにし、そのブロックは検査する
        self.assertEqual(len(errors), 1)
        self.assertIn("理由", errors[0])

    def test_elision_lines_become_comments_without_shifting_lines(self):
        body = ["void f() {", "    ...", "    （省略）", "…", "    foo(a, b);", "}"]
        out = cj.prepare(body).split("\n")
        self.assertEqual(out[:6], ["void f() {", "    // ...", "    // ...", "// ...", "    foo(a, b);", "}"])
        # 式の途中の ... は飛ばした印にしない（構文の誤りとして出す）
        self.assertIn("foo(...)", cj.prepare(["foo(...);"]))

    def test_language_level_from_mkdocs(self):
        mk = self.tmp / "mkdocs.yml"
        mk.write_text('extra:\n  versions:\n    gradle: "9.1"\n    java: "17"\n', encoding="utf-8")
        self.assertEqual(cj.language_level(mk), "JAVA_17")
        mk.write_text("extra: {}\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            cj.language_level(mk)
        self.assertEqual(cj.language_level(), "JAVA_17")  # 実際の mkdocs.yml

    def test_parse_output(self):
        out = cj.parse_output('OK\ta.java\nNG\tb.java\t3\t7\tmethod-body\tParse error. Found "..."\nnoise\n')
        self.assertEqual(out, {"a.java": None, "b.java": (3, 7, "method-body", 'Parse error. Found "..."')})

    def test_missing_jar_is_reported(self):
        with self.assertRaises(ValueError):
            cj.ensure_jar(self.tmp / "none.jar")


JAR = os.environ.get("JAVAPARSER_JAR")


@unittest.skipUnless(JAR and Path(JAR).is_file() and shutil.which("java"), "JAVAPARSER_JAR と java が必要")
class JavaParserTest(unittest.TestCase):
    """実際に JavaParser で読む（CI の code-quotes では JAVAPARSER_JAR を設定して動かす）."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / "docs"
        self.docs.mkdir()

    def tearDown(self):
        rmtree(self.tmp)

    def run_check(self, page: str) -> list[str]:
        doc = self.docs / "p.md"
        doc.write_text(page, encoding="utf-8")
        exs, _ = cj.examples(doc)
        return cj.check([ex for ex in exs if ex.skip_reason is None], Path(JAR), "JAVA_17")

    def test_fragments_in_three_shapes_pass(self):
        page = (
            "```java\npackage a;\n\npublic record P(int x) {}\n```\n\n"
            "```java\n@Test\nvoid f() {\n    ...\n}\n```\n\n"
            "```java\nvar list = List.of(1, 2);\nlist.forEach(System.out::println);\n```\n"
        )
        self.assertEqual(self.run_check(page), [])

    def test_syntax_error_points_at_the_doc_line(self):
        page = "# t\n\n```java\nint a = 1;\nif (a == 1) { ... }\n```\n"
        errors = self.run_check(page)
        self.assertEqual(len(errors), 1)
        # 誤りは 5 行目（{ ... } の ...）
        self.assertRegex(errors[0], r"p\.md:5:\d+: Java の構文の誤り")


if __name__ == "__main__":
    unittest.main()
