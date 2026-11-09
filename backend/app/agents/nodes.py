# The graph nodes. Each node takes the turn state and the session and
# returns the fields it wants to update. The nodes are thin wrappers now:
# the real work happens inside the agents they call. The agents never call
# each other, they hand off through this shared state.

from app.agents import router as router_agent
from app.agents.planner import plan_topic
from app.agents.builder import run_builder
from app.agents.critic import review
from app.agents.memory import update_notes
from app.agents.qa import answer as answer_question
from app.store.versioning import revert_to
from app.store.models import StudyUnit, Artifact, ArtifactVersion, Message, LearnerModel, Chunk

MAX_ATTEMPTS = 3


def router(state: dict, session) -> dict:
    # decide intent and target from the free text. writes a decision only.
    decision = router_agent.route(session, state["course_id"], state["request"])
    out = {"intent": decision.get("intent", "new_topic"),
           "target": decision.get("target", {}),
           "retries": 0}
    if decision.get("message"):
        out["response"] = decision["message"]
    return out


def route_after_router(state: dict) -> str:
    # answer and clarify turns go to the QA agent and reply with no deck;
    # revert goes to its own node; everything else runs the build pipeline.
    intent = state.get("intent")
    if intent in ("answer", "clarify"):
        return "qa"
    if intent == "revert":
        return "revert"
    return "planner"


def revert(state: dict, session) -> dict:
    # go back to an earlier version. the router already decided which one.
    # if it did not name a version, treat it as "undo" and use the parent of
    # the current version.
    artifact = session.get(Artifact, _artifact_id(state))
    target = state.get("target", {})

    target_version = None
    if target.get("version_id"):
        target_version = session.get(ArtifactVersion, target["version_id"])
    if target_version is None:
        current = session.get(ArtifactVersion, artifact.current_version_id)
        target_version = (
            session.get(ArtifactVersion, current.parent_version_id)
            if current.parent_version_id else current
        )

    new_version = revert_to(session, artifact, target_version)
    session.add(Message(
        course_id=state["course_id"],
        role="system",
        text=f"Reverted {artifact.title} to v{target_version.version_number}",
        related_artifact_id=artifact.id,
        related_version_id=new_version.id,
    ))
    session.commit()

    return {"final_version": {
        "artifact_id": artifact.id,
        "version_id": new_version.id,
        "version_number": new_version.version_number,
        "content": new_version.content,
    }}


def qa(state: dict, session) -> dict:
    # answer and clarify turns. the QA agent searches the material and
    # replies in chat with citations, or asks one clarifying question. no
    # deck is built. save the reply with its citations as a system message.
    course_id = state["course_id"]
    req = state["request"]
    question = req["text"]
    if req.get("target_slide_ids"):
        question += f"\n(The student is looking at slides: {req['target_slide_ids']})"

    _, notes = _learner_context(session, course_id)
    reply = answer_question(
        session,
        course_id,
        question,
        intent=state.get("intent", "answer"),
        router_note=state.get("response", ""),
        learner_notes=notes,
    )
    session.add(Message(
        course_id=course_id,
        role="system",
        text=reply["text"],
        citations={"items": reply["citations"], "uses_general_knowledge": reply["uses_general_knowledge"]},
    ))
    session.commit()

    if reply["kind"] == "answer":
        update_notes(session, course_id, req["text"], "none, answered in chat")

    return {
        "response": reply["text"],
        "answer_citations": reply["citations"],
        "uses_general_knowledge": reply["uses_general_knowledge"],
    }


def planner(state: dict, session) -> dict:
    # plan the lesson substance and gather the chunks it rests on.
    req = state["request"]
    target = state.get("target", {})
    course_id = state["course_id"]
    profile, notes = _learner_context(session, course_id)

    if state["intent"] == "evolve":
        artifact = session.get(Artifact, _artifact_id(state))
        unit = session.get(StudyUnit, artifact.study_unit_id)
        plan = plan_topic(session, course_id, unit.topic, notes, instruction=req["text"], learner_profile=profile)
    else:
        topic = target.get("topic") or req["text"]
        plan = plan_topic(session, course_id, topic, notes, instruction=req["text"], learner_profile=profile)

    chunk_ids = []
    for point in plan.get("points", []):
        chunk_ids.extend(point.get("chunk_ids", []))
    chunks = _load_chunks(session, list(dict.fromkeys(chunk_ids)))
    return {"plan_slice": plan, "retrieved_chunks": chunks}


def builder(state: dict, session) -> dict:
    # render or edit the deck on a working copy. on a retry it starts from
    # the last draft and gets the critic notes to fix the problems.
    intent = state["intent"]
    retries = state.get("retries", 0) + 1
    report = state.get("critic_report") or {}
    issues = report.get("issues") if not report.get("passed", True) else None

    if state.get("draft_deck"):
        base = state["draft_deck"]
    elif intent == "evolve":
        artifact = session.get(Artifact, _artifact_id(state))
        current = session.get(ArtifactVersion, artifact.current_version_id)
        base = dict(current.content)
    else:
        base = None

    deck = run_builder(
        session,
        state["course_id"],
        plan=state.get("plan_slice", {}),
        chunks=state.get("retrieved_chunks", []),
        base_deck=base,
        instruction=state["request"]["text"],
        intent=intent,
        issues=issues,
    )
    return {"draft_deck": deck, "retries": retries}


def critic(state: dict, session) -> dict:
    report = review(session, state["course_id"], state.get("draft_deck", {}))
    return {"critic_report": report}


def route_after_critic(state: dict) -> str:
    report = state.get("critic_report", {})
    if report.get("passed"):
        return "finalize"
    if state.get("retries", 0) >= MAX_ATTEMPTS:
        return "finalize"
    return "builder"


def finalize(state: dict, session) -> dict:
    # commit the draft as a new immutable version, move the pointer, and
    # update the learner notes.
    deck = state["draft_deck"]

    if state["intent"] == "evolve":
        artifact = session.get(Artifact, _artifact_id(state))
        current = session.get(ArtifactVersion, artifact.current_version_id)
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=current.version_number + 1,
            parent_version_id=current.id,
            content=deck,
            critic_report=state["critic_report"],
            caused_by=state["request"]["text"][:40],
        )
    else:
        unit = StudyUnit(
            course_id=state["course_id"],
            topic=deck.get("title", state["plan_slice"].get("topic", "Untitled")),
            lesson_plan=state["plan_slice"],
        )
        session.add(unit)
        session.commit()
        artifact = Artifact(study_unit_id=unit.id, type="slides", title=unit.topic)
        session.add(artifact)
        session.commit()
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=1,
            parent_version_id=None,
            content=deck,
            critic_report=state["critic_report"],
            caused_by="generate",
        )

    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.commit()

    session.add(Message(
        course_id=state["course_id"],
        role="system",
        text=f"Updated {artifact.title}",
        related_artifact_id=artifact.id,
        related_version_id=version.id,
    ))
    session.commit()

    update_notes(session, state["course_id"], state["request"]["text"], artifact.title)

    return {"final_version": {
        "artifact_id": artifact.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content": deck,
    }}


def _artifact_id(state: dict) -> str:
    return state.get("target", {}).get("artifact_id") or state["request"].get("artifact_id")


def _load_chunks(session, chunk_ids):
    if not chunk_ids:
        return []
    rows = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    return [{"id": c.id, "text": c.text, "location": c.location} for c in rows]


def _learner_context(session, course_id: str) -> tuple[dict, str]:
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    return (row.profile or {}, row.notes or "") if row else ({}, "")
