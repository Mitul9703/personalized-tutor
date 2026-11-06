# The FastAPI app. For now it only has a health check. Routers for
# upload, chat, and artifacts get added in later phases.

from fastapi import FastAPI

app = FastAPI(title="Personalized Tutor API")


@app.get("/health")
def health():
    return {"status": "ok"}
