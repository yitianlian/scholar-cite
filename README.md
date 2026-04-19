# scholar-cite

A Python CLI that searches **Google Scholar** by paper title and returns the 9 citation formats (MLA, APA, Chicago, Harvard, Vancouver, BibTeX, EndNote, RefMan, RefWorks).

> **Status**: MVP — **all 9 formats verified end-to-end via the Playwright browser path** ([`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md)). Plain-HTTP path (`scholarly`) works intermittently and auto-falls-back to the browser when blocked. Full design in [`docs/design.md`](docs/design.md).

## Install (dev)

```bash
git clone <this-repo>
cd scholar-cite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium   # ~150MB, one-time
```

Python 3.10+ required (tested on 3.14).

## Usage

```bash
# Single title → BibTeX on stdout (default, tries plain HTTP, falls back to browser)
scholar-cite cite "Attention Is All You Need"

# All 9 formats, via the headful browser (most reliable)
scholar-cite cite "Attention Is All You Need" --format all --browser

# Specific subset
scholar-cite cite "Attention Is All You Need" --format apa,mla,bibtex

# Cap candidates
scholar-cite cite "Attention Is All You Need" --limit 3

# JSON output (for scripting)
scholar-cite cite "Attention Is All You Need" --format all --json --browser

# Write to file
scholar-cite cite "Attention Is All You Need" --format bibtex -o refs.bib --browser

# Manage the browser cookie cache
scholar-cite auth status
scholar-cite auth reset
```

### First run with `--browser`

A Chromium window pops up. If Scholar shows "Please show you're not a robot",
click through the challenge — the tool waits up to 5 minutes. Cookies are cached
at `~/.cache/scholar-cite/cookies.json` and reused on subsequent runs, so you
shouldn't see the challenge again for days.

## Example output

Running `scholar-cite cite "Attention Is All You Need" --format all --limit 1 --browser`:

```
[1] Attention is all you need
    A Vaswani — proceedings.neurips.cc
    cluster_id: 5Gohgn6QFikJ
    ──────────────────────────────────────────────────
    MLA:       Vaswani, Ashish, et al. "Attention is all you need." Advances ...
    APA:       Vaswani, A., Shazeer, N., Parmar, N., ... (2017). Attention is ...
    Chicago:   Vaswani, Ashish, Noam Shazeer, Niki Parmar, ... "Attention is ...
    Harvard:   Vaswani, A., Shazeer, N., Parmar, N., ... 2017. Attention is ...
    Vancouver: Vaswani A, Shazeer N, Parmar N, ... Attention is all you need ...
    Bibtex:
        @article{vaswani2017attention,
          title={Attention is all you need},
          author={Vaswani, Ashish and Shazeer, Noam and ...},
          ...
        }
    Endnote:
        %0 Journal Article
        %T Attention is all you need
        ...
    Refman:
        TY  - JOUR
        T1  - Attention is all you need
        ...
    Refworks:
        # Google Scholar's RefWorks export is an external redirect.
        # Import URL:
        http://www.refworks.com/express?sid=google&...
```

## Key design decisions

- **Free-first, paid fallback**: uses [`scholarly`](https://scholarly.readthedocs.io/) by default. A SerpAPI fallback for when Scholar rate-limits is planned (see design §5.4).
- **Captcha handled once (planned)**: a browser opens, you solve the captcha manually, cookies cached and reused. See design §6.
- **SQLite cache keyed by Scholar `cluster_id`** (planned): titles/DOIs are secondary indices, 90-day TTL. See design §4.
- **Ambiguous matches**: non-interactive mode returns all candidates; interactive mode (planned) prompts you to pick.
- **No Scholar request in tests**: CI uses saved HTML fixtures.

## What's implemented vs planned

| Feature | Status |
|---------|--------|
| Scholar search (scholarly + browser fallback) | ✅ working |
| `cluster_id` extraction (scholarly + browser) | ✅ working |
| Cite-popup HTML fetch & parse (5 text formats) | ✅ working live |
| Export formats (BibTeX / EndNote / RefMan / RefWorks) via `--browser` | ✅ **all 9 formats verified live** |
| Playwright browser backend with cookie persistence | ✅ working |
| Captcha: manual-solve once, cookies cached | ✅ working |
| `auth status` / `auth reset` subcommands | ✅ working |
| CLI (`cite`, plain + JSON output, `--format`, `--limit`, `-o`, `--browser`) | ✅ |
| Batch mode (`-f titles.txt`) | ⏳ planned |
| Interactive picker (`-i`) | ⏳ planned |
| Clipboard (`-c`) | ⏳ planned |
| SQLite cache keyed by `cluster_id` | ⏳ planned |
| SerpAPI fallback backend | ⏳ planned |

## Testing

```bash
pytest tests/ -v
```

All parsing/fetching logic is covered by unit tests using a saved cite-popup HTML fixture — no live Google Scholar calls in CI.

## Known limitations (current MVP)

- **RefWorks isn't a citation string** — Scholar's RefWorks export is a redirect to
  `refworks.com/express`. The tool emits that URL instead; open it in a browser
  logged into RefWorks to complete the import.
- **Scholar rate-limits plain HTTP aggressively**. Use `--browser` for reliable runs;
  the default tries the scholarly path first and falls back to the browser when blocked.
- **`--limit` caps the first result page** (typically ≤10). No pagination yet.

## Project layout

```
scholar-cite/
├── docs/
│   ├── design.md              # full design spec
│   └── test-run-2026-04-19.md # first live test results
├── src/scholar_cite/
│   ├── cli.py                 # Typer entry point (cite, auth status, auth reset)
│   ├── search.py              # scholarly path + browser fallback orchestration
│   ├── citation.py            # cite-popup parser + 9-format assembly
│   ├── browser_fetcher.py     # Playwright headful browser w/ cookie persistence
│   ├── models.py              # Paper, CitationSet dataclasses
│   └── __main__.py
├── tests/
│   ├── fixtures/
│   │   └── cite_popup_sample.html
│   └── test_citation.py
├── pyproject.toml
└── README.md
```

## License

MIT (planned).
