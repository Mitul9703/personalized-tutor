# The ingestion pipeline. Given a document row and the file path, it reads
# the file, splits it into chunks, embeds them, and stores them. It marks
# the document ready or failed at the end.

from sqlalchemy.orm import Session

from app.ingest.parse import parse_file
from app.ingest.chunk import chunk_segments
from app.llm.embeddings import embed
from app.store.models import Document, Chunk


def ingest_document(session: Session, document: Document, path: str) -> int:
    # returns the number of chunks stored.
    try:
        segments = parse_file(path)
        pieces = chunk_segments(segments)
        if not pieces:
            document.status = "failed"
            session.commit()
            return 0

        vectors = embed([p["text"] for p in pieces])
        for piece, vector in zip(pieces, vectors):
            session.add(Chunk(
                document_id=document.id,
                course_id=document.course_id,
                ordinal=piece["ordinal"],
                text=piece["text"],
                location=piece["location"],
                embedding=vector,
            ))
        document.status = "ready"
        session.commit()
        return len(pieces)
    except Exception:
        session.rollback()
        document.status = "failed"
        session.commit()
        raise
