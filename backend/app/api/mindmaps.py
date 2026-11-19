# Mind map endpoints. One builds a mind map for a topic, the other edits a map
# from a free text instruction ("add a branch on X", "go deeper on Y").
#
# Create runs the shared Planner, then the mind map generator, and saves the
# result as version 1 of an Artifact with type "mindmap". Edit runs the
# generator on the current version and saves a new version, so version history
# and revert work the same as for slides. This is a direct path so the mind map
# lane works before the content type dispatch lands in the graph. Once the
# dispatch picks run_mindmap_builder from Artifact.type, chat ("make a mind map
# about X") can reach the same generator.

import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.critic import review_map, verify_revise
from app.agents.mindmap import run_mindmap_builder
from app.agents.memory import update_notes
from app.agents.planner import plan_topic
from app.store.db import get_session
from app.store.models import (
    Artifact, ArtifactVersion, Chunk, Course, LearnerModel, Message, StudyUnit,
)

router = APIRouter()


class CreateMindMap(BaseModel):
    topic: str


class EditMindMap(BaseModel):
    instruction: str


@router.post("/courses/{course_id}/mindmaps")
def create_mindmap(course_id: str, body: CreateMindMap, session: Session = Depends(get_session)):
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    request = f"Make a mind map about {body.topic}"
    session.add(Message(course_id=course_id, role="learner", text=request))
    session.commit()

    plan = plan_topic(session, course_id, body.topic, _notes(session, course_id))
    chunks = _plan_chunks(session, plan)

    def build(base, issues):
        return run_mindmap_builder(
            session, course_id,
            plan=plan, chunks=chunks, base_deck=base,
            instruction=request, intent="new_topic", issues=issues,
        )

    mind, report = verify_revise(build, lambda m: review_map(session, course_id, m))
    if not mind.get("nodes"):
        raise HTTPException(status_code=502, detail="the mind map generator did not produce any nodes")

    title = mind.get("title") or plan.get("topic") or body.topic
    mind["title"] = title
    unit = StudyUnit(course_id=course_id, topic=plan.get("topic", body.topic), lesson_plan=plan)
    session.add(unit)
    session.commit()
    artifact = Artifact(study_unit_id=unit.id, type="mindmap", title=title)
    session.add(artifact)
    session.commit()
    version = ArtifactVersion(
        artifact_id=artifact.id, version_number=1, parent_version_id=None,
        content=mind, critic_report=report, caused_by="generate",
    )
    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.add(Message(
        course_id=course_id, role="system", text=f"Created mind map {title}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    update_notes(session, course_id, request, title)
    return _response(artifact, version, mind, "new_topic")


@router.post("/artifacts/{artifact_id}/mindmaps/edit")
def edit_mindmap(artifact_id: str, body: EditMindMap, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.type != "mindmap":
        raise HTTPException(status_code=404, detail="mind map not found")
    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is empty")
    unit = session.get(StudyUnit, artifact.study_unit_id)
    course_id = unit.course_id
    current = session.get(ArtifactVersion, artifact.current_version_id)

    session.add(Message(course_id=course_id, role="learner", text=body.instruction,
                        related_artifact_id=artifact.id))
    session.commit()

    plan = unit.lesson_plan or {"topic": unit.topic}
    mind = run_mindmap_builder(
        session, course_id,
        plan=plan, chunks=_plan_chunks(session, plan), base_deck=copy.deepcopy(current.content),
        instruction=body.instruction, intent="evolve",
    )

    version = ArtifactVersion(
        artifact_id=artifact.id, version_number=current.version_number + 1,
        parent_version_id=current.id, content=mind, critic_report={},
        caused_by=body.instruction[:40],
    )
    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.add(Message(
        course_id=course_id, role="system", text=f"Updated mind map {artifact.title}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    update_notes(session, course_id, body.instruction, artifact.title)
    return _response(artifact, version, mind, "evolve")


def _notes(session, course_id):
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    return row.notes if row and row.notes else ""


def _plan_chunks(session, plan):
    ids = list(dict.fromkeys(cid for p in plan.get("points", []) for cid in p.get("chunk_ids", [])))
    rows = session.query(Chunk).filter(Chunk.id.in_(ids)).all() if ids else []
    return [{"id": c.id, "text": c.text, "location": c.location} for c in rows]


def _response(artifact, version, mind, intent):
    return {
        "intent": intent,
        "type": "mindmap",
        "artifact_id": artifact.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content": mind,
    }
