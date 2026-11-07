# The LLM judge. It grades a slide deck against the source material it should
# be based on. We use it the same way for our system and the baseline, with a
# fixed rubric, so the scores are comparable. For grounding it only counts
# slides the deck itself marks as "source", so honestly-labeled supplementary
# content is not penalized.

import json

from app.llm.chat import chat_json

JUDGE_DOC_CHARS = 60000


def judge_deck(deck: dict, doc_text: str) -> dict:
    slides = deck.get("slides", [])
    view = [
        {"heading": s.get("heading", ""), "bullets": s.get("bullets", []),
         "provenance": s.get("provenance", "source")}
        for s in slides
    ]
    messages = [
        {"role": "system", "content": (
            "You grade a slide deck against the source material it is supposed to be based on. "
            "Be strict and fair. Return JSON only."
        )},
        {"role": "user", "content": (
            f"SOURCE MATERIAL (may be truncated):\n{doc_text[:JUDGE_DOC_CHARS]}\n\n"
            f"SLIDE DECK (each slide carries a provenance tag):\n{json.dumps(view)}\n\n"
            "Grade it and return JSON with these fields:\n"
            '- "supported_source_slides": of the slides marked provenance "source", how many make '
            "claims that are actually supported by the source material.\n"
            '- "total_source_slides": how many slides are marked provenance "source".\n'
            '- "clarity": 1-5, how easy the deck is to follow.\n'
            '- "correctness": 1-5, factual accuracy of the content.\n'
            '- "coverage": 1-5, how well it covers the key points of the topic.\n'
            '- "overall": 1-5, overall teaching quality.'
        )},
    ]
    r = chat_json(messages)
    # fill any missing fields defensively
    r.setdefault("total_source_slides", sum(1 for s in view if s["provenance"] == "source"))
    r.setdefault("supported_source_slides", 0)
    for k in ("clarity", "correctness", "coverage", "overall"):
        r.setdefault(k, 0)
    return r


def groundedness(judgement: dict):
    total = judgement.get("total_source_slides", 0) or 0
    if total == 0:
        return None
    return judgement.get("supported_source_slides", 0) / total


def citation_coverage(deck: dict):
    # objective, no judge: of slides marked source, how many carry a citation.
    source = [s for s in deck.get("slides", []) if s.get("provenance", "source") == "source"]
    if not source:
        return None
    cited = sum(1 for s in source if s.get("citations"))
    return cited / len(source)


def citation_validity(deck: dict, resolve):
    # Stronger than coverage: of all the citations in the deck, what fraction
    # point to a real, retrievable chunk? `resolve(chunk_id)` returns True if
    # the chunk exists in the store. Our citations resolve; a baseline that
    # invents citation text does not. A deck with no citations returns None.
    ids = []
    for s in deck.get("slides", []):
        for c in s.get("citations", []):
            cid = c.get("chunk_id") if isinstance(c, dict) else None
            if cid:
                ids.append(cid)
    if not ids:
        return None
    good = sum(1 for cid in ids if resolve(cid))
    return good / len(ids)
