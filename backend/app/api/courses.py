# Endpoints for creating and reading a course. A course is one learner's
# workspace built on their uploaded material.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.store.db import get_session
from app.store.models import Learner, Course, LearnerModel

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
