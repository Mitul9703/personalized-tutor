# The shape of a mind map. A mind map is the visual content type: a set of
# concept nodes arranged as a tree. One node is the root (the central topic);
# every other node names its parent, so the whole map is a rooted tree. Like a
# slide, each node says where it came from (source or supplementary) and
# carries its citations so the student can open the exact source text.

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.slide import Citation


class MindNode(BaseModel):
    id: str
    label: str                        # short concept name shown in the node
    detail: str = ""                  # one line of explanation, optional
    parent_id: Optional[str] = None   # None for the single root node
    provenance: Literal["source", "supplementary"] = "source"
    citations: list[Citation] = Field(default_factory=list)


class MindMap(BaseModel):
    title: str
    nodes: list[MindNode] = Field(default_factory=list)
