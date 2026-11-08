# The Grader. A tool using agent built on run_agent. It reads the student's
# answers to a quiz, decides for each one whether it is right, partial, or
# wrong by meaning (not string matching), and writes feedback that explains
# the correct idea with a citation to the source. It can search the material
# to check the student's wording against what the source says. It also names
# the misconception behind a wrong or partial answer, which is handed to the
# memory agent so the learner notes learn from it.
#
# The tool handlers only do mechanical checks (the question exists, the cited
# chunk is real) and return errors so the model can fix them. Every judgment
# is the model's.

import json

from app.agents.agent_loop import run_agent
from app.agents.quiz_builder import resolve_citations
from app.ingest.retrieve import retrieve

MAX_STEPS = 12

TOOLS = [
    {"type": "function", "function": {
        "name": "retrieve",
        "description": "Search the student's material to check an answer or find the passage that explains the idea.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "record_grade",
        "description": "Record the grade and cited feedback for one question.",
        "parameters": {
            "type": "object",
            "properties": {
                "question_id": {"type": "string"},
                "verdict": {"type": "string", "enum": ["right", "partial", "wrong"]},
                "feedback": {
                    "type": "string",
                    "description": "short feedback to the student that explains the correct idea using the cited chunks",
                },
                "provenance": {
                    "type": "string",
                    "enum": ["source", "supplementary"],
                    "description": "source if the explanation comes from the material, supplementary if not",
                },
                "chunk_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "the chunk ids that back the explanation",
                },
                "misconception": {
                    "type": "string",
                    "description": "for a wrong or partial answer, what the student seems to misunderstand",
                },
            },
            "required": ["question_id", "verdict", "feedback", "provenance"],
        },
    }},
    {"type": "function", "function": {
        "name": "finish",
        "description": "Call this when every question has a grade.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


def grade_quiz(session, course_id, quiz: dict, answers: dict) -> list[dict]:
    # answers: {question_id: the student's answer text}.
    # returns one grade per question, in quiz order.
    questions = quiz.get("questions", [])
    by_id = {q["id"]: q for q in questions}
    grades = {}

    def retrieve_tool(args):
        rows = retrieve(session, course_id, args.get("query", ""), k=4)
        return {"chunks": [{"chunk_id": r.id, "text": r.text[:500], "loc": r.location} for r in rows]}

    def record_grade(args):
        qid = args.get("question_id")
        if qid not in by_id:
            return {"ok": False, "error": f"question {qid} not found", "valid_ids": list(by_id)}
        if not (args.get("feedback") or "").strip():
            return {"ok": False, "error": "feedback must explain the correct idea"}
        provenance = args.get("provenance", "source")
        citations, error = resolve_citations(session, course_id, args.get("chunk_ids") or [])
        if error:
            return {"ok": False, "error": error}
        if provenance == "source" and not citations:
            return {"ok": False, "error": "source feedback must cite at least one chunk id from the material"}
        grades[qid] = {
            "question_id": qid,
            "verdict": args.get("verdict"),
            "feedback": args["feedback"],
            "provenance": provenance,
            "citations": citations if provenance == "source" else [],
            "misconception": args.get("misconception", ""),
        }
        return {"ok": True, "graded": len(grades), "of": len(by_id)}

    system = (
        "You grade a student's quiz answers and teach from their mistakes. For each question, compare the "
        "student's answer to the correct answer by meaning, not by exact wording. Give 'right' when the "
        "idea is correct, 'partial' when it is on the right track but missing or blurring something "
        "important, and 'wrong' otherwise. A blank answer is wrong. For every question call record_grade "
        "with short, encouraging feedback that explains the correct idea using the source material and "
        "cites the chunk ids it comes from. Put chunk ids only in chunk_ids, never in the feedback text, "
        "because the app shows them as source links. Use the question's cited chunks, and use retrieve to look up "
        "the material when you need to check something. Only mark feedback 'supplementary' when the "
        "material does not cover the idea. For a wrong or partial answer, name the misconception in one "
        "short line. If a tool returns an error, fix it and call it again. Call finish when every "
        "question is graded."
    )
    view = [
        {
            "question_id": q["id"],
            "kind": q.get("kind"),
            "stem": q.get("stem"),
            "options": q.get("options", []),
            "correct_answer": q.get("answer"),
            "explanation": q.get("explanation"),
            "cited_chunk_ids": [c.get("chunk_id") for c in q.get("citations", [])],
            "student_answer": answers.get(q["id"], ""),
        }
        for q in questions
    ]
    user = "Quiz and student answers:\n" + json.dumps(view)
    run_agent(system, user, TOOLS, {"retrieve": retrieve_tool, "record_grade": record_grade}, max_steps=MAX_STEPS)

    # if the loop hit its step fuse before grading everything, say so plainly
    # rather than inventing a grade.
    return [
        grades.get(q["id"]) or {
            "question_id": q["id"],
            "verdict": "ungraded",
            "feedback": "The grader did not finish this question. Please submit again.",
            "provenance": "supplementary",
            "citations": [],
            "misconception": "",
        }
        for q in questions
    ]
