from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.courses import router
from app.store.db import get_session
from app.store.models import Course, Learner, LearnerModel


def model(session, course_id):
    return session.query(LearnerModel).filter_by(course_id=course_id).one()


def test_save_read_and_reload(client, db_session, course, profile):
    path = f"/courses/{course['course_id']}/onboarding"
    assert client.get(path).json()["profile"] is None
    submitted = {**profile, "goal": "  Understand the concepts  ", "background": "  No prior experience  "}
    assert client.post(path, json=submitted).json() == {"course_id": course["course_id"], "profile": profile}
    db_session.expire_all()
    assert client.get(path).json()["profile"] == profile
    row = model(db_session, course["course_id"])
    assert row.notes == "Self-reported level: beginner.\nLearning goal: Understand the concepts\nBackground: No prior experience"
    assert db_session.get(Learner, course["learner_id"]).profile == {}


def test_repeat_and_edit_preserve_history_and_extra_fields(client, db_session, course, profile):
    row = model(db_session, course["course_id"])
    row.profile = {"accessibility": "large text"}
    row.notes = "Struggled with the chain rule; now understands derivatives."
    db_session.commit()
    path = f"/courses/{course['course_id']}/onboarding"
    for _ in range(2):
        assert client.post(path, json=profile).status_code == 200
    updated = {**profile, "level": "advanced", "background": "Calculus and linear algebra"}
    assert client.post(path, json=updated).json()["profile"] == updated
    db_session.expire_all()
    row = model(db_session, course["course_id"])
    assert row.profile == {**updated, "accessibility": "large text"}
    assert row.notes == "Struggled with the chain rule; now understands derivatives."
    assert db_session.query(LearnerModel).filter_by(course_id=course["course_id"]).count() == 1


def test_repeated_onboarding_does_not_duplicate_seed_notes(client, db_session, course, profile):
    path = f"/courses/{course['course_id']}/onboarding"
    client.post(path, json=profile)
    old_notes = model(db_session, course["course_id"]).notes
    client.post(path, json={**profile, "level": "advanced"})
    assert model(db_session, course["course_id"]).notes == old_notes


def test_missing_learner_model_is_created(client, db_session, course, profile):
    db_session.delete(model(db_session, course["course_id"]))
    db_session.commit()
    path = f"/courses/{course['course_id']}/onboarding"
    assert client.get(path).json()["profile"] is None
    assert client.post(path, json=profile).status_code == 200
    assert model(db_session, course["course_id"]).profile == profile


@pytest.mark.parametrize("saved", [{}, {"level": "beginner"}, {"goal": "Learn", "background": "None"}, {"level": "invalid", "goal": "Learn", "background": "None"}])
def test_incomplete_old_profile_is_null(client, db_session, course, saved):
    row = model(db_session, course["course_id"])
    row.profile = saved
    db_session.commit()
    assert client.get(f"/courses/{course['course_id']}/onboarding").json()["profile"] is None


@pytest.mark.parametrize("change", [
    {"level": "expert"}, {"level": None}, {"goal": "   "}, {"goal": "x" * 1001},
    {"background": "\n\t"}, {"background": "x" * 2001}, {"background": None},
])
def test_invalid_input_does_not_change_profile(client, db_session, course, profile, change):
    response = client.post(f"/courses/{course['course_id']}/onboarding", json={**profile, **change})
    assert response.status_code == 422
    assert model(db_session, course["course_id"]).profile == {}


def test_missing_fields_are_rejected(client, course):
    assert client.post(f"/courses/{course['course_id']}/onboarding", json={}).status_code == 422


def test_unknown_course(client, profile):
    assert client.get("/courses/missing/onboarding").status_code == 404
    assert client.post("/courses/missing/onboarding", json=profile).status_code == 404


def test_commit_failure_rolls_back(profile):
    session = MagicMock()
    row = LearnerModel(course_id="course", profile={}, notes="")
    session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = Course(id="course")
    session.query.return_value.filter.return_value.first.return_value = row
    session.commit.side_effect = SQLAlchemyError("simulated database failure")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/courses/course/onboarding", json=profile).status_code == 500
    session.rollback.assert_called_once()
