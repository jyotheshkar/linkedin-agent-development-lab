# LEARN: EVALUATION-01
# ROLE: Trace observable application execution with the real OpenTelemetry SDK.
# FLOW: Application span context -> SDK processor -> allowlisted local JSONL exporter.
# WHY: Timing and correlation are useful evidence; prompts, secrets and hidden reasoning are not telemetry.
# L1: Follow one parent/child span and run tests/test_observability.py.
# L2: Explain what local spans prove and what a remote collector or billing integration would still require.
# PYTHON: A context manager records success/error boundaries while preserving the original exception.
"""Small real OpenTelemetry SDK integration with a local, redacted exporter.

Spans describe observable execution boundaries, not private chain of thought.
The exporter independently filters attributes, names and exception metadata;
it never exports request text, model prompts, payloads or authentication data.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from threading import Lock
from typing import Iterator, Sequence

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status, StatusCode

OPERATIONS = frozenset({
    "application.start", "application.resume", "application.inspect", "rag.retrieve", "rag.answer",
    "workflow.step", "provider.execute", "provider.reconcile", "atlas.commit", "atlas.project",
    "approval.review", "evaluation.run", "mcp.lookup", "mcp.inspect",
})
TOOLS = frozenset({"retrieve_evidence", "draft", "sim_submit", "sim_outreach", "sim_store",
                   "sim_commit", "sim_deliver", "human_review", "knowledge_lookup", "run_inspect"})
SAFE_STATUSES = frozenset({
    "running", "awaiting_review", "pending", "blocked", "completed", "rejected", "approved",
    "ok", "error", "accepted", "verified", "reconciled", "failed", "started", "succeeded",
})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_./-]{0,127}\Z")
_ERROR_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")
_SECRET_PREFIXES = ("sk-", "bearer", "postgres:", "postgresql:", "http:", "https:")


def _identifier(value: object) -> str | None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return None
    if value.casefold().startswith(_SECRET_PREFIXES) or "@" in value:
        return None
    return value


def safe_attributes(metadata: dict) -> dict:
    """Retain only concise typed metadata; never stringify arbitrary objects.

    Identifiers are application-generated references, not a slot for user text.
    Unknown usage remains absent; observed or estimated token counts require
    an explicit usage_source label. Cost is deliberately not computed here.
    """
    result = {}
    for name in ("run_id", "step_id", "model_id", "adapter"):
        value = _identifier(metadata.get(name))
        if value is not None:
            result[name] = value
    tool = metadata.get("tool")
    if isinstance(tool, str) and tool in TOOLS:
        result["tool"] = tool
    status = metadata.get("status")
    if isinstance(status, str) and status.casefold() in SAFE_STATUSES:
        result["status"] = status.casefold()
    for name in ("attempt", "record_count", "case_count", "evidence_count"):
        value = metadata.get(name)
        if type(value) is int and 0 <= value <= 1_000_000:
            result[name] = value
    source_ids = metadata.get("source_ids")
    if isinstance(source_ids, (list, tuple)):
        selected = [item for value in source_ids[:32] if (item := _identifier(value)) is not None]
        if selected:
            result["source_ids"] = selected
    error_type = metadata.get("error_type")
    if isinstance(error_type, str) and _ERROR_TYPE.fullmatch(error_type):
        result["error_type"] = error_type
    usage_source = metadata.get("usage_source")
    if isinstance(usage_source, str) and usage_source in ("observed", "estimate"):
        result["usage_source"] = usage_source
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            value = metadata.get(name)
            if type(value) is int and 0 <= value <= 100_000_000:
                result[name] = value
    return result


def _utc(nanoseconds: int | None) -> str | None:
    return datetime.fromtimestamp(nanoseconds / 1e9, timezone.utc).isoformat() if nanoseconds is not None else None


class JSONLSpanExporter(SpanExporter):
    """Export real SDK spans without events, exception messages or resources.

    Local append-only JSONL is inspectable teaching evidence, not a hosted
    telemetry service or a cross-process transactional event ledger.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._closed = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._closed:
            return SpanExportResult.FAILURE
        rows = []
        for span in spans:
            context = span.context
            attributes = safe_attributes(dict(span.attributes or {}))
            duration_ms = ((span.end_time - span.start_time) / 1e6
                           if span.end_time is not None and span.start_time is not None else None)
            rows.append({
                "schema_version": 1, "integration": "opentelemetry-sdk",
                "operation": span.name if span.name in OPERATIONS else "lab.operation",
                "trace_id": f"{context.trace_id:032x}" if context else None,
                "span_id": f"{context.span_id:016x}" if context else None,
                "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
                "started_at": _utc(span.start_time), "ended_at": _utc(span.end_time),
                "duration_ms": duration_ms,
                "status": span.status.status_code.name,
                "attributes": attributes,
                "token_usage": ({name: attributes[name] for name in
                                 ("usage_source", "input_tokens", "output_tokens", "total_tokens")
                                 if name in attributes} if "usage_source" in attributes else None),
                "cost": None,
            })
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            return SpanExportResult.SUCCESS
        except (OSError, ValueError, TypeError):
            # Do not print a filesystem path, data value or provider exception.
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        self._closed = True

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return not self._closed


class LocalTelemetry:
    """Isolated TracerProvider; never replaces the process-global provider."""

    def __init__(self, path: str | Path | None = None, exporters: list[SpanExporter] | None = None):
        self.path = Path(path) if path is not None else None
        self.provider = TracerProvider(resource=Resource.create({"service.name": "linkedin-agent-development-lab"}))
        self.exporters = list(exporters or [])
        if self.path is not None:
            self.exporters.append(JSONLSpanExporter(self.path))
        for exporter in self.exporters:
            self.provider.add_span_processor(SimpleSpanProcessor(exporter))
        self.tracer = self.provider.get_tracer("l1_lab", "1.0")

    @contextmanager
    def span(self, operation: str, **metadata: object) -> Iterator[Span]:
        if operation not in OPERATIONS:
            raise ValueError("unknown telemetry operation")
        # Explicit flags prevent SDK default exception events from recording
        # messages or stack traces that could contain personal request content.
        with self.tracer.start_as_current_span(
            operation, attributes=safe_attributes(metadata), record_exception=False,
            set_status_on_exception=False,
        ) as span:
            try:
                yield span
            except BaseException as exc:
                span.set_attribute("error_type", type(exc).__name__)
                span.set_status(Status(StatusCode.ERROR))
                raise
            else:
                if span.status.status_code is StatusCode.UNSET:
                    span.set_status(Status(StatusCode.OK))

    def record(self, operation: str, **metadata: object) -> None:
        """Record one observable event as a measured zero-work SDK span."""
        with self.span(operation, **metadata):
            pass

    def force_flush(self) -> bool:
        return self.provider.force_flush()

    def close(self) -> None:
        self.provider.shutdown()

    def __enter__(self) -> "LocalTelemetry":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
