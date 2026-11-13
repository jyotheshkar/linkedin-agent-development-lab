# Build and verification report — 13 November 2026

Dedicated repository: https://github.com/jyotheshkar/linkedin-atlas-l1-lab
Authenticated owner `jyotheshkar` (96298283); native metadata confirms private
visibility. No existing production repository or installed plugin was changed.

Running Codespace observed in the browser:
https://laughing-space-pancake-gv4qwv5p667c9rv6.github.dev/

## Evidence revisions

| Evidence | Immutable revision |
|---|---|
| Reference source and build probe | `4e5a673aca1e756d60f1418d5423b63f7bc464f1` |
| Reference dependency lock and cloud result commit | `dd7a51bd5ea271996b87f841bd108393a8d05045` |
| Initial student source tested | `fcf6a90a0e9edf8dba82e0b9e70348159bfdffec` |
| Student baseline evidence commit | `0aae8049b2c9575903558b08b4c3f85c7559b6cc` |

Branch names are `main` (student) and `coach-reference` (complete builder
reference). Final documentation commits follow these immutable tested source
revisions; use `git rev-parse HEAD` for the current checkout. The final handover
also reports both final remote branch heads. Student history is rooted in the
initial scaffold; the solved reference commit is not a main-branch ancestor.

## Executed verification

| Category | Actual result |
|---|---|
| Cloud setup/infrastructure | 18 passed, 177 deselected; 0.47 s on reference; 18 passed, 177 deselected; 0.55 s on student |
| Complete reference | 194 passed, 1 semantic test deselected; 5.41 s |
| Initial student full offline baseline | 25 passed, 169 failed, 1 semantic test deselected; 1.86 s |
| Genuine local semantic retrieval | 1 passed, 194 deselected; 3.40 s; actual FastEmbed ONNX plus Qdrant local |
| Real model planning/tool selection | Optional adapter contract-tested with fake SDK response; no live API call executed |
| Real model answer generation | Optional adapter rejects private evidence; no live API call executed |
| Codespaces | Cloud workspace launched; Python 3.12 dependency environment and tests executed there; custom development-container rebuild checked separately below |

The 169 student failures are honest unfinished-task evidence: 168 propagate
`NotImplementedError`; one REST integration assertion receives the deliberate
409 unfinished-task response. No student task is blanket-skipped or labelled a
pass. There are exactly **12** deliberate task bodies, listed in
`data/student_tasks.json`. The 25 passing tests concern provided behavior; they
do not demonstrate student competence.

The custom Python development container was rebuilt and the student editor
reconnected on main. Its post-rebuild doctor and infrastructure check are
recorded under `verification/post-rebuild-*`. The rebuild exposed an existing
Codespaces Git LFS pre-push hook without the Git LFS executable; the official
Debian package was installed, preserving the hook. The idempotent setup now
checks for and installs that package for future containers.
The post-rebuild infrastructure rerun passed **18 tests** in **1.85 s** on
the image's Python **3.12.11**, with the same locked package versions. Both
tested interpreters satisfy the declared Python 3.12 contract.

Commands executed in the cloud include:

```bash
uv python install 3.12
uv lock
uv sync --locked
uv run pytest -m 'not semantic and not live' --junitxml=verification/reference.xml
LAB_SEMANTIC=1 uv run pytest -m semantic --junitxml=verification/semantic.xml
uv run python scripts/probe.py
uv run pytest -m infrastructure
# After switching to main:
uv run pytest -m 'not semantic and not live' --junitxml=.lab/student-baseline.xml
```

Reference GitHub Actions also passed independently at the locked reference
revision: https://github.com/jyotheshkar/linkedin-atlas-l1-lab/actions/runs/43456331595
The workflow checks infrastructure on main and the full offline suite on the
reference branch. It does not claim to assess student explanations.

Observed cloud environment: Linux, Python **3.12.16**, uv **0.13.8**.
`uv.lock` pins the complete resolved dependency graph. Tested direct packages:

| Package | Version |
|---|---|
| LangGraph | 1.2.21 |
| FastEmbed | 0.9.1 |
| qdrant-client | 1.20.0 |
| Pydantic | 2.14.3 |
| FastAPI | 0.162.6 |
| pytest | 9.2.0 |
| OpenAI SDK | 2.54.0 |

