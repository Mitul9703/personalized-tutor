# The evaluation harness, built around learning rather than deck mechanics.
#
# It compares our system against two baselines on the same inputs and the same
# model (gpt-6-luna), so a difference is architectural:
#   B1 single call  - whole document in one prompt, no retrieval.
#   B2 RAG one-shot - retrieve top chunks, then one generation. No planner,
#                     critic, learner model, or interaction.
#
# Headline (does the student learn?):
#   - teaching effectiveness: a simulated student reads ONLY the tutorial,
#     answers source-based questions, is scored. A no-tutorial control shows
#     prior knowledge, so the lift is honest.
#   - pedagogy: a learning-science rubric.
#   - personalization: our system under a beginner vs an advanced profile.
#   - interaction quality: can the student steer the deck after the fact
#     (explain deeper, simplify, add example) and stay grounded. The baselines
#     cannot do this at all.
#
# Guardrails (is it trustworthy?):
#   - groundedness, citation validity.
# Agent behavior:
#   - planted-error catch rate (does the Critic catch an injected false claim).
# Footnote: latency.
#
# Run with the backend up:
#   cd backend && .venv/bin/python ../eval/run_eval.py [limit_per_dataset] [questions] [pers_per_dataset] [interaction_per_dataset]

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
from baselines import single_call_baseline, rag_baseline  # noqa: E402
from questions import make_questions  # noqa: E402
from learner import answer_from_tutorial, answer_without_tutorial, score_answers  # noqa: E402
from pedagogy import pedagogy_score  # noqa: E402
from judge import judge_deck, groundedness, citation_validity  # noqa: E402
import personalization as pz  # noqa: E402
import agent_behavior as ab  # noqa: E402
import interaction as itx  # noqa: E402

BASE = os.environ.get("TUTOR_API", "http://localhost:8001")


def _post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))


