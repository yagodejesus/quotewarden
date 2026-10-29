"""Command line: ``quotewarden answer.txt --source 1=report.txt --source 2=faq.md``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .verify import verify


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="quotewarden", description="Check quotes, citations and numbers in an LLM answer against its sources.")
    p.add_argument("answer", help="answer text file ('-' for stdin)")
    p.add_argument("--source", action="append", default=[], metavar="ID=FILE", help="a source and its citation id (repeatable)")
    p.add_argument("--sources", help="a directory: each file is a source, cited by its name without extension")
    p.add_argument("--threshold", type=float, default=0.6)
    p.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = p.parse_args(argv)
    answer = sys.stdin.read() if a.answer == "-" else Path(a.answer).read_text(encoding="utf-8")
    sources: dict[str, str] = {}
    if a.sources:
        for f in sorted(Path(a.sources).iterdir()):
            if f.is_file():
                sources[f.stem] = f.read_text(encoding="utf-8")
    for item in a.source:
        sid, _, path = item.partition("=")
        sources[sid] = Path(path).read_text(encoding="utf-8")
    if not sources:
        p.error("give at least one --source or --sources")
    r = verify(answer, sources, threshold=a.threshold)
    print(r.to_json() if a.format == "json" else r.to_markdown() if a.format == "markdown" else r)
    return 0 if r.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
