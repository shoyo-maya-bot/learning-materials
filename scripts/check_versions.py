#!/usr/bin/env python3
"""教材の本文に書く版（Java・Spring Boot・MyBatis・Gradle・PostgreSQL）を検査する.

本文の版は mkdocs.yml の extra.versions の 1 か所にまとめ、本文では {{ versions.spring_boot }} のように参照する
（mkdocs-macros。参照するページは先頭に render_macros: true を書く）。このスクリプトは次を確かめる:

1. extra.versions の値が、dev-environment の extra.versions.branch（exercise-base）の実ファイルと一致する
   （比べるのは dev-environment-pin.json で固定した SHA. check_code_quotes.py と同じ）
   - spring_boot・mybatis_starter・karate・java: sample-app/build.gradle
   - gradle: sample-app/gradle/wrapper/gradle-wrapper.properties
   - postgres: local/docker-compose.yml
2. 本文（コードブロックの外）に、版を直接書いていない（「Spring Boot 4.0」「Gradle 8.14」など）
3. {{ versions.* }} を使うページに render_macros: true がある（無いと {{ }} がそのまま表示される）

コードブロックの中の版は、引用元のコメント（src:）で check_code_quotes.py が実物と照合する.

使い方:
  python scripts/check_versions.py                                    # 固定した SHA の dev-environment を取得して検査
  python scripts/check_versions.py --repo-dir ../dev-environment      # 手元の clone で検査

終了コード: 0 問題なし / 1 問題あり
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_code_quotes import FENCE, Source, add_source_args, open_source  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"

# 版の名前 → （dev-environment のファイル, 版を取り出す正規表現）
SOURCES = {
    "java": ("sample-app/build.gradle", r"options\.release\s*=\s*(\d+)"),
    "spring_boot": ("sample-app/build.gradle", r"id 'org\.springframework\.boot' version '([\d.]+)'"),
    "mybatis_starter": ("sample-app/build.gradle", r"mybatis-spring-boot-starter:([\d.]+)'"),
    "gradle": ("sample-app/gradle/wrapper/gradle-wrapper.properties", r"gradle-([\d.]+)-bin\.zip"),
    "postgres": ("local/docker-compose.yml", r"image:\s*postgres:(\d+)"),
    "karate": ("sample-app/build.gradle", r"karate-junit5:([\d.]+)'"),
}

# 本文に直接書いてはいけない版の書き方（コードブロックの外）
#   MyBatis 本体（MyBatis 3）は sample-app が直接版を書いていないので対象外.
#   「RDS PostgreSQL 1 台」のような数は版ではない
LITERAL = re.compile(
    r"(Spring Boot|Gradle|mybatis-spring-boot-starter)\s*\d+(\.\d+)*"
    r"|PostgreSQL\s*1\d\b"
    r"|postgresql\.org/docs/\d+"
    r"|gradle-\d+\.\d+(\.\d+)?-bin"
)
# 上に加えて、extra.versions の「x.y.z」の値そのもの（「6 行目の 4.0.7」のような書き方）も本文に直接書かない
FULL_VERSION_KEYS = ("spring_boot", "mybatis_starter", "gradle", "karate")
MACRO = re.compile(r"\{\{\s*versions\.(\w+)\s*\}\}")
FRONT_MATTER_MACROS = re.compile(r"\A---\n(?:.*\n)*?render_macros:\s*true\n(?:.*\n)*?---\n")


def load_versions(mkdocs_yml: Path) -> dict[str, str]:
    """mkdocs.yml の extra.versions を読む（!!python/name などのタグがあるので YAML ライブラリは使わない）."""
    versions: dict[str, str] = {}
    in_extra = in_versions = False
    for line in mkdocs_yml.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_extra = line.startswith("extra:")
            in_versions = False
            continue
        if in_extra and indent == 2:
            in_versions = line.strip() == "versions:"
            continue
        if in_versions and indent == 4:
            m = re.match(r"^\s*(\w+):\s*\"?([^\"#]*?)\"?\s*(#.*)?$", line)
            if m:
                versions[m.group(1)] = m.group(2)
    return versions


def prose_lines(text: str) -> list[tuple[int, str]]:
    """コードブロックと HTML コメントの外の行（行番号は 1 始まり）."""
    out = []
    fence = None
    for i, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group("fence")[0] * len(m.group("fence"))
            continue
        if fence is not None:
            if line.strip().startswith(fence) and line.strip().strip(fence[0]) == "":
                fence = None
            continue
        if line.strip().startswith("<!--"):
            continue
        out.append((i, line))
    return out


def check_sources(versions: dict[str, str], src: Source) -> list[str]:
    errors = []
    branch = versions.get("branch")
    if not branch:
        return ["mkdocs.yml: extra.versions.branch（どのブランチの版を書くか）がありません"]
    if not src.known(branch):
        return [f"mkdocs.yml: extra.versions.branch の {branch} は dev-environment-pin.json で固定していません"]
    for name, (path, pattern) in SOURCES.items():
        if name not in versions:
            errors.append(f"mkdocs.yml: extra.versions.{name} がありません")
            continue
        text = src.read(branch, path)
        if text is None:
            errors.append(f"dev-environment の {branch}:{path} を読めません")
            continue
        m = re.search(pattern, text)
        if not m:
            errors.append(f"dev-environment の {branch}:{path} から {name} の版を読み取れません")
            continue
        if versions[name] != m.group(1):
            errors.append(
                f"mkdocs.yml: extra.versions.{name} は {versions[name]} ですが、"
                f"dev-environment の {branch}:{path} は {m.group(1)} です"
            )
    return errors


def check_docs(docs: Path, versions: dict[str, str]) -> list[str]:
    errors = []
    for doc in sorted(docs.rglob("*.md")):
        text = doc.read_text(encoding="utf-8").replace("\r\n", "\n")
        rel = doc.relative_to(docs)
        used = MACRO.findall(text)
        if used and not FRONT_MATTER_MACROS.match(text):
            errors.append(f"{rel}: {{{{ versions.* }}}} を使っているのに、先頭に render_macros: true がありません")
        for name in used:
            if name not in versions:
                errors.append(f"{rel}: versions.{name} は mkdocs.yml の extra.versions にありません")
        values = [versions[k] for k in FULL_VERSION_KEYS if versions.get(k, "").count(".") >= 1]
        literal = re.compile(LITERAL.pattern + "".join(rf"|(?<![\d.]){re.escape(v)}(?![\d.])" for v in values))
        for line_no, line in prose_lines(text):
            for m in literal.finditer(MACRO.sub("", line)):
                errors.append(
                    f"{rel}:{line_no}: 版を直接書いています（{m.group(0)}）。"
                    f"{{{{ versions.* }}}} で書いてください（値は mkdocs.yml の extra.versions）"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add_source_args(ap)
    ap.add_argument("--docs", type=Path, default=DOCS)
    ap.add_argument("--mkdocs", type=Path, default=MKDOCS)
    args = ap.parse_args(argv)

    versions = load_versions(args.mkdocs)
    errors = check_docs(args.docs, versions)
    try:
        src, tmp = open_source(args.repo_dir, args.repo_url, args.ref)
    except ValueError as e:
        print(f"NG {e}")
        return 1
    try:
        errors += check_sources(versions, src)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)

    for e in errors:
        print(f"NG {e}")
    print(f"版 {len(versions)} 件（{versions.get('branch', '?')}）/ 問題 {len(errors)} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
