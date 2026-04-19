"""Playwright-based URL fetcher that reuses a real browser context.

Google Scholar returns 403 to plain HTTP requests and serves a "Sorry, I'm not
a robot" page to headless browsers. `BrowserFetcher` defaults to a **headful**
Chromium with a few light stealth patches, which lets the user solve a captcha
once if needed; cookies are then cached and reused for future runs.

Flow on first use:
    1. Launch headful Chromium.
    2. On the first Scholar navigation, if Scholar shows the anti-bot page, the
       user solves the challenge in the visible window.
    3. `fetch()` waits for the page to clear (polls for result markers, up to
       the timeout).
    4. Subsequent fetches reuse the same browser context — no captcha needed
       as long as the cookies remain valid.
    5. On shutdown, cookies are written to `~/.cache/scholar-cite/cookies.json`
       for the next invocation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Small JS shim that hides the most obvious automation markers. Not foolproof,
# but enough to keep Scholar from immediately flagging the session when run
# headful.
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
"""

_ANTIBOT_MARKERS = (
    "Please show you're not a robot",
    "/sorry/index",
    'id="captcha-form"',
    "unusual traffic from your computer",
)

_RESULT_MARKERS_SEARCH = ('id="gs_res_ccl"', "gs_r gs_or", "About ")
_RESULT_MARKERS_CITE = ("gs_citr", "gs_citi", "scholar.bib")


def _cookie_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "scholar-cite" / "cookies.json"


def _page_is_antibot(text: str) -> bool:
    return any(m in text for m in _ANTIBOT_MARKERS)


class BrowserFetcher:
    """Open a Chromium context once, fetch many URLs through it, persist cookies on close."""

    def __init__(
        self,
        *,
        headless: bool = False,
        slow_mo_ms: int = 0,
        captcha_wait_seconds: float = 300.0,
    ) -> None:
        self._headless = headless
        self._slow_mo_ms = slow_mo_ms
        self._captcha_wait = captcha_wait_seconds
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # ---------- context manager ----------

    def __enter__(self) -> BrowserFetcher:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            slow_mo=self._slow_mo_ms,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=_DEFAULT_UA,
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        self._context.add_init_script(_STEALTH_JS)
        self._load_cookies_into(self._context)
        self._page = self._context.new_page()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._context is not None:
                self._save_cookies_from(self._context)
        finally:
            if self._context is not None:
                self._context.close()
            if self._browser is not None:
                self._browser.close()
            if self._pw is not None:
                self._pw.stop()

    # ---------- public API ----------

    def fetch(
        self,
        url: str,
        *,
        timeout: float = 30.0,
        settle_ms: int = 300,
        success_markers: tuple[str, ...] | None = None,
    ) -> str:
        """Navigate to `url`, handle captcha if necessary, return response body.

        If `success_markers` is provided and the initial page looks like a
        Scholar anti-bot page, we wait (up to `captcha_wait_seconds`) for the
        user to solve it in the visible window and for one of the markers to
        appear. Otherwise the raw HTML is returned as-is.
        """
        assert self._page is not None, "BrowserFetcher must be used as a context manager"
        if success_markers is None:
            success_markers = (
                _RESULT_MARKERS_CITE
                if "output=cite" in url
                or "scholar.bib" in url
                or "scholar.enw" in url
                or "scholar.ris" in url
                or "scholar.rfw" in url
                else _RESULT_MARKERS_SEARCH
            )

        response = self._page.goto(url, wait_until="load", timeout=int(timeout * 1000))
        if response is None:
            raise RuntimeError(f"No response from {url}")
        status = response.status
        if status >= 400:
            try:
                body_on_error = response.text()
            except Exception:
                body_on_error = self._page.content()
            raise RuntimeError(f"{url} returned HTTP {status}\n---\n{body_on_error[:400]}")

        # `response.text()` gives raw bytes as sent by the server, which is what we want for
        # the text/plain export endpoints. For an HTML page, we prefer the rendered DOM so
        # stealth/init scripts have applied.
        body = (
            self._page.content()
            if "text/html" in (response.headers.get("content-type") or "").lower()
            else response.text()
        )

        # Handle anti-bot / captcha interstitial
        if _page_is_antibot(body):
            if self._headless:
                raise RuntimeError(
                    "Scholar served an anti-bot page to the headless browser. "
                    "Retry with --browser (headful mode) so you can solve it once."
                )
            print(f"[browser] Anti-bot page detected on {url[:80]} — solve it in the window.")
            deadline = time.time() + self._captcha_wait
            while time.time() < deadline:
                time.sleep(2.0)
                current = self._page.content()
                if not _page_is_antibot(current) and any(m in current for m in success_markers):
                    body = current
                    print("[browser] Challenge solved. Continuing.")
                    break
            else:
                raise RuntimeError(
                    "Timed out waiting for user to solve Scholar anti-bot challenge."
                )

        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
        return body

    def fetch_api(self, url: str, *, timeout: float = 30.0) -> str:
        """Fetch a URL via the context's APIRequestContext (shares browser cookies).

        Use this for endpoints that would otherwise trigger a file download in
        Chromium (`/scholar.bib`, `/scholar.enw`, `/scholar.ris`, `/scholar.rfw`
        on scholar.googleusercontent.com). `page.goto()` aborts on downloads;
        the API context just returns the response body.
        """
        assert self._context is not None, "BrowserFetcher must be used as a context manager"
        response = self._context.request.get(url, timeout=timeout * 1000)
        if response.status >= 400:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        body = response.text()
        if _page_is_antibot(body):
            raise RuntimeError(f"Scholar served an anti-bot page for API fetch {url}")
        return body

    # ---------- cookies ----------

    def _save_cookies_from(self, context: BrowserContext) -> None:
        path = _cookie_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            cookies = context.cookies()
            path.write_text(
                json.dumps({"saved_at": int(time.time()), "cookies": cookies}, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_cookies_into(self, context: BrowserContext) -> None:
        path = _cookie_path()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cookies = payload.get("cookies", [])
            if cookies:
                context.add_cookies(cookies)
        except Exception:
            pass


def cookies_status() -> dict:
    """Summarise the cached cookie file.

    Robust against a missing file, a corrupt JSON payload, or a payload whose
    shape is unexpected — each of those returns a descriptive error dict
    rather than raising, so `scholar-cite auth status` can always run.
    """
    path = _cookie_path()
    base = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return base

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return {**base, "error": f"cannot read cookie file: {e}"}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            **base,
            "error": f"cookie file is not valid JSON: {e.msg} (line {e.lineno}, col {e.colno})",
            "size_bytes": len(raw),
        }

    if not isinstance(payload, dict):
        return {**base, "error": f"cookie file root is {type(payload).__name__}, expected object"}

    cookies = payload.get("cookies", [])
    if not isinstance(cookies, list):
        return {**base, "error": f"'cookies' field is {type(cookies).__name__}, expected list"}

    return {
        **base,
        "saved_at": payload.get("saved_at"),
        "cookie_count": len(cookies),
        "domains": sorted(
            {c.get("domain", "") for c in cookies if isinstance(c, dict) and c.get("domain")}
        ),
    }


def clear_cookies() -> bool:
    path = _cookie_path()
    if path.exists():
        path.unlink()
        return True
    return False
