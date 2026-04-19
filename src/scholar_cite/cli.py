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


def _parse_formats(raw: str) -> list[str]:
    if raw == "all":
        return list(ALL_FORMATS)
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    unknown = [n for n in names if n not in ALL_FORMATS]
    if unknown:
        raise typer.BadParameter(f"Unknown format(s): {', '.join(unknown)}")
    return names


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
            if not val:
                continue
            label = fmt.upper() if fmt in ("mla", "apa") else fmt.capitalize()
            if "\n" in val or len(val) > 90:
                lines.append(f"    {label}:")
                for row in val.splitlines() or [val]:
                    lines.append(f"        {row}")
            else:
                lines.append(f"    {label:<9} {val}")
        lines.append("")
    return "\n".join(lines)


def _render_json(papers: list[Paper], formats: list[str]) -> str:
    out = []
    for p in papers:
        out.append(
            {
                "cluster_id": p.cluster_id,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "venue": p.venue,
                "doi": p.doi,
                "citations": {f: getattr(p.citations, f, "") for f in formats},
            }
        )
    return json.dumps(out, indent=2, ensure_ascii=False) + "\n"


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
    browser: bool = typer.Option(
        False, "--browser",
        help="Skip plain HTTP and fetch every citation through a headless Chromium. "
             "Slower, but bypasses Scholar's 403 rate-limiter.",
    ),
) -> None:
    """Search Google Scholar and print citation formats."""
    from scholar_cite.search import search  # lazy (heavy deps)

    formats = _parse_formats(format)
    typer.echo(f"Searching Google Scholar for: {query!r}", err=True)
    papers = search(query, limit=limit, use_browser=browser)
    typer.echo(f"Found {len(papers)} result(s).", err=True)

    text = _render_json(papers, formats) if as_json else _render_plain(papers, formats)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        typer.echo(f"Wrote output to {output}", err=True)
    else:
        sys.stdout.write(text)


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
