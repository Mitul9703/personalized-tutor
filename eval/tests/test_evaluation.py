"""Offline boundary checks; no API or model calls."""
import copy
import json
import os
from pathlib import Path
import sys
from contextlib import nullcontext
from types import SimpleNamespace

os.environ.setdefault("LLM_API_KEY", "offline-test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import pytest
import baselines as B
import questions as Q
import learner as L
import judge as J
import interaction as I
import run_eval as R


def deck():
    return {"title": "Fixture", "slides": [{"id": str(i), "heading": "Heading", "bullets": ["Fact"],
            "notes": "Accessible explanation", "provenance": "source", "citations": [{"chunk_id": "c1"}]} for i in range(3)]}


@pytest.fixture(autouse=True)
def isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "OUT", tmp_path)
    monkeypatch.setattr(R, "DATA", {"steps": {}, "inputs": [], "core": [], "personalization": [], "interaction": []})
    monkeypatch.setattr(Q, "CALLS", None)
    monkeypatch.setattr(Q, "chat_json", lambda *a, **k: pytest.fail("Unexpected live model call"))
    monkeypatch.setattr(R, "_request", lambda *a, **k: pytest.fail("Unexpected API call"))


def test_baselines_share_request_profile_and_use_application_retrieval(monkeypatch):
    import app.ingest.retrieve as retrieval
    rows = [SimpleNamespace(id="c1", text="Source", location={})]
    captured = []
    monkeypatch.setattr(B, "ask_json", lambda instruction, data: captured.append(data) or deck())
    def retrieve(session, course, topic, k):
        assert (session, course, topic, k) == ("session", "course", "Topic", 8)
        return rows
    monkeypatch.setattr(retrieval, "retrieve", retrieve)
    B.single_call_baseline("Source", "Topic", chunks=B.chunk_view(rows, "source.txt"), profile=R.pz.NOVICE)
    B.rag_baseline("Source", "Topic", session="session", course_id="course", filename="source.txt", profile=R.pz.NOVICE)
    assert captured[0] == captured[1]
    assert captured[0]["request"] == B.REQUEST.format(topic="Topic")


def test_learner_sees_notes_and_questions_without_gold(monkeypatch):
    captured = []
    monkeypatch.setattr(L, "ask_json", lambda instruction, data: captured.append(data) or {"answers": ["A"]})
    L.answer_from_tutorial(deck(), [{"q": "Q", "reference_answer": "SECRET_GOLD"}])
    assert "Accessible explanation" in captured[0]["lesson"]
    assert "SECRET_GOLD" not in json.dumps(captured)


@pytest.mark.parametrize("answers", [[], [None], ["one", "two"], "string"])
def test_answers_are_never_padded_or_coerced(answers):
    with pytest.raises(ValueError): L._answers({"answers": answers}, 1)


@pytest.mark.parametrize("verdicts", [[], [None], [{}], ["invalid"]])
def test_malformed_grades_are_unavailable(monkeypatch, verdicts):
    monkeypatch.setattr(L, "ask_json", lambda *a: {"verdicts": verdicts})
    with pytest.raises(ValueError): L.score_answers([{"q": "Q", "reference_answer": "A"}], ["A"])


def test_partial_and_uncovered_points(monkeypatch):
    monkeypatch.setattr(L, "ask_json", lambda *a: {"verdicts": ["correct", "partial", "correct"]})
    grade = L.score_answers([{"q": "Q", "reference_answer": "A"}] * 3, ["A", "part", "NOT_COVERED"])
    assert grade["points"] == [1, .5, 0] and grade["score"] == .5


def test_quality_and_grounding_are_independent():
    quality = {k: {"score": 4, "reason": "Evidence"} for k in J.QUALITY}
    assert J.score_judgment(deck(), {"items": [], "quality": quality})["quality"] == 4
    rows = [{"index": i, "supported": True, "reason": "Source"} for i in range(3)]
    score = J.score_judgment(deck(), {"items": rows})
    assert score["grounded"] == 1 and score["quality"] is None
    assert score["source_slides"] == 3


