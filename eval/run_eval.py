# The evaluation harness, built around learning rather than deck mechanics.
#
# Headline (does the student learn?):
#   - teaching effectiveness: a simulated student reads ONLY the tutorial,
#     answers source based questions, and is scored. We also answer with no
#     tutorial at all (prior-knowledge control) so the tutorial's lift is honest.
#   - personalization: our system under a beginner vs an advanced profile;
#     do the lessons differ in the right direction? The baseline has no
#     learner model, so it cannot personalize at all.
#   - pedagogy: a learning-science rubric (scaffolding, concreteness, checks,
#     load, clarity), not a flat "quality" number.
#
# Guardrails (is it trustworthy?):
#   - groundedness: of source slides, the fraction the judge finds supported.
#   - citation validity: of all citations, the fraction that resolve to a
#     real, retrievable chunk. Our citations resolve; the baseline invents them.
#
# Footnote: latency.
#
# Run with the backend up:
#   cd backend && .venv/bin/python ../eval/run_eval.py [limit_per_dataset] [questions] [pers_per_dataset]

import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "backend"))

from tasks import TASKS, load_doc  # noqa: E402
from baselines import single_call_baseline  # noqa: E402
from questions import make_questions  # noqa: E402
from learner import answer_from_tutorial, answer_without_tutorial, score_answers  # noqa: E402
from pedagogy import pedagogy_score  # noqa: E402
from judge import judge_deck, groundedness, citation_validity  # noqa: E402
import personalization as pz  # noqa: E402

BASE = os.environ.get("TUTOR_API", "http://localhost:8001")


def _post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=600))


