"""本文（コードブロックの外）の「`File.java` N〜M 行目」の照合（check_line_refs）."""

from __future__ import annotations

import re
from pathlib import Path

from .markdown import DOCS, default_ref, prose_lines
from .source import Source

# 本文の行番号の参照（check_line_refs）
LINE_REF_EXTS = ("java", "xml", "yml", "yaml", "sql", "gradle", "feature", "js", "properties", "sh", "ps1", "tf", "hcl")
LINE_REF = re.compile(
    r"`(?P<tok>[^`\n]+)`(?:\s*の\s*|\s*（\s*|\s+)"
    r"(?P<spec>\d+(?:〜\d+)?(?:\s*行目)?(?:\s*[・、]\s*\d+(?:〜\d+)?(?:\s*行目)?)*)\s*行目"
    r"(?:\s*）?\s*の?\s*`(?P<code>[^`\n]+)`)?"
)
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


def check_line_refs(doc: Path, src: Source, ref: str | None = None) -> tuple[int, list[str]]:
    """本文の「`File.java` N〜M 行目」を、固定した SHA の実物と照合する.（照合した件数, 誤り）を返す."""
    ref = ref or default_ref(doc)
    rel = doc.relative_to(DOCS.parent).as_posix() if DOCS.parent in doc.parents else str(doc)
    if src.rev(ref) is None:
        return 0, [f"{rel}: {ref} が dev-environment の clone にありません（git fetch が必要です）"]
    files = src.files(ref)
    checked, errs = 0, []
    for lineno, line in prose_lines(doc):
        for m in LINE_REF.finditer(line):
            path, member, err = resolve_ref_file(m.group("tok"), files)
            where = f"{rel}:{lineno}: `{m.group('tok')}` {m.group('spec')} 行目"
            if err:
                checked += 1
                errs.append(f"{where}: {err}（@{ref}）")
                continue
            if path is None:
                continue
            checked += 1
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
            if code and not code_in(code, text) and not yaml_key_in(code, path, text):
                errs.append(f"{where}: {path}@{ref} のその行に `{code}` がありません{hint_lines(code, file_lines)}")
    return checked, errs


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
