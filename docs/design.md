# scholar-cite — Design Document

**Date**: 2026-04-19
**Status**: Draft, pending user approval before implementation plan
**Owner**: @Touencent

---

## 1. Purpose

A Python CLI tool that takes a paper title, searches **Google Scholar**, and returns all 9 native citation formats (MLA, APA, Chicago, Harvard, Vancouver, BibTeX, EndNote, RefMan, RefWorks).

Solves the recurring pain of manually opening Scholar, searching, clicking "Cite", and copying formats one by one — especially for batch reference list building.

### Non-goals
- Not a bibliography manager (no library / tagging / notes — use Zotero for that).
- Not a full paper search replacement (no full-text search, no PDF download).
- Not meant to replace Scholar's web UI; just the "grab citation" step.

---

## 2. User-Facing Interface

### 2.1 Commands

```bash
# Single title (most common)
scholar-cite "Attention Is All You Need"
scholar-cite "Attention Is All You Need" --format all
scholar-cite "Attention Is All You Need" --format apa,mla,bibtex
scholar-cite "Attention Is All You Need" -c         # copy to clipboard

# Batch
scholar-cite -f titles.txt -o refs.bib              # one title per line → combined output
scholar-cite -f titles.txt --format all -o refs.json --json

# Interactive (pick from candidates when ambiguous)
scholar-cite -i

# Auth management (for captcha cookies)
scholar-cite auth status
scholar-cite auth refresh
scholar-cite auth reset

# Config
scholar-cite config set serpapi_key YOUR_KEY
scholar-cite config get
```

### 2.2 Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `bibtex` | Comma-separated: `bibtex,apa,mla,chicago,harvard,vancouver,endnote,refman,refworks,all` |
| `-c`, `--clipboard` | off | Copy output to system clipboard |
| `-o`, `--output PATH` | stdout | Write to file |
| `-f`, `--file PATH` | — | Read titles from file (one per line) for batch mode |
| `-i`, `--interactive` | off | Launch interactive picker |
| `--json` | off | Emit JSON (machine-readable) |
| `--refresh` | off | Bypass cache, re-fetch from Scholar |
| `--no-cache` | off | Neither read nor write cache |
| `--limit N` | 10 (first result page) | Max candidate papers to return when ambiguous |
| `--backend` | `auto` | `scholarly` / `serpapi` / `auto` (fallback chain) |
| `--timeout SECONDS` | 20 | Per-request timeout |
| `--quiet` | off | Suppress progress/status output |

### 2.3 Ambiguity handling

One title often matches multiple papers (different years / authors / versions):

- **Non-interactive mode (default)**: return **all** candidates from Scholar's first result page (typically up to 10). `--limit N` truncates to the top N. Each candidate is labeled with `[1]`, `[2]`, etc., showing title + first author + year + venue, followed by its full citation block.
- **Interactive mode (`-i`)**: show candidates in a `questionary`/`InquirerPy` picker, user selects which one(s) to emit.

Rationale: non-interactive callers (scripts, batch) shouldn't be blocked. If the user wants disambiguation, they opt in.

### 2.4 Example output (plain text, `--format all`)

```
% scholar-cite "Attention Is All You Need" --format all
[1] Attention Is All You Need
    Vaswani, A. et al. (2017) — Advances in Neural Information Processing Systems
    cluster_id: 2960712678066186980
    —————————————————————————————————————
    MLA:    Vaswani, Ashish, et al. "Attention is all you need." Advances in neural information processing systems 30 (2017).
    APA:    Vaswani, A., Shazeer, N., ..., & Polosukhin, I. (2017). Attention is all you need. Advances in neural information processing systems, 30.
    Chicago: ...
    Harvard: ...
    Vancouver: ...

    BibTeX:
    @inproceedings{vaswani2017attention,
      title={Attention is all you need},
      author={Vaswani, Ashish and Shazeer, Noam and ...},
      booktitle={Advances in neural information processing systems},
      volume={30},
      year={2017}
    }

    EndNote:  ...
    RefMan:   ...
    RefWorks: ...
```

