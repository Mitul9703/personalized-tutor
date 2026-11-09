"""One slide edit: semantic fulfillment and mechanical scope preservation."""
from questions import ask_json

COMMAND = "Simplify slide 2 using plain language and add one concrete example. Preserve its meaning and leave every other slide unchanged."


def judge_interaction(command, before, after):
    result = ask_json(
        'Check the requested revision against actual before/after lessons, including notes. Assess '
        'simplification, a suitable example, and meaning preservation. Return JSON '
        '{"fulfilled":"yes","meaning_preserved":true,"reason":"specific evidence"}. '
        'fulfilled must be yes, partial, or no.',
        {"command": command, "before": before, "after": after})
    if result.get("fulfilled") not in ("yes", "partial", "no") or type(result.get("meaning_preserved")) is not bool or not result.get("reason"):
        raise ValueError("Invalid interaction judgment")
    return result


def scope_preservation(before, after):
    old, new = before["slides"], after["slides"]
    unchanged = sum(i < len(new) and s == new[i] for i, s in enumerate(old) if i != 1)
    denominator = max(len(old) - 1, len(new) - 1)
    return {"unchanged_other_slides": unchanged, "other_slides": denominator,
            "non_target_preservation": unchanged / denominator if denominator else None,
            "target_changed": len(new) > 1 and old[1] != new[1],
            "scope_preserved": len(old) == len(new) and unchanged == len(old) - 1}
