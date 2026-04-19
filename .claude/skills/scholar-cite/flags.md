# `scholar-cite` flag reference

Full flag list for the `cite` subcommand. Read this when you need a non-default
flag; for the common path see `SKILL.md`.

## `cite` subcommand

```
scholar-cite cite QUERY [OPTIONS]
```

`QUERY` is the paper title, free text. Scholar's own search tolerance applies —
close is good enough.

| Flag | Type | Default | Purpose |
| ---- | ---- | ------- | ------- |
| `--format`, `-F` | comma-separated string | `bibtex` | One or more of `mla`, `apa`, `chicago`, `harvard`, `vancouver`, `bibtex`, `endnote`, `refman`, `refworks`, or the literal string `all`. Unknown names error out. |
| `--limit`, `-n` | int | `10` | Max candidates to return. Scholar often has multiple clusters per paper; this caps them after source-quality ranking is applied. |
| `--json` | bool | false | Emit JSON. Output shape: `list[{cluster_id, title, authors, year, venue, doi, citations, citation_errors?}]`. |
| `--output`, `-o` | path | stdout | Write rendered output to a file instead of stdout. Progress logs stay on stderr. `--strict` + missing formats = file NOT written. |
| `--no-browser` | bool | false | Skip Playwright. Uses the `scholarly` HTTP backend only, with **no silent fallback** to browser. Scholar blocks it frequently; prefer the default. |
| `--strict` | bool | false | Exit code 4 if any requested format is missing. Refuses to write stdout or `-o` on partial results. |

## `auth` subcommands

| Command | What it does |
| ------- | ------------ |
| `scholar-cite auth status` | Prints the path + metadata of the cached cookie file. Robust against corrupt JSON — returns an `error` field instead of raising. |
| `scholar-cite auth reset` | Deletes the cookie cache. Next run will trigger a fresh captcha prompt in the browser window. |

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Success. Partial results may still be present; see stderr for warnings. |
| 2 | No search results. |
| 4 | `--strict` set and at least one requested format was missing. Nothing written to stdout or `-o`. |

## Environment

- No API keys required.
- Cookies cached at `$XDG_CACHE_HOME/scholar-cite/cookies.json` (falls back to
  `~/.cache/scholar-cite/cookies.json`).
- Chromium binary expected at Playwright's default location — installed via
  `playwright install chromium` (one-off, ~150 MB).

## Python 3 API (when CLI isn't enough)

For custom workflows (batch, picker, deduping) you can import the internals:

```python
from scholar_cite.browser_fetcher import BrowserFetcher
from scholar_cite.citation import fetch_citation_set
from scholar_cite.ranking import rank_papers
from scholar_cite.search import SCHOLAR_SEARCH_URL, _parse_search_page
from urllib.parse import quote_plus

with BrowserFetcher(headless=False) as bf:
    def fetch(url, timeout=30.0):
        if "scholar.googleusercontent.com" in url or url.endswith(
            (".bib", ".enw", ".ris", ".rfw")
        ):
            return bf.fetch_api(url, timeout=timeout)
        return bf.fetch(url, timeout=timeout, settle_ms=500)

    for query in queries:
        html = bf.fetch(
            SCHOLAR_SEARCH_URL.format(query=quote_plus(query)),
            timeout=45.0, settle_ms=600,
        )
        paper = rank_papers(_parse_search_page(html))[0]
        citations, errors = fetch_citation_set(paper.cluster_id, fetch=fetch)
        print(citations.bibtex)
```

A runnable version is in `examples/demo_five_papers.py`.
