---
name: scholar-cite
description: Use when the user wants citation strings (BibTeX, APA, MLA, Chicago, Harvard, Vancouver, EndNote, RefMan, RefWorks) from Google Scholar for a paper given its title. Triggers on phrases like "get BibTeX for <paper>", "find citation for <paper>", "cite this paper", "MLA entry for <title>", "fetch from Scholar", "生成引用", "Scholar 引用格式". Invokes the `scholar-cite` CLI that lives in this repo.
---

# Using `scholar-cite`

`scholar-cite` is a CLI in this repo that takes a paper title, drives a real
Chromium via Playwright to search Google Scholar, and returns all nine
citation formats. Use it whenever the user needs citation strings from
Scholar.

## When to use this skill

- User names a paper and wants its BibTeX / APA / MLA / Chicago / Harvard /
  Vancouver / EndNote / RefMan / RefWorks entry.
- User wants to build a `.bib` file from paper titles.
- User asks to "cite this paper" / "get the citation for X" and the target is
  a published paper (not an arXiv preprint — for arXiv metadata use the
  `arxiv` skill instead).

## When NOT to use it

- User wants the paper PDF or full text (this tool does not download PDFs).
- User wants preprint metadata only and doesn't care about the venue's
  canonical citation — `arxiv` skill is faster.
- User wants cross-database citation counts — use `semantic-scholar` skill.
- User is running in an environment that cannot open a visible browser
  window (SSH-only / headless CI). The default path needs a headful
  Chromium. `--no-browser` exists but Scholar will almost always block it.

## Quick check before running

Confirm the CLI is available in the current environment:

```bash
scholar-cite --version 2>/dev/null || scholar-cite --help | head -3
```

If that errors, the user needs to install it. Point them at the `Install`
section of `README.md` (this repo). Two steps total:

```bash
pipx install git+ssh://git@github.com/yitianlian/scholar-cite.git
playwright install chromium
```

## Most common invocations

```bash
# Single paper → BibTeX on stdout (the default format)
scholar-cite cite "Attention Is All You Need"

# All nine formats at once
scholar-cite cite "Attention Is All You Need" --format all

# Specific subset, comma-separated
scholar-cite cite "Attention Is All You Need" --format apa,mla,bibtex

# JSON output — the right choice when you need to post-process or collect
# citations across many papers in one script
scholar-cite cite "Attention Is All You Need" --format all --json

# Write to file. With -o the tool emits only progress logs on stderr.
scholar-cite cite "Attention Is All You Need" --format bibtex -o refs.bib

# Fail loudly (exit code 4) if any requested format is missing. --strict
# refuses to write anything at all on partial results, so automation can
# trust that a zero exit + existing file means "everything the user asked
# for is present".
scholar-cite cite "Attention Is All You Need" --format all --strict
```

Full flag reference — read only when you need a non-default flag:
[flags.md](flags.md)

## Output shape

Plain text (default): each candidate paper is numbered `[1]`, `[2]` …
with a header block (title, first author, year, venue, `cluster_id`), a
separator, then the requested citation formats. Missing formats render
inline as `[MISSING: <reason>]`.

JSON (`--json`): an array of objects, one per paper, with keys
`cluster_id`, `title`, `authors`, `year`, `venue`, `doi`, `citations`, and
optionally `citation_errors` when a requested format failed. The `citations`
dict keys are the nine format names verbatim.

## Things that will happen on a first run

1. A Chromium window opens (Playwright headful mode). **Do not close it** —
   the tool is using it.
2. If Scholar shows "Please show you're not a robot", the user must solve
   the challenge in that window within 5 minutes. The command waits.
3. Cookies are persisted to `~/.cache/scholar-cite/cookies.json`. Subsequent
   runs reuse them and skip the challenge for roughly a week.

If the user reports being stuck at the captcha page or the command timed
out without resolution, tell them to run `scholar-cite auth reset` and try
again.

## Troubleshooting playbook

| Symptom | What to do |
| ------- | ---------- |
| `scholar-cite: command not found` | Point at the install instructions in `README.md`. Verify `pipx` or `pip` install succeeded and the venv / pipx bin is on `PATH`. |
| First run hangs on "Anti-bot page detected" | The user needs to click through the challenge in the visible browser. Don't kill the process. |
| Repeated 403s / captcha loops | `scholar-cite auth reset` → rerun. Wait 10–30 min if Scholar is aggressively rate-limiting the IP. |
| `MISSING: …` next to some formats | Not fatal. Scholar's cluster didn't carry that format. Try `--limit 3` to see alternative clusters; usually at least one has the format you want. |
| Wrong author order / fabricated `volume={34}` in BibTeX | User hit a low-quality Scholar cluster. The tool already ranks trusted hosts first, but if the only clusters Scholar has are mirrors, the output can be dirty. Run with `--limit 5` and let the user pick manually from the candidates. |
| `playwright install chromium` missing | Standard error on a fresh machine. Tell the user to run it once; it's a ~150 MB one-time download. |
| `--no-browser` run fails with `MaxTriesExceeded` | Expected — Scholar blocked the scholarly HTTP backend. Switch back to the default (drop `--no-browser`). |

## What the tool does NOT do

- Does not download PDFs.
- Does not deduplicate across a batch (yet — planned).
- Does not implement an interactive picker for ambiguous titles (yet —
  planned). For now pass `--limit N` and let the user choose from the list.
- Does not provide a batch mode (`-f titles.txt`) — also planned. For
  multi-paper workflows in the meantime, either loop the CLI in shell, or
  import the Python API directly; see `examples/demo_five_papers.py` in
  this repo for a working one-browser-many-queries pattern.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0    | Success. Missing-format warnings may still appear on stderr. |
| 2    | No search results. |
| 4    | `--strict` set and at least one requested format was missing. Nothing was written to stdout or `-o`. |
