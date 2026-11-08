# The database tables. The main rule here is versioning. An artifact points
# to its current version, and every change adds a new version row. We never
# edit a version in place.

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.store.db import Base

# size of the bge-small-en-v1.5 vectors
EMBED_DIM = 384


def new_id() -> str:
    return str(uuid.uuid4())


class Learner(Base):
    __tablename__ = "learner"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    # level, goal, background. kept small.
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Course(Base):
    # one course is one set of uploaded material. it is the workspace.
    __tablename__ = "course"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    learner_id: Mapped[str] = mapped_column(ForeignKey("learner.id"))
    title: Mapped[str] = mapped_column(String, default="Untitled course")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    # one uploaded file inside a course.
    __tablename__ = "document"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    filename: Mapped[str] = mapped_column(String)
    # pending, ready, or failed
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Chunk(Base):
    # a piece of a document. we store the verbatim text and where it came
    # from so a citation can show the exact wording. the embedding is the
    # vector we use to find it.
    __tablename__ = "chunk"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id"))
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    # { page, section, char_span }
    location: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list] = mapped_column(Vector(EMBED_DIM))


class CourseOutline(Base):
    # the one time survey output. topics, order, dependencies, and a map
    # from each topic to the chunks that cover it.
    __tablename__ = "course_outline"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    outline: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyUnit(Base):
    # a topic workspace. it owns the lesson plan and the artifacts made for
    # that topic.
    __tablename__ = "study_unit"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    topic: Mapped[str] = mapped_column(String)
    lesson_plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Artifact(Base):
    # the logical deck. it points at its current version.
    __tablename__ = "artifact"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    study_unit_id: Mapped[str] = mapped_column(ForeignKey("study_unit.id"))
    type: Mapped[str] = mapped_column(String, default="slides")
    title: Mapped[str] = mapped_column(String, default="Untitled")
    current_version_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArtifactVersion(Base):
    # an immutable snapshot of a deck. content holds the full deck json.
    # caused_by says what made this version, like "simplify" or "edit".
    __tablename__ = "artifact_version"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifact.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    parent_version_id: Mapped[str] = mapped_column(String, nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    critic_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    caused_by: Mapped[str] = mapped_column(String, default="generate")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearnerModel(Base):
    # the memory for one course. a small profile plus free text notes the
    # agent reads before generating and appends to after each turn.
    __tablename__ = "learner_model"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


class Message(Base):
    # chat history for a course.
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"))
    # learner or system
    role: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    related_artifact_id: Mapped[str] = mapped_column(String, nullable=True)
    related_version_id: Mapped[str] = mapped_column(String, nullable=True)
    # for chat answers: {"items": [{chunk_id, doc, loc}], "uses_general_knowledge": bool}
    citations: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