Host-local Python 3.11 compilation and limited pure-Python probes preceded cloud
testing. Local package downloads failed DNS resolution; these were not counted
as successful runtime verification. The cloud runtime supplied the actual
dependency lock, target interpreter, reference tests and semantic execution.

## Evaluation and integrated behavior

Fourteen developer-labelled development cases are stored outside the indexed
corpus. The same small bank calibrates the declared offline relevance threshold
0.3; it is not an independent held-out benchmark.

| Metric | Observed numerator / denominator |
|---|---|
| Retrieval recall@k | 11 / 11 expected evidence records |
| Citation membership validity | 10 / 10 citations |
| Labelled extractive answer support | 10 / 10 generated claims |
| Insufficient-evidence abstention | 4 / 4 negative cases |
| Answerable supported-status coverage | 8 / 10 cases |
| Expected conflict/injection review status | 2 / 2 cases |

Support here checks expected record IDs, exact extractive text and prohibited
strings. It is not semantic entailment or a calibrated model judge. Conflict
and injected-document cases correctly require review rather than counting as
supported-status coverage. No observed token use/cost is invented: those fields
remain null in offline evaluation.

The integrated probe retrieved synthetic evidence, built budgeted context,
generated a cited extractive draft, paused at `awaiting_review`, then completed
five distinct simulated effects only after exact-plan approval. It observed
five fake-provider effects and `completion.full_unit=true`. A completed
inspect/draft plan has `completion.full_unit=false`. Provider receipts persist
independently of the JSON journal; tests cover timeout-after-effect, journal
failure, pending delivery, cross-run identity and changed-payload rejection.

Real semantic testing used **BAAI/bge-small-en-v1.5**, **384** dimensions and L2
normalization. It retrieved the expected receipt-recovery evidence via Qdrant
local mode. The offline hash adapter is explicitly a test double and was not
used as semantic proof. Generation in this semantic test was not a live LLM.

## Knowledge provenance and privacy

Atlas scans returned all 34 approved Candidate_Facts and all 4 approved
Project_Registry records at revision **3482**, with no remaining page. The
separate private export selects five records; it preserves native source IDs,
versions, approval, content hashes, source refs and retrieval time. The selected
Atlas project also retains its source commit, narrow approved claims, unknown
personal authorship and proposed maturity. Full-CV/contact/message/credential
content is excluded. A host-side load/chunk probe accepted 5 records and made
6 chunks. Real snapshot RAG in the Codespace remains a later file-import path;
the executed cloud demos use synthetic fixtures.

Private file: `Atlas_L1_Knowledge_Snapshot_20261113.json`. Its durable identity
is recorded in `docs/provenance.json`; it is not tracked Git content. Import
instructions are in `docs/ATLAS_SNAPSHOT.md`. This snapshot is not live sync.
The app has no operational Atlas writer or production submit/send adapter.

The LinkedIn helpers `batch_guard.py`, `five_gate_guard.py` and
`atlas_sync_plan.py` were inspected as source snapshots. Their pure checks and
evidence/recovery concepts informed the new implementation; they were not
treated as remote verification or execution tools. Exact source-content hashes
are recorded in the provenance manifest. RAG, LangGraph wiring, the fake
provider and learning tasks are new lab components. Archived AIE agent/RAG
practice files were inspected and left unchanged.

## Handover and limitations

Initial interview competence is unmeasured: no graded student attempt was
created. Perfect builder tests do not establish independent implementation or
interview readiness. Graded progress requires an explicit `assisted` Boolean;
missing assistance evidence cannot create independent accuracy or mastery.

Optional live-model planning and generation were implemented but not exercised
against a real provider. No key was created/copied, no recruiter was messaged,
and no application or operational Atlas record was changed. The external-model
demo is restricted to synthetic fixture evidence. Structural validation and
provider idempotency are narrow simulation contracts, not exactly-once or
production-security guarantees.

Start with `uv run pytest -m m1`, then `contracts.parse_job`, using
`COACH_HANDOVER.md`. Keep main checked out. Mock questions remain unexposed;
the coaching chat creates fresh variants later. Learning is untimed by default.
