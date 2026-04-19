"""Search Google Scholar and assemble Paper objects with all 9 citation formats.

There are two paths:

  * `_search_via_scholarly` — uses the `scholarly` library's plain-HTTP
    session. Fast when it works, but Scholar frequently returns 403 /
    MaxTriesExceeded once it decides the caller isn't a browser.

  * `_search_via_browser` — drives a real headless Chromium through
    `BrowserFetcher` for the search page, the cite popup, and every export
    link. Slower but survives Scholar's rate limiter because the browser
    session looks like a normal user.

The top-level `search()` dispatches between them. If `use_browser=True` or
`scholarly` raises `MaxTriesExceededException`, the browser path takes over.
"""
from __future__ import annotations

import re
import sys
from itertools import islice
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scholar_cite.browser_fetcher import BrowserFetcher
from scholar_cite.citation import extract_cluster_id, fetch_citation_set
from scholar_cite.models import ALL_FORMATS, Paper

SCHOLAR_SEARCH_URL = "https://scholar.google.com/scholar?hl=en&q={query}"


# ----------------------- scholarly path ---------------------------------------


def _paper_from_scholarly_pub(pub: dict) -> Paper | None:
    cluster_id = extract_cluster_id(pub)
    if not cluster_id:
        return None
    bib = pub.get("bib", {}) or {}
    authors = bib.get("author")
    if isinstance(authors, str):
        authors_list = [a.strip() for a in authors.split(" and ")]
    elif isinstance(authors, list):
        authors_list = [str(a) for a in authors]
    else:
        authors_list = []

    year_raw = bib.get("pub_year") or bib.get("year")
    try:
        year = int(year_raw) if year_raw else None
    except (TypeError, ValueError):
        year = None

    return Paper(
        cluster_id=str(cluster_id),
        title=str(bib.get("title", "")).strip(),
        authors=authors_list,
        year=year,
        venue=str(bib.get("venue", "")).strip(),
    )


def _search_via_scholarly(query: str, limit: int) -> list[Paper]:
    """Return candidate Papers (metadata only) via the scholarly library."""
    from scholarly import scholarly  # lazy

    papers: list[Paper] = []
    for pub in islice(scholarly.search_pubs(query), limit):
        p = _paper_from_scholarly_pub(pub)
        if p is not None:
            papers.append(p)
    return papers


def _fill_via_scholarly(papers: list[Paper]) -> None:
    """Try to fill each paper's citations via scholarly's session. Silent on failure."""
    from scholarly._navigator import Navigator  # type: ignore[attr-defined]

    nav = Navigator()

    def fetch(url: str, timeout: float = 20.0) -> str:  # noqa: ARG001
        text = nav._get_page(url)
        if not isinstance(text, str):
            raise RuntimeError(f"Unexpected response type: {type(text)}")
        return text

    for paper in papers:
        try:
            paper.citations = fetch_citation_set(paper.cluster_id, fetch=fetch)
        except Exception:  # noqa: BLE001
            pass


# ----------------------- browser path -----------------------------------------


_CLUSTER_FROM_HREF = re.compile(r"info:([^:]+):scholar\.google\.com")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parse_search_page(html: str) -> list[Paper]:
    """Parse Scholar's search results page into metadata-only Paper objects."""
    soup = BeautifulSoup(html, "lxml")
    papers: list[Paper] = []

    for row in soup.select("div.gs_r.gs_or.gs_scl, div.gs_r.gs_or"):
        title_el = row.select_one("h3.gs_rt a") or row.select_one("h3.gs_rt")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        # Authors / venue / year line: "A Author, B Author - Venue, 2020 - publisher"
        gs_a = row.select_one("div.gs_a")
        authors: list[str] = []
        year: int | None = None
        venue = ""
        if gs_a:
            gs_a_text = gs_a.get_text(" ", strip=True)
            parts = [p.strip() for p in gs_a_text.split(" - ")]
            if parts:
                authors = [a.strip() for a in parts[0].split(",") if a.strip()]
            if len(parts) > 1:
                m = _YEAR_RE.search(parts[1])
                if m:
                    try:
                        year = int(m.group(0))
                    except ValueError:
                        year = None
                venue = re.sub(_YEAR_RE, "", parts[1]).strip(", ").strip()

        # cluster_id from the "Cite" link
        cite_link = row.select_one("a.gs_or_cit[data-clk]") or row.select_one("a.gs_or_cit")
        cluster_id = None
        if cite_link:
            href = cite_link.get("href", "")
            m = _CLUSTER_FROM_HREF.search(href)
            if m:
                cluster_id = m.group(1)
        if not cluster_id:
            # Fallback: <div data-cid="..."> wrapping the result
            cid = row.get("data-cid")
            if cid:
                cluster_id = cid

        if not cluster_id or not title:
            continue

        papers.append(
            Paper(
                cluster_id=str(cluster_id),
                title=title,
                authors=authors,
                year=year,
                venue=venue,
            )
        )

    return papers


