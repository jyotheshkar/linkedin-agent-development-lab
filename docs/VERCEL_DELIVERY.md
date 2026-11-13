# Deliver the completed simulation to Vercel

This is the delivery exercise to perform **after the student simulation is
complete**. It does not report an existing deployment or provisioned database.
The current student branch intentionally contains unfinished functions. Keep
production release disabled until those functions and release checks pass on
the exact learner commit. A tested reference branch does not satisfy that gate
for student work.

The deployment continues to use isolated synthetic evidence and simulated
receipts. Hosting the lab does not turn `sim_submit`, `sim_outreach` or an Atlas
snapshot into a live application integration. The browser question bank was
authored from AIE/JD context; AIE and Minister are not runtime services here.

## Runtime shape

The repository-root `app.py` exposes the FastAPI application as `app`. Vercel's
FastAPI integration resolves that entrypoint and deploys the application as one
Python function. Configuration for this function belongs under `app.py` in
`vercel.json`, rather than treating every FastAPI route as a separate function.
The lab console is served at `/console` by the application.

| Concern | Codespace/local practice | Cloud deployment |
| --- | --- | --- |
| Workflow journal | Local files in ignored working state | Postgres journal |
| Fake-provider receipts | Local SQLite independent of journal | Separate durable Postgres receipt transactions |
| Concurrent resume | One local learner process | Run-scoped advisory lock around complete start/resume |
| Retrieval | Offline test vectors, or optional local FastEmbed/Qdrant lab | Lightweight immutable synthetic index with explicitly labelled offline hash vectors |
| Secrets | Local environment or Codespaces secrets | Vercel environment secrets |
| Private Atlas evidence | Explicit ignored local import | Excluded from this synthetic cloud release |

Cloud process memory and local scratch files are not the durable source of
workflow truth. A fresh function instance must recover the run and fake receipt
from Postgres. The cloud hash-vector path remains deterministic offline
retrieval; it is not proof of semantic embeddings. Keep genuine FastEmbed/Qdrant
experiments in the local/Codespaces lab and report their execution separately.

`PostgresJournal.run_lock` uses a session advisory lock. Its connection must be
direct or session-pooled and remain associated with that session for the entire
locked operation. A transaction-pooled DSN is unsuitable for this lock. Normal
short journal/receipt transactions can use the managed provider's suitable
database connection; configure a separate lock DSN where required. The workflow
must hold the run lock across read, reconciliation, execution and journal save.
Unique receipt identity and payload-fingerprint checks are the simulated
provider contract. They do not establish exactly-once behavior for an unrelated
real employer or email provider.

## Required environment

| Variable | Purpose and boundary |
| --- | --- |
| `LAB_STATE_BACKEND=postgres` | Select durable cloud state; local filesystem state is not a cloud substitute |
| `DATABASE_URL` | Secret managed-Postgres connection string with required provider TLS settings |
| `DATABASE_LOCK_URL` | Optional only when `DATABASE_URL` is already direct/session-capable; otherwise supply a direct/session-pooled lock connection |
| `LAB_API_TOKEN` | Secret bearer token of at least 32 characters; required for cloud API access |
| `LAB_RELEASE_READY=true` | Explicit release intent after checks; this flag is not evidence that checks passed |
| `TEST_DATABASE_URL` | Disposable isolated Postgres database for integration/release verification, not the production data store |

Configure secrets through the Vercel environment editor or interactive CLI
prompts. Never place a token or DSN in a command argument, tracked file, browser
URL, question draft or trace. The bearer token is a simple lab access control,
not a multi-user authentication or authorization system. Keep the deployment
private through the project's access controls and use separate preview and
production credentials/databases when both environments are used.

No database is provisioned by these instructions. Before the later delivery
exercise, select an authorized managed Postgres database dedicated to the lab,
obtain its TLS connection details and a direct/session-capable locking route,
and configure the variables above. Do not reuse operational Atlas tables.

## Complete and verify the learner commit

