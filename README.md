# Personalized Tutor

An agentic system that turns a learner's own uploaded material into
personalized slides they can steer turn by turn. Every change is grounded
in their sources, labeled when it goes beyond them, and saved as a version
they can revisit.

This is the Milestone 2 build for the CSE598 capstone.

## Structure

- `backend/` the FastAPI backend, the agent graph, ingestion, and storage
- `frontend/` the React app (chat plus the slide artifact panel)
- `docker-compose.yml` Postgres with the pgvector extension

Backend and frontend are fully separate. They talk only over the HTTP API.

## Getting started

1. Start the database:

   ```
   cp .env.example .env
   docker compose up -d
   ```

2. Set up the backend: see `backend/README.md`.
3. Set up the frontend: see `frontend/README.md`.

## Environment

Secrets live in `.env` files and are never committed. Copy each
`.env.example` to `.env` and fill in the values. The chat model provider
is set in `backend/.env`, so switching from OpenAI to the ASU key later is
a config change.
