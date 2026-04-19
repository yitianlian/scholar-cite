"""Typer CLI for scholar-cite."""
from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from scholar_cite.models import ALL_FORMATS, Paper

app = typer.Typer(
    add_completion=False,
    help="Fetch Google Scholar citation formats by paper title.",
    no_args_is_help=True,
)

auth_app = typer.Typer(
    help="Manage the cached browser cookies used for the Playwright fallback.",
    no_args_is_help=True,
)
app.add_typer(auth_app, name="auth")

# Exit codes — kept narrow for shell-level scripting.
EXIT_OK = 0
EXIT_NO_RESULTS = 2
EXIT_PARTIAL = 4  # Some requested formats were missing; see stderr.


def _parse_formats(raw: str) -> list[str]:
    if raw == "all":
        return list(ALL_FORMATS)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in ALL_FORMATS]
    if unknown:
        raise typer.BadParameter(f"Unknown format(s): {', '.join(unknown)}")
    return names


def _fmt_label(fmt: str) -> str:
    return fmt.upper() if fmt in ("mla", "apa") else fmt.capitalize()


def _render_plain(papers: list[Paper], formats: list[str]) -> str:
    if not papers:
        return "(no results)\n"
    lines: list[str] = []
    for i, p in enumerate(papers, 1):
        lines.append(f"[{i}] {p.title}")
        meta = [m for m in (p.first_author, str(p.year) if p.year else "", p.venue) if m]
        if meta:
            lines.append("    " + " — ".join(meta))
        lines.append(f"    cluster_id: {p.cluster_id}")
        lines.append("    " + "—" * 50)
        for fmt in formats:
            val = getattr(p.citations, fmt, "")
            label = _fmt_label(fmt)
            if val:
                if "\n" in val or len(val) > 90:
                    lines.append(f"    {label}:")
                    for row in val.splitlines() or [val]:
                        lines.append(f"        {row}")
                else:
                    lines.append(f"    {label:<9} {val}")
            else:
                reason = p.citation_errors.get(fmt, "not returned by Scholar")
                lines.append(f"    {label:<9} [MISSING: {reason}]")
        lines.append("")
    return "\n".join(lines)


def _render_json(papers: list[Paper], formats: list[str]) -> str:
    out = []
    for p in papers:
        citations = {f: getattr(p.citations, f, "") for f in formats}
        errors = {f: p.citation_errors[f] for f in formats if f in p.citation_errors}
        entry = {
            "cluster_id": p.cluster_id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "venue": p.venue,
            "doi": p.doi,
            "citations": citations,
        }
        if errors:
            entry["citation_errors"] = errors
        out.append(entry)
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


def _summarize_missing(papers: list[Paper], formats: list[str]) -> list[str]:
    """One line per paper that is missing one or more requested formats."""
    issues: list[str] = []
    for i, p in enumerate(papers, 1):
        missing = p.missing_formats(formats)
        if missing:
            issues.append(
                f"[{i}] {p.cluster_id}: missing {', '.join(missing)}"
            )
    return issues


@app.command("cite")
def cite(
    query: str = typer.Argument(..., help="Paper title to search on Google Scholar."),
    format: str = typer.Option(
        "bibtex", "--format", "-F",
        help="Comma-separated formats or 'all'. Options: mla, apa, chicago, harvard, "
             "vancouver, bibtex, endnote, refman, refworks.",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max candidates to return."),
    as_json: bool = typer.Option(False, "--json", help="Output JSON."),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Write output to file."),
    no_browser: bool = typer.Option(
        False, "--no-browser",
        help="Skip the Playwright browser path. Uses the scholarly HTTP backend only. "
             "Faster when it works, but Scholar frequently blocks it — no silent fallback.",
    ),
    strict: bool = typer.Option(
        False, "--strict",
        help="Exit non-zero (code 4) if ANY requested citation format is missing. "
             "By default, missing formats are reported but the command still exits 0.",
    ),
) -> None:
    """Search Google Scholar and print citation formats.

    Default path drives a headful Chromium so Scholar doesn't block; the first
    run may ask you to solve a captcha once, after which cookies are cached.
    Pass `--no-browser` to use the scholarly HTTP backend instead.
    """
    from scholar_cite.search import search  # lazy (heavy deps)

    formats = _parse_formats(format)
    typer.echo(f"Searching Google Scholar for: {query!r}", err=True)
    papers = search(query, limit=limit, no_browser=no_browser)
    typer.echo(f"Found {len(papers)} result(s).", err=True)

    text = _render_json(papers, formats) if as_json else _render_plain(papers, formats)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        typer.echo(f"Wrote output to {output}", err=True)
    else:
        sys.stdout.write(text)

    if not papers:
        raise typer.Exit(code=EXIT_NO_RESULTS)

    issues = _summarize_missing(papers, formats)
    if issues:
        typer.echo("", err=True)
        typer.echo(f"Warning: {len(issues)} paper(s) missing requested format(s):", err=True)
        for line in issues:
            typer.echo(f"  {line}", err=True)
        if strict:
            raise typer.Exit(code=EXIT_PARTIAL)


@auth_app.command("status")
def auth_status() -> None:
    """Show the Playwright cookie-cache status."""
    from scholar_cite.browser_fetcher import cookies_status

    typer.echo(json.dumps(cookies_status(), indent=2, ensure_ascii=False))


@auth_app.command("reset")
def auth_reset() -> None:
    """Delete the cached Playwright cookies."""
    from scholar_cite.browser_fetcher import clear_cookies

    typer.echo("Cookies deleted." if clear_cookies() else "No cookies to delete.")


if __name__ == "__main__":
    app()
