# The shared state that flows through the agent graph for one turn. Each
# node reads and writes fields here. draft_deck is the working copy the
# Builder edits before we commit it as a new version.

from typing import TypedDict


class TurnState(TypedDict, total=False):
    course_id: str
    learner_model: dict
    request: dict          # text, target_artifact_id, target_slide_ids, intent
    retrieved_chunks: list
    plan_slice: dict
    draft_deck: dict       # the working copy
    critic_report: dict
    retries: int
    final_version: dict