def _upload(course_id, path):
    body = open(path, "rb").read()
    b = "----evalb"
    payload = (
        f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: text/plain\r\n\r\n"
    ).encode() + body + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + f"/courses/{course_id}/documents", data=payload,
                                 method="POST", headers={"content-type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=600)


def _new_course_with_doc(doc_path):
    course_id = _post("/courses", {"title": "eval"})["course_id"]
    _upload(course_id, doc_path)
    return course_id


def system_generate(course_id, topic):
    t0 = time.time()
    res = _post(f"/courses/{course_id}/messages", {"text": f"teach me about {topic}"})
    return res.get("deck", {"slides": []}), time.time() - t0


def resolve_chunk(chunk_id):
    try:
        with urllib.request.urlopen(BASE + f"/chunks/{chunk_id}", timeout=60) as r:
            return r.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return False


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        print(f"      (metric failed: {e})")
        return default


def _mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


# ---------------- core run (teaching, pedagogy, guardrails) ----------------

def run_core(task, qn):
    ds, topic = task["dataset"], task["topic"]
    doc = load_doc(task["doc"])
    print(f"[{ds}] {os.path.basename(task['doc'])} :: {topic}")

    questions = _safe(lambda: make_questions(doc, topic, n=qn), []) or []
    print(f"   {len(questions)} questions")

    course_id = _new_course_with_doc(task["doc"])
    sys_deck, sys_lat = system_generate(course_id, topic)

    t0 = time.time()
    base_deck = single_call_baseline(doc, topic)
    base_lat = time.time() - t0

    # teaching effectiveness
    control = _safe(lambda: score_answers(questions, answer_without_tutorial(questions))) if questions else None
    teach_sys = _safe(lambda: score_answers(questions, answer_from_tutorial(sys_deck, questions))) if questions else None
    teach_base = _safe(lambda: score_answers(questions, answer_from_tutorial(base_deck, questions))) if questions else None

    rec = {
        "dataset": ds, "doc": os.path.basename(task["doc"]), "topic": topic,
        "n_questions": len(questions),
        "teach_control": control["score"] if control else None,
        "teach_system": teach_sys["score"] if teach_sys else None,
        "teach_baseline": teach_base["score"] if teach_base else None,
        "pedagogy_system": _safe(lambda: pedagogy_score(sys_deck, topic), {}).get("mean"),
        "pedagogy_baseline": _safe(lambda: pedagogy_score(base_deck, topic), {}).get("mean"),
        "grounded_system": _safe(lambda: groundedness(judge_deck(sys_deck, doc))),
        "grounded_baseline": _safe(lambda: groundedness(judge_deck(base_deck, doc))),
        "cite_valid_system": _safe(lambda: citation_validity(sys_deck, resolve_chunk)),
        "cite_valid_baseline": _safe(lambda: citation_validity(base_deck, resolve_chunk)),
        "latency_system": round(sys_lat, 1), "latency_baseline": round(base_lat, 1),
        "slides_system": len(sys_deck.get("slides", [])), "slides_baseline": len(base_deck.get("slides", [])),
    }
    print(f"   teaching : control={rec['teach_control']} system={rec['teach_system']} baseline={rec['teach_baseline']}")
    print(f"   pedagogy : system={rec['pedagogy_system']} baseline={rec['pedagogy_baseline']}")
    print(f"   grounded : system={rec['grounded_system']} baseline={rec['grounded_baseline']}  "
          f"cite_valid: system={rec['cite_valid_system']} baseline={rec['cite_valid_baseline']}")
    return rec


# ---------------- personalization run (our system only) ----------------

def run_personalization(task):
    ds, topic = task["dataset"], task["topic"]
    print(f"[pers/{ds}] {topic}")

    nov_course = _new_course_with_doc(task["doc"])
    pz.set_learner_notes(nov_course, pz.NOVICE)
    nov_deck, _ = system_generate(nov_course, topic)

    adv_course = _new_course_with_doc(task["doc"])
    pz.set_learner_notes(adv_course, pz.ADVANCED)
    adv_deck, _ = system_generate(adv_course, topic)

    d = _safe(lambda: pz.differentiation(nov_deck, adv_deck), {}) or {}
    rec = {"dataset": ds, "topic": topic, "differ": d.get("differ"),
           "direction_correct": d.get("direction_correct"), "note": d.get("note")}
    print(f"   differ={rec['differ']}/5  direction_correct={rec['direction_correct']}  {rec['note']}")
    return rec


def run(limit=None, qn=5, pers_limit=1):
    core, pers = [], []
    counts, pcounts = {}, {}
    for task in TASKS:
        ds = task["dataset"]
        counts[ds] = counts.get(ds, 0) + 1
        if not (limit and counts[ds] > limit):
            core.append(_safe(lambda t=task: run_core(t, qn)))
        if pcounts.get(ds, 0) < pers_limit:
            pcounts[ds] = pcounts.get(ds, 0) + 1
            pers.append(_safe(lambda t=task: run_personalization(t)))
    core = [r for r in core if r]
    pers = [r for r in pers if r]
    _report(core, pers)
    out = os.path.join(HERE, "results.json")
    json.dump({"core": core, "personalization": pers}, open(out, "w"), indent=2)
    print(f"\nsaved {out}")


def _report(core, pers):
    print("\n================ RESULTS ================")
    for ds in ("novel", "public", "ml"):
        rows = [r for r in core if r["dataset"] == ds]
        if not rows:
            continue
        print(f"\nDataset: {ds}  (n={len(rows)})")
        print(f"{'metric':<26}{'OUR SYSTEM':>12}{'BASELINE':>12}")
        print("-- headline: learning --")
        print(f"{'teaching effectiveness':<26}{str(_mean([r['teach_system'] for r in rows])):>12}"
              f"{str(_mean([r['teach_baseline'] for r in rows])):>12}")
        print(f"{'  (no-tutorial control)':<26}{str(_mean([r['teach_control'] for r in rows])):>12}{'':>12}")
        print(f"{'pedagogy (1-5)':<26}{str(_mean([r['pedagogy_system'] for r in rows])):>12}"
              f"{str(_mean([r['pedagogy_baseline'] for r in rows])):>12}")
        print("-- guardrails: trust --")
        print(f"{'groundedness':<26}{str(_mean([r['grounded_system'] for r in rows])):>12}"
              f"{str(_mean([r['grounded_baseline'] for r in rows])):>12}")
        print(f"{'citation validity':<26}{str(_mean([r['cite_valid_system'] for r in rows])):>12}"
              f"{str(_mean([r['cite_valid_baseline'] for r in rows])):>12}")
        print("-- footnote --")
        print(f"{'latency (s)':<26}{str(_mean([r['latency_system'] for r in rows])):>12}"
              f"{str(_mean([r['latency_baseline'] for r in rows])):>12}")

    if pers:
        print(f"\nPersonalization (our system; baseline has no learner model, cannot personalize)")
        for r in pers:
            print(f"  [{r['dataset']}] {r['topic']}: differ={r['differ']}/5 "
                  f"direction_correct={r['direction_correct']}")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    qn = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    pl = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    run(lim, qn, pl)
