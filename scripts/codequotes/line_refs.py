"""本文（コードブロックの外）の「`File.java` N〜M 行目」の照合（check_line_refs）."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .blocks import locate, parse_ranges, segments
from .markdown import DOCS, MARKER, Block, default_ref, parse_blocks, prose_lines
from .source import Source

# 本文の行番号の参照（check_line_refs）
LINE_REF_EXTS = ("java", "xml", "yml", "yaml", "sql", "gradle", "feature", "js", "properties", "sh", "ps1", "tf", "hcl")
LINE_REF = re.compile(
    r"`(?P<tok>[^`\n]+)`(?:\s*の\s*|\s*（\s*|\s+)"
    r"(?P<spec>\d+(?:〜\d+)?(?:\s*行目)?(?:\s*[・、]\s*\d+(?:〜\d+)?(?:\s*行目)?)*)\s*行目"
    # 直後に書いたコードも照合する:
    # 「の `x`」「の条件 `x`」（の + 短い名詞）「（`x`）」「: `x`」「が `x`」「は `x`」「に `x`」「）の `x`」
    r"(?:(?:\s*(?:の(?:[^\s`、。|（）「」]{1,6})?|（|[:：]|が|は|に)|\s*）\s*の?)?\s*`(?P<code>[^`\n]+)`)?"
)
# 照合できない参照（コード・メンバー名・隣のコードブロックのどれとも結び付かない行番号）の件数の上限.
# 増やさない. 書くときは「`File.java` N〜M 行目（`メソッド名`）」「… 行目の `コード`」の形にする（CONTRIBUTING.md）
UNVERIFIED_MAX = 0
LINE_SPAN = re.compile(r"(\d+)(?:〜(\d+))?")
FILE_TOKEN = re.compile(r"^[\w./-]+\.(?:" + "|".join(LINE_REF_EXTS) + r")$")
CLASS_TOKEN = re.compile(
    r"^(?P<cls>[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*)(?:\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)(?:\(\))?)?$"
)


def resolve_ref_file(tok: str, files: list[str]) -> tuple[str | None, str | None, str | None]:
    """参照の `...` を（パス, メンバー名, 誤り）にする. 照合しないものは（None, None, None）."""
    if FILE_TOKEN.match(tok):
        if "/" in tok:
            return (tok, None, None) if tok in files else (None, None, f"{tok} がありません")
        hits = [f for f in files if f.rsplit("/", 1)[-1] == tok]
        if len(hits) == 1:
            return hits[0], None, None
        if not hits:
            return None, None, f"{tok} がありません"
        return None, None, f"{tok} は {len(hits)} か所にあります（パスで書いてください）"
    m = CLASS_TOKEN.match(tok)
    if not m:
        return None, None, None
    hits = [f for f in files if f.endswith(f"/{m.group('cls')}.java")]
    if len(hits) != 1:
        return None, None, None  # dev-environment の外のクラス（SpringApplication など）は照合しない
    return hits[0], m.group("member"), None


def code_in(code: str, text: str) -> bool:
    """`fetcher.readLines(...)` のような本文中のコードが text にあるか（空白は比べない. `...` は任意の文字列）."""
    squash = re.compile(r"\s+")
    parts = [re.escape(squash.sub("", p)) for p in re.split(r"\.\.\.|…", code)]
    return re.search(".*?".join(parts), squash.sub("", text), re.S) is not None


# 参照の行と、直後のコードブロックの引用元コメントの間に置いてよい行数（空行・短い説明）
ADJACENT_LINES = 3
# 直前のコードブロックの閉じのフェンスから、参照の行までの行数（ブロックの下の箇条書きの説明）
FOLLOWING_LINES = 8


@dataclass
class LineRefResult:
    """check_line_refs の結果."""

    checked: int = 0  # 照合した参照の数
    errors: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)  # 行があることしか確かめられなかった参照（場所）


def block_lines(block: Block, src: Source) -> tuple[str, str, list[tuple[int, int]]] | None:
    """引用ブロックが実物のどの行か（パス, ブランチ, 範囲）. 引用元コメントが無い・一致しないときは None."""
    m = MARKER.match(block.marker or "")
    if not m:
        return None
    path, ref = m.group("path"), m.group("ref") or "main"
    text = src.read(ref, path) if src.known(ref) else None
    if text is None:
        return None
    if m.group("lines"):
        try:
            return path, ref, parse_ranges(m.group("lines"))
        except ValueError:
            return None
    hit = locate(segments(block.body), text.split("\n"))
    if not hit:
        return None
    return path, ref, [(int(a), int(b)) for a, b in re.findall(r"L(\d+)-L(\d+)", hit)]


def next_block(blocks: list[Block], lineno: int, lines: list[str]) -> Block | None:
    """参照の行の直後（ADJACENT_LINES 行以内. 間に別の行番号の参照が無い）にある引用ブロック."""
    for b in blocks:
        start = b.marker_line or b.line
        if start <= lineno:
            continue
        if start - lineno > ADJACENT_LINES:
            return None
        between = lines[lineno : start - 1]
        return None if any(LINE_REF.search(x) for x in between) else b
    return None


def prev_block(blocks: list[Block], lineno: int, lines: list[str]) -> Block | None:
    """参照の行の直前（FOLLOWING_LINES 行以内. 間に見出しが無い）で閉じた引用ブロック."""
    before = [b for b in blocks if b.line + len(b.body) + 1 < lineno]
    if not before:
        return None
    b = before[-1]
    end = b.line + len(b.body) + 1  # 閉じのフェンスの行
    if lineno - end > FOLLOWING_LINES or any(x.startswith("#") for x in lines[end : lineno - 1]):
        return None
    return b


def covered_by_block(block: Block | None, src: Source, path: str, ref: str, spans: list[tuple[int, int]]) -> bool:
    """直前の引用ブロックが同じファイルで、参照の行をすべて含む（本文はそのブロックの行を説明している）."""
    quoted = block_lines(block, src) if block else None
    if not quoted or quoted[0] != path or quoted[1] != ref:
        return False
    return all(any(qa <= a and b <= qb for qa, qb in quoted[2]) for a, b in spans)


def check_line_refs(doc: Path, src: Source, ref: str | None = None) -> tuple[int, list[str]]:
    """本文の「`File.java` N〜M 行目」を、固定した SHA の実物と照合する.（照合した件数, 誤り）を返す."""
    r = check_line_refs_detail(doc, src, ref)
    return r.checked, r.errors


def check_line_refs_detail(doc: Path, src: Source, ref: str | None = None) -> LineRefResult:
    """check_line_refs の詳細版. 行があることしか確かめられなかった参照（unverified）も返す.

    行番号の参照は、次のどれかで中身と照合する（どれも無いものが unverified）:
    - 直後に書いたコード（「の `x`」「（`x`）」「: `x`」など）がその行にある. メソッド名ならその行がそのメソッドの中
    - `クラス名.メンバー` のメンバーがその行にある
    - 直後（ADJACENT_LINES 行以内）に同じファイルの引用ブロックがあり、その引用が参照の範囲の中にある
    - 直前（FOLLOWING_LINES 行以内）に同じファイルの引用ブロックがあり、参照の行がその引用の中にある
    """
    ref = ref or default_ref(doc)
    rel = doc.relative_to(DOCS.parent).as_posix() if DOCS.parent in doc.parents else str(doc)
    res = LineRefResult()
    if src.rev(ref) is None:
        res.errors.append(f"{rel}: {ref} が dev-environment の clone にありません（git fetch が必要です）")
        return res
    files = src.files(ref)
    lines = doc.read_text(encoding="utf-8").split("\n")
    blocks: list[Block] | None = None
    errs = res.errors
    for lineno, line in prose_lines(doc):
        for m in LINE_REF.finditer(line):
            path, member, err = resolve_ref_file(m.group("tok"), files)
            where = f"{rel}:{lineno}: `{m.group('tok')}` {m.group('spec')} 行目"
            if err:
                res.checked += 1
                errs.append(f"{where}: {err}（@{ref}）")
                continue
            if path is None:
                continue
            res.checked += 1
            file_lines = (src.read(ref, path) or "").split("\n")
            spans = [(int(a), int(b or a)) for a, b in LINE_SPAN.findall(m.group("spec"))]
            bad = [(a, b) for a, b in spans if b < a or a < 1 or b > len(file_lines)]
            if bad:
                errs.append(f"{where}: {path}@{ref} は {len(file_lines)} 行です（範囲の外）")
                continue
            text = "\n".join(x for a, b in spans for x in file_lines[a - 1 : b])
            if not text.strip():
                errs.append(f"{where}: {path}@{ref} の該当行が空行です")
                continue
            if member and not member_covers(member, spans, file_lines):
                errs.append(f"{where}: {path}@{ref} のその行に `{member}` がありません{hint_lines(member, file_lines)}")
                continue
            code = m.group("code")
            if code:
                if not code_matches(code, path, spans, file_lines, text):
                    errs.append(f"{where}: {path}@{ref} のその行に `{code}` がありません{hint_lines(code, file_lines)}")
                continue
            if member:
                continue
            if blocks is None:
                blocks = parse_blocks(doc)
            block = next_block(blocks, lineno, lines)
            quoted = block_lines(block, src) if block else None
            if quoted and quoted[0] == path and quoted[1] == ref:
                outside = [(a, b) for a, b in quoted[2] if not any(s <= a and b <= e for s, e in spans)]
                if outside:
                    got = ",".join(f"L{a}-L{b}" for a, b in quoted[2])
                    errs.append(f"{where}: 直後の引用（{block.where}）は {got} で、参照の範囲の外を含みます")
                continue
            if covered_by_block(prev_block(blocks, lineno, lines), src, path, ref, spans):
                continue
            res.unverified.append(where)
    return res


def code_matches(code: str, path: str, spans: list[tuple[int, int]], file_lines: list[str], text: str) -> bool:
    """参照の直後に書いたコードが、その行にあるか. メソッド名（`register`）なら、その行がそのメソッドの中でもよい."""
    if code_in(code, text) or yaml_key_in(code, path, text):
        return True
    name = code.removesuffix("()")
    return (
        path.endswith(".java")
        and re.fullmatch(r"[a-z_]\w*", name) is not None
        and member_covers(name, spans, file_lines)
    )


JAVA_DECL = re.compile(
    r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:public|protected|private|static|final|abstract|synchronized|default)\s+)*"
    r"(?:<[^>]+>\s+)?[\w.<>\[\],? ]+?\s+(?P<name>\w+)\s*\("
)


def java_decl(line: str) -> re.Match[str] | None:
    """メソッド・コンストラクタの宣言の行（`{` で終わり、制御文・代入・throw new などでない）."""
    if not line.rstrip().endswith("{") or "=" in line.split("(")[0]:
        return None
    if re.match(r"^\s*(?:if|for|while|switch|catch|else|try|do|return|throw|new|synchronized)\b", line):
        return None
    return JAVA_DECL.match(line)


def member_covers(member: str, spans: list[tuple[int, int]], file_lines: list[str]) -> bool:
    """`Class.member`（N〜M 行目）: その行に member があるか、その行が member のメソッドの中にある."""
    for a, b in spans:
        if any(re.search(rf"\b{re.escape(member)}\b", x) for x in file_lines[a - 1 : b]):
            continue
        # a 行目から上にさかのぼり、最初に見つかったメソッドの宣言が member なら、その中の行
        enclosing = next(
            (m.group("name") for x in reversed(file_lines[:a]) if (m := java_decl(x))),
            None,
        )
        if enclosing != member:
            return False
    return True


def yaml_key_in(code: str, path: str, text: str) -> bool:
    """YAML の `spring.messages.basename` のような入れ子のキーは、最後の名前がその行にあればよい."""
    if not path.endswith((".yml", ".yaml")) or not re.fullmatch(r"[\w-]+(?:\.[\w-]+)+", code):
        return False
    return re.search(rf"^\s*{re.escape(code.rsplit('.', 1)[-1])}\s*:", text, re.M) is not None


def hint_lines(code: str, file_lines: list[str]) -> str:
    """同じコードがある行の案内（行番号のずれを直すため）."""
    hits = [str(i) for i, x in enumerate(file_lines, 1) if code_in(code, x)]
    return f"（{'・'.join(hits[:5])} 行目にあります）" if hits else ""
