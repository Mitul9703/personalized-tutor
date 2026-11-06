# Revert as a deterministic version write. Deciding to revert and which
# version to go back to is the agent's job (the Router understands "undo" or
# "go back to v1" from free text). Actually creating the version stays in
# code so history cannot get corrupted.
#
# Revert is append-only: it writes a new version whose content equals the
# chosen old one and moves the pointer. Nothing is deleted, so the history
# stays honest.

from app.store.models import ArtifactVersion


def revert_to(session, artifact, target_version) -> ArtifactVersion:
    current = session.get(ArtifactVersion, artifact.current_version_id)
    new_version = ArtifactVersion(
        artifact_id=artifact.id,
        version_number=current.version_number + 1,
        parent_version_id=current.id,
        content=target_version.content,
        critic_report={"passed": True, "notes": "reverted"},
        caused_by=f"revert to v{target_version.version_number}",
    )
    session.add(new_version)
    session.commit()
    artifact.current_version_id = new_version.id
    session.commit()
    return new_version
