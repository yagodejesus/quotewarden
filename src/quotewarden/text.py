"""Normalization, tokenization, sentences and numbers (English and Portuguese aware)."""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize", "tokens", "content_tokens", "sentences", "numbers", "STOPWORDS"]

STOPWORDS = frozenset(
    """a an the and or but if of to in on at by for with from as is are was were be been being it its this that these those
    there their they them he she his her we our you your i me my not no do does did has have had will would can could should
    may might than then so such also into about over after before between which who whom whose what when where why how all any
    each more most other some only very just per via o os as um uma uns umas de do da dos das em no na nos nas por pelo pela
    pelos pelas para com sem sob sobre e ou mas se que é são foi foram ser estar está estão esse essa isso este esta isto
    aquele aquela seu sua seus suas ao aos à às como mais menos já não também entre até""".split()
)
_QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "–": "-", "—": "-"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.translate(_QUOTES))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).casefold()
    return " ".join(re.findall(r"\w+", t))


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


def sentences(text: str) -> list[tuple[int, int, str]]:
    """``(start, end, sentence)`` spans, splitting on . ! ? and line breaks (keeps decimals like 3.5 together)."""
    out = []
    start = 0
    for m in re.finditer(r"(?<=[.!?])\s+(?=[\"“«(\[A-ZÀ-Ý0-9])|\n+", text):
        seg = text[start : m.start()]
        if seg.strip():
            out.append((start, m.start(), seg.strip()))
        start = m.end()
    if text[start:].strip():
        out.append((start, len(text), text[start:].strip()))
    return out


_NUM = re.compile(r"(?<![\w])\d[\d.,]*\d(?![\w])|(?<![\w.,])\d(?![\w.,]?\d)")


def _values(raw: str) -> set[float]:
    """All plausible readings of ``1,234.5`` / ``1.234,5`` / ``1,234`` / ``3.5``."""
    vals: set[float] = set()
    s = raw.strip(".,")
    candidates = {s.replace(",", ""), s.replace(".", "").replace(",", "."), s.replace(" ", "")}
    if s.count(",") == 1 and "." not in s:
        candidates.add(s.replace(",", "."))
    for c in candidates:
        try:
            vals.add(round(float(c), 6))
        except ValueError:
            pass
    return vals


def numbers(text: str) -> list[tuple[int, int, str, set[float]]]:
    """Numbers in ``text`` with every plausible value (decimal comma or point)."""
    return [(m.start(), m.end(), m.group(), _values(m.group())) for m in _NUM.finditer(text)]
