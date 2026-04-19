"""CLI behaviour tests — missing-format surfacing and exit codes."""

from __future__ import annotations

from typer.testing import CliRunner

from scholar_cite import cli
from scholar_cite.models import CitationSet, Paper

runner = CliRunner()


def _paper_with_partial_results() -> Paper:
    """Paper with MLA present, everything else missing with error notes."""
    p = Paper(cluster_id="c1", title="Test Paper", authors=["Doe, J"], year=2024)
    p.citations = CitationSet(mla="Doe, J. Test Paper. 2024.")
    p.citation_errors = {
        "apa": "HTTPError: 403 Forbidden",
        "chicago": "not present in cite popup",
        "harvard": "not present in cite popup",
        "vancouver": "not present in cite popup",
        "bibtex": "RuntimeError: download aborted",
        "endnote": "RuntimeError: download aborted",
        "refman": "RuntimeError: download aborted",
        "refworks": "RuntimeError: download aborted",
    }
    return p


def test_render_plain_shows_missing_markers():
    """Review finding #2: a --format all request must visibly flag missing
    formats, not silently drop them."""
    text = cli._render_plain([_paper_with_partial_results()], formats=list(cli.ALL_FORMATS))

    assert "Doe, J. Test Paper" in text  # the one that succeeded
    # Every missing format must appear with a MISSING marker + reason.
    for fmt in (
        "apa",
        "chicago",
        "harvard",
        "vancouver",
        "bibtex",
        "endnote",
        "refman",
        "refworks",
    ):
        label = cli._fmt_label(fmt)
        assert f"{label:<9} [MISSING:" in text or f"{label}:" in text or "[MISSING:" in text
    # Reason substrings propagated.
    assert "403 Forbidden" in text
    assert "not present in cite popup" in text


def test_render_json_exposes_citation_errors():
    import json as _json

    payload = cli._render_json([_paper_with_partial_results()], formats=list(cli.ALL_FORMATS))
    data = _json.loads(payload)
    assert data[0]["citation_errors"]["apa"].startswith("HTTPError")
    assert "bibtex" in data[0]["citation_errors"]


def test_cli_cite_strict_flag_exits_non_zero_on_partial(monkeypatch):
    """Review finding #2: --strict must propagate partial failure as exit code."""
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa", "bibtex"])

    def fake_search(query, limit, no_browser):
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="Only APA worked.")
        p.citation_errors = {"bibtex": "download aborted"}
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)

    result = runner.invoke(cli.app, ["cite", "any title", "--format", "apa,bibtex", "--strict"])
    assert result.exit_code == cli.EXIT_PARTIAL
    # Warning must be visible on stderr.
    assert "missing" in result.stderr.lower()


def test_cli_cite_no_strict_exits_zero_but_warns(monkeypatch):
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa", "bibtex"])

    def fake_search(query, limit, no_browser):
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="Only APA worked.")
        p.citation_errors = {"bibtex": "download aborted"}
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)

    result = runner.invoke(cli.app, ["cite", "any title", "--format", "apa,bibtex"])
    assert result.exit_code == cli.EXIT_OK
    assert "Warning" in result.stderr
    assert "missing" in result.stderr.lower()


def test_cli_cite_no_results_returns_exit_2(monkeypatch):
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa"])
    monkeypatch.setattr("scholar_cite.search.search", lambda q, limit, no_browser: [])
    result = runner.invoke(cli.app, ["cite", "nothing here"])
    assert result.exit_code == cli.EXIT_NO_RESULTS
