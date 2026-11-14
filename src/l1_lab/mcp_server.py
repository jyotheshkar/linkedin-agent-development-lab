# LEARN: DELIVERY-01
# ROLE: Expose a tiny read-only interface through the actual local MCP protocol.
# FLOW: SDK stdio client -> advertised schema -> strict validation -> bounded synthetic read.
# WHY: A Python function alone is not protocol discovery, framing or invocation evidence.
# L1: Trace one tools/call request and run tests/test_mcp_server.py.
# L2: Defend the difference between local process trust and a remotely authenticated service.
# PYTHON: Nested async handlers close over the owner-selected root without accepting caller paths.
"""Read-only local MCP exercise using the official Python SDK v1 protocol path.

Only bundled synthetic knowledge and a bounded run-summary reader are exposed.
There is no SQL, shell, arbitrary file, provider effect or Atlas-write tool.
stdout belongs exclusively to the SDK's stdio JSON-RPC transport.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp import types
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError


class KnowledgeLookupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: StrictStr = Field(min_length=1, max_length=500, description="Search text over bundled synthetic approved evidence only")
    top_k: StrictInt = Field(default=3, ge=1, le=5, description="Maximum retrieved chunks, from one to five")


class RunInspectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: StrictStr = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$",
                             description="Existing local lab run identifier, never a path")


def _knowledge_lookup(request: KnowledgeLookupArgs) -> dict:
    if not request.query.strip():
        raise ValueError("query must contain visible text")
    # The fixed fixture is deliberate. Neither tool parameters nor environment
    # variables can substitute a private Atlas snapshot or turn on a live model.
    from .service import FIXTURE, RAGService
    from .deploy_retrieval import ImmutableVectorIndex

    rag = RAGService(FIXTURE, mode="offline", generation="offline", index_factory=ImmutableVectorIndex)
    try:
        if rag.snapshot.get("kind") != "synthetic":
            raise ValueError("MCP lookup requires the bundled synthetic fixture")
        hits = rag.index.search(request.query, top_k=request.top_k, min_score=.3)
        fields = ("chunk_id", "record_id", "record_version", "source_ref", "source_version",
                  "content_hash", "snapshot_revision", "score", "text")
        return {"source_kind": "synthetic", "mode": "offline-hash-vectors", "read_only": True,
                "generation": "none", "hits": [{key: hit[key] for key in fields if key in hit} for hit in hits]}
    finally:
        rag.close()


def _run_inspect(root: Path, request: RunInspectArgs) -> dict:
    """Read bounded execution fields without constructing a mutating service.

    A command-line owner chooses the journal root at server startup. Tool
    callers choose an ID only; symlinks/traversal cannot escape that root.
    Raw goal, request payload, artifact bodies and trace text are not returned.
    """
    directory = (root / "runs").resolve()
    path = (directory / f"{request.run_id}.json").resolve()
    if path.parent != directory or not path.is_file():
        raise ValueError("run not found")
    if path.stat().st_size > 2_000_000:
        raise ValueError("run exceeds read-only inspection limit")
    run = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(run, dict) or run.get("run_id") != request.run_id:
        raise ValueError("invalid run record")
    status = run.get("status")
    if status not in {"running", "awaiting_review", "pending", "blocked", "completed", "rejected"}:
        raise ValueError("invalid run status")
    summary = {"run_id": request.run_id, "status": status, "read_only": True,
               "effects": "simulated", "gate_status": {}, "trace_event_count": 0}
    for field in ("index", "calls", "max_calls"):
        value = run.get(field)
        if type(value) is int and 0 <= value <= 1_000_000:
            summary[field] = value
    receipts = run.get("receipts", {})
    if isinstance(receipts, dict):
        for gate in ("application", "outreach", "storage", "commit", "delivery"):
            receipt = receipts.get(gate)
            if isinstance(receipt, dict) and receipt.get("status") in ("VERIFIED", "PENDING"):
                summary["gate_status"][gate] = receipt["status"]
    trace = run.get("trace", [])
    if isinstance(trace, list):
        summary["trace_event_count"] = len(trace)
    return summary


def create_server(root: str | Path = ".lab") -> Server:
    """Construct the two-tool server without creating a database or run."""
    root = Path(root)
    server = Server("linkedin-agent-development-lab-readonly")
    annotations = types.ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                        idempotentHint=True, openWorldHint=False)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(name="lab_knowledge_lookup", description="Retrieve approved bundled synthetic evidence; offline and read-only; no private snapshot access",
                       inputSchema=KnowledgeLookupArgs.model_json_schema(), annotations=annotations),
            types.Tool(name="lab_run_inspect", description="Inspect an existing local simulated run's allowlisted status/count/gate summary; no raw payloads or writes",
                       inputSchema=RunInspectArgs.model_json_schema(), annotations=annotations),
        ]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
        # Manual Pydantic validation retains the advertised strict schema while
        # replacing raw validation dumps with a safe, bounded error message.
        try:
            if name == "lab_knowledge_lookup":
                result = _knowledge_lookup(KnowledgeLookupArgs.model_validate(arguments))
            elif name == "lab_run_inspect":
                result = _run_inspect(root, RunInspectArgs.model_validate(arguments))
            else:
                return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text="Unknown read-only lab tool")])
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, allow_nan=False))])
        except (ValidationError, ValueError, OSError, KeyError, TypeError):
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text="Invalid arguments or unavailable local synthetic lab data")])

    return server


async def _serve(root: Path) -> None:
    server = create_server(root)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Local read-only MCP exercise; stdio protocol only")
    parser.add_argument("--root", type=Path, default=Path(".lab"), help="Owner-selected existing lab root containing runs/")
    args = parser.parse_args(argv)
    asyncio.run(_serve(args.root))


if __name__ == "__main__":
    main()