def _search_via_browser(query: str, limit: int) -> list[Paper]:
    """Use Playwright end-to-end: search page → parse → cite popup → 9 formats."""
    url = SCHOLAR_SEARCH_URL.format(query=quote_plus(query))

    with BrowserFetcher(headless=False) as bf:
        print("[browser] fetching search page…", file=sys.stderr)
        search_html = bf.fetch(url, timeout=45.0, settle_ms=800)
        papers = _parse_search_page(search_html)[:limit]
        print(f"[browser] parsed {len(papers)} result(s); fetching citations…", file=sys.stderr)

        def fetch(u: str, timeout: float = 30.0) -> str:
            # Cite popup = HTML page on scholar.google.com → use page.goto()
            # Export endpoints = text/plain on scholar.googleusercontent.com →
            # use the API request context to avoid Chromium's download prompt.
            if "scholar.googleusercontent.com" in u or u.endswith((".bib", ".enw", ".ris", ".rfw")):
                return bf.fetch_api(u, timeout=timeout)
            return bf.fetch(u, timeout=timeout, settle_ms=600)

        for i, paper in enumerate(papers, 1):
            try:
                paper.citations = fetch_citation_set(paper.cluster_id, fetch=fetch)
                filled = sum(1 for v in paper.citations.as_dict().values() if v)
                print(
                    f"[browser]   [{i}/{len(papers)}] {paper.cluster_id} — {filled}/9 formats",
                    file=sys.stderr,
                )
            except Exception as e:  # noqa: BLE001
                print(f"[browser]   [{i}/{len(papers)}] {paper.cluster_id} — FAILED: {e}",
                      file=sys.stderr)
                if not paper.citations.mla:
                    paper.citations.mla = f"[error fetching citations: {e}]"

    return papers


def _all_formats_populated(paper: Paper) -> bool:
    d = paper.citations.as_dict()
    return all(d[name] for name in ALL_FORMATS)


# ----------------------- public API -------------------------------------------


def search(query: str, limit: int = 10, use_browser: bool = False) -> list[Paper]:
    """Search Scholar and return up to `limit` Papers with citations filled.

    - `use_browser=True`: use Playwright for everything (search + citations).
    - `use_browser=False`: try scholarly first; if that path blows up (the
      usual cause is Scholar serving a 403 captcha page), automatically fall
      back to the browser path.
    """
    if use_browser:
        return _search_via_browser(query, limit)

    try:
        papers = _search_via_scholarly(query, limit)
    except Exception as e:  # noqa: BLE001
        print(f"[fallback] scholarly path failed ({e}); switching to browser.", file=sys.stderr)
        return _search_via_browser(query, limit)

    _fill_via_scholarly(papers)

    incomplete = [p for p in papers if not _all_formats_populated(p)]
    if not incomplete:
        return papers

    # Some (or all) papers are missing formats — retry the missing ones via browser.
    print(
        f"[fallback] {len(incomplete)}/{len(papers)} papers missing format(s); "
        f"reopening via browser.",
        file=sys.stderr,
    )
    with BrowserFetcher(headless=False) as bf:
        def fetch(u: str, timeout: float = 30.0) -> str:
            if "scholar.googleusercontent.com" in u or u.endswith((".bib", ".enw", ".ris", ".rfw")):
                return bf.fetch_api(u, timeout=timeout)
            return bf.fetch(u, timeout=timeout, settle_ms=600)

        for paper in incomplete:
            try:
                fresh = fetch_citation_set(paper.cluster_id, fetch=fetch)
                for name in ALL_FORMATS:
                    v = getattr(fresh, name, "")
                    if v:
                        setattr(paper.citations, name, v)
            except Exception as e:  # noqa: BLE001
                if not paper.citations.mla:
                    paper.citations.mla = f"[error fetching citations: {e}]"

    return papers
