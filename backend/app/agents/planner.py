# The Planner. For now it has one mode: survey the course. The survey runs
# once after upload. It reads the uploaded material, drafts a topic outline
# in a sensible order, and builds a map from each topic to the chunks that
# cover it. The coverage map comes from real retrieval, so the outline is
# grounded in what the material actually contains.
#
# The per topic planning mode (plan one topic on demand) is added in a
# later phase.

from sqlalchemy.orm import Session

from app.llm.chat import chat_json
from app.ingest.retrieve import retrieve_scored
from app.store.models import Chunk, CourseOutline

# how many chunks to show the model when it drafts the outline.
SAMPLE_CHUNKS = 30
# how many chunks to map to each topic for the coverage map.
COVERAGE_K = 5


def survey_course(session: Session, course_id: str) -> dict:
    sample = _sample_chunks(session, course_id)
    if not sample:
        return {}

    topics = _draft_outline(sample)
    coverage = _build_coverage(session, course_id, topics)

    result = {"topics": topics, "coverage": coverage}
    session.add(CourseOutline(course_id=course_id, outline=result))
    session.commit()
    return result


def _sample_chunks(session: Session, course_id: str) -> list[Chunk]:
    # take an evenly spread sample so the model sees the whole document, not
    # just the start.
    rows = (
        session.query(Chunk)
        .filter(Chunk.course_id == course_id)
        .order_by(Chunk.ordinal)
        .all()
    )
    if len(rows) <= SAMPLE_CHUNKS:
        return rows
    step = len(rows) / SAMPLE_CHUNKS
    return [rows[int(i * step)] for i in range(SAMPLE_CHUNKS)]


def _draft_outline(sample: list[Chunk]) -> list[dict]:
    joined = "\n\n".join(f"[chunk {c.ordinal}] {c.text}" for c in sample)
    messages = [
        {
            "role": "system",
            "content": "You plan a short course from a student's own material. Return JSON only.",
        },
        {
            "role": "user",
            "content": (
                "Here are pieces of the uploaded material:\n\n"
                f"{joined}\n\n"
                "List the main topics to teach, in a sensible learning order. "
                'Return JSON shaped like {"topics": [{"topic": "...", '
                '"summary": "...", "prerequisites": ["..."]}]}. '
                "Only include topics the material actually covers."
            ),
        },
    ]
    data = chat_json(messages)
    return data.get("topics", [])


def _build_coverage(session: Session, course_id: str, topics: list[dict]) -> dict:
    # for each topic, find the chunks that cover it and how close they are.
    # the score is the cosine distance, so a smaller best_score means the
    # material covers the topic well. a later phase uses this to decide
    # source grounded versus supplementary.
    coverage = {}
    for item in topics:
        topic = item.get("topic", "")
        if not topic:
            continue
        query = f"{topic}. {item.get('summary', '')}"
        scored = retrieve_scored(session, course_id, query, k=COVERAGE_K)
        coverage[topic] = {
            "chunks": [{"chunk_id": c.id, "score": round(d, 3)} for c, d in scored],
            "best_score": round(scored[0][1], 3) if scored else None,
        }
    return coverage
