"""引用したコードブロックと実物の照合（src コメント）と、引用元の提案（--suggest）."""

from __future__ import annotations

import re

from .markdown import LINENUMS, MARKER, RANGE, TITLE_LINES, Block, default_ref
from .source import REFS, SOURCE_PREFIXES, Source

ELISION = re.compile(
    r"^(//|#|--|<!--)?\s*(\.\.\.|…|（省略）|（中略）|\(省略\)|\(中略\))\s*(-->)?$"
    r"|^(//|#|--)\s*(\.\.\.|…)\s*（.*）$"  # 「// ...（S3 から読む）」のように、飛ばした中身を括弧で添えたもの
    r"|^(//|#|--)\s*\d+(〜\d+)?\s*行目\s*[:：]"  # 「// 46〜50 行目: 登録（30-11 で読む）」のような飛ばした箇所の説明
)
WILDCARD = "（省略）"


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
