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

本文（コードブロックの外）の行番号の参照も照合する（check_line_refs）:

    `DefaultFileFetcher.java` の 33〜35 行目 …  /  `OrderImportJob.java` 51 行目の `fetcher.readLines(...)`
    `MemberServiceTest.get_throwsNotFoundForUnknownId`（61〜67 行目）

- `ファイル名`（拡張子付き。パスでもよい）か `クラス名` / `クラス名.メンバー` の直後の「N 行目」「N〜M 行目」
  （「・」「、」で並べてもよい）を、ページの既定のブランチ（冒頭に exercise-base の注記がある章と解答は
  @exercise-base、それ以外は @main）の、固定した SHA の実物と比べる
- 行がファイルにあること（範囲の行がすべて空行なら誤り）
- 直後に「の `コード`」があれば、そのコードが範囲の中にあること（`...` は任意の文字列）
- `クラス名.メンバー` なら、メンバー名が範囲の中にあること
- ファイル名が同名のファイルに複数当たるときは、パスで書くこと。クラス名で引いてファイルが無いもの
  （Spring の `SpringApplication` など、dev-environment の外のクラス）は照合しない

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
import shutil
import sys
from pathlib import Path

# 役割ごとのモジュール（scripts/codequotes/）. テストや check_versions.py のため、ここからも同じ名前で使えるようにする
from codequotes.blocks import (  # noqa: F401
    ELISION,
    WILDCARD,
    check_block,
    check_title_lines,
    find_run,
    first_mismatch,
    line_matches,
    locate,
    norm,
    parse_ranges,
    segments,
    suggest,
)
from codequotes.line_refs import (  # noqa: F401
    CLASS_TOKEN,
    FILE_TOKEN,
    JAVA_DECL,
    LINE_REF,
    LINE_REF_EXTS,
    LINE_SPAN,
    check_line_refs,
    code_in,
    hint_lines,
    java_decl,
    member_covers,
    resolve_ref_file,
    yaml_key_in,
)
from codequotes.markdown import (  # noqa: F401
    DOCS,
    EXERCISE_NOTE,
    FENCE,
    LINENUMS,
    MARKER,
    MARKER_LOOSE,
    RANGE,
    TITLE,
    TITLE_LINES,
    Block,
    default_ref,
    parse_blocks,
    prose_lines,
)
from codequotes.source import (  # noqa: F401
    PIN_FILE,
    REFS,
    REPO_URL,
    ROOT,
    SHA,
    SOURCE_PREFIXES,
    Source,
    add_source_args,
    fetch,
    load_pins,
    open_source,
    parse_overrides,
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
        line_refs = 0
        for doc in sorted(args.docs.rglob("*.md")):
            n, errs = check_line_refs(doc, src)
            line_refs += n
            errors += errs
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
    print(f"引用 {checked} 件・本文の行番号 {line_refs} 件（{pinned}）/ 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
