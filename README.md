# scholar-cite

> A Python CLI that searches **Google Scholar** by paper title and returns all nine citation formats — `BibTeX`, `EndNote`, `RefMan` (RIS), `RefWorks`, `MLA`, `APA`, `Chicago`, `Harvard`, `Vancouver`.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-31%20passing-brightgreen.svg)](#running-the-tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Status:** MVP. The nine formats are verified end-to-end against live Google
Scholar via a Playwright browser backend. See
[`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md) for the evidence and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the code is organised.

---

## Table of contents

1. [Why this tool exists](#why-this-tool-exists)
2. [Install](#install)
3. [Quick start](#quick-start)
4. [Usage](#usage)
5. [How it works](#how-it-works)
6. [Missing-format handling](#missing-format-handling)
7. [Source-quality ranking](#source-quality-ranking)
8. [What's implemented vs planned](#whats-implemented-vs-planned)
9. [Running the tests](#running-the-tests)
10. [Project layout](#project-layout)
11. [Documentation index](#documentation-index)
12. [License](#license)

---

## Why this tool exists

Google Scholar's "Cite" popup produces nine clean citation formats for any
paper. Getting them in bulk is painful though: there's no public API, the HTML
surface is rate-limited within a request or two, and export URLs serve
`text/plain` downloads that don't play well with either `requests` or a
headless browser. `scholar-cite` wraps all of that so you can type:

```bash
scholar-cite cite "Attention Is All You Need" --format bibtex
```

…and get a working BibTeX entry.

## Install

```bash
git clone https://github.com/yitianlian/scholar-cite
cd scholar-cite
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
playwright install chromium           # ~150 MB, one-time
```

Python 3.10 or later is required (tested on 3.10 – 3.14).

## Quick start

```bash
# Default: browser path, BibTeX on stdout
scholar-cite cite "Attention Is All You Need"

# All nine formats
scholar-cite cite "Attention Is All You Need" --format all
```

A Chromium window pops up on the first run. If Scholar asks "Please show
you're not a robot", click through the challenge once — cookies are cached at
`~/.cache/scholar-cite/cookies.json` and silently reused on later runs.

## Usage

```bash
# Single paper → BibTeX on stdout (default format)
scholar-cite cite "<paper title>"

# Pick the formats you want (comma-separated or 'all')
scholar-cite cite "..." --format all
scholar-cite cite "..." --format apa,mla,bibtex

# Cap or expand the candidate pool (Scholar may have multiple clusters)
scholar-cite cite "..." --limit 3

# Machine-readable output (includes citation_errors on partial results)
scholar-cite cite "..." --format all --json

# Write the output to a file instead of stdout
scholar-cite cite "..." --format bibtex -o refs.bib

# Skip the browser and use scholarly's HTTP backend only — no silent fallback
scholar-cite cite "..." --no-browser

# Fail loudly (exit code 4) if any requested format is missing
scholar-cite cite "..." --format all --strict

# Inspect or clear the browser's cookie cache
scholar-cite auth status
scholar-cite auth reset
```

### Exit codes

| Code | Meaning                                                           |
| ---- | ----------------------------------------------------------------- |
| 0    | Success (even if some formats were missing — they're reported)    |
| 2    | Search returned no results                                        |
| 4    | `--strict` set and at least one requested format was missing      |

### Example output (`--format all`)

```
[1] Attention is all you need
    A Vaswani — proceedings.neurips.cc
    cluster_id: 5Gohgn6QFikJ
    ──────────────────────────────────────────────────
    MLA:       Vaswani, Ashish, et al. "Attention is all you need." …
    APA:       Vaswani, A., Shazeer, N., Parmar, N., … (2017). …
    Chicago:   …
    Harvard:   …
    Vancouver: …
    Bibtex:
        @article{vaswani2017attention,
          title={Attention is all you need},
          author={Vaswani, Ashish and Shazeer, Noam and …},
          …
        }
    Endnote:
        %0 Journal Article
        …
    Refman:
        TY  - JOUR
        …
    Refworks:
        # Google Scholar's RefWorks export is an external redirect.
        # Import URL:
        http://www.refworks.com/express?sid=google&…
```

## How it works

`scholar-cite` has two backends with very different reliability profiles:

1. **Playwright browser (default, most reliable).** A real headful Chromium
   navigates Scholar's search page, cite popup, and export URLs. Light stealth
   patches reduce anti-bot flags; if Scholar still asks for a captcha, the
   user solves it once and the cookies carry the session for days.
2. **scholarly HTTP (`--no-browser`, opt-in).** The [`scholarly`](https://scholarly.readthedocs.io/)
   library's plain HTTP session. Fast when it works, but Scholar blocks it
   aggressively. This path does **not** silently fall back to the browser —
   failures surface per format instead.

Both paths converge on the same pipeline inside `search.py`, and both rank
candidate clusters by source quality before applying `--limit` (see below).
For the gritty details, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Missing-format handling

When Scholar returns a format incompletely (some clusters are missing export
links, some URLs 403, etc.), `scholar-cite` never drops it silently:

- **Plain-text** output renders `[MISSING: <reason>]` inline for each failed
  format.
- **JSON** output adds a `citation_errors` field per paper.
- **Stderr** gets a short warning summary listing every paper with missing
  formats.
- `--strict` elevates this to a non-zero exit code (4) for scripts that
  can't afford partial results.

## Source-quality ranking

Google Scholar often indexes a paper multiple times (arXiv preprint, official
conference version, third-party mirrors). Citation quality varies wildly —
some mirrors produce metadata with reversed author order, fabricated volume
numbers, and mangled venue strings. `scholar-cite` ranks candidates by host:

| Tier            | Example hosts                                           |
| --------------- | ------------------------------------------------------- |
| Trusted venues  | `openaccess.thecvf.com`, `aclanthology.org`, `proceedings.neurips.cc`, `proceedings.mlr.press`, `ieeexplore.ieee.org`, `dl.acm.org`, `nature.com` |
| Preprints       | `arxiv.org`, `biorxiv.org`                              |
| Unknown         | Everything else (kept in Scholar's original order)      |
| Known low-quality| `sandbox.getindico.io`, `scholar.google.com` self-refs |

The real-world consequence: searching "Deep Residual Learning for Image
Recognition" with `--limit 1` used to land on a sandbox indico mirror that
produced `@inproceedings{kaiming2016deep, ..., volume={34}}`. With ranking on,
the same query lands on the clean cluster `he2016deep` from the official CVPR
host. See `tests/test_ranking.py::test_rank_papers_handles_resnet_style_scenario`.

## What's implemented vs planned

| Feature                                                        | Status |
| -------------------------------------------------------------- | ------ |
| Scholar search (browser + scholarly paths)                     | ✅     |
| `cluster_id` extraction                                        | ✅     |
| Cite-popup HTML parse (five text formats)                      | ✅     |
| Four export formats via `BrowserContext.request`               | ✅     |
| Playwright cookie persistence / captcha recovery               | ✅     |
| Source-quality ranking of candidate clusters                   | ✅     |
| `auth status` / `auth reset` subcommands                       | ✅     |
| `--format`, `--limit`, `-o`, `--json`, `--no-browser`, `--strict`| ✅   |
| Batch mode (`-f titles.txt`)                                   | ⏳ planned |
| Interactive picker (`-i`)                                      | ⏳ planned |
| Clipboard (`-c`)                                               | ⏳ planned |
| SQLite cache keyed by `cluster_id`                             | ⏳ planned |
| SerpAPI fallback backend                                       | ⏳ planned |

## Running the tests

```bash
pip install -e ".[dev]"
pytest -q
```

All parsing and fetching logic is covered by 31 unit tests. No live Google
Scholar calls in CI — tests use a saved HTML fixture and fake fetchers.

```bash
ruff check src/ tests/      # lint
ruff format src/ tests/     # format
```

## Project layout

```
scholar-cite/
├── LICENSE                    MIT
├── CHANGELOG.md               Release notes
├── README.md                  ← you are here
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md        Current code map (start here to hack)
│   ├── design.md              Original design spec (planning doc)
│   └── test-run-2026-04-19.md Live end-to-end evidence
├── examples/
│   └── demo_five_papers.py    Fetches BibTeX for 5 classic ML papers
├── src/scholar_cite/
│   ├── cli.py                 Typer CLI (`cite`, `auth status`, `auth reset`)
│   ├── search.py              Browser + scholarly orchestration
│   ├── citation.py            Cite-popup parser + 9-format assembly
│   ├── browser_fetcher.py     Playwright session with cookie persistence
│   ├── ranking.py             Source-quality hostname ranking
│   └── models.py              Paper / CitationSet dataclasses
└── tests/
    ├── fixtures/
    │   └── cite_popup_sample.html
    ├── test_browser_fetcher.py
    ├── test_citation.py
    ├── test_cli.py
    ├── test_ranking.py
    └── test_search.py
```

## Documentation index

| Doc | What you'll find there |
| --- | ---------------------- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module map, one-query lifecycle, exception policy, cache layout |
| [`docs/design.md`](docs/design.md) | Original 14-section design specification (planning-era snapshot) |
| [`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md) | Live end-to-end evidence for the 9-format pipeline |
| [`CHANGELOG.md`](CHANGELOG.md) | Release-level summary of what changed and why |

## License

[MIT](LICENSE). Google Scholar's HTML structure and Terms of Service govern
your use of the upstream data.
