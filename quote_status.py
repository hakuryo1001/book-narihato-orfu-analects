#!/usr/bin/env python3
"""
Scan chapters/quotes/*.tex and write a progress checklist.

A quote is marked done when its file contains the word DONE (any case).

Run:
  python3 quote_status.py
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_source_question(text: str) -> str:
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == "% Source question:":
            start = i + 1
            break
    if start is None:
        return ""

    question_lines: list[str] = []
    for line in lines[start:]:
        if not line.startswith("% "):
            break
        content = line[2:].strip()
        if content.startswith("="):
            break
        if content:
            question_lines.append(content)
    return " ".join(question_lines)


def extract_chapter_toc(text: str) -> str:
    match = re.search(r"\\chapter\[([^\]]*)\]", text)
    return match.group(1).strip() if match else ""


def preview(text: str, max_len: int = 72) -> str:
    flat = " ".join(text.split())
    if len(flat) <= max_len:
        return flat
    return flat[: max_len - 1].rstrip() + "…"


def is_done(text: str) -> bool:
    return bool(re.search(r"\bDONE\b", text, re.IGNORECASE))


def scan_quotes(quotes_dir: Path) -> list[tuple[str, bool, str]]:
    rows: list[tuple[str, bool, str]] = []
    for path in sorted(quotes_dir.glob("*.tex")):
        text = path.read_text(encoding="utf-8")
        label = extract_source_question(text) or extract_chapter_toc(text) or path.stem
        rows.append((path.name, is_done(text), preview(label)))
    return rows


def format_row(name: str, label: str) -> str:
    num = name.removesuffix(".tex")
    return f"- **{num}** — {label}"


def render_report(rows: list[tuple[str, bool, str]]) -> str:
    done_rows = [(n, l) for n, finished, l in rows if finished]
    todo_rows = [(n, l) for n, finished, l in rows if not finished]
    done = len(done_rows)
    total = len(rows)
    pct = (100 * done / total) if total else 0
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Quote progress",
        "",
        f"Generated: {now}",
        "",
        f"**{done} / {total} done ({pct:.0f}%)**",
        "",
        "Mark a quote finished by putting `DONE` anywhere in its `.tex` file",
        "(for example `% Status: DONE` in the header).",
        "",
        "Regenerate this report:",
        "",
        "```bash",
        "python3 quote_status.py",
        "```",
        "",
        f"## Done ({done})",
        "",
    ]

    if done_rows:
        lines.extend(format_row(name, label) for name, label in done_rows)
    else:
        lines.append("_None yet._")

    lines.extend(["", f"## Not done ({len(todo_rows)})", ""])

    if todo_rows:
        lines.extend(format_row(name, label) for name, label in todo_rows)
    else:
        lines.append("_All complete._")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Write quote progress checklist from chapters/quotes/.")
    ap.add_argument(
        "--quotes-dir",
        type=Path,
        default=root / "chapters" / "quotes",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=root / "chapters" / "quotes" / "STATUS.md",
    )
    args = ap.parse_args()

    if not args.quotes_dir.is_dir():
        print(f"Quotes directory not found: {args.quotes_dir}", file=sys.stderr)
        return 1

    rows = scan_quotes(args.quotes_dir)
    if not rows:
        print(f"No .tex files in {args.quotes_dir}", file=sys.stderr)
        return 1

    report = render_report(rows)
    args.out.write_text(report, encoding="utf-8")

    done = sum(1 for _, finished, _ in rows if finished)
    todo = len(rows) - done
    print(f"Wrote {args.out} — {done} done, {todo} not done", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
