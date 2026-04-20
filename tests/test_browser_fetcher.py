"""Cookie-cache robustness tests (no live browser launched)."""

from __future__ import annotations

import json
from pathlib import Path

from scholar_cite import browser_fetcher as bf


def test_cookies_status_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    st = bf.cookies_status()
    assert st["exists"] is False
    assert str(tmp_path) in st["path"]


def test_cookies_status_on_corrupt_json(tmp_path, monkeypatch):
    """Review finding #4: a corrupt cookie file must not crash the CLI."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = Path(tmp_path) / "scholar-cite" / "cookies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{this is not json", encoding="utf-8")

    st = bf.cookies_status()

    assert st["exists"] is True
    assert "error" in st
    assert "not valid JSON" in st["error"]
    # And the command that would have called it should not have raised.


def test_cookies_status_on_wrong_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = Path(tmp_path) / "scholar-cite" / "cookies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    st = bf.cookies_status()
    assert st["exists"] is True
    assert "error" in st
    assert "expected object" in st["error"]


def test_cookies_status_on_valid_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = Path(tmp_path) / "scholar-cite" / "cookies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "saved_at": 1700000000,
                "cookies": [
                    {"name": "SID", "value": "x", "domain": ".google.com"},
                    {"name": "NID", "value": "y", "domain": ".google.com"},
                    {"name": "Z", "value": "z", "domain": ".scholar.google.com"},
                ],
            }
        ),
        encoding="utf-8",
    )

    st = bf.cookies_status()
    assert st["exists"] is True
    assert "error" not in st
    assert st["cookie_count"] == 3
    assert ".google.com" in st["domains"]
    assert st["saved_at"] == 1700000000


def test_fetch_survives_playwright_navigation_race(monkeypatch):
    """Regression: during Scholar's anti-bot interstitial, the page is
    mid-navigation and `page.content()` raises:
        'Page.content: Unable to retrieve content because the page is
         navigating and changing the content.'

    Two code paths are exposed to this race: the initial content read
    (right after `page.goto`) and the post-captcha poll loop. Both used
    to propagate the exception and kill the entire search. Both should
    now degrade gracefully — the initial read falls back to
    `response.text()`, and the poll loop simply retries on the next tick.
    """
    import time as _time

    from scholar_cite import browser_fetcher as bf

    # page.content() return schedule: three mid-navigation raises, then the
    # cleared page's HTML. The initial read + poll ticks together exercise
    # both code paths.
    page_states = iter(
        [
            "RAISE",  # initial read: falls back to response.text()
            "RAISE",  # first poll tick: swallowed, retry
            "<html>Please show you're not a robot</html>",  # still anti-bot
            "RAISE",  # another race
            "<html>gs_r gs_or About 9 results</html>",  # challenge cleared
        ]
    )

    class _Response:
        def __init__(self):
            self.status = 200
            self.headers = {"content-type": "text/html"}

        def text(self):
            # Fallback body: the raw anti-bot HTML so the anti-bot detector
            # fires and hands off to the poll loop.
            return "<html>Please show you're not a robot</html>"

    class _FakePage:
        def content(self):
            state = next(page_states)
            if state == "RAISE":
                raise RuntimeError(
                    "Page.content: Unable to retrieve content because the page is navigating"
                )
            return state

        def goto(self, *_a, **_kw):
            return _Response()

    fetcher = bf.BrowserFetcher(headless=False)
    fetcher._page = _FakePage()
    fetcher._context = object()  # type: ignore[assignment]
    fetcher._captcha_wait = 30.0  # plenty of poll ticks

    monkeypatch.setattr(_time, "sleep", lambda _s: None)  # instant ticks

    body = fetcher.fetch(
        "https://scholar.google.com/scholar?q=anything",
        timeout=5.0,
        settle_ms=0,
    )
    assert "About 9 results" in body
    assert "not a robot" not in body


def test_clear_cookies_when_absent_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert bf.clear_cookies() is False


def test_clear_cookies_when_present_returns_true(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = Path(tmp_path) / "scholar-cite" / "cookies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")

    assert bf.clear_cookies() is True
    assert not path.exists()
