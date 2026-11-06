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

## Layout

- `app/api/` HTTP routers (added per phase)
- `app/agents/` the orchestrator, planner, builder, critic, and the graph
- `app/ingest/` upload, chunk, embed, and the course survey
- `app/llm/` the chat wrapper and the local embedding model
- `app/store/` database connection and models
- `app/schemas/` shared data shapes, like the slide deck
