# Deployment preparation — verified 13 November 2026

The Python learning lab now has a browser console and a concrete Vercel delivery
path. Production deployment remains the exercise after the student simulation.
No Vercel project, managed database, API key or live employer integration was
created. Existing Vercel projects were inspected read-only.

## Executed checks

| Check | Observed result |
| --- | --- |
| Complete reference, including actual PostgreSQL 16 | **254 passed**, 1 semantic test deselected, 5.90 seconds |
| Infrastructure checks on reference | **60 passed**, 195 deselected, 2.77 seconds |
| Student infrastructure and installed-wheel smoke test | GitHub workflow completed successfully |
| Isolated noneditable production wheel | Resources, console assets, config/practice and complete reference review/receipt flow passed outside the repository |
| Slim runtime | Installed wheel excludes both FastEmbed/ONNX and qdrant-client; no runtime model download |
| Student browser behavior | Actual unfinished M3 function returned 409; no synthetic success substituted |
| Reference browser behavior | Retrieved cited synthetic evidence, paused before effects, approved exact plan, verified all five simulated receipts |
| Browser recovery | Reloaded page and loaded the completed run from persistent local state |
| Mobile layout | 390-pixel viewport checked; document/client width both 375 pixels after scrollbar, no horizontal overflow |
| Source integrity | All 12 student TODO bodies retained; solved reference remains on a separate branch |

Tested student source: `b86969936b34b1aa9e5c3ac093ef07fa9f86206f`.
Tested reference source: `2b55b71658ee0d7a8a2776bf83b54c7061cb6475`.
Documentation commits may follow without changing those tested implementations.

- [Student CI](https://github.com/jyotheshkar/linkedin-atlas-l1-lab/actions/runs/43463182509)
- [Reference CI](https://github.com/jyotheshkar/linkedin-atlas-l1-lab/actions/runs/43463190960)

The first scaffold CI run lacked the newly generated dependency lock and failed;
the lock was generated in the Codespace, committed and used in the successful
runs above. The Windows host could compile code but could not supply this full
runtime. These are real Linux/Python 3.12 and PostgreSQL results, not host-side
test claims. The browser run used local persistence; the separate CI database
tests establish the Postgres behavior.

## Behaviors exercised

Thirteen actual database integration tests cover independent receipt commits,
restart recovery, lost lock sessions, concurrent duplicate effects, changed
payload rejection, request budgets, approval races, and uncertain outcomes.
The HTTP recovery test commits a simulated provider effect, loses its reply,
creates a fresh request, reconciles the saved receipt and completes without a
duplicate. Concurrent approvals yield one logical effect per gate.

Authentication rejects absent/wrong/non-ASCII credentials. Cloud configuration
fails closed without durable storage, a sufficiently long token, a direct or
session-pooled locking connection, completed task bodies and release intent.
Actual request bytes are bounded, private responses are not cached, and errors
omit database strings. A bearer token is a single-owner lab control, not a
multi-user access model. No secrets enter browser persistent storage.

Vercel uses the root FastAPI entrypoint and a 60-second function configuration.
The slim package contains immutable synthetic resources and a read-only hash
index. It does not need writable vector files or model weights. Real semantic
FastEmbed/Qdrant work remains available with `uv sync --locked --extra lab`.
The web planner and answer generator are offline adapters; this verification
does not claim hosted LLM behavior. Optional live adapters remain in the CLI.

## Learning and release boundaries

Sixteen original AIE/JD prompts cover implementation, tracing, debugging and
transfer. The practice view exports ungraded answers with assistance flags; no
score or personal readiness is inferred. AIE informed the content but is not a
live runtime integration. Builder tests are not learner competence evidence.

The runtime's unfinished-task scan is a guard, not proof of correctness.
`scripts/check_release.py` additionally requires the full offline suite and
actual Postgres checks against a disposable database. Deployment still needs
the completed learner commit, a dedicated managed database, securely configured
credentials, a Vercel build, and post-deployment authentication/restart checks.
Those external deployment steps have not been executed. Follow
[VERCEL_DELIVERY.md](VERCEL_DELIVERY.md) when the simulation is complete.
