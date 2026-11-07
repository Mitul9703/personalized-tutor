# Baseline 1: a single LLM call with the whole document in the prompt. No
# retrieval, no critic, no interaction. It gets the same document, topic, and
# chat model as our system, so the comparison isolates what our agentic
# grounding, verification, and interaction add on top of just prompting the
# model with the material.

import json

from app.llm.chat import chat_json

# gpt-6-luna has a very large context, so we give the baseline essentially the
# whole document. Its disadvantage is architectural, not a context limit.
MAX_DOC_CHARS = 150000


def single_call_baseline(doc_text: str, topic: str) -> dict:
    material = doc_text[:MAX_DOC_CHARS]
    messages = [
        {"role": "system", "content": "You make a short slide deck to teach a student. Return JSON only."},
        {"role": "user", "content": (
            f"Here is the student's material:\n\n{material}\n\n"
            f"Make a slide deck that teaches: {topic}\n"
            'Return JSON shaped like {"title": "...", "slides": [{"heading": "...", '
            '"bullets": ["..."], "provenance": "source", "citations": []}]}. '
            "Use provenance 'source' for content taken from the material and 'supplementary' for "
            "anything you add from general knowledge beyond the material."
        )},
    ]
    deck = chat_json(messages)
    if not isinstance(deck, dict):
        deck = {"title": topic, "slides": []}
    deck.setdefault("slides", [])
    return deck
