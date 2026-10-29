"""quotewarden — catch hallucinated quotes, wrong citations and invented numbers in LLM answers, deterministically."""

__version__ = "0.1.0"

from .verify import CitationCheck, NotGrounded, NumberCheck, QuoteCheck, Report, assert_grounded, verify

__all__ = ["__version__", "CitationCheck", "NotGrounded", "NumberCheck", "QuoteCheck", "Report", "assert_grounded", "verify"]
