# Changelog

All notable changes to scholar-cite are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- **Browser path no longer crashes on cite-popup HTTP 403.** The per-paper
  citation loop used to catch only `ScholarBlockedError`, but
  `BrowserFetcher.fetch()` raises a plain `RuntimeError("... returned HTTP 403")`
  on anti-bot responses, and `fetch_citation_set()` raises `CaptchaError`,
  neither of which matched the old catch. Extracted a shared
  `_fill_paper_citations()` that funnels every scholar-blocking exception
  (via `_is_scholar_blocked()`) into per-format error entries; real bugs still
  propagate. Used by both the browser and scholarly paths.
- **`--strict` no longer writes a partial output file before exiting 4.** The
  strict gate now runs before any output is produced — neither stdout nor the
  `-o` file is touched when any requested format is missing. Downstream
  automation that checks file existence first will no longer be fooled by a
  partially-populated dump.
- **`cv-foundation.org` added to the trusted-host ranking table.** The older
  CVF proceedings archive (pre-`openaccess.thecvf.com`) was getting the default
  score of 0, so an unknown mirror listed first by Scholar would outrank it.
  Also added `thecvf.com` bare-domain, `ojs.aaai.org`, and `aaai.org` for
  completeness. The ResNet-scenario regression test now asserts the CVF
  cluster lands first.

### Added
- Packaging polish: MIT `LICENSE`, expanded `pyproject.toml` metadata
  (classifiers, keywords, project URLs, optional-dependencies group, ruff + pytest
  configuration), `CHANGELOG.md`, `docs/ARCHITECTURE.md`, and an `examples/`
  directory with a five-paper demo script.
- 7 new regression tests (38 total, up from 31) covering each of the three
  review findings and two adjacent cases (real bugs still propagate; strict
  still writes output when the result is complete).
- `docs/e2e-verification.md` — live end-to-end evidence after the fixes,
  including a wheel install smoke test in a clean venv.
- README install section rewritten with three options (`pipx` from git,
  `pip install` from wheel, editable dev install) and a first-run captcha
  note.
- `.gitignore` now excludes `dist/`, `build/`, `wheels/`, `*.whl`, `*.tar.gz`
  so build artefacts don't accidentally get committed.

### Changed
- Code formatted with `ruff format` and lint-clean under the new ruff ruleset
  (`E W F I UP B SIM RUF`).

## [0.1.0] — 2026-04-19

First working MVP. Commits, newest first:

### `29bd104` — Rank candidates by source quality to avoid bad Scholar clusters
- Added `Paper.source_url`, extracted from each Scholar result row's title link
  (and from `pub["pub_url"]` in the scholarly path).
- New `scholar_cite.ranking` module: hostname → score table, suffix matching
  covers subdomains, stable sort preserves Scholar's order within a tier.
- `_search_via_browser` parses all rows on the first page and ranks before
  truncating to `--limit`; `_search_via_scholarly` pulls 2× `limit` (≤10) to
  give ranking enough candidates.
- 7 new tests in `test_ranking.py`, including a ResNet-scenario regression
  (skip `sandbox.getindico.io`, land on the clean CVPR cluster).

### `db1d7b3` — Address review: narrow catches, surface partial failures, robust auth
- `search()` no longer treats every exception as "Scholar blocked us".
  `_is_scholar_blocked()` only recognises rate-limit / captcha / 403 / 429 /
  `MaxTriesExceeded` / timeout signatures. Generic bugs (ValueError, KeyError,
  parser regressions) propagate.
- Per-format failures are now surfaced:
  - `fetch_citation_set()` returns `(CitationSet, errors: dict[str, str])`.
  - `Paper.citation_errors` records the reason for each missing format.
  - Plain-text output renders `[MISSING: <reason>]` inline; JSON output adds
    a `citation_errors` field; stderr prints a warning summary.
  - New `--strict` flag exits 4 when any requested format is missing.
- `scholarly` HTTP path is no longer the default — `--browser` is the default,
  `--no-browser` opts into scholarly with no silent fallback.
- `cookies_status()` robust against corrupt / wrong-shape / unreadable cookie
  caches — returns an `error` field instead of raising.
- 17 new tests across `test_search.py`, `test_cli.py`, `test_browser_fetcher.py`.

### `4ec7286` — Fix exports: add Playwright browser backend; 9/9 formats live
- New `scholar_cite.browser_fetcher.BrowserFetcher`: headful Chromium with
  light stealth patches (hide `navigator.webdriver` etc.), waits up to 5 min
  for the user to solve Scholar's anti-bot page, persists cookies to
  `~/.cache/scholar-cite/cookies.json`.
- Key fix: `page.goto()` aborts on `text/plain` downloads, which is how
  Scholar serves `.enw` and `.ris`. Export URLs now go through
  `BrowserContext.request` (`fetch_api`) — same cookies, no download prompt.
- CLI restructured into subcommands (`cite`, `auth status`, `auth reset`).
- RefWorks redirect stub cleaned: the `www.refworks.com/express?...` import
  URL is extracted from Scholar's JS redirect and presented in place of raw
  HTML.
- All 9 formats verified live against "Attention Is All You Need".

### `6229b61` — MVP: scholar-cite CLI with design doc + parser tests
- Initial project layout: `cli.py`, `search.py`, `citation.py`, `models.py`,
  cite-popup HTML fixture, 7 unit tests.
- `docs/design.md` with full specification; `docs/test-run-2026-04-19.md` with
  first live test evidence (5/9 formats captured before export URLs hit 403).
