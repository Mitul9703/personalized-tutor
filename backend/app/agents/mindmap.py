# The mind map generator. A tool using agent built on run_agent, the same way
# as the slides Builder and the flashcards generator. It works on a working
# copy of the map, never the database. For a new map it usually calls set_map
# once. For an edit it uses the surgical tools (add, update, delete). It can
# call retrieve_more when a node needs more source material. When it is done it
# calls finish. The caller then saves the working copy as one new immutable
# version.
#
# A mind map is a rooted tree of concept nodes. One node is the root (the
# central topic, parent_id empty); every other node names an existing node as
# its parent. This file applies the model's edits and runs mechanical checks:
# the map stays a single rooted tree with no cycles, every parent exists, and a
# source node cites at least one real chunk. A failed check is returned to the
# model as a tool error so it can fix the node.
#
# run_mindmap_builder takes the same arguments as run_builder, so a caller can
# treat every content type the same way. base_deck is the current map when
# editing, or None for a new map.

import json

from app.agents.agent_loop import run_agent
from app.agents.visuals import VISUAL_SCHEMA, clean_visual
from app.ingest.retrieve import retrieve
from app.store.models import Chunk, Document, LearnerModel

MAX_STEPS = 10

_NODE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "short id like m1"},
        "label": {"type": "string", "description": "the concept name shown in the node, a few words"},
        "detail": {"type": "string", "description": "one short line explaining the concept, optional"},
        "parent_id": {
            "type": "string",
            "description": "the id of this node's parent. Leave empty for the single root (the central topic).",
        },
        "provenance": {"type": "string", "enum": ["source", "supplementary"]},
        "chunk_ids": {
            "type": "array", "items": {"type": "string"},
            "description": "ids of the source chunks that support this node. Empty for supplementary nodes.",
        },
        "visual": VISUAL_SCHEMA,
    },
    "required": ["label", "provenance"],
}

