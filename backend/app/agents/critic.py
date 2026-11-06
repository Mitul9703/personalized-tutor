# The Critic. It reads the finished draft and the source chunks and checks a
# few things: every source slide should be supported by the chunks it cites,
# supplementary slides should be labeled and should not contradict the
# sources, and the slides should be clear. It returns a pass or fail with a
# list of problems. A fail sends the Builder back with these notes.
#
# This is a single structured call, not a tool loop.

import json

from app.llm.chat import chat_json


def review(deck: dict, chunks: list) -> dict:
    slides_view = [
        {
            "id": s.get("id"),
            "heading": s.get("heading"),
            "bullets": s.get("bullets", []),
            "provenance": s.get("provenance", "source"),
            "cited_chunk_ids": [c.get("chunk_id") for c in s.get("citations", [])],
        }
        for s in deck.get("slides", [])
    ]
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"

    messages = [
        {"role": "system", "content": "You review a slide deck for a student. Return JSON only."},
        {"role": "user", "content": (
            "Slides:\n"
            f"{json.dumps(slides_view)}\n\n"
            "Source chunks (id in brackets):\n"
            f"{sources}\n\n"
            "Check these things:\n"
            "1. Each slide with provenance 'source' is supported by the chunks it cites, "
            "and it actually cites at least one chunk.\n"
            "2. Each slide with provenance 'supplementary' does not contradict the sources.\n"
            "3. The slides are clear and on topic.\n\n"
            'Return JSON like {"passed": true, "issues": [{"slide_id": "...", "problem": "..."}]}. '
            "Set passed to false only if there is a real grounding problem, not for small style points."
        )},
    ]
    report = chat_json(messages)
    if "passed" not in report:
        report["passed"] = True
    report.setdefault("issues", [])
    return report
