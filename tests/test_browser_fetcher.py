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
