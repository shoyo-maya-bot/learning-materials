#!/usr/bin/env python3
"""章の構成を検査する（CONTRIBUTING.md のテンプレート）.

- 章のページ（docs/<編>/<NN-NN>-*.md）に、到達目標と必須の見出しがこの順である
- 30 実ソース読解の章は「演習」があり、解答ページ（answers/30-xx.md）へのリンクがあり、解答ページが存在する
- 社名などの禁止語（BANNED）が無い

終了コード: 0 問題なし / 1 問題あり
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
REQUIRED = [
    "何か",
    "なぜ必要か",
    "どうやるか",
    "サンプルアプリでは",
    "なかったら？",
    "理解度チェック",
    "コードを読むときの確認観点",
]
BANNED: list[str] = []  # 実案件の名前などを足す（大文字小文字を区別しない）
CHAPTER = re.compile(r"^\d{2}-\d{2}-.+\.md$")


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(DOCS)
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
    if rel.parts[0] == "30-reading":
        if not any("演習" in h for h in heads):
            errs.append(f"{rel}: 「演習」がありません")
        num = path.name[:5]
        if f"answers/{num}.md" not in text:
            errs.append(f"{rel}: 解答ページ answers/{num}.md へのリンクがありません")
        if not (DOCS / "30-reading/answers" / f"{num}.md").is_file():
            errs.append(f"{rel}: 解答ページ answers/{num}.md がありません")
    for term in BANNED:
        if term.lower() in text.lower():
            errs.append(f"{rel}: 禁止語「{term}」があります")
    return errs


def main() -> int:
    chapters = sorted(p for p in DOCS.rglob("*.md") if CHAPTER.match(p.name) and "answers" not in p.parts)
    errors = [e for p in chapters for e in check(p)]
    for e in errors:
        print(f"NG {e}")
    print(f"章 {len(chapters)} / 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