def test_grounding_denominator_uses_actual_source_labels():
    d = deck(); d["slides"][1]["provenance"] = "supplementary"
    rows = [{"index": i, "supported": i == 0, "reason": "Evidence"} for i in range(3)]
    score = J.score_judgment(d, {"items": rows, "total_source_slides": 99})
    assert score["grounded"] == .5 and score["source_slides"] == 2


def test_citation_denominators_include_malformed_and_foreign_entries():
    d = deck(); d["slides"] = d["slides"][:1]
    d["slides"][0]["citations"] = [{"chunk_id": "c1"}, {}, None, "bad", {"chunk_id": "foreign"}]
    score = J.citation_stats(d, lambda cid: cid == "c1")
    assert score["citation_validity"] == .2 and score["citation_entries"] == 5
    d["slides"][0]["citations"] = None
    assert J.citation_stats(d, lambda cid: True)["citation_entries"] == 1
    d["slides"][0]["citations"] = []
    assert J.citation_stats(d, lambda cid: True)["citation_validity"] is None


@pytest.mark.parametrize("response", [{"reply": "clarify"}, {"deck": {"title": "Empty", "slides": []}}])
def test_empty_or_chat_only_generation_is_a_visible_failure(response):
    result = R.classify({"status": "ok", "output": response})
    assert not result["completed"] and result["response"] == response


def test_failed_step_is_saved_and_never_repeated():
    count = []
    def fail():
        count.append(1)
        raise ValueError("Failure")
    assert R._step("generation", fail)["status"] == "failed"
    assert R._step("generation", fail)["status"] == "failed"
    assert len(count) == 1
    assert json.loads((R.OUT / "results.json").read_text())["steps"]["generation"]["error"] == "Failure"


def test_unsupported_assessment_is_rejected(monkeypatch):
    monkeypatch.setattr(Q, "ask_json", lambda *a: {"items": [{"index": 0, "supported": False, "unambiguous": True, "reason": "Unsupported"}]})
    with pytest.raises(ValueError): Q.validate_questions("Source", [{"q": "Q", "reference_answer": "A"}])


@pytest.mark.parametrize("change", ["neighbor", "insert", "delete", "reorder"])
def test_edit_scope_detects_other_changes(change):
    before, after = deck(), deck()
    after["slides"][1]["bullets"] = ["Simplified"]
    if change == "neighbor": after["slides"][0]["notes"] = "Changed"
    elif change == "insert": after["slides"].append(copy.deepcopy(after["slides"][0]))
    elif change == "delete": after["slides"].pop()
    else: after["slides"][0], after["slides"][2] = after["slides"][2], after["slides"][0]
    assert not I.scope_preservation(before, after)["scope_preserved"]


def test_failed_edit_does_not_reuse_previous_deck(monkeypatch):
    R.DATA["steps"]["college/setup"] = {"status": "ok", "output": {"course_id": "cid"}}
    monkeypatch.setattr(R, "_post", lambda *a: {"reply": "Cannot edit"})
    initial = {"completed": True, "response": {"deck": deck(), "artifact_id": "aid"}}
    assert not R.run_interaction_task({"dataset": "college"}, initial)["completed"]


