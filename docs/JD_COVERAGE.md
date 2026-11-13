# Role evidence and lab coverage

This lab is aligned with the recruiter-provided **Capgemini AI Engineer,
Engineering Augmentation** role. The source is attachment
`AI-Engineer-JD-2026-10-15.html` in Gmail message `1a1a0ca9d338a22d`, preserved in
the installed AIE `references/jd-source.md`. The packaged role/evidence and
coaching protocol were read for this build. They are source snapshots, not
evidence of an official interview agenda or of current employment terms.

The newer 13 November user report says the recruiter confirmed assessment
clearance and progression to L1. It supersedes the older packaged
clearance-unknown note. Interview date, format and official score remain
unknown. L1 implementation emphasis is a preparation choice, not a confirmed
employer rubric. No prior guided practice result is imported as independent
competence.

## Exact coverage map

| Role requirement, paraphrased from the JD | Existing evidence or concept reused | Newly built learning surface | Remaining evidence or gap |
| --- | --- | --- | --- |
| Clean Python, environments, packaging and pytest | Archived assisted agent/RAG practice; installed LinkedIn validators inspected as source | `contracts.py`, focused task bodies, `pyproject.toml`, lock and milestone tests | Learner must implement, explain and test independent changes; a builder/reference test pass is different evidence |
| REST APIs, JSON, authentication and errors | Existing project architecture is context, not a claim of personal production API ownership | FastAPI request contracts, bearer boundary, local CLI/browser integration and rejection tests | Verify cloud access controls and secret handling on the actual deployment; the lab token is not full multi-user identity |
| Tools, structured LLM outputs and prompt design | Archived agent tool-routing exercise and inspected workflow concepts | `OpenAIPlanner`, `OpenAIAnswerGenerator`, schema checks and the shared deterministic executor path | Contract tests with fakes do not verify live planning or generation; report each actual provider run separately |
| At least one framework and common workflow patterns | Existing private LinkedIn workflow is a project anchor; its installed helpers are validators/planners, not proof of autonomous provider execution | Thin LangGraph plan/execute graph with explicit Python state, distinct fixture plans and review pause | Explain why the graph is useful and when a script suffices; no need to claim all named frameworks are implemented |
| Human approval and safe failure | LinkedIn/Atlas concepts: completion gates, pending events and recovery | Immutable reviewed-plan identity, declared retries, validation failures and simulated effect review | Demonstrate fresh failure/recovery variants; simulation is not a live employer authorization system |
| RAG chunking, embeddings and vector queries | Approved selected Atlas facts/project metadata are a private read-only snapshot; RAG was not asserted to exist in inspected LinkedIn helpers | Provenance-preserving ingestion/chunks, offline hash vectors, optional FastEmbed/Qdrant semantic lab, retrieval manifest and filters | A snapshot is not live synchronization; hash vectors are not semantic embeddings; a model download/test requires its own observed result |
| Context and token limits | AIE explanation/verification discipline | Whole-chunk context budget and citation IDs in `grounding.py` | The budget counts characters; provider token accounting and actual model limits require additional checks |
| Evaluation before release and output testing | Archived RAG practice distinguished lexical overlap from semantic truth | Separate retrieval/citation/extractive-support/abstention metrics; stable case-ID regression comparison | Small developer-labelled cases are not an expert truth set; output membership and quotation do not prove entailment |
| Tracing, telemetry, usage, cost and adoption | Atlas provenance and event-evidence concepts | Run/step/tool/status/attempt/source-ID trace events and measured elapsed execution times | No production adoption data, full telemetry platform or observed provider billing; unknown token/cost fields remain absent or null |
| Git, CI/CD and Docker working knowledge | Existing GitHub portfolio is context; authorship and deployment need separate evidence | Student/reference branches, labelled Actions workflow, dev-container configuration and release gate | A host-local run is not a Codespaces/container/Actions pass; actual cloud receipts must be observed |
| Troubleshooting and feedback-driven improvement | User-supplied Amazon evaluation and failure-analysis experience, kept separate from engineering claims | Failure injection, receipt reconciliation, concurrent/durable-state delivery exercises and changed scenarios | Learner explains a concrete observed failure and correction; do not invent scale, savings, production ownership or teamwork outcomes |
| MCP awareness and exposing an agent tool | Connected ChatGPT plugins supplied source context during the build | Delivery review and original question comparing the Python registry with an MCP interface | This lab does not implement an MCP server; discovery, schemas, transport and authenticated access remain an explanation/extension topic |
| AI risks, injection, validation and sensitive data | Approved-claim boundaries and conservative project wording | Injection fixture, untrusted-context envelope, structural output checks and excluded private corpus/state | String/structural tests are bounded controls, not a security certification or a semantic safety guarantee |
| Walk through a substantial application, its tests and failures | Real Amazon evaluation, assisted historical code and verified portfolio work remain distinct | End-to-end synthetic project plus original code-linked interview prompts | Only observed learner explanations, changes, tests and transfer support independent competence |

## New cloud delivery extension

Postgres-backed state, run locking and Vercel packaging are delivery exercises
added to this lab. The JD asks for basic delivery practices; it does not mandate
Vercel, Postgres or a particular cloud architecture. Local journal/SQLite
mechanisms and the optional cloud Postgres backend should be explained as
different deployment contracts. A migration file or adapter implementation is
not evidence of a provisioned database, an executed real-database test, or a live
deployment. See `VERCEL_DELIVERY.md` and the build report for the precise release
sequence and observed verification.

## AIE-informed practice without fabricated scoring

`data/interview_questions.json` contains sixteen original code-linked prompts,
including changed scenarios. It stores question IDs, topic/mode, required-point
categories, code symbols and optional hints; it contains no answer key. The
browser displays one prompt at a time and exports raw ungraded drafts with
assistance information. Those drafts do not become scored attempts simply by
being submitted or downloaded.

A coach can later grade an observed answer using correctness 4, reasoning 2,
boundaries/verification 2 and explanation 2. Every graded attempt requires an
explicit assistance declaration. Two independent fully correct distinct
scenarios, including transfer, are required for the lab's mastery label; a later
critical misconception resets that evidence. Missing denominators remain N/A.
These are transparent practice measures, not employer pass thresholds or hiring
probabilities. The final mock uses fresh questions later, and learning is
untimed unless requested.

The packaged AIE sources informed the content at build time. The runtime app
does not invoke AIE, append to its static package, write Minister learning or
update operational Atlas records. Portable exports enable a later coaching chat
to review the learner's evidence explicitly.
