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
    citations: CitationSet = field(default_factory=CitationSet)

    @property
    def first_author(self) -> str:
        return self.authors[0] if self.authors else ""
