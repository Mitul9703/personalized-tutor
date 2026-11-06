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

from app.llm.chat import chat_tools
from app.ingest.retrieve import retrieve

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

    messages = [
        {"role": "system", "content": (
            "You build and edit a slide deck for a student using the tools. "
            "Ground slides in the source chunks and cite their chunk_id. "
            "Mark anything beyond the sources as provenance 'supplementary' with no citation. "
            "Keep slides short and clear. Call finish when the deck is ready."
        )},
        {"role": "user", "content": _compose_task(plan, chunks, deck, instruction, intent, issues)},
    ]

    for _ in range(MAX_STEPS):
        message = chat_tools(messages, TOOLS)
        messages.append(message)
        if not message.tool_calls:
            break
        done = False
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _handle(name, args, deck, session, course_id)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })
            if name == "finish":
                done = True
        if done:
            break

    _ensure_ids(deck)
    return deck


def _compose_task(plan, chunks, deck, instruction, intent, issues):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = []
    if intent == "evolve":
        parts.append("Here is the current deck as JSON:")
        parts.append(json.dumps(deck))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append("Edit the deck with the surgical tools to satisfy the request.")
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
        deck["slides"] = [_norm_slide(s, i) for i, s in enumerate(args.get("slides", []))]
        return {"ok": True, "slides": len(deck["slides"])}

    if name == "add_slide":
        slide = _norm_slide(args.get("slide", {}), len(slides))
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
            slide["citations"] = args["citations"]
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


def _norm_slide(slide: dict, index: int) -> dict:
    return {
        "id": slide.get("id") or f"s{index + 1}",
        "heading": slide.get("heading", ""),
        "bullets": slide.get("bullets", []),
        "notes": slide.get("notes", ""),
        "provenance": slide.get("provenance", "source"),
        "citations": slide.get("citations", []),
        "level": slide.get("level", "standard"),
    }


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
