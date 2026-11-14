# Coach handover: investigate the complete MVP

The learning design changed on 14 November 2026. `main` is complete; the earlier twelve-function scaffold/reference split remains historical. Reading complete code is explicitly authorized. Do not recreate mandatory TODOs or replace the chosen lesson with setup work.

The role is Capgemini AI Engineer - Engineering Augmentation, grounded in the recruiter JD preserved by AIE. The user reported assessment clearance/progression to L1 on 13 November. Interview date, agenda, pass threshold and official score remain unknown. L1 implementation/L2 design emphasis are preparation choices.

## Establish actual source

Resolve private repository ID **1456774523**, actual branch/commit and checkpoint. Read `START_HERE.md`, `AGENTS.md`, this file and the selected lesson entry. Open its exact source/tests. A private link neither grants access nor reveals unsaved edits. Use a bounded fallback when necessary:

```bash
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

## First learning action

Show [system anatomy](docs/architecture/system-anatomy.svg), then read `src/l1_lab/contracts.py` with `tests/test_contracts.py`. Explain JSON text versus decoded objects versus validated `Job`. Trace one valid request and one Boolean budget, then offer the optional CONTRACTS-01 experiment. One concept/question at a time.

| Boundary | Source | Teaching focus |
|---|---|---|
| Application journey | `application.py`, `service.py` | Shared CLI/API service; persisted evidence and artifacts |
| Input | `contracts.py` | Strict types, exceptions, canonical identity |
| Proposal/policy | `planner.py`, `openai_adapter.py`, `agent.py` | Fixture versus live; schema, permission and budget |
| Recovery | `workflow.py`, `provider.py`, `journal.py` | LangGraph state, exact review, independent receipts |
| Atlas Lab | `atlas_lab.py`, `knowledge.py` | Versions, approvals, provenance, ledger/projection |
| RAG | `retrieval.py`, `grounding.py`, `service.py` | Eligible sources, vectors, retained context and citations |
| Measurement | `evaluation.py`, `progress.py` | System quality versus observed learner evidence |
| Interfaces | `cli.py`, `api.py`, `web_api.py`, `web/` | Thin routes, auth/errors, packaging and preview |

The [versioned lesson index](docs/learning/lesson-index.json) owns exact symbols, test nodes and diagrams. Read [DECISIONS](docs/DECISIONS.md) and [JD_COVERAGE](docs/JD_COVERAGE.md) for trade-offs and limitations.

## Learning evidence

The builder supplied code, tests and teaching material. Only observed learner explanations, modifications, tests and fresh scenarios establish competence. Reference-exposed work is useful learning, not independent implementation.

Declare criteria before grading: correctness 4, reasoning 2, boundaries/verification 2, explanation 2. Preserve question/variant ID, explicit assistance/reference exposure, actual tests, source commit, reviewer and next action. Fully correct requires all 10 points and no critical misconception. Mastery needs two independent fully correct distinct scenarios including transfer; a later critical misconception resets relevant evidence. No graded attempts means `N/A`. Never grade accent or polished English instead of understandable reasoning.

Keep system evaluation, optional exercise completion, independent mastery and recruitment outcome separate. Fresh mock questions should be created when the mock starts, not stored beside browsing lessons. Observe a walkthrough, small Python change, recovery failure, RAG diagnosis and delivery trade-off. Timers are opt-in; these are not known employer questions.

## Runtime boundaries

All employer effects are **SIMULATION**. Atlas Lab is not operational Atlas. Source approval, action approval, stored events and projection delivery remain separate. Review binds actual target/actions/artifact/version/digest/payload. Unknown outcomes reconcile; logging/projection repair must not repeat application/outreach.

Data, retrieval, planning and generation are independent modes. Hash vectors are a test double; local semantic embeddings do not establish live planning/generation. Imported private data stays untracked. Citation/quote validity is structural, not semantic truth or personal authorship. `docs/VERIFICATION.md` owns fresh results; historical reports retain their original claims.
