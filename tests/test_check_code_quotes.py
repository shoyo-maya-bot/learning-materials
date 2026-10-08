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


if __name__ == "__main__":
    unittest.main()