### 2.5 JSON output schema (`--json`)

```json
[
  {
    "query": "Attention Is All You Need",
    "candidates": [
      {
        "cluster_id": "2960712678066186980",
        "title": "Attention is all you need",
        "authors": ["Vaswani, A.", "Shazeer, N.", "..."],
        "year": 2017,
        "venue": "Advances in neural information processing systems",
        "doi": null,
        "citations": {
          "mla": "...",
          "apa": "...",
          "chicago": "...",
          "harvard": "...",
          "vancouver": "...",
          "bibtex": "@inproceedings{...}",
          "endnote": "%0 ...",
          "refman": "TY - ...",
          "refworks": "..."
        },
        "fetched_at": "2026-04-19T12:34:56Z",
        "from_cache": false
      }
    ]
  }
]
```

---

## 3. Architecture

### 3.1 Module layout

```
scholar-cite/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/
│   └── design.md                  # ← this file
├── src/
│   └── scholar_cite/
│       ├── __init__.py
│       ├── __main__.py            # python -m scholar_cite
│       ├── cli.py                 # Typer entry point
│       ├── config.py              # TOML config read/write
│       ├── models.py              # Paper, Citation, CitationSet dataclasses
│       ├── search.py              # Unified search interface
│       ├── backends/
│       │   ├── __init__.py
│       │   ├── base.py            # Backend ABC
│       │   ├── scholarly_backend.py
│       │   └── serpapi_backend.py
│       ├── citation.py            # Fetch the 9 formats from Scholar cite endpoint
│       ├── cache.py               # SQLite cache layer
│       ├── captcha.py             # Playwright-based manual captcha recovery
│       ├── output.py              # Text / JSON / clipboard formatters
│       └── interactive.py         # InquirerPy picker
└── tests/
    ├── fixtures/                  # Saved Scholar HTML responses
    ├── test_cli.py
    ├── test_search.py
    ├── test_citation.py
    ├── test_cache.py
    └── test_output.py
```

### 3.2 Module responsibilities & interfaces

| Module | Responsibility | Key interface |
|--------|----------------|---------------|
| `cli.py` | Argument parsing, command dispatch | Typer app; thin — delegates to other modules |
| `config.py` | Load/save `~/.config/scholar-cite/config.toml` | `Config.load()`, `Config.set(key, value)` |
| `models.py` | Data types | `Paper`, `Citation`, `CitationSet` (frozen dataclasses) |
| `search.py` | Orchestrate: try cache → try backend(s) → write cache | `search(query: str) -> list[Paper]` |
| `backends/base.py` | Abstract backend | `class Backend: def search(query) -> list[Paper]; def fetch_citations(cluster_id) -> CitationSet` |
| `backends/scholarly_backend.py` | Free scraping via `scholarly` + custom cite endpoint hit | Implements `Backend` |
| `backends/serpapi_backend.py` | Paid fallback via SerpAPI's `google_scholar` + `google_scholar_cite` engines | Implements `Backend` |
| `citation.py` | Parse Scholar's cite popup HTML → 5 text + 4 export formats | `parse_cite_html(html)` |
| `cache.py` | SQLite-backed lookup by `cluster_id` / `title_hash` / `doi` | `Cache.get(key)`, `Cache.put(paper)`, `Cache.invalidate(cluster_id)` |
| `captcha.py` | Detect captcha, launch Playwright, harvest cookies, inject into session | `CaptchaSolver.recover(requests_session)` |
| `output.py` | Format `list[Paper]` as plain / JSON / clipboard | `render(papers, mode)` |
| `interactive.py` | Present picker when ambiguous | `pick(candidates) -> Paper \| list[Paper]` |

Each module is < 300 lines and individually testable.

### 3.3 Data flow (single query, cache miss)

