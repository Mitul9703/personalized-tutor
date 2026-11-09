# Agent-behavior metric: does the Critic actually earn its place?
#
# We plant a plausible but false claim on a source slide of a real, grounded
# deck and ask the Critic to review it. A Critic that works should fail the
# planted deck (caught) and pass the clean deck (no false alarm). Run over
# several decks to get a catch rate and a false-alarm rate. This is the
# "planted-error catch rate" the Milestone 2 plan lists under agent behavior.
#
# The Critic reads chunks from the database, so we open a session to the same
# database the running API uses (TUTOR_DB, default the local test db on 5434).

import copy
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.critic import review
from app.llm.chat import chat_json

DB_URL = os.environ.get("TUTOR_DB", "postgresql+psycopg://tutor:tutor@localhost:5434/tutor")
_Session = sessionmaker(bind=create_engine(DB_URL))


def _false_claim(topic: str) -> str:
    r = chat_json([
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": (
            f"Write one plausible-sounding but factually FALSE one-sentence statement about {topic}. "
            'Return JSON {"claim": "..."}.'
        )},
    ])
    return str(r.get("claim", "")) if isinstance(r, dict) else ""


def _plant(deck: dict, false_claim: str) -> dict:
    planted = copy.deepcopy(deck)
    for s in planted.get("slides", []):
        if s.get("provenance", "source") == "source":
            # keep the slide's citation, but make a bullet say something false.
            s["bullets"] = [false_claim] + list(s.get("bullets", []))[:1]
            break
    return planted


def catch_check(course_id: str, deck: dict, topic: str) -> dict:
    # returns whether the planted error was caught and whether the clean deck
    # passed (a false alarm is clean_passed == False).
    claim = _false_claim(topic)
    if not claim:
        return {"caught": None, "clean_passed": None}
    session = _Session()
    try:
        clean = review(session, course_id, deck)
        planted = review(session, course_id, _plant(deck, claim))
    finally:
        session.close()
    return {
        "planted_claim": claim,
        "caught": (planted.get("passed") is False),
        "clean_passed": (clean.get("passed") is True),
    }
