import pytest

from quotewarden import NotGrounded, assert_grounded, verify
from quotewarden.cli import main

SOURCES = {
    "1": "Acme's revenue grew 12% in the third quarter, reaching $1,234.5 million. "
    'The CEO said "we are investing heavily in renewable energy" during the call.',
    "2": "The company opened 14 new stores in Brazil. Employee headcount reached 8,500 by September.",
    "3": "A receita da Acme no Brasil foi de R$ 2.340,75 milhões, segundo o relatório anual.",
}


def test_fully_grounded_answer():
    answer = (
        "Revenue grew 12% in the third quarter, reaching $1,234.5 million [1]. "
        'The company opened 14 new stores in Brazil [2]. The CEO said "we are investing heavily in renewable energy".'
    )
    r = verify(answer, SOURCES)
    assert r.ok and r.score == 1.0
    assert r.quotes[0].status == "exact" and r.quotes[0].source == "1"
    assert all(c.status == "supported" for c in r.citations)


def test_fabricated_and_altered_quotes():
    r = verify('The CEO said "we are investing massively in renewable energy". He added "profits will triple next year".', SOURCES)
    statuses = [q.status for q in r.quotes]
    assert statuses == ["altered", "missing"]
    assert r.quotes[0].closest == "we are investing heavily in renewable energy"
    assert not r.ok and any("not found" in p for p in r.problems)


def test_miscited_unsupported_and_unknown_sources():
    r = verify("The company opened 14 new stores in Brazil [1]. Acme was founded on the Moon in 1802 [2]. Profits doubled [7].", SOURCES)
    by = {c.sentence.split()[1]: c for c in r.citations}
    assert by["company"].status == "miscited" and by["company"].better_source == "2"
    assert by["was"].status == "unsupported"
    assert by["doubled"].status == "unknown_source"


def test_invented_numbers_are_flagged():
    r = verify("Revenue grew 15% in the third quarter [1]. Headcount reached 8,500 [2].", SOURCES)
    found = {n.number: n.found for n in r.numbers}
    assert found == {"15": False, "8,500": True}


def test_number_formats_and_portuguese():
    r = verify("A receita no Brasil foi de 2,340.75 milhões [3]. Revenue reached 1.234,5 million [1].", SOURCES)
    assert all(n.found for n in r.numbers) and r.ok
    curly = verify("Segundo o relatório, “a receita da Acme no Brasil foi” alta.", SOURCES)
    assert curly.quotes[0].status == "exact"


def test_citation_formats():
    r = verify(
        "Revenue grew 12% in the third quarter [1, 2]. Stores in Brazil grew by 14 new stores [^2]. "
        "Headcount reached 8,500 by September [1-2].",
        SOURCES,
    )
    assert [c.cited for c in r.citations] == [("1", "2"), ("2",), ("1", "2")]
    assert all(c.status == "supported" for c in r.citations)


def test_list_sources_and_small_numbers():
    r = verify("There are 3 key points. Revenue grew 12% [1].", list(SOURCES.values()))
    assert [n.number for n in r.numbers] == ["12"] and r.ok


def test_assert_grounded_and_outputs():
    with pytest.raises(NotGrounded, match="not grounded"):
        assert_grounded("Revenue grew 99% [1].", SOURCES)
    r = assert_grounded("Revenue grew 12% [1].", SOURCES)
    assert r.to_dict()["ok"] and "Grounded" in r.to_markdown() and "score 100%" in str(r)


def test_cli(tmp_path, capsys):
    d = tmp_path / "src"
    d.mkdir()
    (d / "1.txt").write_text(SOURCES["1"])
    ans = tmp_path / "a.txt"
    ans.write_text("Revenue grew 12% [1].")
    assert main([str(ans), "--sources", str(d)]) == 0
    ans.write_text('Revenue grew 20% [1]. The CEO said "we will buy the Moon tomorrow".')
    assert main([str(ans), "--source", f"1={d / '1.txt'}", "--format", "json"]) == 1
    assert '"ok": false' in capsys.readouterr().out
