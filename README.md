# LinkedIn + Atlas L1 learning lab

Your student workspace is **main**. Twelve focused functions are deliberately
unfinished. The complete builder implementation is on **coach-reference**;
opening it counts as reference exposure, not independent work.

This is an interview simulation: every submit, outreach, document-save,
Atlas-commit and dashboard-delivery action uses a local fake provider and `sim:`
receipts. No Gmail, LinkedIn or operational Atlas writer is included.

## Start in Codespaces

Open this repository's **Code → Codespaces → Create codespace on main**. The
development container installs the locked Python 3.12 environment. Then:

```bash
uv run l1-lab doctor
uv run pytest -m infrastructure
uv run pytest -m m1
```

The last command initially fails on the M1 TODOs. That is the assignment
baseline; see [ASSIGNMENT.md](ASSIGNMENT.md) for exact edit boundaries. The
infrastructure suite does not blanket-skip unfinished work. Follow
[LEARNING_PATH.md](LEARNING_PATH.md) with your coaching chat, one concept at a
time. Initial interview competence is unmeasured.

## Modes and commands

| Mode | Retrieval | Generation | Network |
|---|---|---|---|
| offline | Deterministic hash test vectors in Qdrant local | Extractive fixture adapter | None after dependencies installed |
| semantic | FastEmbed BAAI/bge-small-en-v1.5, 384 dimensions, Qdrant local | Extractive fixture adapter | First model download; cached afterward |
| live | Semantic retrieval | Optional real OpenAI structured outputs | Model API, requires your configured secrets |

Reference-side demonstrations (work after the relevant student functions):

```bash
uv run l1-lab demo --mode offline --query 'Python evaluation'
uv run l1-lab demo --mode semantic --query 'human evaluation of language models'
uv run l1-lab evaluate --mode offline
uv run l1-lab run --goal 'prepare application'
uv run l1-lab resume RUN_ID --approve
uv run l1-lab trace RUN_ID
uv run l1-lab export-progress --output .lab/checkpoint.json
uv run uvicorn l1_lab.api:app --host 127.0.0.1 --port 8000
```

`run` pauses for review before any simulated effect. `resume --approve` approves
the exact saved plan. A completed inspect/draft plan still has
`completion.full_unit=false`; only all five verified simulation gates form a
full unit. Restart recovery uses a provider database separate from the journal.
Custom framework users must re-inject their own adapters when constructing a
Workflow for resume; the CLI supports its three documented read-before-effect
plan templates.

Optional live adapters require `OPENAI_API_KEY` and `OPENAI_MODEL` in Codespaces
secrets. The lab never creates, copies or logs credentials. Use `--planner live`
on `run` to exercise real planning independently of generation; use
`--generation live` for real answer generation. Both remain subject to the same
executor and review checks. External-model demos accept only synthetic fixture
evidence. Missing secrets leave these optional paths unverified.

## Atlas snapshot

The committed corpus is synthetic. An approved, selected real Atlas snapshot
is a separate private file, not Git content or a continuously synced source.
Download your provided snapshot into the Codespace, then:

```bash
uv run l1-lab import-snapshot /path/to/Atlas_L1_Knowledge_Snapshot_20261113.json
uv run l1-lab demo --mode offline --snapshot private/atlas_snapshot.json --query 'evaluation'
```

Private snapshots, vectors, journals and raw traces belong in ignored `private/`
or `.lab/`. See [docs/ATLAS_SNAPSHOT.md](docs/ATLAS_SNAPSHOT.md) for mappings,
source hashes and refresh/revocation. The application has no operational Atlas
write path. Citation membership/quote checks are structural; they do not prove
semantic entailment.

## Verification and troubleshooting

See [BUILD_REPORT.md](BUILD_REPORT.md) for executed results and exact revisions,
and [COACH_HANDOVER.md](COACH_HANDOVER.md) for the pasteable project map.

- `unfinished_student_task`: complete the named milestone; setup is working.
- Package errors: rerun `uv sync --locked`; do not edit the lock during lessons.
- Model download error: offline learning remains available; semantic verification
  requires actual weights, never substitute fixed vectors and call it semantic.
- Pending simulation receipt: reconcile on resume; do not create another run to
  disguise the pending effect or edit the journal to fabricate completion.
- `/fit` returns 422 for malformed JSON/schema; 401 when a configured bearer token
  is missing; 409 while an assessed student function is unfinished.
