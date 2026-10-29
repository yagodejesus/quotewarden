<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo.svg" alt="quotewarden" width="440">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/yagodejesus/quotewarden/actions/workflows/ci.yml"><img src="https://github.com/yagodejesus/quotewarden/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/quotewarden/"><img src="https://img.shields.io/pypi/v/quotewarden.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/quotewarden/"><img src="https://img.shields.io/pypi/pyversions/quotewarden.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT"></a>
</p>

**Catch hallucinated quotes, wrong citations and invented numbers in LLM answers** — by checking them against the source documents. Deterministic, fast, no API calls, no dependencies.

> 🇧🇷 *Pega citações inventadas, fontes erradas e números que não existem nas respostas de LLMs e sistemas RAG, conferindo tudo contra os documentos de origem — sem chamar nenhuma API.*

Lawyers have been sanctioned for filing briefs with quotes that don't exist. Support bots promise refunds the policy never mentions. RAG systems cite `[2]` for a fact that's in `[3]` — or nowhere. The worst hallucinations are the ones that *look* grounded. `quotewarden` checks the three things readers trust most:

```python
from quotewarden import verify

report = verify(answer, sources={"1": annual_report, "2": press_release})
print(report)
```

```text
✗ not grounded — score 57% (2 quotes, 3 cited sentences, 2 numbers checked)
  • quote differs from source 1 (88% similar): "we are investing massively in renewable energy" ≠ "we are investing heavily in renewable energy"
  • quote not found in any source: "profits will triple next year"
  • cited ['1'] but the content is in [2]: The company opened 14 new stores in Brazil [1].
  • number 15 not found in 1: Revenue grew 15% in the third quarter [1].
```

## What it checks

| Check | How | Statuses |
|---|---|---|
| **Quotes** in `"…"`, `“…”`, `«…»`, `„…“` (4+ words) | exact match after normalizing case, accents, punctuation and curly quotes; otherwise the closest passage | `exact`, `altered` (words changed — often the worst kind), `missing` |
| **Citations** `[1]`, `[2, 3]`, `[1-3]`, `[^1]` | the sentence's content words must be covered by one passage (1–2 sentences) of the cited source | `supported`, `weak`, `unsupported`, `miscited` (another source matches — and which), `unknown_source` |
| **Numbers** | every number in a sentence must appear in the cited sources (or any source); `1,234.5` and `1.234,5` are matched both ways | found / not found |

Works with English and Portuguese text (stopwords, accents, decimal commas).

## Use it where answers are produced

```python
from quotewarden import assert_grounded, verify

# in production: block or flag answers before users see them
r = verify(answer, retrieved_chunks)          # sources as a list → cited as [1], [2], ...
if not r.ok:
    answer = regenerate_or_add_disclaimer(answer, r.problems)

# in your eval suite / pytest
def test_refund_answer_is_grounded():
    assert_grounded(bot.ask("Can I get a refund after 40 days?"), policy_docs)
```

```bash
quotewarden answer.txt --source 1=report.txt --source 2=faq.md
quotewarden answer.txt --sources retrieved/ --format json    # files cited by name, exit 1 if not grounded
```

`report.score`, `report.problems`, `report.to_dict()` and `report.to_markdown()` are there for dashboards and PR comments.

## What it is — and isn't

`quotewarden` is a precise, cheap **first line of defense**: exact quotes, citation targets and numbers are verifiable without a model, so it checks them deterministically on every answer. It does not judge paraphrased meaning — a sentence that reuses the source's words but reverses its meaning can pass the citation check. Combine it with an LLM-as-judge or an NLI model for semantics, and use `quotewarden` to make those judges' job (and cost) smaller.

## Install

```bash
pip install quotewarden
```

## Development

```bash
git clone https://github.com/yagodejesus/quotewarden && cd quotewarden
pip install -e ".[dev]"
pytest && ruff check .
```

## License

MIT © Yago de Jesus Martins
