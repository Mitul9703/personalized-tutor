# Sets up the database connection and session. We use SQLAlchemy.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_session():
    # gives a session and makes sure it closes after use.
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