```
user runs CLI
  ↓
cli.py parses args, calls search.search(query)
  ↓
search.py checks cache.Cache (title_hash → cluster_id → Paper)
  ↓ cache miss
search.py picks backend (auto → scholarly first)
  ↓
scholarly_backend.search(query)
  ├─ calls scholarly library → list[ScholarlyResult]
  ├─ for each result: extract cluster_id, metadata
  ├─ for each result: fetch Scholar cite popup HTML
  │   └─ if HTTP response is captcha page:
  │       └─ captcha.CaptchaSolver.recover()
  │           └─ Playwright headful → user solves → cookies saved → retry
  └─ citation.parse_cite_html(html) → CitationSet
  ↓
search.py writes each Paper to cache
  ↓
cli.py calls output.render(papers, format=args.format)
  ↓
stdout / file / clipboard
```

---

## 4. Cache Design

### 4.1 Storage
- **Format**: SQLite (single file, transactional, indexed lookups).
- **Location**: `$XDG_CACHE_HOME/scholar-cite/scholar.db`, fallback `~/.cache/scholar-cite/scholar.db`.

### 4.2 Schema

```sql
CREATE TABLE papers (
  cluster_id   TEXT PRIMARY KEY,
  doi          TEXT,
  title        TEXT NOT NULL,
  authors_json TEXT NOT NULL,         -- JSON array of author strings
  year         INTEGER,
  venue        TEXT,
  citations_json TEXT NOT NULL,       -- JSON: {"bibtex": "...", "apa": "...", ...}
  fetched_at   TEXT NOT NULL          -- ISO 8601 UTC
);

CREATE TABLE title_index (
  title_hash TEXT PRIMARY KEY,        -- SHA1 of normalize_title(raw)
  cluster_id TEXT NOT NULL REFERENCES papers(cluster_id) ON DELETE CASCADE
);

CREATE TABLE doi_index (
  doi        TEXT PRIMARY KEY,        -- lowercased DOI
  cluster_id TEXT NOT NULL REFERENCES papers(cluster_id) ON DELETE CASCADE
);

CREATE INDEX idx_papers_fetched_at ON papers(fetched_at);
```

### 4.3 Key strategy
- **Primary key**: Scholar `cluster_id` — stable internal Google ID that both `scholarly` and SerpAPI expose. Extracted from Scholar's cite link: `https://scholar.google.com/scholar?cites=<cluster_id>`.
- **Title index**: `sha1(normalize_title(title))` → `cluster_id`. `normalize_title` = lowercase, strip punctuation, collapse whitespace. Same logical title (regardless of casing / trailing periods) hashes identically.
- **DOI index**: lowercased DOI → `cluster_id`. Populated when metadata includes a DOI.

### 4.4 Lookup order
1. Exact query → `title_index` → `cluster_id` → `papers`
2. If query looks like a DOI → `doi_index` → `cluster_id` → `papers`
3. Cache miss → call backend, populate all three tables on success.

### 4.5 TTL
- Default: 90 days. Citations almost never change; a long TTL is safe.
- Configurable in `config.toml`: `cache.ttl_days = 90`.
- `--refresh` bypasses TTL and forces re-fetch.
- `--no-cache` skips cache read and write entirely.

### 4.6 Eviction
- No automatic eviction (personal tool, disk cheap).
- `scholar-cite cache clear` manual subcommand.
- `scholar-cite cache stats` shows size, entry count.

---

## 5. Google Scholar Backend Details

### 5.1 The citation endpoint

Scholar's "Cite" popup is served at:

```
GET https://scholar.google.com/scholar?q=info:{cluster_id}:scholar.google.com/&output=cite&scirp=0&hl=en
```

Response is HTML containing:
- 5 `<div class="gs_citr">` elements for MLA, APA, Chicago, Harvard, Vancouver (plain text).
- 4 `<a>` links for BibTeX, EndNote, RefMan, RefWorks — each link hits `scholar.googleusercontent.com/scholar.bib?...` to return the machine-readable format.

