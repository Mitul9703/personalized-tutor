# The QA tutor. It answers a learner's question in the chat, without
# building a deck. The Router sends the answer and clarify intents here.
#
# It is a tool using agent on run_agent. It searches the material with
# retrieve as many times as it needs, then decides for itself what to do:
# answer with citations, ask one clarifying question when the request is
# ambiguous, or say the material does not cover it and offer to build
# content instead. It knows the course title and outline, so it reads a
# question in the course's subject (for example "momentum" in an ML course
# means the optimizer, not physics).
#
# Our code only does mechanical work: it turns the chunk ids the model cites
# into {chunk_id, doc, loc} citations, and drops ids that do not belong to
# this course so a citation always resolves to a real chunk.

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Course, CourseOutline, Document, Message

MAX_STEPS = 6
HISTORY_TURNS = 6  # how many earlier chat messages the agent sees

TOOLS = [
    {"type": "function", "function": {
        "name": "retrieve",
        "description": "Search the student's material for chunks related to a query.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Send the reply to the student.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["answer", "clarify"],
                    "description": "answer: a reply to the question. clarify: one short question back.",
                },
                "text": {
                    "type": "string",
                    "description": (
                        "The reply. Put a marker like [1] or [2] right after each claim that comes "
                        "from the material. The number is the position of that chunk in citations, "
                        "starting at 1."
                    ),
                },
                "citations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The chunk_ids the reply cites, in marker order. [1] is the first id.",
                },
                "uses_general_knowledge": {
                    "type": "boolean",
                    "description": "true if any part of the reply comes from general knowledge, not the material.",
                },
            },
            "required": ["kind", "text"],
        },
    }},
]

SYSTEM = (
    "You are a tutor answering a student's question in a chat, inside one course built from the "
    "student's own uploaded material. You do not build slides here, you reply in chat.\n"
    "Always search the material with retrieve before you answer. Try more than one query if the "
    "first results are weak. Read the question in the subject of this course.\n"
    "Then call finish with one of these:\n"
    "- answer: a short, clear reply grounded in the chunks you retrieved. Put a marker like [1] "
    "right after every claim taken from the material, and list the chunk_ids in citations in the "
    "same order. Any explanation of a topic must be cited. Only cite chunks you actually retrieved "
    "and that support the claim.\n"
    "- If the material does not cover the question, say so plainly. You may add a short note from "
    "general knowledge, but say clearly that it is not from their material, and set "
    "uses_general_knowledge. Never invent a citation for it.\n"
    "- clarify: if the question is ambiguous and you cannot tell what they mean, ask one short "
    "clarifying question instead of guessing.\n"
    "If a full lesson would serve the student better than a chat reply, answer briefly and offer "
    "to make slides on it.\n"
    "You also get the recent conversation. Use it to work out what a follow-up like 'that', "
    "'the other one', or 'explain it more simply' refers to. Earlier replies are not a source: "
    "retrieve again and cite the material for anything you explain."
)


def answer(session, course_id: str, question: str, *, intent: str = "answer",
           router_note: str = "", learner_notes: str = "") -> dict:
    # returns {"kind", "text", "citations": [{chunk_id, doc, loc}], "uses_general_knowledge"}
    seen = {}

    def retrieve_tool(args):
        rows = retrieve(session, course_id, args.get("query", ""), k=5)
        for r in rows:
            seen[r.id] = r
        return {"chunks": [
            {"chunk_id": r.id, "text": r.text[:700], "loc": _loc_label(r.location)} for r in rows
        ]}

    user = (
        f"Course: {_course_title(session, course_id)}\n"
        f"Topics in this course: {_outline_topics(session, course_id)}\n"
        f"What we know about the learner: {learner_notes or 'nothing yet'}\n"
        f"Recent conversation, oldest first:\n{_recent_turns(session, course_id)}\n\n"
        f"The router read this message as: {intent}"
        + (f" (its note: {router_note})" if router_note else "")
        + f"\n\nStudent message: {question}\n"
    )
    result = run_agent(SYSTEM, user, TOOLS, {"retrieve": retrieve_tool}, max_steps=MAX_STEPS)

    text = result.get("text") or result.get("_text") or ""
    if not text:
        return {
            "kind": "clarify",
            "text": "Could you say a bit more about what you want to know?",
            "citations": [],
            "uses_general_knowledge": False,
        }
    return {
        "kind": result.get("kind", "answer"),
        "text": text,
        "citations": _resolve_citations(session, course_id, result.get("citations") or [], seen),
        "uses_general_knowledge": bool(result.get("uses_general_knowledge", False)),
    }


def _resolve_citations(session, course_id, chunk_ids, seen):
    # keep the model's order so [n] markers still line up. an id that does
    # not resolve to a chunk in this course becomes None, and the frontend
    # shows that marker without a source instead of a wrong one.
    out = []
    for cid in chunk_ids:
        chunk = seen.get(cid) or session.get(Chunk, cid)
        if chunk is None or chunk.course_id != course_id:
            out.append(None)
            continue
        doc = session.get(Document, chunk.document_id)
        out.append({
            "chunk_id": chunk.id,
            "doc": doc.filename if doc else "",
            "loc": _loc_label(chunk.location),
        })
    return out


def _loc_label(location) -> str:
    location = location or {}
    if location.get("section"):
        return str(location["section"])
    if location.get("page") is not None:
        return f"p.{location['page']}"
    return ""


def _recent_turns(session, course_id):
    # the last few chat messages before this one. the API saves the
    # current learner message before the graph runs, so skip that newest row.
    rows = (
        session.query(Message)
        .filter(Message.course_id == course_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_TURNS + 1)
        .all()
    )
    if rows and rows[0].role == "learner":
        rows = rows[1:]
    rows = list(reversed(rows[:HISTORY_TURNS]))
    if not rows:
        return "(none, this is the first message)"
    lines = []
    for m in rows:
        who = "Student" if m.role == "learner" else "Tutor"
        lines.append(f"{who}: {m.text[:500]}")
    return "\n".join(lines)


def _course_title(session, course_id):
    course = session.get(Course, course_id)
    return course.title if course else "unknown"


def _outline_topics(session, course_id):
    row = (
        session.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.created_at.desc())
        .first()
    )
    if not row or not row.outline:
        return "not surveyed yet"
    topics = [t.get("topic") for t in row.outline.get("topics", []) if t.get("topic")]
    return ", ".join(topics) or "not surveyed yet"
