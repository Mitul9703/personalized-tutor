# The FastAPI app. Wires up the routers and a health check. More routers
# (chat, artifacts) get added in later phases.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import courses, documents

app = FastAPI(title="Personalized Tutor API")

# allow the frontend dev server to call the api during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses.router)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok"}
