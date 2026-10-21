#!/usr/bin/env python3
"""教材の Java のコード例（「例:」「悪い例」「修正案」など、src コメントの無い ```java のブロック）の構文を検査する.

src コメントの付いた引用は check_code_quotes.py が dev-environment の実物と照合するので、ここでは見ない。
コード例は実物と照合できないため、少なくとも Java として読めること（構文）を確かめる。
型・import・メソッドの有無は見ない（断片なのでコンパイルはしない）。

- 構文の検査は JavaParser（javaparser-core）で行う。言語レベルは mkdocs.yml の `extra.versions.java`
- 断片が多いので「ファイル全体」「クラスの中身」「メソッドの中身」の 3 通りで読み、どれかで読めれば OK
- 「ここを飛ばした」印の行（`...`・`…`・`（省略）`・`（中略）` だけの行）はコメントとして扱う。
  式の途中を飛ばすときは `/* ... */` と書く（`foo(...)` のような書き方は構文の誤りになる）
- わざと構文が誤ったコードを見せるブロックは、直前に `<!-- java-syntax: skip 理由 -->` を書くと検査しない（理由は必須）
- 型の食い違いのうち、機械で見つけやすいものだけを Java なしで確かめる: 同じページで宣言した record の変数に、
  その record に無いアクセサ（`msg.memberId()` など）を呼んでいないか（record_accessor_errors）

使い方:
  python scripts/check_java_examples.py                 # javaparser-core を取得（.cache/）して検査
  python scripts/check_java_examples.py --jar PATH      # 手元の javaparser-core の jar を使う
  python scripts/check_java_examples.py --list          # 検査する・しないブロックの一覧

必要なもの: Java 17 以上（java コマンド）。

終了コード: 0 問題なし / 1 問題あり / 2 Java や jar が使えない
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from codequotes.markdown import DOCS, Block, parse_blocks
from codequotes.source import ROOT

JAVAPARSER_VERSION = "3.28.2"
JAVAPARSER_SHA256 = "b5499a3b1c40b16c0671fabe478c9aafeab38160c6fde74a6c13f42d86716ecd"
JAVAPARSER_URL = (
    "https://repo1.maven.org/maven2/com/github/javaparser/javaparser-core/"
    f"{JAVAPARSER_VERSION}/javaparser-core-{JAVAPARSER_VERSION}.jar"
)
CACHE_DIR = ROOT / ".cache" / "javaparser"
CHECKER = Path(__file__).resolve().parent / "java" / "JavaSyntaxCheck.java"
MKDOCS = ROOT / "mkdocs.yml"

SKIP = re.compile(r"^\s*<!--\s*java-syntax:\s*skip(?P<reason>[^>]*?)\s*-->\s*$")
SKIP_LOOSE = re.compile(r"^\s*<!--\s*java-syntax:")
ELISION_LINE = re.compile(r"^(?P<indent>\s*)(?:\.\.\.|…+|（省略）|（中略）)\s*$")


@dataclass
class Example:
    block: Block
    skip_reason: str | None  # skip の印があればその理由


def is_java(block: Block) -> bool:
    words = block.info.split()
    return bool(words) and words[0] == "java"


def preceding_line(lines: list[str], fence_line: int) -> str:
    """フェンスの直前の空でない行（src コメントの上に書いた skip の印も拾えるよう、src コメントは飛ばす）."""
    j = fence_line - 2
    while j >= 0 and (not lines[j].strip() or lines[j].lstrip().startswith("<!-- src:")):
        j -= 1
    return lines[j] if j >= 0 else ""


def examples(doc: Path) -> tuple[list[Example], list[str]]:
    """そのページの、src コメントの無い ```java のブロックと、skip の印の書き方の誤り."""
    lines = doc.read_text(encoding="utf-8-sig").split("\n")
    out: list[Example] = []
    errors: list[str] = []
    for block in parse_blocks(doc):
        if not is_java(block) or block.marker:
            continue
        prev = preceding_line(lines, block.line)
        reason = None
        if SKIP_LOOSE.match(prev):
            m = SKIP.match(prev)
            reason = m.group("reason").strip() if m else ""
            if not reason:
                errors.append(
                    f"{block.where}: java-syntax: skip には理由を書いてください"
                    "（例: <!-- java-syntax: skip 誤りの例 -->）"
                )
                reason = None
        out.append(Example(block, reason))
    return out, errors


def prepare(body: list[str]) -> str:
    """「ここを飛ばした」印の行をコメントにする（行の数は変えない. 誤りの行番号がずれないように）."""
    out = []
    for line in body:
        m = ELISION_LINE.match(line)
        out.append(f"{m.group('indent')}// ..." if m else line)
    return "\n".join(out) + "\n"


def language_level(mkdocs: Path = MKDOCS) -> str:
    """mkdocs.yml の extra.versions.java（例: "17"）から JavaParser の言語レベル（JAVA_17）を作る."""
    m = re.search(r"^\s+java:\s*[\"']?(\d+)[\"']?\s*$", mkdocs.read_text(encoding="utf-8-sig"), re.M)
    if not m:
        raise ValueError(f"{mkdocs.name} に extra.versions.java がありません")
    return f"JAVA_{m.group(1)}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_jar(jar: Path | None) -> Path:
    """javaparser-core の jar. 指定が無ければ .cache/ に取得し、SHA-256 を確かめる."""
    if jar is not None:
        if not jar.is_file():
            raise ValueError(f"jar がありません: {jar}")
        return jar
    path = CACHE_DIR / f"javaparser-core-{JAVAPARSER_VERSION}.jar"
    if not path.is_file() or sha256(path) != JAVAPARSER_SHA256:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        # URL は上の定数（https の Maven Central）だけ. 中身は SHA-256 で確かめる
        with urllib.request.urlopen(JAVAPARSER_URL, timeout=60) as r, tmp.open("wb") as f:  # nosec B310
            shutil.copyfileobj(r, f)
        if sha256(tmp) != JAVAPARSER_SHA256:
            tmp.unlink()
            raise ValueError(f"javaparser-core の SHA-256 が一致しません（{JAVAPARSER_URL}）")
        tmp.replace(path)
    return path


def parse_output(stdout: str) -> dict[str, tuple[int, int, str, str] | None]:
    """JavaSyntaxCheck の出力 → {ファイル: None（OK）か (行, 列, 読み方, メッセージ)}."""
    out: dict[str, tuple[int, int, str, str] | None] = {}
    for line in stdout.splitlines():
        parts = line.split("\t")
        if parts[0] == "OK" and len(parts) == 2:
            out[parts[1]] = None
        elif parts[0] == "NG" and len(parts) == 6:
            out[parts[1]] = (int(parts[2]), int(parts[3]), parts[4], parts[5])
    return out


def check(targets: list[Example], jar: Path, level: str) -> list[str]:
    """ブロックを一時ファイルに書き、JavaSyntaxCheck でまとめて読む. 誤りの一覧を返す."""
    java = shutil.which("java")
    if not java:
        raise ValueError("java コマンドがありません（Java 17 以上が必要です）")
    tmp = Path(tempfile.mkdtemp(prefix="java-examples-"))
    try:
        files = {}
        for i, ex in enumerate(targets):
            f = tmp / f"Example{i:04d}.java"
            f.write_text(prepare(ex.block.body), encoding="utf-8")
            files[str(f)] = ex
        if not files:
            return []
        cmd = [java, "-cp", str(jar), str(CHECKER), level, *files]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)  # nosec B603
        results = parse_output(r.stdout)
        if r.returncode not in (0, 1) or set(results) != set(files):
            raise ValueError(f"JavaSyntaxCheck が失敗しました（終了コード {r.returncode}）\n{r.stderr.strip()}")
        errors = []
        for f, ex in files.items():
            res = results[f]
            if res is None:
                continue
            line, col, mode, msg = res
            doc = ex.block.where.rsplit(":", 1)[0]
            errors.append(f"{doc}:{ex.block.line + line}:{col}: Java の構文の誤り（{msg}. 読み方 {mode}）")
        return errors
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


RECORD = re.compile(r"\brecord\s+(?P<name>[A-Z]\w*)\s*(?:<[^>]*>)?\s*\(")
OBJECT_METHODS = {"equals", "hashCode", "toString", "getClass"}


def _closing(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """text[start] が open_ch のとき、対応する close_ch の位置（無ければ -1）."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top(text: str) -> list[str]:
    """カンマで分ける（括弧・山括弧の中のカンマでは分けない）."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [x for x in parts if x.strip()]


def records(text: str) -> dict[str, set[str]]:
    """Java のテキストで宣言した record → 呼べるメソッド名（コンポーネントのアクセサと本体で宣言したメソッド）."""
    out: dict[str, set[str]] = {}
    for m in RECORD.finditer(text):
        open_at = m.end() - 1
        close_at = _closing(text, open_at, "(", ")")
        if close_at < 0:
            continue
        names = set()
        for comp in _split_top(text[open_at + 1 : close_at]):
            words = re.findall(r"\w+", re.sub(r"@\w+(?:\([^)]*\))?", " ", comp))
            if words:
                names.add(words[-1])
        rest = text[close_at + 1 :]
        body = re.match(r"\s*(?:implements\s+[\w.<>, ]+)?\s*\{", rest)
        if body:
            start = close_at + 1 + body.end() - 1
            end = _closing(text, start, "{", "}")
            names |= set(re.findall(r"\b(\w+)\s*\([^;{}]*\)\s*(?:throws\s+[\w., ]+)?\{", text[start + 1 : end]))
        out[m.group("name")] = names
    return out


def record_accessor_errors(doc: Path) -> list[str]:
    """同じページで宣言した record の変数に、その record に無いメソッドを呼んでいるコード例.

    例: `record OrderMessage(String orderNo) {}` を見せたあとで `OrderMessage msg = ...; msg.memberId()` と書く
    （コンパイルできない）。src コメントの付いた引用の record も宣言として数えるが、確かめるのはコード例だけ。
    """
    blocks = [b for b in parse_blocks(doc) if is_java(b)]
    known: dict[str, set[str]] = {}
    for b in blocks:
        known.update(records("\n".join(b.body)))
    if not known:
        return []
    errors = []
    types = "|".join(map(re.escape, known))
    decl = re.compile(rf"\b(?P<type>{types})\s+(?P<var>[a-z]\w*)\s*[=;:,)]")
    for b in blocks:
        if b.marker:
            continue
        text = "\n".join(b.body)
        variables = {m.group("var"): m.group("type") for m in decl.finditer(text)}
        for var, typ in variables.items():
            for call in re.finditer(rf"\b{re.escape(var)}\.(?P<m>\w+)\s*\(", text):
                name = call.group("m")
                if name in known[typ] or name in OBJECT_METHODS:
                    continue
                line = b.line + text[: call.start()].count("\n") + 1
                doc_name = b.where.rsplit(":", 1)[0]
                errors.append(
                    f"{doc_name}:{line}: {var}.{name}() — record {typ} に {name} がありません"
                    f"（このページの {typ} の宣言: {', '.join(sorted(known[typ])) or 'なし'}）"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--docs", type=Path, default=DOCS)
    ap.add_argument("--jar", type=Path, help="javaparser-core の jar（省略すると取得する）")
    ap.add_argument("--list", action="store_true", help="検査する・しないブロックの一覧を出す")
    args = ap.parse_args(argv)

    all_examples: list[Example] = []
    errors: list[str] = []
    for doc in sorted(args.docs.rglob("*.md")):
        exs, errs = examples(doc)
        all_examples += exs
        errors += errs
        errors += record_accessor_errors(doc)
    targets = [ex for ex in all_examples if ex.skip_reason is None]
    skipped = [ex for ex in all_examples if ex.skip_reason is not None]
    if args.list:
        for ex in all_examples:
            print(f"{'skip' if ex.skip_reason else 'check'}\t{ex.block.where}\t{ex.skip_reason or ''}")

    try:
        errors += check(targets, ensure_jar(args.jar), language_level())
    except (ValueError, OSError) as e:
        print(f"NG {e}")
        return 2
    for e in errors:
        print(f"NG {e}")
    print(f"Java のコード例 {len(targets)} 件を検査（skip {len(skipped)} 件）/ 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
