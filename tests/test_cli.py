"""CLI behaviour tests — missing-format surfacing and exit codes."""

from __future__ import annotations

import pytest
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
    """Review finding #2 (part 1): --strict must propagate partial failure as
    exit code, and the message must mention the missing formats."""
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa", "bibtex"])

    def fake_search(query, limit, no_browser):
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="Only APA worked.")
        p.citation_errors = {"bibtex": "download aborted"}
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)

    result = runner.invoke(cli.app, ["cite", "any title", "--format", "apa,bibtex", "--strict"])
    assert result.exit_code == cli.EXIT_PARTIAL
    # Error message must be visible on stderr and name the missing format(s).
    assert "missing" in result.output.lower() or "missing" in (result.stderr or "").lower()


def test_cli_cite_strict_does_not_write_file_on_partial(tmp_path, monkeypatch):
    """Review finding #2 (part 2): --strict with -o must NOT write a file when
    any requested format is missing. Previously, the file was written AND the
    command exited 4 — dangerous for automation that checks file existence first."""
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa", "bibtex"])

    def fake_search(query, limit, no_browser):
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="Only APA worked.")
        p.citation_errors = {"bibtex": "download aborted"}
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)

    out_file = tmp_path / "refs.txt"
    result = runner.invoke(
        cli.app,
        ["cite", "any title", "--format", "apa,bibtex", "--strict", "-o", str(out_file)],
    )

    assert result.exit_code == cli.EXIT_PARTIAL
    assert not out_file.exists(), (
        f"--strict should refuse to write output on partial results, but {out_file} was created"
    )


def test_cli_cite_strict_writes_file_when_complete(tmp_path, monkeypatch):
    """--strict must still produce output when every requested format is present."""
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa"])

    def fake_search(query, limit, no_browser):
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="All good.")
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)

    out_file = tmp_path / "refs.txt"
    result = runner.invoke(
        cli.app,
        ["cite", "any title", "--format", "apa", "--strict", "-o", str(out_file)],
    )

    assert result.exit_code == cli.EXIT_OK
    assert out_file.exists()
    assert "All good." in out_file.read_text()


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


# ---------- input validation regressions ----------


def test_parse_formats_rejects_empty_string():
    """Regression: --format '' used to silently yield [] and render empty output."""
    import typer

    with pytest.raises(typer.BadParameter, match="at least one"):
        cli._parse_formats("")


def test_parse_formats_rejects_only_commas():
    import typer

    with pytest.raises(typer.BadParameter, match="at least one"):
        cli._parse_formats(",,,")
    with pytest.raises(typer.BadParameter, match="at least one"):
        cli._parse_formats("   ,  ,  ")


def test_parse_formats_accepts_all_keyword():
    assert cli._parse_formats("all") == list(cli.ALL_FORMATS)


def test_parse_formats_accepts_single_and_multi():
    assert cli._parse_formats("apa") == ["apa"]
    assert cli._parse_formats("apa,mla, bibtex") == ["apa", "mla", "bibtex"]


def test_cli_cite_rejects_empty_format_arg():
    """End-to-end: an empty --format is an error before the search even runs."""
    result = runner.invoke(cli.app, ["cite", "any title", "--format", ""])
    assert result.exit_code != 0
    output = (result.output or "") + (result.stderr or "")
    assert "at least one" in output.lower() or "format" in output.lower()


def test_cli_cite_rejects_zero_and_negative_limit():
    """Regression: --limit -1 used to silently cut the last candidate.
    Typer now rejects non-positive ints before we ever reach the slice."""
    for bad in ("-1", "0", "-10"):
        result = runner.invoke(cli.app, ["cite", "any title", "--limit", bad])
        assert result.exit_code != 0, f"--limit {bad} should be rejected"


def test_cli_cite_accepts_limit_one(monkeypatch):
    """The smallest valid --limit still works."""
    monkeypatch.setattr(cli, "_parse_formats", lambda _raw: ["apa"])

    def fake_search(query, limit, no_browser):
        assert limit == 1
        p = Paper(cluster_id="x", title="T")
        p.citations = CitationSet(apa="OK.")
        return [p]

    monkeypatch.setattr("scholar_cite.search.search", fake_search)
    result = runner.invoke(cli.app, ["cite", "q", "--format", "apa", "--limit", "1"])
    assert result.exit_code == cli.EXIT_OK
