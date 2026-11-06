# Endpoints to read an artifact: its version history and the content of a
# single version. The frontend uses these for the version bar and the deck
# view.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.store.db import get_session
from app.store.models import Artifact, ArtifactVersion

router = APIRouter()


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, session: Session = Depends(get_session)):
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="artifact not found")

    versions = (
        session.query(ArtifactVersion)
        .filter(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.version_number)
        .all()
    )
    return {
        "artifact_id": artifact.id,
        "title": artifact.title,
        "type": artifact.type,
        "current_version_id": artifact.current_version_id,
        "versions": [
            {
                "version_id": v.id,
                "version_number": v.version_number,
                "parent_version_id": v.parent_version_id,
                "caused_by": v.caused_by,
                "slide_count": len(v.content.get("slides", [])),
            }
            for v in versions
        ],
    }


@router.get("/artifacts/{artifact_id}/versions/{version_id}")
def get_version(artifact_id: str, version_id: str, session: Session = Depends(get_session)):
    version = session.get(ArtifactVersion, version_id)
    if version is None or version.artifact_id != artifact_id:
        raise HTTPException(status_code=404, detail="version not found")
    return {
        "version_id": version.id,
        "version_number": version.version_number,
        "parent_version_id": version.parent_version_id,
        "caused_by": version.caused_by,
        "deck": version.content,
    }
