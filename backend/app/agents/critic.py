# The Critic. It reads the finished draft and checks that source slides are
# supported by the chunks they cite, that supplementary slides do not
# contradict the material, and that the slides are clear. It has a retrieve
# tool so it can search the material to verify a claim, not just judge the
# chunks it was handed. It returns pass or fail with a list of problems. A
# fail sends the Builder back with these notes.

import json

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk

TOOLS = [
    {"type": "function", "function": {
        "name": "retrieve",
        "description": "Search the student's material to check whether a claim is supported.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Record the review result.",
        "parameters": {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean"},
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "slide_id": {"type": "string"},
                            "problem": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["passed"],
        },
    }},
]


def review(session, course_id, deck: dict) -> dict:
    # resolve the cited chunk ids to their text so the critic can check each
    # slide against what it actually cites, not just search for support.
    cited_ids = {
        c.get("chunk_id")
        for s in deck.get("slides", [])
        for c in s.get("citations", [])
        if c.get("chunk_id")
    }
    chunk_text = {}
    if cited_ids:
        rows = session.query(Chunk).filter(Chunk.id.in_(cited_ids)).all()
        chunk_text = {r.id: r.text for r in rows}

    slides_view = [
        {
            "id": s.get("id"),
            "heading": s.get("heading"),
            "bullets": s.get("bullets", []),
            "provenance": s.get("provenance", "source"),
            "cited_chunks": [
                {"chunk_id": c.get("chunk_id"), "text": chunk_text.get(c.get("chunk_id"), "(not found)")[:600]}
                for c in s.get("citations", []) if c.get("chunk_id")
            ],
        }
        for s in deck.get("slides", [])
    ]

    def retrieve_tool(args):
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"chunks": [{"chunk_id": r.id, "text": r.text[:500]} for r in rows]}

    system = (
        "You review a slide deck for a student. Your job is to catch claims that are FALSE or not in "
        "the material at all, not to nitpick wording or citation precision. Each 'source' slide below "
        "lists its cited chunks with their text.\n"
        "When a slide's claim is not in its own cited text, do NOT assume it is wrong: first search the "
        "whole material with retrieve to check whether the material supports it somewhere else. A claim "
        "that is true and supported somewhere in the material is fine, even if that slide happens to "
        "cite a chunk that does not contain that exact point. That is only a citation-precision issue, "
        "not a grounding failure, so do not fail the deck for it. A slide may also restate, combine, "
        "and explain the material in its own words and add correct elaboration that follows from it.\n"
        "Fail a 'source' slide only for a real problem:\n"
        "- a specific claim (a fact, number, definition, formula, or relationship) that the material "
        "contradicts;\n"
        "- a specific claim that, after you searched for it with retrieve, the material does not "
        "support anywhere, and that is not just common-sense framing;\n"
        "- a 'source' slide with no citation at all.\n"
        "You MUST search with retrieve before failing any claim as unsupported. A 'supplementary' slide "
        "only needs to not contradict the material. Do not fail for style, phrasing, ordering, length, "
        "citation precision, or correct elaboration. Name the exact claim and why for any fail. "
        "Call finish with the result."
    )
    user = "Slides to review:\n" + json.dumps(slides_view)
    result = run_agent(system, user, TOOLS, {"retrieve": retrieve_tool}, max_steps=6)

    if "passed" not in result:
        result = {"passed": True, "issues": []}
    result.setdefault("issues", [])
    return result
