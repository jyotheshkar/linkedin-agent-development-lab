# Future delivery: Python/FastAPI on Vercel

**Status: DEPLOYMENT_PREPARED_NOT_EXECUTED.** The current product is the complete
local LinkedIn Agent Development Lab, repository ID **1456774523**:
https://github.com/jyotheshkar/linkedin-agent-development-lab.
The core functions are implemented; learning uses investigation and isolated
experiments. Completion of the code does not establish learner competence.

This build does not import/link a Vercel project, run deployment commands, attach
automatic deployment to pushes, provision a database/domain, create credentials
or publish a package. GitHub is the source of truth; Codespaces is the development
environment and its private forwarded port is a development preview.

## What is portable, and what still needs work

The root `app.py` exports FastAPI. `vercel.json` selects FastAPI and configures
the resolved `app.py` function with a 60-second duration and development/private
file exclusions. Python 3.12, `pyproject.toml` and `uv.lock` remain the delivery
basis. There is no reason to rewrite the service in TypeScript to use a template.

The local complete journey stores approved knowledge versions, artifact bytes,
application events and projection state through `AtlasLab`. It keeps provider
receipt commits independent of the workflow journal. These are durable within
the chosen local workspace, but the workspace's lifetime is not a production
storage guarantee.

**Hosted full-MVP execution must fail closed.** Existing Postgres journal,
simulated-receipt and request-budget adapters cover the earlier engine's narrow
contracts. They do not provide parity for the new Atlas Lab knowledge,
artifact, approval, event-ledger and projection contracts. Configuring
`DATABASE_URL` or `LAB_RELEASE_READY=true` cannot complete that missing adapter.
A deployment that mixes durable runs with ephemeral SQLite/artifact files would
lose the content an approval and receipt refer to.

| Concern | Current local MVP | Required before hosted full-MVP release |
| --- | --- | --- |
| Knowledge/version state | SQLite Atlas Lab; immutable snapshot imports | Durable versioned store with atomic refresh, revocation and source restrictions |
| Prepared/reviewed material | Persisted manifests and content-bound review state | Durable artifact registry and immutable byte storage, with matching versions/hashes |
| Workflow state | Local journal; lock-coordinated execution | Durable journal and concurrency contract across instances |
| Provider effects | Separate persistent fake-provider receipts | Separate durable receipt transactions with the same idempotency/payload rules |
| Events/projection | Atlas Lab ledger and derived readback | Durable ledger plus independently checked projection revision/membership and repair |
| Retrieval | Explicit offline or real local FastEmbed/Qdrant | A tested semantic option with fixed embedding identity; no silent hash fallback |
| Credentials | Local environment/Codespaces secrets | Separate preview/production secrets and restricted storage access |
| Data | Synthetic by default; explicit private local snapshot import | Synthetic hosted release by default; any new private-data transfer needs its own reviewed scope |

Implement a durable Atlas storage interface and its migrations before enabling
the application routes on an ephemeral host. Verify the entire journey against
that implementation, including a fresh process, two concurrent resumes and a
failure after provider success but before ledger/projection success. Existing
Postgres component test passes are evidence only for their stated scope.

## Retaining genuine semantic RAG

The current genuine semantic exercise uses FastEmbed's
`BAAI/bge-small-en-v1.5`, 384-dimensional normalized vectors and Qdrant local.
The `lab` dependency extra supplies its ONNX and vector dependencies. The slim
default wheel excludes them and retains an explicitly labelled hash-vector test
double. Selecting semantic mode must require the real adapter; it must never
quietly become offline mode after a model-download or service error.

Three future hosting designs are plausible:

