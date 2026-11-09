# Backend

FastAPI backend for the personalized tutor. Holds the agent graph,
ingestion, and the database layer.

## Setup

1. Create and activate a virtual environment:

   ```
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Copy the env file and fill it in:

   ```
   cp .env.example .env
   ```

4. Make sure the database is running (see the root README), then create
   the tables:

   ```
   python -m app.store.init_db
   ```

5. Run the API:

   ```
   uvicorn app.main:app --reload
   ```

Visit http://localhost:8000/health to check it is up.

## Tests

From `backend/`, install the dependencies, including the test tools:

```sh
.venv/bin/python -m pip install -r requirements.txt
```

Persistence tests require a separate Postgres database with pgvector. Its name
must end in `_test`; never use the application database. With the standard
Docker setup, create it once from the repository root:

```sh
docker compose exec db psql -U tutor -d postgres -c 'CREATE DATABASE tutor_onboarding_test'
```

Then run the suite from `backend/`:

```sh
ONBOARDING_TEST_DATABASE_URL=postgresql+psycopg://tutor:tutor@localhost:5432/tutor_onboarding_test .venv/bin/python -m pytest -q
```

Adjust the connection URL for your local database settings. The suite creates
the extension and tables in the test database, then rolls back each persistence
test's data. Model calls are mocked, so no real model credentials are needed.
Without `ONBOARDING_TEST_DATABASE_URL`, persistence tests are skipped and only
the remaining unit tests run.

## Layout

- `app/api/` HTTP routers (added per phase)
- `app/agents/` the orchestrator, planner, builder, critic, and the graph
- `app/ingest/` upload, chunk, embed, and the course survey
- `app/llm/` the chat wrapper and the local embedding model
- `app/store/` database connection and models
- `app/schemas/` shared data shapes, like the slide deck
