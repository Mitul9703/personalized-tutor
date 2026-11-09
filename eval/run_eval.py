"""Six-deck preliminary evaluation. Run from backend/; see eval/README.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
from app.config import settings
from tasks import TASKS, load_doc
from baselines import REQUEST, chunk_view, single_call_baseline, rag_baseline, require_deck
import questions as Q
from learner import _deck_text, answer_from_tutorial, answer_without_tutorial, score_answers
from judge import QUALITY, judge_deck, score_judgment, citation_stats
import personalization as pz
import interaction as itx

BASE = os.environ.get("TUTOR_API", "http://127.0.0.1:8010").rstrip("/")
OUT = HERE / "data/runs" / os.environ.get("EVAL_RUN_ID", "school_college")
DATA = {"steps": {}, "inputs": [], "core": [], "personalization": [], "interaction": []}
LABELS = {"b1": "Single call", "b2": "Fixed RAG", "system": "Proposed system"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def _step(key, fn):
    """Save before and after each operation; never automatically repeat POSTs."""
    if key in DATA["steps"]:
        return DATA["steps"][key]
    previous, Q.PHASE = Q.PHASE, key
    row = {"status": "running", "started_at": now()}
    DATA["steps"][key] = row
    save(OUT / "results.json", DATA)
    start = time.monotonic()
    print(key, flush=True)
    try:
        row.update(status="ok", output=fn())
    except Exception as error:
        message = str(error).replace(settings.llm_api_key, "[redacted]") if settings.llm_api_key else str(error)
        row.update(status="failed", error=message[:5000])
    finally:
        row.update(seconds=time.monotonic() - start, finished_at=now())
        save(OUT / "results.json", DATA)
        Q.PHASE = previous
    print(" ", row["status"], row.get("error", ""), flush=True)
    return row


def value(row):
    return row.get("output") if row and row["status"] == "ok" else None


def _request(method, path, body=None, upload=None):
    headers, payload = {}, None
    if upload:
        boundary = "----tutorevaluation"
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{Path(upload).name}"\r\n'
                   'Content-Type: text/plain\r\n\r\n').encode() + Path(upload).read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        headers["content-type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        payload, headers = json.dumps(body).encode(), {"content-type": "application/json"}
    Q.log("api_request", method=method, path=path, body=body)
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, data=payload, method=method, headers=headers), timeout=900) as response:
            raw = response.read().decode()
    except urllib.error.HTTPError as error:
        Q.log("api_failure", path=path, status=error.code, body=error.read().decode(errors="replace"))
        raise RuntimeError(f"HTTP {error.code}: {path}") from error
    Q.log("api_response", path=path, raw=raw)
    return json.loads(raw)


def _post(path, body):
    return _request("POST", path, body)


def require_database():
    from sqlalchemy.engine import make_url
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith(("_eval", "_test")):
        raise ValueError("Set DATABASE_URL to a dedicated Postgres database ending in _eval or _test")
    if os.environ.get("TUTOR_DB") and make_url(os.environ["TUTOR_DB"]) != url:
        raise ValueError("TUTOR_DB and DATABASE_URL disagree")
    return url


def _new_course_with_doc(path, profile=pz.NOVICE):
    from app.store.db import SessionLocal
    from app.store.models import Chunk, Document, LearnerModel
    cid = _post("/courses", {"title": "Evaluation: " + Path(path).stem})["course_id"]
    saved = _post(f"/courses/{cid}/onboarding", profile)
    if saved.get("profile") != profile:
        raise ValueError("Onboarding profile mismatch")
    uploaded = _request("POST", f"/courses/{cid}/documents", upload=path)
    if uploaded.get("status") != "ready" or uploaded.get("chunks", 0) <= 0:
        raise ValueError("Upload did not produce ready chunks")
    with SessionLocal() as session:
        document = session.get(Document, uploaded["document_id"])
        learner = session.query(LearnerModel).filter_by(course_id=cid).first()
        rows = session.query(Chunk).filter_by(course_id=cid).order_by(Chunk.ordinal).all()
        if not document or document.course_id != cid or not learner or learner.profile != profile or len(rows) != uploaded["chunks"]:
            raise ValueError("API and evaluator database do not match")
        chunks = chunk_view(rows, Path(path).name)
    survey = _post(f"/courses/{cid}/survey", {})
    return {"course_id": cid, "document_id": uploaded["document_id"], "chunks": chunks, "profile": profile, "survey": survey}


def system_generate(course_id, topic):
    return _post(f"/courses/{course_id}/messages", {"text": REQUEST.format(topic=topic)})


def classify(row):
    if value(row) is None:
        return {"completed": False, "status": row["status"], "error": row.get("error", "Interrupted operation")}
    response = value(row)
    try:
        require_deck(response.get("deck") if isinstance(response, dict) else None)
    except ValueError as error:
        return {"completed": False, "status": "invalid_output", "response": response, "error": str(error)}
    return {"completed": True, "status": "ok", "response": response}


def excerpt(source, maximum=50000):
    if len(source) > maximum:
        end = source.rfind("\n\n", 0, maximum)
        if end < 200:
            raise ValueError("No complete paragraphs within the source limit")
        source = source[:end]
    return source.strip()


def prepare(tasks, qn):
    from download_data import selected_sources
    from app.ingest.chunk import chunk_segments
    selected_sources()
    for task in tasks:
        ds = task["dataset"]
        frozen = OUT / "sources" / (ds + ".txt")
        existing = next((c for c in DATA["inputs"] if c["dataset"] == ds), None)
        if existing:
            if not frozen.exists() or digest(frozen.read_bytes()) != existing["source_sha256"]:
                raise ValueError("Frozen source changed")
            continue
        source = excerpt(load_doc(task["doc"]))
        authored = _step(ds + "/questions", lambda: Q.make_questions(source, task["topic"], qn))
        if value(authored) is None:
            raise ValueError("Assessment authoring failed; no evaluated generation started")
        checked = _step(ds + "/validation", lambda: Q.validate_questions(source, value(authored)))
        if value(checked) is None:
            feedback = checked.get("error", "Invalid validation response")
            revised = _step(ds + "/revised_questions", lambda: Q.make_questions(source, task["topic"], qn, previous=value(authored), feedback=feedback))
            if value(revised) is not None:
                checked = _step(ds + "/revised_validation", lambda: Q.validate_questions(source, value(revised)))
                authored = revised
        if value(checked) is None:
            raise ValueError("Assessment revalidation failed; freezing blocked")
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text(source, encoding="utf-8")
        case = {**task, "source_path": str(frozen), "source": source, "source_sha256": digest(source.encode()),
                "provenance": json.loads(Path(task["doc"]).with_suffix(".meta.json").read_text()),
                "selected_chars": len(load_doc(task["doc"])), "evaluated_chars": len(source), "words": len(source.split()),
                "chunk_count": len(chunk_segments([{"text": source, "page": None}])),
                "questions": value(authored), "validation": value(checked), "frozen_at": now()}
        DATA["inputs"].append(case)
        save(OUT / "results.json", DATA)
    save(OUT / "inputs.json", DATA["inputs"])


def resolve_chunk(cid, chunks, source):
    allowed = {c["chunk_id"] for c in chunks}
    if cid not in allowed:
        return False
    try:
        response = _request("GET", f"/chunks/{cid}")
    except RuntimeError as error:
        if str(error).startswith("HTTP 404"):
            return False
        raise
    text = response.get("text")
    return isinstance(text, str) and bool(text) and text in source


def _deck_metrics(deck, case, workspace, prefix):
    # Each dimension is independent: failed scoring does not erase valid measurements.
    source, questions = case["source"], case["questions"]
    answers = _step(prefix + "/answers", lambda: answer_from_tutorial(deck, questions))
    grade = _step(prefix + "/grades", lambda: score_answers(questions, value(answers))) if value(answers) is not None else None
    judged = _step(prefix + "/judge", lambda: judge_deck(deck, source, case["topic"], pz.NOVICE))
    result = score_judgment(deck, value(judged))
    result.update(answerability=(value(grade) or {}).get("score"), answer_points=(value(grade) or {}).get("points"),
                  answerability_n=len((value(grade) or {}).get("points", [])),
                  questions=len(questions), words=len(_deck_text(deck).split()), slides=len(deck["slides"]))
    # Coverage and entry counts remain available even if a resolution request fails.
    result.update(citation_stats(deck, lambda cid: False))
    result["citation_validity"], result["valid_citations"] = None, None
    cache = {}
    def resolve(cid):
        if cid not in cache:
            cache[cid] = resolve_chunk(cid, workspace["chunks"], source)
        return cache[cid]
    citations = _step(prefix + "/citations", lambda: citation_stats(deck, resolve))
    if value(citations) is not None:
        result.update(value(citations))
    result["supplementary_fraction"] = 1 - result["source_slides"] / len(deck["slides"])
    return result


def run_core(case):
    from app.store.db import SessionLocal
    from app.llm.embeddings import embed
    ds = case["dataset"]
    answers = _step(ds + "/control_answers", lambda: answer_without_tutorial(case["questions"]))
    control = _step(ds + "/control_grade", lambda: score_answers(case["questions"], value(answers))) if value(answers) is not None else None
    setup = _step(ds + "/setup", lambda: _new_course_with_doc(case["source_path"]))
    result = {"dataset": ds, "topic": case["topic"], "control": (value(control) or {}).get("score"),
              "setup_seconds": setup["seconds"], "systems": {}}
    DATA["core"] = [r for r in DATA["core"] if r["dataset"] != ds] + [result]
    save(OUT / "results.json", DATA)
    if value(setup) is None:
        result["setup_error"] = setup.get("error", "Incomplete setup")
        return
    workspace = value(setup)
    warm = _step(ds + "/warmup", lambda: (embed(["evaluation warmup"]), {"warmed": True})[1])
    if value(warm) is None:
        result["setup_error"] = warm.get("error", "Embedding warmup failed")
        return
    embed(["evaluation warmup"])  # Also warm this process after resuming saved results.
    for method in LABELS:
        def generate():
            if method == "system":
                return system_generate(workspace["course_id"], case["topic"])
            if method == "b1":
                return {"deck": single_call_baseline(case["source"], case["topic"], chunks=workspace["chunks"], profile=pz.NOVICE)}
            with SessionLocal() as session:
                return {"deck": rag_baseline(case["source"], case["topic"], session=session, course_id=workspace["course_id"], filename=Path(case["source_path"]).name, profile=pz.NOVICE)}
        row = _step(ds + "/generate/" + method, generate)
        cell = classify(row)
        cell["latency"] = row["seconds"]
        if cell["completed"]:
            cell["metrics"] = _deck_metrics(cell["response"]["deck"], case, workspace, ds + "/" + method)
        else:
            cell["metrics"] = {"answerability": 0., "questions": len(case["questions"]), "answerability_n": len(case["questions"]), "answer_points": [0] * len(case["questions"])}
        result["systems"][method] = cell
        save(OUT / "results.json", DATA)


def run_personalization(case, initial):
    if not initial or not initial["completed"]:
        return {"status": "not_completed", "reason": "No valid beginner deck"}
    setup = _step("personalization/setup", lambda: _new_course_with_doc(case["source_path"], pz.ADVANCED))
    if value(setup) is None:
        return {"status": "not_completed", "reason": "Advanced setup failed"}
    generated = _step("personalization/generate", lambda: system_generate(value(setup)["course_id"], case["topic"]))
    advanced = classify(generated)
    if not advanced["completed"]:
        return advanced
    return _step("personalization/judge", lambda: pz.differentiation(initial["response"]["deck"], advanced["response"]["deck"]))


def run_interaction_task(case, initial):
    if not initial or not initial["completed"] or len(initial["response"]["deck"]["slides"]) < 2:
        return {"status": "not_completed", "reason": "No valid slide 2 in beginner deck"}
    before = initial["response"]["deck"]
    workspace = value(DATA["steps"][case["dataset"] + "/setup"])
    edit = _step("interaction/edit", lambda: _post(f"/courses/{workspace['course_id']}/messages", {
        "text": itx.COMMAND, "artifact_id": initial["response"]["artifact_id"]}))
    edited = classify(edit)
    if not edited["completed"]:
        return edited
    after = edited["response"]["deck"]
    judged = _step("interaction/judge", lambda: itx.judge_interaction(itx.COMMAND, before, after))
    return {"status": "ok", **itx.scope_preservation(before, after), "judgment": judged}


def fmt(value, pct=False):
    return "N/A" if value is None else (f"{value * 100:.1f}%" if pct else f"{value:.2f}")


def _report():
    """Render saved measurements; keep explicit follow-ups outside the primary cohort."""
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    identity = manifest.get("identity", {})
    indexed = {r["dataset"]: r for r in DATA["core"]}
    followups = DATA.get("followups", [])

    def text(value):
        return "N/A" if value is None else " ".join(str(value).split()).replace("|", "/")

    def ratio(metrics, name, numerator, denominator):
        if metrics.get(name) is None:
            return "N/A"
        return f"{fmt(metrics[name], True)} ({metrics[numerator]}/{metrics[denominator]})"

    def performance_row(ds, label, cell):
        metrics = cell.get("metrics", {}) if cell else {}
        completed = int(bool(cell and cell.get("completed")))
        completion = f"{completed}/{int(cell is not None)}"
        answer = fmt(metrics.get("answerability"), True)
        if cell and not cell.get("completed"):
            answer += "†"
        elif metrics.get("answerability") is not None:
            points = sum(metrics.get("answer_points") or [])
            answer += f" ({points:g}/{metrics['questions']})"
        return (f"| {ds} | {label} | {completion} | {answer} | {fmt(metrics.get('quality'))} | "
                f"{ratio(metrics, 'grounded', 'supported_slides', 'source_slides')} | "
                f"{ratio(metrics, 'citation_validity', 'valid_citations', 'citation_entries')} | "
                f"{fmt(cell.get('latency') if cell else None)} |")

    attempted = sum(len(c.get("systems", {})) for c in DATA["core"])
    completed = sum(cell.get("completed", False) for c in DATA["core"] for cell in c.get("systems", {}).values())
    lines = ["# Preliminary Evaluation Results", "",
             f"**Run:** `{OUT.name}`  ",
             f"**Model:** `{identity.get('model', 'not recorded')}` for generation, answering, and judging  ",
             f"**Created:** {manifest.get('created_at', 'not recorded')} (UTC)", "",
             f"The primary pilot contains two source/topic cases, ten frozen questions, and six planned initial generations. **{completed}/{attempted} initial attempts returned valid decks.** "
             + (f"There are also {len(followups)} explicitly requested follow-up attempt(s), reported separately below." if followups else "No additional generations are included."), "",
             "These are automated tutorial-answerability and instructional-quality estimates. No human learning or instructor-workload study was conducted.", "",
             "## Evaluation setup", "", "### Datasets", "",
             "| Dataset | Evaluated task | Original text, chars | Selected text, chars | Evaluated text, chars | Words | Chunks | Questions |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for case in DATA["inputs"]:
        lines.append(f"| {case['dataset']} | {case['topic']} | {case['provenance']['original_chars']:,} | {case['selected_chars']:,} | {case['evaluated_chars']:,} | {case['words']:,} | {case['chunk_count']} | {len(case['questions'])} |")
    lines += ["", "Both collections are public course materials and stakeholder-relevant proxies, rather than standardized benchmarks or stakeholder-provided data. School material tests foundational explanations and worked examples; college material tests technical explanations.", ""]
    for case in DATA["inputs"]:
        provenance = case["provenance"]
        links = ", ".join(f"[source {i + 1}]({url})" for i, url in enumerate(provenance["urls"]))
        lines += [f"- **{case['dataset'].title()}:** {provenance['attribution']}. Retrieved {provenance['retrieved_at']}. {provenance['extraction']}. {links}."]
    lines += ["", "School original text size covers the first 110 PDF pages before selecting the Integers chapter (PDF pages 33–44, printed pages 27–38). College original size covers three raw Markdown sections before cleaning. All systems are evaluated against the same frozen source: B1 receives all chunks, B2 receives eight retrieved chunks, and the proposed system accesses chunks through its retrieval tools. Judges receive the full frozen source. Complete paragraphs are retained within a 50,000-character cap; neither selected source required a paragraph cutoff. College's two-character reduction is leading-whitespace removal.", "",
              "Five questions and reference answers per case were authored from the source and independently checked for support and clarity before any lesson generation. Both passed the first check. Questions and keys were withheld from generators. There was no model training or train/test split; a separate development fixture was used. Frozen inputs, source hashes, and validation records are retained in [inputs.json](inputs.json).", "",
              "### Compared systems and execution conditions", "",
              "| Condition | Procedure |",
              "|---|---|",
              "| B1 — Single call | One generation call using all ingested source chunks. |",
              "| B2 — Fixed RAG | Application retrieval, k=8, followed by one generation call. |",
              "| Proposed system | Existing message API and router → planner → builder → critic workflow. |", "",
              "All systems receive the same beginner profile, topic, request for five concise slides, genuine source chunk IDs, and option to generate explanatory notes. Headings, bullets, and accessible **Go deeper** notes are scored. Application tool schemas constrain output fields; baselines request the same contract through JSON prompts. This enforcement difference can affect format reliability.", "",
              f"The embedding model is `{identity.get('embedding_model', 'not recorded')}`. Direct JSON calls and application tool calls use reasoning effort `none`; other application settings and SDK defaults remain unchanged. Agent limits are router 5, survey 8, planner 6, builder 10, critic 6, and three build attempts. The HTTP timeout is 900 seconds. The initial evaluator makes one generation attempt per condition; internal application retries remain enabled.", "",
              "Normal setup creates a course, saves onboarding, uploads the frozen text, and runs the survey. API and evaluator use the same dedicated database. Setup and embedding warmup are excluded from generation latency. Initial order is B1, B2, proposed. Latency is descriptive and may reflect ordering, transport behavior, or provider load. Full conditions and code hashes are in [manifest.json](manifest.json).", "",
              "### Scoring rules", "",
              "| Metric | Definition |",
              "|---|---|",
              "| Answerability | Lesson-only answers graded against references: correct = 1, partial = 0.5, incorrect/uncovered = 0; average over five questions. Parentheses show points / questions. |",
              "| Quality | Mean of alignment, learner appropriateness, and accuracy, each scored 1–5 with reasons. All three valid ratings are required. Anchors: 1 = complete redevelopment, 3 = moderate revisions, 5 = minimal edits. |",
              "| Groundedness | Source-labeled slides whose substantive claims are supported / source-labeled slides. |",
              "| Citation coverage | Source-labeled slides carrying citation entries / source-labeled slides. |",
              "| Citation validity | Entries resolving to chunks of the evaluated source / all citation entries. Malformed entries count as invalid. |",
              "| Completion | Valid, nonempty decks / attempted generations. This does not require exactly five slides; slide count is reported separately. |",
              "| Latency | Elapsed generation seconds, excluding setup, warmup, and scoring. |", "",
              "Judges receive no system identities and use the same rubric. Denominators are computed in code. Missing or malformed judgments remain **N/A**, independently of other valid metrics. Citation resolution does not establish semantic support.", "",
              "## Primary comparison: initial attempts", "",
              "| Dataset | System | Completed / attempted | Answerability | Quality / 5 | Groundedness | Citation validity | Latency, s |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for ds in ("school", "college"):
        for method, label in LABELS.items():
            lines.append(performance_row(ds, label, indexed.get(ds, {}).get("systems", {}).get(method)))
    if DATA.get("score_review"):
        lines += ["", "**Scoring correction applied:** college question 4 was reviewed across four anonymized saved answers in one consistency pass against the same frozen reference and correct/partial/wrong rubric. The proposed answer omitted the learning-rate factor η and was changed from correct (1 point) to partial (0.5). Its total therefore changed from 3/5 (60%) to 2.5/5 (50%). The control, fixed RAG, and format-clarified single-call scores were unchanged. This table uses the reviewed score; original grades and the rationale remain in [score_review.json](score_review.json) and the [original results snapshot](review_original_results.json). No lesson was regenerated for this scoring correction."]
    lines += ["", "**† Failure-policy score:** a generation that fails the output contract receives zero end-to-end answerability. No lesson-answering or content-quality judgment is performed for that failed output. This zero is a protocol penalty, not five measured incorrect answers. **N/A** means unavailable, not zero. Each dataset has one case and one initial attempt per system, so dataset means equal case scores (n=1). Follow-ups do not replace these rows.", "",
              "### Quality dimensions and output size", "",
              "| Dataset | System | Alignment | Appropriateness | Accuracy | Slides | Words |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for ds in ("school", "college"):
        for method, label in LABELS.items():
            cell = indexed.get(ds, {}).get("systems", {}).get(method)
            metrics = cell.get("metrics", {}) if cell else {}
            quality = metrics.get("quality_scores", {})
            slides, words = metrics.get("slides"), metrics.get("words")
            raw = (cell or {}).get("response", {}).get("deck")
            if cell and not cell.get("completed") and isinstance(raw, dict):
                try:
                    slides, words = f"{len(raw['slides'])} (raw)", f"{len(_deck_text(raw).split())} (raw)"
                except (KeyError, TypeError):
                    pass
            lines.append(f"| {ds} | {label} | {fmt(quality.get('alignment'))} | {fmt(quality.get('appropriateness'))} | {fmt(quality.get('accuracy'))} | {text(slides)} | {text(words)} |")
    lines += ["", "Raw output sizes may be available even when a deck fails its schema; they do not make the output a valid completed lesson.", "",
              "### Citation coverage and source labeling", "",
              "| Dataset | System | Source-labeled / all slides | Citation coverage | Supplementary slides |",
              "|---|---|---:|---:|---:|"]
    for ds in ("school", "college"):
        for method, label in LABELS.items():
            metrics = indexed.get(ds, {}).get("systems", {}).get(method, {}).get("metrics", {})
            labeled = f"{metrics['source_slides']}/{metrics['slides']}" if 'source_slides' in metrics else "N/A"
            supplementary = metrics['slides'] - metrics['source_slides'] if 'source_slides' in metrics else None
            lines.append(f"| {ds} | {label} | {labeled} | {ratio(metrics, 'citation_coverage', 'cited_source_slides', 'citation_source_slides')} | {text(supplementary)} |")
    lines += ["", "### No-tutorial controls", "",
              "| Dataset | No-tutorial score | Single call − control, pp | Fixed RAG − control, pp | Proposed − control, pp |",
              "|---|---:|---:|---:|---:|"]
    for ds in ("school", "college"):
        case = indexed.get(ds, {})
        control = case.get("control")
        deltas = []
        for method in LABELS:
            answer = case.get("systems", {}).get(method, {}).get("metrics", {}).get("answerability")
            deltas.append(fmt((answer - control) * 100 if answer is not None and control is not None else None))
        lines.append(f"| {ds} | {fmt(control, True)} | {' | '.join(deltas)} |")
    lines += ["", "Controls allow prior knowledge, whereas lesson-only answers prohibit it. Differences are descriptive and are not Hake normalized gain or measured benefit/harm to students. The failed college B1 difference includes its zero-score failure penalty.", "",
              "## Invalid output review and explicit follow-up", ""]
    for ds, case in indexed.items():
        for method, cell in case.get("systems", {}).items():
            if not cell.get("completed"):
                lines += [f"- **Initial {ds} / {LABELS[method]}:** {text(cell.get('error', cell.get('status')))}. Raw response retained in [results.json](results.json)."]
    if followups:
        lines += ["", "Only the initially invalid college single-call condition was regenerated. All follow-ups reuse its frozen source, profile, topic, chunk IDs, model, and questions. The first repeats the original prompt; the final diagnostic makes the allowed provenance labels explicit. These follow-ups are separate conditions, not replacements or new independent cases.", "",
                  "| Dataset | System / follow-up | Completed / attempted | Answerability | Quality / 5 | Groundedness | Citation validity | Latency, s |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"]
        for followup in followups:
            label = f"{LABELS[followup['system']]} — attempt {followup['attempt']}"
            if followup.get('prompt_change'):
                label += " (format clarified)"
            lines.append(performance_row(followup['dataset'], label, followup if 'completed' in followup else None))
        for followup in followups:
            original = indexed.get(followup['dataset'], {}).get('systems', {}).get(followup['system'])
            previous = [r for r in followups if r['dataset'] == followup['dataset'] and r['system'] == followup['system']
                        and r['attempt'] <= followup['attempt'] and 'completed' in r]
            total = ([original] if original else []) + previous
            total_ok = sum(bool(row.get('completed')) for row in total)
            if 'completed' in followup:
                lines += ["", f"**Attempt {followup['attempt']}:** {text(followup.get('status'))}. "
                          + (text(followup['error']) + ". " if followup.get('error') else "")
                          + f"Cumulative valid outputs for this case across the listed prompts: **{total_ok}/{len(total)}**. This is an attempt count, not an estimate from identical-condition trials."]
            if followup.get('identical_generation_messages'):
                lines += ["", "Generation messages were verified identical to the first attempt."]
            if followup.get('prompt_change'):
                lines += ["", "**Recorded prompt change:** " + text(followup['prompt_change'])]
        lines += ["", "No output provenance was normalized after generation. Both original failures remain visible. Follow-up scores are not pooled into the six-row primary comparison. See [original-prompt follow-up](followup.json), [format-clarified follow-up](format_followup.json), [follow-up call log](followup_calls.jsonl), and the [original results snapshot](review_original_results.json)."]
    else:
        lines += ["No follow-up generation has been performed."]
    lines += ["", "## Current-system diagnostics", "",
              "| Check | Result | Baselines |", "|---|---|---|"]
    profile_row = next(iter(DATA.get('personalization', [])), {})
    profile = value(profile_row) if profile_row else None
    if profile:
        lines.append(f"| Personalization | Adaptation **{profile.get('differ')}/5**; intended direction: **{'Yes' if profile.get('direction_correct') else 'No'}** | Not evaluated |")
    else:
        lines.append(f"| Personalization | {text(profile_row.get('reason', profile_row.get('status', 'Not completed')))} | Not evaluated |")
    interaction = next(iter(DATA.get('interaction', [])), {})
    edit = value(interaction.get('judgment')) if interaction else None
    if edit:
        lines.append(f"| Slide 2 edit | Fulfillment: **{text(edit.get('fulfilled'))}**; meaning preserved: **{'Yes' if edit.get('meaning_preserved') else 'No'}**; other slides unchanged: **{interaction['unchanged_other_slides']}/{interaction['other_slides']}** | Not evaluated |")
    else:
        lines.append(f"| Slide 2 edit | {text(interaction.get('error', interaction.get('reason', interaction.get('status', 'Not completed'))))} | Not evaluated |")
    if profile:
        lines += ["", "**Personalization evidence:** " + text(profile.get('note'))]
    if edit:
        lines += ["", "**Edit evidence:** " + text(edit.get('reason'))]
    lines += ["", "These are two diagnostics on one college case. Baseline personalization and editing capabilities were not tested and are not assigned zero.", "",
              "## Setup and diagnostic timing", "",
              "| Operation | Elapsed seconds |", "|---|---:|"]
    for ds, case in indexed.items():
        lines += [f"| {ds.title()} onboarding, upload, survey | {fmt(case.get('setup_seconds'))} |",
                  f"| {ds.title()} embedding warmup | {fmt(DATA['steps'].get(ds + '/warmup', {}).get('seconds'))} |"]
    for key, label in (("personalization/generate", "Advanced-profile generation"), ("interaction/edit", "Slide edit")):
        if key in DATA['steps']:
            lines.append(f"| {label} | {fmt(DATA['steps'][key].get('seconds'))} |")
    if (OUT / "analysis.md").exists():
        lines += ["", (OUT / "analysis.md").read_text(encoding="utf-8")]
    audit_path = OUT / "review_audit.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        lines += ["", "## Verification", "", f"Review performed: {audit.get('reviewed_at', 'not recorded')}. Frozen sources, original outputs, score arithmetic, citation denominators, and saved timings were checked against their underlying artifacts. The ten-question assessment and original grades were preserved; the documented question-4 consistency review corrected one derived score. Only the invalid college single-call condition was regenerated: one unchanged-prompt attempt and one final format-clarification diagnostic. Automated semantic judgments remain estimates.", "",
                  "Targeted report checks were run; the full test suite was not run. Audit details: [review_audit.json](review_audit.json)."]
    lines += ["", "## Limitations and deferred experiments", "",
              "One case per dataset and one initial run per condition cannot support significance or broad generalization. The explicit follow-up is not an additional independent case. Public-source familiarity, model-generated questions, model self-judging, and correlated errors limit validity. Some held-out questions ask for details a five-slide beginner lesson may omit, including distributive justification and Yogi's update.", "",
              "This pilot addresses Milestone 1's concerns about comprehension, source faithfulness, interaction, and reliability through automated proxies. It does not establish the original human-study success criterion, actual learning gains, confidence, or instructor workload savings. Individual agent contributions are not isolated by an ablation.", "",
              "Human studies, Q&A, flashcards, quizzes, version restoration, critic interventions, ablations, cost instrumentation, and stress tests remain uncompleted by this pilot. Instructional Agents is related work and a deferred empirical comparison.", "",
              "## Saved artifacts", "",
              "- [Frozen inputs and references](inputs.json)",
              "- [Initial and follow-up measurements](results.json)",
              "- [Execution settings and measured code hashes](manifest.json)",
              "- [Initial model/API call log](calls.jsonl)", ""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report:", OUT / "report.md")


def run(limit=1, qn=5, pers_limit=1, itx_limit=1, *, prepare_only=False):
    require_database()
    allowed = set(os.environ.get("EVAL_DATASETS", "school,college").split(","))
    if allowed != {"school", "college"} or limit != 1 or qn != 5 or pers_limit not in (0, 1) or itx_limit not in (0, 1):
        raise ValueError("This pilot requires school,college; limit=1; questions=5; diagnostic counts 0 or 1")
    diagnostics = os.environ.get("EVAL_DIAGNOSTICS", "college")
    if diagnostics != "college":
        raise ValueError("EVAL_DIAGNOSTICS must be college for this pilot")
    tasks = [t for t in TASKS if t["dataset"] in allowed]
    prepare(tasks, qn)
    if prepare_only:
        return
    if _request("GET", "/health").get("status") != "ok":
        raise ValueError("API is unhealthy")
    for case in DATA["inputs"]:
        run_core(case)
        save(OUT / "results.json", DATA)
        _report()
    case = next(c for c in DATA["inputs"] if c["dataset"] == diagnostics)
    core = next(c for c in DATA["core"] if c["dataset"] == diagnostics)
    initial = core["systems"].get("system")
    if pers_limit:
        DATA["personalization"] = [run_personalization(case, initial)]
        save(OUT / "results.json", DATA)
    if itx_limit:
        DATA["interaction"] = [run_interaction_task(case, initial)]
        save(OUT / "results.json", DATA)


def main():
    global DATA
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("limit", "questions", "personalization", "interaction"):
        parser.add_argument(name, nargs="?", type=int, default=5 if name == "questions" else 1)
    stages = parser.add_mutually_exclusive_group()
    for name in ("prepare-only", "report-only", "smoke"):
        stages.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    if not OUT.name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in OUT.name):
        parser.error("EVAL_RUN_ID must contain letters, numbers, hyphens, underscores")
    OUT.mkdir(parents=True, exist_ok=True)
    if args.smoke:
        deck = {"title": "Development fixture", "slides": [{"heading": "Luma", "bullets": ["Cooling releases light."], "provenance": "source", "citations": [{"chunk_id": "fixture"}]}]}
        require_deck(deck)
        assert not classify({"status": "ok", "output": {"reply": "clarify"}})["completed"]
        assert citation_stats(deck, lambda cid: cid == "fixture")["citation_validity"] == 1
        save(OUT / "smoke.json", {"passed": True, "mode": "development_only", "model_calls": 0})
        print("Offline smoke fixture passed")
        return
    if (OUT / "results.json").exists():
        DATA = json.loads((OUT / "results.json").read_text())
    if args.report_only:
        _report()
        return
    import fcntl
    with (OUT / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = require_database()
        from urllib.parse import urlparse
        identity = {"model": settings.llm_model, "provider": settings.llm_provider, "endpoint_host": urlparse(settings.llm_base_url).hostname, "embedding_model": settings.embed_model,
                    "api": BASE, "database": {"host": db.host, "port": db.port, "name": db.database},
                    "code": {str(p.relative_to(HERE.parent)): digest(p.read_bytes()) for directory in (HERE, HERE.parent / 'backend/app') for p in sorted(directory.rglob('*.py')) if '__pycache__' not in p.parts and 'data' not in p.parts},
                    "sample": [args.limit, args.questions, args.personalization, args.interaction]}
        manifest = {"identity": identity, "created_at": now(), "conditions": {
            "profile": pz.NOVICE, "advanced_profile": pz.ADVANCED, "request": REQUEST, "rag_k": 8,
            "http_timeout": 900, "runs_per_condition": 1, "evaluator_generation_retries": 0,
            "reasoning_effort": "Direct JSON and application tool calls: none; other application settings unchanged",
            "agent_limits": {"router": 5, "survey": 8, "planner": 6, "builder": 10, "critic": 6, "build_attempts": 3},
            "execution_order": list(LABELS), "sdk_defaults": "unchanged", "judge": settings.llm_model}}
        if (OUT / "manifest.json").exists():
            if json.loads((OUT / "manifest.json").read_text())["identity"] != identity:
                raise ValueError("Code/settings changed; use a new EVAL_RUN_ID for new measurements")
        else:
            save(OUT / "manifest.json", manifest)
        Q.CALLS = OUT / "calls.jsonl"
        try:
            run(args.limit, args.questions, args.personalization, args.interaction, prepare_only=args.prepare_only)
        finally:
            save(OUT / "results.json", DATA)
            _report()


if __name__ == "__main__":
    main()
