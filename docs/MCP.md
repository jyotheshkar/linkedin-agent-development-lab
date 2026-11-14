# Read-only MCP and local OpenTelemetry

The lab includes a small genuine local Model Context Protocol server and a real
OpenTelemetry SDK integration. They are inspectable learning components, not
production Atlas endpoints, hosted monitoring, or hidden model reasoning.
See the current verification report for the commands and results actually run.

## Local protocol boundary

`src/l1_lab/mcp_server.py` uses the official MCP Python SDK, with the supported
1.x compatibility line explicitly bounded below version 2 in the dependency
lock. The SDK's current stable major is 2; the official 1.x documentation
describes its maintained compatibility line. The lab does not silently assume
that examples from the two major versions share imports and handler contracts.
The exact resolved version belongs in the lock and verification report.

| Tool | Input | Output | Boundary |
| --- | --- | --- | --- |
| `lab_knowledge_lookup` | Visible query up to 500 characters; strict integer `top_k` from 1 to 5 | Bounded retrieved chunks with source/version/hash/score | Bundled approved synthetic fixture only; offline hash vectors; no generation |
| `lab_run_inspect` | Existing local run ID, at most 100 letters/digits/underscores/hyphens | Run status, call counts, gate statuses and trace-event count | Owner-configured journal root only; no raw goal, payload, artifacts, trace text or secrets |

Tool discovery returns their JSON Schemas and read-only annotations. Pydantic
checks the same contracts at invocation, rejects unknown arguments and does not
coerce Boolean values into integers. A caller cannot pass SQL, a shell command,
a snapshot filename, a model mode, a private-data option or a root path as tool
authority. Unknown tools and malformed arguments produce bounded errors without
echoing raw inputs. A tool annotation is descriptive metadata; the narrow code
and tests enforce the actual boundary.

The owner selects the lab journal root when launching the process. The tool
receives an ID rather than a path, checks the resolved path stays under `runs/`,
and bounds the file size. It does not instantiate the application service to
read a run, so a lookup cannot accidentally seed a database, repair a projection
or submit a simulated effect. Knowledge lookup uses `RAGService` with an
immutable in-memory synthetic index and cannot switch to a private snapshot.

Launch from the repository root after the locked environment is installed:

```bash
uv run python -m l1_lab.mcp_server --root .lab
```

The process waits for an MCP client on standard input/output; it is not a normal
interactive terminal command. Standard output is the SDK's JSON-RPC wire and
must not receive `print` logging. There is no listener port or remotely hosted
endpoint. The local child process and its owner inherit the filesystem trust
boundary; this is not a multi-user security boundary or a remote auth scheme.

The automated protocol exercise is the shortest reproducible client:

```bash
uv run pytest tests/test_mcp_server.py -q
```

It launches a child Python process through the official `stdio_client`, opens
an official `ClientSession`, initializes the connection, lists tools, inspects
their schemas, calls both tools, and checks malformed/unknown calls are rejected.
It compares existing local file hashes before and after the session. A direct
Python helper invocation is not counted as protocol verification. A missing SDK
or unexecuted child-process test leaves protocol verification unverified.

The run reader expects the lab's existing JSON journal layout, `ROOT/runs/ID.json`.
Choose the same root used by the workflow. It does not expose database connection
strings or a query tool for the optional Postgres deployment backend. Extending
it to another store requires a separately designed read-only interface and
protocol tests, rather than adding arbitrary paths or SQL arguments.

## Real SDK spans without a dashboard account

`src/l1_lab/observability.py` creates an isolated OpenTelemetry `TracerProvider`,
uses `SimpleSpanProcessor`, and exports real ended SDK spans to local JSONL.
The application may also attach the SDK's in-memory exporter for tests. It does
not replace the process-global provider or send telemetry to an external service.

```python
from l1_lab.observability import LocalTelemetry

with LocalTelemetry(".lab/otel-spans.jsonl") as telemetry:
    with telemetry.span("application.start", run_id="run-example", adapter="offline"):
        # Existing application work goes here; no private request text as metadata.
        telemetry.record("workflow.step", run_id="run-example", step_id="step_0",
                         tool="retrieve_evidence", status="accepted", attempt=1,
                         source_ids=["fact:python"])
```

The JSONL exporter records SDK trace/span/parent IDs, start/end timestamps,
measured duration, status, adapter/tool identifiers, attempts and selected source
IDs. A `record` call is a measured zero-work span representing an observable
event; wrap the actual operation in `span` to measure its execution duration.
The nested SDK context creates parent/child correlation automatically.

The metadata contract is an explicit allowlist. Unknown fields are discarded;
request text, prompts, job descriptions, artifacts, authentication headers,
DSNs and arbitrary exception messages are not telemetry fields. Do not disguise
private content as an identifier. The exporter re-applies the allowlist even
if code directly adds an attribute to the SDK span. Exception recording is
disabled at the SDK context boundary; on failure the wrapper records only the
exception class and error status, then re-raises the original exception. It
exports no exception event, stack trace, source payload or hidden reasoning.

Usage stays unknown (`null`) unless the caller explicitly supplies observed
token counts or a labelled estimate. Estimated counts remain labelled
`estimate`; they are not provider billing. Cost stays unknown because this
integration has no observed billing plus dated pricing contract. A demo trace
does not establish production adoption, business value or a live model call.

```bash
uv run pytest tests/test_observability.py -q
```

Tests use the real SDK in-memory exporter to check parent correlation, measured
durations and error status, and inspect JSONL for secret/message exclusion and
unknown usage. Local JSONL is teaching evidence, not a transactional multi-process
event ledger. The Atlas Lab ledger and provider receipts retain their separate
business-evidence responsibilities. No remote OTLP collector or paid tracing
dashboard has been configured or verified by this local integration.

## Primary implementation references

- [Official MCP Python SDK 1.x documentation](https://py.sdk.modelcontextprotocol.io/v1/)
- [Official SDK maintained-line README](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/README.md)
- [MCP transport specification](https://modelcontextprotocol.io/specification/latest/basic/transports)
- [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/)

These references informed implementation. Passing the protocol/tracing tests
verifies the stated local paths, not an external production integration.
