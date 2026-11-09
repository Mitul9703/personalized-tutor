# Baselines for Section 3. Both use the same chat model (gpt-6-luna) as our
# system, so any difference is architectural.
#
# B1 - single LLM call with the whole document in the prompt. No retrieval,
#   no critic, no learner model, no interaction. Isolates what our whole
#   agentic pipeline adds over just prompting the model with the material.
#
# B2 - RAG + single generation. Retrieve the most relevant chunks (same local
#   embedding model our system uses), then make the deck in one call from
#   those chunks. No planner, no critic, no learner model, no interaction.
#   This is the sharper comparison: it isolates what our plan -> build ->
#   critique loop adds over plain retrieval + one generation.

import json

from app.llm.chat import chat_json
from app.llm.embeddings import embed

# gpt-6-luna has a very large context, but the single-call baseline still
# truncates very long documents, which is the honest limit of "just paste the
# whole thing". Our system and the RAG baseline retrieve instead.
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


# ---------------- B2: RAG + single generation ----------------

def _local_chunks(doc_text: str, target_chars: int = 1000) -> list[str]:
    # simple paragraph packing, close to what the real ingester does, but kept
    # self-contained so the baseline does not depend on the database.
    paras = [p.strip() for p in doc_text.split("\n\n") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 > target_chars and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _top_k(doc_text: str, topic: str, k: int) -> list[str]:
    chunks = _local_chunks(doc_text)
    if len(chunks) <= k:
        return chunks
    vecs = embed(chunks)
    qvec = embed([f"teach a student about: {topic}"])[0]
    scored = [(sum(a * b for a, b in zip(qvec, v)), i) for i, v in enumerate(vecs)]
    scored.sort(reverse=True)
    keep = sorted(i for _, i in scored[:k])
    return [chunks[i] for i in keep]


def rag_baseline(doc_text: str, topic: str, k: int = 8) -> dict:
    material = "\n\n".join(_top_k(doc_text, topic, k))
    messages = [
        {"role": "system", "content": "You make a short slide deck to teach a student. Return JSON only."},
        {"role": "user", "content": (
            f"Here are the most relevant passages from the student's material:\n\n{material}\n\n"
            f"Make a slide deck that teaches: {topic}\n"
            'Return JSON shaped like {"title": "...", "slides": [{"heading": "...", '
            '"bullets": ["..."], "provenance": "source", "citations": []}]}. '
            "Use provenance 'source' for content grounded in the passages and 'supplementary' for "
            "anything you add from general knowledge beyond them."
        )},
    ]
    deck = chat_json(messages)
    if not isinstance(deck, dict):
        deck = {"title": topic, "slides": []}
    deck.setdefault("slides", [])
    return deck
