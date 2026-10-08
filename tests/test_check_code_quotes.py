"""scripts/check_code_quotes.py のテスト（仮の dev-environment と章を作り、ずれを検知できるか）."""

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

JAVA = """\
package com.example.sample.member;

public class MemberService {

    private final MemberMapper mapper;

    public Member get(long id) {
        return mapper.findById(id).orElseThrow();
    }

    public long count() {
        return 0;
    }
}
"""


def git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
    )


class CodeQuotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "dev-environment"
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        path = self.repo / "sample-app/MemberService.java"
        path.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        path.write_text(JAVA, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "branch", "exercise-base")
        path.write_text(JAVA.replace("orElseThrow()", "orElseThrow(NotFound::new)"), encoding="utf-8")
        git(self.repo, "commit", "-qam", "fix")
        self.src = cq.Source(self.repo)

    def tearDown(self):
        rmtree(self.tmp)

    def errors(self, text):
        doc = self.docs / "ch.md"
        doc.write_text(text, encoding="utf-8")
        errs = []
        for block in cq.parse_blocks(doc):
            if block.marker:
                errs += cq.check_block(block, self.src)
            elif block.title.startswith(cq.SOURCE_PREFIXES):
                errs.append("no marker")
        return errs

    def test_lines_match_with_other_indent(self):
        text = (
            '!!! success "良い例"\n'
            "    <!-- src: sample-app/MemberService.java#L7-L9 @main -->\n"
            '    ```java title="sample-app/MemberService.java" linenums="7"\n'
            "    public Member get(long id) {\n"
            "      return mapper.findById(id).orElseThrow(NotFound::new);\n"
            "    }\n"
            "    ```\n"
        )
        self.assertEqual(self.errors(text), [])

    def test_branch_matters(self):
        body = "```java\nreturn mapper.findById(id).orElseThrow();\n```\n"
        self.assertEqual(self.errors("<!-- src: sample-app/MemberService.java @exercise-base -->\n" + body), [])
        errs = self.errors("<!-- src: sample-app/MemberService.java @main -->\n" + body)
        self.assertTrue(errs and "部分がありません" in errs[0], errs)

    def test_shifted_lines_are_reported_with_hint(self):
        text = (
            "<!-- src: sample-app/MemberService.java#L6-L8 @main -->\n"
            "```java\npublic Member get(long id) {\n"
            "    return mapper.findById(id).orElseThrow(NotFound::new);\n}\n```\n"
        )
        errs = self.errors(text)
        self.assertTrue(errs and "L7-L9" in errs[0], errs)

    def test_linenums_and_title_must_agree(self):
        text = (
            "<!-- src: sample-app/MemberService.java#L7-L9 @main -->\n"
            '```java title="sample-app/MemberService.java（6〜8 行目）" linenums="6"\n'
            "public Member get(long id) {\n"
            "    return mapper.findById(id).orElseThrow(NotFound::new);\n}\n```\n"
        )
        errs = self.errors(text)
        self.assertEqual(len(errs), 2, errs)

    def test_elision_and_multi_range(self):
        body = "public class MemberService {\n    // ...\n    public long count() {\n        return 0;\n    }\n}\n```\n"
        self.assertEqual(self.errors("<!-- src: sample-app/MemberService.java @main -->\n```java\n" + body), [])
        ranged = body.replace("    // ...\n", "")
        marker = "<!-- src: sample-app/MemberService.java#L3-L3,L11-L14 @main -->\n```java\n"
        self.assertEqual(self.errors(marker + ranged), [])

    def test_wildcard_in_line(self):
        text = (
            "<!-- src: sample-app/MemberService.java @main -->\n"
            "```java\nreturn mapper.findById(id).orElseThrow(（省略）);\n```\n"
        )
        self.assertEqual(self.errors(text), [])

    def test_changed_code_and_missing_file(self):
        changed = "<!-- src: sample-app/MemberService.java @main -->\n```java\nreturn 1;\n```\n"
        self.assertTrue(self.errors(changed))
        missing = "<!-- src: sample-app/Nope.java @main -->\n```java\nreturn 0;\n```\n"
        self.assertIn("ありません", self.errors(missing)[0])

    def test_titled_block_needs_marker(self):
        text = '```java title="sample-app/MemberService.java"\nreturn 0;\n```\n'
        self.assertEqual(self.errors(text), ["no marker"])

    def test_bad_marker_syntax(self):
        text = "<!-- src: sample-app/MemberService.java#7-9 -->\n```java\nreturn 0;\n```\n"
        self.assertIn("読めません", self.errors(text)[0])
        self.assertIn("書き方", self.errors("<!-- src: -->\n```java\nreturn 0;\n```\n")[0])

    def test_suggest(self):
        doc = self.docs / "ch.md"
        doc.write_text('```java title="sample-app/MemberService.java"\npublic long count() {\n```\n', encoding="utf-8")
        block = cq.parse_blocks(doc)[0]
        self.assertEqual(cq.suggest(block, self.src), "<!-- src: sample-app/MemberService.java @main -->")


