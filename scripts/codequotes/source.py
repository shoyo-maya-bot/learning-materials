"""dev-environment の clone から、固定した SHA のファイルを読む（check_code_quotes と check_versions の共通部分）."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = ROOT / "dev-environment-pin.json"  # 引用元の SHA の固定（ここ 1 か所）
REPO_URL = "https://github.com/shoyo-maya-bot/dev-environment.git"
REFS = ("main", "exercise-base")
SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_PREFIXES = ("sample-app/", "local/", "cloud/")


def load_pins(path: Path = PIN_FILE) -> tuple[str, dict[str, str]]:
    """dev-environment-pin.json を読み、（リポジトリの URL, {ブランチ名: SHA}）を返す."""
    data = json.loads(path.read_text(encoding="utf-8"))
    refs = data.get("refs") or {}
    for name in REFS:
        if name not in refs:
            raise ValueError(f"{path.name}: refs.{name} がありません")
    for name, sha in refs.items():
        if not SHA.match(str(sha)):
            raise ValueError(f"{path.name}: refs.{name} は 40 桁の SHA で書いてください（{sha}）")
    return data.get("repo_url") or REPO_URL, dict(refs)


def parse_overrides(items: list[str]) -> dict[str, str]:
    """--ref main=HEAD の形を {ブランチ名: rev} にする."""
    out = {}
    for item in items:
        name, sep, rev = item.partition("=")
        if not sep or not name or not rev:
            raise ValueError(f"--ref は 名前=rev の形で書いてください（{item}）")
        out[name] = rev
    return out


class Source:
    """dev-environment の clone から、ブランチごとのファイルを読む.

    pins を渡すと、引用元コメントの @main などをその rev（固定した SHA）に読み替え、pins に無い名前は受け付けない.
    pins が None なら、名前をそのままブランチとして読む（テスト用）.
    """

    def __init__(self, repo_dir: Path, pins: dict[str, str] | None = None):
        self.repo_dir = repo_dir
        self.pins = pins
        self.cache: dict[tuple[str, str], str | None] = {}
        self.rev_cache: dict[str, str | None] = {}
        self.files_cache: dict[str, list[str]] = {}

    def known(self, ref: str) -> bool:
        return self.pins is None or ref in self.pins

    def rev(self, ref: str) -> str | None:
        if ref not in self.rev_cache:
            self.rev_cache[ref] = self._resolve(ref)
        return self.rev_cache[ref]

    def _resolve(self, ref: str) -> str | None:
        if not self.known(ref):
            return None
        target = self.pins[ref] if self.pins is not None else ref
        if SHA.match(target) or target == "HEAD":
            # HEAD は手元の作業中のコミット（refs/remotes/origin/HEAD = リモートの main と取り違えない）
            cands: tuple[str, ...] = (target,)
        else:
            cands = (f"refs/remotes/origin/{target}", f"refs/heads/{target}", target)
        for cand in cands:
            r = subprocess.run(
                ["git", "-C", str(self.repo_dir), "rev-parse", "--verify", "-q", f"{cand}^{{commit}}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        return None

    def read(self, ref: str, path: str) -> str | None:
        key = (ref, path)
        if key not in self.cache:
            rev = self.rev(ref)
            text = None
            if rev:
                r = subprocess.run(
                    ["git", "-C", str(self.repo_dir), "show", f"{rev}:{path}"], capture_output=True, check=False
                )
                if r.returncode == 0:
                    text = r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
            self.cache[key] = text
        return self.cache[key]

    def files(self, ref: str) -> list[str]:
        if ref not in self.files_cache:
            rev = self.rev(ref)
            if not rev:
                return []
            r = subprocess.run(
                ["git", "-C", str(self.repo_dir), "ls-tree", "-r", "--name-only", rev],
                capture_output=True,
                text=True,
                check=False,
            )
            self.files_cache[ref] = [p for p in r.stdout.split("\n") if p.startswith(SOURCE_PREFIXES)]
        return self.files_cache[ref]


def fetch(dest: Path, url: str, pins: dict[str, str]) -> None:
    """固定した SHA だけを取得し、refs/remotes/origin/<名前> に置く（ブランチの最新は見ない）."""
    subprocess.run(["git", "init", "-q", str(dest)], check=True)
    specs = [f"+{sha}:refs/remotes/origin/{name}" for name, sha in pins.items()]
    subprocess.run(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", url, *specs], check=True)


def open_source(repo_dir: Path | None, repo_url: str | None, overrides: list[str]) -> tuple[Source, Path | None]:
    """引用元を用意する. 戻り値の 2 つ目は、後で消す一時ディレクトリ（--repo-dir のときは None）."""
    url, pins = load_pins()
    pins.update(parse_overrides(overrides))
    if repo_dir:
        return Source(repo_dir, pins), None
    tmp = Path(tempfile.mkdtemp(prefix="dev-environment-"))
    fetch(tmp, repo_url or url, {k: v for k, v in pins.items() if SHA.match(v)})
    return Source(tmp, pins), tmp


def add_source_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--repo-dir", type=Path, help="dev-environment の clone（指定すると取得しない）")
    ap.add_argument("--repo-url", help="取得元（既定は dev-environment-pin.json の repo_url）")
    ap.add_argument(
        "--ref",
        action="append",
        default=[],
        metavar="名前=REV",
        help="固定した SHA の代わりに比べる rev（例: --repo-dir ../dev-environment --ref main=HEAD）",
    )
