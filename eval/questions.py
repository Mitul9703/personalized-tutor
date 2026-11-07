# Comprehension questions, built from the SOURCE (not from any tutorial).
#
# The point of the whole eval is learning, so we need something a learner
# should be able to answer after a good lesson. We ask the model to write
# questions whose answers live in this specific document, with a short
# reference answer taken from the source. Source specific questions matter:
# if a question is answerable from general knowledge alone, it cannot tell a
# good tutorial from a weak one, because the student already knew it.

import json

from app.llm.chat import chat_json

MAX_DOC_CHARS = 60000


def make_questions(doc_text: str, topic: str, n: int = 5) -> list[dict]:
    messages = [
        {"role": "system", "content": (
            "You write comprehension questions to test whether a student learned a topic. "
            "Return JSON only."
        )},
        {"role": "user", "content": (
            f"SOURCE MATERIAL:\n{doc_text[:MAX_DOC_CHARS]}\n\n"
            f"Topic being taught: {topic}\n\n"
            f"Write {n} short comprehension questions that a student should be able to answer "
            "AFTER a good lesson on this topic. Rules:\n"
            "- Each answer must be found in or directly follow from the source material above.\n"
            "- Prefer questions whose answer is specific to THIS material (a definition it gives, "
            "a mechanism it describes, a relationship it states), not trivia answerable from general "
            "knowledge without the material.\n"
            "- Keep each question to one sentence.\n"
            'Return JSON: {"questions": [{"q": "...", "reference_answer": "..."}]}'
        )},
    ]
    r = chat_json(messages)
    qs = r.get("questions", []) if isinstance(r, dict) else []
    out = []
    for item in qs[:n]:
        q = (item.get("q") or "").strip()
        a = (item.get("reference_answer") or "").strip()
        if q:
            out.append({"q": q, "reference_answer": a})
    return out
