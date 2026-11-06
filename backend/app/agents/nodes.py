# The nodes of the agent graph. Each node takes the turn state and the
# database session and returns the fields it wants to update in the state.
#
# The orchestrator routes, the planner shapes the substance, the builder
# renders slides with its tools, and the critic checks them. A failed check
# sends the builder back with the critic notes, up to a cap. The finalize
# node commits the finished draft as one new immutable version.

from app.ingest.retrieve import retrieve_scored
from app.store.models import StudyUnit, Artifact, ArtifactVersion, Message, LearnerModel
from app.agents.planner import plan_topic
from app.agents.builder import run_builder
from app.agents.critic import review

# the most build attempts before we give up and deliver the best draft.
MAX_ATTEMPTS = 3


def orchestrator(state: dict, session) -> dict:
    # decide what the learner wants. for now the rule is simple: if the
    # request points at an existing artifact it is an edit, otherwise it is
    # a new topic. a later phase reads the free text to classify intent.
    req = state["request"]
    if req.get("artifact_id"):
        return {"intent": "evolve", "retries": 0}
    return {"intent": "new_topic", "retries": 0}


def planner(state: dict, session) -> dict:
    # work out the topic, pull the chunks that cover it, and for a new topic
    # plan the lesson substance.
    req = state["request"]
    course_id = state["course_id"]

    if state["intent"] == "evolve":
        artifact = session.get(Artifact, req["artifact_id"])
        unit = session.get(StudyUnit, artifact.study_unit_id)
        topic = unit.topic
        scored = retrieve_scored(session, course_id, f"{topic}. {req['text']}", k=5)
        plan = {"topic": topic, "instruction": req["text"], "chunk_ids": [c.id for c, _ in scored]}
    else:
        topic = req["text"]
        scored = retrieve_scored(session, course_id, topic, k=6)
        brief = [{"id": c.id, "text": c.text} for c, _ in scored]
        plan = plan_topic(topic, brief, _learner_notes(session, course_id))

    chunks = [{"id": c.id, "text": c.text, "location": c.location} for c, _ in scored]
    return {"plan_slice": plan, "retrieved_chunks": chunks}


def builder(state: dict, session) -> dict:
    # render or edit the deck on a working copy. on a retry it starts from
    # the last draft and gets the critic notes so it can fix the problems.
    req = state["request"]
    intent = state["intent"]
    retries = state.get("retries", 0) + 1

    report = state.get("critic_report") or {}
    issues = report.get("issues") if not report.get("passed", True) else None

    if state.get("draft_deck"):
        base = state["draft_deck"]
    elif intent == "evolve":
        artifact = session.get(Artifact, req["artifact_id"])
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
        instruction=req["text"],
        intent=intent,
        issues=issues,
    )
    return {"draft_deck": deck, "retries": retries}


def critic(state: dict, session) -> dict:
    # check the draft against the source chunks. returns passed plus any
    # problems for the builder to fix.
    report = review(state.get("draft_deck", {}), state.get("retrieved_chunks", []))
    return {"critic_report": report}


def route_after_critic(state: dict) -> str:
    # pass goes to finalize. a fail goes back to the builder, until we hit
    # the attempt cap, then we finalize with the best draft we have.
    report = state.get("critic_report", {})
    if report.get("passed"):
        return "finalize"
    if state.get("retries", 0) >= MAX_ATTEMPTS:
        return "finalize"
    return "builder"


def finalize(state: dict, session) -> dict:
    # commit the draft deck as a new immutable version and move the current
    # pointer. a new topic also creates the study unit and the artifact.
    req = state["request"]
    deck = state["draft_deck"]

    if state["intent"] == "evolve":
        artifact = session.get(Artifact, req["artifact_id"])
        current = session.get(ArtifactVersion, artifact.current_version_id)
        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=current.version_number + 1,
            parent_version_id=current.id,
            content=deck,
            critic_report=state["critic_report"],
            caused_by=req["text"][:40],
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

    return {"final_version": {
        "artifact_id": artifact.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content": deck,
    }}


def _learner_notes(session, course_id: str) -> str:
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    return row.notes if row and row.notes else ""
