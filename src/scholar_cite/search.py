"""Search Google Scholar and assemble Paper objects with all 9 citation formats."""
from __future__ import annotations

from itertools import islice

from scholarly import scholarly
from scholarly._navigator import Navigator  # type: ignore[attr-defined]

from scholar_cite.citation import extract_cluster_id, fetch_citation_set
from scholar_cite.models import Paper


def _make_fetch():
    """Return a `fetch(url, timeout=...)` bound to scholarly's navigator session.

    scholarly maintains httpx Clients with the cookies Scholar expects; going
    through the navigator avoids the plain-requests 403s we see otherwise.
    """
    nav = Navigator()

    def fetch(url: str, timeout: float = 20.0) -> str:  # noqa: ARG001 — nav manages its own timeout
        text = nav._get_page(url)
        if not isinstance(text, str):
            raise RuntimeError(f"Unexpected response type from scholarly navigator: {type(text)}")
        return text

    return fetch


def search(query: str, limit: int = 10) -> list[Paper]:
    """Search Scholar by title and return up to `limit` Papers, each with full citation set."""
    results_iter = scholarly.search_pubs(query)
    fetch = _make_fetch()

    papers: list[Paper] = []
    for pub in islice(results_iter, limit):
        cluster_id = extract_cluster_id(pub)
        if not cluster_id:
            continue

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

        paper = Paper(
            cluster_id=str(cluster_id),
            title=str(bib.get("title", "")).strip(),
            authors=authors_list,
            year=year,
            venue=str(bib.get("venue", "")).strip(),
        )

        try:
            paper.citations = fetch_citation_set(paper.cluster_id, fetch=fetch)
        except Exception as e:  # noqa: BLE001
            paper.citations.mla = f"[error fetching citations: {e}]"

        papers.append(paper)

    return papers
