# Data, persistence and privacy boundaries

The LinkedIn Agent Development Lab is a single-owner learning application.
It has no runtime connection to operational LinkedIn, Gmail, Atlas Sheets/Drive,
the production dashboard, Minister or ChatGPT connector credentials.
Installed plugin materials and the JD inform design and teaching. They do not
grant the Python application connector sessions or employer write authority.

## Independent mode selections

| Selection | Choices | Boundary |
| --- | --- | --- |
| Data | Synthetic default; explicit private Atlas snapshot import | Real imported records are read-only observations; experiments use synthetic forks |
| Retrieval | Offline hash test double; genuine FastEmbed/Qdrant semantic path | A score from the test double is not semantic evidence; no silent fallback |
| Planner | Offline fixture; optional configured real-model adapter | A model proposes calls; executor schemas, permissions, budgets and review control execution |
| Generation | Offline extractive; optional configured real-model adapter | Schema-valid text still requires source/quote/support review |
| Effects | Simulation only | Receipts identify simulated application/outreach; no real email or portal action |

The current live-model demonstration accepts only synthetic fixture evidence.
Configuring a model key does not authorize sending private Atlas imports,
personal application drafts or learning transcripts to that provider. Never
route private records through a synthetic-labelled adapter.

## Where data lives

| Material | Committed/source package | Local persistence | Future ephemeral host |
| --- | --- | --- | --- |
| Synthetic knowledge and evaluation cases | Yes, separately stored | Seeded into Atlas Lab; evaluation labels never indexed | Safe fixtures may be bundled, but mutable state still needs durable storage |
| Selected real Atlas snapshot | No | Explicit ignored `private/` import with provenance/revision/time | Excluded from this build and later default synthetic release |
| Knowledge versions and approvals | Schema/code and synthetic examples only | Atlas Lab SQLite transaction state | Requires a durable adapter; process memory or temporary files are insufficient |
| Prepared/reviewed artifacts | No generated personal payloads | Manifests, actual bytes and immutable digest identity in ignored lab state | Requires durable registry and byte storage before hosted execution |
| Workflow journal | No raw state | Ignored local journal; reconstructable after process restart | Durable store required |
| Provider receipts | Code/contracts only | Independent fake-provider database/transactions | Durable receipt transaction boundary required |
| Event ledger and dashboard projection | Code/contracts only | Atlas Lab committed events and derived readback | Durable events plus checked projection/repair required |
| Model weights and vectors | No | Ignored cache/index; private-derived vectors remain private | Measured bundle or authorized service architecture; not an approval store |
| Learner answers/checkpoints | Schema and synthetic examples only | Private portable versioned checkpoint/export | No automatic upload or cross-chat memory |
| Traces and telemetry | Sanitized examples/summary only | Allowlisted IDs/status/duration; no full content or secrets | Export destination must be explicitly configured/reviewed |
| API/provider/database credentials | Never | Secure environment/secret mechanism | Separate preview/production secret configuration |

Local SQLite and files survive a Python process restart in the same workspace.
That is not a guarantee against workspace deletion, cloud disk expiry or
machine loss. An ignored working copy is not a backup. Use the explicit private
checkpoint/import/export route for material the owner chooses to retain.

## Source trust and refresh

Knowledge eligibility uses latest source version, approval state, provenance
and snapshot revision. A refreshed collection replaces active membership
atomically; removed or revoked records must stop being searchable. Original
source hashes, sanitized text hashes, chunk hashes and artifact byte hashes have
different purposes and must remain distinct. Snapshot age is visible; imports
do not claim continuous synchronization or a new source approval.

Generated briefs, outreach text, receipts, evaluation answers and starred
development references never become candidate evidence. A document/job prompt
cannot change tool permissions, create approval or expand an execution budget.
The console renders content as text instead of executable HTML.

## Review, exports and secrets

Review binds the actual job, action, policy and artifact/payload identity.
A changed source or material needs fresh review. Reconciliation repairs the
existing receipt/ledger/projection rather than inventing completion or repeating
an uncertain employer simulation.

Context export uses explicit source/lesson/test allowlists, bounded size and
redaction. Its normal purpose is code coaching, not exporting the entire
workspace. It must exclude `.env`, keys, private snapshots, full logs and
personal drafts. Inspect an export before sharing; a private Codespace link
alone does not give another chat file access.

Bearer tokens stay in the browser page session only; the last run ID may be
remembered. Closing the page clears unsaved answer state, so export an intended
practice checkpoint first. Record assistance and ungraded status honestly.
Observed model usage may be recorded; missing usage/cost stays unknown.
