# The shared state that flows through the agent graph for one turn. Each
# node reads and writes fields here. The agents never call each other; they
# hand off through this state and the graph decides the order.

from typing import TypedDict


class TurnState(TypedDict, total=False):
    course_id: str
    request: dict          # text, artifact_id, target_slide_ids
    intent: str            # new_topic, evolve, answer, or clarify
    target: dict           # artifact_id, slide_ids, topic, set by the router
    response: str          # reply text for answer or clarify turns
    retrieved_chunks: list
    plan_slice: dict
    draft_deck: dict       # the working copy
    critic_report: dict
    retries: int
    final_version: dict
