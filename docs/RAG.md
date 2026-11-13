# Atlas knowledge and retrieval contract

The tracked fixture is invented. It is not the owner's CV, a live Atlas connection, or evidence of production engineering work. `AtlasSnapshotSource` reads one file; nothing in this lab writes operational Atlas records. ChatGPT connector credentials are not available inside Codespaces.

| Component | Input | Output | Failure boundary |
| --- | --- | --- | --- |
| `load_snapshot` / `AtlasSnapshotSource.load` | UTF-8 JSON path, at most 5 MB | Version 1 envelope | Malformed JSON, wrong envelope or `live` kind fails |
| `select_records` (M3) | Snapshot with flattened provenance | Latest eligible approved record copies | Reject mixed revisions, malformed provenance, sensitive fields and contradictory equal versions |
| `chunk_records` (M3) | Selected records, 40–4000 character bound | Paragraph/word chunks with deterministic IDs | Reject nonapproved input, duplicate chunks and invalid bounds |
| `VectorIndex` | Chunks and explicit mode | One Qdrant local collection | No remote Qdrant endpoint exists |
| `rank_hits` (M4) | Scored hits, top-k, threshold, filters | Filtered stable ranking | Reject Boolean/nonfinite numbers and duplicate IDs |
| `build_context` (M5) | Ranked hits, exact character budget | JSON untrusted-evidence envelope | Whole chunks only, no silent text truncation |
| `validate_answer` (M5) | Structured answer and actual context hits | Validated copied answer | Reject invented citations and inexact quotes; conflicts require review |

## Snapshot envelope

Required envelope fields are `schema_version: 1`, `kind: synthetic | atlas_snapshot`, integer `revision`, string `retrieved_at`, and `records`. Only `Candidate_Facts` and `Project_Registry` are supported.

Each record has `record_id`, integer `record_version`, `approval_status`, `table`, `source_ref`, string `source_version`, native `content_hash`, selected `text`, integer `snapshot_revision`, and `retrieved_at`. Optional fields are `source_commit_sha`, `metadata`, `superseded` and `export_text_hash`. Native payloads must be mapped deliberately; a native Atlas record is not assumed to contain a `text` field. Preserve any claim-level limitations in selected text or metadata. Contacts, recipients, message bodies, full CVs and credentials are outside this contract.

Choose the highest version before checking approval. An approved version 1 followed by rejected version 2 contributes no evidence. Equal copies at the same ID/version collapse; conflicting copies raise an error. Every record's snapshot revision must match the envelope. A source scan that changes revision must restart before this file is made.

The source `content_hash` is retained unchanged. `export_text_hash` describes the selected text; `chunk_text_hash` describes a chunk. Neither claims to reproduce the native record hash. Chunk IDs incorporate table, record ID, version, chunk position and text hash. Changing a version changes IDs even when the text is unchanged.

Keep private snapshot files, derived embeddings and raw traces in the ignored private working directories described in the root README. Import is a point-in-time snapshot, not synchronization. Rebuilding the Qdrant collection removes all previous points, including superseded or revoked records. A disk path has one owning process; close the index before reopening it.

## Two retrieval modes

| Mode | Embeddings | Store | Generation |
| --- | --- | --- | --- |
| `offline` | SHA256 bucketed word counts, 256 dimensions, L2 normalized; deterministic test double | Qdrant local | `OfflineGenerator` copies exact evidence |
| `semantic` | FastEmbed ONNX `BAAI/bge-small-en-v1.5`, 384 dimensions, L2 normalized | Qdrant local | Still offline extractive unless a separate live generator is selected |

The semantic mode downloads weights on its first use. Once cached, local retrieval needs no paid API. Fixed or hashed vectors are not proof of semantic embedding behavior. A successful semantic test does not verify live LLM planning or answer generation.

The retrieval manifest records the actual model ID, dimensions, normalization and mode. Qdrant uses cosine distance. `rank_hits` keeps `score >= min_score`, applies exact provenance/metadata equality filters, orders by score and then chunk ID, and takes top-k. The function's starting default is `.2`. The labelled offline development set uses the same `.3` threshold for every case: measured relevant first-hit similarities were `.463`–`.678`, while the four negative questions' maximum similarities were `.082`–`.237`. The set is small and exposed, so these are calibration observations, not held-out generalization. Unanswerable semantic queries may still have high cosine similarity; thresholds must be remeasured when model, corpus or query distribution changes. A threshold is not an entailment test.

For an understandable example, normalized vectors `(1, 0)` and `(0.8, 0.6)` have cosine similarity `.8`; an orthogonal `(0, 1)` has similarity `0`. Real model coordinates are learned features, not individual named skills. Increasing top-k improves recall only until irrelevant evidence consumes the context budget.

## Context, answers and evidence limits

`build_context` returns a JSON envelope with `kind: UNTRUSTED_EVIDENCE`. Text remains data even when it says to send an email or change budgets. This module contains no tool-execution path. The hostile fixture therefore cannot authorize an effect, and the offline generator labels that fixture for review.

The context limit counts every character, including JSON escaping and citation headers. It is not a guarantee about model tokens. Live adapters must additionally budget system instructions, tool schemas, output allowance and provider token limits. Validate citations against the chunks actually retained by context construction, not against every search hit that was dropped by the budget.

Answers contain exactly `status`, `claims` and `gaps`. Claims have `text`, one or more `evidence_ids` drawn from chunk IDs, and optionally an exact `quote`. Supported answers require claims and no gaps. Abstention requires no claims and at least one gap. Review requires a gap. Curated conflicting claim values in a shared `conflict_group` cannot be represented as supported. The label is a conservative fixture signal; it is not general natural-language contradiction detection.

Citation membership and exact quotation are structural evidence checks. They do not prove semantic entailment, source truth or successful task completion. A live model judge would be fallible. Token overlap, a deterministic temperature setting and passing unit tests do not prove factual truth.

## Verification and diagnosis

Run these on `coach-reference` for complete behavior, or as milestone checks after implementing the named student tasks:

```bash
uv run pytest -m m3
uv run pytest -m m4
uv run pytest -m m5
LAB_SEMANTIC=1 uv run pytest -m semantic -v
```

The semantic test must actually load the ONNX model and retrieve receipt-recovery evidence using a paraphrased question. If a download fails, preserve the error and report semantic verification unavailable; offline success is a separate result.

`data/eval_cases.json` contains 14 labelled cases outside the indexed corpus: 10 answerable retrieval cases and 4 unanswerable cases. The conflict and injection cases should enter review. Score retrieval recall against expected record IDs, citation membership against cited chunks, and abstention against labelled unanswerable cases with separate denominators. Answer support needs the expected evidence labels plus the generated content, not membership alone. Inspect each failed case before changing a threshold; do not tune on an unseen final mock.

Changed-scenario exercises: revoke a source version and rebuild; swap an embedding model and recalibrate; shrink the context budget until a relevant hit is omitted; introduce a conflicting source; or paraphrase a query with no shared words. Explain the observed failure and a meaningful test before accepting a fix.

## Official API references inspected

- [FastEmbed quickstart](https://qdrant.tech/documentation/fastembed/fastembed-quickstart/): TextEmbedding and the small English model.
- [FastEmbed and Qdrant local search](https://qdrant.tech/documentation/fastembed/fastembed-semantic-search/): local client, collection and query_points APIs.

The implementation explicitly embeds before insertion so the same vector-store path can be exercised with deterministic test embeddings and real local embeddings. Framework wiring and model downloads are provided infrastructure; the five named functions remain the learner's focused edit boundaries on `main`.
