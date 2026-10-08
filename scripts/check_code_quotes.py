#!/usr/bin/env python3
"""教材が引用している dev-environment のコードが、実物と一致しているかを検査する.

引用したコードブロックの直前（空行を挟んでもよい）に、次の形のコメントを書きます（CONTRIBUTING.md）。

    <!-- src: sample-app/src/main/java/com/example/sample/member/MemberService.java#L19-L25 @exercise-base -->
    ```java title="sample-app/src/main/java/com/example/sample/member/MemberService.java" linenums="19"
    ...
    ```

- パスは dev-environment のリポジトリ直下から（sample-app/・local/・cloud/）
- `#L19-L25` は行の範囲。抜粋は `#L24-L34,L41-L65` のように範囲を並べる。
  範囲を書くと、ブロックの中身が「その行だけ」と一致することを確かめる（行番号のずれも検出）
- 範囲を省くと、ブロックの中身がファイルのどこかにそのまま（連続して）あることを確かめる
- `@main` / `@exercise-base` は比べるブランチ（省略すると main）. 実際に比べるのは、そのブランチの最新ではなく
  dev-environment-pin.json で固定した SHA（dev-environment の更新で教材が急に壊れないように）
- 比べるときは空白の量と空行を無視する（インデントの違い・行末の空白・空行の有無は差分にしない）
- ブロック内の `// ...`・`# ...`・`（省略）`・`（中略）` だけの行と、
  `// ...（説明）`・`// 46〜50 行目: 登録` の形のコメント行は
  「ここを飛ばした」印。前後はそれぞれ連続して一致すればよい
  （範囲を書いた場合は使わず、範囲を分けて書く）。行の一部の `（省略）` は任意の文字列に一致する
- title が `sample-app/`・`local/`・`cloud/` で始まるブロックには、このコメントが必須（付け忘れを検出）
- linenums="N" を付けたブロックは、N が範囲の始まりと一致していること

使い方:
  python scripts/check_code_quotes.py                       # 固定した SHA の dev-environment を取得して検査
  python scripts/check_code_quotes.py --repo-dir ../dev-environment   # 手元の clone で検査（固定した SHA を含むこと）
  python scripts/check_code_quotes.py --repo-dir ../dev-environment --ref main=HEAD
      # 固定を外し、手元の作業中のコードと比べる（SHA を上げる前の確認）
  python scripts/check_code_quotes.py --suggest             # コメントの無いブロックに、一致する引用元を提案する

終了コード: 0 問題なし / 1 問題あり
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
PIN_FILE = ROOT / "dev-environment-pin.json"  # 引用元の SHA の固定（ここ 1 か所）
REPO_URL = "https://github.com/shoyo-maya-bot/dev-environment.git"
REFS = ("main", "exercise-base")
SHA = re.compile(r"^[0-9a-f]{40}$")
SOURCE_PREFIXES = ("sample-app/", "local/", "cloud/")

MARKER = re.compile(
    r"^\s*<!--\s*src:\s*(?P<path>[^\s#@]+)(?:#(?P<lines>[L0-9,\-]+))?(?:\s+@(?P<ref>[\w./-]+))?\s*-->\s*$"
)
MARKER_LOOSE = re.compile(r"^\s*<!--\s*src:")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
TITLE = re.compile(r'title="(?P<title>[^"]*)"')
TITLE_LINES = re.compile(r"(\d+)(?:〜(\d+))? 行目")
LINENUMS = re.compile(r'linenums="(?P<n>\d+)"')
RANGE = re.compile(r"^L(?P<a>\d+)(?:-L?(?P<b>\d+))?$")
ELISION = re.compile(
    r"^(//|#|--|<!--)?\s*(\.\.\.|…|（省略）|（中略）|\(省略\)|\(中略\))\s*(-->)?$"
    r"|^(//|#|--)\s*(\.\.\.|…)\s*（.*）$"  # 「// ...（S3 から読む）」のように、飛ばした中身を括弧で添えたもの
    r"|^(//|#|--)\s*\d+(〜\d+)?\s*行目\s*[:：]"  # 「// 46〜50 行目: 登録（30-11 で読む）」のような飛ばした箇所の説明
)
WILDCARD = "（省略）"
EXERCISE_NOTE = '!!! note "読むコードは `exercise-base` ブランチ"'


@dataclass
class Block:
    doc: Path
    line: int  # フェンスの行（1 始まり）
    info: str
    body: list[str]
    marker: str | None  # マーカーの行の文字列（無ければ None）
    marker_line: int | None

    @property
    def title(self) -> str:
        m = TITLE.search(self.info)
        return m.group("title") if m else ""

    @property
    def where(self) -> str:
        doc = self.doc.relative_to(DOCS.parent).as_posix() if DOCS.parent in self.doc.parents else self.doc
        return f"{doc}:{self.line}"


def parse_blocks(path: Path) -> list[Block]:
    lines = path.read_text(encoding="utf-8").split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        indent, fence, info = m.group("indent"), m.group("fence"), m.group("info")
        start = i
        body = []
        i += 1
        while i < len(lines):
            close = FENCE.match(lines[i])
            if close and close.group("fence").startswith(fence[0] * len(fence)) and not close.group("info").strip():
                break
            line = lines[i]
            body.append(line[len(indent) :] if line.startswith(indent) else line.lstrip())
            i += 1
        # 直前の空でない行がマーカーか
        j = start - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        marker = lines[j] if j >= 0 and MARKER_LOOSE.match(lines[j]) else None
        blocks.append(Block(path, start + 1, info, body, marker, j + 1 if marker else None))
        i += 1
    return blocks


def norm(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def segments(body: list[str]) -> list[list[str]]:
    """空行を除き、省略の印で区切った連続部分の一覧."""
    out: list[list[str]] = [[]]
    for line in body:
        n = norm(line)
        if not n:
            continue
        if ELISION.match(n):
            out.append([])
        else:
            out[-1].append(n)
    return [s for s in out if s]


def line_matches(snippet: str, actual: str) -> bool:
    if WILDCARD in snippet:
        pattern = ".*?".join(re.escape(p) for p in snippet.split(WILDCARD))
        return re.fullmatch(pattern, actual) is not None
    return snippet == actual


def find_run(seg: list[str], hay: list[str], start: int) -> int:
    """hay[start:] の中で seg が連続して現れる位置（無ければ -1）."""
    for k in range(start, len(hay) - len(seg) + 1):
        if all(line_matches(s, hay[k + t]) for t, s in enumerate(seg)):
            return k
    return -1


def parse_ranges(spec: str) -> list[tuple[int, int]]:
    ranges = []
    for part in spec.split(","):
        m = RANGE.match(part.strip())
        if not m:
            raise ValueError(f"行の範囲 {part!r} が読めません（L10-L25 の形）")
        a = int(m.group("a"))
        b = int(m.group("b") or a)
        if b < a:
            raise ValueError(f"行の範囲 {part!r} が逆順です")
        ranges.append((a, b))
    return ranges


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
        rev = self.rev(ref)
        if not rev:
            return []
        r = subprocess.run(
            ["git", "-C", str(self.repo_dir), "ls-tree", "-r", "--name-only", rev],
            capture_output=True,
            text=True,
            check=False,
        )
        return [p for p in r.stdout.split("\n") if p.startswith(SOURCE_PREFIXES)]


def check_block(block: Block, src: Source) -> list[str]:
    m = MARKER.match(block.marker or "")
    if not m:
        return [f"{block.where}: 引用元コメントの書き方が違います: {block.marker.strip()}"]
    path, ref = m.group("path"), m.group("ref") or "main"
    if not src.known(ref):
        return [f"{block.where}: @{ref} は dev-environment-pin.json で固定していません（{', '.join(src.pins or [])}）"]
    if src.rev(ref) is None:
        want = f"（{src.pins[ref]}）" if src.pins else ""
        return [f"{block.where}: {ref}{want} が dev-environment の clone にありません（git fetch が必要です）"]
    text = src.read(ref, path)
    if text is None:
        return [f"{block.where}: {path} が dev-environment の {ref} にありません"]
    file_lines = text.split("\n")
    errs = []
    title = block.title
    if title.startswith(SOURCE_PREFIXES) and not title.startswith(path):
        errs.append(f"{block.where}: title のパスとコメントのパス（{path}）が違います")
    segs = segments(block.body)
    if not segs:
        return errs + [f"{block.where}: ブロックが空です"]
    if m.group("lines"):
        try:
            ranges = parse_ranges(m.group("lines"))
        except ValueError as e:
            return errs + [f"{block.where}: {e}"]
        ln = LINENUMS.search(block.info)
        if ln and int(ln.group("n")) != ranges[0][0]:
            errs.append(f'{block.where}: linenums="{ln.group("n")}" と範囲の始まり L{ranges[0][0]} が違います')
        errs += check_title_lines(block, ranges, m.group("lines"))
        if ranges[-1][1] > len(file_lines):
            return errs + [
                f"{block.where}: {path}@{ref} は {len(file_lines)} 行しかありません（範囲 {m.group('lines')}）"
            ]
        expected = [norm(x) for a, b in ranges for x in file_lines[a - 1 : b] if norm(x)]
        got = [s for seg in segs for s in seg]
        if len(got) != len(expected) or not all(line_matches(g, e) for g, e in zip(got, expected, strict=True)):
            hint = locate(segs, file_lines)
            errs.append(
                f"{block.where}: {path}#{m.group('lines')} @{ref} と一致しません"
                + (f"（ファイル内では {hint} 行目に同じ内容があります）" if hint else first_mismatch(got, expected))
            )
        return errs
    hay = [norm(x) for x in file_lines]
    hay_idx = [i for i, x in enumerate(hay) if x]
    compact = [hay[i] for i in hay_idx]
    pos = 0
    for seg in segs:
        k = find_run(seg, compact, pos)
        if k < 0:
            errs.append(f"{block.where}: {path} @{ref} に次の部分がありません: {seg[0][:60]}")
            break
        pos = k + len(seg)
    return errs


def check_title_lines(block: Block, ranges: list[tuple[int, int]], spec: str) -> list[str]:
    """title の「（24〜34 行目、41〜65 行目）」と、コメントの範囲が食い違っていないか."""
    if "行目" not in block.title:
        return []
    titled = [(int(a), int(b or a)) for a, b in TITLE_LINES.findall(block.title)]
    inside = all(any(ta <= a and b <= tb for ta, tb in titled) for a, b in ranges)
    covered = all(any(ta <= a and b <= tb for a, b in ranges) for ta, tb in titled)
    if inside and covered:
        return []
    return [f"{block.where}: title の行番号（{block.title}）と範囲 {spec} が合いません"]


def locate(segs: list[list[str]], file_lines: list[str]) -> str | None:
    """内容がファイル内の別の行にあれば、その範囲（L 表記）を返す（行番号だけのずれの案内用）."""
    hay = [norm(x) for x in file_lines]
    idx = [i for i, x in enumerate(hay) if x]
    compact = [hay[i] for i in idx]
    pos, parts = 0, []
    for seg in segs:
        k = find_run(seg, compact, pos)
        if k < 0:
            return None
        parts.append(f"L{idx[k] + 1}-L{idx[k + len(seg) - 1] + 1}")
        pos = k + len(seg)
    return ",".join(parts)


def first_mismatch(got: list[str], expected: list[str]) -> str:
    for i in range(max(len(got), len(expected))):
        g = got[i] if i < len(got) else "<なし>"
        e = expected[i] if i < len(expected) else "<なし>"
        if not line_matches(g, e):
            return f"\n    教材: {g[:80]}\n    実物: {e[:80]}"
    return ""


def default_ref(doc: Path) -> str:
    return "exercise-base" if EXERCISE_NOTE in doc.read_text(encoding="utf-8") else "main"


def suggest(block: Block, src: Source) -> str | None:
    """コメントの無いブロックについて、一致する引用元（ファイルと行）を探す."""
    segs = segments(block.body)
    title = block.title
    # 題名の無い短いブロックは偶然の一致が多いので提案しない
    if not segs or sum(len(s) for s in segs) < (1 if title.startswith(SOURCE_PREFIXES) else 2):
        return None
    first = default_ref(block.doc)
    refs = [first] + [r for r in REFS if r != first]
    if title.startswith(SOURCE_PREFIXES) and "行目" in title:
        # title に書いた行番号で一致するなら、それを使う（行を飛ばした抜粋にも対応）
        path = title.split("（")[0].split(" ")[0]
        spec = ",".join(f"L{a}-L{b or a}" for a, b in TITLE_LINES.findall(title))
        for ref in refs:
            marker = f"<!-- src: {path}#{spec} @{ref} -->"
            trial = Block(block.doc, block.line, block.info, block.body, marker, None)
            if not check_block(trial, src):
                return marker
    for ref in refs:
        files = [f for f in src.files(ref) if not f.endswith(".md")]
        if title.startswith(SOURCE_PREFIXES):
            want = title.split("（")[0].split(" ")[0]
            files = [f for f in files if f == want] or files
        for f in files:
            text = src.read(ref, f)
            if text is None:
                continue
            hit = locate(segs, text.split("\n"))
            if hit:
                # 行番号を示しているブロック（linenums・title の「行目」）だけ範囲を書く。示していなければ範囲は省く
                shows_lines = LINENUMS.search(block.info) or "行目" in title
                return f"<!-- src: {f}#{hit} @{ref} -->" if shows_lines else f"<!-- src: {f} @{ref} -->"
    return None


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add_source_args(ap)
    ap.add_argument("--docs", type=Path, default=DOCS)
    ap.add_argument("--suggest", action="store_true", help="コメントの無いブロックの引用元を提案する")
    args = ap.parse_args(argv)

    try:
        src, tmp = open_source(args.repo_dir, args.repo_url, args.ref)
    except ValueError as e:
        print(f"NG {e}")
        return 1
    try:
        errors: list[str] = []
        checked = 0
        for doc in sorted(args.docs.rglob("*.md")):
            for block in parse_blocks(doc):
                if block.marker:
                    checked += 1
                    errors += check_block(block, src)
                elif args.suggest:
                    s = suggest(block, src)
                    if s:
                        print(f"提案 {block.where}: {s}")
                    elif block.title.startswith(SOURCE_PREFIXES):
                        print(f"不一致 {block.where}: {block.title}")
                elif block.title.startswith(SOURCE_PREFIXES):
                    errors.append(f"{block.where}: title が引用元（{block.title}）なのに src コメントがありません")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    for e in errors:
        print(f"NG {e}")
    pinned = ", ".join(f"{k}={str(v)[:12]}" for k, v in (src.pins or {}).items())
    print(f"引用 {checked} 件（{pinned}）/ 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
