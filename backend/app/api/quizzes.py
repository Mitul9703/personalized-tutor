# Quiz endpoints. One creates a quiz for a topic, the other grades a
# student's answers with cited feedback.
#
# Create runs the shared Planner, then the quiz generator, and saves the
# result as version 1 of an Artifact with type "quiz". It is a direct path so
# the quiz lane works before the content type dispatch lands in the graph.
# Once the dispatch picks run_quiz_builder from Artifact.type, chat ("quiz me
# on X") can reach the same generator through the graph.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.grader import grade_quiz
from app.agents.memory import record_misconceptions
from app.agents.planner import plan_topic
from app.agents.quiz_builder import run_quiz_builder
from app.store.db import get_session
from app.store.models import (
    Artifact, ArtifactVersion, Chunk, Course, LearnerModel, Message, StudyUnit,
)

router = APIRouter()

# points per verdict, for the score shown to the student
_POINTS = {"right": 1.0, "partial": 0.5, "wrong": 0.0, "ungraded": 0.0}


class CreateQuiz(BaseModel):
    topic: str


class SubmitQuiz(BaseModel):
    answers: dict[str, str]          # {question_id: answer text}
    version_id: str | None = None    # which version was taken; defaults to current


@router.post("/courses/{course_id}/quizzes")
def create_quiz(course_id: str, body: CreateQuiz, session: Session = Depends(get_session)):
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    session.add(Message(course_id=course_id, role="learner", text=f"Quiz me on {body.topic}"))
    session.commit()

    learner = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    notes = learner.notes if learner and learner.notes else ""
    plan = plan_topic(session, course_id, body.topic, notes)

    chunk_ids = list(dict.fromkeys(cid for p in plan.get("points", []) for cid in p.get("chunk_ids", [])))
    rows = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all() if chunk_ids else []
    chunks = [{"id": c.id, "text": c.text, "location": c.location} for c in rows]

    quiz = run_quiz_builder(
        session, course_id,
        plan=plan, chunks=chunks, base_quiz=None,
        instruction=body.topic, intent="new_topic",
    )
    if not quiz.get("questions"):
        raise HTTPException(status_code=502, detail="the quiz generator did not produce any questions")

    title = quiz.get("title") or plan.get("topic") or body.topic
    unit = StudyUnit(course_id=course_id, topic=plan.get("topic", body.topic), lesson_plan=plan)
    session.add(unit)
    session.commit()
    artifact = Artifact(study_unit_id=unit.id, type="quiz", title=title)
    session.add(artifact)
    session.commit()
    version = ArtifactVersion(
        artifact_id=artifact.id, version_number=1, parent_version_id=None,
        content=quiz, critic_report={}, caused_by="generate",
    )
    session.add(version)
    session.commit()
    artifact.current_version_id = version.id
    session.add(Message(
        course_id=course_id, role="system", text=f"Created quiz {title}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    return {
        "intent": "new_topic",
        "type": "quiz",
        "artifact_id": artifact.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content": quiz,
    }


@router.post("/artifacts/{artifact_id}/quiz/submit")
def submit_quiz(artifact_id: str, body: SubmitQuiz, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.type != "quiz":
        raise HTTPException(status_code=404, detail="quiz not found")
    version = session.get(ArtifactVersion, body.version_id or artifact.current_version_id)
    if version is None or version.artifact_id != artifact_id:
        raise HTTPException(status_code=404, detail="version not found")
    course_id = session.get(StudyUnit, artifact.study_unit_id).course_id

    grades = grade_quiz(session, course_id, version.content, body.answers)
    score = sum(_POINTS[g["verdict"]] for g in grades)
    total = len(grades)

    session.add(Message(
        course_id=course_id, role="system",
        text=f"Graded {artifact.title}: {score:g} of {total}",
        related_artifact_id=artifact.id, related_version_id=version.id,
    ))
    session.commit()

    # hand what went wrong to the memory agent so the learner notes learn from it
    stems = {q["id"]: q.get("stem", "") for q in version.content.get("questions", [])}
    misconceptions = [
        {"question": stems.get(g["question_id"], ""),
         "student_answer": body.answers.get(g["question_id"], ""),
         "misconception": g["misconception"]}
        for g in grades if g["verdict"] in ("wrong", "partial")
    ]
    record_misconceptions(session, course_id, artifact.title, misconceptions)

    return {
        "artifact_id": artifact.id,
        "version_id": version.id,
        "score": score,
        "total": total,
        "grades": grades,
    }
