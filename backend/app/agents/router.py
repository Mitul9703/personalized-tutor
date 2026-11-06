# The Router. It reads the learner's free text and decides what they want.
# It is a classifier, not a dispatcher: it does not call other agents, it
# just writes its decision (intent and target). The graph routes on that.
#
# It has a list_decks tool so it can look up existing decks and resolve a
# reference like "the momentum slide" or "slide 3" on its own.

from app.agents.agent_loop import run_agent
from app.store.models import Artifact, StudyUnit, ArtifactVersion

TOOLS = [
    {"type": "function", "function": {
        "name": "list_decks",
        "description": "List the decks that already exist in this course, with their slide headings.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Record the decision.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["new_topic", "evolve", "answer", "clarify"],
                },
                "target": {
                    "type": "object",
                    "description": "For evolve: artifact_id and slide_ids. For new_topic: topic.",
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "slide_ids": {"type": "array", "items": {"type": "string"}},
                        "span": {"type": "string"},
                        "topic": {"type": "string"},
                    },
                },
                "message": {
                    "type": "string",
                    "description": "For answer or clarify: the text to send the learner.",
                },
            },
            "required": ["intent"],
        },
    }},
]


def route(session, course_id, request):
    def list_decks(_args):
        rows = (
            session.query(Artifact)
            .join(StudyUnit, Artifact.study_unit_id == StudyUnit.id)
            .filter(StudyUnit.course_id == course_id)
            .all()
        )
        decks = []
        for art in rows:
            headings = []
            if art.current_version_id:
                version = session.get(ArtifactVersion, art.current_version_id)
                if version:
                    headings = [s.get("heading") for s in version.content.get("slides", [])]
            decks.append({"artifact_id": art.id, "title": art.title, "slide_headings": headings})
        return {"decks": decks}

    system = (
        "You decide what a student wants from one chat message in a learning app. "
        "Choose one intent: new_topic (teach something new), evolve (change an existing deck, "
        "for example explain deeper, simplify, add an example, edit), answer (a plain question you "
        "can answer in chat with no deck), or clarify (the request is unclear, ask one short question). "
        "Use list_decks if you need to resolve which deck or slide the student means. "
        "Then call finish with the intent and target."
    )
    user = (
        f"Student message: {request.get('text')}\n"
        f"Focused deck id, if the UI set one: {request.get('artifact_id')}\n"
        f"Focused slides, if any: {request.get('target_slide_ids')}\n"
    )
    result = run_agent(system, user, TOOLS, {"list_decks": list_decks}, max_steps=4)

    # safety fallback if the model stopped without a clean decision
    if "intent" not in result:
        result = {"intent": "evolve" if request.get("artifact_id") else "new_topic", "target": {}}
    result.setdefault("target", {})
    return result
