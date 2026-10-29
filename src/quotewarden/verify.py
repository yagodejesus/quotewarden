"""Checks an LLM answer against its sources: quotes, citations and numbers."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .text import content_tokens, normalize, numbers, sentences, tokens

__all__ = ["verify", "assert_grounded", "Report", "QuoteCheck", "CitationCheck", "NumberCheck", "NotGrounded"]

_QUOTE = re.compile(r'"([^"\n]{3,}?)"|“([^”\n]{3,}?)”|«([^»\n]{3,}?)»|„([^“”\n]{3,}?)[“”]')
_CITE = re.compile(r"\[\^?\s*([A-Za-z0-9_.:-]+(?:\s*[,;]\s*[A-Za-z0-9_.:-]+)*(?:\s*[–-]\s*\d+)?)\s*\]")


class NotGrounded(AssertionError):
    """Raised by :func:`assert_grounded`."""


@dataclass(frozen=True)
class QuoteCheck:
    quote: str
    status: str  # "exact" | "altered" | "missing"
    source: str | None
    similarity: float
    closest: str | None = None


@dataclass(frozen=True)
class CitationCheck:
    sentence: str
    cited: tuple[str, ...]
    status: str  # "supported" | "weak" | "unsupported" | "miscited" | "unknown_source"
    support: float
    better_source: str | None = None


@dataclass(frozen=True)
class NumberCheck:
    number: str
    found: bool
    sentence: str
    checked_in: tuple[str, ...]


@dataclass
class Report:
    quotes: list[QuoteCheck] = field(default_factory=list)
    citations: list[CitationCheck] = field(default_factory=list)
    numbers: list[NumberCheck] = field(default_factory=list)

    @property
    def problems(self) -> list[str]:
        out = []
        for q in self.quotes:
            if q.status == "missing":
                out.append(f'quote not found in any source: "{q.quote}"')
            elif q.status == "altered":
                out.append(f'quote differs from source {q.source} ({q.similarity:.0%} similar): "{q.quote}" ≠ "{q.closest}"')
        for c in self.citations:
            if c.status == "unknown_source":
                out.append(f"cites a source that wasn't provided {list(c.cited)}: {c.sentence[:90]}")
            elif c.status == "miscited":
                out.append(f"cited {list(c.cited)} but the content is in [{c.better_source}]: {c.sentence[:90]}")
            elif c.status == "unsupported":
                out.append(f"cited source(s) {list(c.cited)} don't support this ({c.support:.0%} overlap): {c.sentence[:90]}")
        for n in self.numbers:
            if not n.found:
                out.append(f"number {n.number} not found in {', '.join(n.checked_in) or 'any source'}: {n.sentence[:90]}")
        return out

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def score(self) -> float:
        """Share of checks that passed (1.0 when there was nothing to check)."""
        checks = [q.status == "exact" for q in self.quotes] + [c.status in ("supported", "weak") for c in self.citations]
        checks += [n.found for n in self.numbers]
        return round(sum(checks) / len(checks), 3) if checks else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "problems": self.problems,
            "quotes": [asdict(q) for q in self.quotes],
            "citations": [asdict(c) for c in self.citations],
            "numbers": [asdict(n) for n in self.numbers],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def __str__(self) -> str:
        head = (
            f"{'✓ grounded' if self.ok else '✗ not grounded'} — score {self.score:.0%} "
            f"({len(self.quotes)} quotes, {len(self.citations)} cited sentences, {len(self.numbers)} numbers checked)"
        )
        return "\n".join([head, *[f"  • {p}" for p in self.problems]])

    def to_markdown(self) -> str:
        lines = [f"**{'✅ Grounded' if self.ok else '❌ Not grounded'}** — score {self.score:.0%}"]
        lines += [f"- {p}" for p in self.problems]
        return "\n".join(lines)


class _Source:
    def __init__(self, sid: str, text: str) -> None:
        self.id = sid
        self.text = text
        self.norm = normalize(text)
        self.toks = self.norm.split()
        sents = [content_tokens(s) for _, _, s in sentences(text)]
        self.windows = [set(s) for s in sents] + [set(a) | set(b) for a, b in zip(sents, sents[1:])]
        self.values: set[float] = set().union(*(v for *_, v in numbers(text))) if text else set()

    def coverage(self, ctoks: list[str]) -> float:
        if not ctoks:
            return 1.0
        want = set(ctoks)
        return max((len(want & w) / len(want) for w in self.windows), default=0.0)


def _as_sources(sources: Mapping[str, str] | Sequence[str]) -> dict[str, _Source]:
    items = sources.items() if isinstance(sources, Mapping) else ((str(i + 1), s) for i, s in enumerate(sources))
    return {str(k): _Source(str(k), v) for k, v in items}


def _check_quote(q: str, srcs: dict[str, _Source]) -> QuoteCheck:
    nq = normalize(q)
    for s in srcs.values():
        if nq and f" {nq} " in f" {s.norm} ":
            return QuoteCheck(q, "exact", s.id, 1.0)
    qt = nq.split()
    best = (0.0, None, None)
    for s in srcs.values():
        anchors = {i for i, t in enumerate(s.toks) if t in set(qt)}
        starts = sorted({max(0, a - k) for a in anchors for k in range(min(len(qt), 6))})[:4000]
        for st in starts:
            window = s.toks[st : st + len(qt)]
            r = SequenceMatcher(None, qt, window, autojunk=False).ratio()
            if r > best[0]:
                best = (r, s.id, " ".join(window))
    sim, sid, closest = best
    status = "altered" if sim >= 0.75 else "missing"
    return QuoteCheck(q, status, sid if status == "altered" else None, round(sim, 3), closest if status == "altered" else None)


def _expand(ids_raw: str) -> list[str]:
    out = []
    for part in re.split(r"[,;]", ids_raw):
        part = part.strip()
        m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if m and int(m.group(2)) - int(m.group(1)) < 50:
            out += [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif part:
            out.append(part)
    return out


def verify(
    answer: str,
    sources: Mapping[str, str] | Sequence[str],
    *,
    threshold: float = 0.6,
    weak: float = 0.35,
    min_quote_words: int = 4,
    check_numbers: bool = True,
    ignore_small_numbers: bool = True,
) -> Report:
    """Check ``answer`` against ``sources`` (a dict ``{id: text}`` or a list, cited as ``[1]``, ``[2]``…).

    - **quotes** in "…", “…” or «…» with at least ``min_quote_words`` words must appear in a source
      (``altered`` = a near match with words changed; ``missing`` = not found);
    - **citations** like ``[1]``, ``[2, 3]``, ``[1-3]`` or ``[^1]``: the sentence's content words must be covered by
      a passage of the cited source(s) (``threshold``), and a better uncited source is reported as ``miscited``;
    - **numbers** in each sentence must appear in the cited sources (or in any source when uncited).
    """
    srcs = _as_sources(sources)
    report = Report()
    for m in _QUOTE.finditer(answer):
        q = next(g for g in m.groups() if g)
        if len(tokens(q)) >= min_quote_words:
            report.quotes.append(_check_quote(q, srcs))
    for _, _, sent in sentences(answer):
        cites = [c for m in _CITE.finditer(sent) for c in _expand(m.group(1))]
        cites = [c for c in cites if c in srcs or c.isdigit()]
        body = _CITE.sub(" ", sent)
        if cites:
            unknown = [c for c in cites if c not in srcs]
            ctoks = [t for t in content_tokens(body)]
            if unknown:
                report.citations.append(CitationCheck(sent, tuple(cites), "unknown_source", 0.0))
            else:
                cov = max(srcs[c].coverage(ctoks) for c in cites)
                best_other = max(((s.coverage(ctoks), s.id) for s in srcs.values() if s.id not in cites), default=(0.0, None))
                if cov >= threshold:
                    status, better = "supported", None
                elif best_other[0] >= threshold:
                    status, better = "miscited", best_other[1]
                else:
                    status, better = ("weak" if cov >= weak else "unsupported"), None
                report.citations.append(CitationCheck(sent, tuple(cites), status, round(cov, 3), better))
        if check_numbers:
            pool = [srcs[c] for c in cites if c in srcs] or list(srcs.values())
            values = set().union(*(s.values for s in pool)) if pool else set()
            for _, _, raw, vals in numbers(body):
                if ignore_small_numbers and all(v == int(v) and abs(v) < 10 for v in vals):
                    continue
                report.numbers.append(NumberCheck(raw, bool(vals & values), sent, tuple(s.id for s in pool)))
    return report


def assert_grounded(answer: str, sources: Mapping[str, str] | Sequence[str], min_score: float = 1.0, **kw: Any) -> Report:
    """Raise :class:`NotGrounded` (an ``AssertionError``) when problems are found or the score is below ``min_score``."""
    r = verify(answer, sources, **kw)
    if r.score < min_score or (min_score >= 1.0 and not r.ok):
        raise NotGrounded("\n" + str(r))
    return r
