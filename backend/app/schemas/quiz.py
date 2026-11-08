# The shape of a quiz. Every version of a quiz artifact stores a Quiz in
# this shape. Like a slide, each question says where it came from (source or
# supplementary) and carries citations to the exact chunks that back its
# answer and explanation. The provenance and citation shape is copied from
# slide.py so grounding and the eval work the same way.

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.slide import Citation


class Question(BaseModel):
    id: str
    # mcq has options and the answer is one of them. open is a free text answer.
    kind: Literal["mcq", "open"] = "mcq"
    stem: str
    options: list[str] = Field(default_factory=list)
    answer: str                 # the correct answer, grounded in the cited chunks
    explanation: str = ""       # why the answer is right, backed by the citations
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)


class Quiz(BaseModel):
    title: str
    questions: list[Question] = Field(default_factory=list)


class Grade(BaseModel):
    # the grader's verdict on one answer. feedback explains the right idea and
    # cites the source, so the student can see exactly where it comes from.
    question_id: str
    verdict: Literal["right", "partial", "wrong", "ungraded"]
    feedback: str
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)
    misconception: str = ""     # what the student seems to misunderstand, if anything
