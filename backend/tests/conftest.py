import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# All automated agent calls are mocked. No provider credentials are needed.
os.environ.setdefault("LLM_API_KEY", "onboarding-tests-no-network")

from app.api.courses import router
from app.store.db import Base, get_session


@pytest.fixture(scope="session")
def test_engine():
    url = os.environ.get("ONBOARDING_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ONBOARDING_TEST_DATABASE_URL to an isolated Postgres database ending in _test")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("The onboarding test database name must end in _test")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client


@pytest.fixture
def course(client):
    response = client.post("/courses", json={"title": "Machine learning"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def profile():
    return {"level": "beginner", "goal": "Understand the concepts", "background": "No prior experience"}
