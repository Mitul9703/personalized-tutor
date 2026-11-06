# The nodes of the agent graph. Each node takes the turn state and the
# database session and returns the fields it wants to update in the state.
#
# For this phase the builder and critic are stubs. The builder returns a
# fake deck and the critic always passes. The point right now is to get the
# flow and the versioning right. The real builder and critic come next.

from app.ingest.retrieve import retrieve_scored
from app.store.models import StudyUnit, Artifact, ArtifactVersion, Message


def orchestrator(state: dict, session) -> dict:
    # decide what the learner wants. for now the rule is simple: if the
    # request points at an existing artifact it is an edit, otherwise it is
    # a new topic. a later phase reads the free text to classify intent.
    req = state["request"]
    if req.get("artifact_id"):
        return {"intent": "evolve", "retries": 0}
    return {"intent": "new_topic", "retries": 0}


def planner(state: dict, session) -> dict:
    # work out the topic and pull the chunks that cover it. this is the
    # substance the builder will render.
    req = state["request"]
    if state["intent"] == "evolve":
        artifact = session.get(Artifact, req["artifact_id"])
        unit = session.get(StudyUnit, artifact.study_unit_id)
        topic = unit.topic
    else:
        topic = req["text"]

    scored = retrieve_scored(session, state["course_id"], topic, k=5)
    plan = {
        "topic": topic,
        "objective": f"Understand {topic}",
        "chunk_ids": [c.id for c, _ in scored],
    }
    chunks = [{"id": c.id, "text": c.text, "location": c.location} for c, _ in scored]
    return {"plan_slice": plan, "retrieved_chunks": chunks}


def builder(state: dict, session) -> dict:
    # STUB builder. makes a fake deck so we can test the flow and the
    # versioning. for an edit it starts from the current deck and adds a
    # slide so the new version clearly differs from its parent.
    plan = state["plan_slice"]
    req = state["request"]
    citations = [{"chunk_id": cid, "doc": "", "loc": ""} for cid in plan["chunk_ids"][:2]]

    if state["intent"] == "evolve":
        artifact = session.get(Artifact, req["artifact_id"])
        current = session.get(ArtifactVersion, artifact.current_version_id)
        deck = dict(current.content)
        slides = list(deck.get("slides", []))
        slides.append({
            "id": f"s{len(slides) + 1}",
            "heading": f"Update: {req['text']}",
            "bullets": ["(stub) this slide was added by the stub builder"],
            "notes": "",
            "provenance": "source",
            "citations": citations,
            "level": "standard",
        })
        deck["slides"] = slides
    else:
        deck = {
            "title": plan["topic"],
            "slides": [
                {
                    "id": "s1",
                    "heading": plan["topic"],
                    "bullets": ["(stub) overview slide"],
                    "notes": "",
                    "provenance": "source",
                    "citations": citations,
                    "level": "intro",
                },
                {
                    "id": "s2",
                    "heading": "Key points",
                    "bullets": ["(stub) point one", "(stub) point two"],
                    "notes": "",
                    "provenance": "source",
                    "citations": citations,
                    "level": "standard",
                },
            ],
        }
    return {"draft_deck": deck}


def critic(state: dict, session) -> dict:
    # STUB critic. always passes for now. the real one checks grounding,
    # labels, and level, and can send the builder back.
    return {"critic_report": {"passed": True, "notes": "stub critic, always passes"}}


def route_after_critic(state: dict) -> str:
    # pass goes to finalize. a fail would go back to the builder, up to two
    # retries, then finalize with whatever we have.
    report = state.get("critic_report", {})
    if report.get("passed"):
        return "finalize"
    if state.get("retries", 0) >= 2:
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
            topic=state["plan_slice"]["topic"],
            lesson_plan=state["plan_slice"],
        )
        session.add(unit)
        session.commit()
        artifact = Artifact(study_unit_id=unit.id, type="slides", title=state["plan_slice"]["topic"])
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
