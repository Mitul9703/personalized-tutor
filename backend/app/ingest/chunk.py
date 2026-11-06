# Split parsed segments into medium sized chunks. We split on paragraph and
# sentence boundaries so a chunk never cuts a word in half, and we pack
# paragraphs together up to a target size. Each chunk keeps the verbatim
# text and its character span so a citation can point at the exact words.

import re

# target and minimum chunk sizes in characters.
TARGET_CHARS = 1000
MIN_CHARS = 200


def _find_ranges(text: str, pieces: list[str], cursor: int = 0) -> list[tuple]:
    # locate each piece in order and return its (start, end) range in text.
    ranges = []
    for piece in pieces:
        start = text.find(piece, cursor)
        if start < 0:
            start = cursor
        end = start + len(piece)
        ranges.append((start, end))
        cursor = end
    return ranges


def _units(text: str) -> list[tuple]:
    # the small pieces we pack into chunks. paragraphs by default, and any
    # paragraph bigger than the target is split into sentences first.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units = []
    for (p_start, p_end) in _find_ranges(text, paragraphs):
        if p_end - p_start <= TARGET_CHARS:
            units.append((p_start, p_end))
            continue
        para_text = text[p_start:p_end]
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para_text) if s.strip()]
        units.extend(_find_ranges(text, sentences, p_start))
    return units


def _pack(units: list[tuple]) -> list[tuple]:
    # group unit ranges into chunks up to the target size. fold a tiny last
    # chunk into the one before it.
    if not units:
        return []
    chunks = []
    cur_start, cur_end = units[0]
    for (start, end) in units[1:]:
        if end - cur_start > TARGET_CHARS:
            chunks.append((cur_start, cur_end))
            cur_start, cur_end = start, end
        else:
            cur_end = end
    chunks.append((cur_start, cur_end))

    if len(chunks) >= 2 and (chunks[-1][1] - chunks[-1][0]) < MIN_CHARS:
        last = chunks.pop()
        prev = chunks.pop()
        chunks.append((prev[0], last[1]))
    return chunks


def chunk_segments(segments: list[dict]) -> list[dict]:
    # returns a list of chunks:
    # { "text", "ordinal", "location": { "page", "char_span": [start, end] } }
    chunks = []
    ordinal = 0
    for seg in segments:
        text = seg["text"]
        page = seg["page"]
        for (start, end) in _pack(_units(text)):
            chunks.append({
                "text": text[start:end],
                "ordinal": ordinal,
                "location": {"page": page, "char_span": [start, end]},
            })
            ordinal += 1
    return chunks
