# Endpoints for a course: create it, read it, run the one time survey, and
# read the resulting outline. A course is one learner's workspace built on
# their uploaded material.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.store.db import get_session
from app.store.models import Learner, Course, LearnerModel, CourseOutline
from app.agents.planner import survey_course

router = APIRouter()


class CreateCourse(BaseModel):
    title: str = "Untitled course"


@router.post("/courses")
def create_course(body: CreateCourse, session: Session = Depends(get_session)):
    # for now we make a fresh learner per course. onboarding fills in the
    # profile in a later phase.
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
