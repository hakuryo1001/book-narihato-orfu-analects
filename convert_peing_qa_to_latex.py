#!/usr/bin/env python3
"""
Generate Q&A LaTeX from raw/peing_qa_traditional.json.

Default (split) mode writes one file per entry under chapters/quotes/ and a
manifest chapters/1-quotes.tex that \\input{}s them in order. Edit each quote
file individually; track progress in the comment header at the top.

Regenerate split files (skip files that already exist):
  python3 convert_peing_qa_to_latex.py

Overwrite all split files from JSON:
  python3 convert_peing_qa_to_latex.py --force

Merge split files back into a single chapters/1-quotes.tex:
  python3 convert_peing_qa_to_latex.py --combine

After bulk-editing the combined file, split back into chapters/quotes/:
  python3 convert_peing_qa_to_latex.py --split-from-combined
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


QUOTE_HEADER = """% =============================================================================
% {num:03d} / {total:03d}
% Status: raw
% =============================================================================
% Notes:
%
% Source question:
% {question_source}
% =============================================================================

"""


def escape_latex(text: str) -> str:
    """Escape characters that break LaTeX when pasted verbatim."""
    if not text:
        return ""
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("^", r"\textasciicircum{}"),
        ("_", r"\_"),
        ("~", r"\textasciitilde{}"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def text_to_latex_body(text: str) -> str:
    """Turn plain text (possibly multi-paragraph) into LaTeX body fragments."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return ""
    return "\n\n".join(escape_latex(p) for p in paragraphs)


def flatten_question(question: str) -> str:
    """Single-line question for the TOC."""
    return " ".join(question.split())


def format_question_heading(question: str) -> str:
    """Multi-line question for the chapter heading on the page."""
    lines = [line.strip() for line in question.split("\n") if line.strip()]
    if not lines:
        return ""
    if len(lines) == 1:
        return escape_latex(lines[0])
    return r" \\[0.35em] ".join(escape_latex(line) for line in lines)


