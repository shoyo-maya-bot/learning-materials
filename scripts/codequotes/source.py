"""dev-environment の clone から、固定した SHA のファイルを読む（check_code_quotes と check_versions の共通部分）."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN_FILE = ROOT / "dev-environment-pin.json"  # 引用元の SHA の固定（ここ 1 か所）
REPO_URL = "https://github.com/shoyo-maya-bot/dev-environment.git"
REFS = ("main", "exercise-base")
SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_PREFIXES = ("sample-app/", "local/", "cloud/")


class SourceUnavailable(ValueError):
    """dev-environment を用意できない（git が無い・取得できない・--repo-dir が git の clone でない）.

    教材の誤りではないので、検査スクリプトは終了コード 2 にする.
    """


FETCH_HINT = "ネットワークと取得元の URL を確かめてください。手元の clone なら --repo-dir"


def _git(args: list[str], what: str, hint: str = FETCH_HINT) -> subprocess.CompletedProcess[str]:
    """git を実行する. git が無い・失敗したら SourceUnavailable（トレースバックにしない）."""
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    except OSError:  # FileNotFoundError など（PATH に git が無い）
        raise SourceUnavailable(f"{what}: git コマンドが見つかりません（Git を入れて PATH を通してください）") from None
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or "").strip().splitlines()
        reason = detail[-1] if detail else f"終了コード {e.returncode}"
        raise SourceUnavailable(f"{what}: {reason}（{hint}）") from None


def load_pins(path: Path = PIN_FILE) -> tuple[str, dict[str, str]]:
    """dev-environment-pin.json を読み、（リポジトリの URL, {ブランチ名: SHA}）を返す."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
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
    _git(["init", "-q", str(dest)], "作業用の git リポジトリを作れません")
    specs = [f"+{sha}:refs/remotes/origin/{name}" for name, sha in pins.items()]
    _git(["-C", str(dest), "fetch", "-q", "--depth", "1", url, *specs], f"{url} から固定した SHA を取得できません")


def latest_revs(url: str, names: list[str]) -> dict[str, str]:
    """取得元のブランチ（names）の最新の SHA を git ls-remote で調べる. 調べられない・ブランチが無いなら ValueError."""
    r = _git(["ls-remote", url, *(f"refs/heads/{n}" for n in names)], f"{url} のブランチの最新を調べられません")
    found = {}
    for line in r.stdout.splitlines():
        sha, _, ref = line.partition("\t")
        name = ref.strip().removeprefix("refs/heads/")
        if name in names and SHA.match(sha):
            found[name] = sha
    missing = [n for n in names if n not in found]
    if missing:
        raise ValueError(f"{url} にブランチ {', '.join(missing)} がありません")
    return found


def open_source(
    repo_dir: Path | None, repo_url: str | None, overrides: list[str], latest: bool = False
) -> tuple[Source, Path | None]:
    """引用元を用意する. 戻り値の 2 つ目は、後で消す一時ディレクトリ（--repo-dir のときは None）.

    latest なら、固定した SHA の代わりに各ブランチの最新（取得元の git ls-remote）と比べる（週 1 回の定期検査用）.
    --ref で個別に指定したものは、それを優先する.
    """
    url, pins = load_pins()
    if latest:
        revs = latest_revs(repo_url or url, list(pins))
        for name, sha in revs.items():
            moved = "固定と同じ" if sha == pins[name] else f"固定 {pins[name][:12]} から進んでいます"
            print(f"比べる dev-environment: {name} の最新 {sha[:12]}（{moved}）")
        pins.update(revs)
    pins.update(parse_overrides(overrides))
    if repo_dir:
        _git(
            ["-C", str(repo_dir), "rev-parse", "--git-dir"],
            f"--repo-dir {repo_dir} は git の clone ではありません",
            "dev-environment を clone したフォルダを指定してください",
        )
        return Source(repo_dir, pins), None
    tmp = Path(tempfile.mkdtemp(prefix="dev-environment-"))
    try:
        fetch(tmp, repo_url or url, {k: v for k, v in pins.items() if SHA.match(v)})
    except SourceUnavailable:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
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
    ap.add_argument(
        "--latest",
        action="store_true",
        help="固定した SHA ではなく、dev-environment の各ブランチの最新と比べる（週 1 回の定期検査で使う）",
    )