def test_core_preserves_failures_and_does_not_leak_gold(monkeypatch):
    import app.store.db as db
    import app.llm.embeddings as embeddings
    captured = []
    monkeypatch.setattr(embeddings, "embed", lambda *a: [[1.]])
    monkeypatch.setattr(db, "SessionLocal", lambda: nullcontext("session"))
    monkeypatch.setattr(R, "answer_without_tutorial", lambda *a: ["A"])
    monkeypatch.setattr(R, "score_answers", lambda *a: {"score": 1})
    monkeypatch.setattr(R, "_new_course_with_doc", lambda *a: {"course_id": "cid", "chunks": [{"chunk_id": "c1", "text": "Source"}]})
    monkeypatch.setattr(R, "system_generate", lambda *a: {"reply": "Clarify"})
    monkeypatch.setattr(R, "single_call_baseline", lambda *a, **k: captured.append((a, k)) or deck())
    monkeypatch.setattr(R, "rag_baseline", lambda *a, **k: captured.append((a, k)) or deck())
    monkeypatch.setattr(R, "_deck_metrics", lambda *a: {"answerability": .5})
    R.run_core({"dataset": "college", "source": "Source", "topic": "Topic", "source_path": "fixture.txt", "questions": [{"q": "Q", "reference_answer": "SECRET_GOLD"}]})
    cell = R.DATA["core"][0]["systems"]["system"]
    assert not cell["completed"] and cell["metrics"]["answerability"] == 0
    assert "SECRET_GOLD" not in json.dumps(captured)


def test_report_has_six_rows_and_distinguishes_unattempted():
    R._report()
    report = (R.OUT / "report.md").read_text()
    primary = report.split("## Primary comparison: initial attempts", 1)[1].split("### Quality dimensions", 1)[0]
    assert primary.count("| school |") == 3 and primary.count("| college |") == 3
    assert primary.count("| 0/0 |") == 6
    assert "N/A/N/A" not in report


def test_report_keeps_followup_separate_and_preserves_original_failure():
    failed = {"completed": False, "status": "invalid_output", "error": "Invalid provenance", "latency": 7,
              "metrics": {"answerability": 0., "questions": 5, "answer_points": [0] * 5}}
    R.DATA["core"] = [{"dataset": "college", "systems": {"b1": copy.deepcopy(failed)}}]
    R.DATA["followups"] = [{"id": "college_b1_attempt2", "dataset": "college", "system": "b1", "attempt": 2,
                            "identical_generation_messages": True, **copy.deepcopy(failed)}]
    original = copy.deepcopy(R.DATA)
    R._report()
    report = (R.OUT / "report.md").read_text()
    assert R.DATA == original
    primary = report.split("## Primary comparison: initial attempts", 1)[1].split("### Quality dimensions", 1)[0]
    assert "attempt 2" not in primary
    assert "Single call — attempt 2" in report and "**0/2**" in report
    assert "0.0%†" in report and "not five measured incorrect answers" in report


def test_report_formats_diagnostics_as_text_without_json_escapes():
    R.DATA["personalization"] = [{"status": "ok", "output": {"differ": 4, "direction_correct": True, "note": "Explains β₁ appropriately."}}]
    R.DATA["interaction"] = [{"status": "ok", "unchanged_other_slides": 4, "other_slides": 4,
                             "judgment": {"status": "ok", "output": {"fulfilled": "yes", "meaning_preserved": True, "reason": "Simplifies β₁."}}}]
    R._report()
    report = (R.OUT / "report.md").read_text()
    assert "4/5" in report and "4/4" in report and "β₁" in report
    assert r"\u03b2" not in report and '"direction_correct"' not in report


def test_report_displays_reviewed_score_and_discloses_correction():
    R.DATA["core"] = [{"dataset": "college", "systems": {"system": {
        "completed": True, "status": "ok", "latency": 55.79,
        "metrics": {"answerability": .5, "answerability_before_review": .6,
                    "answer_points": [1, 0, 1, .5, 0], "questions": 5}}}}]
    R.DATA["score_review"] = {"reviews": [{"condition": "system"}]}
    R._report()
    report = (R.OUT / "report.md").read_text()
    primary = report.split("## Primary comparison: initial attempts", 1)[1].split("### Quality dimensions", 1)[0]
    assert "50.0% (2.5/5)" in primary
    assert "60.0% (3/5)" not in primary
    assert "Scoring correction applied" in primary


def test_excerpt_keeps_complete_paragraphs():
    text = "first" * 60 + "\n\n" + "tail" * 100
    assert R.excerpt(text, 350) == "first" * 60
