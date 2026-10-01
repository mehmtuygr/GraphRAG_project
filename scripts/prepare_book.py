from __future__ import annotations
import argparse
import re
from pathlib import Path
import fitz

HEADER_FOOTER_PATTERNS = [
    re.compile(r"^Draft: please send errata to .*?$", re.I),
    re.compile(r"^This work is subject to a Creative Commons .*?$", re.I),
]


def clean_page(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        if any(p.search(line) for p in HEADER_FOOTER_PATTERNS):
            continue
        lines.append(line)
    # Rejoin hyphenated line breaks conservatively only when a word ends in '-'.
    out = []
    for line in lines:
        if out and out[-1].endswith("-") and line and line[0].islower():
            out[-1] = out[-1][:-1] + line
        else:
            out.append(line)
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract the UDL PDF into page-aware GraphRAG text inputs.")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=Path("input"))
    ap.add_argument("--pages-per-file", type=int, default=5)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    # Remove only files this script created.
    for old in args.out.glob("udl_pages_*.txt"):
        old.unlink()

    doc = fitz.open(args.pdf)
    total = len(doc)
    bundle = []
    start_page = 1
    written = 0

    for idx, page in enumerate(doc, start=1):
        text = clean_page(page.get_text("text"))
        bundle.append(f"[SOURCE_PAGE={idx}]\n{text}\n")
        if len(bundle) == args.pages_per_file or idx == total:
            end_page = idx
            target = args.out / f"udl_pages_{start_page:03d}_{end_page:03d}.txt"
            target.write_text("\n\n".join(bundle), encoding="utf-8")
            written += 1
            bundle = []
            start_page = idx + 1

    print(f"OK: {total} PDF pages -> {written} text files in {args.out.resolve()}")
    print("Each page keeps a [SOURCE_PAGE=N] marker for traceability.")


if __name__ == "__main__":
    main()