Run these commands from the repository root in a prepared Codespace. The
committed dependency lock is authoritative; `requirements.txt`, when used for
the deployment bundle, must be the frozen export generated from that lock.
Do not resolve a new dependency set during release.

```bash
uv sync --locked
uv run pytest -m 'not semantic and not live and not postgres'
uv run python scripts/check_release.py
```

`check_release.py` is the release gate: it checks for unfinished task bodies and
runs the defined local verification, including the separate real-Postgres
integration requirement with `TEST_DATABASE_URL`. A missing test database or an
unrun integration is an incomplete release check. Do not convert an unavailable
integration into a passing result. Real model planning, generation and local
semantic tests have separate opt-in evidence; offline passes do not verify them.

Record the exact Git commit, lockfile hash, commands and test results. Confirm
the deployment export contains only runtime dependencies and excludes private
snapshots, model caches, `.lab` state, local environment files and raw private
traces. Installing development dependencies into the Codespace does not mean
they should all be bundled into the function.

Run the explicit schema migration once against the chosen dedicated deployment
database with its `DATABASE_URL` already set securely:

```bash
uv run python -m l1_lab.postgres_store migrate
```

The migration source is `migrations/001_deployment.sql`; the module command is
the supported application migration entrypoint. Review its changes before
applying them. Use the release tests against a disposable database to verify
migration and state behavior before touching deployment state. Do not run
migrations as a request handler or assume a function startup is executed once.

## Configure and deploy at the end of the exercise

Use the authorized Vercel project and record the CLI version used. Interactive
linking and secret entry avoid printing credential values into shell history.
These are instructions for the later release, not actions taken by this build:

```bash
vercel --version
vercel link
vercel env add DATABASE_URL --environment production --type secret
vercel env add DATABASE_LOCK_URL --environment production --type secret
vercel env add LAB_API_TOKEN --environment production --type secret
vercel env add LAB_STATE_BACKEND --environment production --type config
vercel env add LAB_RELEASE_READY --environment production --type config
```

Enter the configured values at the prompts. Omit the `DATABASE_LOCK_URL` command
only after verifying that `DATABASE_URL` meets the session-lock requirement.
Set the non-secret configuration values to `postgres` and `true` respectively.
If the project already has a variable, use its update flow and redeploy after
configuration changes. Do not paste secret values into the command line.

After the exact learner commit passes the release checks and its database is
migrated, deploy the reviewed release:

```bash
vercel --prod
```

The current CLI documentation says a new project's first deployment is
production even when `--prod` is omitted. Therefore, omitting that flag is not a
way to bypass the lab's production release gate. No deployment should run
during unfinished simulation work. The intended sequence is learn, implement,
test, review, migrate, then deploy the completed simulation.

## Verify what was actually deployed

Use the observed deployment URL and exact commit. Check the health response and
the console, then test an authenticated synthetic request and an unauthenticated
rejection. Start a simulated run, observe its review pause, approve/resume it,
and recover it through a later request. Inspect the database-backed state and
receipt evidence rather than relying on one warm process. Exercise two concurrent
resumes in the dedicated integration environment and confirm one logical effect.

Retain the deployment/build receipt and outcomes of these checks. A successful
build does not prove database connectivity, concurrency correctness, authorization
or durable recovery. Keep production data synthetic even after verification.
If a check fails, stop traffic to the affected exercise and return to the last
verified code/configuration. Database changes have their own compatibility and
recovery plan; reverting a deployment does not revert schema or data.

## Official references checked 13 November 2026

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi): supported entrypoints and single-function packaging.
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python): Python/dependency configuration and runtime bundle scope.
- [Vercel CLI deploy](https://vercel.com/docs/cli/deploy): deployment target and first-deployment behavior.
- [Vercel CLI environment variables](https://vercel.com/docs/cli/env): interactive environment management.

Platform commands and limits can change. Recheck these official pages at the
later deployment exercise rather than inferring an unchanged service contract
from this preparation document.
