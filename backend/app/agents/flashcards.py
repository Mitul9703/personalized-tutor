# The flashcard generator. A tool using agent built on run_agent, the same
# way as the slides Builder. It works on a working copy of the card set,
# never the database. For a new set it usually calls set_cards once. For an
# edit it uses the surgical tools (add, update, delete). It can call
# retrieve_more when a card needs more source material. When it is done it
# calls finish. The caller then saves the working copy as one new immutable
# version.
#
# The model writes every card and picks which chunks support it. This file
# only applies the model's edits and runs mechanical checks: chunk ids must
# exist in this course, and a source card must cite at least one. A failed
# check is returned to the model as a tool error so it can fix the card.
#
# run_flashcard_builder takes the same arguments as run_builder, so the
# content type dispatch can call either one the same way. base_deck is the
# current card set when editing, or None for a new set.

import json

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Document, LearnerModel

MAX_STEPS = 10

_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "short id like c1"},
        "front": {"type": "string", "description": "the question or prompt the student sees first"},
        "back": {"type": "string", "description": "the answer or short explanation"},
        "provenance": {"type": "string", "enum": ["source", "supplementary"]},
        "chunk_ids": {
            "type": "array", "items": {"type": "string"},
            "description": "ids of the source chunks that support this card. Empty for supplementary cards.",
        },
    },
    "required": ["front", "back", "provenance"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_cards",
        "description": "Replace the whole card set. Use this to build a set from scratch.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "cards": {"type": "array", "items": _CARD_SCHEMA},
            },
            "required": ["title", "cards"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_card",
        "description": "Insert a card after the given card id, or at the end if after_id is empty.",
        "parameters": {
            "type": "object",
            "properties": {
                "after_id": {"type": "string"},
                "card": _CARD_SCHEMA,
            },
            "required": ["card"],
        },
    }},
    {"type": "function", "function": {
        "name": "update_card",
        "description": "Change fields on one card. Only pass the fields you want to change.",
        "parameters": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string"},
                "front": {"type": "string"},
                "back": {"type": "string"},
                "provenance": {"type": "string", "enum": ["source", "supplementary"]},
                "chunk_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["card_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "delete_card",
        "description": "Remove one card by id.",
        "parameters": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}},
            "required": ["card_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "retrieve_more",
        "description": "Search the source material for more chunks when a card needs grounding.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when the card set is ready.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

SYSTEM = (
    "You build and edit a set of study flashcards for a student using the tools. "
    "Each card tests one idea: a clear question or prompt on the front and a short, correct answer on the back. "
    "Ground cards in the source chunks and list the chunk_ids that support each one. "
    "Mark anything beyond the sources as provenance 'supplementary' with no chunk_ids. "
    "If a card would be thin or you are unsure the material supports it, call retrieve_more before writing it. "
    "Use what is known about the learner to pick how hard the cards are and how they are worded, "
    "and to focus cards on what they find hard or have struggled with, so the set helps them recall it later. "
    "If a tool returns an error, fix the card and try again. "
    "When editing an existing set, make the smallest change that satisfies the request: "
    "touch only the cards the request is about and leave every other card exactly as it is. "
    "Call finish when the set is ready."
)


def run_flashcard_builder(session, course_id, *, plan, chunks, base_deck, instruction, intent, issues=None):
    cards = base_deck if base_deck else {"title": plan.get("topic", "Untitled"), "cards": []}
    cards.setdefault("cards", [])
    _ensure_ids(cards)

    # each tool handler edits the working copy in place
    def make_handler(tool_name):
        return lambda args: _handle(tool_name, args, cards, session, course_id)

    handlers = {name: make_handler(name) for name in (
        "set_cards", "add_card", "update_card", "delete_card", "retrieve_more",
    )}

    learner = _learner_context(session, course_id)
    user = _compose_task(plan, chunks, cards, instruction, intent, issues, learner)
    run_agent(SYSTEM, user, TOOLS, handlers, max_steps=MAX_STEPS)

    _ensure_ids(cards)
    return cards


def _compose_task(plan, chunks, cards, instruction, intent, issues, learner):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = [f"What we know about the learner:\n{learner or 'nothing yet'}\n"]
    if intent == "evolve":
        parts.append("Here is the current card set as JSON:")
        parts.append(json.dumps(_for_model(cards)))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append(
            "Edit with the surgical tools (update_card, add_card, delete_card). "
            "Do not call set_cards for an edit. Change only the card or cards the request is about, "
            "and leave all the other cards exactly as they are, word for word."
        )
    else:
        parts.append(f"Build a flashcard set for the topic: {plan.get('topic', instruction)}")
        if plan.get("objective"):
            parts.append(f"Objective: {plan['objective']}")
        if plan.get("points"):
            parts.append("Lesson plan points:")
            parts.append(json.dumps(plan["points"]))
        parts.append(f"The learner asked: {instruction}")
        parts.append("Build the whole set in one set_cards call, then finish.")
    if issues:
        parts.append("\nA reviewer found these problems. Fix them:")
        parts.append(json.dumps(issues))
    parts.append("\nSource chunks (use these chunk ids on source cards):")
    parts.append(sources)
    return "\n".join(parts)


def _for_model(cards):
    # show the model chunk_ids, the same field it writes, not the resolved citations.
    return {
        "title": cards.get("title", ""),
        "cards": [
            {"id": c["id"], "front": c["front"], "back": c["back"], "provenance": c["provenance"],
             "chunk_ids": [x["chunk_id"] for x in c.get("citations", [])]}
            for c in cards.get("cards", [])
        ],
    }


def _handle(name, args, cards, session, course_id):
    items = cards.setdefault("cards", [])

    if name == "set_cards":
        built, errors = [], []
        for i, raw in enumerate(args.get("cards", [])):
            card, error = _build_card(session, course_id, raw, f"c{i + 1}")
            if error:
                errors.append({"card": i + 1, "front": raw.get("front", ""), "error": error})
            else:
                built.append(card)
        if errors:
            # nothing is applied, so the set never holds a half checked mix
            return {"ok": False, "errors": errors, "hint": "fix these cards and call set_cards again"}
        cards["title"] = args.get("title", cards.get("title", "Untitled"))
        cards["cards"] = built
        _dedupe_ids(cards["cards"])
        return {"ok": True, "cards": len(built)}

    if name == "add_card":
        card, error = _build_card(session, course_id, args.get("card", {}), _next_id(items))
        if error:
            return {"ok": False, "error": error}
        if card["id"] in _ids(items):
            card["id"] = _next_id(items)
        after = args.get("after_id")
        if not after:
            items.append(card)
        else:
            idx = _index_of(items, after)
            if idx is None:
                return {"ok": False, "error": f"card {after} not found", "valid_ids": _ids(items)}
            items.insert(idx + 1, card)
        return {"ok": True, "card_id": card["id"]}

    if name == "update_card":
        card = _get(items, args.get("card_id"))
        if card is None:
            return {"ok": False, "error": f"card {args.get('card_id')} not found", "valid_ids": _ids(items)}
        merged = {
            "id": card["id"],
            "front": args["front"] if args.get("front") is not None else card["front"],
            "back": args["back"] if args.get("back") is not None else card["back"],
            "provenance": args["provenance"] if args.get("provenance") is not None else card["provenance"],
            "chunk_ids": (args["chunk_ids"] if args.get("chunk_ids") is not None
                          else [c["chunk_id"] for c in card.get("citations", [])]),
        }
        new_card, error = _build_card(session, course_id, merged, card["id"])
        if error:
            return {"ok": False, "error": error}
        card.update(new_card)
        return {"ok": True}

    if name == "delete_card":
        idx = _index_of(items, args.get("card_id"))
        if idx is None:
            return {"ok": False, "error": f"card {args.get('card_id')} not found", "valid_ids": _ids(items)}
        items.pop(idx)
        return {"ok": True}

    if name == "retrieve_more":
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"ok": True, "chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    if name == "finish":
        return {"ok": True}

    return {"ok": False, "error": f"unknown tool {name}"}


def _build_card(session, course_id, raw, default_id):
    # mechanical checks only. returns (card, error).
    provenance = raw.get("provenance", "source")
    if provenance not in ("source", "supplementary"):
        return None, "provenance must be 'source' or 'supplementary'"
    if not raw.get("front") or not raw.get("back"):
        return None, "a card needs both a front and a back"
    citations = []
    if provenance == "source":
        citations, error = _resolve_citations(session, course_id, raw.get("chunk_ids") or [])
        if error:
            return None, error
        if not citations:
            return None, "a source card must list at least one chunk id from the material"
    return {
        "id": raw.get("id") or default_id,
        "front": raw["front"],
        "back": raw["back"],
        "provenance": provenance,
        "citations": citations,
    }, None


def _resolve_citations(session, course_id, chunk_ids):
    # turn chunk ids into {chunk_id, doc, loc} citations, so every citation
    # resolves to a real chunk in this course. returns (citations, error).
    ids = list(dict.fromkeys(chunk_ids))
    if not ids:
        return [], None
    rows = (
        session.query(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.course_id == course_id, Chunk.id.in_(ids))
        .all()
    )
    found = {chunk.id: (chunk, filename) for chunk, filename in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        return None, f"these chunk ids do not exist in the material: {missing}. Use retrieve_more to find real ones."
    return [{"chunk_id": i, "doc": found[i][1], "loc": _loc(found[i][0].location)} for i in ids], None


def _loc(location):
    location = location or {}
    if location.get("page") is not None:
        return f"p.{location['page']}"
    return str(location.get("section") or "")


def _learner_context(session, course_id: str) -> str:
    # load the learner profile and notes as text for the prompt. this only
    # reads, the model decides what to do with it.
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    if row is None:
        return ""
    parts = []
    if row.profile:
        parts.append(f"Profile (self-reported): {json.dumps(row.profile, ensure_ascii=False)}")
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    return "\n".join(parts)


def _ensure_ids(cards: dict):
    # give any card without an id a stable one, based on its position.
    for i, card in enumerate(cards.get("cards", [])):
        if not card.get("id"):
            card["id"] = f"c{i + 1}"
    _dedupe_ids(cards.get("cards", []))


def _dedupe_ids(items):
    # the model sometimes repeats an id. ids must be unique so edits hit the
    # right card, so a repeated id gets a fresh one.
    seen = set()
    for card in items:
        if card["id"] in seen:
            card["id"] = _next_id(items)
        seen.add(card["id"])


def _next_id(items):
    taken = set(_ids(items))
    n = len(items) + 1
    while f"c{n}" in taken:
        n += 1
    return f"c{n}"


def _ids(items):
    return [c["id"] for c in items]


def _index_of(items, card_id):
    for i, c in enumerate(items):
        if c["id"] == card_id:
            return i
    return None


def _get(items, card_id):
    idx = _index_of(items, card_id)
    return items[idx] if idx is not None else None
