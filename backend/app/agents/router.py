# The Router. It reads the learner's free text and decides what they want.
# It is a classifier, not a dispatcher: it does not call other agents, it
# just writes its decision (intent and target). The graph routes on that.
#
# It has tools to look things up so it can resolve a reference on its own:
# list_decks to find which deck, and list_versions to find which version to
# revert to when the learner says "undo" or "go back".

from app.agents.agent_loop import run_agent
from app.store.models import Artifact, StudyUnit, ArtifactVersion

TOOLS = [
    {"type": "function", "function": {
        "name": "list_decks",
        "description": "List the decks in this course, with their slide headings.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "list_versions",
        "description": "List the version history of a deck, newest last, with what caused each version.",
        "parameters": {
            "type": "object",
            "properties": {"artifact_id": {"type": "string"}},
            "required": ["artifact_id"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Record the decision.",
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "enum": ["new_topic", "evolve", "revert", "answer", "clarify"],
                },
                "target": {
                    "type": "object",
                    "description": "For evolve: artifact_id and slide_ids. For revert: artifact_id and version_id. For new_topic: topic.",
                    "properties": {
                        "artifact_id": {"type": "string"},
                        "slide_ids": {"type": "array", "items": {"type": "string"}},
                        "version_id": {"type": "string"},
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

    def list_versions(args):
        rows = (
            session.query(ArtifactVersion)
            .filter(ArtifactVersion.artifact_id == args.get("artifact_id"))
            .order_by(ArtifactVersion.version_number)
            .all()
        )
        return {"versions": [
            {"version_id": v.id, "version_number": v.version_number, "caused_by": v.caused_by}
            for v in rows
        ]}

    system = (
        "You decide what a student wants from one chat message in a learning app. "
        "Choose one intent: new_topic (the student asks you to teach, cover, or make slides or a "
        "lesson on something), evolve (change an existing deck, for example explain deeper, simplify, "
        "add an example, reorder, edit), revert (undo or go back to an earlier version of a deck), "
        "answer (a question that a chat reply can handle without building a deck, such as what does "
        "X mean, how does X differ from Y, why does X happen, or a question about a slide), "
        "or clarify (the request is unclear). "
        "Building a deck is slow, so only pick new_topic when the student wants a lesson or slides, "
        "not for a question they want answered. "
        "A tutor agent writes the reply for answer and clarify, so leave message empty for those, "
        "or use it for a short note on what you think they mean. "
        "Use list_decks to find which deck the student means, and list_versions to pick which version "
        "to revert to. For revert, put the chosen version_id in target. Then call finish."
    )
    user = (
        f"Student message: {request.get('text')}\n"
        f"Focused deck id, if the UI set one: {request.get('artifact_id')}\n"
        f"Focused slides, if any: {request.get('target_slide_ids')}\n"
    )
    result = run_agent(system, user, TOOLS, {"list_decks": list_decks, "list_versions": list_versions}, max_steps=5)

    if "intent" not in result:
        result = {"intent": "evolve" if request.get("artifact_id") else "new_topic", "target": {}}
    result.setdefault("target", {})
    return result