### 5.2 Fetch sequence
1. Search → get cluster_ids from result page.
2. For each cluster_id, fetch the cite HTML → parse 5 text formats.
3. For each of 4 export links, issue a separate GET → full format content.
4. Assemble `CitationSet` and cache.

### 5.3 Rate limiting
- Batch mode: minimum 3s + random [0, 2s] jitter between Scholar requests.
- Single-query mode: no artificial delay (1 cite popup + 4 export fetches is still 5 requests; acceptable).
- After captcha recovery, double the delay for next 10 requests to avoid immediate re-trigger.

### 5.4 SerpAPI fallback
- Engines used: `google_scholar` (search) + `google_scholar_cite` (citation formats).
- Single SerpAPI call per paper returns all 9 formats directly.
- Free tier: 100 searches/month. Config key: `serpapi_key`.
- Auto-fallback trigger: scholarly backend raises `CaptchaError` OR `MaxRetriesError` AND SerpAPI key is configured.

---

## 6. Captcha Handling — Manual Once, Reuse After

### 6.1 Detection
Response body matches known captcha markers (`id="captcha-form"`, `sorry/index`, etc.) → raise `CaptchaError`.

### 6.2 Recovery flow
1. `CaptchaSolver.recover()` prints: `"⚠ Google Scholar triggered a captcha. Opening browser — please solve it, then close the window."`
2. Launch **Playwright Chromium in headful mode**, navigate to `https://scholar.google.com/scholar?q={original_query}`.
3. Wait for the URL / DOM to indicate a successful search result page (poll every 2s, timeout 5min).
4. Extract `context.cookies()` filtered to `.google.com` / `scholar.google.com`.
5. Save cookies to `~/.cache/scholar-cite/cookies.json` with `{"saved_at": iso, "cookies": [...]}`.
6. Close the browser.
7. Inject cookies into the running `requests.Session` (used by `scholarly`).
8. Retry the original failed request.

### 6.3 Cookie reuse
- On every backend call, `scholarly_backend` initializes its session with cookies from `~/.cache/scholar-cite/cookies.json` if present.
- Cookies are not pruned by TTL; reuse until they fail. When they fail → trigger captcha recovery again.

### 6.4 Dependencies
- `playwright` Python package.
- Chromium browser: one-time `playwright install chromium` (~150MB).
- README documents this clearly in the install section.

### 6.5 Auth subcommands
- `scholar-cite auth status` → prints cookie file path, saved_at, number of cookies, domain coverage.
- `scholar-cite auth refresh` → force-launches the Playwright flow even if cookies exist.
- `scholar-cite auth reset` → deletes `cookies.json`.

---

## 7. Configuration

### 7.1 File
- Location: `$XDG_CONFIG_HOME/scholar-cite/config.toml`, fallback `~/.config/scholar-cite/config.toml`.
- Format: TOML.

### 7.2 Schema

```toml
[backend]
default = "auto"          # "scholarly" | "serpapi" | "auto"

[serpapi]
api_key = ""              # if set, used as fallback when scholarly fails

[cache]
enabled = true
ttl_days = 90

[scholar]
request_delay_seconds = 3 # base delay between scholar requests in batch mode
jitter_seconds = 2        # random jitter added on top
timeout_seconds = 20

[output]
default_format = "bibtex"
```

### 7.3 Env var overrides
- `SCHOLAR_CITE_SERPAPI_KEY` overrides `[serpapi].api_key`
- `SCHOLAR_CITE_NO_CACHE=1` equivalent to `--no-cache`

---

## 8. Error Handling

| Error | Cause | User-facing behavior |
|-------|-------|----------------------|
| `NoResultsError` | Search returned zero results | Exit 2, print `"No papers matched: <query>"` |
| `CaptchaError` (recoverable) | First-time captcha | Launch Playwright flow, retry automatically |
| `CaptchaError` (after recovery fails) | User closed browser without solving | Exit 3, suggest `--backend serpapi` |
| `HTTPError` / `Timeout` | Network issue | Retry 2× with exponential backoff (1s, 3s); exit 4 if still failing |
| `ParsingError` | Scholar HTML structure changed | Exit 5, print `"Could not parse Scholar response — please report at <repo>/issues"` with the query and a truncated HTML snippet |
| `ConfigError` | Invalid config.toml / missing SerpAPI key when required | Exit 6, clear remediation message |
| Exit 0 | Success | — |
| Exit 1 | Generic / unexpected | — |