TOOLS = [
    {"type": "function", "function": {
        "name": "set_map",
        "description": "Replace the whole mind map. Use this to build a map from scratch. "
                       "Give exactly one root node with an empty parent_id; every other node's "
                       "parent_id must be another node in the list.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "nodes": {"type": "array", "items": _NODE_SCHEMA},
            },
            "required": ["title", "nodes"],
        },
    }},
    {"type": "function", "function": {
        "name": "add_node",
        "description": "Add one node under an existing parent.",
        "parameters": {
            "type": "object",
            "properties": {"node": _NODE_SCHEMA},
            "required": ["node"],
        },
    }},
    {"type": "function", "function": {
        "name": "update_node",
        "description": "Change fields on one node. Only pass the fields you want to change.",
        "parameters": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "label": {"type": "string"},
                "detail": {"type": "string"},
                "parent_id": {"type": "string"},
                "provenance": {"type": "string", "enum": ["source", "supplementary"]},
                "chunk_ids": {"type": "array", "items": {"type": "string"}},
                "visual": VISUAL_SCHEMA,
            },
            "required": ["node_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "delete_node",
        "description": "Remove one node by id. Its children move up to its parent.",
        "parameters": {
            "type": "object",
            "properties": {"node_id": {"type": "string"}},
            "required": ["node_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "retrieve_more",
        "description": "Search the source material for more chunks when a node needs grounding.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when the mind map is ready.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

SYSTEM = (
    "You build and edit a mind map for a student using the tools. A mind map is a tree of concept "
    "nodes: the root is the central topic, and each branch breaks it into sub-concepts, then details. "
    "Keep each label short (a few words) and put any one-line explanation in detail. A label or detail "
    "may include a short formula written as LaTeX inline math $...$. A node may also carry a small "
    "diagram (Mermaid or a self-contained SVG) when a picture helps that concept; add one only where it "
    "genuinely helps, not on every node. Build a map that "
    "is genuinely useful to revise from: cover the main ideas and how they connect, usually two or "
    "three levels deep. Ground nodes in the source chunks and list the chunk_ids that support each one. "
    "Mark anything beyond the sources as provenance 'supplementary' with no chunk_ids. If you are "
    "unsure the material supports a node, call retrieve_more before adding it. "
    "Use what is known about the learner to pick the depth and which branches to emphasise. "
    "If a tool returns an error, fix the node and try again. "
    "When editing an existing map, make the smallest change that satisfies the request: touch only the "
    "node or nodes the request is about and leave the rest of the map exactly as it is. "
    "Call finish when the map is ready."
)


def run_mindmap_builder(session, course_id, *, plan, chunks, base_deck, instruction, intent, issues=None):
    mind = base_deck if base_deck else {"title": plan.get("topic", "Untitled"), "nodes": []}
    mind.setdefault("nodes", [])
    _ensure_ids(mind)

    def make_handler(tool_name):
        return lambda args: _handle(tool_name, args, mind, session, course_id)

    handlers = {name: make_handler(name) for name in (
        "set_map", "add_node", "update_node", "delete_node", "retrieve_more",
    )}

    learner = _learner_context(session, course_id)
    user = _compose_task(plan, chunks, mind, instruction, intent, issues, learner)
    run_agent(SYSTEM, user, TOOLS, handlers, max_steps=MAX_STEPS)

    _ensure_ids(mind)
    return mind


def _compose_task(plan, chunks, mind, instruction, intent, issues, learner):
    sources = "\n\n".join(f"[{c['id']}] {c['text']}" for c in chunks) or "(no source chunks)"
    parts = [f"What we know about the learner:\n{learner or 'nothing yet'}\n"]
    if intent == "evolve":
        parts.append("Here is the current mind map as JSON:")
        parts.append(json.dumps(_for_model(mind)))
        parts.append(f"\nThe learner asked: {instruction}")
        parts.append(
            "Edit with the surgical tools (update_node, add_node, delete_node). Do not call set_map "
            "for an edit. Change only the node or nodes the request is about, and leave the rest of the "
            "map exactly as it is."
        )
    else:
        parts.append(f"Build a mind map for the topic: {plan.get('topic', instruction)}")
        if plan.get("objective"):
            parts.append(f"Objective: {plan['objective']}")
        if plan.get("points"):
            parts.append("Lesson plan points:")
            parts.append(json.dumps(plan["points"]))
        parts.append(f"The learner asked: {instruction}")
        parts.append("Build the whole map in one set_map call, then finish.")
    if issues:
        parts.append("\nA reviewer found these problems. Fix them:")
        parts.append(json.dumps(issues))
    parts.append("\nSource chunks (use these chunk ids on source nodes):")
    parts.append(sources)
    return "\n".join(parts)


def _for_model(mind):
    # show the model chunk_ids, the same field it writes, not the resolved citations.
    return {
        "title": mind.get("title", ""),
        "nodes": [
            {"id": n["id"], "label": n["label"], "detail": n.get("detail", ""),
             "parent_id": n.get("parent_id"), "provenance": n["provenance"],
             "chunk_ids": [x["chunk_id"] for x in n.get("citations", [])], "visual": n.get("visual")}
            for n in mind.get("nodes", [])
        ],
    }


def _handle(name, args, mind, session, course_id):
    nodes = mind.setdefault("nodes", [])

    if name == "set_map":
        built, errors = [], []
        for i, raw in enumerate(args.get("nodes", [])):
            node, error = _build_node(session, course_id, raw, f"m{i + 1}")
            if error:
                errors.append({"node": i + 1, "label": raw.get("label", ""), "error": error})
            else:
                built.append(node)
        if errors:
            return {"ok": False, "errors": errors, "hint": "fix these nodes and call set_map again"}
        tree_error = _check_tree(built)
        if tree_error:
            return {"ok": False, "error": tree_error, "hint": "a mind map must be one rooted tree"}
        mind["title"] = args.get("title", mind.get("title", "Untitled"))
        mind["nodes"] = built
        return {"ok": True, "nodes": len(built)}

    if name == "add_node":
        raw = args.get("node", {})
        node, error = _build_node(session, course_id, raw, _next_id(nodes))
        if error:
            return {"ok": False, "error": error}
        if node["id"] in _ids(nodes):
            node["id"] = _next_id(nodes)
        parent = node.get("parent_id")
        if not nodes:
            # first node: it must be the root
            node["parent_id"] = None
        elif not parent:
            return {"ok": False, "error": "this map already has a root; give the new node a parent_id",
                    "valid_ids": _ids(nodes)}
        elif _get(nodes, parent) is None:
            return {"ok": False, "error": f"parent {parent} not found", "valid_ids": _ids(nodes)}
        nodes.append(node)
        return {"ok": True, "node_id": node["id"]}

    if name == "update_node":
        node = _get(nodes, args.get("node_id"))
        if node is None:
            return {"ok": False, "error": f"node {args.get('node_id')} not found", "valid_ids": _ids(nodes)}
        new_parent = node.get("parent_id")
        if "parent_id" in args:
            new_parent = args["parent_id"] or None
            if new_parent is None and node.get("parent_id") is not None:
                return {"ok": False, "error": "a map has only one root; give this node a parent_id"}
            if new_parent is not None:
                if _get(nodes, new_parent) is None:
                    return {"ok": False, "error": f"parent {new_parent} not found", "valid_ids": _ids(nodes)}
                if new_parent == node["id"] or new_parent in _descendants(nodes, node["id"]):
                    return {"ok": False, "error": "that parent would make a cycle"}
        merged = {
            "id": node["id"],
            "label": args["label"] if args.get("label") is not None else node["label"],
            "detail": args["detail"] if args.get("detail") is not None else node.get("detail", ""),
            "parent_id": new_parent,
            "provenance": args["provenance"] if args.get("provenance") is not None else node["provenance"],
            "chunk_ids": (args["chunk_ids"] if args.get("chunk_ids") is not None
                          else [c["chunk_id"] for c in node.get("citations", [])]),
            "visual": args["visual"] if args.get("visual") is not None else node.get("visual"),
        }
        new_node, error = _build_node(session, course_id, merged, node["id"])
        if error:
            return {"ok": False, "error": error}
        node.update(new_node)
        return {"ok": True}

    if name == "delete_node":
        node = _get(nodes, args.get("node_id"))
        if node is None:
            return {"ok": False, "error": f"node {args.get('node_id')} not found", "valid_ids": _ids(nodes)}
        children = [n for n in nodes if n.get("parent_id") == node["id"]]
        if node.get("parent_id") is None and len(children) > 1:
            return {"ok": False, "error": "cannot delete the root while it has more than one branch; "
                                          "delete or move the branches first"}
        # children move up to the deleted node's parent (None if it was the root)
        for child in children:
            child["parent_id"] = node.get("parent_id")
        nodes.remove(node)
        return {"ok": True}

    if name == "retrieve_more":
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"ok": True, "chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    if name == "finish":
        return {"ok": True}

    return {"ok": False, "error": f"unknown tool {name}"}


def _build_node(session, course_id, raw, default_id):
    # mechanical checks only. returns (node, error).
    provenance = raw.get("provenance", "source")
    if provenance not in ("source", "supplementary"):
        return None, "provenance must be 'source' or 'supplementary'"
    if not raw.get("label"):
        return None, "a node needs a label"
    citations = []
    if provenance == "source":
        citations, error = _resolve_citations(session, course_id, raw.get("chunk_ids") or [])
        if error:
            return None, error
        if not citations:
            return None, "a source node must list at least one chunk id from the material"
    parent = raw.get("parent_id")
    return {
        "id": raw.get("id") or default_id,
        "label": raw["label"],
        "detail": raw.get("detail", ""),
        "parent_id": parent if parent else None,
        "provenance": provenance,
        "citations": citations,
        "visual": clean_visual(raw.get("visual")),
    }, None


def _check_tree(nodes):
    # the whole node set must be one rooted tree: exactly one root, every
    # parent exists, and no cycles. returns an error string or None.
    if not nodes:
        return "a mind map needs at least a root node"
    ids = {n["id"] for n in nodes}
    roots = [n for n in nodes if not n.get("parent_id")]
    if len(roots) != 1:
        return f"a mind map needs exactly one root (a node with no parent), found {len(roots)}"
    for n in nodes:
        parent = n.get("parent_id")
        if parent and parent not in ids:
            return f"node {n['id']} names a parent {parent} that is not in the map"
    # every node must reach the root without looping
    root_id = roots[0]["id"]
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        seen, cur = set(), n["id"]
        while cur and cur != root_id:
            if cur in seen:
                return "the map has a cycle; every node must lead back to the root"
            seen.add(cur)
            cur = by_id[cur].get("parent_id")
    return None


def _descendants(nodes, node_id):
    # ids of every node under node_id, so a reparent cannot point into its own subtree.
    out, stack = set(), [node_id]
    while stack:
        cur = stack.pop()
        for n in nodes:
            if n.get("parent_id") == cur and n["id"] not in out:
                out.add(n["id"])
                stack.append(n["id"])
    return out


def _resolve_citations(session, course_id, chunk_ids):
    ids = list(dict.fromkeys(chunk_ids))
    if not ids:
        return [], None
    rows = (
        session.query(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.course_id == course_id, Chunk.id.in_(ids))
        .all()
    )
    found = {chunk.id: (chunk, filename) for chunk, filename in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        return None, f"these chunk ids do not exist in the material: {missing}. Use retrieve_more to find real ones."
    return [{"chunk_id": i, "doc": found[i][1], "loc": _loc(found[i][0].location)} for i in ids], None


def _loc(location):
    location = location or {}
    if location.get("page") is not None:
        return f"p.{location['page']}"
    return str(location.get("section") or "")


def _learner_context(session, course_id: str) -> str:
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    if row is None:
        return ""
    parts = []
    if row.profile:
        parts.append(f"Profile (self-reported): {json.dumps(row.profile, ensure_ascii=False)}")
    if row.notes:
        parts.append(f"Notes: {row.notes}")
    return "\n".join(parts)


def _ensure_ids(mind: dict):
    for i, node in enumerate(mind.get("nodes", [])):
        if not node.get("id"):
            node["id"] = f"m{i + 1}"


def _next_id(nodes):
    taken = set(_ids(nodes))
    n = len(nodes) + 1
    while f"m{n}" in taken:
        n += 1
    return f"m{n}"


def _ids(nodes):
    return [n["id"] for n in nodes]


def _get(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n
    return None
