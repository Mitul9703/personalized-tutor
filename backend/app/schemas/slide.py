# The shape of a slide and a deck. Every version of an artifact stores a
# deck in this shape. Each slide says where it came from (source or
# supplementary) and carries its citations so we can show the exact source.

from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    doc: str            # the file the chunk came from
    loc: str            # where in the file, like "p.4" or a section name


class Slide(BaseModel):
    id: str
    heading: str
    bullets: list[str] = Field(default_factory=list)
    notes: str = ""     # the spoken explanation behind the slide
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)
    level: Literal["intro", "standard", "deep"] = "standard"


class Deck(BaseModel):
    title: str
    slides: list[Slide] = Field(default_factory=list)