def _upload(course_id, path):
    body = open(path, "rb").read()
    b = "----evalb"
    payload = (
        f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: text/plain\r\n\r\n"
    ).encode() + body + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(BASE + f"/courses/{course_id}/documents", data=payload,
                                 method="POST", headers={"content-type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=900)


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


def _rate(flags):
    vals = [bool(f) for f in flags if f is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


# ---- per-deck metrics shared by our system and both baselines ----

def _deck_metrics(deck, doc, questions):
    teach = _safe(lambda: score_answers(questions, answer_from_tutorial(deck, questions))) if questions else None
    return {
        "teach": teach["score"] if teach else None,
        "pedagogy": _safe(lambda: pedagogy_score(deck, ""), {}).get("mean"),
        "grounded": _safe(lambda: groundedness(judge_deck(deck, doc))),
        "cite_valid": _safe(lambda: citation_validity(deck, resolve_chunk)),
        "slides": len(deck.get("slides", [])),
    }


def run_core(task, qn):
    ds, topic = task["dataset"], task["topic"]
    doc = load_doc(task["doc"])
    print(f"[{ds}] {os.path.basename(task['doc'])} :: {topic}")

    questions = _safe(lambda: make_questions(doc, topic, n=qn), []) or []
    control = _safe(lambda: score_answers(questions, answer_without_tutorial(questions))) if questions else None

    # our system
    course_id = _new_course_with_doc(task["doc"])
    sys_deck, sys_lat = system_generate(course_id, topic)
    sysm = _deck_metrics(sys_deck, doc, questions); sysm["latency"] = round(sys_lat, 1)

    # B1 single call
    t0 = time.time(); b1_deck = single_call_baseline(doc, topic); b1_lat = time.time() - t0
    b1m = _deck_metrics(b1_deck, doc, questions); b1m["latency"] = round(b1_lat, 1)

    # B2 RAG one-shot
    t0 = time.time(); b2_deck = rag_baseline(doc, topic); b2_lat = time.time() - t0
    b2m = _deck_metrics(b2_deck, doc, questions); b2m["latency"] = round(b2_lat, 1)

    catch = _safe(lambda: ab.catch_check(course_id, sys_deck, topic), {}) or {}

    rec = {"dataset": ds, "doc": os.path.basename(task["doc"]), "topic": topic,
           "n_questions": len(questions), "control": control["score"] if control else None,
           "system": sysm, "b1": b1m, "b2": b2m, "catch": catch}
    print(f"   teach   : ctrl={rec['control']} ours={sysm['teach']} b1={b1m['teach']} b2={b2m['teach']}")
    print(f"   grounded: ours={sysm['grounded']} b1={b1m['grounded']} b2={b2m['grounded']}  "
          f"catch={catch.get('caught')} clean_ok={catch.get('clean_passed')}")
    return rec


def run_personalization(task):
    ds, topic = task["dataset"], task["topic"]
    print(f"[pers/{ds}] {topic}")
    nov = _new_course_with_doc(task["doc"]); pz.set_learner_notes(nov, pz.NOVICE)
    nov_deck, _ = system_generate(nov, topic)
    adv = _new_course_with_doc(task["doc"]); pz.set_learner_notes(adv, pz.ADVANCED)
    adv_deck, _ = system_generate(adv, topic)
    d = _safe(lambda: pz.differentiation(nov_deck, adv_deck), {}) or {}
    rec = {"dataset": ds, "topic": topic, "differ": d.get("differ"),
           "direction_correct": d.get("direction_correct"), "note": d.get("note")}
    print(f"   differ={rec['differ']}/5 direction_correct={rec['direction_correct']} {rec['note']}")
    return rec


def run_interaction_task(task):
    print(f"[interaction] {task['topic']}")
    rec = _safe(lambda: itx.run_interaction(task["doc"], task["topic"]), {}) or {}
    print(f"   fulfillment={rec.get('fulfillment')} grounded_after={rec.get('grounded_after')}")
    return rec


def run(limit=None, qn=5, pers_limit=1, itx_limit=1):
    core, pers, inter = [], [], []
    c, pc, ic = {}, {}, {}
    for task in TASKS:
        ds = task["dataset"]
        c[ds] = c.get(ds, 0) + 1
        if not (limit and c[ds] > limit):
            core.append(_safe(lambda t=task: run_core(t, qn)))
        if pc.get(ds, 0) < pers_limit:
            pc[ds] = pc.get(ds, 0) + 1
            pers.append(_safe(lambda t=task: run_personalization(t)))
        if ic.get(ds, 0) < itx_limit:
            ic[ds] = ic.get(ds, 0) + 1
            inter.append(_safe(lambda t=task: run_interaction_task(t)))
    core = [r for r in core if r]; pers = [r for r in pers if r]; inter = [r for r in inter if r]
    _report(core, pers, inter)
    out = os.path.join(HERE, "results.json")
    json.dump({"core": core, "personalization": pers, "interaction": inter}, open(out, "w"), indent=2)
    print(f"\nsaved {out}")


def _report(core, pers, inter):
    print("\n================ RESULTS ================")
    for ds in ("novel", "public", "ml", "large"):
        rows = [r for r in core if r["dataset"] == ds]
        if not rows:
            continue
        print(f"\nDataset: {ds}  (n={len(rows)})")
        print(f"{'metric':<24}{'OURS':>9}{'B1 single':>11}{'B2 rag':>9}")

        def col(key, which):
            return _mean([r[which][key] for r in rows])
        print("-- headline: learning --")
        print(f"{'teaching effectiveness':<24}{str(col('teach','system')):>9}{str(col('teach','b1')):>11}{str(col('teach','b2')):>9}")
        print(f"{'  (no-tutorial control)':<24}{str(_mean([r['control'] for r in rows])):>9}")
        print(f"{'pedagogy (1-5)':<24}{str(col('pedagogy','system')):>9}{str(col('pedagogy','b1')):>11}{str(col('pedagogy','b2')):>9}")
        print("-- guardrails --")
        print(f"{'groundedness':<24}{str(col('grounded','system')):>9}{str(col('grounded','b1')):>11}{str(col('grounded','b2')):>9}")
        print(f"{'citation validity':<24}{str(col('cite_valid','system')):>9}{str(col('cite_valid','b1')):>11}{str(col('cite_valid','b2')):>9}")
        print("-- agent behavior (our system) --")
        print(f"{'critic catch rate':<24}{str(_rate([r['catch'].get('caught') for r in rows])):>9}")
        print(f"{'clean-pass rate':<24}{str(_rate([r['catch'].get('clean_passed') for r in rows])):>9}")
        print("-- footnote --")
        print(f"{'latency (s)':<24}{str(col('latency','system')):>9}{str(col('latency','b1')):>11}{str(col('latency','b2')):>9}")

    if pers:
        print("\nPersonalization (our system; baselines have no learner model):")
        for r in pers:
            print(f"  [{r['dataset']}] differ={r['differ']}/5 direction_correct={r['direction_correct']}")
    if inter:
        print("\nInteraction quality (our system; baselines cannot interact at all):")
        for r in inter:
            print(f"  {r.get('topic','')}: fulfillment={r.get('fulfillment')} grounded_after={r.get('grounded_after')}")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    qn = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    pl = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    il = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    run(lim, qn, pl, il)
