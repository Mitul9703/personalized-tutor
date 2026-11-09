# Evaluation (Milestone 2, Section 3)

The goal of this project is learning, so the evaluation is built around
learning, not around how polished a deck looks. We run our system and two
baselines on the same inputs and the same model (gpt-6-luna), so any
difference is architectural, not a model or luck difference. We report three
headline qualities (does the student learn, is it personalized, can it be
steered), two trust guardrails, and one agent-behavior check. Latency is a
footnote.

## The task

Given a source document and a topic, produce a slide deck that teaches the
topic. Every system gets the same document, topic, and model.

## Baselines

- **B1 single call.** The whole document in one prompt, no retrieval, no
  critic, no learner model, no interaction. Truncates very long documents at
  150k chars, which is the honest limit of "just paste the whole thing."
  Isolates what our entire pipeline adds over prompting the model.
- **B2 RAG + single generation.** Retrieve the most relevant chunks (same
  local embedding model our system uses), then make the deck in one call. No
  planner, no critic, no learner model, no interaction. The sharper
  comparison: it isolates what our plan -> build -> critique loop adds over
  plain retrieval plus one generation.
- Instructional Agents (our given baseline) is deferred to the final
  milestone; B1 and B2 are enough for the Section 3 comparison and B2 is the
  more informative of the two for our thesis.

## Datasets

Raw files are not committed. Regenerate with
`backend/.venv/bin/python eval/download_data.py`.

- **D1 public** (`data/public/`): Wikipedia (CC BY-SA) and OpenStax (CC BY).
- **D2 ML/CS** (`data/ml/`): Wikipedia, arXiv 1609.04747 (Ruder), Stanford CS229.
- **D3 novel** (`data/novel/`, written in `novel_docs.py`): short,
  clearly-fictional topics with specific, unguessable facts. For the learning
  metric only: on a famous topic the simulated student already knows the
  answers, so no tutorial can show a gain (a ceiling we confirmed). On novel
  material the only way to answer is if the tutorial taught it.
- **D4 large** (`data/large/`): one ~165k-char reader built by concatenating
  the ML docs, with the needle topic (Nadam) in the tail, past B1's 150k
  cutoff. B1 truncates and cannot reach it; our system and B2 retrieve it.
  This is the condition where retrieval is supposed to matter.

## Headline metrics (does the student learn?)

- **Teaching effectiveness.** A simulated student reads ONLY the generated
  tutorial (not the source), answers source-based questions, and is scored by
  a judge against reference answers (correct 1, partial 0.5, else 0). A
  **no-tutorial control** (same student, no tutorial) measures prior knowledge
  so the lift is honest. This is the runnable proxy for the pre/post human
  learning-gain study planned for the final milestone.
- **Personalization fidelity.** Our system generates the same topic under a
  beginner and an advanced learner profile (set in the learner model the
  system actually reads); a judge rates whether the two lessons differ in the
  right direction. The baselines have no learner model and cannot personalize.
- **Interaction quality.** We generate a deck, then send steering commands
  (explain deeper, simplify, add an example) and check whether each was
  carried out and the result stayed grounded. The baselines produce a deck and
  stop, so they score zero here by construction; we report it as a capability
  our architecture has and they do not.
- **Pedagogy (1-5).** A learning-science rubric: scaffolding, concreteness,
  checks for understanding, cognitive load, clarity.

## Guardrail metrics (is it trustworthy?)

- **Groundedness.** Of the slides marked "source", the fraction a judge finds
  supported by the material. Supplementary slides are not penalized.
- **Citation validity.** Of all citations, the fraction that resolve to a
  real, retrievable chunk. Our citations resolve; the baselines produce none,
  so they cannot be audited.

## Agent behavior

- **Planted-error catch rate.** We inject a plausible but false claim onto a
  source slide and check that the Critic fails the deck. A **clean-pass rate**
  (does the Critic pass the untouched deck) is the control: a Critic that fails
  everything would catch errors trivially, so both numbers matter.

## Footnote

- **Latency.** Reported, not a goal. Our system is slower because it retrieves,
  plans, builds, and criticizes; that cost buys the headline qualities.

## How to run

Backend up (see backend/README.md), then:

```
cd backend && .venv/bin/python ../eval/run_eval.py [limit_per_dataset] [questions] [pers_per_dataset] [interaction_per_dataset]
```

Example: `../eval/run_eval.py 1 5 1 1` runs one core task per dataset (five
questions each), one personalization check per dataset, and one interaction
check per dataset. Omit the limit to run everything. Results print as a table
and save to `eval/results.json`.

## Reading the results

On famous topics the no-tutorial control is high, so teaching effectiveness
cannot separate systems there; that is why D3 and D4 exist. On novel and large
material the control drops and the differences are real. The honest frame: a
single call is a strong content generator on short in-context documents, but
it cannot personalize, cannot be steered, cannot be audited, and truncates
large documents, which is where our architecture is designed to matter.
