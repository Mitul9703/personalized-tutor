"""Author and independently check source-based assessments before generation."""
import json
from pathlib import Path
from app.llm.chat import chat_json

# Set by the runner; record parsed model outputs without modifying the SDK.
CALLS = None
PHASE = None


def log(kind, **data):
    if CALLS:
        with Path(CALLS).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"phase": PHASE, "kind": kind, **data}, ensure_ascii=False) + "\n")


def ask_json(instruction, data):
    messages = [{"role": "system", "content": instruction},
                {"role": "user", "content": instruction + "\nReturn JSON only. Input:\n" + json.dumps(data)}]
    log("model_request", messages=messages, reasoning_effort="none")
    try:
        result = chat_json(messages, reasoning_effort="none")
    except json.JSONDecodeError as error:
        log("malformed_json", raw=error.doc)
        raise ValueError("Model returned malformed JSON") from error
    log("model_response", response=result)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def make_questions(doc_text, topic, n=5, *, previous=None, feedback=None):
    result = ask_json(
        'Write exactly count clear, source-specific comprehension questions about the topic. '
        'Every reference answer must be precise and explicitly supported by the source. '
        'If supplied, resolve validation feedback while keeping valid items. Return JSON '
        '{"questions":[{"q":"...","reference_answer":"..."}]}.',
        {"source": doc_text, "topic": topic, "count": n, "previous": previous, "feedback": feedback})
    rows = result.get("questions")
    if not isinstance(rows, list) or len(rows) != n or not all(isinstance(r, dict) and all(
        isinstance(r.get(k), str) and r[k].strip() for k in ("q", "reference_answer")) for r in rows):
        raise ValueError("Assessment question count or fields invalid")
    return rows


def validate_questions(doc_text, questions):
    result = ask_json(
        'Independently verify each question and reference answer against the source. Check source '
        'support and unambiguous wording. Do not accept answers just because they are generally true. '
        'Return JSON {"items":[{"index":0,"supported":true,"unambiguous":true,"reason":"..."}]} in order.',
        {"source": doc_text, "questions": questions})
    rows = result.get("items")
    if not isinstance(rows, list) or len(rows) != len(questions):
        raise ValueError("Assessment validation count mismatch")
    if any(not isinstance(r, dict) or r.get("index") != i or r.get("supported") is not True or
           r.get("unambiguous") is not True or not r.get("reason") for i, r in enumerate(rows)):
        raise ValueError("Assessment rejected: " + json.dumps(result))
    return result
