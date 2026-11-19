# The shape of a doc and its sections. A doc is the long-form content type:
# a readable article broken into sections, each one a heading and a block of
# prose. Like a slide, each section says where it came from (source or
# supplementary) and carries its citations so the student can open the exact
# source text.

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.slide import Citation, Visual


class DocSection(BaseModel):
    id: str
    heading: str
    body: str = ""      # the prose for this section, a few short paragraphs
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)
    visual: Visual | None = None


class Doc(BaseModel):
    title: str
    sections: list[DocSection] = Field(default_factory=list)
