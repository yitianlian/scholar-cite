# Architecture

A map of the current codebase. For the design decisions and rationale that led
to this shape, see [`design.md`](./design.md).

## Module map

```
src/scholar_cite/
├── cli.py             CLI entry point. Typer app with two subcommands:
│                      `cite` (search + fetch) and `auth` (cookie cache).
│                      Exit codes: 0 OK, 2 no results, 4 partial with --strict.
│
├── search.py          Orchestration. Two paths:
│                       - _search_via_browser  (default): Playwright end-to-end.
│                       - _search_via_scholarly (opt-in): scholarly HTTP.
│                      _is_scholar_blocked() narrows which exceptions are treated
│                      as rate-limiting vs genuine bugs (the latter propagate).
│                      _parse_search_page() pulls cluster_ids + source URLs from
│                      Scholar's results page for the browser path.
│
├── citation.py        Cite-popup parser and 9-format assembly.
│                       - parse_cite_html() extracts 5 text formats + 4 export
│                         links from Scholar's /output=cite HTML.
│                       - fetch_citation_set() hits each export URL, returning
│                         (CitationSet, errors: dict[str, str]).
│                       - _clean_refworks() turns Scholar's JS-redirect stub
│                         into a usable import URL.
│
├── browser_fetcher.py Playwright session wrapper. Opens a headful Chromium,
│                      applies light stealth patches, lets the user solve one
│                      captcha, persists cookies to
│                      ~/.cache/scholar-cite/cookies.json. Two fetch methods:
│                       - fetch(url)      → page.goto, good for HTML pages.
│                       - fetch_api(url)  → BrowserContext.request, used for
│                                           export URLs (avoids the download
│                                           prompt that page.goto triggers on
│                                           text/plain responses).
│                      cookies_status() / clear_cookies() back the `auth`
│                      subcommands; cookies_status is hardened against corrupt
│                      JSON so `auth status` never crashes.
│
├── ranking.py         Source-quality ranking. Hostname → score table
│                      classifies result clusters. rank_papers() is a stable
│                      sort: trusted venues (CVF / ACL / NeurIPS / IEEE / ACM /
│                      Springer / arXiv) float up, known-bad mirrors sink,
│                      unknown stays in Scholar's original order.
│
└── models.py          Dataclasses and type aliases.
                        - FormatName / ALL_FORMATS / TEXT_FORMATS /
                          EXPORT_FORMATS enumerations.
                        - CitationSet (9 string fields).
                        - Paper (cluster_id, title, authors, year, venue, doi,
                          source_url, citations, citation_errors).
```

## One-query lifecycle (browser path, default)

```
user: scholar-cite cite "Attention Is All You Need" --format all
           │
           ▼
 cli.cite → search.search(query, limit, no_browser=False)
           │
           ▼
 search._search_via_browser
  ├─ BrowserFetcher.__enter__
  │     launches headful Chromium, loads cached cookies
  ├─ bf.fetch(SCHOLAR_SEARCH_URL + query)
  │     ├─ if anti-bot page → wait for user to solve
  │     └─ returns rendered HTML
  ├─ _parse_search_page(html) → list[Paper] (10 candidates, metadata only)
  ├─ ranking.rank_papers(candidates)[:limit]
  └─ for each ranked Paper:
         citation.fetch_citation_set(cluster_id, fetch)
           ├─ bf.fetch(cite_url)            → HTML with 5 text + 4 export links
           ├─ parse_cite_html(html)         → CitationSet (text fields)
           └─ for each export link:
                  bf.fetch_api(link.url)    → raw BibTeX / EndNote / RIS / RefWorks
                  (fills the remaining fields; records per-format errors)
 BrowserFetcher.__exit__
  └─ persists cookies for the next invocation
           │
           ▼
 cli renders plain or JSON, prints stderr warnings for any missing formats,
 exits 0 (or 4 if --strict and anything is missing).
```

## One-query lifecycle (scholarly path, `--no-browser`)

```
cli.cite → search.search(query, limit, no_browser=True)
           │
           ▼
 search._search_via_scholarly
  ├─ scholarly.search_pubs(query)      → iterator of pub dicts
  ├─ _paper_from_scholarly_pub(pub)    → Paper (pulls source_url from pub_url)
  ├─ ranking.rank_papers(...)[:limit]
  └─ _fill_via_scholarly(papers)
         for each paper:
           fetch_citation_set(cluster_id, via scholarly's Navigator._get_page)
             - on _is_scholar_blocked(exc): record per-format error, continue
             - on any other exception: RE-RAISE — bugs are not masked
```

## Exception policy

| Situation                             | Behaviour                              |
| ------------------------------------- | -------------------------------------- |
| `MaxTriesExceededException`           | `_is_scholar_blocked` → record error   |
| HTTP 403 / 429 / 503                  | `_is_scholar_blocked` → record error   |
| `CaptchaError` / `ScholarBlockedError`| `_is_scholar_blocked` → record error   |
| `ValueError` / `KeyError` / `TypeError`| **propagate** (real bug)              |
| `ParseError`                          | **propagate** (Scholar HTML changed)   |

## Format-field flow

```
CitationSet = { mla, apa, chicago, harvard, vancouver,       ← from /output=cite HTML
                bibtex, endnote, refman, refworks }          ← from 4 export URLs

Paper.citation_errors: dict[format → reason]
  key present  → that field was requested, fetch failed, reason recorded
  key absent   → field succeeded or wasn't requested
```

Plain text output: `[MISSING: <reason>]` inline. JSON output: top-level
`citation_errors` object per paper. Stderr: one warning line per paper that
has any missing field.

## Cache layout

```
~/.cache/scholar-cite/cookies.json   Playwright browser cookies
                                      ({"saved_at": unix_ts, "cookies": [...]})
```

Read on every BrowserFetcher startup; written on clean shutdown. `auth status`
inspects this file; `auth reset` deletes it.

## What's NOT implemented yet

See `README.md` > "What's implemented vs planned". Known gaps: batch mode
(`-f titles.txt`), interactive picker (`-i`), clipboard (`-c`), SQLite
citation cache, SerpAPI fallback backend.
