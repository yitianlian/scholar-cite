"""Rank candidate Papers by the trustworthiness of their source host.

Google Scholar maintains multiple "clusters" per paper — arXiv preprint, official
conference proceedings, a mirror on some random site, etc. Each cluster has its
own Scholar-generated citation, and quality varies wildly: the official CVPR /
NeurIPS / ACL hosts typically produce clean citations, while scrapes from
aggregator sites (seen in the wild: `sandbox.getindico.io`) often have wrong
author order, fabricated volume numbers, and mangled venue strings.

We keep a small allow/deny list of hostnames with explicit scores. Everything
unlisted gets a neutral 0. Sorting is stable: within the same tier, Scholar's
original result order is preserved.
"""
from __future__ import annotations

from urllib.parse import urlparse

from scholar_cite.models import Paper

# Hostname → score. Higher = more trusted. Scores are just an ordering device;
# the absolute values don't matter, only their relative order.
_SOURCE_SCORES: dict[str, int] = {
    # Tier 1 — authoritative venue proceedings / repositories
    "openaccess.thecvf.com": 100,
    "aclanthology.org": 100,
    "proceedings.neurips.cc": 100,
    "papers.nips.cc": 100,
    "proceedings.mlr.press": 100,
    "openreview.net": 100,
    "jmlr.org": 100,
    "ieeexplore.ieee.org": 95,
    "dl.acm.org": 95,
    "link.springer.com": 90,
    "sciencedirect.com": 85,
    "nature.com": 95,
    "science.org": 95,
    # Tier 2 — preprints and common repositories
    "arxiv.org": 80,
    "biorxiv.org": 75,
    # Tier 3 — neutral aggregators / discovery engines
    "semanticscholar.org": 30,
    "researchgate.net": 10,
    # Tier 4 — known low-quality mirrors
    "sandbox.getindico.io": -100,
    "scholar.google.com": -50,  # self-reference — not a real paper source
}


def source_score(paper: Paper) -> int:
    """Return a score for ranking; higher = more trusted. Default 0 when unknown."""
    host = _hostname(paper.source_url)
    if not host:
        return 0
    if host in _SOURCE_SCORES:
        return _SOURCE_SCORES[host]
    # Suffix match so subdomains inherit the score.
    for known, score in _SOURCE_SCORES.items():
        if host.endswith("." + known):
            return score
    return 0


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:  # noqa: BLE001 — malformed URL → treat as unknown
        return ""


def rank_papers(papers: list[Paper]) -> list[Paper]:
    """Stable-sort papers by descending source_score.

    Ties preserve Scholar's original order, so unknown-source candidates keep
    their relative ranking exactly as Scholar surfaced them.
    """
    indexed = list(enumerate(papers))
    indexed.sort(key=lambda pair: (-source_score(pair[1]), pair[0]))
    return [p for _, p in indexed]
