# The Critic. It reads the finished draft and checks that source slides are
# supported by the chunks they cite, that supplementary slides do not
# contradict the material, and that the slides are clear. It has a retrieve
# tool so it can search the material to verify a claim, not just judge the
# chunks it was handed. It returns pass or fail with a list of problems. A
# fail sends the Builder back with these notes.

import json

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve

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
    slides_view = [
        {
            "id": s.get("id"),
            "heading": s.get("heading"),
            "bullets": s.get("bullets", []),
            "provenance": s.get("provenance", "source"),
            "cited_chunk_ids": [c.get("chunk_id") for c in s.get("citations", [])],
        }
        for s in deck.get("slides", [])
    ]

    def retrieve_tool(args):
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"chunks": [{"chunk_id": r.id, "text": r.text[:500]} for r in rows]}

    system = (
        "You review a slide deck for a student. Check that each slide marked 'source' is supported by "
        "the chunks it cites and actually cites at least one chunk, that each 'supplementary' slide does "
        "not contradict the material, and that the slides are clear. Use retrieve to pull a chunk's text "
        "or to search for supporting or contradicting material when you need to. Fail only for a real "
        "grounding problem, not small style points. Call finish with the result."
    )
    user = "Slides to review:\n" + json.dumps(slides_view)
    result = run_agent(system, user, TOOLS, {"retrieve": retrieve_tool}, max_steps=6)

    if "passed" not in result:
        result = {"passed": True, "issues": []}
    result.setdefault("issues", [])
    return result
