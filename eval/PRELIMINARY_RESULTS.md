# Preliminary Evaluation Results

This summary presents selected valid outputs for two public course-material cases,
with five frozen questions each. Baselines come from the initial pilot; college
single call uses its format-clarified follow-up. Proposed-system results come from
a fresh-course recheck. These are not first-attempt completion rates.

## Setup

| Dataset | Source and task | Evaluated size | Sample |
|---|---|---|---|
| School | [Siyavula Grade 9 Mathematics](https://www.siyavula.com/downloads/books/maths/Gr9A_Mathematics_Learner_Eng.pdf), Integers chapter: addition, subtraction, multiplication, and negative-number rules | 13,018 characters; 2,538 words; 14 chunks | 1 topic; 5 questions |
| College | Dive into Deep Learning: [Adam](https://raw.githubusercontent.com/d2l-ai/d2l-en/master/chapter_optimization/adam.md), [momentum](https://raw.githubusercontent.com/d2l-ai/d2l-en/master/chapter_optimization/momentum.md), and [RMSProp](https://raw.githubusercontent.com/d2l-ai/d2l-en/master/chapter_optimization/rmsprop.md) | 25,589 characters; 3,785 words; 31 chunks | 1 topic; 5 questions |

These are stakeholder-relevant public proxies, not standardized benchmarks or
stakeholder-provided data. School material tests foundational explanations and
worked examples; college material tests technical explanations. Source attribution:
Siyavula Mathematics Grade 9, CC BY 3.0; Zhang, Lipton, Li and Smola, Dive into Deep
Learning, CC BY-SA 4.0.

School extraction used PDF pages 33–44 (printed 27–38). College extraction removed
code blocks/book markup while retaining prose and formulas. Both frozen sources
fit within 50,000 characters. Five model-authored questions and references per case
passed an independent source-support/clarity check before generation. Generators
never received questions or keys. No training or train/test split was involved.

All conditions used model identifier `openai/gpt6_luna`, a matching beginner
profile, and a request for five concise slides with optional notes and citations.
B1 generated once from all ingested chunks. B2 used application retrieval, k=8,
then generated once. The proposed system used the message API and router → planner
→ builder → critic workflow. B1 tests full-context prompting; B2 compares fixed
retrieval plus one generation with the complete workflow.

Embeddings: `BAAI/bge-small-en-v1.5`. Direct JSON/application tool reasoning effort:
`none`; other application/SDK defaults unchanged. HTTP timeout: 900 seconds.
Agent limits: router 5, survey 8, planner 6, builder 10, critic 6; build attempts 3.
Setup and embedding warmup occurred before timing. The proposed-system recheck
used fresh courses with the original frozen sources, questions, and profile.

The successful college B1 follow-up explicitly required literal provenance labels
`source` or `supplementary`. Its content request, source, profile, model, and
assessment were unchanged. This prompt-format difference limits comparison; the
output was not normalized after generation.

## Metrics and results

Answerability uses a lesson-only answering model, including accessible Go deeper
notes, followed by reference-based grading: correct=1, partial=0.5,
incorrect/uncovered=0. Quality is the anonymous LLM mean of alignment,
appropriateness, and accuracy, each 1–5 with reasons. Paper-aligned anchors:
1 redevelopment, 3 moderate revisions, 5 minimal edits. Grounding counts supported
source-labeled slides / source-labeled slides. Citation validity counts resolving
entries from the evaluated source / all entries. Denominators and arithmetic are
computed in code. Citation coverage was 100% of source-labeled slides in these
valid outputs. Latency excludes setup, warmup, and scoring.

| Dataset | System | Answerability | Quality / 5 | Groundedness | Citation validity | Latency, s |
|---|---|---:|---:|---:|---:|---:|
| School | Single call | 80% (4/5) | 4.67 | 100% (4/4) | 88.9% (8/9) | 187.52 |
| School | Fixed RAG | 20% (1/5) | 4.00 | 100% (1/1) | 100% (3/3) | 3.91 |
| School | Proposed system (fresh recheck) | 80% (4/5) | 4.33 | 100% (5/5) | 100% (8/8) | 58.09 |
| College | Single call (format clarified) | 60% (3/5) | 4.67 | 100% (4/4) | 100% (9/9) | 187.28 |
| College | Fixed RAG | 40% (2/5) | 4.33 | 100% (4/4) | 100% (8/8) | 7.81 |
| College | Proposed system (fresh recheck) | 50% (2.5/5) | 4.33 | 100% (3/3) | 100% (5/5) | 31.34 |

The proposed recheck completed 2/2 attempts, returning five slides each. School
quality components were 4/4/5 and college components 5/4/4. College question 4
correctly received partial credit for omitting the learning-rate factor, consistent
with the earlier blinded scoring review. All original outputs and grades remain
in the local audit artifacts.

## Analysis and limitations

Proposed school answerability tied single call and exceeded fixed RAG. RAG produced
two slides and 114 words, versus five slides and 373 words in the proposed recheck;
coverage and request fulfillment plausibly explain part of the gap. Proposed
school quality (4.33) was below single call (4.67).

On college material, proposed answerability exceeded RAG but was below clarified
single call. Proposed and RAG quality tied at 4.33; clarified single call scored
4.67. Single call covered beta values/time scales omitted by proposed, while
proposed supplied bias-correction formulas more explicitly than RAG. These
observations do not isolate individual agents' causal contributions.

RAG was faster than proposed in both cases. Single-call latency outliers, fixed
execution order, and single-run variability prevent firm architectural latency
conclusions. Prior no-tutorial controls scored 80% (school) and 90% (college);
they were not rerun. Those conditions permit prior knowledge, unlike lesson-only
answering, so differences do not demonstrate human learning gains or harm.

Earlier college diagnostics rated advanced-profile adaptation 4/5 in the intended
direction. A slide edit fulfilled simplification/example requests with preserved
meaning and 4/4 other slides unchanged. Baseline diagnostics were not evaluated.

One case per dataset, selected valid outputs, public-source familiarity,
model-generated assessments, and correlated LLM judgments limit generalization.
Answerability addresses Milestone 1 comprehension through a proxy; grounding and
citations address faithfulness, and completion/latency address reliability. Human
learning, confidence, instructor workload, cost, internal tool-use success,
ablations, stress tests, and empirical comparison with Instructional Agents remain
unmeasured.

## Reproduction and evidence

See [README.md](README.md) for setup and execution. Downloaded sources and raw
model/API logs remain in the existing ignored `eval/data/` directory. Local run
artifacts are under `school_college_v1` and `proposed_recheck_v1`; they are not
included in this commit. The proposed-only audit verified source/assessment
hashes, fresh course/chunk identity, scoring arithmetic, actual citation API
responses, grounding/citation denominators, and timings. Baselines and the full
test suite were not rerun for that check.
