# The simulated learner: our headline metric is teaching effectiveness.
#
# A good tutorial should let a student answer questions about the topic. So
# we have a simulated student READ ONLY the generated tutorial (not the
# source), then answer the comprehension questions using only what the
# tutorial taught. A judge scores the answers against the source based
# reference answers. Whichever system's tutorial produces more correct
# answers taught better. This is the runnable proxy for the pre/post human
# learning study that comes in the final milestone.
#
# Validity: an LLM already knows a lot, so a naive test is meaningless. Two
# guards. First, the student is told to answer ONLY from the tutorial and to
# say NOT_COVERED when the tutorial did not teach it, so the score reflects
# what the tutorial conveyed, not the model's prior knowledge. Second, we
# run a no-tutorial control (the same student answers with no tutorial at
# all) to measure prior knowledge, so the lift a tutorial adds is visible
# and we are not fooled by an easy topic.

import json

from app.llm.chat import chat_json


def _deck_text(deck: dict) -> str:
    lines = []
    for s in deck.get("slides", []):
        lines.append("## " + s.get("heading", ""))
        for b in s.get("bullets", []):
            lines.append("- " + b)
        if s.get("notes"):
            lines.append(s["notes"])
    return "\n".join(lines)


def answer_from_tutorial(deck: dict, questions: list[dict]) -> list[str]:
    tutorial = _deck_text(deck)
    qlist = [q["q"] for q in questions]
    messages = [
        {"role": "system", "content": (
            "You are a student who just studied a short tutorial. Answer the questions using ONLY "
            "what the tutorial taught you. If the tutorial did not cover something, answer exactly "
            "NOT_COVERED for that question. Do not use outside knowledge. Return JSON only."
        )},
        {"role": "user", "content": (
            f"TUTORIAL YOU STUDIED:\n{tutorial}\n\n"
            f"QUESTIONS:\n{json.dumps(qlist)}\n\n"
            'Return JSON: {"answers": ["...", "..."]} in the same order as the questions.'
        )},
    ]
    r = chat_json(messages)
    ans = r.get("answers", []) if isinstance(r, dict) else []
    # pad/trim to match
    ans = [str(a) for a in ans][:len(qlist)]
    while len(ans) < len(qlist):
        ans.append("NOT_COVERED")
    return ans


def answer_without_tutorial(questions: list[dict]) -> list[str]:
    # control: prior knowledge only, no tutorial. shows how much the topic
    # was already answerable, so the tutorial's lift is honest.
    qlist = [q["q"] for q in questions]
    messages = [
        {"role": "system", "content": (
            "Answer these questions from your own general knowledge. If you do not know, say "
            "NOT_COVERED. Return JSON only."
        )},
        {"role": "user", "content": (
            f"QUESTIONS:\n{json.dumps(qlist)}\n\n"
            'Return JSON: {"answers": ["...", "..."]} in the same order as the questions.'
        )},
    ]
    r = chat_json(messages)
    ans = r.get("answers", []) if isinstance(r, dict) else []
    ans = [str(a) for a in ans][:len(qlist)]
    while len(ans) < len(qlist):
        ans.append("NOT_COVERED")
    return ans


def score_answers(questions: list[dict], answers: list[str]) -> dict:
    # a judge compares each student answer to the source based reference
    # answer and marks it correct, partial, wrong, or not_covered.
    triples = [
        {"q": q["q"], "reference_answer": q["reference_answer"], "student_answer": a}
        for q, a in zip(questions, answers)
    ]
    messages = [
        {"role": "system", "content": (
            "You grade a student's answers against reference answers. For each item return one verdict: "
            '"correct" (matches the reference in substance), "partial" (partly right or incomplete), '
            '"wrong" (incorrect), or "not_covered" (the student said NOT_COVERED or left it blank). '
            "Be strict about substance, not wording. Return JSON only."
        )},
        {"role": "user", "content": (
            f"ITEMS:\n{json.dumps(triples)}\n\n"
            'Return JSON: {"verdicts": ["correct"|"partial"|"wrong"|"not_covered", ...]} in order.'
        )},
    ]
    r = chat_json(messages)
    verdicts = r.get("verdicts", []) if isinstance(r, dict) else []
    verdicts = [str(v) for v in verdicts][:len(triples)]
    while len(verdicts) < len(triples):
        verdicts.append("not_covered")

    weight = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "not_covered": 0.0}
    score = sum(weight.get(v, 0.0) for v in verdicts) / len(verdicts) if verdicts else None
    counts = {k: verdicts.count(k) for k in ("correct", "partial", "wrong", "not_covered")}
    return {"score": round(score, 3) if score is not None else None, "verdicts": verdicts, "counts": counts}
