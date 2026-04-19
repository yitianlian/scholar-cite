"""Search Google Scholar and assemble Paper objects with all 9 citation formats.

Two paths:

  * **Browser (default, most reliable)**: drive a real headful Chromium via
    `BrowserFetcher` for the search page, the cite popup, and every export
    link. Survives Scholar's rate limiter because the session looks like a
    normal browser. Slower but consistent.

  * **scholarly (opt-in via `no_browser=True`)**: use the `scholarly` library's
    plain-HTTP session. Faster when it works, but Scholar blocks it frequently
    on fresh IPs or after a handful of requests. Does *not* silently fall back
    — if Scholar blocks it or partial citations fail, the failures are surfaced
    to the caller rather than masked.

Non-blocking bugs (parser errors, type errors, etc.) always propagate — they
should not be misinterpreted as "Scholar is rate-limiting us".
"""
from __future__ import annotations

import re
import sys
from itertools import islice
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scholar_cite.browser_fetcher import BrowserFetcher
from scholar_cite.citation import (
    ScholarBlockedError,
    extract_cluster_id,
    fetch_citation_set,
)
from scholar_cite.models import ALL_FORMATS, Paper

SCHOLAR_SEARCH_URL = "https://scholar.google.com/scholar?hl=en&q={query}"


# ----------------------- metadata adaptors ------------------------------------


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


# ----------------------- scholarly path ---------------------------------------


def _is_scholar_blocked(exc: BaseException) -> bool:
    """Return True for exceptions that mean 'Scholar refused the request'.

    Crucially, this does NOT return True for generic programming errors —
    ValueError, KeyError, TypeError, parser bugs, etc. Those propagate.
    """
    name = type(exc).__name__
    if name in ("MaxTriesExceededException", "ScholarBlockedError", "CaptchaError"):
        return True
    # requests-level failures that match Scholar's rate-limiting behaviour.
    if name in ("ConnectionError", "Timeout", "ReadTimeout", "ProxyError"):
        return True
    if name == "HTTPError":
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (403, 429, 503):
            return True
    msg = str(exc)
    if "403" in msg or "429" in msg or "MaxTries" in msg or "captcha" in msg.lower():
        return True
    return False


def _search_via_scholarly(query: str, limit: int) -> list[Paper]:
    from scholarly import scholarly  # lazy

    papers: list[Paper] = []
    for pub in islice(scholarly.search_pubs(query), limit):
        p = _paper_from_scholarly_pub(pub)
        if p is not None:
            papers.append(p)
    return papers


def _fill_via_scholarly(papers: list[Paper]) -> None:
    from scholarly._navigator import Navigator  # type: ignore[attr-defined]

    nav = Navigator()

    def fetch(url: str, timeout: float = 20.0) -> str:  # noqa: ARG001
        text = nav._get_page(url)
        if not isinstance(text, str):
            raise RuntimeError(f"Unexpected response type: {type(text)}")
        return text

    for paper in papers:
        try:
            paper.citations, paper.citation_errors = fetch_citation_set(
                paper.cluster_id, fetch=fetch
            )
        except Exception as e:  # noqa: BLE001
            if _is_scholar_blocked(e):
                # Record it as a blocked-by-Scholar state; caller decides policy.
                for name in ALL_FORMATS:
                    paper.citation_errors.setdefault(name, f"scholar blocked: {e}")
            else:
                # Real bug: don't mask it.
                raise


# ----------------------- browser path -----------------------------------------


_CLUSTER_FROM_HREF = re.compile(r"info:([^:]+):scholar\.google\.com")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parse_search_page(html: str) -> list[Paper]:
    soup = BeautifulSoup(html, "lxml")
    papers: list[Paper] = []

    for row in soup.select("div.gs_r.gs_or.gs_scl, div.gs_r.gs_or"):
        title_el = row.select_one("h3.gs_rt a") or row.select_one("h3.gs_rt")
        if not title_el:
            continue
        title = title_el.get_text(" ", strip=True)
        gs_a = row.select_one("div.gs_a")
        authors: list[str] = []
        year: int | None = None
        venue = ""
        if gs_a:
            parts = [p.strip() for p in gs_a.get_text(" ", strip=True).split(" - ")]
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

        cite_link = row.select_one("a.gs_or_cit[data-clk]") or row.select_one("a.gs_or_cit")
        cluster_id = None
        if cite_link:
            m = _CLUSTER_FROM_HREF.search(cite_link.get("href", ""))
            if m:
                cluster_id = m.group(1)
        if not cluster_id:
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
    url = SCHOLAR_SEARCH_URL.format(query=quote_plus(query))

    with BrowserFetcher(headless=False) as bf:
        print("[browser] fetching search page…", file=sys.stderr)
        search_html = bf.fetch(url, timeout=45.0, settle_ms=800)
        papers = _parse_search_page(search_html)[:limit]
        print(f"[browser] parsed {len(papers)} result(s); fetching citations…", file=sys.stderr)

        def fetch(u: str, timeout: float = 30.0) -> str:
            if "scholar.googleusercontent.com" in u or u.endswith(
                (".bib", ".enw", ".ris", ".rfw")
            ):
                return bf.fetch_api(u, timeout=timeout)
            return bf.fetch(u, timeout=timeout, settle_ms=600)

        for i, paper in enumerate(papers, 1):
            try:
                paper.citations, paper.citation_errors = fetch_citation_set(
                    paper.cluster_id, fetch=fetch
                )
            except ScholarBlockedError as e:
                for name in ALL_FORMATS:
                    paper.citation_errors.setdefault(name, f"scholar blocked: {e}")
            filled = sum(1 for v in paper.citations.as_dict().values() if v)
            msg = f"[browser]   [{i}/{len(papers)}] {paper.cluster_id} — {filled}/9 formats"
            if paper.citation_errors:
                msg += f" ({len(paper.citation_errors)} missing)"
            print(msg, file=sys.stderr)

    return papers


# ----------------------- public API -------------------------------------------


def search(query: str, limit: int = 10, no_browser: bool = False) -> list[Paper]:
    """Search Scholar and return up to `limit` Papers with citations filled.

    - default (`no_browser=False`): end-to-end Playwright (reliable).
    - `no_browser=True`: scholarly path only, no fallback. Partial/blocked
      results are recorded on each `Paper.citation_errors` and the caller can
      decide how strict to be.

    Real programming errors (parse bugs, type errors, etc.) are NEVER masked
    as "Scholar blocked us". Only exceptions that look like genuine Scholar
    refusals (403/429/MaxTries/captcha/timeout) are recorded as such.
    """
    if not no_browser:
        return _search_via_browser(query, limit)

    papers = _search_via_scholarly(query, limit)
    _fill_via_scholarly(papers)
    return papers
