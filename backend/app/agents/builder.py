# The Builder. This is the tool using agent. It works on a working copy of
# the deck, never the database. For a new deck it usually calls set_deck
# once. For an edit it uses the surgical tools (add, update, delete,
# reorder). It can call retrieve_more if a slide needs more source material.
# When it is done it calls finish. The finalize step later turns the
# finished working copy into one new immutable version.
#
# Tool errors are returned to the model so it can see what went wrong and
# try again. Because every tool writes to the working copy, a failed tool
# never touches a saved version.

import json

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Document

MAX_STEPS = 10

_SLIDE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "short id like s1"},
        "heading": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
        "provenance": {"type": "string", "enum": ["source", "supplementary"]},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "doc": {"type": "string"},
                    "loc": {"type": "string"},
                },
                "required": ["chunk_id"],
            },
        },
        "level": {"type": "string", "enum": ["intro", "standard", "deep"]},
    },
    "required": ["heading", "bullets", "provenance"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_deck",
        "description": "Replace the whole deck. Use this to build a deck from scratch.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "slides": {"type": "array", "items": _SLIDE_SCHEMA},
            },
            "required": ["title", "slides"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_slide",
        "description": "Insert a slide after the given slide id, or at the end if after_id is empty.",
        "parameters": {
            "type": "object",
            "properties": {
                "after_id": {"type": "string"},
                "slide": _SLIDE_SCHEMA,
            },
            "required": ["slide"],
        },
    }},
    {"type": "function", "function": {
        "name": "update_slide",
        "description": "Change fields on one slide. Only pass the fields you want to change.",
        "parameters": {
            "type": "object",
            "properties": {
                "slide_id": {"type": "string"},
                "heading": {"type": "string"},
                "bullets": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "provenance": {"type": "string", "enum": ["source", "supplementary"]},
                "citations": {"type": "array", "items": {"type": "object"}},
                "level": {"type": "string", "enum": ["intro", "standard", "deep"]},
            },
            "required": ["slide_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "delete_slide",
        "description": "Remove one slide by id.",
        "parameters": {
            "type": "object",
            "properties": {"slide_id": {"type": "string"}},
            "required": ["slide_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "reorder_slides",
        "description": "Set a new order. Pass every slide id exactly once.",
        "parameters": {
            "type": "object",
            "properties": {"order": {"type": "array", "items": {"type": "string"}}},
            "required": ["order"],
        },
    }},
    {"type": "function", "function": {
        "name": "retrieve_more",
        "description": "Search the source material for more chunks when a slide needs grounding.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when the deck is ready.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


def run_builder(session, course_id, *, plan, chunks, base_deck, instruction, intent, issues=None):
    deck = base_deck if base_deck else {"title": plan.get("topic", "Untitled"), "slides": []}
    _ensure_ids(deck)

    # each tool handler edits the working copy deck in place
    def make_handler(tool_name):
        return lambda args: _handle(tool_name, args, deck, session, course_id)

    handlers = {name: make_handler(name) for name in (
        "set_deck", "add_slide", "update_slide", "delete_slide", "reorder_slides", "retrieve_more",
    )}

    system = (
        "You build and edit a slide deck for a student using the tools. "
        "Ground slides in the source chunks and cite their chunk_id. The app fills in the "
        "document name and location from the chunk_id, so you only need to give the id. "
        "Mark anything beyond the sources as provenance 'supplementary' with no citation. "
        "Make each slide actually teach, not just label the topic. Write substantive bullets, one "
        "idea each, as full and clear sentences a student could learn from on their own, not "
        "telegraphic fragments. When the material gives a concrete example, number, formula, or "
        "worked case, put it on the slide. Aim for roughly three to five developed bullets per "
        "slide, following the lesson plan, and draw the depth from the material rather than padding. "
        "Give every slide a notes field with the deeper explanation, reasoning, or worked example "
        "behind its bullets, so the student can expand it to go further; keep the notes consistent "
        "with the cited material. Follow the lesson plan's depth and emphasis, and keep bullets clear "
        "and readable. "
        "When editing an existing deck, make the smallest change that satisfies the request: "
        "touch only the slides the request is about and leave every other slide exactly as it is. "
        "Do not reword or re-simplify slides you were not asked about. "
        "Call finish when the deck is ready."
    )
    user = _compose_task(plan, chunks, deck, instruction, intent, issues)
    run_agent(system, user, TOOLS, handlers, max_steps=MAX_STEPS)

    _ensure_ids(deck)
    return deck


def _compose_task(plan, chunks, deck, instruction, intent, issues):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = []
    if intent == "evolve":
        parts.append("Here is the current deck as JSON:")
        parts.append(json.dumps(deck))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append(
            "Edit with the surgical tools (update_slide, add_slide, delete_slide, reorder_slides). "
            "Do not call set_deck for an edit. Change only the slide or slides the request is about, "
            "and leave all the other slides exactly as they are, word for word."
        )
    else:
        parts.append(f"Build a slide deck for the topic: {plan.get('topic', instruction)}")
        if plan.get("objective"):
            parts.append(f"Objective: {plan['objective']}")
        if plan.get("points"):
            parts.append("Lesson plan points:")
            parts.append(json.dumps(plan["points"]))
        parts.append("Build the whole deck in one set_deck call, then finish.")
    if issues:
        parts.append("\nA reviewer found these problems. Fix them:")
        parts.append(json.dumps(issues))
    parts.append("\nSource chunks (cite these chunk ids on source slides):")
    parts.append(sources)
    return "\n".join(parts)


def _handle(name, args, deck, session, course_id):
    slides = deck.setdefault("slides", [])

    if name == "set_deck":
        deck["title"] = args.get("title", deck.get("title", "Untitled"))
        deck["slides"] = [_norm_slide(s, i, session, course_id) for i, s in enumerate(args.get("slides", []))]
        return {"ok": True, "slides": len(deck["slides"])}

    if name == "add_slide":
        slide = _norm_slide(args.get("slide", {}), len(slides), session, course_id)
        after = args.get("after_id")
        if not after:
            slides.append(slide)
        else:
            idx = _index_of(slides, after)
            if idx is None:
                return {"ok": False, "error": f"slide {after} not found", "valid_ids": _ids(slides)}
            slides.insert(idx + 1, slide)
        return {"ok": True, "slide_id": slide["id"]}

    if name == "update_slide":
        slide = _get(slides, args.get("slide_id"))
        if slide is None:
            return {"ok": False, "error": f"slide {args.get('slide_id')} not found", "valid_ids": _ids(slides)}
        for field in ("heading", "notes", "provenance", "level"):
            if args.get(field) is not None:
                slide[field] = args[field]
        if args.get("bullets") is not None:
            slide["bullets"] = args["bullets"]
        if args.get("citations") is not None:
            slide["citations"] = _resolve_citations(session, course_id, args["citations"])
        return {"ok": True}

    if name == "delete_slide":
        idx = _index_of(slides, args.get("slide_id"))
        if idx is None:
            return {"ok": False, "error": f"slide {args.get('slide_id')} not found", "valid_ids": _ids(slides)}
        slides.pop(idx)
        return {"ok": True}

    if name == "reorder_slides":
        order = args.get("order", [])
        by_id = {s["id"]: s for s in slides}
        if set(order) != set(by_id):
            return {"ok": False, "error": "order must list every slide id exactly once", "valid_ids": _ids(slides)}
        deck["slides"] = [by_id[i] for i in order]
        return {"ok": True}

    if name == "retrieve_more":
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"ok": True, "chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    if name == "finish":
        return {"ok": True}

    return {"ok": False, "error": f"unknown tool {name}"}


def _norm_slide(slide: dict, index: int, session, course_id) -> dict:
    return {
        "id": slide.get("id") or f"s{index + 1}",
        "heading": slide.get("heading", ""),
        "bullets": slide.get("bullets", []),
        "notes": slide.get("notes", ""),
        "provenance": slide.get("provenance", "source"),
        "citations": _resolve_citations(session, course_id, slide.get("citations", [])),
        "level": slide.get("level", "standard"),
    }


def _resolve_citations(session, course_id, citations):
    # turn whatever the model cited into {chunk_id, doc, loc} using the real
    # chunk and its document, so a slide citation always names a real source.
    # the model may pass dicts or bare ids; we only trust the chunk_id and look
    # up the rest. ids that are not a chunk in this course are dropped, so a
    # citation never points at nothing.
    ids = []
    for c in citations or []:
        cid = c.get("chunk_id") if isinstance(c, dict) else c
        if cid and cid not in ids:
            ids.append(cid)
    if not ids:
        return []
    rows = (
        session.query(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.course_id == course_id, Chunk.id.in_(ids))
        .all()
    )
    found = {chunk.id: (chunk, filename) for chunk, filename in rows}
    out = []
    for cid in ids:
        if cid in found:
            chunk, filename = found[cid]
            out.append({"chunk_id": cid, "doc": filename, "loc": _loc(chunk.location)})
    return out


def _loc(location):
    location = location or {}
    if location.get("page") is not None:
        return f"p.{location['page']}"
    return str(location.get("section") or "")


def _ensure_ids(deck: dict):
    # give any slide without an id a stable one, based on its position.
    for i, slide in enumerate(deck.get("slides", [])):
        if not slide.get("id"):
            slide["id"] = f"s{i + 1}"


def _ids(slides):
    return [s["id"] for s in slides]


def _index_of(slides, slide_id):
    for i, s in enumerate(slides):
        if s["id"] == slide_id:
            return i
    return None


def _get(slides, slide_id):
    idx = _index_of(slides, slide_id)
    return slides[idx] if idx is not None else None
