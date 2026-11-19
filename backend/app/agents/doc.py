# The doc generator. A tool using agent built on run_agent, the same way as
# the slides Builder and the flashcards generator. It works on a working copy
# of the doc, never the database. For a new doc it usually calls set_doc once.
# For an edit it uses the surgical tools (add, update, delete, reorder). It can
# call retrieve_more when a section needs more source material. When it is done
# it calls finish. The caller then saves the working copy as one new immutable
# version.
#
# The model writes every section and picks which chunks support it. This file
# only applies the model's edits and runs mechanical checks: chunk ids must
# exist in this course, and a source section must cite at least one. A failed
# check is returned to the model as a tool error so it can fix the section.
#
# run_doc_builder takes the same arguments as run_builder, so a caller can
# treat every content type the same way. base_deck is the current doc when
# editing, or None for a new doc.

import json

from app.agents.agent_loop import run_agent
from app.agents.visuals import VISUAL_SCHEMA, clean_visual
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Document, LearnerModel

MAX_STEPS = 10

_SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "short id like d1"},
        "heading": {"type": "string"},
        "body": {
            "type": "string",
            "description": "the prose for this section: one to three short paragraphs a student can read and learn from",
        },
        "provenance": {"type": "string", "enum": ["source", "supplementary"]},
        "chunk_ids": {
            "type": "array", "items": {"type": "string"},
            "description": "ids of the source chunks that support this section. Empty for supplementary sections.",
        },
        "visual": VISUAL_SCHEMA,
    },
    "required": ["heading", "body", "provenance"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_doc",
        "description": "Replace the whole doc. Use this to write a doc from scratch.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {"type": "array", "items": _SECTION_SCHEMA},
            },
            "required": ["title", "sections"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_section",
        "description": "Insert a section after the given section id, or at the end if after_id is empty.",
        "parameters": {
            "type": "object",
            "properties": {
                "after_id": {"type": "string"},
                "section": _SECTION_SCHEMA,
            },
            "required": ["section"],
        },
    }},
    {"type": "function", "function": {
        "name": "update_section",
        "description": "Change fields on one section. Only pass the fields you want to change.",
        "parameters": {
            "type": "object",
            "properties": {
                "section_id": {"type": "string"},
                "heading": {"type": "string"},
                "body": {"type": "string"},
                "provenance": {"type": "string", "enum": ["source", "supplementary"]},
                "chunk_ids": {"type": "array", "items": {"type": "string"}},
                "visual": VISUAL_SCHEMA,
            },
            "required": ["section_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "delete_section",
        "description": "Remove one section by id.",
        "parameters": {
            "type": "object",
            "properties": {"section_id": {"type": "string"}},
            "required": ["section_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "reorder_sections",
        "description": "Set a new order. Pass every section id exactly once.",
        "parameters": {
            "type": "object",
            "properties": {"order": {"type": "array", "items": {"type": "string"}}},
            "required": ["order"],
        },
    }},
    {"type": "function", "function": {
        "name": "retrieve_more",
        "description": "Search the source material for more chunks when a section needs grounding.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when the doc is ready.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

SYSTEM = (
    "You write and edit a study doc for a student using the tools. A doc is a readable article: "
    "each section has a short heading and a few short paragraphs of clear prose the student can "
    "learn from on their own. Explain in full sentences, define terms the first time they appear, "
    "and when the material gives a concrete example, number, formula, or worked case, include it. "
    "Write the body in Markdown: use **bold** for key terms, bulleted or numbered lists to lay out "
    "steps, and a Markdown table when you compare things. Write every formula or equation as LaTeX, "
    "inline as $...$ and as $$...$$ on its own line for an important one, so it renders as real math. "
    "Teach with worked examples: when there is a formula or procedure, walk through a short "
    "step-by-step example using the actual numbers from the material. "
    "When a diagram would make a section clearer, attach a visual to it: use Mermaid for a process, "
    "cycle, or how parts connect, or a small self-contained SVG for a labelled, coloured diagram. Keep "
    "it accurate to the material and captioned, and add one only where it genuinely helps. "
    "Ground sections in the source chunks and list the chunk_ids that support each one. Do not write "
    "chunk ids, citation markers, or '[Source: ...]' tags in the body text; the app records grounding "
    "separately from the chunk_ids you list. Mark anything "
    "beyond the sources as provenance 'supplementary' with no chunk_ids. If a section would be thin "
    "or you are unsure the material supports it, call retrieve_more before writing it. "
    "Use what is known about the learner to pick the depth, terminology, and examples. "
    "If a tool returns an error, fix the section and try again. "
    "When editing an existing doc, make the smallest change that satisfies the request: touch only the "
    "section or sections the request is about and leave every other section exactly as it is, word for "
    "word. Call finish when the doc is ready."
)


def run_doc_builder(session, course_id, *, plan, chunks, base_deck, instruction, intent, issues=None):
    doc = base_deck if base_deck else {"title": plan.get("topic", "Untitled"), "sections": []}
    doc.setdefault("sections", [])
    _ensure_ids(doc)

    def make_handler(tool_name):
        return lambda args: _handle(tool_name, args, doc, session, course_id)

    handlers = {name: make_handler(name) for name in (
        "set_doc", "add_section", "update_section", "delete_section", "reorder_sections", "retrieve_more",
    )}

    learner = _learner_context(session, course_id)
    user = _compose_task(plan, chunks, doc, instruction, intent, issues, learner)
    run_agent(SYSTEM, user, TOOLS, handlers, max_steps=MAX_STEPS)

    _ensure_ids(doc)
    return doc


def _compose_task(plan, chunks, doc, instruction, intent, issues, learner):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = [f"What we know about the learner:\n{learner or 'nothing yet'}\n"]
    if intent == "evolve":
        parts.append("Here is the current doc as JSON:")
        parts.append(json.dumps(_for_model(doc)))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append(
            "Edit with the surgical tools (update_section, add_section, delete_section, reorder_sections). "
            "Do not call set_doc for an edit. Change only the section or sections the request is about, "
            "and leave all the other sections exactly as they are, word for word."
        )
    else:
        parts.append(f"Write a study doc for the topic: {plan.get('topic', instruction)}")
        if plan.get("objective"):
            parts.append(f"Objective: {plan['objective']}")
        if plan.get("points"):
            parts.append("Lesson plan points:")
            parts.append(json.dumps(plan["points"]))
        parts.append(f"The learner asked: {instruction}")
        parts.append("Write the whole doc in one set_doc call, then finish.")
    if issues:
        parts.append("\nA reviewer found these problems. Fix them:")
        parts.append(json.dumps(issues))
    parts.append("\nSource chunks (use these chunk ids on source sections):")
    parts.append(sources)
    return "\n".join(parts)


def _for_model(doc):
    # show the model chunk_ids, the same field it writes, not the resolved citations.
    return {
        "title": doc.get("title", ""),
        "sections": [
            {"id": s["id"], "heading": s["heading"], "body": s["body"], "provenance": s["provenance"],
             "chunk_ids": [x["chunk_id"] for x in s.get("citations", [])], "visual": s.get("visual")}
            for s in doc.get("sections", [])
        ],
    }


def _handle(name, args, doc, session, course_id):
    items = doc.setdefault("sections", [])

    if name == "set_doc":
        built, errors = [], []
        for i, raw in enumerate(args.get("sections", [])):
            section, error = _build_section(session, course_id, raw, f"d{i + 1}")
            if error:
                errors.append({"section": i + 1, "heading": raw.get("heading", ""), "error": error})
            else:
                built.append(section)
        if errors:
            # nothing is applied, so the doc never holds a half checked mix
            return {"ok": False, "errors": errors, "hint": "fix these sections and call set_doc again"}
        doc["title"] = args.get("title", doc.get("title", "Untitled"))
        doc["sections"] = built
        _dedupe_ids(doc["sections"])
        return {"ok": True, "sections": len(built)}

    if name == "add_section":
        section, error = _build_section(session, course_id, args.get("section", {}), _next_id(items))
        if error:
            return {"ok": False, "error": error}
        if section["id"] in _ids(items):
            section["id"] = _next_id(items)
        after = args.get("after_id")
        if not after:
            items.append(section)
        else:
            idx = _index_of(items, after)
            if idx is None:
                return {"ok": False, "error": f"section {after} not found", "valid_ids": _ids(items)}
            items.insert(idx + 1, section)
        return {"ok": True, "section_id": section["id"]}

    if name == "update_section":
        section = _get(items, args.get("section_id"))
        if section is None:
            return {"ok": False, "error": f"section {args.get('section_id')} not found", "valid_ids": _ids(items)}
        merged = {
            "id": section["id"],
            "heading": args["heading"] if args.get("heading") is not None else section["heading"],
            "body": args["body"] if args.get("body") is not None else section["body"],
            "provenance": args["provenance"] if args.get("provenance") is not None else section["provenance"],
            "chunk_ids": (args["chunk_ids"] if args.get("chunk_ids") is not None
                          else [c["chunk_id"] for c in section.get("citations", [])]),
            "visual": args["visual"] if args.get("visual") is not None else section.get("visual"),
        }
        new_section, error = _build_section(session, course_id, merged, section["id"])
        if error:
            return {"ok": False, "error": error}
        section.update(new_section)
        return {"ok": True}

    if name == "delete_section":
        idx = _index_of(items, args.get("section_id"))
        if idx is None:
            return {"ok": False, "error": f"section {args.get('section_id')} not found", "valid_ids": _ids(items)}
        items.pop(idx)
        return {"ok": True}

    if name == "reorder_sections":
        order = args.get("order", [])
        by_id = {s["id"]: s for s in items}
        if set(order) != set(by_id):
            return {"ok": False, "error": "order must list every section id exactly once", "valid_ids": _ids(items)}
        doc["sections"] = [by_id[i] for i in order]
        return {"ok": True}

    if name == "retrieve_more":
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"ok": True, "chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    if name == "finish":
        return {"ok": True}

    return {"ok": False, "error": f"unknown tool {name}"}


def _build_section(session, course_id, raw, default_id):
    # mechanical checks only. returns (section, error).
    provenance = raw.get("provenance", "source")
    if provenance not in ("source", "supplementary"):
        return None, "provenance must be 'source' or 'supplementary'"
    if not raw.get("heading") or not raw.get("body"):
        return None, "a section needs both a heading and a body"
    citations = []
    if provenance == "source":
        citations, error = _resolve_citations(session, course_id, raw.get("chunk_ids") or [])
        if error:
            return None, error
        if not citations:
            return None, "a source section must list at least one chunk id from the material"
    return {
        "id": raw.get("id") or default_id,
        "heading": raw["heading"],
        "body": raw["body"],
        "provenance": provenance,
        "citations": citations,
        "visual": clean_visual(raw.get("visual")),
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
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    if row is None:
        return ""
    parts = []
    if row.profile:
        parts.append(f"Profile (self-reported): {json.dumps(row.profile, ensure_ascii=False)}")
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    return "\n".join(parts)


def _ensure_ids(doc: dict):
    for i, section in enumerate(doc.get("sections", [])):
        if not section.get("id"):
            section["id"] = f"d{i + 1}"
    _dedupe_ids(doc.get("sections", []))


def _dedupe_ids(items):
    seen = set()
    for section in items:
        if section["id"] in seen:
            section["id"] = _next_id(items)
        seen.add(section["id"])


def _next_id(items):
    taken = set(_ids(items))
    n = len(items) + 1
    while f"d{n}" in taken:
        n += 1
    return f"d{n}"


def _ids(items):
    return [s["id"] for s in items]


def _index_of(items, section_id):
    for i, s in enumerate(items):
        if s["id"] == section_id:
            return i
    return None


def _get(items, section_id):
    idx = _index_of(items, section_id)
    return items[idx] if idx is not None else None
