# Doc endpoints. One writes a doc for a topic, the other edits a doc from a
# free text instruction ("simplify", "go deeper").
#
# Create runs the shared Planner, then the doc generator, then the Critic in a
# short verify-revise loop: a doc is long-form prose, which is where an
# unsupported claim hides most easily, so it is the one content type we check
# before saving. The Critic reads the doc through a section-to-slide adapter so
# we reuse it unchanged. Edit runs the generator on the current version and
# saves a new version, so version history and revert work the same as for
# slides. This is a direct path so the docs lane works before the content type
# dispatch lands in the graph. Once the dispatch picks run_doc_builder from
# Artifact.type, chat ("write a doc about X") can reach the same generator.

import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.critic import review_doc
from app.agents.doc import run_doc_builder
from app.agents.memory import update_notes
from app.agents.planner import plan_topic
from app.store.db import get_session
from app.store.models import (
    Artifact, ArtifactVersion, Chunk, Course, LearnerModel, Message, StudyUnit,
)

router = APIRouter()

MAX_DOC_ATTEMPTS = 2  # one write, then at most one revise on a critic fail


class CreateDoc(BaseModel):
    topic: str


class EditDoc(BaseModel):
    instruction: str


@router.post("/courses/{course_id}/docs")
def create_doc(course_id: str, body: CreateDoc, session: Session = Depends(get_session)):
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    request = f"Write a doc about {body.topic}"
    session.add(Message(course_id=course_id, role="learner", text=request))
    session.commit()

    plan = plan_topic(session, course_id, body.topic, _notes(session, course_id))
    chunks = _plan_chunks(session, plan)

    # write, verify, and revise once if the critic flags a grounding problem
    doc = run_doc_builder(
        session, course_id,
        plan=plan, chunks=chunks, base_deck=None,
        instruction=request, intent="new_topic",
    )
    report = {}
    for attempt in range(MAX_DOC_ATTEMPTS):
        report = review_doc(session, course_id, doc)
        if report.get("passed", True) or attempt + 1 >= MAX_DOC_ATTEMPTS:
            break
        doc = run_doc_builder(
            session, course_id,
            plan=plan, chunks=chunks, base_deck=doc,
            instruction=request, intent="new_topic", issues=report["issues"],
        )

    if not doc.get("sections"):
        raise HTTPException(status_code=502, detail="the doc generator did not produce any sections")

    title = doc.get("title") or plan.get("topic") or body.topic
    doc["title"] = title
    unit = StudyUnit(course_id=course_id, topic=plan.get("topic", body.topic), lesson_plan=plan)
    session.add(unit)
    session.commit()
    artifact = Artifact(study_unit_id=unit.id, type="doc", title=title)
    session.add(artifact)
    session.commit()
    version = ArtifactVersion(
        artifact_id=artifact.id, version_number=1, parent_version_id=None,
        content=doc, critic_report=report, caused_by="generate",
    )
    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.add(Message(
        course_id=course_id, role="system", text=f"Created doc {title}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    update_notes(session, course_id, request, title)
    return _response(artifact, version, doc, "new_topic")


@router.post("/artifacts/{artifact_id}/docs/edit")
def edit_doc(artifact_id: str, body: EditDoc, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.type != "doc":
        raise HTTPException(status_code=404, detail="doc not found")
    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is empty")
    unit = session.get(StudyUnit, artifact.study_unit_id)
    course_id = unit.course_id
    current = session.get(ArtifactVersion, artifact.current_version_id)

    session.add(Message(course_id=course_id, role="learner", text=body.instruction,
                        related_artifact_id=artifact.id))
    session.commit()

    plan = unit.lesson_plan or {"topic": unit.topic}
    # work on a copy so the saved version is never edited in place
    doc = run_doc_builder(
        session, course_id,
        plan=plan, chunks=_plan_chunks(session, plan), base_deck=copy.deepcopy(current.content),
        instruction=body.instruction, intent="evolve",
    )

    version = ArtifactVersion(
        artifact_id=artifact.id, version_number=current.version_number + 1,
        parent_version_id=current.id, content=doc, critic_report={},
        caused_by=body.instruction[:40],
    )
    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.add(Message(
        course_id=course_id, role="system", text=f"Updated doc {artifact.title}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    update_notes(session, course_id, body.instruction, artifact.title)
    return _response(artifact, version, doc, "evolve")


def _notes(session, course_id):
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    return row.notes if row and row.notes else ""


def _plan_chunks(session, plan):
    ids = list(dict.fromkeys(cid for p in plan.get("points", []) for cid in p.get("chunk_ids", [])))
    rows = session.query(Chunk).filter(Chunk.id.in_(ids)).all() if ids else []
    return [{"id": c.id, "text": c.text, "location": c.location} for c in rows]


def _response(artifact, version, doc, intent):
    return {
        "intent": intent,
        "type": "doc",
        "artifact_id": artifact.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content": doc,
    }