All errors emit to stderr; stdout only receives citation content (so `>` redirection works cleanly).

---

## 9. Testing

### 9.1 Unit tests
- **`test_citation.py`**: parse saved Scholar HTML fixtures (in `tests/fixtures/cite_vaswani.html` etc.) → assert extracted formats match expected.
- **`test_cache.py`**: in-memory SQLite, round-trip paper, test TTL expiry, title normalization.
- **`test_output.py`**: render logic for plain / JSON / format filtering.
- **`test_cli.py`**: use `typer.testing.CliRunner`; mock `search.search()`.

### 9.2 Integration tests
- Use `responses` library to mock HTTP endpoints with fixture HTML.
- Test the full pipeline: CLI arg → search → cache → output.
- **No tests hit real Google Scholar** (too flaky for CI).

### 9.3 Fixture refresh playbook
- When Scholar changes its HTML structure, re-save fresh fixtures manually via a helper script (`scripts/refresh_fixtures.py`).
- Document this in `tests/fixtures/README.md`.

### 9.4 Manual smoke test checklist
Before each release:
- [ ] Single query for a known paper → all 9 formats correct.
- [ ] Batch mode with 5-title file → `-o output.bib` well-formed.
- [ ] Interactive picker → arrow keys + enter work.
- [ ] Cache hit: second invocation of same query completes < 100ms.
- [ ] `--refresh` bypasses cache.
- [ ] Captcha flow (manually trigger with many rapid queries).

---

## 10. Dependencies

### 10.1 Runtime
- `typer[all]` — CLI framework
- `scholarly` — Google Scholar scraping
- `requests` — HTTP (already a scholarly dep, explicit for our own calls)
- `beautifulsoup4` + `lxml` — HTML parsing
- `playwright` — captcha recovery browser
- `inquirerpy` or `questionary` — interactive picker
- `pyperclip` — clipboard
- `tomli` (stdlib `tomllib` on Py ≥ 3.11) — config reading
- `tomli-w` — config writing
- `serpapi` — optional, lazy-imported only if SerpAPI backend is used

### 10.2 Dev
- `pytest`, `pytest-cov`, `responses`, `ruff`, `mypy`

### 10.3 Python version
- **≥ 3.11** (for `tomllib` in stdlib; aligns with scholarly's requirements).

---

## 11. Distribution

- `pyproject.toml` with a `project.scripts` entry: `scholar-cite = "scholar_cite.cli:app"`.
- Published to PyPI as `scholar-cite`.
- Recommended install: `pipx install scholar-cite`.
- Post-install hint in README: `playwright install chromium` (one-time).

---

## 12. Out of Scope (explicit YAGNI)

- Multi-language Scholar (`&hl=`) — default `en`; not parameterizing yet.
- Concurrent batch requests — serial with delay is safer for rate limiting.
- Proxy rotation — `scholarly` supports it, but we delegate that choice to the user via scholarly's own API if they really need it.
- Semantic Scholar / DBLP / Crossref fallback — user explicitly asked for Google Scholar only.
- GUI / web UI — CLI only.
- De-duplication of citations across a batch — keep as-is; user can post-process.

---

## 13. Open questions
_None at this time — awaiting user review before moving to implementation plan._

---

## 14. References
- `scholarly` library: https://scholarly.readthedocs.io/
- SerpAPI Google Scholar: https://serpapi.com/google-scholar-api
- SerpAPI Google Scholar Cite: https://serpapi.com/google-scholar-cite-api
- Playwright Python: https://playwright.dev/python/
- Typer: https://typer.tiangolo.com/
