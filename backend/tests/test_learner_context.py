import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.agents import memory, nodes, planner


@pytest.mark.parametrize("intent", ["new_topic", "evolve"])
def test_planning_node_passes_profile_notes_and_instruction(monkeypatch, profile, intent):
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = SimpleNamespace(profile=profile, notes="Needs help with gradients")
    session.get.side_effect = [SimpleNamespace(study_unit_id="unit"), SimpleNamespace(topic="Gradient descent")]
    plan = {"topic": "Gradient descent", "objective": "Learn", "points": [], "topic_absent": False}
    call = MagicMock(return_value=plan)
    monkeypatch.setattr(nodes, "plan_topic", call)
    state = {"course_id": "course", "intent": intent, "request": {"text": "Explain with an example", "artifact_id": "artifact"}, "target": {"topic": "Gradient descent"}}
    assert nodes.planner(state, session) == {"plan_slice": plan, "retrieved_chunks": []}
    call.assert_called_once_with(session, "course", "Gradient descent", "Needs help with gradients", instruction="Explain with an example", learner_profile=profile)
    session.query.assert_called_once()


def test_missing_context_is_compatible():
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    assert nodes._learner_context(session, "old-course") == ({}, "")


def test_planner_passes_context_to_shared_loop_without_changing_plan(monkeypatch, profile):
    expected = {"topic": "Gradients", "objective": "Follow an intuitive example", "points": [{"point": "Define a gradient", "provenance": "source", "chunk_ids": ["chunk"]}], "topic_absent": False}
    loop = MagicMock(return_value=expected)
    monkeypatch.setattr(planner, "run_agent", loop)
    result = planner.plan_topic(MagicMock(), "course", "Gradients", "Previously struggled", "Include an example", learner_profile=profile)
    assert result == expected
    system, user, tools, handlers = loop.call_args.args
    assert json.dumps(profile) in user
    assert "Previously struggled" in user
    assert "Include an example" in user
    assert "priority" in system
    assert tools is planner.PLAN_TOOLS
    assert "retrieve" in handlers


def test_existing_positional_planner_call_still_works(monkeypatch):
    loop = MagicMock(return_value={"topic": "X", "objective": "Learn", "points": []})
    monkeypatch.setattr(planner, "run_agent", loop)
    planner.plan_topic(MagicMock(), "course", "X", "Legacy notes", "Go deeper")
    assert "Legacy notes" in loop.call_args.args[1]
    assert "Go deeper" in loop.call_args.args[1]


def test_memory_uses_updated_profile_and_preserves_profile(monkeypatch, profile):
    updated = {**profile, "level": "advanced"}
    row = SimpleNamespace(profile=updated.copy(), notes="Self-reported level: beginner. Struggled with derivatives.")
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = row
    chat = MagicMock(return_value="Learning history: practiced derivatives.")
    monkeypatch.setattr(memory, "chat", chat)
    memory.update_notes(session, "course", "Explain the chain rule", "Calculus")
    messages = chat.call_args.args[0]
    assert json.dumps(updated) in messages[1]["content"]
    assert "Struggled with derivatives" in messages[1]["content"]
    assert "remove outdated assertions" in messages[0]["content"]
    assert row.profile == updated
    assert row.notes == "Learning history: practiced derivatives."
    session.commit.assert_called_once()


def test_memory_missing_model_is_compatible(monkeypatch):
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    chat = MagicMock()
    monkeypatch.setattr(memory, "chat", chat)
    memory.update_notes(session, "old-course", "Hello", "Topic")
    chat.assert_not_called()
