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


def retrieve_scored(session: Session, course_id: str, query: str, k: int = 6) -> list[tuple]:
    # like retrieve, but also returns the cosine distance for each chunk. a
    # smaller distance means the chunk is more similar to the query, so this
    # tells us how well the material covers something, not just that some
    # chunk came back.
    query_vector = embed([query])[0]
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = (
        session.query(Chunk, distance.label("distance"))
        .filter(Chunk.course_id == course_id)
        .order_by(distance)
        .limit(k)
        .all()
    )
    return [(row[0], float(row[1])) for row in rows]
