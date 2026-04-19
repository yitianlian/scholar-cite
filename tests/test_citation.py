"""Parser-level tests that don't hit Google Scholar."""
from __future__ import annotations

from pathlib import Path

import pytest

from scholar_cite.citation import (
    CaptchaError,
    ParseError,
    extract_cluster_id,
    fetch_citation_set,
    parse_cite_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_cite_html_extracts_all_five_text_formats():
    html = _load("cite_popup_sample.html")
    citations, _ = parse_cite_html(html)

    assert "Vaswani, Ashish, et al." in citations.mla
    assert "Vaswani, A., Shazeer, N." in citations.apa
    assert "Vaswani, Ashish, Noam Shazeer" in citations.chicago
    assert "Vaswani, A., Shazeer, N., Parmar, N." in citations.harvard
    assert citations.vancouver.startswith("Vaswani A, Shazeer N")


def test_parse_cite_html_extracts_all_four_export_links():
    html = _load("cite_popup_sample.html")
    _, exports = parse_cite_html(html)

    fields = {link.field for link in exports}
    assert fields == {"bibtex", "endnote", "refman", "refworks"}

    by_field = {link.field: link.url for link in exports}
    assert "/scholar.bib" in by_field["bibtex"]
    assert "/scholar.enw" in by_field["endnote"]
    assert "/scholar.ris" in by_field["refman"]
    assert "/scholar.rfw" in by_field["refworks"]


def test_parse_cite_html_raises_on_captcha():
    captcha_html = '<html><body><form id="captcha-form">solve me</form></body></html>'
    with pytest.raises(CaptchaError):
        parse_cite_html(captcha_html)


def test_parse_cite_html_raises_on_unrelated_html():
    with pytest.raises(ParseError):
        parse_cite_html("<html><body><p>nothing here</p></body></html>")


def test_fetch_citation_set_composes_all_nine_formats():
    cite_html = _load("cite_popup_sample.html")

    export_bodies = {
        "/scholar.bib": "@inproceedings{vaswani2017,\n  title={Attention is all you need}\n}",
        "/scholar.enw": "%0 Conference Paper\n%T Attention is all you need",
        "/scholar.ris": "TY  - CONF\nTI  - Attention is all you need",
        "/scholar.rfw": "RT Conference Proceedings\nT1 Attention is all you need",
    }

    def fake_fetch(url: str, timeout: float = 20.0) -> str:
        if "output=cite" in url:
            return cite_html
        for path, body in export_bodies.items():
            if path in url:
                return body
        raise AssertionError(f"Unexpected URL: {url}")

    citations, errors = fetch_citation_set("5Gohgn6QFikJ", fetch=fake_fetch)

    assert errors == {}
    assert citations.bibtex.startswith("@inproceedings{vaswani2017")
    assert citations.endnote.startswith("%0 Conference Paper")
    assert citations.refman.startswith("TY  - CONF")
    assert citations.refworks.startswith("RT Conference Proceedings")
    assert all(citations.as_dict().values())


def test_fetch_citation_set_records_per_export_failures():
    """Regression: partial failures must surface in the returned errors dict,
    not be silently swallowed."""
    cite_html = _load("cite_popup_sample.html")

    def fake_fetch(url: str, timeout: float = 20.0) -> str:
        if "output=cite" in url:
            return cite_html
        if "/scholar.bib" in url:
            return "@article{ok,\n  title={OK}\n}"
        # All other export URLs fail.
        raise RuntimeError(f"HTTP 403 on {url}")

    citations, errors = fetch_citation_set("5Gohgn6QFikJ", fetch=fake_fetch)

    assert citations.bibtex.startswith("@article{ok")
    # Text formats all came from the popup, so no errors for them.
    assert "mla" not in errors and "apa" not in errors
    # The three failed exports must be recorded.
    assert set(errors.keys()) == {"endnote", "refman", "refworks"}
    for name in ("endnote", "refman", "refworks"):
        assert "RuntimeError" in errors[name]
        assert "403" in errors[name]


def test_fetch_citation_set_refworks_redirect_cleaned():
    cite_html = _load("cite_popup_sample.html")
    redirect_html = (
        "<!doctype html><html><head>"
        "<script>location.replace('http://www.refworks.com/express?sid\\x3dgoogle"
        "\\x26au\\x3dFoo')</script></head><body></body></html>"
    )

    def fake_fetch(url: str, timeout: float = 20.0) -> str:
        if "output=cite" in url:
            return cite_html
        if "/scholar.rfw" in url:
            return redirect_html
        return "stub"

    citations, _ = fetch_citation_set("x", fetch=fake_fetch)
    assert "www.refworks.com/express" in citations.refworks
    assert citations.refworks.startswith("# Google Scholar's RefWorks export")
    # The escaped chars got decoded:
    assert "sid=google" in citations.refworks and "au=Foo" in citations.refworks


def test_extract_cluster_id_from_url_scholarbib():
    pub = {"url_scholarbib": "/scholar.bib?q=info:5Gohgn6QFikJ:scholar.google.com/&output=citation"}
    assert extract_cluster_id(pub) == "5Gohgn6QFikJ"


def test_extract_cluster_id_returns_none_when_missing():
    assert extract_cluster_id({"bib": {}}) is None
