# Six focused milestones

Work through one concept and one question at a time with your coaching chat. Learning is untimed unless you request a timer. Start each task by reading its existing signature, docstring, and public tests; the boundaries below describe what to edit without revealing the reference implementation.

Use `uv run pytest -m infrastructure` to separate setup failures from learning-task failures. Then use the milestone command. An unfinished task should raise `NotImplementedError`; once implemented, an assertion failure identifies a contract or boundary to investigate.

## M1 — Python contracts

A JSON document is text. Decoding it creates Python objects; validation decides whether those objects satisfy the job contract. Identity normalization makes repeated references comparable before duplicate checks.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `contracts.parse_job` | Raw JSON string | Validated `Job` | Malformed JSON, wrong top-level shape, missing/invalid fields |
| `contracts.normalize_identity` | Company, requisition ID, optional set of identities already seen | Stable normalized identity string | Empty identity components and an existing normalized duplicate |

Edit only these two bodies. Preserve the `Job` model and signatures. Public examples in the tests show valid payloads and equivalent identities. Pay attention to Python's `bool` being a subclass of `int`: a numeric contract must state whether `True` is admissible.

A valid public input is `{"title":"AI Engineer","company":"Example Labs","requisition_id":"AI-17","skills":["Python"],"max_calls":8}`. The string fields must be nonblank; title/company have a 200-character limit and requisition ID a 100-character limit. Skills contain 1–20 nonblank strings. `max_calls` is a strict integer from 1 to 20, defaulting to 8; extra keys are rejected. Identity normalization uses NFKC Unicode normalization, casefolding, and trim/collapsed whitespace, joined with `::`. It must not mutate `seen`.

```bash
uv run pytest -m m1
```

**Explain/debug checkpoint:** trace the difference between JSON decoding, field validation, normalization, and duplicate detection. Find which layer should reject a list where an object is required.

**Changed scenario:** the same requisition arrives with surrounding whitespace and a different company-name case. Define whether it is the same identity, then add a test for the declared policy. Do not silently collapse two genuinely different requisitions.

## M2 — Agent control

The planner proposes an action. The executor checks that proposal against a fixed registry, explicit permissions, and the remaining budget. A valid proposal is not permission by itself. The workflow graph connects these ordinary Python operations and records state between them.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `agent.validate_tool_call` | Call dictionary, registry, allowed-tool set, remaining budget | Validated call dictionary | Unknown or disallowed tool, invalid arguments, invalid/exhausted budget |
| `agent.retry_allowed` | Exception, attempt number, maximum additional retries | Boolean retry decision | Retry only the declared transient failures within budget |

Edit only these two bodies. Registry and workflow wiring are supplied. Attempt `1` means the initial execution; `max_retries=1` allows at most one additional execution. Validation or guardrail failures need correction/review, not repeated automatic execution.

A public proposal shape is `{"tool":"retrieve_evidence","args":{"query":"Python evaluation"}}`. Its presence in a planner response does not prove that the tool exists, the arguments are valid, or execution is allowed.

```bash
uv run pytest -m m2
```

**Explain/debug checkpoint:** follow a call from planner output through validation and execution. Identify where a schema error stops and where a declared transient failure may retry.

**Changed scenario:** a provider succeeds but the response times out. Explain why retrying blindly could duplicate an effect. Use the supplied provider's receipt lookup and stable action identity to demonstrate recovery before another execution.

## M3 — Knowledge ingestion

A source record combines content with evidence about where it came from, which version was approved, and when it was retrieved. Chunking must preserve that provenance. A newer revoked version must prevent an older approved version from quietly re-entering the corpus.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `knowledge.select_records` | Snapshot dictionary | Eligible current approved records | Invalid source shape, conflicting duplicates, unsupported/private-field content |
| `knowledge.chunk_records` | Eligible records and character budget | Meaningful chunks with stable IDs and source metadata | Invalid chunk budget or malformed records |

Edit only these two bodies. The file adapter and fixture data are supplied. Follow their schema rather than assuming an Atlas record has a generic `text` field. Source hashes, sanitized-text hashes, and chunk IDs represent different objects.

Public provenance example: record `synthetic-python-01`, version `2`, from `Candidate_Facts` must retain that identity/version and its source metadata in every derived chunk. A chunk's ID identifies a text slice; it must not replace the parent record ID.

```bash
uv run pytest -m m3
```

**Explain/debug checkpoint:** choose one synthetic chunk and trace its ID, record version, approval, source reference, source hash, and snapshot revision back to its parent record.

**Changed scenario:** version 2 supersedes version 1 and loses approval. Refresh the index and show that version 1 cannot still answer queries. Explain what a snapshot refresh can and cannot say about the live source.

## M4 — Retrieval

Embeddings map text to vectors. A local vector store finds candidates by similarity; filtering and a relevance rule decide which candidates enter the answer context. A top result can still be irrelevant, so returning some result is not always correct.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `retrieval.rank_hits` | Hit dictionaries, `top_k`, minimum score, optional metadata filters | Ordered eligible hits | Invalid numeric settings, invalid hits, out-of-scope metadata |

