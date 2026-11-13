"""Read-only, deliberately small Atlas snapshot contract; no connector credentials.

Only flattened, selected knowledge belongs here. The importer, not this module,
maps native Atlas payloads into text and preserves native provenance.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any


TABLES = {"Candidate_Facts", "Project_Registry"}
APPROVALS = {"APPROVED", "REVIEW_REQUIRED", "ARCHIVED", "REJECTED"}
REQUIRED = {
    "record_id", "record_version", "approval_status", "table", "source_ref",
    "source_version", "content_hash", "text", "snapshot_revision", "retrieved_at",
}
OPTIONAL = {"source_commit_sha", "metadata", "superseded", "export_text_hash"}
FORBIDDEN_KEYS = {
    "email", "phone", "contact", "contacts", "recipient", "recipients",
    "email_body", "body", "full_cv", "cv", "password", "token", "api_key",
    "credential", "credentials", "authorization", "cookies",
}


def _integer(value: Any, label: str, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")


def _no_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or set(re.split(r"[^a-z0-9]+", key.casefold())) & FORBIDDEN_KEYS:
                raise ValueError("snapshot contains a disallowed sensitive field")
            _no_sensitive_keys(child)
    elif isinstance(value, list):
        for child in value:
            _no_sensitive_keys(child)


def _validate_record(record: dict) -> None:
    if not isinstance(record, dict):
        raise ValueError("each record must be an object")
    if REQUIRED - record.keys() or record.keys() - REQUIRED - OPTIONAL:
        raise ValueError("record is missing provenance or has unknown fields")
    _no_sensitive_keys(record)
    _integer(record["record_version"], "record_version", 1)
    _integer(record["snapshot_revision"], "snapshot_revision")
    if record["table"] not in TABLES or record["approval_status"] not in APPROVALS:
        raise ValueError("invalid source table or approval status")
    for key in ("record_id", "source_ref", "source_version", "retrieved_at", "text"):
        if not isinstance(record[key], str) or not record[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if len(record["text"]) > 20_000 or len(record["record_id"]) > 256:
        raise ValueError("record exceeds lab limits")
    if any(ord(char) < 32 for char in record["record_id"]):
        raise ValueError("record_id contains control characters")
    if not isinstance(record["content_hash"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["content_hash"]):
        raise ValueError("content_hash must preserve the native SHA256 hex string")
    if not isinstance(record.get("metadata", {}), dict):
        raise ValueError("metadata must be an object")
    if "superseded" in record and not isinstance(record["superseded"], bool):
        raise ValueError("superseded must be Boolean")


def load_snapshot(path: str | Path) -> dict:
    """Read an envelope only. Selection is the separate M3 exercise.

    This never contacts Atlas. JSON error/schema failures are ValueError.
    Paths and private bytes stay on the caller's machine.
    """
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError("snapshot exceeds 5 MB lab limit")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object")
    if snapshot.get("schema_version") != 1 or isinstance(snapshot.get("schema_version"), bool):
        raise ValueError("unsupported snapshot schema_version")
    if snapshot.get("kind") not in {"synthetic", "atlas_snapshot"}:
        raise ValueError("kind must be synthetic or atlas_snapshot; live access is not implemented")
    _integer(snapshot.get("revision"), "revision")
    if not isinstance(snapshot.get("retrieved_at"), str) or not snapshot["retrieved_at"].strip():
        raise ValueError("retrieved_at is required")
    if not isinstance(snapshot.get("records"), list) or len(snapshot["records"]) > 500:
        raise ValueError("records must be a list of at most 500 items")
    return snapshot


class AtlasSnapshotSource:
    """A file source, not a live Atlas connection or continuous synchronizer."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> dict:
        return load_snapshot(self.path)


def select_records(snapshot: dict) -> list[dict]:
    """M3: Return latest eligible approved records, copied and sorted.

    Input is the flattened snapshot envelope. Validate every record's native
    provenance and snapshot revision. Equal ID/version duplicate bytes collapse;
    unequal duplicates fail. Choose the latest version BEFORE filtering approval
    or superseded status so a revocation cannot resurrect old evidence. Duplicate
    identity is (table,record_id). Preserve native content_hash and add a separate
    export_text_hash for selected text. Raise ValueError on malformed inputs.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("records"), list):
        raise ValueError("snapshot records must be a list")
    if snapshot.get("schema_version") != 1 or isinstance(snapshot.get("schema_version"), bool):
        raise ValueError("unsupported snapshot schema_version")
    if snapshot.get("kind") not in {"synthetic", "atlas_snapshot"}:
        raise ValueError("select only an explicit synthetic or atlas_snapshot envelope")
    _integer(snapshot.get("revision"), "revision")
    latest: dict[tuple[str, str], dict] = {}
    versions: dict[tuple[str, str, int], str] = {}
    for record in snapshot["records"]:
        _validate_record(record)
        if record["snapshot_revision"] != snapshot["revision"]:
            raise ValueError("mixed snapshot revisions; restart the source scan")
        identity = (record["table"], record["record_id"])
        version_key = (*identity, record["record_version"])
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if version_key in versions and versions[version_key] != canonical:
            raise ValueError("contradictory duplicate record version")
        versions[version_key] = canonical
        if identity not in latest or record["record_version"] > latest[identity]["record_version"]:
            latest[identity] = record
    selected = []
    for identity in sorted(latest):
        record = latest[identity]
        if record["approval_status"] != "APPROVED" or record.get("superseded", False):
            continue
        copy = deepcopy(record)
        copy["export_text_hash"] = hashlib.sha256(copy["text"].encode("utf-8")).hexdigest()
        copy.setdefault("metadata", {})
        selected.append(copy)
    return selected


def _text_parts(text: str, max_chars: int) -> list[str]:
    """Paragraph-aware splitting, then word boundaries; never discard text."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    parts: list[str] = []
    for paragraph in paragraphs:
        while len(paragraph) > max_chars:
            boundary = paragraph.rfind(" ", 0, max_chars + 1)
            if boundary < max_chars // 2:
                boundary = max_chars
            parts.append(paragraph[:boundary].strip())
            paragraph = paragraph[boundary:].strip()
        if paragraph:
            parts.append(paragraph)
    return parts


def chunk_records(records: list[dict], max_chars: int = 600) -> list[dict]:
    """M3: Create deterministic whole-paragraph/word chunks with full provenance.

    max_chars is a non-Boolean integer 40..4000. Each chunk is a copied record
    whose text is one bounded part; add chunk_id, chunk_index and chunk_text_hash.
    Native content_hash remains the source hash, never the new text hash. IDs
    change when record version or chunk text changes. Empty input returns [].
    Only approved, non-superseded records may be supplied. No input mutation.
    """
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    _integer(max_chars, "max_chars", 40)
    if max_chars > 4000:
        raise ValueError("max_chars must be <= 4000")
    chunks = []
    seen: set[str] = set()
    for record in records:
        _validate_record(record)
        if record["approval_status"] != "APPROVED" or record.get("superseded", False):
            raise ValueError("chunk only selected approved records")
        for index, text in enumerate(_text_parts(record["text"], max_chars)):
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            identity = json.dumps([record["table"], record["record_id"], record["record_version"], index, text_hash])
            chunk_id = "chunk:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
            if chunk_id in seen:
                raise ValueError("duplicate selected record would create duplicate chunks")
            seen.add(chunk_id)
            chunk = deepcopy(record)
            chunk.update(chunk_id=chunk_id, chunk_index=index, chunk_text_hash=text_hash, text=text)
            chunks.append(chunk)
    return chunks
