# Personalization fidelity: the thing the baseline structurally cannot do.
#
# The project is PERSONALIZED tutorial generation. Our system carries a
# learner model that shapes what it builds. A single LLM call has no learner
# model and no memory across turns, so it cannot personalize at all. We show
# this directly: give our system the same topic and source under two learner
# profiles, a complete beginner and an advanced learner, and measure whether
# the two lessons actually differ in the right direction.
#
# We set the profile where the real system reads it: the learner_model notes
# in the database. For a brand new topic the request text is not fed to the
# planner, only the learner notes are, so this exercises the real
# personalization path. We talk to the same database the running API uses
# (TUTOR_DB, default the local test db on 5434).

import os

from sqlalchemy import create_engine, text

DB_URL = os.environ.get("TUTOR_DB", "postgresql+psycopg://tutor:tutor@localhost:5434/tutor")

NOVICE = (
    "The student is a complete beginner with no background in this subject. They need simple, "
    "plain language, everyday analogies, and no jargon or math unless it is built up from scratch. "
    "Go slowly and define every term."
)
ADVANCED = (
    "The student already has a strong background in this subject and finds the basics boring. They "
    "want depth: precise technical detail, underlying mechanisms, edge cases, and the formal "
    "definitions or math. Skip the introductory framing."
)

_engine = create_engine(DB_URL)


def set_learner_notes(course_id: str, notes: str) -> None:
    with _engine.begin() as conn:
        conn.execute(
            text("UPDATE learner_model SET notes = :n WHERE course_id = :c"),
            {"n": notes, "c": course_id},
        )


def differentiation(novice_deck: dict, advanced_deck: dict) -> dict:
    # a judge rates how much, and in which direction, the two lessons differ.
    import json
    from app.llm.chat import chat_json

    def view(d):
        return [{"heading": s.get("heading", ""), "bullets": s.get("bullets", []),
                 "notes": s.get("notes", "")} for s in d.get("slides", [])]

    messages = [
        {"role": "system", "content": (
            "You compare two lessons on the same topic, one meant for a complete beginner and one for "
            "an advanced learner. Return JSON only."
        )},
        {"role": "user", "content": (
            f"LESSON A (meant for a BEGINNER):\n{json.dumps(view(novice_deck))}\n\n"
            f"LESSON B (meant for an ADVANCED learner):\n{json.dumps(view(advanced_deck))}\n\n"
            "Judge:\n"
            '- "differ": 1-5, how much the two lessons actually differ in depth and framing (5 = very different).\n'
            '- "direction_correct": true if A really is simpler/more beginner friendly and B really is '
            "deeper/more advanced; false if they are swapped or indistinguishable.\n"
            '- "note": one short sentence on the main difference you saw.\n'
            'Return JSON {"differ": n, "direction_correct": true/false, "note": "..."}.'
        )},
    ]
    r = chat_json(messages)
    try:
        differ = float(r.get("differ", 0))
    except (TypeError, ValueError):
        differ = 0.0
    return {
        "differ": differ,
        "direction_correct": bool(r.get("direction_correct", False)),
        "note": str(r.get("note", "")),
    }