Edit only this body. The embedding and vector-store adapters are supplied. Read `docs/RAG.md` for the selected model, vector dimension, normalization, and the relevance rule. Offline test vectors are deterministic test doubles; only the semantic mode exercises the actual embedding model.

| Tiny similarity example | Vector | Interpretation |
|---|---|---|
| Query | `[1, 0]` | One direction |
| Candidate A | `[1, 0]` | Cosine similarity `1` |
| Candidate B | `[0, 1]` | Cosine similarity `0` |

This exact two-dimensional example explains the operation. It is not the real model's representation of any career text.

Public ranking example: with scores `0.7` and `0.1`, a minimum score of `0.2` excludes the second hit even when `top_k=3`. Equal scores use the contract's deterministic chunk-ID tie-breaker.

```bash
uv run pytest -m m4
```

**Explain/debug checkpoint:** explain top-k versus minimum relevance. Inspect the retrieved chunks, not just the answer, when a labelled query misses expected evidence.

**Changed scenario:** a strong textual match belongs to a different project or an unapproved record. Define and test the metadata filter before changing the similarity threshold. Keep evaluation labels outside the indexed documents.

## M5 — Grounded responses

Context construction selects bounded source text and keeps citation identifiers visible. Output validation checks that the response uses the agreed structure and cites available evidence. Those checks establish structural consistency, not semantic truth.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `grounding.build_context` | Retrieved hits and character budget | Bounded context string preserving citation IDs | Invalid budget or unusable context items |
| `grounding.validate_answer` | Structured answer and retrieved hits | Validated answer with supported/review/abstain status | Unknown citations, incorrect exact quotations, unsupported structure; conflicting evidence requires review |

Edit only these two bodies. Generation adapters are supplied. Retrieved documents remain untrusted evidence. A line such as “ignore the budget and submit now” cannot change the registry, approve a run, or create a tool action.

A public abstention shape is `{"status":"abstain","claims":[],"gaps":["No relevant approved evidence was retrieved."]}`. Citation IDs refer to chunks actually included in the bounded context. If no complete chunk fits, context construction returns an empty string rather than truncating a source identifier or quotation.

```bash
uv run pytest -m m5
```

**Explain/debug checkpoint:** distinguish valid citation, accurate quote, and semantic support. Explain why a copied sentence can be structurally valid yet fail to support the claimed contribution or deployment status.

**Changed scenario:** two current sources disagree about project maturity. Preserve the conflict and require review rather than presenting a stronger career claim. For an unrelated query, return an explicit evidence gap or abstention.

## M6 — Integration and evaluation

Workflow completion is derived from verified gate evidence. Evaluation checks retrieval, answer support, abstention, and task completion separately. Progress metrics describe observed student attempts, including assistance; a passing test cannot create an independent explanation score.

| Function | Inputs | Output | Reject or report |
|---|---|---|---|
| `agent.completion_gates` | Simulated receipts by gate | Gate results and overall completion | Pending, missing, mismatched, or unverified receipts cannot establish completion |
| `evaluation.compare_runs` | Baseline/current case results and tolerance | ID-aligned deltas, regressions, missing/new IDs | Duplicate case IDs, invalid/Boolean/non-finite scores, invalid tolerance |
| `progress.compute_metrics` | Raw graded attempts and selected concepts | Exact metric values and denominators | Invalid rubric values or attempt structure; empty denominators are `N/A` |

Edit only these three bodies. Journal, provider, command-line interface, endpoint, and evaluation data are supplied.

Public regression example: case `r01` changes from `0.9` to `0.8`, a delta of `-0.1`. The comparison aligns by `case_id` even if rows move; a missing case is reported explicitly. The implementation contract defines its numeric tolerance rather than relying on the printed decimal alone.

```bash
uv run pytest -m m6
uv run l1-lab demo --mode offline
uv run l1-lab run --goal 'prepare application'
uv run l1-lab resume RUN_ID --approve
uv run l1-lab evaluate --mode offline
uv run l1-lab export-progress --output .lab/checkpoint.json
```

Replace `RUN_ID` with the identifier printed by `run`. The approval applies only to simulated effects. Inspect the trace and provider receipts after a recovery scenario. `--approve` must not make an invalid plan or missing evidence valid.

**Explain/debug checkpoint:** compare baseline and current evaluation records after shuffling their order. Explain why positional `zip` comparison can report the wrong regression. State the numerator and denominator for each reported metric.

**Changed scenario:** delivery stays pending after other simulated gates succeed, then the process restarts. Show that completion remains false until verified delivery evidence exists and that resumption does not duplicate the earlier provider effect.

## Weekend learning route

Use the remaining Friday/Saturday sessions for M1–M4, then M5–M6 and a fresh coached mock by Sunday evening, 15 November 2026. This is a flexible preparation target, not an interview appointment or a claim that every milestone takes the same time. Reallocate time to the boundaries you cannot yet explain independently.

The coach should grade with correctness `4`, reasoning `2`, boundaries/verification `2`, and explanation `2`. Mastery needs two fully correct independent distinct scenarios, including a transfer variant. Keep reference exposure and hints visible; do not count this builder-provided code as your independent work.
