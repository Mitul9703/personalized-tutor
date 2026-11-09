# Preliminary evaluation

This evaluates the current tutor and two one-call baselines on **two cases,
six initial decks, and ten frozen questions**. It uses the existing runner,
source utilities, and scoring helpers. Production code and interfaces are unchanged.

## Datasets

| Dataset | Selected source and task | Sample | Relevance |
|---|---|---|---|
| School | Siyavula Grade 9 Mathematics, Integers chapter: addition, subtraction, multiplication | 1 topic, 5 questions | Foundational explanations and worked examples |
| College | Dive into Deep Learning: Adam, momentum, RMSProp | 1 topic, 5 questions | Technical explanations of uploaded college material |

These are public course-material collections and stakeholder-relevant proxies,
not standardized benchmarks or stakeholder-provided datasets. Topics are the
existing school/college entries in `tasks.py`.

`download_data.py --selected` downloads only these sources. School extraction
uses PDF pages 33–44 (printed 27–38), with boundary checks, from
[Siyavula](https://www.siyavula.com/downloads/books/maths/Gr9A_Mathematics_Learner_Eng.pdf)
(CC BY 3.0). School original text size refers to the first 110 PDF pages; total
PDF pages and file bytes are also recorded. College extraction reuses the existing
cleaning of [Adam](https://raw.githubusercontent.com/d2l-ai/d2l-en/master/chapter_optimization/adam.md),
momentum, and RMSProp (Dive into Deep Learning, Zhang et al., CC BY-SA 4.0).
It removes code blocks and book markup and retains explanatory prose/formulas.
Raw section sizes and hashes are recorded before cleaning.

Sources are frozen as complete paragraphs within 50,000 characters. Metadata
includes URLs, retrieval dates, attribution, extraction boundaries, original,
selected, and evaluated sizes, hashes, word counts, and application chunk counts.
Five source-based questions/reference answers per case are independently checked
for support and clarity before generation. A rejected assessment receives at
most one recorded revision and revalidation; a second rejection blocks freezing.
Both cases must be accepted before any evaluated generation. Questions and keys
never enter generation prompts. No training/split; use the separate smoke fixture.

## Systems and conditions

- **B1:** one generation call over all ingested chunks of the frozen source.
- **B2:** application `retrieve` with k=8, then one generation call.
- **Proposed:** existing message API, including its router, planner, builder,
  critic, and memory behavior.

All use the configured application model, matching beginner profile, topic,
five-slide request, genuine chunk IDs, and opportunity to generate notes and
citations. Notes are accessible through **Go deeper** and included in evaluation.
B1/B2 use the existing JSON model wrapper with reasoning effort `none`, as do
application tool calls. Other application settings and SDK defaults are unchanged.
Agent limits: router 5, survey 8, planner 6, builder 10, critic 6, build attempts 3.
Model/provider/endpoint host, embedding model, request, code hashes, and conditions
are saved in the manifest. Code/settings changes require a new run ID.

Use one generation attempt per condition, 900-second HTTP timeout, and no
evaluator generation retries. The application's internal retries remain enabled.
Warm embeddings before timing; record setup (onboarding/upload/survey) separately.
Fixed order is B1, B2, proposed; latency may reflect order/provider load.

## Metrics

| Metric | Procedure |
|---|---|
| Automated tutorial answerability | Answering model sees only lesson headings, bullets, notes, and questions. Grade against references: correct=1, partial=0.5, wrong/uncovered=0; average over five questions. |
| No-tutorial control | Same questions answered from prior knowledge; report difference in percentage points descriptively. |
| Instructional quality | Anonymous judge scores alignment, learner appropriateness, accuracy separately, each 1–5 with reasons. Paper anchors: 1 redevelopment, 3 moderate revisions, 5 minimal edits. Mean requires all three valid ratings. |
| Groundedness | Source-labeled slides with all substantive claims supported / source-labeled slides. Supplementary fraction is recorded separately. |
| Citation coverage | Source-labeled slides carrying citation entries / source-labeled slides. |
| Citation validity | Entries resolving to chunks of this evaluated source / all entries; malformed entries count as invalid. Resolution alone does not prove semantic support. |
| Completion | Valid, nonempty decks returned / attempted generations. Five slides are requested; actual slide count is reported. |
| Latency | Elapsed generation time; setup/warmup excluded. |

Judges use identical instructions across systems and receive no system labels.
Denominators come from code. Unavailable/malformed scoring is N/A; independent
valid metrics survive other scoring failures. No answer padding or silent score
coercion. Failed generations receive zero end-to-end answerability and unavailable
content-quality scores. Empty decks/chat-only responses remain explicit failures.
Raw API replies/intents, parsed model responses, malformed JSON, and failures are saved.

## Two college diagnostics

Reuse the proposed beginner deck. Generate one fresh advanced-profile lesson
through normal onboarding, then judge appropriate adaptation in depth,
terminology, prerequisites, mechanisms, and examples. Submit one edit to simplify
slide 2 and add an example while preserving meaning and other slides. Judge actual
fulfillment and meaning preservation; mechanically compare non-target slides.
A missing revised deck is a failed edit, never a fallback to the previous deck.
Baseline diagnostics are **not evaluated**. The comparison does not establish
that baselines cannot personalize, revise, or cite.

## Run

From the repository root, start the existing database and create a dedicated
application database once (do not reuse an existing measurement run's database):

```sh
docker compose up -d db
docker compose exec db psql -U tutor -d postgres -c 'CREATE DATABASE tutor_small_eval'
cd backend
export DATABASE_URL=postgresql+psycopg://tutor:tutor@localhost:5432/tutor_small_eval
export UPLOAD_DIR=../eval/data/small_api_uploads
.venv/bin/python -m app.store.init_db
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

In another terminal, from `backend/` (so the existing `.env` is loaded):

```sh
export DATABASE_URL=postgresql+psycopg://tutor:tutor@localhost:5432/tutor_small_eval
export TUTOR_DB="$DATABASE_URL"
export TUTOR_API=http://127.0.0.1:8011
export EVAL_DATASETS=school,college
export EVAL_DIAGNOSTICS=college
export EVAL_RUN_ID=school_college_v1
.venv/bin/python ../eval/run_eval.py 1 5 1 1
```

API and evaluator must share the same database. The runner rejects a conflicting
`TUTOR_DB` alias and verifies that the API's uploaded document/profile/chunks are
visible through its database connection. No direct learner-note writes.

The positional arguments remain `[limit] [questions] [personalization] [interaction]`.
This selected pilot requires `1 5`, and each diagnostic count is `0` or `1`.
School/college are the only supported datasets for this preliminary runner.
Optional `--prepare-only` freezes assessments without generating lessons;
`--report-only` rebuilds the report offline. Use the same run ID/settings to resume:
saved operations, including failures and interrupted requests, are never retried
automatically. Start a new run ID for corrected measurements. A file lock prevents
concurrent commands from duplicating operations.

Offline validation from the repository root:

```sh
backend/.venv/bin/python -m pytest -q eval/tests
LLM_API_KEY=offline-smoke EVAL_RUN_ID=development_fixture backend/.venv/bin/python eval/run_eval.py --smoke
```

## Outputs and limitations

`eval/data/runs/<run-id>/` contains `manifest.json`, `inputs.json`, frozen source
files, incremental `results.json`, raw `calls.jsonl`, and `report.md`. Generated
data stays under the repository's existing ignored data area. Reporting requires
no new model calls and always includes six comparison rows, controls, output
lengths, per-metric denominators, unavailable fields, failures, and two diagnostics.
The report separates the six initial comparison rows from any explicitly requested
follow-up. A failed generation's zero answerability is marked as a failure-policy
score, while its content-quality scores remain unavailable. Follow-ups preserve
the original attempt and never silently replace the primary comparison.
Any explicit prompt clarification is disclosed with its follow-up. Scoring
consistency reviews retain original grades and record the reviewed answer points
and rationale; the report uses the corrected derived score.
With n=1, case scores and dataset means are identical. Inspect saved decks and
rubric reasons when discussing successes, ties, and regressions; no individual
agent's contribution is isolated by this comparison.

One case per dataset, one run per condition, public-source familiarity,
model-generated assessments, and correlated model judgments limit interpretation.
These are automated quality and answerability estimates, not observed student
learning, Hake normalized gain, confidence, or instructor workload savings. They
address Milestone 1 concerns without establishing its human-study success criterion.
Human studies, Q&A, flashcards, quizzes, version restoration, critic interventions,
ablations, cost instrumentation, and stress tests are deferred. Instructional
Agents remains related work and a deferred empirical comparison.
