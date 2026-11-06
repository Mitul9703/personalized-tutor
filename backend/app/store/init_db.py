# Run this once to set up the database. It turns on the pgvector extension
# and creates all the tables. Later we can move to proper migrations.

from sqlalchemy import text

from app.store.db import engine, Base
from app.store import models  # noqa: F401  (import so the tables register)


def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    print("database ready")


if __name__ == "__main__":
    init_db()
