"""Fetch BibTeX for five classic ML papers using one browser session.

This is the snippet we use as a smoke test (see README). Running it is the
fastest way to confirm a fresh install works end-to-end.

    python examples/demo_five_papers.py

Expected output: five `@article{...}` / `@inproceedings{...}` entries, one per
paper, on stdout. Progress goes to stderr so `python examples/demo_five_papers.py > refs.bib`
gives a clean `.bib` file.
"""
from __future__ import annotations

import sys
from urllib.parse import quote_plus

from scholar_cite.browser_fetcher import BrowserFetcher
from scholar_cite.citation import fetch_citation_set
from scholar_cite.ranking import rank_papers
from scholar_cite.search import SCHOLAR_SEARCH_URL, _parse_search_page

QUERIES = [
    "Attention Is All You Need Vaswani",
    "Deep Residual Learning for Image Recognition He Kaiming",
    "You Only Look Once Unified Real-Time Object Detection Redmon",
    "ImageNet Classification with Deep Convolutional Neural Networks Krizhevsky",
    "Generative Adversarial Nets Goodfellow",
]


def main() -> int:
    print("Opening one browser session for all five queries…", file=sys.stderr)

    with BrowserFetcher(headless=False) as bf:

        def fetch(url: str, timeout: float = 30.0) -> str:
            if "scholar.googleusercontent.com" in url or url.endswith(
                (".bib", ".enw", ".ris", ".rfw")
            ):
                return bf.fetch_api(url, timeout=timeout)
            return bf.fetch(url, timeout=timeout, settle_ms=500)

        for idx, query in enumerate(QUERIES, 1):
            print(f"\n[{idx}/{len(QUERIES)}] searching: {query!r}", file=sys.stderr)
            search_html = bf.fetch(
                SCHOLAR_SEARCH_URL.format(query=quote_plus(query)),
                timeout=45.0,
                settle_ms=600,
            )
            ranked = rank_papers(_parse_search_page(search_html))
            if not ranked:
                print("   (no results)", file=sys.stderr)
                continue

            paper = ranked[0]
            print(
                f"   → {paper.title[:80]}   cluster_id={paper.cluster_id}",
                file=sys.stderr,
            )
            try:
                citations, errors = fetch_citation_set(paper.cluster_id, fetch=fetch)
            except Exception as e:  # noqa: BLE001 — report and continue to next paper.
                print(f"   ! citation fetch failed: {e}", file=sys.stderr)
                continue

            if citations.bibtex:
                print(f"% [{idx}] {paper.title}")
                print(citations.bibtex)
                print()
            else:
                reason = errors.get("bibtex", "missing")
                print(f"% [{idx}] {paper.title}   [MISSING bibtex: {reason}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
