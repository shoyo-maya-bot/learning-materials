"""引用元を SHA で固定する仕組み（dev-environment-pin.json）のテスト.

以前の後退: 引用元が dev-environment の main の最新だったため、dev-environment 側の変更
（.env.example の文言、ports の 127.0.0.1、main.tf の locals）だけで教材の CI が赤くなった.
固定した SHA と比べれば、main が進んでも壊れない.
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

import check_code_quotes as cq  # noqa: E402
from _util import rmtree  # noqa: E402


def git(repo, *args):
    r = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


DOC = "<!-- src: local/.env.example @main -->\n```text\nDB_PORT=5432\n```\n"


class PinTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "dev-environment"
        f = self.repo / "local/.env.example"
        f.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        f.write_text("DB_PORT=5432\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pinned")
        self.pinned = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "branch", "exercise-base")
        # 固定の後に main が進み、教材が引用した行が変わった
        f.write_text("DB_PORT=15432\n", encoding="utf-8")
        git(self.repo, "commit", "-qam", "newer")
        self.docs = self.tmp / "docs"
        self.docs.mkdir()
        (self.docs / "ch.md").write_text(DOC, encoding="utf-8")

    def tearDown(self):
        rmtree(self.tmp)

    def errors(self, src):
        return [e for b in cq.parse_blocks(self.docs / "ch.md") if b.marker for e in cq.check_block(b, src)]

    def pins(self):
        return {"main": self.pinned, "exercise-base": self.pinned}

    def test_pinned_sha_is_used_even_if_main_moved(self):
        self.assertEqual(self.errors(cq.Source(self.repo, self.pins())), [])
        # 固定しない（ブランチの最新を見る）と、main が進んだだけで壊れる（以前の動き）
        self.assertTrue(self.errors(cq.Source(self.repo)))

    def test_override_compares_with_working_head(self):
        pins = self.pins() | cq.parse_overrides(["main=HEAD"])
        errs = self.errors(cq.Source(self.repo, pins))
        self.assertTrue(errs and "部分がありません" in errs[0], errs)

    def test_override_head_is_local_head_not_origin_head(self):
        # clone には refs/remotes/origin/HEAD（= リモートの main）がある. HEAD は手元の作業中のコミットを指すこと
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "-q", self.repo.as_uri(), str(clone)], check=True)
        (clone / "local/.env.example").write_text("DB_PORT=5432\n", encoding="utf-8")
        git(clone, "commit", "-qam", "work")
        pins = self.pins() | cq.parse_overrides(["main=HEAD"])
        self.assertEqual(self.errors(cq.Source(clone, pins)), [])

    def test_unpinned_ref_is_rejected(self):
        (self.docs / "ch.md").write_text(DOC.replace("@main", "@feature-x"), encoding="utf-8")
        errs = self.errors(cq.Source(self.repo, self.pins()))
        self.assertTrue(errs and "固定していません" in errs[0], errs)

    def test_fetch_takes_only_pinned_sha(self):
        dest = self.tmp / "fetched"
        cq.fetch(dest, self.repo.as_uri(), {"main": self.pinned})
        src = cq.Source(dest, {"main": self.pinned})
        self.assertEqual(src.rev("main"), self.pinned)
        self.assertEqual(src.read("main", "local/.env.example"), "DB_PORT=5432\n")

    def test_load_pins_validates(self):
        p = self.tmp / "pin.json"
        p.write_text(json.dumps({"refs": {"main": "abc", "exercise-base": "0" * 40}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "40 桁"):
            cq.load_pins(p)
        p.write_text(json.dumps({"refs": {"main": "0" * 40}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exercise-base"):
            cq.load_pins(p)
        with self.assertRaises(ValueError):
            cq.parse_overrides(["main"])

    def test_repository_pin_file(self):
        url, pins = cq.load_pins()
        self.assertTrue(url.endswith("/dev-environment.git"))
        self.assertEqual(set(pins), set(cq.REFS))


if __name__ == "__main__":
    unittest.main()
