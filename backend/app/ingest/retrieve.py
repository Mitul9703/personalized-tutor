# Retrieval over the stored chunks. We embed the query and find the nearest
# chunks for a course using pgvector cosine distance.

from sqlalchemy.orm import Session

from app.llm.embeddings import embed
from app.store.models import Chunk


def retrieve(session: Session, course_id: str, query: str, k: int = 6) -> list[Chunk]:
    query_vector = embed([query])[0]
    return (
        session.query(Chunk)
        .filter(Chunk.course_id == course_id)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(k)
        .all()
    )