def load_pairs(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = list(data.values())
    items.sort(key=lambda item: item.get("answer_created_at", ""))
    pairs: list[tuple[str, str]] = []
    for item in items:
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        if not question and not answer:
            continue
        pairs.append((question, answer))
    return pairs


def render_entry(question: str, answer: str) -> str:
    toc = escape_latex(flatten_question(question))
    heading = format_question_heading(question)
    body = text_to_latex_body(answer)
    return f"\\chapter[{toc}]{{{heading}}}\n\\qaanswer{{\n{body}\n}}\n"


def render_quote_file(num: int, total: int, question: str, answer: str) -> str:
    header = QUOTE_HEADER.format(
        num=num,
        total=total,
        question_source=question.replace("\n", "\n% "),
    )
    return header + render_entry(question, answer) + "\n"


def emit_manifest(quote_names: list[str], out: Path) -> None:
    lines = [
        "% Manifest for Q&A chapters — one \\input per entry in chapters/quotes/.",
        "% Regenerate: python3 convert_peing_qa_to_latex.py",
        "% Merge back: python3 convert_peing_qa_to_latex.py --combine",
        "",
        r"\chapter*{問答語錄}",
        r"\addcontentsline{toc}{chapter}{問答語錄}",
        "",
    ]
    for name in quote_names:
        lines.append(f"\\input{{chapters/quotes/{name}}}")
        lines.append("")
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def split_pairs(
    pairs: list[tuple[str, str]],
    quotes_dir: Path,
    manifest: Path,
    force: bool,
) -> tuple[int, int]:
    quotes_dir.mkdir(parents=True, exist_ok=True)
    quote_names: list[str] = []
    written = 0
    skipped = 0
    total = len(pairs)

    for num, (question, answer) in enumerate(pairs, start=1):
        name = f"{num:03d}.tex"
        quote_names.append(name)
        path = quotes_dir / name
        if path.exists() and not force:
            skipped += 1
            continue
        path.write_text(render_quote_file(num, total, question, answer), encoding="utf-8")
        written += 1

    emit_manifest(quote_names, manifest)
    return written, skipped


def strip_progress_header(text: str) -> str:
    """Remove the editable progress header when combining."""
    if text.startswith("% ====="):
        end = text.find("% =============================================================================\n\n", 1)
        if end != -1:
            return text[end + len("% =============================================================================\n\n") :]
    return text


def quote_files(quotes_dir: Path) -> list[Path]:
    return sorted(
        p for p in quotes_dir.glob("*.tex") if re.fullmatch(r"\d{3}\.tex", p.name)
    )


def parse_combined_entries(text: str) -> list[str]:
    """Split a combined 1-quotes.tex into \\chapter[...]...\\qaanswer{...} blocks."""
    chunks = re.split(r"(?=\\chapter\[)", text)
    entries: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk.startswith("\\chapter["):
            entries.append(chunk)
    return entries


def latex_toc_to_source_question(toc: str) -> str:
    """Rough plain-text question for progress headers from TOC line."""
    q = toc.replace(r" \\[0.35em] ", "\n")
    q = re.sub(r"\\textasciitilde\{\}", "~", q)
    q = re.sub(r"\\textasciicircum\{\}", "^", q)
    q = re.sub(r"\\&", "&", q)
    return q


def split_from_combined(combined: Path, quotes_dir: Path, manifest: Path) -> int:
    text = combined.read_text(encoding="utf-8")
    entries = parse_combined_entries(text)
    if not entries:
        print(f"No \\chapter[...] entries found in {combined}", file=sys.stderr)
        return 1

    quotes_dir.mkdir(parents=True, exist_ok=True)
    quote_names: list[str] = []
    total = len(entries)

    for num, entry in enumerate(entries, start=1):
        toc_match = re.match(r"\\chapter\[([^\]]*)\]", entry)
        if not toc_match:
            print(f"Could not parse entry {num:03d}", file=sys.stderr)
            return 1
        toc = toc_match.group(1)
        source_question = latex_toc_to_source_question(toc)

        name = f"{num:03d}.tex"
        quote_names.append(name)
        header = QUOTE_HEADER.format(
            num=num,
            total=total,
            question_source=source_question.replace("\n", "\n% "),
        )
        (quotes_dir / name).write_text(header + entry.rstrip() + "\n", encoding="utf-8")

    emit_manifest(quote_names, manifest)
    print(
        f"Split {total} entries from {combined} into {quotes_dir}; manifest: {manifest}",
        file=sys.stderr,
    )
    return 0


def combine_quotes(quotes_dir: Path, manifest: Path) -> int:
    files = quote_files(quotes_dir)
    if not files:
        print(f"No quote files found in {quotes_dir}", file=sys.stderr)
        return 1

    blocks = [
        "% Combined from chapters/quotes/*.tex",
        "% Merge command: python3 convert_peing_qa_to_latex.py --combine",
        "",
        r"\chapter*{問答語錄}",
        r"\addcontentsline{toc}{chapter}{問答語錄}",
        "",
    ]
    for path in files:
        body = strip_progress_header(path.read_text(encoding="utf-8")).strip()
        blocks.append(body)
        blocks.append("")

    manifest.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    print(f"Combined {len(files)} quote files into {manifest}", file=sys.stderr)
    return 0


def main() -> int:
    root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Generate or combine Peing Q&A LaTeX chapters.")
    ap.add_argument(
        "--json",
        type=Path,
        default=root / "raw" / "peing_qa_traditional.json",
    )
    ap.add_argument(
        "--quotes-dir",
        type=Path,
        default=root / "chapters" / "quotes",
    )
    ap.add_argument(
        "--manifest",
        type=Path,
        default=root / "chapters" / "1-quotes.tex",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing split files (progress comments in headers will be lost).",
    )
    ap.add_argument(
        "--combine",
        action="store_true",
        help="Merge chapters/quotes/*.tex back into chapters/1-quotes.tex.",
    )
    ap.add_argument(
        "--split-from-combined",
        action="store_true",
        help="Split chapters/1-quotes.tex back into chapters/quotes/*.tex.",
    )
    ap.add_argument(
        "--combined",
        type=Path,
        default=None,
        help="Combined file for --split-from-combined (default: chapters/1-quotes.tex).",
    )
    args = ap.parse_args()

    if args.combine:
        return combine_quotes(args.quotes_dir, args.manifest)

    if args.split_from_combined:
        combined = args.combined or args.manifest
        return split_from_combined(combined, args.quotes_dir, args.manifest)

    pairs = load_pairs(args.json)
    written, skipped = split_pairs(pairs, args.quotes_dir, args.manifest, args.force)
    print(
        f"Split {len(pairs)} Q&A pairs into {args.quotes_dir} "
        f"({written} written, {skipped} skipped); manifest: {args.manifest}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
