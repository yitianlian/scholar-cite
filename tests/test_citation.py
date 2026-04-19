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
    citations, exports = parse_cite_html(html)

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

    citations = fetch_citation_set("5Gohgn6QFikJ", fetch=fake_fetch)

    assert citations.mla.startswith("Vaswani, Ashish")
    assert citations.apa.startswith("Vaswani, A.")
    assert citations.chicago.startswith("Vaswani, Ashish, Noam Shazeer")
    assert citations.harvard.startswith("Vaswani, A., Shazeer, N.")
    assert citations.vancouver.startswith("Vaswani A")
    assert citations.bibtex.startswith("@inproceedings{vaswani2017")
    assert citations.endnote.startswith("%0 Conference Paper")
    assert citations.refman.startswith("TY  - CONF")
    assert citations.refworks.startswith("RT Conference Proceedings")

    # Every one of the 9 formats populated — no empties.
    assert all(citations.as_dict().values())


def test_extract_cluster_id_from_url_scholarbib():
    pub = {"url_scholarbib": "/scholar.bib?q=info:5Gohgn6QFikJ:scholar.google.com/&output=citation"}
    assert extract_cluster_id(pub) == "5Gohgn6QFikJ"


def test_extract_cluster_id_returns_none_when_missing():
    assert extract_cluster_id({"bib": {}}) is None
