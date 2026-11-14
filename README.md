# LinkedIn Agent Development Lab

A complete Python learning MVP for evidence-backed application workflows,
isolated Atlas knowledge, exact material review and recoverable simulated
actions. Created in **2026**. Repository ID **1456774523**, private.

The default application is implemented. Investigate its code, run an experiment
and explain the result. The former twelve-function scaffold is preserved on
`archive/student-scaffold-20261114`; `coach-reference` remains historical.
Builder-generated implementation and software tests do not establish independent
learner skill. Employer actions are always **SIMULATION**.

## Start

Use the existing [Codespace](https://laughing-space-pancake-gv4qwv5p667c9rv6.github.dev/)
or create one from this repository. The development container uses Python 3.12.

```bash
uv sync --locked --extra lab
uv run l1-lab doctor
uv run l1-lab seed --root .lab
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

Open the **private** forwarded port at `/console`. Supply a synthetic job, inspect
its retrieved evidence and two actual Markdown drafts, then approve/reject/revise
the exact plan. Approval stores the reviewed bytes before application/outreach
simulation. Inspect separate receipts, committed Atlas Lab events and projection
membership. Recover the same saved run after restarting.

## Modes are independent

| Setting | Choices | Boundary |
| --- | --- | --- |
| Data | Synthetic default; selected private Atlas snapshot via CLI | Operational Atlas is untouched; no live synchronization |
| Retrieval | Offline hash test double; FastEmbed semantic + Qdrant local | Hash similarity is explicitly nonsemantic |
| Planner | Offline fixture; optional live structured model | Executor enforces permissions and approval |
| Generation | Offline extractive; optional live structured model | Citations and exact quotes are structural checks |
| Effects | Simulation | No employer, LinkedIn or Gmail writer |

The console supports semantic retrieval and independent model settings. The
optional real-model adapters use securely configured `OPENAI_API_KEY` and
`OPENAI_MODEL`; they accept only synthetic evidence. No fallback silently turns
a failed live/semantic request into an offline success. Verification status is
reported separately in [docs/VERIFICATION.md](docs/VERIFICATION.md).

## CLI journey

```bash
uv run l1-lab run --job data/job.json --goal 'prepare application' --root .lab
# Inspect the returned artifacts and exact approval hash first:
uv run l1-lab resume RUN_ID --approve --plan-hash PLAN_HASH --root .lab
uv run l1-lab trace RUN_ID --root .lab
uv run l1-lab knowledge --root .lab
uv run l1-lab dashboard --root .lab
uv run l1-lab demo --mode semantic --query 'How are duplicate actions prevented after a timeout?'
uv run l1-lab evaluate --mode offline
uv run l1-lab validate-lessons
uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/context.json
```

The CLI and browser use `ApplicationService`. Its SQLite Atlas Lab stores
immutable knowledge versions, approvals, artifact bytes/hashes and an event
ledger. Provider receipts commit independently from the workflow journal.
Reporting is a derived projection with separate revision and membership checks.
Logging repair reconciles existing receipts instead of repeating an action.

## Learn from the implementation

- [START_HERE.md](START_HERE.md): system map and launch commands.
- [CHAT_BOOTSTRAP.md](CHAT_BOOTSTRAP.md): pasteable new-chat handover.
- [COACH_HANDOVER.md](COACH_HANDOVER.md): source-first coaching and contribution boundaries.
- [Lesson index](docs/learning/lesson-index.json): ten lessons linked to actual symbols, tests and diagrams.
- [System anatomy](docs/architecture/system-anatomy.svg) and [request sequence](docs/architecture/request-sequence.svg).
- [JD coverage](docs/JD_COVERAGE.md), [architecture decisions](docs/DECISIONS.md) and [starred source library](docs/skills-library/README.md).

A future chat needs actual source access or the bounded JSON export; the private
Codespace URL alone does not provide it. Start with repository anatomy, then
`contracts.py`, unless you choose another component. Practice exports remain
ungraded until observed work is reviewed. No readiness or hiring probability
is inferred from completed code.

## Verification and extensions

```bash
uv run pytest -m 'not semantic and not live and not postgres'
LAB_SEMANTIC=1 uv run pytest -m semantic
# With a disposable isolated PostgreSQL service:
uv run pytest -m postgres
uv run python -m l1_lab.mcp_server --root .lab
```

The read-only [MCP example](docs/MCP.md) uses genuine protocol discovery and
invocation. OpenTelemetry SDK spans export measured timing and safe identifiers
locally; unavailable usage/cost remain unknown. CI tests the package, local
workflow, Postgres adapters and container build without publishing.

Private snapshots, state, vectors, context bundles, traces and environment files
stay outside Git. See [privacy](docs/PRIVACY.md) and [Atlas import](docs/ATLAS_SNAPSHOT.md).
The archived reports retain the original scaffold's observed failures.

Vercel/FastAPI delivery is **prepared, not executed**. The full MVP needs durable
hosted Atlas knowledge/artifact/event storage and verified semantic adapter
parity before release. The narrow Postgres workflow adapter is tested separately.
The current cloud runtime fails closed; no project, public preview, database,
domain or package was published. See [delivery guide](docs/VERCEL_DELIVERY.md).
