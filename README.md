# scholar-cite

[English](README.md) · [简体中文](README.zh-CN.md)

> A Python CLI that searches **Google Scholar** by paper title and returns all nine citation formats — `BibTeX`, `EndNote`, `RefMan` (RIS), `RefWorks`, `MLA`, `APA`, `Chicago`, `Harvard`, `Vancouver`.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-48%20passing-brightgreen.svg)](#running-the-tests)
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
8. [Claude Code & Codex integration](#claude-code--codex-integration)
9. [What's implemented vs planned](#whats-implemented-vs-planned)
10. [Running the tests](#running-the-tests)
11. [Project layout](#project-layout)
12. [Documentation index](#documentation-index)
13. [License](#license)

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

Installing always takes **two steps**:

1. Install the Python package (pulls every Python dependency in automatically).
2. Download the Chromium browser binary that Playwright drives (~150 MB, one-off).

Python 3.10 or later is required (tested on 3.10 – 3.14).

### FAQ before you install

**Can I just `pip install scholar-cite`?**
Yes — `scholar-cite` is on PyPI as of v0.1.0:
<https://pypi.org/project/scholar-cite/>. That's option A below.

**Do I need an API key or token?**
**No.** Google Scholar has no public API. The tool drives a real browser and
parses Scholar's own HTML; nothing authenticates. You may need to solve a
captcha once in the visible browser window, after which cookies carry the
session for days.

**Do I have to install dependencies manually?**
No. `pip` / `pipx` reads `pyproject.toml` and pulls in every Python dep
automatically (`typer`, `scholarly`, `requests`, `beautifulsoup4`, `lxml`,
`playwright`). The *only* manual step is step 2 — downloading the Chromium
binary. `pip` can't ship 150 MB of browser inside a Python wheel, so Playwright
exposes `playwright install chromium` to fetch it separately.

**What is Playwright and why does scholar-cite need it?**
[Playwright](https://playwright.dev/python/) is a Python library that drives a
real Chromium browser programmatically. We use it because:
- Google Scholar **403s plain HTTP requests** within a request or two, even
  through the `scholarly` library.
- Scholar **detects headless browsers** and shows a "please show you're not a
  robot" page to them.
- A real headful Chromium with light stealth patches (hide
  `navigator.webdriver` etc.) reliably survives. When Scholar does show a
  captcha, it appears in the visible window and you can click through it
  once; cookies are cached at `~/.cache/scholar-cite/cookies.json` and reused
  silently for subsequent runs.

We do not use Selenium, pyppeteer, or plain `requests` for the main path.
See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit
together.

### Option A — install from PyPI (recommended)

```bash
pipx install scholar-cite
playwright install chromium
```

`pipx` isolates scholar-cite into its own virtualenv and puts the
`scholar-cite` binary on your `PATH`. Plain `pip install scholar-cite`
works too; you manage the venv yourself.

To track the bleeding edge on `main` instead of the latest PyPI release,
use `pipx install git+https://github.com/yitianlian/scholar-cite.git`.

### Option B — build a wheel locally and install it

Useful if you want a single `.whl` you can copy to other machines.

```bash
git clone https://github.com/yitianlian/scholar-cite.git
cd scholar-cite
pip install build
python -m build                     # produces dist/scholar_cite-0.1.0-*.whl

pipx install dist/scholar_cite-0.1.0-py3-none-any.whl
playwright install chromium
```

### Option C — editable install for development

```bash
git clone https://github.com/yitianlian/scholar-cite.git
cd scholar-cite
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"             # includes pytest + ruff
playwright install chromium
pytest -q                           # 38 tests, all offline
```

### First-run behaviour (all options)

The first `scholar-cite cite "..."` call opens a visible Chromium window. If
Scholar shows "Please show you're not a robot", click through the challenge
once. The tool waits up to 5 minutes, harvests the resulting cookies to
`~/.cache/scholar-cite/cookies.json`, and reuses them silently on later runs.
Run `scholar-cite auth status` any time to see the cached cookie state, and
`scholar-cite auth reset` to force a fresh login.

## Quick start

```bash
# Default: browser path, BibTeX on stdout
scholar-cite cite "Attention Is All You Need"

# All nine formats
scholar-cite cite "Attention Is All You Need" --format all
```

See [install](#install) above — the first-run captcha note applies.

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

## Claude Code & Codex integration

This repo ships a ready-to-use agent skill so that **Claude Code** or
**OpenAI Codex CLI** can call the `scholar-cite` CLI on your behalf when you
ask for a citation, without you having to explain the tool every time.

### Where the skill lives

Both agent runtimes auto-discover project-scoped skills from their own
directory. The content is identical, so the repo keeps a single source in
`.claude/skills/` and symlinks it for Codex:

```
scholar-cite/
├── .claude/
│   └── skills/
│       └── scholar-cite/
│           ├── SKILL.md     ← the real file (Claude Code reads here)
│           └── flags.md
└── .agents/
    └── skills/
        └── scholar-cite  →  ../../.claude/skills/scholar-cite   (symlink)
                           (Codex CLI reads here)
```

### How to "install" the skill

Nothing to install. Both agents scan for skills when a session starts in
this directory. Just clone the repo and open it in your agent of choice:

| Agent | Skill root it looks at | What you do |
| ----- | ---------------------- | ----------- |
| Claude Code | `.claude/skills/<name>/SKILL.md` (project), `~/.claude/skills/<name>/SKILL.md` (user) | Open the repo in Claude Code. The skill is auto-discovered; it's listed in the available-skills section and Claude invokes it via the `Skill` tool when your request matches the description. |
| Codex CLI | `.agents/skills/<name>/SKILL.md` (project), `~/.agents/skills/<name>/SKILL.md` (user) | Open the repo in Codex CLI (`codex` in this directory). Skills are scanned at session start and Codex also watches for changes at runtime. |

**To make the skill globally available** (every project, not just this one):

```bash
# Claude Code
ln -s "$PWD/.claude/skills/scholar-cite" "$HOME/.claude/skills/scholar-cite"

# Codex CLI
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/.claude/skills/scholar-cite" "$HOME/.agents/skills/scholar-cite"
```

The CLI itself still needs to be on `PATH` — see the [Install](#install)
section above.

### What the skill tells the agent

- When to invoke (trigger phrases in English and Chinese).
- When *not* to use it (arXiv preprints → `arxiv` skill; headless CI → it
  won't work; users asking for PDFs → this tool doesn't fetch PDFs).
- The common invocations and their flags.
- First-run captcha behaviour and the 5-minute wait.
- A troubleshooting table for the six recurring failure modes.
- The exit-code contract so the agent can branch correctly on failure.

Read [`.claude/skills/scholar-cite/SKILL.md`](.claude/skills/scholar-cite/SKILL.md)
(and [`flags.md`](.claude/skills/scholar-cite/flags.md) for the full flag
reference and a Python-API snippet) to see exactly what the agent is
taught.

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
| [`docs/test-run-2026-04-19.md`](docs/test-run-2026-04-19.md) | First live 9-format pipeline run |
| [`docs/e2e-verification.md`](docs/e2e-verification.md) | Post-fix E2E evidence + wheel install smoke test |
| [`.claude/skills/scholar-cite/SKILL.md`](.claude/skills/scholar-cite/SKILL.md) | Agent skill — auto-discovered by Claude Code from `.claude/skills/` and by Codex CLI from `.agents/skills/` (symlinked to the same file); teaches the agent when and how to call the CLI |
| [`.claude/skills/scholar-cite/flags.md`](.claude/skills/scholar-cite/flags.md) | Flag reference + Python API snippet referenced by the skill |
| [`CHANGELOG.md`](CHANGELOG.md) | Release-level summary of what changed and why |
| [`PUBLISHING.md`](PUBLISHING.md) | How to cut a release (version bump, `twine check`, TestPyPI dry-run, real PyPI upload, GitHub release) |

## License

[MIT](LICENSE). Google Scholar's HTML structure and Terms of Service govern
your use of the upstream data.