| Design | What it preserves | Trade-offs and evidence needed |
| --- | --- | --- |
| Bundle FastEmbed with the Python function; use durable remote vector storage | Same embedding model in indexing and query paths | Measure unpacked dependencies/weights, memory, cold starts, inference duration and provider limits; never download weights for every request |
| Separate Python semantic worker/service and durable vector store | Current model and Python retrieval logic | Adds deployment, service authentication, network latency and operational work; needs timeouts, version pinning and monitored availability |
| Hosted embedding service plus managed vector store | Stateless request handler and durable index | Adds credentials, data-sharing review, vendor cost and network dependency; re-embed the whole corpus, pin model/dimension/normalization and calibrate thresholds rather than mix vector spaces |

A separate semantic worker is a reasonable first design to measure when
bundling proves unsuitable; this is an engineering proposal, not an implemented
integration. No service above was provisioned. Latency, cold-start and cost
measurements are unknown. Do not quote prices or claim a budget until the
selected service, region, observed use and dated rate source are recorded.
Live answer generation and live planning remain independent selections from
semantic retrieval.

## Release rehearsal in the repository

Run the documented local checks against the exact commit and frozen lock:

```bash
uv sync --locked --extra lab
uv run l1-lab doctor
uv run pytest -m 'not semantic and not live and not postgres'
LAB_SEMANTIC=1 uv run pytest -m semantic
uv build --wheel
```

Use `TEST_DATABASE_URL` only for an isolated disposable database when testing
the retained Postgres contracts. Run `uv run pytest -m postgres` against that
service. It does not migrate or verify production Atlas.

The installed-wheel smoke test must run from outside the checkout and confirm
packaged data, lessons and console assets. Build a container locally if the
current CI provides that check; do not publish it merely to test packaging.
Record actual results in `docs/VERIFICATION.md` with commit/lock/model identity.

`scripts/check_release.py` is a local verification aid, not a deployment action
or proof that hosted Atlas parity exists. Any earlier report saying the old
journal/receipt engine passed is historical evidence. A later cloud release
requires new application-level tests for the durable Atlas adapter and chosen
semantic service/bundle.

## Manual delivery after a later explicit release instruction

Before a future import, linking action or deployment:

1. Resolve this same private repository ID and the reviewed commit; choose the
   intended Vercel team/project/environment.
2. Finish and test durable knowledge/artifact/event/projection adapters and
   migrations. Review backups, schema compatibility and least-privilege access.
3. Measure the chosen semantic path within the host's package, memory and
   duration limits. Record that path and its unavailable/error behavior.
4. Configure preview and production with separate synthetic databases/artifact
   namespaces and secrets. Keep migration privileges away from request handlers.
5. Review the deploy action and keep its workflow manual and guarded. Ordinary
   code pushes in this task run tests only.
6. After an authorized later deploy, test the observed URL: auth rejection,
   exact-artifact approval, full run, pending/reconciliation repair, process
   restart and concurrency. Capture actual deployment/build receipts.

Legacy Postgres session advisory locks require a direct or session-pooled lock
connection; a transaction-pooled DSN cannot preserve that session association.
The lock must span read, reconciliation, effect execution and saves. Keep provider
effects in their own committed transactions. Migrations run explicitly, never
as a request handler or with an assumption that startup happens once.

Keep `LAB_API_TOKEN` and database credentials in supported secret mechanisms;
never paste them into chat, URLs, tracked files, browser storage or traces.
A single-owner bearer token does not implement multi-user authorization.
No credential values or deployment commands are supplied here.

A rollback changes application traffic/code; it does not undo stored effects,
data or schema migrations. Reconciliation must remain compatible with receipts
and reviewed artifacts created by a prior release. Preview testing cannot prove
production environment credentials or storage routing are correct.

## Official references rechecked 14 November 2026

- [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi): Python entrypoint, single-function configuration and application packaging.
- [Python runtime](https://vercel.com/docs/functions/runtimes/python): dependency manifests, version selection and explicit file exclusions.
- [Function limits](https://vercel.com/docs/functions/limitations): package, memory and execution constraints.

Platform options change. Re-read these references for the eventual selected
plan instead of treating this preparation document as a permanent limit table.
