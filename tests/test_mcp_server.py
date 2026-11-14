"""Real protocol verification: official SDK client launches a child process."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest

from l1_lab.mcp_server import KnowledgeLookupArgs, RunInspectArgs


def _files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_stdio_discovery_invocation_rejection_and_read_only_state(tmp_path):
    directory = tmp_path / "runs"
    directory.mkdir()
    run = {"run_id": "mcp-demo", "status": "pending", "index": 3, "calls": 4, "max_calls": 8,
           "goal": "private goal secret@example.com", "plan": [{"payload": "never return this"}],
           "receipts": {"application": {"status": "VERIFIED", "payload": "private material"},
                        "delivery": {"status": "PENDING"}}, "trace": [{"message": "private trace"}]}
    (directory / "mcp-demo.json").write_text(json.dumps(run))
    before = _files(tmp_path)
    environment = {key: os.environ[key] for key in
                   ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE") if key in os.environ}
    environment["PYTHONPATH"] = os.pathsep.join(sys.path)
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "l1_lab.mcp_server", "--root", str(tmp_path)], env=environment)

    async def exercise():
        with anyio.fail_after(40):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    tools = {tool.name: tool for tool in listed.tools}
                    assert set(tools) == {"lab_knowledge_lookup", "lab_run_inspect"}
                    assert all(tool.annotations.readOnlyHint for tool in tools.values())
                    assert tools["lab_knowledge_lookup"].inputSchema["additionalProperties"] is False
                    assert tools["lab_knowledge_lookup"].inputSchema["properties"]["top_k"]["maximum"] == 5
                    lookup = await session.call_tool("lab_knowledge_lookup", {"query": "Python pytest unit tests", "top_k": 2})
                    assert not lookup.isError
                    knowledge = json.loads(lookup.content[0].text)
                    assert knowledge["source_kind"] == "synthetic"
                    assert knowledge["read_only"] is True and knowledge["hits"]
                    assert all(hit["source_ref"].startswith("synthetic:fixture:") for hit in knowledge["hits"])
                    inspected = await session.call_tool("lab_run_inspect", {"run_id": "mcp-demo"})
                    assert not inspected.isError
                    summary = json.loads(inspected.content[0].text)
                    assert summary["gate_status"] == {"application": "VERIFIED", "delivery": "PENDING"}
                    assert summary["calls"] == 4 and summary["trace_event_count"] == 1
                    for forbidden in ("private", "secret@example.com", "never return", "payload"):
                        assert forbidden not in inspected.content[0].text
                    for name, arguments in [
                        ("lab_knowledge_lookup", {"query": "Python", "top_k": True}),
                        ("lab_knowledge_lookup", {"query": "Python", "top_k": 6}),
                        ("lab_knowledge_lookup", {"query": " "}),
                        ("lab_knowledge_lookup", {"query": "Python", "sql": "DROP TABLE users"}),
                        ("lab_run_inspect", {"run_id": "../private"}),
                        ("lab_run_inspect", {"run_id": "mcp-demo", "path": "/etc/passwd"}),
                        ("lab_run_inspect", {"run_id": "not-found"}),
                        ("shell", {"command": "echo secret@example.com"}),
                    ]:
                        rejected = await session.call_tool(name, arguments)
                        assert rejected.isError, (name, arguments)
                        assert "secret@example.com" not in rejected.content[0].text
    asyncio.run(exercise())
    assert _files(tmp_path) == before


@pytest.mark.parametrize("value", [True, 0, 6, "2", None])
def test_lookup_argument_model_rejects_wrong_types_and_bounds(value):
    with pytest.raises(ValueError):
        KnowledgeLookupArgs(query="Python", top_k=value)


@pytest.mark.parametrize("value", ["../secret", "a/b", "a\\b", "", 12])
def test_run_identifier_is_not_an_arbitrary_path(value):
    with pytest.raises(ValueError):
        RunInspectArgs(run_id=value)
