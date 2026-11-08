# Endpoints for a course: create it, read it, run the one time survey, and
# read the resulting outline. A course is one learner's workspace built on
# their uploaded material.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.store.db import get_session
from app.store.models import Learner, Course, LearnerModel, CourseOutline, Artifact, StudyUnit
from app.agents.planner import survey_course
from app.schemas.learner import LearnerProfile, OnboardingResponse

router = APIRouter()


class CreateCourse(BaseModel):
    title: str = "Untitled course"


@router.post("/courses")
def create_course(body: CreateCourse, session: Session = Depends(get_session)):
    # The learner profile belongs to the course's LearnerModel.
    learner = Learner(profile={})
    session.add(learner)
    session.commit()

    course = Course(learner_id=learner.id, title=body.title)
    session.add(course)
    session.commit()

    # start an empty learner model for this course
    session.add(LearnerModel(course_id=course.id, profile={}, notes=""))
    session.commit()

    return {"course_id": course.id, "learner_id": learner.id, "title": course.title}


@router.get("/courses/{course_id}")
def get_course(course_id: str, session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")
    return {"course_id": course.id, "title": course.title, "learner_id": course.learner_id}


@router.get("/courses/{course_id}/onboarding", response_model=OnboardingResponse)
def get_onboarding(course_id: str, session: Session = Depends(get_session)):
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
    try:
        profile = LearnerProfile.model_validate(row.profile if row else {})
    except ValidationError:
        profile = None
    return OnboardingResponse(course_id=course_id, profile=profile)


@router.post("/courses/{course_id}/onboarding", response_model=OnboardingResponse)
def save_onboarding(body: LearnerProfile, course_id: str, session: Session = Depends(get_session)):
    try:
        # Serialize saves for this course, including creation of a missing model.
        course = session.query(Course).filter(Course.id == course_id).with_for_update().first()
        if course is None:
            raise HTTPException(status_code=404, detail="course not found")
        row = session.query(LearnerModel).filter(LearnerModel.course_id == course_id).first()
        if row is None:
            row = LearnerModel(course_id=course_id, profile={}, notes="")
            session.add(row)
        row.profile = {**(row.profile or {}), **body.model_dump()}
        if not (row.notes or "").strip():
            row.notes = (
                f"Self-reported level: {body.level}.\n"
                f"Learning goal: {body.goal}\n"
                f"Background: {body.background}"
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return OnboardingResponse(course_id=course_id, profile=body)


@router.post("/courses/{course_id}/survey")
def run_survey(course_id: str, session: Session = Depends(get_session)):
    # reads the uploaded material and builds the outline and coverage map.
    # run this after the documents are uploaded.
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    outline = survey_course(session, course_id)
    if not outline:
        raise HTTPException(status_code=400, detail="no material to survey yet")
    return outline


@router.get("/courses/{course_id}/artifacts")
def list_artifacts(course_id: str, session: Session = Depends(get_session)):
    # the decks that exist in this course, for the UI to list and switch.
    rows = (
        session.query(Artifact)
        .join(StudyUnit, Artifact.study_unit_id == StudyUnit.id)
        .filter(StudyUnit.course_id == course_id)
        .order_by(Artifact.created_at)
        .all()
    )
    return [
        {"artifact_id": a.id, "title": a.title, "current_version_id": a.current_version_id}
        for a in rows
    ]


@router.get("/courses/{course_id}/outline")
def get_outline(course_id: str, session: Session = Depends(get_session)):
    # returns the most recent outline for the course.
    row = (
        session.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.created_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="no outline yet, run the survey first")
    return row.outline
