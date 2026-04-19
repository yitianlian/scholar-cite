"""Parse Scholar's cite popup HTML and fetch the 4 export formats."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scholar_cite.models import EXPORT_FORMATS, TEXT_FORMATS, CitationSet


class PageFetcher(Protocol):
    """Callable that fetches a URL and returns the response text (raises on failure)."""

    def __call__(self, url: str, timeout: float = ...) -> str: ...

SCHOLAR_BASE = "https://scholar.google.com"
CITE_URL_TEMPLATE = (
    SCHOLAR_BASE
    + "/scholar?q=info:{cluster_id}:scholar.google.com/&output=cite&scirp=0&hl=en"
)

# Scholar's cite popup text-format order; maps anchor label → our CitationSet field.
_TEXT_LABEL_MAP = {
    "MLA": "mla",
    "APA": "apa",
    "Chicago": "chicago",
    "Harvard": "harvard",
    "Vancouver": "vancouver",
}

# Export link inference by href extension.
_EXPORT_EXT_MAP = {
    ".bib": "bibtex",
    ".enw": "endnote",
    ".ris": "refman",
    ".rfw": "refworks",
}


class CaptchaError(RuntimeError):
    """Raised when Scholar serves a captcha instead of the expected page."""


class ScholarBlockedError(RuntimeError):
    """Raised when Scholar rejects the request (HTTP 403/429, MaxTriesExceeded, captcha).

    Semantically: 'Scholar is actively refusing us, falling back to a different
    backend may help'. Distinct from genuine bugs (parsing, type errors, etc.).
    """


class ParseError(RuntimeError):
    """Raised when the cite popup HTML cannot be parsed."""


@dataclass
class _ExportLink:
    field: str
    url: str


def _looks_like_captcha(html: str) -> bool:
    markers = ('id="captcha-form"', "/sorry/index", "unusual traffic from your computer")
    return any(m in html for m in markers)


def parse_cite_html(html: str, base_url: str = SCHOLAR_BASE) -> tuple[CitationSet, list[_ExportLink]]:
    """Extract the 5 text formats and the 4 export links from Scholar's cite popup HTML.

    Returns (CitationSet with text fields filled, list of export links still to fetch).
    """
    if _looks_like_captcha(html):
        raise CaptchaError("Scholar served a captcha page instead of citation data")

    soup = BeautifulSoup(html, "lxml")
    citations = CitationSet()

    # Text formats: each row in the cite popup is a <tr> with a <th> label and a <td> value.
    # Layout (simplified):
    #   <tr><th>MLA</th><td><div class="gs_citr">...</div></td></tr>
    rows_found = 0
    for tr in soup.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(strip=True)
        field = _TEXT_LABEL_MAP.get(label)
        if not field:
            continue
        citr = td.find(class_="gs_citr") or td
        setattr(citations, field, citr.get_text(" ", strip=True))
        rows_found += 1

    # Fallback: some layouts use <div class="gs_cith"> for labels.
    if rows_found == 0:
        labels = soup.find_all(class_="gs_cith")
        values = soup.find_all(class_="gs_citr")
        for label_el, value_el in zip(labels, values):
            field = _TEXT_LABEL_MAP.get(label_el.get_text(strip=True))
            if field:
                setattr(citations, field, value_el.get_text(" ", strip=True))
                rows_found += 1

    if rows_found == 0:
        raise ParseError("Could not locate any text citation formats in cite popup HTML")

    # Export links: Scholar emits <a href="/scholar.bib?..." class="gs_citi">BibTeX</a>
    # etc., but the class has varied historically. Match by href extension + label to
    # be robust to cosmetic HTML changes.
    exports: list[_ExportLink] = []
    seen_fields: set[str] = set()
    for a in soup.find_all("a"):
        href = a.get("href", "") or ""
        label = a.get_text(strip=True).lower()
        field = None
        for ext, f in _EXPORT_EXT_MAP.items():
            if ext in href:
                field = f
                break
        if field is None:
            for key in ("bibtex", "endnote", "refman", "refworks"):
                if key in label:
                    field = key
                    break
        if field and field not in seen_fields and href:
            exports.append(_ExportLink(field=field, url=urljoin(base_url, href)))
            seen_fields.add(field)

    return citations, exports


def fetch_citation_set(
    cluster_id: str,
    fetch: PageFetcher,
    timeout: float = 20.0,
) -> tuple[CitationSet, dict[str, str]]:
    """Fetch all 9 formats for a paper via Scholar's cite popup + export links.

    Returns `(CitationSet, errors)` where `errors` maps format name → one-line
    failure reason for any format that could not be retrieved. A partial
    result is always returned — the caller decides whether to treat missing
    formats as fatal.

    Raises:
        CaptchaError / ScholarBlockedError: the cite popup itself was blocked;
            nothing useful was fetched. The caller should either retry via a
            different backend or surface the error to the user.
        ParseError: the cite popup was served but its structure wasn't
            recognised — indicates a bug or a Scholar HTML change.
    """
    cite_url = CITE_URL_TEMPLATE.format(cluster_id=cluster_id)
    html = fetch(cite_url, timeout=timeout)
    if _looks_like_captcha(html):
        raise CaptchaError(f"Scholar captcha triggered on cluster_id={cluster_id}")

    citations, export_links = parse_cite_html(html)
    errors: dict[str, str] = {}

    # Any text format that didn't come through is a parse-level miss, not a
    # network failure — record it so the caller can decide.
    for name in TEXT_FORMATS:
        if not getattr(citations, name):
            errors[name] = "not present in cite popup"

    # Record which export formats didn't even have a link in the HTML.
    found_export_fields = {link.field for link in export_links}
    for name in EXPORT_FORMATS:
        if name not in found_export_fields:
            errors[name] = "no export link in cite popup"

    for link in export_links:
        try:
            body = fetch(link.url, timeout=timeout)
            if _looks_like_captcha(body):
                raise CaptchaError(f"Scholar captcha triggered on export {link.field}")
            cleaned = _clean_refworks(body) if link.field == "refworks" else body
            setattr(citations, link.field, cleaned.strip())
            errors.pop(link.field, None)
        except CaptchaError as e:
            errors[link.field] = f"captcha: {e}"
        except Exception as e:  # noqa: BLE001 — narrow handling; still record.
            errors[link.field] = f"{type(e).__name__}: {e}"

    return citations, errors


_REFWORKS_REDIRECT_RE = re.compile(
    r"""location\.replace\(['"]([^'"]+)['"]\)""", re.IGNORECASE
)


def _clean_refworks(body: str) -> str:
    """Scholar's 'RefWorks' export is a redirect stub to refworks.com — not a citation.

    If we recognise the redirect, return a minimal, useful payload: a one-line
    comment + the target URL. Users who have a RefWorks account can paste that
    URL into a logged-in browser to import the citation.
    """
    if "refworks.com" not in body:
        return body
    m = _REFWORKS_REDIRECT_RE.search(body)
    if not m:
        return body
    url = (
        m.group(1)
        .replace(r"\x3d", "=")
        .replace(r"\x26", "&")
        .replace(r"\x2f", "/")
    )
    return f"# Google Scholar's RefWorks export is an external redirect.\n# Import URL:\n{url}"


_CLUSTER_ID_RE = re.compile(r"info:([^:]+):scholar\.google\.com")


def extract_cluster_id(pub: dict) -> str | None:
    """Pull cluster_id out of a scholarly publication dict."""
    # Direct keys sometimes present
    for key in ("cluster_id", "cites_id"):
        val = pub.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, list) and val:
            return str(val[0])

    # Fallback: parse from url_scholarbib
    bib_url = pub.get("url_scholarbib") or pub.get("url_add_sclib") or ""
    m = _CLUSTER_ID_RE.search(bib_url)
    return m.group(1) if m else None
