"""第 8 回: git が無い・取得できないときにトレースバックにしない（終了コード 2）.

README と CI・実際の章数のずれも検査する.
"""

import contextlib
import io
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_code_quotes as cq  # noqa: E402
import check_versions as cv  # noqa: E402
from codequotes import source  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8-sig")
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def run(main, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = main(list(args))
    return rc, out.getvalue()


class GitFailureTest(unittest.TestCase):
    """前は subprocess.CalledProcessError のトレースバックで終わっていた."""

    def test_git_missing_is_exit_2_without_traceback(self):
        with mock.patch.dict(os.environ, {"PATH": os.devnull}):
            for main in (cq.main, cv.main):
                with self.subTest(main=main.__module__):
                    rc, out = run(main)
                    self.assertEqual(rc, 2, out)
                    self.assertIn("git コマンドが見つかりません", out)
                    self.assertNotIn("Traceback", out)

    def test_fetch_failure_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "no-such-repo"  # 存在しない取得元（ネットワークを使わない）
            for main in (cq.main, cv.main):
                with self.subTest(main=main.__module__):
                    rc, out = run(main, "--repo-url", str(bad))
                    self.assertEqual(rc, 2, out)
                    self.assertIn("固定した SHA を取得できません", out)

    def test_fetch_failure_removes_temp_dir(self):
        made = []
        real = tempfile.mkdtemp

        def spy(*a, **kw):
            made.append(Path(real(*a, **kw)))
            return str(made[-1])

        with (
            tempfile.TemporaryDirectory() as d,
            mock.patch.object(source.tempfile, "mkdtemp", spy),
            self.assertRaises(source.SourceUnavailable),
        ):
            source.open_source(None, str(Path(d) / "missing"), [])
        self.assertTrue(made and not made[0].exists())

    def test_repo_dir_that_is_not_a_clone_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out = run(cq.main, "--repo-dir", d)
        self.assertEqual(rc, 2, out)
        self.assertIn("git の clone ではありません", out)

    def test_ls_remote_failure_is_source_unavailable(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(source.SourceUnavailable):
            source.latest_revs(str(Path(d) / "missing"), ["main"])

    def test_bad_pin_file_is_still_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            pin = Path(d) / "pin.json"
            pin.write_text('{"refs": {"main": "x"}}', encoding="utf-8")
            with mock.patch.object(source.load_pins, "__defaults__", (pin,)):
                rc, out = run(cq.main)
        self.assertEqual(rc, 1, out)

    def test_exit_codes_are_documented(self):
        for script in ("check_code_quotes.py", "check_versions.py"):
            doc = (ROOT / "scripts" / script).read_text(encoding="utf-8")
            with self.subTest(script=script):
                self.assertIn("/ 2 dev-environment を用意できない", doc)
        self.assertIn("2 で終わります", README)


class ReadmeMatchesCiTest(unittest.TestCase):
    def test_python_version(self):
        versions = set(re.findall(r'python-version: "([\d.]+)"', CI))
        self.assertEqual(len(versions), 1, versions)
        self.assertIn(f"| Python {versions.pop()}（CI と同じ版", README)

    def test_ruff_version(self):
        (ci_ruff,) = set(re.findall(r'pip install "ruff==([\d.]+)"', CI))
        self.assertIn(f'pip install "ruff=={ci_ruff}"', README)
        self.assertIn(f"ruff {ci_ruff}（CI の lint ジョブと同じ版）", README)

    def test_every_check_command_in_ci_is_in_readme(self):
        commands = set(re.findall(r"run: (python (?:scripts/\w+\.py|-m unittest discover -s tests -v))", CI))
        commands |= {"ruff check .", "ruff format --check .", "mkdocs build --strict"}
        self.assertTrue(len(commands) >= 6, commands)
        for cmd in sorted(commands):
            with self.subTest(cmd=cmd):
                self.assertIn(cmd, README)


class AppendixCountTest(unittest.TestCase):
    """devtools-workspace の repos.yaml・武具屋は「全 73 章と付録 3」と書く. 付録の数も実際のファイルと合わせる."""

    def test_appendix_count(self):
        files = [f for f in (ROOT / "docs/appendix").glob("*.md") if f.name != "index.md"]
        index = (ROOT / "docs/index.md").read_text(encoding="utf-8-sig")
        n = len(files)
        self.assertRegex(index, re.compile(rf"^\| \[付録\]\([^)]*\) \| [^|]* \| {n} \|", re.M), "index.md の付録")
        self.assertRegex(README, re.compile(rf"^\| 付録 \| {n} \|", re.M), "README.md の付録の数")

    def test_total_chapters(self):
        chapter = re.compile(r"^\d{2}-\d{2}-.*\.md$")
        total = sum(1 for f in (ROOT / "docs").rglob("*.md") if chapter.match(f.name))
        rows = re.findall(r"^\| \d{2} [^|]* \| (\d+)(?: \+ 解答)? \|", README, re.M)
        self.assertEqual(sum(map(int, rows)), total)


if __name__ == "__main__":
    unittest.main()