class LineRefsTest(unittest.TestCase):
    """本文の「`File.java` N〜M 行目」を、実物と照合する（check_line_refs）."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "dev-environment"
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        java = self.repo / "sample-app/src/main/java/MemberService.java"
        java.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        java.write_text(JAVA, encoding="utf-8")
        (self.repo / "sample-app/src/main/resources").mkdir(parents=True)
        (self.repo / "sample-app/src/main/resources/application.yml").write_text(
            "spring:\n  messages:\n    basename: messages\n", encoding="utf-8"
        )
        for d in ("dev1", "prod"):
            (self.repo / f"cloud/{d}").mkdir(parents=True)
            (self.repo / f"cloud/{d}/main.tf").write_text("locals {}\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "branch", "exercise-base")
        self.src = cq.Source(self.repo)

    def tearDown(self):
        rmtree(self.tmp)

    def refs(self, text, name="ch.md"):
        doc = self.docs / name
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(text, encoding="utf-8")
        return cq.check_line_refs(doc, self.src)

    def test_correct_refs(self):
        text = (
            "`MemberService.java` の 7〜9 行目です。`MemberService.java` 8 行目の `mapper.findById(...)` を見ます。\n"
            "`MemberService.get`（7〜9 行目）と `MemberService.count`（12 行目）。\n"
            "`application.yml` 3 行目の `spring.messages.basename` です。\n"
            "`SpringApplication.run`（99 行目）は dev-environment の外なので照合しない。\n"
        )
        self.assertEqual(self.refs(text), (5, []))

    def test_shifted_line_is_reported(self):
        # 後退: 本文の行番号はどこからも照合されず、コードの変更でずれても気づけなかった
        n, errs = self.refs("`MemberService.java` 7 行目の `mapper.findById(id)` です。\n")
        self.assertEqual(n, 1)
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("8 行目にあります", errs[0])

    def test_member_outside_range(self):
        _, errs = self.refs("`MemberService.count`（7〜9 行目）\n")
        self.assertTrue(errs and "`count` がありません" in errs[0], errs)

    def test_out_of_range_and_blank_lines(self):
        _, errs = self.refs("`MemberService.java` 40 行目\n`MemberService.java` 2 行目\n")
        self.assertEqual(len(errs), 2, errs)
        self.assertIn("範囲の外", errs[0])
        self.assertIn("空行", errs[1])

    def test_unknown_and_ambiguous_file(self):
        _, errs = self.refs("`Nope.java` 3 行目\n`main.tf` 1 行目\n`cloud/dev1/main.tf` 1 行目\n")
        self.assertEqual(len(errs), 2, errs)
        self.assertIn("ありません", errs[0])
        self.assertIn("2 か所", errs[1])

    def test_code_blocks_are_skipped(self):
        self.assertEqual(self.refs("```text\n`MemberService.java` 40 行目\n```\n"), (0, []))

    def test_page_branch(self):
        self.refs("本文\n", "x.md")
        self.assertEqual(cq.default_ref(self.docs / "x.md"), "main")
        doc = self.docs / "30-reading/answers/30-01.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# 解答\n", encoding="utf-8")
        self.assertEqual(cq.default_ref(doc), "exercise-base")


if __name__ == "__main__":
    unittest.main()
