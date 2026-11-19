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


# Every content type is grounded the same way: a source item makes a claim and
# cites the chunks that back it. So we review them all with the one Critic, by
# mapping each type's items onto the slide shape it understands (a heading plus
# body text), then renaming the issue id back to that type's own id so the
# generator's fixes land on the right item.

def _review_items(session, course_id, title, items, issue_key):
    # items are already slide-shaped: {id, heading, bullets, provenance, citations}.
    report = review(session, course_id, {"title": title, "slides": items})
    report["issues"] = [
        {issue_key: i.get("slide_id"), "problem": i.get("problem")}
        for i in report.get("issues", [])
    ]
    return report


def review_doc(session, course_id, doc: dict) -> dict:
    # a doc section is a heading plus a body of prose, where an unsupported claim
    # hides most easily, so docs are always reviewed.
    items = [
        {"id": s["id"], "heading": s.get("heading", ""), "bullets": [s.get("body", "")],
         "provenance": s.get("provenance", "source"), "citations": s.get("citations", [])}
        for s in doc.get("sections", [])
    ]
    return _review_items(session, course_id, doc.get("title", ""), items, "section_id")


def review_cards(session, course_id, cardset: dict) -> dict:
    # the claim on a flashcard is its answer (the back); the front is the prompt.
    items = [
        {"id": c["id"], "heading": c.get("front", ""), "bullets": [c.get("back", "")],
         "provenance": c.get("provenance", "source"), "citations": c.get("citations", [])}
        for c in cardset.get("cards", [])
    ]
    return _review_items(session, course_id, cardset.get("title", ""), items, "card_id")


def review_quiz(session, course_id, quiz: dict) -> dict:
    # the claim on a quiz question is that its answer is correct and its
    # explanation is supported; the stem is the prompt.
    items = []
    for q in quiz.get("questions", []):
        bullets = [f"Answer: {q.get('answer', '')}"]
        if q.get("explanation"):
            bullets.append(q["explanation"])
        items.append({
            "id": q["id"], "heading": q.get("stem", ""), "bullets": bullets,
            "provenance": q.get("provenance", "source"), "citations": q.get("citations", []),
        })
    return _review_items(session, course_id, quiz.get("title", ""), items, "question_id")


def review_map(session, course_id, mind: dict) -> dict:
    # the claim on a mind map node is its label and one-line detail.
    items = [
        {"id": n["id"], "heading": n.get("label", ""),
         "bullets": [n["detail"]] if n.get("detail") else [n.get("label", "")],
         "provenance": n.get("provenance", "source"), "citations": n.get("citations", [])}
        for n in mind.get("nodes", [])
    ]
    return _review_items(session, course_id, mind.get("title", ""), items, "node_id")


def verify_revise(build, review_fn, max_attempts=2):
    # the generate-verify-revise loop for the dedicated endpoints, which have no
    # graph retry loop of their own. build(base, issues) -> content and
    # review_fn(content) -> report. The first build is from scratch; on a critic
    # fail it revises from the last draft. Returns (content, final report).
    content = build(None, None)
    report = {}
    for attempt in range(max_attempts):
        report = review_fn(content)
        if report.get("passed", True) or attempt + 1 >= max_attempts:
            break
        content = build(content, report["issues"])
    return content, report
