#!/usr/bin/env python3
"""Format ruby-annotated script text into movie-script environments.

Usage:
  python3 format_ruby_movie.py \
    /Users/hongjan/Documents/book-lawyer-lawyer/wip/1.add-ruby.tex \
    /Users/hongjan/Documents/book-lawyer-lawyer/wip/2.run-python-script.tex
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


RUBY_RE = re.compile(r"\\ruby\{([^}]*)\}\{[^}]*\}")
SKIP_RE = re.compile(
    r"^(周星馳-|\s*由 Admin|\s*Admin 在|\s*Admin$|\s*文章數|\s*注冊日期|\s*LIKEDISLIKE|\s*回復：)"
)
STAGE_NAMES = {"外景", "內景", "場景"}


def plain_text(s: str) -> str:
    return RUBY_RE.sub(r"\1", s)


def merge_parenthetical_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    paren_buf: str | None = None
    for line in lines:
        raw = line.rstrip("\n")
        stripped = raw.strip()
        if paren_buf is not None:
            paren_buf += stripped
            if paren_buf.endswith("）") or paren_buf.endswith(")"):
                merged.append(paren_buf)
                paren_buf = None
            continue
        if (stripped.startswith("（") or stripped.startswith("(")) and not (
            stripped.endswith("）") or stripped.endswith(")")
        ):
            paren_buf = stripped
            continue
        merged.append(raw)

    if paren_buf is not None:
        merged.append(paren_buf)

    return merged


def format_script(text: str) -> str:
    lines = text.splitlines()
    merged = merge_parenthetical_lines(lines)

    blocks: list[dict[str, object]] = []
    last_dialogue: dict[str, object] | None = None
    prev_blank = True

    for raw in merged:
        if raw.strip() == "":
            prev_blank = True
            continue

        s = raw.strip()
        plain = plain_text(s)
        if SKIP_RE.search(plain) or "作了第" in plain:
            continue

        if "：" in s:
            name_raw, text_raw = s.split("：", 1)
            name_raw = name_raw.strip()
            text_raw = text_raw.strip()
            name_plain = plain_text(name_raw)

            if name_plain in STAGE_NAMES:
                stage_content = f"{name_raw}：{text_raw}".strip()
                blocks.append({"type": "stage", "text": stage_content})
                last_dialogue = None
                prev_blank = False
                continue

            stage_raw = None
            if "（" in name_raw and name_raw.endswith("）"):
                idx = name_raw.rfind("（")
                stage_raw = name_raw[idx + 1 : -1].strip()
                name_raw = name_raw[:idx].strip()
            elif "(" in name_raw and name_raw.endswith(")"):
                idx = name_raw.rfind("(")
                stage_raw = name_raw[idx + 1 : -1].strip()
                name_raw = name_raw[:idx].strip()

            block = {
                "type": "dialogue",
                "char": name_raw,
                "stage": stage_raw,
                "lines": [text_raw],
            }
            blocks.append(block)
            last_dialogue = block
            prev_blank = False
            continue

        # Non-dialogue line
        if (s.startswith("（") or s.startswith("(")) or (
            s.endswith("）") or s.endswith(")")
        ):
            stage_content = s
            if (stage_content.startswith("（") or stage_content.startswith("(")) and (
                stage_content.endswith("）") or stage_content.endswith(")")
            ):
                stage_content = stage_content[1:-1].strip()
            elif stage_content.startswith("（") or stage_content.startswith("("):
                stage_content = stage_content[1:].strip()
            elif stage_content.endswith("）") or stage_content.endswith(")"):
                stage_content = stage_content[:-1].strip()
            blocks.append({"type": "stage", "text": stage_content})
            last_dialogue = None
            prev_blank = False
            continue

        if last_dialogue is not None and not prev_blank:
            last_dialogue["lines"].append(s)
        else:
            blocks.append({"type": "stage", "text": s})
            last_dialogue = None
        prev_blank = False

    out_lines: list[str] = []
    for block in blocks:
        if block["type"] == "stage":
            out_lines.append(f"\\stage{{{block['text']}}}")
            out_lines.append("")
        else:
            out_lines.append(f"\\charname{{{block['char']}}}")
            stage = block.get("stage")
            if stage:
                out_lines.append(f"\\stage{{{stage}}}")
            out_lines.append("\\begin{dialogue}")
            out_lines.extend(block["lines"])  # type: ignore[arg-type]
            out_lines.append("\\end{dialogue}")
            out_lines.append("")

    return "\n".join(out_lines).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: format_ruby_movie.py INPUT.tex OUTPUT.tex", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    text = src.read_text()
    dst.write_text(format_script(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
