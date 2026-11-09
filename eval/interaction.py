# Interaction quality: the capability neither baseline has at all.
#
# Our system lets a student steer an existing deck ("explain this deeper",
# "simplify it", "add an example"). We generate a deck, then send a series of
# interaction commands and check two things for each: did the system actually
# do what was asked (a judge compares before and after), and did the result
# stay grounded in the material. A single LLM call and a RAG one-shot produce
# a deck and stop, so they score zero here by construction; we report this as
# a capability our architecture has and they do not.

import json

from app.llm.chat import chat_json
from tasks import load_doc
from judge import judge_deck, groundedness

COMMANDS = [
    "Explain the first slide in more depth.",
    "Simplify the whole deck for a complete beginner.",
    "Add a concrete example to help understanding.",
]


def _view(deck):
    return [{"heading": s.get("heading", ""), "bullets": s.get("bullets", []), "notes": s.get("notes", "")}
            for s in deck.get("slides", [])]


def judge_interaction(command: str, before: dict, after: dict) -> dict:
    messages = [
        {"role": "system", "content": (
            "You check whether an edit command was carried out on a slide deck. You see the deck before "
            "and after. Return JSON only."
        )},
        {"role": "user", "content": (
            f"COMMAND: {command}\n\n"
            f"BEFORE:\n{json.dumps(_view(before))}\n\n"
            f"AFTER:\n{json.dumps(_view(after))}\n\n"
            'Did the AFTER deck carry out the command? Return JSON '
            '{"fulfilled": "yes"|"partial"|"no", "reason": "one short sentence"}.'
        )},
    ]
    r = chat_json(messages)
    return {"fulfilled": str(r.get("fulfilled", "no")), "reason": str(r.get("reason", ""))}


def run_interaction(doc_path: str, topic: str) -> dict:
    # lazy import: run_eval imports this module at top level.
    import run_eval as R

    doc = load_doc(doc_path)
    course_id = R._new_course_with_doc(doc_path)
    res = R._post(f"/courses/{course_id}/messages", {"text": f"teach me about {topic}"})
    before = res.get("deck", {"slides": []})
    artifact_id = res.get("artifact_id")

    weight = {"yes": 1.0, "partial": 0.5, "no": 0.0}
    steps = []
    for cmd in COMMANDS:
        r = R._post(f"/courses/{course_id}/messages", {"text": cmd, "artifact_id": artifact_id})
        after = r.get("deck", before)
        verdict = judge_interaction(cmd, before, after)
        g = groundedness(judge_deck(after, doc))
        steps.append({"command": cmd, "fulfilled": verdict["fulfilled"],
                      "grounded_after": g, "reason": verdict["reason"]})
        before = after

    fulfill_vals = [weight.get(s["fulfilled"], 0.0) for s in steps]
    grounded_vals = [s["grounded_after"] for s in steps if s["grounded_after"] is not None]
    return {
        "topic": topic,
        "fulfillment": round(sum(fulfill_vals) / len(fulfill_vals), 3) if fulfill_vals else None,
        "grounded_after": round(sum(grounded_vals) / len(grounded_vals), 3) if grounded_vals else None,
        "steps": steps,
    }
