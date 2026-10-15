#!/usr/bin/env python3
"""章の構成を検査する（CONTRIBUTING.md のテンプレート）.

- 章のページ（docs/<編>/<NN-NN>-*.md）に、到達目標と必須の見出しがこの順である
- 30 実ソース読解の章は「演習」があり、解答ページ（answers/30-xx.md）へのリンクがあり、解答ページが存在する
- docs/ のすべての .md に、禁止語（banned-terms.txt. 実在の会社名・個人のメールアドレスなど）が無い.
  禁止語のリストが読めない・空のときも失敗にする（検査が黙って無効にならないように）.
  `path:` で始まる語（ローカルのユーザーパス）は大文字小文字を区別し、行頭・空白・クォート・括弧の直後から
  始まるパスの形のときだけ当てる（`/api/users/{id}` のような URL の一部は誤検出しない）.
  照合の前に、本文と禁止語の両方を NFKC で正規化する（全角の「＠ｇｍａｉｌ．ｃｏｍ」や「㈱」も当てる）
- ページは BOM 付き（UTF-8 with BOM）でも読める（utf-8-sig）

終了コード: 0 問題なし / 1 問題あり
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
BANNED_FILE = ROOT / "banned-terms.txt"
REQUIRED = [
    "何か",
    "なぜ必要か",
    "どうやるか",
    "サンプルアプリでは",
    "なかったら？",
    "理解度チェック",
    "コードを読むときの確認観点",
]
CHAPTER = re.compile(r"^\d{2}-\d{2}-.+\.md$")
PATH_PREFIX = "path:"
# ローカルパスが始まる位置: 行頭・空白・クォート・バッククォート・括弧・= の直後
PATH_START = r"(?:^|(?<=[\s'\"`(（「\[<=]))"


def load_banned(path: Path = BANNED_FILE) -> list[str]:
    """禁止語のリスト（1 行 1 語、# から行末はコメント）. 読めない・空なら ValueError."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise ValueError(f"禁止語のリスト {path.name} が読めません（{e.strerror}）") from e
    terms = []
    for line in text.splitlines():
        term = line.split(" #", 1)[0].strip() if not line.lstrip().startswith("#") else ""
        if term:
            terms.append(term)
    if not terms:
        raise ValueError(f"禁止語のリスト {path.name} が空です（検査が無効になります）")
    return terms


def check(path: Path, docs: Path = DOCS) -> list[str]:
    """章のページの構成."""
    text = path.read_text(encoding="utf-8-sig")
    rel = path.relative_to(docs).as_posix()  # Windows でも / 区切りで出す
    errs = []
    if '!!! abstract "到達目標"' not in text:
        errs.append(f'{rel}: 到達目標（!!! abstract "到達目標"）がありません')
    heads = re.findall(r"^## (.+)$", text, re.M)
    pos = -1
    for req in REQUIRED:
        idx = next((i for i, h in enumerate(heads) if req in h), None)
        if idx is None:
            errs.append(f"{rel}: 見出し「{req}」がありません")
        elif idx < pos:
            errs.append(f"{rel}: 見出し「{req}」の順番が違います")
        else:
            pos = idx
    if rel.split("/", 1)[0] == "30-reading":
        if not any("演習" in h for h in heads):
            errs.append(f"{rel}: 「演習」がありません")
        num = path.name[:5]
        if f"answers/{num}.md" not in text:
            errs.append(f"{rel}: 解答ページ answers/{num}.md へのリンクがありません")
        if not (docs / "30-reading/answers" / f"{num}.md").is_file():
            errs.append(f"{rel}: 解答ページ answers/{num}.md がありません")
    return errs


def banned_matcher(term: str) -> tuple[str, re.Pattern[str]]:
    """禁止語 1 つを（表示名, 正規表現）にする.

    ふつうの語は大文字小文字を区別せず、どこにあっても当てる.
    `path:/Users/` の形（ローカルのユーザーパス）は大文字小文字を区別し、パスの始まりの位置だけに当てる.
    """
    if term.startswith(PATH_PREFIX):
        word = term[len(PATH_PREFIX) :].strip()
        return word, re.compile(PATH_START + re.escape(nfkc(word)))
    return term, re.compile(re.escape(nfkc(term)), re.IGNORECASE)


def nfkc(text: str) -> str:
    """全角・半角などの表記ゆれをそろえる（禁止語の照合用. 本文も禁止語もこれを通してから比べる）."""
    return unicodedata.normalize("NFKC", text)


def check_banned(path: Path, banned: list[str], docs: Path = DOCS) -> list[str]:
    """禁止語. 行番号付きで返す（大文字小文字の扱いと当てる位置は banned_matcher. 照合は NFKC で正規化して）."""
    rel = path.relative_to(docs).as_posix()  # Windows でも / 区切りで出す
    matchers = [banned_matcher(t) for t in banned]
    errs = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        norm = nfkc(line)
        errs += [f"{rel}:{lineno}: 禁止語「{name}」があります" for name, pat in matchers if pat.search(norm)]
    return errs


def run(docs: Path = DOCS, banned_file: Path = BANNED_FILE) -> tuple[int, list[str]]:
    """（章の数, 誤り）."""
    try:
        banned = load_banned(banned_file)
    except ValueError as e:
        return 0, [str(e)]
    chapters = sorted(p for p in docs.rglob("*.md") if CHAPTER.match(p.name) and "answers" not in p.parts)
    errors = [e for p in chapters for e in check(p, docs)]
    errors += [e for p in sorted(docs.rglob("*.md")) for e in check_banned(p, banned, docs)]
    return len(chapters), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--docs", type=Path, default=DOCS)
    ap.add_argument("--banned", type=Path, default=BANNED_FILE, help="禁止語のリスト（既定は banned-terms.txt）")
    args = ap.parse_args(argv)
    count, errors = run(args.docs, args.banned)
    for e in errors:
        print(f"NG {e}")
    print(f"章 {count} / 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
