# Delivery investigation

The complete local product is a role-aligned learning application, not a deployed employer-facing service. Read [DELIVERY-01](learning/10-delivery.md), [future hosting](VERCEL_DELIVERY.md) and fresh [verification](VERIFICATION.md).

## Git, CI and the complete default branch

`main` contains the working implementation. Earlier scaffold/reference branches and reports preserve history; they no longer define startup gates. Tests remain meaningful contract/integration checks, not blanket skips or expected failures for mandatory lessons. Existing milestone marker names are convenient test groupings, not unfinished product stages.

Read the actual workflow and exact code/lock revision behind a CI result. A CI definition is not an observed run. Preserve learner edits, commit explained changes, and record commands/results without rewriting historical evidence. Optional experiments should have a reset limited to their own copied files.

## Codespaces and packaging

The development container supplies a reproducible Python 3.12 environment with an idempotent setup. `uv sync --locked --extra lab` follows the committed dependency resolution. Editable checkouts and installed wheels must both resolve packaged data/learning resources; test both rather than assuming repository-relative paths exist after installation.

A private forwarded Codespace port is development preview, not production hosting. Keep it private. For console work use the documented `uv run uvicorn app:app --host 0.0.0.0 --port 8000` in the Codespace; local-machine-only inspection can bind `127.0.0.1` instead. Store optional credentials through supported secrets mechanisms, never Git or traces.

## REST, authentication and errors

CLI and browser/API call shared application services. A valid job is still not an approved action. Authentication, request-size bounds and JSON/schema validation precede mutation; the executor separately enforces permissions/budgets and exact review.

The legacy `POST /fit` response provides grounded retrieval inspection. The application journey uses `/api/runs` and its explicit review/resume route. Read the current request models/examples rather than inventing fields. A 2xx response or a completed inspect plan does not establish a full unit; inspect artifacts, receipts, gates and reporting membership.

If configured, the bearer token is single-owner access protection, not multi-user identity. Browser tokens remain in page memory. Errors and telemetry must omit credentials/private content. Distinguish invalid input, missing evidence, blocked review, pending receipts, transient service failure and request budgets.

## Storage and future hosting

The complete local journey uses Atlas Lab knowledge versions, material/artifact bytes, approvals, event ledger and a derived projection. Existing Postgres run/provider/budget adapters are a separate older contract, not automatic full Atlas/artifact parity. Future full-MVP hosting must fail closed until durable material/state contracts and migrations are implemented and exercised.

No project import/link, automatic deployment, deployment command, public preview, database/domain provisioning or package publication is authorized by this upgrade. Prepared Vercel/FastAPI files are inert delivery preparation. Preserve actual semantic retrieval; a lightweight hosted hash cache cannot silently substitute for it.

## Context, tracing and MCP

Character budgets are not exact token counts. Read the current real-model adapter's declared input estimate/limit and output headroom. Report measured usage only when returned; unknown cost stays unknown. Structured outputs do not replace deterministic schema, permission, citation and semantic-support checks.

The real local OpenTelemetry exporter records observable spans/durations and allowlisted attributes, not hidden reasoning or raw personal payloads. See `observability.py` and its tests. The small read-only stdio MCP exercise performs genuine discovery/schema/invocation and rejection checks; see [MCP.md](MCP.md). It is not operational Atlas's endpoint and exposes no arbitrary SQL/shell/write tool.

## Optional Java refresher

Use a short factory/registry example to discuss interfaces, lookup, unsupported keys and per-order object isolation. Singleton initialization does not make later mutable state thread-safe. This remains optional; the central application is Python, agents, evidence and recovery.
