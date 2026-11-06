# The main chat endpoint. One message runs one turn through the agent
# graph. A message with no artifact_id starts a new topic. A message with an
# artifact_id edits that artifact and saves a new version.

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.store.db import get_session
from app.store.models import Course, Message
from app.agents.graph import build_graph

router = APIRouter()


class PostMessage(BaseModel):
    text: str
    artifact_id: str | None = None
    target_slide_ids: list[str] | None = None


@router.post("/courses/{course_id}/messages")
def post_message(course_id: str, body: PostMessage, session: Session = Depends(get_session)):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    # save the learner message
    session.add(Message(
        course_id=course_id,
        role="learner",
        text=body.text,
        related_artifact_id=body.artifact_id,
    ))
    session.commit()

    graph = build_graph(session)
    state = {
        "course_id": course_id,
        "request": {
            "text": body.text,
            "artifact_id": body.artifact_id,
            "target_slide_ids": body.target_slide_ids,
        },
        "retries": 0,
    }
    result = graph.invoke(state)
    final = result["final_version"]
    return {
        "artifact_id": final["artifact_id"],
        "version_id": final["version_id"],
        "version_number": final["version_number"],
        "deck": final["content"],
    }
