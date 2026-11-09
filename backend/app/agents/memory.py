# The memory updater. After a turn it rewrites the learner's running notes.
# The model decides what is worth remembering, we just store what it writes.
# The notes are read before planning so the system adapts to the learner.

import json

from app.llm.chat import chat
from app.store.models import LearnerModel


def update_notes(session, course_id: str, turn_text: str, deck_title: str):
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    if row is None:
        return

    old = row.notes or "nothing yet"
    messages = [
        {"role": "system", "content": (
            "You keep short running notes about a student, to help teach them better. "
            "Keep it to a few plain lines. Note what they are working on and anything about what they "
            "find hard or easy, or how they like things explained. Preserve useful learning history. "
            "The current structured profile is authoritative over conflicting older profile assertions: "
            "remove outdated assertions while retaining observations about progress and difficulties. "
            "Keep observed learning history distinct from self-reported background, and do not infer "
            "progress merely from a profile edit. Return only the updated notes."
        )},
        {"role": "user", "content": (
            f"Current learner profile (self-reported):\n{json.dumps(row.profile or {}, ensure_ascii=False)}\n\n"
            f"Current notes:\n{old}\n\n"
            f"This turn, the student asked: {turn_text}\n"
            f"The deck in play was: {deck_title}\n\n"
            "Give the updated notes."
        )},
    ]
    row.notes = chat(messages)
    session.commit()


def record_misconceptions(session, course_id: str, quiz_title: str, misconceptions: list[dict]):
    # the grader hands over what the student got wrong on a quiz. the model
    # decides how to fold it into the running notes.
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    if row is None or not misconceptions:
        return

    old = row.notes or "nothing yet"
    messages = [
        {"role": "system", "content": (
            "You keep short running notes about a student, to help teach them better. "
            "Keep it to a few plain lines. The student just took a quiz. Add what they misunderstood so "
            "later lessons can address it, and keep what still matters from the old notes. "
            "Return only the updated notes."
        )},
        {"role": "user", "content": (
            f"Current notes:\n{old}\n\n"
            f"Quiz: {quiz_title}\n"
            f"Mistakes the grader found:\n{misconceptions}\n\n"
            "Give the updated notes."
        )},
    ]
    row.notes = chat(messages)
    session.commit()
