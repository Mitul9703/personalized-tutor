# Pedagogical quality, judged on learning science, not generic "quality".
#
# A deck can be faithful and still teach badly. This rubric comes from how
# education tuned systems (LearnLM) and the tutoring literature judge
# teaching: does the lesson build up step by step, make ideas concrete, check
# understanding, and keep the load manageable. These are closer to learning
# than a flat "is it clear" score.

import json

from app.llm.chat import chat_json

DIMENSIONS = {
    "scaffolding": "builds up in a sensible order, each step resting on the last, not a flat list of facts",
    "concreteness": "makes ideas concrete with examples, analogies, or worked steps",
    "checks_understanding": "prompts the student to think or self check, not just read",
    "cognitive_load": "introduces one idea at a time and does not overload a single slide",
    "clarity": "plain, precise language a learner at this level can follow",
}


def pedagogy_score(deck: dict, topic: str) -> dict:
    view = [
        {"heading": s.get("heading", ""), "bullets": s.get("bullets", []), "notes": s.get("notes", "")}
        for s in deck.get("slides", [])
    ]
    rubric = "\n".join(f'- "{k}": {v}' for k, v in DIMENSIONS.items())
    messages = [
        {"role": "system", "content": (
            "You are an expert teacher grading how well a lesson teaches, on learning science grounds. "
            "Return JSON only."
        )},
        {"role": "user", "content": (
            f"Topic: {topic}\n\n"
            f"LESSON (slides):\n{json.dumps(view)}\n\n"
            "Score each dimension 1-5 (5 best):\n"
            f"{rubric}\n\n"
            'Return JSON with each dimension name as a key holding its 1-5 score, '
            'e.g. {"scaffolding": 4, "concreteness": 3, "checks_understanding": 2, '
            '"cognitive_load": 4, "clarity": 5}.'
        )},
    ]
    r = chat_json(messages)
    scores = {}
    for k in DIMENSIONS:
        try:
            scores[k] = float(r.get(k, 0))
        except (TypeError, ValueError):
            scores[k] = 0.0
    vals = [v for v in scores.values() if v]
    scores["mean"] = round(sum(vals) / len(vals), 2) if vals else None
    return scores
