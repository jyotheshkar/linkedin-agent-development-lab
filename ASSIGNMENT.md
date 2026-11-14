# Investigate the complete application

The default `main` contains completed core code. There are no mandatory TODO gates before running the application or console. The old scaffold/reference history is preserved as provenance.

Your task is to understand the working system: diagram -> actual execution -> annotated source -> one isolated experiment -> targeted test -> explanation. Tests verify software behavior, not your independent competence.

| Investigation | Complete symbols | Lesson |
|---|---|---|
| Input | `Job`, `parse_job`, `normalize_identity` | [CONTRACTS-01](docs/learning/02-contracts.md) |
| Execution policy | `validate_tool_call`, `retry_allowed` | [AGENT-01](docs/learning/03-agent-control.md) |
| Review/recovery | `Workflow.start`, `Workflow.resume`, `completion_gates` | [WORKFLOW-01](docs/learning/04-workflow-recovery.md) |
| Evidence | `AtlasSnapshotSource`, `select_records`, `chunk_records` | [ATLAS-01](docs/learning/05-atlas-lab.md), [RAG-01](docs/learning/06-ingestion.md) |
| Search | `VectorIndex.search`, `rank_hits` | [RETRIEVAL-01](docs/learning/07-retrieval.md) |
| Grounding | `build_context`, `validate_answer`, `RAGService.answer` | [GROUNDING-01](docs/learning/08-grounding.md) |
| Measurement | `evaluate`, `compare_runs`, `compute_metrics` | [EVALUATION-01](docs/learning/09-evaluation.md) |
| Delivery | CLI/API, packaging and runtime boundaries | [DELIVERY-01](docs/learning/10-delivery.md) |

Start with [ANATOMY-01](docs/learning/01-anatomy.md). The [lesson index](docs/learning/lesson-index.json) provides exact source/test/diagram mappings.

Experiments are optional. Use copied fixtures, temporary tests or a dedicated experiment branch. Keep private scratch work in ignored `.lab/experiments/`. Reset only the experiment's own files; do not discard unrelated edits or deliberately break the required application path.

Inspect real local artifact bytes, hashes, target, review state, distinct application/outreach receipts and projection membership. A completed inspect/draft plan is not a completed full application unit. Every employer outcome remains **SIMULATION**.

Reference-code exposure is authorized for investigation. Record it when later assessing fresh work. Use the AIE rubric only for observed attempts: correctness 4, reasoning 2, boundaries/verification 2, explanation 2. No graded attempts means `N/A`. Two independent fully correct distinct scenarios including transfer are needed for mastery. Test passing does not fill explanation or independence fields.

Data, retrieval, planner, generation and effects are independent modes. Fresh executed results and gaps belong in [docs/VERIFICATION.md](docs/VERIFICATION.md), not inferred from old reports. No system metric is a hiring probability.
