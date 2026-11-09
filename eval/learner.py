"""Automated tutorial answerability, not observed student learning."""
from questions import ask_json


def _deck_text(deck):
    return "\n".join(part for s in deck["slides"] for part in
                     [s["heading"], *s["bullets"], s.get("notes") or ""])


def _answers(value, count):
    rows = value.get("answers")
    if not isinstance(rows, list) or len(rows) != count or not all(isinstance(r, str) for r in rows):
        raise ValueError("Answer count/type mismatch; no padding or trimming")
    return rows


def answer_from_tutorial(deck, questions):
    return _answers(ask_json(
        'Answer using ONLY the lesson, including accessible explanatory notes. Do not use outside '
        'knowledge. Say NOT_COVERED for missing information. Return JSON {"answers":["..."]} in order.',
        {"lesson": _deck_text(deck), "questions": [q["q"] for q in questions]}), len(questions))


def answer_without_tutorial(questions):
    return _answers(ask_json(
        'Answer from existing knowledge without a lesson or source. If unsure say NOT_COVERED. '
        'Return JSON {"answers":["..."]} in order.',
        {"questions": [q["q"] for q in questions]}), len(questions))


def score_answers(questions, answers):
    if not questions or len(questions) != len(answers):
        raise ValueError("Question/answer count mismatch")
    result = ask_json(
        'Grade answers by meaning against references. correct=substantively correct; partial=partly '
        'correct but incomplete; wrong=incorrect; not_covered=blank or NOT_COVERED. Return JSON '
        '{"verdicts":["correct","partial","wrong","not_covered"]} in question order.',
        {"items": [{**q, "student_answer": a} for q, a in zip(questions, answers)]})
    rows = result.get("verdicts")
    weights = {"correct": 1, "partial": .5, "wrong": 0, "not_covered": 0}
    if not isinstance(rows, list) or len(rows) != len(questions) or any(not isinstance(r, str) or r not in weights for r in rows):
        raise ValueError("Invalid grading response; metric unavailable")
    points = [0 if not a.strip() or a.strip() == "NOT_COVERED" else weights[r] for a, r in zip(answers, rows)]
    return {"score": sum(points) / len(points), "points": points, "denominator": len(points), "verdicts": rows}
