"""教材の Markdown の読み取り（コードブロック・引用元コメント・本文の行）."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .source import ROOT

DOCS = ROOT / "docs"

MARKER = re.compile(
    r"^\s*<!--\s*src:\s*(?P<path>[^\s#@]+)(?:#(?P<lines>[L0-9,\-]+))?(?:\s+@(?P<ref>[\w./-]+))?\s*-->\s*$"
)
MARKER_LOOSE = re.compile(r"^\s*<!--\s*src:")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
TITLE = re.compile(r'title="(?P<title>[^"]*)"')
TITLE_LINES = re.compile(r"(\d+)(?:〜(\d+))? 行目")
LINENUMS = re.compile(r'linenums="(?P<n>\d+)"')
RANGE = re.compile(r"^L(?P<a>\d+)(?:-L?(?P<b>\d+))?$")


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
    lines = path.read_text(encoding="utf-8-sig").split("\n")
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


def prose_lines(path: Path) -> list[tuple[int, str]]:
    """コードブロックの外の行（行番号は 1 始まり）."""
    out = []
    fence: str | None = None
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").split("\n"), 1):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group("fence")
                continue
            out.append((i, line))
        elif m and m.group("fence").startswith(fence[0] * len(fence)) and not m.group("info").strip():
            fence = None
    return out


EXERCISE_NOTE = '!!! note "読むコードは `exercise-base` ブランチ"'


def default_ref(doc: Path) -> str:
    """ページの既定のブランチ. 冒頭に exercise-base の注記がある章と、30 実ソース読解の解答は exercise-base."""
    if EXERCISE_NOTE in doc.read_text(encoding="utf-8-sig"):
        return "exercise-base"
    if doc.parent.name == "answers" and doc.parent.parent.name == "30-reading":
        return "exercise-base"
    return "main"
