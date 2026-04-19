# scholar-cite

A Python CLI that searches **Google Scholar** by paper title and returns the 9 citation formats (MLA, APA, Chicago, Harvard, Vancouver, BibTeX, EndNote, RefMan, RefWorks).

> **Status**: MVP — search + text-format extraction verified against live Google Scholar for a real paper (see [`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md)). Export formats covered by parser unit tests; live verification pending the captcha-recovery flow. Full design in [`docs/design.md`](docs/design.md).

## Install (dev)

```bash
git clone <this-repo>
cd scholar-cite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.10+ required (tested on 3.14).

## Usage

```bash
# Single title → BibTeX on stdout (default)
scholar-cite "Attention Is All You Need"

# All 9 formats
scholar-cite "Attention Is All You Need" --format all

# Specific subset (comma-separated)
scholar-cite "Attention Is All You Need" --format apa,mla,bibtex

# Cap candidates
scholar-cite "Attention Is All You Need" --limit 3

# JSON output (for scripting)
scholar-cite "Attention Is All You Need" --format all --json

# Write to file
scholar-cite "Attention Is All You Need" --format bibtex -o refs.bib
```

## Example output

```
[1] Attention is all you need
    A Vaswani — 2017 — Advances in neural …
    cluster_id: 5Gohgn6QFikJ
    ──────────────────────────────────────────────────
    MLA:     Vaswani, Ashish, et al. "Attention is all you need." ...
    APA:     Vaswani, A., Shazeer, N., ... (2017). Attention is all you need. ...
    Chicago: ...
    Harvard: ...
    Vancouver: ...
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
| Scholar search | ✅ working |
| `cluster_id` extraction | ✅ working |
| Cite-popup HTML fetch & parse | ✅ working (5 text formats verified live) |
| Export-link parsing (BibTeX/EndNote/RefMan/RefWorks) | ✅ parser unit-tested; live fetch blocked by Scholar on first run |
| CLI (plain + JSON output, `--format`, `--limit`, `-o`) | ✅ |
| Batch mode (`-f titles.txt`) | ⏳ planned |
| Interactive picker (`-i`) | ⏳ planned |
| Clipboard (`-c`) | ⏳ planned |
| SQLite cache | ⏳ planned |
| Playwright captcha recovery | ⏳ planned |
| SerpAPI fallback backend | ⏳ planned |

## Testing

```bash
pytest tests/ -v
```

All parsing/fetching logic is covered by unit tests using a saved cite-popup HTML fixture — no live Google Scholar calls in CI.

## Known limitations (current MVP)

- Google Scholar aggressively rate-limits. A run of more than a couple of papers will likely hit 403 / `MaxTriesExceeded`. The captcha-recovery flow and SerpAPI fallback (both in the design doc) address this.
- The `--limit` flag currently caps Scholar's first result page. No pagination yet.

## Project layout

```
scholar-cite/
├── docs/
│   ├── design.md              # full design spec
│   └── test-run-2026-04-19.md # first live test results
├── src/scholar_cite/
│   ├── cli.py                 # Typer entry point
│   ├── search.py              # search orchestration
│   ├── citation.py            # cite-popup parser + export fetching
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
