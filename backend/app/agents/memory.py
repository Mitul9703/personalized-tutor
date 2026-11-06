# The memory updater. After a turn it rewrites the learner's running notes.
# The model decides what is worth remembering, we just store what it writes.
# The notes are read before planning so the system adapts to the learner.

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
            "find hard or easy, or how they like things explained. Return only the updated notes."
        )},
        {"role": "user", "content": (
            f"Current notes:\n{old}\n\n"
            f"This turn, the student asked: {turn_text}\n"
            f"The deck in play was: {deck_title}\n\n"
            "Give the updated notes."
        )},
    ]
    row.notes = chat(messages)
    session.commit()
