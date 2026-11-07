# Evaluation (Milestone 2, Section 3)

The goal of this project is learning, so the evaluation is built around
learning, not around how polished a deck looks. We run our system and a
baseline on the same inputs and compare three headline qualities (does the
student learn, is it personalized, is it taught well) plus two trust
guardrails (is it grounded, do its citations resolve). Latency is a footnote.

## The task

Given a source document and a topic, produce a slide deck that teaches the
topic. Our system and every baseline get the same document, the same topic,
and the same chat model (gpt-6-luna), so a difference is architectural, not a
model or luck difference.

## How learning systems are actually evaluated

Two traditions, and we borrow from both. NotebookLM-style tools are judged
mostly on faithfulness and citations (does every claim trace to a source).
Education systems (intelligent tutoring systems, LearnLM) are judged on
learning: pre/post learning gain, pedagogical quality, and adaptivity. Our
headline metrics come from the second tradition; faithfulness becomes a
guardrail rather than the headline.

## Datasets

Raw files are not committed. Re-fetch/regenerate them with
`backend/.venv/bin/python eval/download_data.py`.

**D1 - public, general knowledge** (`data/public/`): Wikipedia (CC BY-SA)
photosynthesis, plate tectonics, French Revolution, supply and demand; OpenStax
Biology 2e (CC BY).

**D2 - ML / CS, stakeholder-relevant** (`data/ml/`): Wikipedia gradient descent,
overfitting, backpropagation, SVM; arXiv 1609.04747 (Ruder); Stanford CS229 notes.

**D3 - novel, synthetic** (`data/novel/`, written in `novel_docs.py`): short,
clearly-fictional topics (the Vernalis Tide, Kessler partitioning) with specific,
unguessable facts. These exist for the learning metric only: on a famous topic
the simulated student already knows the answers, so no tutorial can show a gain
(a ceiling effect we confirmed empirically). On novel material the only way to
answer is if the tutorial taught it, so learning is actually measurable.

## Headline metrics (does the student learn?)

- **Teaching effectiveness.** A simulated student reads ONLY the generated
  tutorial (not the source), answers source-based comprehension questions, and
  is scored by a judge against reference answers (correct 1, partial 0.5, else 0).
  We also run a **no-tutorial control** (same student, no tutorial) to measure
  prior knowledge, so the lift a tutorial adds is honest. This is the runnable
  proxy for the pre/post human learning-gain study planned for the final milestone.
- **Personalization fidelity.** Our system generates the same topic under a
  beginner and an advanced learner profile (set in the learner model the system
  actually reads); a judge rates whether the two lessons differ in the right
  direction. The single-call baseline has no learner model and cannot
  personalize at all, so this is a structural capability, not a tuning contest.
- **Pedagogy (1-5).** A learning-science rubric: scaffolding, concreteness,
  checks for understanding, cognitive load, clarity. Replaces a flat "quality".

## Guardrail metrics (is it trustworthy?)

- **Groundedness.** Of the slides marked "source", the fraction the judge finds
  actually supported by the material. Honestly-labeled supplementary slides are
  not penalized.
- **Citation validity.** Of all citations in the deck, the fraction that resolve
  to a real, retrievable chunk (checked against `/chunks/{id}`). Our citations
  resolve; the baseline produces none, so it cannot be audited.

## Footnote

- **Latency / cost.** Reported, but not a goal. Our system is slower because it
  retrieves, plans, builds, and criticizes; that cost buys the headline qualities.

## Baselines

- **B1 (built): single LLM call** with the whole document in the prompt. No
  retrieval, no critic, no learner model, no interaction. Isolates what our
  agentic grounding, personalization, and verification add over just prompting.
- **B2 (planned): Instructional Agents** (our given baseline) or RAG +
  single-generation, added before the final.

## How to run

Backend up (see backend/README.md), then:

```
cd backend && .venv/bin/python ../eval/run_eval.py [limit_per_dataset] [questions] [pers_per_dataset]
```

Example: `../eval/run_eval.py 1 5 1` runs one task per dataset, five questions
each, one personalization check per dataset. Omit the limit to run everything.
Results print as a table and save to `eval/results.json`.

## Preliminary finding

On famous topics the no-tutorial control scores near the top, so teaching
effectiveness cannot separate systems there (the student already knew it) - this
is why D3 exists. On novel material the control drops (~0.2) and both tutorials
show a large learning lift, with our system matching or ahead of the single-call
baseline, ahead on pedagogy, and the only system whose citations resolve.
Faithfulness is high for both. The honest summary: on short in-context documents
a single call is a strong content generator, but it cannot personalize and cannot
be audited, which is where our architecture is designed to matter.
