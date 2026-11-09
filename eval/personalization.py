"""One proposed-system profile diagnostic; baseline capability is not evaluated."""
from questions import ask_json

NOVICE = {"level": "beginner", "goal": "Understand and explain the main concepts.", "background": "New to this topic; explain necessary prerequisites."}
ADVANCED = {"level": "advanced", "goal": NOVICE["goal"], "background": "Comfortable with calculus, linear algebra, gradient descent, and foundational terminology."}


def differentiation(novice_deck, advanced_deck):
    result = ask_json(
        'Compare lessons A (beginner) and B (advanced) on the same topic. Assess appropriate changes '
        'in depth, terminology, prerequisites, mechanisms, and examples, not just length or jargon. '
        'Return JSON {"differ":3,"direction_correct":true,"note":"specific evidence"}. '
        'differ: 1 indistinguishable, 3 some appropriate adaptation, 5 consistent appropriate adaptation.',
        {"A": novice_deck, "B": advanced_deck, "profiles": [NOVICE, ADVANCED]})
    if type(result.get("differ")) is not int or not 1 <= result["differ"] <= 5 or type(result.get("direction_correct")) is not bool or not isinstance(result.get("note"), str) or not result["note"].strip():
        raise ValueError("Invalid personalization judgment")
    return result
