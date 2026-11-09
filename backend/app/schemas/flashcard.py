# The shape of a flashcard and a flashcard set. Every version of a
# flashcards artifact stores a set in this shape. Like a slide, each card
# says where it came from (source or supplementary) and carries its
# citations so the student can see the exact source text.

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.slide import Citation


class Flashcard(BaseModel):
    id: str
    front: str          # the prompt the student sees first
    back: str           # the answer or explanation on the other side
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)


class FlashcardSet(BaseModel):
    title: str
    cards: list[Flashcard] = Field(default_factory=list)
