import json

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from l1_lab.observability import LocalTelemetry, safe_attributes


def test_real_sdk_spans_have_parent_identity_and_measured_duration(tmp_path):
    memory = InMemorySpanExporter()
    path = tmp_path / "spans.jsonl"
    with LocalTelemetry(path, exporters=[memory]) as telemetry:
        with telemetry.span("application.start", run_id="run-001", adapter="offline"):
            with telemetry.span("workflow.step", run_id="run-001", step_id="step_0",
                                tool="retrieve_evidence", attempt=1, source_ids=["fact:python"]):
                pass
        assert telemetry.force_flush()
        spans = memory.get_finished_spans()
        assert len(spans) == 2
        child, parent = spans
        assert child.parent.span_id == parent.context.span_id
        assert child.context.trace_id == parent.context.trace_id
        assert child.end_time >= child.start_time
        assert child.status.status_code is StatusCode.OK
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["duration_ms"] >= 0
    assert rows[0]["attributes"]["source_ids"] == ["fact:python"]
    assert rows[0]["token_usage"] is None and rows[0]["cost"] is None


def test_exception_message_stack_and_request_content_are_not_recorded(tmp_path):
    memory = InMemorySpanExporter()
    path = tmp_path / "redacted.jsonl"
    with LocalTelemetry(path, exporters=[memory]) as telemetry:
        with pytest.raises(ValueError):
            with telemetry.span("rag.answer", query="private candidate email", token="sk-secret",
                                authorization="Bearer hidden", run_id="run-002"):
                raise ValueError("secret@example.com password sk-never-log-this")
        span = memory.get_finished_spans()[0]
        assert span.status.status_code is StatusCode.ERROR
        assert dict(span.attributes) == {"run_id": "run-002", "error_type": "ValueError"}
        assert span.events == ()
    serialized = path.read_text()
    for private in ("private candidate", "Bearer", "sk-secret", "secret@example", "password", "stacktrace"):
        assert private not in serialized
    assert json.loads(serialized)["attributes"]["error_type"] == "ValueError"


def test_exporter_filters_even_attributes_set_directly_on_sdk_span(tmp_path):
    path = tmp_path / "direct.jsonl"
    with LocalTelemetry(path) as telemetry:
        with telemetry.span("application.inspect", run_id="run-003") as span:
            span.set_attribute("raw_job", "private job content")
            span.set_attribute("authorization", "Bearer private-token")
    row = json.loads(path.read_text())
    assert row["attributes"] == {"run_id": "run-003"}
    assert "private" not in path.read_text()


def test_unknown_usage_stays_unknown_and_observed_tokens_are_labelled(tmp_path):
    path = tmp_path / "usage.jsonl"
    with LocalTelemetry(path) as telemetry:
        telemetry.record("rag.answer", input_tokens=10, output_tokens=5, cost_usd=.01)
        telemetry.record("rag.answer", usage_source="observed", input_tokens=10,
                         output_tokens=5, total_tokens=15, cost_usd=.01)
        telemetry.record("rag.answer", usage_source="estimate", input_tokens=4)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["token_usage"] is None and rows[0]["cost"] is None
    assert rows[1]["token_usage"] == {"usage_source": "observed", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    assert rows[1]["cost"] is None
    assert rows[2]["token_usage"]["usage_source"] == "estimate"


def test_metadata_allowlist_drops_malformed_or_secret_like_values():
    assert safe_attributes({"run_id": "Bearer secret", "model_id": "https://secret", "adapter": "sk-private",
                            "attempt": True, "tool": "shell", "status": "private free text",
                            "source_ids": ["fact:python", "secret@example.com"], "raw_query": "private"}) == {
                                "source_ids": ["fact:python"]}


def test_unknown_operation_rejected_before_recording(tmp_path):
    path = tmp_path / "unknown.jsonl"
    with LocalTelemetry(path) as telemetry:
        with pytest.raises(ValueError, match="unknown telemetry"):
            telemetry.record("query containing personal data")
    assert not path.exists()
