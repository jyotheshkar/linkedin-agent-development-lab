# Verification — complete MVP, 14 November 2026

This is software verification, not a grade or a hiring/readiness forecast.
Employer actions are local simulations. No operational LinkedIn/Gmail/Atlas
write, public deployment, hosted database or package publication occurred.

## Source and environments

- Private repository: https://github.com/jyotheshkar/linkedin-agent-development-lab
  (stable ID **1456774523**). Renamed in place; history retained.
- Starting remote main: `59d61725b1a7d05e7d11aac69eabda9f112c7cbb`, preserved as
  `archive/student-scaffold-20261114`. Historical `coach-reference` retained.
- Completed implementation branch: `complete-mvp-20261114`, integrated through
  [PR #1](https://github.com/jyotheshkar/linkedin-agent-development-lab/pull/1).
  The PR's merge record identifies the resulting main commit.
- Final executed code head: `01100cc77447bd23d600ecd416f7600eaef69c6f`.
  Actions tested its merge tree `d39ad9c081232aa493640007043f27e5f4c8b57b`.
  Subsequent verification documents/manifests do not change that runtime code.
- Lock SHA256: `2a967354c161b7ab6331d1b632fc714c095981a28661d2fd6c03d96c6fbf6d60`.
- Existing Codespace actually started and exercised with Python **3.12.11**:
  https://laughing-space-pancake-gv4qwv5p667c9rv6.github.dev/
- Observed private development preview, port **8001**, route `/console`:
  https://laughing-space-pancake-gv4qwv5p667c9rv6-8001.app.github.dev/console
  It needs the owner's authentication and a running Codespace. This is not
  production hosting. The existing container was used, not claimed rebuilt.
- GitHub Actions used Python 3.12, uv **0.13.8** and disposable PostgreSQL **16**.
  Host-only checks used Python **3.11.15** and are identified separately.

Selected locked versions: LangGraph **1.2.21**, FastAPI **0.162.6**,
Pydantic **2.14.3**, OpenAI **2.54.0**, FastEmbed **0.9.1**,
Qdrant client **1.20.0**, MCP **1.30.0**, OpenTelemetry SDK **1.45.2**,
pytest **9.2.0**, psycopg **3.3.9**, uvicorn **0.54.0**.

## Observed results

| Check / actual command | Environment | Result and scope |
|---|---|---|
| Baseline `uv run pytest -m 'not semantic and not live and not postgres'` | Codespace, original clean `c484ce84d858c45f30cf7595ac25eb27fb74a52d` | **174 failed, 67 passed, 14 deselected; 5.22s**. Expected scaffold failures; not the final implementation. The later starting remote commit added README provenance only. |
| `uv run pytest -m 'not semantic and not live' --junitxml=.lab/deployment-reference.xml` | Actions, code head above, actual isolated Postgres | **343 passed, 0 failed, 2 deselected; 21.11s**. Includes core, API, real CLI subprocesses, SQLite/Postgres persistence, recovery/concurrency, genuine MCP child-process protocol and OTel SDK tests. |
| `uv run pytest -m infrastructure` | Same Actions tree | **68 passed, 277 deselected; 2.87s**. This subset overlaps the full suite; do not add the totals. |
| `uv build --wheel`; install wheel in a fresh venv; `python -I scripts/check_installed.py` | Actions, noneditable install outside checkout | Passed resource/API/artifact flow with no FastEmbed/Qdrant installed; this is explicitly offline mode. |
| `docker build -t linkedin-agent-lab:test .` | Actions | Passed local image build; image not published. |
| `uv run pytest tests/test_workflow.py tests/test_cli_journey.py -q --junitxml=.lab/mvp-recovery-final.xml` | Codespace, final code head | **29 passed; 7.88s**. Includes bounded backoff, interruption after effect, original receipt recovery, CLI root parity and fresh processes. |
| `LAB_SEMANTIC=1 uv run pytest -m semantic -q --junitxml=.lab/mvp-semantic-final.xml` | Codespace, final code head | **2 passed, 343 deselected; 3.20s**. Actual ONNX `BAAI/bge-small-en-v1.5`, 384 dimensions, L2 normalization and local Qdrant; no hash fallback. |
| `uv run l1-lab validate-lessons`; `uv run l1-lab context-export --lesson CONTRACTS-01 --output .lab/ci-context.json` | Actions and Codespace | **10 lessons validated**, exact symbol/test links; three-file bounded export. Separate bundle-only handoff inspection documented below. |
| Selected real Atlas import, read-only check, chunk/rank/ground | Host only; existing authorized selected snapshot | **5 records, 6 chunks, 2 retrieved hits**, supported extractive answer, mutation rejected. Native revision **3482**, observed snapshot about 27.5h old at check; no fresh/live synchronization. Deterministic hash retrieval, not a semantic/private-model test. |
| Real model planning / generation | Not run | **Pending**. No configured model/authorized live request in this run; contract mocks are not live evidence. No key copied or created. |

Actions evidence: [run 43630905036](https://github.com/jyotheshkar/linkedin-agent-development-lab/actions/runs/43630905036),
reference job **132557042524**, infrastructure job **132557042790**.
Earlier unsuccessful integration runs exposed and corrected fixture, resource,
CLI-root and LangGraph cancellation-wrapper problems. The earlier **335 passed**
run is superseded by this **343 passed** run. A failed run at `2fab4d8` had
342 passed/1 failed: the locked LangGraph wraps a sync-node `CancelledError` in
`NodeCancelledError`; the fix preserves the original cause and in-flight intent.

Machine-readable summaries: [MVP report](../verification/mvp-20261114.json),
[selected Atlas check](../verification/selected-atlas-20261114.json),
[fresh evaluation](../verification/fresh-evaluation-20261114.json), and
[source manifest](../verification/source-manifest.json).
Raw JUnit and local state remain ignored under `.lab/`; CI logs are available
in the linked private run. Private snapshot/drafts/keys are not committed.

## Browser journey actually observed

Using the supplied synthetic Python Workflow Engineer requirement, **semantic
retrieval**, offline planning and extractive generation:

1. Prepared run `33444d7880ff40c2be95cebf3f90b7a3`; read two actual job-specific
   Markdown drafts, citations, provenance and exact artifact identities.
2. Approved the displayed material for simulation; observed **7/8 calls**, all
   seven plan steps completed and **five verified gates**.
3. Read Atlas Lab ledger revision **5** and projection revision **5**, exact
   five-event membership, `up_to_date=true` and one simulated complete unit.
4. Reloaded the browser and recovered the same completed run without a new
   application or outreach effect.
5. Downloaded the 953-byte application brief and independently hashed the saved
   file: `d30d23a58efce427ffe05a6cd2419dadf594a20cfe037c2889237f4e128aeb2c`,
   exactly matching the registered immutable bytes. The outreach draft was
   1088 bytes, digest `dc3c363253e83d206de2d7514ccdcfa0051f1c1ed81464acf0afb7e6a167f143`.
   Download controls remain disabled before reviewed bytes are stored.
6. Opened the ten-lesson learning view, Contracts lesson, actual diagram and
   source/test references. Desktop layout visually inspected. No new mobile
   breakpoint result is claimed for this final version.

## Fresh evaluation and a known relevance limitation

The original 14-case development bank is calibration/regression material, not
an independent benchmark. Four new developer-authored scenarios were held out
from that implementation and never indexed. Executed with the frozen **0.3**
similarity threshold; the threshold was not changed after seeing these results.

`uv run python scripts/evaluate_holdout.py --mode semantic` produced:

| Metric | Observed |
|---|---|
| Expected-evidence retrieval recall | **4/4** |
| Citation IDs valid | **4/4** |
| Label-supported extractive claims | **3/4** |
| Negative-case abstention | **0/1** |
| Answerable coverage proxy | **1/3** |
| Explicit expected review statuses | **2/2** |

The unrelated quantum query retrieved material and returned a claim instead of
abstaining. A citation can be valid while irrelevant to a question. This is a
known quality limitation, not hidden by the passing integration tests. The
coverage proxy counts the two deliberately conflicting/injection cases as
answerable even though their intended status is review; it is not a readiness
score. Four cases cannot establish general retrieval reliability.

The workflow still requires exact owner review and permits only simulations.
Before any future operational use, improve relevance/abstention on a separate
development set, then measure new unseen positives and negatives. Do not tune
the threshold to make this now-exposed bank look independent again.

## Learning and release status

| Category | Status |
|---|---|
| `LOCAL_MVP_VERIFIED` | Functional local scope above verified; known retrieval-quality limitation remains. No claim that every benchmark passed. |
| `LIVE_MODEL_VERIFIED` | Pending; no live call observed. |
| `ATLAS_SNAPSHOT_VERIFIED` | Selected host-local read-only import and deterministic exercise verified; not a live Atlas integration. |
| `LEARNING_HANDOFF_VERIFIED` | Ten code-linked lessons, five SVG/PNG diagrams, allowlisted export and [bundle-only handoff check](learning/HANDOFF_CHECK.md). Independent learner skill remains unmeasured. |
| `DEPLOYMENT_PREPARED_NOT_EXECUTED` | Packaging/configuration reviewed and built; no deployment. Full hosted Atlas artifact/knowledge/event and semantic parity still required; cloud execution fails closed. |

Stars audit observed **32 public starred repositories** on the authenticated
two-page list, selected six pinned/licence-reviewed reference cards, added no
unnecessary framework and copied no upstream source. Private/hidden stars were
not proven complete. See [source library](skills-library/README.md).

For verified setup/demo/test/console/context commands, use [README](../README.md)
and [COACH_HANDOVER](../COACH_HANDOVER.md). Start with anatomy, then Contracts.
A private URL alone does not let another chat inspect the repository; use the
reviewed context JSON if source access is unavailable. `python
scripts/check_source_manifest.py` compares saved source bytes only and does not
replace execution tests.
