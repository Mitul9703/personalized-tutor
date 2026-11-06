# The Planner. Two modes, both tool using agents that search the material
# themselves instead of being handed a fixed set of chunks.
#
# survey_course runs once at upload and builds the outline and coverage map.
# plan_topic runs per request and plans one lesson, deciding for each point
# whether the material supports it (source) or not (supplementary). The
# model drives the searching: it decides the queries, judges if what came
# back is enough, tries different queries on weak points, and when the
# material truly does not cover something it says so. max_steps is only a
# fuse.

from sqlalchemy.orm import Session

from app.agents.agent_loop import run_agent
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, CourseOutline

MAX_SURVEY_CHUNKS = 24


def _retrieve_tool(session, course_id):
    def handler(args):
        rows = retrieve(session, course_id, args.get("query", ""), k=5)
        return {"chunks": [{"chunk_id": r.id, "text": r.text[:600], "loc": r.location} for r in rows]}
    return handler


# ---------- mode 2: plan one topic ----------

PLAN_TOOLS = [
    {"type": "function", "function": {
        "name": "retrieve",
        "description": "Search the student's material for chunks related to a query.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Record the lesson plan.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "a clean short title"},
                "objective": {"type": "string"},
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "point": {"type": "string"},
                            "provenance": {"type": "string", "enum": ["source", "supplementary"]},
                            "chunk_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["point", "provenance"],
                    },
                },
                "topic_absent": {
                    "type": "boolean",
                    "description": "true if the material does not cover this topic at all",
                },
            },
            "required": ["topic", "objective", "points"],
        },
    }},
]


def plan_topic(session: Session, course_id: str, topic: str, learner_notes: str = "", instruction: str = "") -> dict:
    system = (
        "You plan one lesson for a student from their own uploaded material. "
        "Search the material with retrieve as many times as you need, trying different queries to "
        "chase down the material for each point. For a point the material supports, set provenance "
        "'source' and list the chunk_ids. For a point you add from general knowledge, set 'supplementary' "
        "with an empty chunk_ids list. If the material does not cover the topic at all, set topic_absent. "
        "When the plan is ready, call finish."
    )
    user = (
        f"Topic the student asked about: {topic}\n"
        f"Extra instruction, if any: {instruction or 'none'}\n"
        f"What we know about the learner: {learner_notes or 'nothing yet'}\n"
    )
    result = run_agent(system, user, PLAN_TOOLS, {"retrieve": _retrieve_tool(session, course_id)}, max_steps=6)
    if "points" not in result:
        result = {"topic": topic, "objective": f"Understand {topic}", "points": [], "topic_absent": False}
    return result


# ---------- mode 1: survey the whole course ----------

SURVEY_TOOLS = [
    {"type": "function", "function": {
        "name": "corpus_sample",
        "description": "Get a spread of short snippets from across the whole material to see its breadth.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "retrieve",
        "description": "Search the material for chunks related to a query.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Record the course outline.",
        "parameters": {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string"},
                            "summary": {"type": "string"},
                            "prerequisites": {"type": "array", "items": {"type": "string"}},
                            "chunk_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["topic"],
                    },
                },
            },
            "required": ["topics"],
        },
    }},
]


def survey_course(session: Session, course_id: str) -> dict:
    rows = session.query(Chunk).filter(Chunk.course_id == course_id).order_by(Chunk.ordinal).all()
    if not rows:
        return {}

    def corpus_sample(_args):
        step = max(1, len(rows) // MAX_SURVEY_CHUNKS)
        sample = rows[::step][:MAX_SURVEY_CHUNKS]
        return {"sample": [{"chunk_id": c.id, "text": c.text[:160]} for c in sample]}

    handlers = {"corpus_sample": corpus_sample, "retrieve": _retrieve_tool(session, course_id)}
    system = (
        "You survey a student's uploaded material and build a course outline. "
        "Start with corpus_sample to see the breadth, then use retrieve to look closer where you need to. "
        "List the main topics in a sensible learning order, give each a short summary and its prerequisites, "
        "and list the chunk_ids that cover each topic. Only include topics the material actually covers. "
        "Call finish with the topics."
    )
    user = "Survey this course and build the outline."
    result = run_agent(system, user, SURVEY_TOOLS, handlers, max_steps=8)

    topics = result.get("topics", [])
    coverage = {t["topic"]: {"chunk_ids": t.get("chunk_ids", [])} for t in topics if t.get("topic")}
    outline = {"topics": topics, "coverage": coverage}
    session.add(CourseOutline(course_id=course_id, outline=outline))
    session.commit()
    return outline
