# Coaching handover

This repository is an implementation environment for Jyothesh Karnam's Capgemini AI Engineer L1 preparation. On 13 November 2026 he reported clearing the assessment and progressing to L1; the interview date and agenda remain unknown. The learning target is Sunday evening, 15 November. The exercises are role-aligned preparation, not known employer questions.

## Start here

Keep `main` checked out. Run:

```bash
uv run l1-lab doctor
uv run pytest -m infrastructure
uv run pytest -m m1
```

Begin with `src/l1_lab/contracts.py::parse_job`. Teach the distinction between JSON text, decoded Python objects, and a validated contract, then ask one question or small implementation task. Do not start by revealing the reference body.

## Repository map

| Area | Files | Teaching purpose |
|---|---|---|
| Contracts | `src/l1_lab/contracts.py` | JSON validation and duplicate identity |
| Agent | `agent.py`, `planner.py`, `workflow.py` | Structured proposals, deterministic checks, explicit graph state |
| Recovery | `provider.py`, `journal.py` | Stable action identity, independent simulated receipts, restart/reconciliation |
| Knowledge | `knowledge.py` | Approved snapshot ingestion and provenance-preserving chunks |
| Retrieval | `retrieval.py` | Embeddings, Qdrant local search, filters and relevance |
| Responses | `grounding.py` | Bounded context, citations, gaps, review and abstention |
| Measurement | `evaluation.py`, `progress.py` | ID-aligned regression checks and honest practice metrics |
| Interfaces | CLI and FastAPI adapter | Inspectable commands and REST/JSON boundaries |
| Learning | `ASSIGNMENT.md`, `LEARNING_PATH.md`, `docs/` | Contracts, public examples, changed scenarios and delivery review |

See `BUILD_REPORT.md` for exact verified branches/commits, commands, test results, semantic/live integration status, and Codespaces observations. A host-local run is not proof that a Codespace launched successfully.

## Student and reference boundaries

`main` contains 12 deliberate task bodies raising `NotImplementedError`. `coach-reference` contains the complete builder-tested implementation of those contracts. The owner can access both; record any reference viewing/copying as assistance. Setup and infrastructure work do not mean the assignment is solved.

The 12 tasks are:

1. `contracts.parse_job` — M1
2. `contracts.normalize_identity` — M1
3. `agent.validate_tool_call` — M2
4. `agent.retry_allowed` — M2
5. `knowledge.select_records` — M3
6. `knowledge.chunk_records` — M3
7. `retrieval.rank_hits` — M4
8. `grounding.build_context` — M5
9. `grounding.validate_answer` — M5
10. `agent.completion_gates` — M6
11. `evaluation.compare_runs` — M6
12. `progress.compute_metrics` — M6

Preserve existing signatures and public tests. Ask the learner to explain changes and one boundary after a passing test. If an essential concept is missing, teach that gap and use a fresh same-topic variant. A corrected exposed answer is assisted; it does not demonstrate independent transfer.

## Coaching and progress contract

Learning is untimed unless requested. Use one concept/question at a time, concise visual teaching when useful, and white/black/teal presentation. Prefer a mix of explanation, tracing, debugging, test design, and small code changes. Keep Java an optional short refresher.

Declare the requirement groups before an attempt. Grade correctness `4`, reasoning `2`, boundaries/verification `2`, and explanation `2`. Fully correct requires all `10` points and no critical misconception. Do not grade accent or polished English. Preserve question/variant IDs, assistance/reference exposure, tests actually run, source IDs, and the next action.

Initial independent competence is **unmeasured**. With no graded attempts, knowledge/first-attempt/cumulative accuracy are `N/A`; mastery is not inferred from builder tests. Mastery requires two fully correct independent distinct scenarios, including a changed transfer variant. A later critical misconception resets the relevant evidence. See `docs/EVALUATION.md` for the implemented formulas.

Use `.lab/checkpoint.json` for a portable progress export. Do not fabricate an explanation or independence field from a terminal pass. Minister/AIE records can carry minimal objective learning evidence when those tools are available in the coaching chat; this lab itself does not call those connected services.

## Evidence and simulation boundaries

Synthetic fixtures are safe teaching data. A private Atlas snapshot is file-based, read-only, explicitly imported, and ignored by Git. It is neither continuous synchronisation nor an authenticated connector inside Codespaces. Preserve provenance and avoid unsupported personal claims. Real Amazon evaluation experience, assisted practice code, and independent project work remain distinct.

All employer/Atlas/storage/delivery operations use simulation adapters and `sim:` receipts. Human review precedes simulated effects. Idempotency belongs to the simulated provider's receipt contract; a hash by itself does not guarantee exactly-once execution in a real distributed system. Retrieval text cannot grant permissions or approvals.

Report offline tests, genuine semantic retrieval, live planning, live generation, and a running Codespace separately. Missing paid-model credentials must not block offline learning. A valid citation/quote alone does not prove semantic entailment or career authorship.

## Final mock blueprint — keep questions unexposed

Create fresh variants only when the learner starts the mock. Do not store model answers beside these tasks on `main`.

| Segment | Evidence to observe |
|---|---|
| Project walkthrough | Trace an input through validation, planning, retrieval, grounded output, review, receipts, and completion |
| Small Python change | Clarify a changed contract, edit a focused function, and add one meaningful boundary test |
| Agent failure | Diagnose transient versus blocked/unknown outcomes and demonstrate restart without duplicate simulated effects |
| RAG diagnosis | Inspect retrieval/citations for irrelevant or conflicting evidence and justify a gap/review/abstention decision |
| Delivery review | Explain Git/CI, container setup, REST/auth/errors, context budgets, and where MCP would fit |

Use a timer only if requested. Grade observed work with the same declared rubric; do not convert practice readiness into hiring probability.

## Paste into the original coaching chat

> The LinkedIn + Atlas L1 lab is built with `main` as my student branch and `coach-reference` as the complete reference. Read `BUILD_REPORT.md` and `COACH_HANDOVER.md` for exact commits and observed verification. There are 12 deliberate TODO functions across M1–M6; please preserve independent work and record reference exposure as assistance. Start with `uv run pytest -m m1` and `contracts.parse_job`: teach one concept, then ask one question/task. My independent baseline is unmeasured. Use the 10-point AIE rubric, fresh transfer variants, and no timer unless I ask. I reported progression to L1 on 13 November; the date and format remain unknown.
