"""Paper-aligned anonymous quality estimates and independent grounding/citations."""
from questions import ask_json

QUALITY = ("alignment", "appropriateness", "accuracy")


def judge_deck(deck, doc_text, topic, profile):
    view = [{"index": i, **{k: s.get(k) for k in ("heading", "bullets", "notes", "provenance")}} for i, s in enumerate(deck["slides"])]
    return ask_json(
        'Evaluate this anonymous lesson against the source, topic, and profile. Include headings, '
        'bullets, and accessible notes. For each slide, supported=true only if ALL substantive source '
        'claims follow from the source. Supplementary content may extend it but must not contradict it. '
        'Rate topic alignment, learner appropriateness, and accuracy separately, with reasons. '
        'Revision-effort anchors: 1 complete redevelopment, 2 major rewriting, 3 moderate revisions, '
        '4 minor revisions, 5 minimal edits. Return JSON {"items":[{"index":0,"supported":true,'
        '"reason":"..."}],"quality":{"alignment":{"score":3,"reason":"..."},'
        '"appropriateness":{"score":3,"reason":"..."},"accuracy":{"score":3,"reason":"..."}}}.',
        {"source": doc_text, "topic": topic, "profile": profile, "lesson": view})


def score_judgment(deck, value):
    value = value if isinstance(value, dict) else {}
    source_indices = [i for i, s in enumerate(deck["slides"]) if s["provenance"] == "source"]
    result = {"grounded": None, "supported_slides": None, "source_slides": len(source_indices), "quality": None, "quality_scores": {}}
    rows = value.get("items")
    if isinstance(rows, list) and len(rows) == len(deck["slides"]) and all(isinstance(r, dict) and r.get("index") == i and type(r.get("supported")) is bool and r.get("reason") for i, r in enumerate(rows)):
        result["supported_slides"] = sum(rows[i]["supported"] for i in source_indices)
        if source_indices:
            result["grounded"] = result["supported_slides"] / len(source_indices)
    quality = value.get("quality")
    for name in QUALITY:
        row = quality.get(name) if isinstance(quality, dict) else None
        result["quality_scores"][name] = row["score"] if isinstance(row, dict) and type(row.get("score")) is int and 1 <= row["score"] <= 5 and row.get("reason") else None
    if all(v is not None for v in result["quality_scores"].values()):
        result["quality"] = sum(result["quality_scores"].values()) / 3
    return result


def citation_stats(deck, resolve):
    source = [s for s in deck["slides"] if s["provenance"] == "source"]
    cited = sum(isinstance(s.get("citations"), list) and bool(s["citations"]) for s in source)
    entries = []
    for slide in deck["slides"]:
        value = slide.get("citations", [])
        entries.extend(value if isinstance(value, list) else [None])
    valid = sum(isinstance(c, dict) and isinstance(c.get("chunk_id"), str) and bool(c["chunk_id"]) and resolve(c["chunk_id"]) for c in entries)
    return {"citation_coverage": cited / len(source) if source else None, "cited_source_slides": cited,
            "citation_source_slides": len(source), "citation_validity": valid / len(entries) if entries else None,
            "valid_citations": valid, "citation_entries": len(entries)}
