# The quiz generator. A tool using agent built on run_agent, the same way as
# the slides Builder. It reads the shared lesson plan and writes questions
# whose correct answer is grounded in a chunk. It works on a working copy of
# the quiz, never the database. For a new quiz it usually calls set_quiz
# once. For an edit it uses the surgical tools. It can call retrieve_more
# when a question needs more source material.
#
# The model decides what to ask, how hard, and which chunk backs it. The tool
# handlers only do mechanical checks (the cited chunk exists in this course,
# an mcq answer is one of its options) and return errors so the model can
# fix them. The signature matches run_builder so the content type dispatch
# can call it the same way.

import json

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Document

MAX_STEPS = 10

_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "short id like q1"},
        "kind": {"type": "string", "enum": ["mcq", "open"]},
        "stem": {"type": "string", "description": "the question text"},
        "options": {"type": "array", "items": {"type": "string"}, "description": "for mcq only"},
        "answer": {"type": "string", "description": "the correct answer. for mcq, exactly one of the options"},
        "explanation": {"type": "string", "description": "why the answer is right, based on the cited chunks"},
        "provenance": {"type": "string", "enum": ["source", "supplementary"]},
        "chunk_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "the chunk ids that back the answer and explanation",
        },
    },
    "required": ["stem", "answer", "explanation", "provenance"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_quiz",
        "description": "Replace the whole quiz. Use this to build a quiz from scratch.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "questions": {"type": "array", "items": _QUESTION_SCHEMA},
            },
            "required": ["title", "questions"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_question",
        "description": "Insert a question after the given question id, or at the end if after_id is empty.",
        "parameters": {
            "type": "object",
            "properties": {"after_id": {"type": "string"}, "question": _QUESTION_SCHEMA},
            "required": ["question"],
        },
    }},
    {"type": "function", "function": {
        "name": "update_question",
        "description": "Replace one question by id with a new version of it.",
        "parameters": {
            "type": "object",
            "properties": {"question_id": {"type": "string"}, "question": _QUESTION_SCHEMA},
            "required": ["question_id", "question"],
        },
    }},
    {"type": "function", "function": {
        "name": "delete_question",
        "description": "Remove one question by id.",
        "parameters": {
            "type": "object",
            "properties": {"question_id": {"type": "string"}},
            "required": ["question_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "retrieve_more",
        "description": "Search the source material for more chunks when a question needs grounding.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when the quiz is ready.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


def run_quiz_builder(session, course_id, *, plan, chunks, base_quiz, instruction, intent, issues=None):
    quiz = base_quiz if base_quiz else {"title": plan.get("topic", "Quiz"), "questions": []}

    def make_handler(tool_name):
        return lambda args: _handle(tool_name, args, quiz, session, course_id)

    handlers = {name: make_handler(name) for name in (
        "set_quiz", "add_question", "update_question", "delete_question", "retrieve_more",
    )}

    system = (
        "You write and edit a quiz that checks whether a student understood a lesson, using the tools. "
        "Every question marked 'source' must have its correct answer and its explanation backed by the "
        "source chunks, and must list those chunk ids. Write the explanation so it teaches the idea, using "
        "only what the cited chunks say. Put chunk ids only in chunk_ids, never in the question, options, or "
        "explanation text. Only mark a question 'supplementary' when the material does not "
        "cover it, and give it no chunk ids. Mix multiple choice (mcq) and open questions. For mcq, give "
        "plausible wrong options that reflect common misunderstandings, and make the answer exactly one of "
        "the options. When editing, change only the questions the request is about. "
        "If a tool returns an error, fix the problem and call it again. Call finish when the quiz is ready."
    )
    user = _compose_task(plan, chunks, quiz, instruction, intent, issues)
    run_agent(system, user, TOOLS, handlers, max_steps=MAX_STEPS)
    return quiz


def _compose_task(plan, chunks, quiz, instruction, intent, issues):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = []
    if intent == "evolve":
        parts.append("Here is the current quiz as JSON:")
        parts.append(json.dumps(quiz))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append("Edit with add_question, update_question, or delete_question. Do not call set_quiz for an edit.")
    else:
        parts.append(f"Write a quiz for the topic: {plan.get('topic', instruction)}")
        if plan.get("objective"):
            parts.append(f"Objective: {plan['objective']}")
        if plan.get("points"):
            parts.append("Lesson plan points:")
            parts.append(json.dumps(plan["points"]))
        parts.append("Build the whole quiz in one set_quiz call, then finish.")
    if issues:
        parts.append("\nA reviewer found these problems. Fix them:")
        parts.append(json.dumps(issues))
    parts.append("\nSource chunks (cite these chunk ids on source questions):")
    parts.append(sources)
    return "\n".join(parts)


def _handle(name, args, quiz, session, course_id):
    questions = quiz.setdefault("questions", [])

    if name == "set_quiz":
        built = []
        for i, q in enumerate(args.get("questions", [])):
            question, error = _build_question(session, course_id, q, f"q{i + 1}")
            if error:
                return {"ok": False, "error": f"question {i + 1}: {error}"}
            built.append(question)
        quiz["title"] = args.get("title", quiz.get("title", "Quiz"))
        quiz["questions"] = built
        return {"ok": True, "questions": len(built)}

    if name == "add_question":
        question, error = _build_question(session, course_id, args.get("question", {}), _next_id(questions))
        if error:
            return {"ok": False, "error": error}
        after = args.get("after_id")
        if not after:
            questions.append(question)
        else:
            idx = _index_of(questions, after)
            if idx is None:
                return {"ok": False, "error": f"question {after} not found", "valid_ids": _ids(questions)}
            questions.insert(idx + 1, question)
        return {"ok": True, "question_id": question["id"]}

    if name == "update_question":
        idx = _index_of(questions, args.get("question_id"))
        if idx is None:
            return {"ok": False, "error": f"question {args.get('question_id')} not found", "valid_ids": _ids(questions)}
        question, error = _build_question(session, course_id, args.get("question", {}), questions[idx]["id"])
        if error:
            return {"ok": False, "error": error}
        question["id"] = questions[idx]["id"]
        questions[idx] = question
        return {"ok": True}

    if name == "delete_question":
        idx = _index_of(questions, args.get("question_id"))
        if idx is None:
            return {"ok": False, "error": f"question {args.get('question_id')} not found", "valid_ids": _ids(questions)}
        questions.pop(idx)
        return {"ok": True}

    if name == "retrieve_more":
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"ok": True, "chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    return {"ok": False, "error": f"unknown tool {name}"}


def _build_question(session, course_id, q, default_id):
    # mechanical checks only. returns (question, error).
    kind = q.get("kind") or ("mcq" if q.get("options") else "open")
    options = q.get("options") or []
    if kind == "mcq" and q.get("answer") not in options:
        return None, "for an mcq the answer must be exactly one of the options"

    provenance = q.get("provenance", "source")
    citations, error = resolve_citations(session, course_id, q.get("chunk_ids") or [])
    if error:
        return None, error
    if provenance == "source" and not citations:
        return None, "a source question must cite at least one chunk id from the material"

    return {
        "id": q.get("id") or default_id,
        "kind": kind,
        "stem": q.get("stem", ""),
        "options": options if kind == "mcq" else [],
        "answer": q.get("answer", ""),
        "explanation": q.get("explanation", ""),
        "provenance": provenance,
        "citations": citations if provenance == "source" else [],
    }, None


def resolve_citations(session, course_id, chunk_ids):
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
        return None, f"these chunk ids do not exist in the material: {missing}. Use retrieve to find real ones."
    return [
        {"chunk_id": i, "doc": found[i][1], "loc": _loc(found[i][0].location)}
        for i in ids
    ], None


def _loc(location):
    location = location or {}
    if location.get("page") is not None:
        return f"p.{location['page']}"
    return str(location.get("section") or "")


def _next_id(questions):
    taken = set(_ids(questions))
    n = len(questions) + 1
    while f"q{n}" in taken:
        n += 1
    return f"q{n}"


def _ids(questions):
    return [q["id"] for q in questions]


def _index_of(questions, question_id):
    for i, q in enumerate(questions):
        if q["id"] == question_id:
            return i
    return None
