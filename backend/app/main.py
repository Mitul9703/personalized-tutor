# The FastAPI app. Wires up the routers and a health check. More routers
# get added as we build.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import courses, documents, messages, artifacts, quizzes, flashcards

app = FastAPI(title="Personalized Tutor API")

# allow the frontend dev server to call the api during development. we match
# any localhost port because Vite may shift ports if 5173 is taken.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses.router)
app.include_router(documents.router)
app.include_router(messages.router)
app.include_router(artifacts.router)
app.include_router(quizzes.router)
app.include_router(flashcards.router)


@app.get("/health")
def health():
    return {"status": "ok"}
