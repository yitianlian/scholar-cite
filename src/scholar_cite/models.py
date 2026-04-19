from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FormatName = Literal[
    "mla", "apa", "chicago", "harvard", "vancouver",
    "bibtex", "endnote", "refman", "refworks",
]

ALL_FORMATS: tuple[FormatName, ...] = (
    "mla", "apa", "chicago", "harvard", "vancouver",
    "bibtex", "endnote", "refman", "refworks",
)

TEXT_FORMATS: tuple[FormatName, ...] = ("mla", "apa", "chicago", "harvard", "vancouver")
EXPORT_FORMATS: tuple[FormatName, ...] = ("bibtex", "endnote", "refman", "refworks")


@dataclass
class CitationSet:
    mla: str = ""
    apa: str = ""
    chicago: str = ""
    harvard: str = ""
    vancouver: str = ""
    bibtex: str = ""
    endnote: str = ""
    refman: str = ""
    refworks: str = ""

    def as_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in ALL_FORMATS}


@dataclass
class Paper:
    cluster_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    # URL the title link points at on the Scholar results page. Used to rank
    # candidate clusters by the quality of their primary source (CVF / ACL / IEEE
    # / arXiv are trusted; random aggregator hosts are demoted).
    source_url: str = ""
    citations: CitationSet = field(default_factory=CitationSet)
    # Per-format fetch errors, keyed by format name. Present → that format failed
    # and the corresponding CitationSet field is empty. Absent → either the format
    # succeeded or was never attempted.
    citation_errors: dict[str, str] = field(default_factory=dict)

    @property
    def first_author(self) -> str:
        return self.authors[0] if self.authors else ""

    def missing_formats(self, requested: list[str] | tuple[str, ...]) -> list[str]:
        return [f for f in requested if not getattr(self.citations, f, "")]
