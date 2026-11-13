# Small delivery review

This review connects the lab to role-derived delivery topics. It does not claim that these are confirmed interview rounds or that the lab is a deployed employer-facing system.

## Git and CI

`main` is a deliberate student scaffold; its milestone tests initially fail. Infrastructure verification and the complete `coach-reference` suite must therefore have distinct CI labels and expectations. Do not mask unfinished tasks with blanket skips or expected-failure markers. Commit your code changes with a short description of the contract changed and the tests actually run.

Read the workflow files to see which branch and test selection a CI result covers. A green infrastructure job says that wiring works; it does not say the 12 task functions are complete. Use stable case IDs for evaluation comparisons so fixture reordering cannot change the meaning of a regression.

## Development container and Codespaces

The development container describes a reproducible Python environment, startup command, and editor setup. Its setup command should be safe to run again. The lockfile pins the tested dependency resolution; use `uv sync --frozen` to install it without silently changing versions.

Repository preparation, a local installation, a container build, and a running Codespace are separate observations. See `BUILD_REPORT.md` for which were actually verified. Create a Codespace from `main` for learning. Keep the optional model key in a Codespaces secret, then restart the terminal/container if needed; never place it in a committed file or a trace.

## REST, JSON, authentication, and errors

The thin FastAPI endpoint is `POST /fit`, with a JSON body shaped as `{"job":{"title":"AI Engineer","company":"Example Labs","requisition_id":"AI-17","skills":["Python"]},"query":"Python evaluation"}`. `query` is optional; the strict `job` contract is the same one taught in M1. The endpoint uses offline fixture retrieval. Read the CLI/API examples in `README.md` before sending a request. Reuse the same validation and retrieval contracts as the command line rather than creating another version of the logic.

Bind the teaching server to `127.0.0.1`. If `LAB_API_TOKEN` is configured, send it as a bearer token; the unset local configuration is not evidence of internet-facing authentication. Keep forwarded Codespaces ports private. Authentication answers who may call the endpoint; tool permissions and human review still decide what the workflow may do.

Distinguish malformed JSON, request validation errors, missing evidence, blocked workflow actions, and transient provider errors. An HTTP success code alone is not a completed application unit. Inspect the structured status and gate evidence. Error bodies and traces must not expose credentials or raw private snapshot text.

## Context and model limits

The lab has an explicit context character budget. Character counts are easy to inspect but are not token counts; tokenization depends on the configured model. A real integration needs a token-aware budget that reserves room for instructions, tool definitions, history, and the answer. Do not report unobserved token usage, latency, or cost as measured facts.

Structured outputs reduce shape ambiguity. Deterministic validation must still check names, schemas, permissions, budgets, citations, and ranges. A generated plan and retrieved document cannot enlarge their own authority. Model judges can be useful signals, but their agreement with labelled examples must be evaluated rather than assumed.

## MCP awareness

Model Context Protocol provides a standard interface for exposing tools/resources to an AI application. It is separate from a retrieval algorithm, vector database, and workflow state machine. The current lab imports an Atlas snapshot from a file; it does not implement an Atlas MCP client/server or reuse ChatGPT connector credentials inside Codespaces.

Before adding a genuine service later, establish its documented endpoint, authentication, read/write scope, input/output contracts, error semantics, and human-review boundary. No endpoint or token should be inferred from the existence of a connected ChatGPT app.

## Optional Java refresher

Explain a small factory/registry dispatch: interface, implementation, lookup, unsupported-key exception, and why returning a new instance avoids shared mutable order state. Distinguish singleton initialization from thread safety of later mutable state. Keep this short; the main lab targets Python, agent execution, and RAG.
