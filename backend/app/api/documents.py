# Endpoints for uploading a document to a course and for a quick search to
# check that retrieval works. Ingestion runs during the upload request for
# now. We can move it to the background later if uploads get large.

import os

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.store.db import get_session
from app.store.models import Course, Document, Chunk
from app.ingest.pipeline import ingest_document
from app.ingest.retrieve import retrieve

router = APIRouter()


@router.post("/courses/{course_id}/documents")
def upload_document(
    course_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="course not found")

    os.makedirs(settings.upload_dir, exist_ok=True)

    document = Document(course_id=course_id, filename=file.filename, status="pending")
    session.add(document)
    session.commit()

    path = os.path.join(settings.upload_dir, f"{document.id}_{file.filename}")
    with open(path, "wb") as out:
        out.write(file.file.read())

    count = ingest_document(session, document, path)
    return {"document_id": document.id, "status": document.status, "chunks": count}


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str, session: Session = Depends(get_session)):
    # lets a citation show the exact source text it points at.
    chunk = session.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    return {"chunk_id": chunk.id, "text": chunk.text, "location": chunk.location}


@router.get("/courses/{course_id}/search")
def search(
    course_id: str,
    q: str,
    k: int = 6,
    session: Session = Depends(get_session),
):
    # a small helper to confirm retrieval returns sensible chunks.
    rows = retrieve(session, course_id, q, k)
    return [
        {"chunk_id": c.id, "text": c.text[:300], "location": c.location}
        for c in rows
    ]
