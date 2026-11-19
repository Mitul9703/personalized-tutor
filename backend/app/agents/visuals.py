# A small, shared helper for the optional visual a slide or a doc section can
# carry: a Mermaid diagram or an inline SVG the agent writes. This keeps only
# well-formed visuals and drops anything suspicious. The frontend sanitizes the
# SVG again with DOMPurify before it renders, so this is a light server-side
# guard, not the only line of defence.

# The visual block, shared by the slide and doc generators:
#   {"format": "svg" | "mermaid", "code": "...", "caption": "..."}
VISUAL_SCHEMA = {
    "type": "object",
    "description": (
        "Optional diagram for this item. Add one only when a picture genuinely helps "
        "understanding. 'mermaid' for a flow, cycle, or how things connect (for example "
        "'flowchart TD; A[Light] --> B[PSII]'); 'svg' for a complete, self-contained "
        "<svg> with a viewBox, simple shapes, text labels, and colour. Keep it small and "
        "readable: a handful of nodes in a top-down flow (flowchart TD), short plain labels, "
        "and avoid wide rows or deeply nested subgraphs. No scripts, click events, HTML "
        "labels, or external references."
    ),
    "properties": {
        "format": {"type": "string", "enum": ["svg", "mermaid"]},
        "code": {"type": "string", "description": "Mermaid source, or a complete <svg>...</svg> element."},
        "caption": {"type": "string", "description": "A short caption under the diagram."},
    },
    "required": ["format", "code"],
}

_BAD_SVG = ("<script", "onload", "onclick", "onerror", "<foreignobject", "javascript:")


def clean_visual(v):
    # returns a cleaned visual dict, or None if it is missing or malformed.
    if not isinstance(v, dict):
        return None
    fmt = v.get("format")
    code = (v.get("code") or "").strip()
    if fmt not in ("svg", "mermaid") or not code:
        return None
    if fmt == "svg":
        low = code.lower()
        if "<svg" not in low or any(bad in low for bad in _BAD_SVG):
            return None
    out = {"format": fmt, "code": code}
    caption = (v.get("caption") or "").strip()
    if caption:
        out["caption"] = caption
    return out
