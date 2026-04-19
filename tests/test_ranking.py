"""Source-quality ranking tests."""

from __future__ import annotations

from scholar_cite.models import Paper
from scholar_cite.ranking import rank_papers, source_score


def _p(cluster_id: str, url: str) -> Paper:
    return Paper(cluster_id=cluster_id, title="t", source_url=url)


def test_source_score_recognises_trusted_venues():
    assert source_score(_p("a", "https://openaccess.thecvf.com/...")) == 100
    assert source_score(_p("a", "https://aclanthology.org/...")) == 100
    assert source_score(_p("a", "https://proceedings.neurips.cc/...")) == 100
    assert source_score(_p("a", "https://ieeexplore.ieee.org/...")) == 95
    assert source_score(_p("a", "https://arxiv.org/abs/1234.5678")) == 80


def test_source_score_demotes_known_junk():
    assert source_score(_p("a", "https://sandbox.getindico.io/event/...")) == -100
    assert source_score(_p("a", "https://scholar.google.com/scholar?...")) == -50


def test_source_score_unknown_host_is_neutral():
    assert source_score(_p("a", "https://www.somerandom.blog/post")) == 0
    assert source_score(_p("a", "")) == 0  # no URL at all
    assert source_score(_p("a", "not-a-url")) == 0


def test_source_score_suffix_match_covers_subdomains():
    assert source_score(_p("a", "https://papers.nips.cc/paper_files/...")) == 100
    # A subdomain of openaccess.thecvf.com should still inherit the score.
    assert source_score(_p("a", "https://mirror.openaccess.thecvf.com/...")) == 100


def test_rank_papers_prefers_trusted_over_junk():
    """The bad cluster (sandbox.getindico.io) must land last, even if Scholar
    put it first."""
    junk = _p("c1", "https://sandbox.getindico.io/event/999/resnet.pdf")
    good = _p("c2", "https://openaccess.thecvf.com/content_cvpr_2016/papers/resnet.pdf")
    ranked = rank_papers([junk, good])
    assert [p.cluster_id for p in ranked] == ["c2", "c1"]


def test_rank_papers_is_stable_within_a_tier():
    """Unknown-source candidates (all score 0) must keep Scholar's original order."""
    a = _p("a", "https://a.example.com/")
    b = _p("b", "https://b.example.com/")
    c = _p("c", "https://c.example.com/")
    # Inject a high-score one in the middle: it must jump to the top;
    # the rest stay in their original a-b-c order.
    trusted = _p("t", "https://arxiv.org/abs/xyz")
    ranked = rank_papers([a, b, trusted, c])
    assert [p.cluster_id for p in ranked] == ["t", "a", "b", "c"]


def test_source_score_recognises_cv_foundation_org():
    """Regression for review finding #3: cv-foundation.org is an official CVF archive
    and must be tier-1, not unknown."""
    assert source_score(_p("a", "https://www.cv-foundation.org/openaccess/resnet.pdf")) == 100
    assert source_score(_p("a", "https://cv-foundation.org/openaccess/resnet.pdf")) == 100


def test_rank_papers_official_cvf_beats_unknown_mirror():
    """Regression for review finding #3: an unknown mirror listed FIRST by Scholar
    must NOT outrank the cv-foundation.org cluster when ranking is on."""
    mirror = _p("mirror", "https://mirror.example.com/resnet.pdf")  # unknown → 0
    cvf = _p("cvf", "https://www.cv-foundation.org/openaccess/resnet.pdf")  # now 100
    ranked = rank_papers([mirror, cvf])
    assert [p.cluster_id for p in ranked] == ["cvf", "mirror"]


def test_rank_papers_handles_resnet_style_scenario():
    """Simulate the real-world ResNet case: bad cluster #1, good cluster #2."""
    bad = _p("56OwN-n020UJ", "https://sandbox.getindico.io/event/101/contributions/x.pdf")
    cvf = _p("LrPNPdmMzoAJ", "https://www.cv-foundation.org/openaccess/resnet.pdf")
    ieee = _p("F3zseCJbSpwJ", "https://ieeexplore.ieee.org/document/7780459")
    arxiv = _p("X", "https://arxiv.org/abs/1512.03385")

    # Scholar's original order (worst result first, which is what we actually see)
    ranked = rank_papers([bad, cvf, ieee, arxiv])
    # CVF (100) > IEEE (95) > arXiv (80) > sandbox (-100)
    assert [p.cluster_id for p in ranked] == [
        "LrPNPdmMzoAJ",
        "F3zseCJbSpwJ",
        "X",
        "56OwN-n020UJ",
    ]
