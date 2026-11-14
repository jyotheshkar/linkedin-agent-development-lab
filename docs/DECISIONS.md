# Architecture decisions

These decisions describe the intended/current implementation boundaries. Fresh execution evidence belongs in `VERIFICATION.md`; configuration or a code path is not proof it ran.

| Decision | Choice and reason | Alternative and cost | Evidence to inspect |
|---|---|---|---|
| Complete main | Make the working application readable; keep optional experiments isolated | Mandatory broken tasks made product use depend on lessons and encouraged setup work | `START_HERE.md`, preserved baseline history, core source/tests |
| One modular application | Shared `ApplicationService` coordinates CLI/API journeys; `RAGService` coordinates retrieval | Separate services/queues add deployment/state complexity before scale justifies it | `application.py`, `service.py`, route tests |
| Explicit state graph | LangGraph links ordinary Python functions with bounded transitions | A script is simpler for a fixed stateless task; a general autonomous shell/browser is unnecessary | `Workflow`, `validate_tool_call`, recovery tests |
| Isolated Atlas Lab | Immutable local versions, approvals, artifacts, events and a derived projection | Operational Sheets/Drive integration would add authority and private-data risk outside this build | `AtlasLab`, `tests/test_atlas_lab.py` |
| Separate receipts | Provider uniqueness/payload binding survives process/journal failure | A generated key without an independent durable receipt cannot establish exactly-once behavior | `FakeProvider`, unknown-outcome and changed-payload tests |
| Content-bound review | Bind actual job, policy, source versions, artifact hashes and action payload | Goal-only approval permits unnoticed material changes | `ApplicationService._validate_preparation`, approval/recovery tests |
| Honest RAG modes | FastEmbed/Qdrant semantic path and an explicitly labelled deterministic test double | Hash vectors are lightweight but do not verify semantic embeddings; real generation is separate | `retrieval.py`, `test_semantic.py`, adapter tests |
| Retained-context validation | Generate and validate using only chunks that fit final context | Validating against all retrieved IDs permits citations to unseen evidence | `RAGService.answer`, `test_context_budget_only_retained_citations` |
| Local first, future host separate | Complete local storage; keep legacy Postgres/deployment contracts explicit | Ephemeral hosted files can lose review/artifact/receipt state; Postgres run state alone is not full artifact parity | `ApplicationService`, delivery docs, durable-state tests |
| Small observability/MCP extensions | Real local OTel export and read-only MCP discovery/invocation | Paid dashboard setup or arbitrary remote tools add unnecessary dependencies/authority | `observability.py`, `mcp_server.py`, protocol/exporter tests |
| Portable coaching context | Versioned manifest and bounded allowlisted source/test export | A private Codespace link does not grant future access; full-repository exports risk private data | `context_export.py`, schema/link/redaction tests |

The system is a single-owner learning MVP. It does not establish production security, multi-user identity, operational deployment, personal authorship or interview readiness. Compare alternatives against actual needs and observed failures rather than adding frameworks for their names.
