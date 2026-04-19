"""Tests for search-path exception handling.

Covers the review findings that `search()` must NOT silently catch generic
exceptions and that scholar-blocking failures must be reported per-format
rather than hidden.
"""
from __future__ import annotations

import pytest

from scholar_cite import search as search_mod
from scholar_cite.citation import ScholarBlockedError
from scholar_cite.models import Paper


@pytest.fixture
def dummy_paper():
    return Paper(cluster_id="abc123", title="Test", authors=["A B"], year=2024, venue="X")


def test_is_scholar_blocked_recognises_rate_limit_errors():
    class MaxTriesExceededException(Exception):
        pass

    assert search_mod._is_scholar_blocked(MaxTriesExceededException("blocked"))
    assert search_mod._is_scholar_blocked(ScholarBlockedError("blocked"))
    # Message-based fallback (requests.HTTPError text).
    assert search_mod._is_scholar_blocked(RuntimeError("HTTP 403 Forbidden"))
    assert search_mod._is_scholar_blocked(RuntimeError("HTTP 429 Too Many Requests"))


def test_is_scholar_blocked_rejects_generic_bugs():
    # Review finding #1: generic programming errors must NOT look like rate limiting.
    assert not search_mod._is_scholar_blocked(ValueError("parser bug"))
    assert not search_mod._is_scholar_blocked(KeyError("missing key"))
    assert not search_mod._is_scholar_blocked(TypeError("type mismatch"))
    assert not search_mod._is_scholar_blocked(AttributeError("no attr"))


def test_fill_via_scholarly_propagates_real_bugs(monkeypatch, dummy_paper):
    """Review finding #1: a ValueError in the scholarly path must propagate,
    not be swallowed as 'Scholar blocked us'."""

    def boom(*_args, **_kwargs):
        raise ValueError("parser bug")

    monkeypatch.setattr(search_mod, "fetch_citation_set", boom)
    # Stub out Navigator so we don't actually hit the network on import.
    import scholarly._navigator as nav_mod  # type: ignore

    class _FakeNav:
        def _get_page(self, url: str) -> str:
            return ""

    monkeypatch.setattr(nav_mod, "Navigator", _FakeNav)

    with pytest.raises(ValueError, match="parser bug"):
        search_mod._fill_via_scholarly([dummy_paper])


def test_fill_via_scholarly_records_blocked_state(monkeypatch, dummy_paper):
    """Scholar-blocking errors are recorded per format, not raised."""

    class MaxTriesExceededException(Exception):
        pass

    def blocked(*_args, **_kwargs):
        raise MaxTriesExceededException("Cannot Fetch from Google Scholar.")

    monkeypatch.setattr(search_mod, "fetch_citation_set", blocked)
    import scholarly._navigator as nav_mod  # type: ignore

    class _FakeNav:
        def _get_page(self, url: str) -> str:
            return ""

    monkeypatch.setattr(nav_mod, "Navigator", _FakeNav)

    search_mod._fill_via_scholarly([dummy_paper])

    # All 9 formats should be marked as blocked — none silently dropped.
    from scholar_cite.models import ALL_FORMATS

    assert set(dummy_paper.citation_errors.keys()) == set(ALL_FORMATS)
    for err in dummy_paper.citation_errors.values():
        assert "scholar blocked" in err
