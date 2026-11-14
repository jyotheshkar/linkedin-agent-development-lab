"""Isolated Atlas Lab: immutable knowledge, artifact bytes and receipt evidence.

@concept The SQLite database is authoritative; RAG snapshots and the dashboard
are derived views. This module never connects to operational Atlas or employers.
@invariant Imported real records are observations, not locally issued approvals.
@invariant Provider receipts remain independent of this event ledger. Repairing
logging or projection must reuse them instead of repeating simulated effects.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from .knowledge import APPROVALS, TABLES, _no_sensitive_keys, _validate_record
from .provider import FakeProvider


class VersionConflict(ValueError):
    """The caller reviewed or edited a version that is no longer current."""


class ReadOnlySource(ValueError):
    """A real source import cannot be changed or approved by this lab."""


class IntegrityError(ValueError):
    """Stored immutable bytes or evidence do not match their declared identity."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS lab_meta(key TEXT PRIMARY KEY,value INTEGER NOT NULL);
INSERT OR IGNORE INTO lab_meta VALUES('schema_version',1);
INSERT OR IGNORE INTO lab_meta VALUES('knowledge_revision',0);
INSERT OR IGNORE INTO lab_meta VALUES('ledger_revision',0);
CREATE TABLE IF NOT EXISTS knowledge_imports(
 import_id TEXT PRIMARY KEY,kind TEXT NOT NULL,source_revision INTEGER NOT NULL,
 retrieved_at TEXT NOT NULL,envelope_hash TEXT NOT NULL,envelope_json TEXT NOT NULL,
 created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_versions(
 version_id TEXT PRIMARY KEY,origin TEXT NOT NULL,table_name TEXT NOT NULL,
 record_id TEXT NOT NULL,record_version INTEGER NOT NULL,semantic_hash TEXT NOT NULL,
 record_json TEXT NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(origin,table_name,record_id,record_version));
CREATE TABLE IF NOT EXISTS knowledge_current(
 table_name TEXT NOT NULL,record_id TEXT NOT NULL,version_id TEXT NOT NULL,
 observed_json TEXT NOT NULL,import_id TEXT,
 PRIMARY KEY(table_name,record_id),
 FOREIGN KEY(version_id) REFERENCES knowledge_versions(version_id),
 FOREIGN KEY(import_id) REFERENCES knowledge_imports(import_id));
CREATE TABLE IF NOT EXISTS lab_runs(run_id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(
 artifact_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,kind TEXT NOT NULL,version INTEGER NOT NULL,
 digest TEXT NOT NULL,content_type TEXT NOT NULL,byte_size INTEGER NOT NULL,
 metadata_json TEXT NOT NULL,metadata_hash TEXT NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(run_id,kind,version),UNIQUE(run_id,kind,digest,metadata_hash),
 FOREIGN KEY(run_id) REFERENCES lab_runs(run_id));
CREATE INDEX IF NOT EXISTS artifact_digest ON artifacts(digest);
CREATE TABLE IF NOT EXISTS event_ledger(
 event_id TEXT PRIMARY KEY,event_revision INTEGER NOT NULL UNIQUE,run_id TEXT NOT NULL,
 gate TEXT NOT NULL,idempotency_key TEXT NOT NULL,status TEXT NOT NULL,
 receipt_json TEXT NOT NULL,payload_json TEXT NOT NULL,payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,UNIQUE(run_id,gate,idempotency_key,status),
 FOREIGN KEY(run_id) REFERENCES lab_runs(run_id));
CREATE TABLE IF NOT EXISTS event_artifacts(
 event_id TEXT NOT NULL,artifact_id TEXT NOT NULL,PRIMARY KEY(event_id,artifact_id),
 FOREIGN KEY(event_id) REFERENCES event_ledger(event_id),
 FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id));
CREATE TABLE IF NOT EXISTS action_approvals(
 approval_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,plan_hash TEXT NOT NULL,
 decision TEXT NOT NULL,manifest_json TEXT NOT NULL,manifest_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES lab_runs(run_id));
CREATE TABLE IF NOT EXISTS reporting_projection(
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,
 payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        raise ValueError("Atlas Lab accepts finite JSON values only") from None


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _identifier(value, label="identifier") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError(f"invalid {label}")
    return value


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")


def _semantic(record: dict) -> str:
    # Retrieval observations can refresh without rewriting a source version.
    return _hash({k: v for k, v in record.items() if k not in {
        "snapshot_revision", "retrieved_at", "export_text_hash"}})


class AtlasLab:
    """Transactional local store; ``root`` is a directory or SQLite file path."""

    def __init__(self, root: Path | str):
        root = Path(root)
        self.path = root if root.suffix in {".sqlite3", ".sqlite", ".db"} else root / "atlas.sqlite3"
        self.root = self.path.parent
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifact_root = self.root / "artifacts"
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)
            if db.execute("SELECT value FROM lab_meta WHERE key='schema_version'").fetchone()[0] != 1:
                raise ValueError("unsupported Atlas Lab database schema")
            db.commit()
        finally:
            db.close()

    @contextmanager
    def _connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _revision(db, key):
        return db.execute("SELECT value FROM lab_meta WHERE key=?", (key,)).fetchone()[0]

    @staticmethod
    def _advance(db, key):
        db.execute("UPDATE lab_meta SET value=value+1 WHERE key=?", (key,))
        return AtlasLab._revision(db, key)

    @staticmethod
    def _run(db, run_id):
        _identifier(run_id, "run ID")
        db.execute("INSERT OR IGNORE INTO lab_runs VALUES(?,?)", (run_id, _now()))

    @staticmethod
    def _insert_version(db, record, origin):
        existing = db.execute(
            "SELECT version_id,semantic_hash FROM knowledge_versions WHERE origin=? AND table_name=? AND record_id=? AND record_version=?",
            (origin, record["table"], record["record_id"], record["record_version"])).fetchone()
        semantic_hash = _semantic(record)
        if existing:
            if existing["semantic_hash"] != semantic_hash:
                raise VersionConflict("source ID/version has conflicting immutable content")
            return existing["version_id"]
        version_id = "knowledge:" + _hash([origin, record["table"], record["record_id"], record["record_version"]])
        db.execute("INSERT INTO knowledge_versions VALUES(?,?,?,?,?,?,?,?)", (
            version_id, origin, record["table"], record["record_id"], record["record_version"],
            semantic_hash, _json(record), _now()))
        return version_id

    @staticmethod
    def _validate_snapshot(snapshot):
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1 or type(snapshot.get("schema_version")) is not int:
            raise ValueError("unsupported snapshot envelope")
        if snapshot.get("kind") not in {"synthetic", "atlas_snapshot"}:
            raise ValueError("snapshot kind must be synthetic or atlas_snapshot")
        _integer(snapshot.get("revision"), "snapshot revision")
        if not isinstance(snapshot.get("retrieved_at"), str) or not snapshot["retrieved_at"].strip():
            raise ValueError("snapshot retrieval time is required")
        if not isinstance(snapshot.get("records"), list) or len(snapshot["records"]) > 500:
            raise ValueError("snapshot requires at most 500 records")
        if len(_json(snapshot).encode()) > 5_000_000:
            raise ValueError("snapshot exceeds five MB")
        selected = {}
        all_versions = {}
        for record in snapshot["records"]:
            _validate_record(record)
            if record["snapshot_revision"] != snapshot["revision"]:
                raise ValueError("source snapshot revision mismatch")
            identity = (record["table"], record["record_id"])
            version = (*identity, record["record_version"])
            if version in all_versions and _semantic(all_versions[version]) != _semantic(record):
                raise VersionConflict("duplicate source ID/version has conflicting content")
            all_versions[version] = deepcopy(record)
            if identity not in selected or selected[identity]["record_version"] < record["record_version"]:
                selected[identity] = deepcopy(record)
        return list(all_versions.values()), selected

    def seed_snapshot(self, snapshot: dict) -> dict:
        """Seed once; restarting the application never overwrites local review."""
        return self.import_snapshot(snapshot, only_if_empty=True)

    def import_snapshot(self, snapshot: dict, expected_revision: int | None = None, *, only_if_empty=False) -> dict:
        """Atomically replace active membership, retaining immutable old versions.

        Missing, revoked and newer unapproved records cannot leave old approved
        versions active. Real source imports are permanently read-only locally.
        """
        records, selected = self._validate_snapshot(snapshot)
        origin = snapshot["kind"]
        envelope_hash = _hash(snapshot)
        import_id = "import:" + envelope_hash
        with self._connect(write=True) as db:
            current = self._revision(db, "knowledge_revision")
            if only_if_empty and db.execute("SELECT 1 FROM knowledge_versions LIMIT 1").fetchone():
                return {"seeded": False, "revision": current}
            if expected_revision is not None:
                _integer(expected_revision, "expected revision")
                if current != expected_revision:
                    raise VersionConflict("knowledge collection revision changed")
            latest_source = db.execute("SELECT max(source_revision) FROM knowledge_imports WHERE kind=?", (origin,)).fetchone()[0]
            if latest_source is not None and snapshot["revision"] < latest_source:
                raise VersionConflict("source snapshot revision moved backwards")
            for record in selected.values():
                maximum = db.execute("SELECT max(record_version) FROM knowledge_versions WHERE origin=? AND table_name=? AND record_id=?",
                    (origin, record["table"], record["record_id"])).fetchone()[0]
                if maximum is not None and record["record_version"] < maximum:
                    raise VersionConflict("source refresh would reactivate an older record version")
            db.execute("INSERT OR IGNORE INTO knowledge_imports VALUES(?,?,?,?,?,?,?)", (
                import_id, origin, snapshot["revision"], snapshot["retrieved_at"], envelope_hash, _json(snapshot), _now()))
            versions = {}
            for record in records:
                versions[(record["table"], record["record_id"], record["record_version"])] = self._insert_version(db, record, origin)
            db.execute("DELETE FROM knowledge_current")
            for record in selected.values():
                version_id = versions[(record["table"], record["record_id"], record["record_version"])]
                db.execute("INSERT INTO knowledge_current VALUES(?,?,?,?,?)", (
                    record["table"], record["record_id"], version_id, _json(record), import_id))
            revision = self._advance(db, "knowledge_revision")
        return {"seeded": True, "revision": revision, "import_id": import_id,
                "source_revision": snapshot["revision"], "records": len(selected), "kind": origin}

    def imports(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT import_id,kind,source_revision,retrieved_at,envelope_hash,created_at FROM knowledge_imports ORDER BY created_at,import_id")]

    def list_records(self, include_history=False) -> list[dict]:
        """Display records with lab_origin/read_only fields; never index this view."""
        with self._connect() as db:
            query = ("SELECT record_json AS record_json,origin FROM knowledge_versions ORDER BY table_name,record_id,record_version"
                     if include_history else
                     "SELECT c.observed_json AS record_json,v.origin FROM knowledge_current c JOIN knowledge_versions v USING(version_id) ORDER BY c.table_name,c.record_id")
            return [{**json.loads(row["record_json"]), "lab_origin": row["origin"],
                     "read_only": row["origin"] == "atlas_snapshot"} for row in db.execute(query)]

    def snapshot(self) -> dict:
        """Eligible RAG export; source revisions remain separate provenance.

        ``revision`` and record ``snapshot_revision`` identify this atomic lab
        export. Native observed source revision/time are retained in metadata;
        original source JSON remains immutable in knowledge_versions/imports.
        """
        with self._connect() as db:
            revision = self._revision(db, "knowledge_revision")
            rows = db.execute("SELECT c.observed_json,v.origin,c.import_id FROM knowledge_current c JOIN knowledge_versions v USING(version_id) ORDER BY c.table_name,c.record_id").fetchall()
            records, source_kinds = [], set()
            for row in rows:
                record = json.loads(row["observed_json"])
                source_kinds.add(row["origin"])
                if record["approval_status"] != "APPROVED" or record.get("superseded", False):
                    continue
                record["metadata"] = {**record.get("metadata", {}),
                    "source_snapshot_revision": record["snapshot_revision"],
                    "source_retrieved_at": record["retrieved_at"], "lab_origin": row["origin"]}
                record["snapshot_revision"] = revision
                record["export_text_hash"] = hashlib.sha256(record["text"].encode()).hexdigest()
                records.append(record)
            return {"schema_version": 1, "kind": "atlas_snapshot" if "atlas_snapshot" in source_kinds else "synthetic",
                    "revision": revision, "retrieved_at": _now(), "records": records,
                    "coverage": {"source_records": len(rows), "selected_records": len(records),
                        "snapshot_revision_meaning": "atomic lab export revision; native source revision/time retained in record metadata",
                        "source": "isolated Atlas Lab; no live synchronization"}}

    @staticmethod
    def _current(db, record_id, table=None):
        rows = db.execute("SELECT c.*,v.origin FROM knowledge_current c JOIN knowledge_versions v USING(version_id) WHERE c.record_id=?" +
                          (" AND c.table_name=?" if table else ""), (record_id, table) if table else (record_id,)).fetchall()
        if len(rows) > 1:
            raise ValueError("record ID is ambiguous; specify its table")
        return rows[0] if rows else None

    def put_synthetic(self, record: dict, expected_version: int | None = None) -> dict:
        """Create/edit synthetic evidence; every changed version needs review."""
        if not isinstance(record, dict):
            raise ValueError("synthetic record must be an object")
        _no_sensitive_keys(record)
        record_id, table, text = record.get("record_id"), record.get("table", "Candidate_Facts"), record.get("text")
        if not isinstance(record_id, str) or not record_id.strip() or len(record_id) > 256 or table not in TABLES:
            raise ValueError("valid record ID/table required")
        if not isinstance(text, str) or not text.strip() or len(text) > 20_000 or not isinstance(record.get("metadata", {}), dict):
            raise ValueError("synthetic text/metadata is invalid")
        if expected_version is not None:
            _integer(expected_version, "expected version")
        with self._connect(write=True) as db:
            existing = self._current(db, record_id, table)
            if existing and existing["origin"] != "synthetic":
                raise ReadOnlySource("imported real records are read-only; create a new synthetic ID")
            old = json.loads(existing["observed_json"]) if existing else None
            if (old is not None and expected_version != old["record_version"]) or (old is None and expected_version not in {None, 0}):
                raise VersionConflict("synthetic record version changed")
            # Version numbers also survive an explicit snapshot replacement.
            maximum = db.execute("SELECT max(record_version) FROM knowledge_versions WHERE origin='synthetic' AND table_name=? AND record_id=?", (table, record_id)).fetchone()[0] or 0
            version = maximum + 1
            revision = self._advance(db, "knowledge_revision")
            value = {"record_id": record_id, "record_version": version, "approval_status": "REVIEW_REQUIRED",
                     "table": table, "source_ref": "synthetic:atlas-lab:" + record_id,
                     "source_version": f"lab-{version}", "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                     "text": text, "snapshot_revision": revision, "retrieved_at": _now(),
                     "metadata": deepcopy(record.get("metadata", {}))}
            _validate_record(value)
            version_id = self._insert_version(db, value, "synthetic")
            db.execute("INSERT INTO knowledge_current VALUES(?,?,?,?,NULL) ON CONFLICT(table_name,record_id) DO UPDATE SET version_id=excluded.version_id,observed_json=excluded.observed_json,import_id=NULL",
                       (table, record_id, version_id, _json(value)))
        return value

    def review(self, record_id: str, expected_version: int, status: str, table: str | None = None) -> dict:
        """Review a synthetic version. Revocation is an ARCHIVED new version."""
        _integer(expected_version, "expected version", 1)
        status = "ARCHIVED" if status == "REVOKED" else status
        if status not in APPROVALS:
            raise ValueError("invalid review status")
        with self._connect(write=True) as db:
            existing = self._current(db, record_id, table)
            if existing is None:
                raise KeyError("knowledge record not found")
            if existing["origin"] != "synthetic":
                raise ReadOnlySource("source approval is an observed fact; imported records are read-only")
            value = json.loads(existing["observed_json"])
            if value["record_version"] != expected_version:
                raise VersionConflict("reviewed record version changed")
            value["record_version"] += 1
            value["approval_status"] = status
            value["source_version"] = f"lab-{value['record_version']}"
            value["snapshot_revision"] = self._advance(db, "knowledge_revision")
            value["retrieved_at"] = _now()
            version_id = self._insert_version(db, value, "synthetic")
            db.execute("UPDATE knowledge_current SET version_id=?,observed_json=?,import_id=NULL WHERE table_name=? AND record_id=?",
                       (version_id, _json(value), value["table"], record_id))
        return value

    def revoke(self, record_id, expected_version, table=None):
        return self.review(record_id, expected_version, "ARCHIVED", table)

    @staticmethod
    def _manifest(row):
        return {"artifact_id": row["artifact_id"], "run_id": row["run_id"], "kind": row["kind"],
                "version": row["version"], "sha256": row["digest"], "content_hash": row["digest"],
                "content_type": row["content_type"], "byte_size": row["byte_size"],
                "metadata": json.loads(row["metadata_json"]), "created_at": row["created_at"]}

    def store_artifact(self, run_id: str, kind: str, content: bytes, metadata: dict | None = None) -> dict:
        """Persist exact immutable bytes before registering a versioned manifest."""
        _identifier(run_id, "run ID")
        if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", kind):
            raise ValueError("invalid artifact kind")
        if not isinstance(content, bytes) or not content or len(content) > 5_000_000:
            raise ValueError("artifact must contain 1..5000000 bytes")
        metadata = deepcopy({} if metadata is None else metadata)
        if not isinstance(metadata, dict) or len(_json(metadata).encode()) > 65536:
            raise ValueError("invalid artifact metadata")
        _no_sensitive_keys(metadata)
        content_type = metadata.get("content_type", "text/markdown")
        if content_type not in {"text/markdown", "text/plain", "application/json", "application/pdf"}:
            raise ValueError("unsupported artifact content type")
        digest = hashlib.sha256(content).hexdigest()
        target = self.artifact_root / digest
        if target.exists():
            if target.read_bytes() != content:
                raise IntegrityError("artifact bytes do not match the immutable digest")
        else:
            temporary = self.artifact_root / (".tmp-" + uuid4().hex)
            try:
                with temporary.open("xb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                # Same digest means the same bytes; replace is atomic for readers.
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        metadata_json, metadata_hash = _json(metadata), _hash(metadata)
        with self._connect(write=True) as db:
            self._run(db, run_id)
            existing = db.execute("SELECT * FROM artifacts WHERE run_id=? AND kind=? AND digest=? AND metadata_hash=?", (run_id, kind, digest, metadata_hash)).fetchone()
            if existing:
                return self._manifest(existing)
            version = (db.execute("SELECT max(version) FROM artifacts WHERE run_id=? AND kind=?", (run_id, kind)).fetchone()[0] or 0) + 1
            artifact_id = "artifact:" + _hash([run_id, kind, version, digest])[:32]
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?)", (artifact_id, run_id, kind, version,
                digest, content_type, len(content), metadata_json, metadata_hash, _now()))
            return self._manifest(db.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone())

    def artifacts(self, run_id: str | None = None) -> list[dict]:
        if run_id is not None:
            _identifier(run_id, "run ID")
        with self._connect() as db:
            return [self._manifest(row) for row in db.execute("SELECT * FROM artifacts" +
                (" WHERE run_id=?" if run_id else "") + " ORDER BY run_id,kind,version", (run_id,) if run_id else ())]

    def get_artifact(self, digest: str) -> bytes:
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid artifact digest")
        with self._connect() as db:
            if db.execute("SELECT 1 FROM artifacts WHERE digest=?", (digest,)).fetchone() is None:
                raise KeyError("artifact not registered")
        try:
            content = (self.artifact_root / digest).read_bytes()
        except OSError:
            raise IntegrityError("registered artifact bytes are unavailable") from None
        if hashlib.sha256(content).hexdigest() != digest:
            raise IntegrityError("artifact byte hash verification failed")
        return content

    def save_approval(self, run_id: str, plan_hash: str, decision: str, manifest: dict) -> dict:
        """Persist exact action-review material separately from source approval."""
        if not isinstance(plan_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", plan_hash) or decision not in {"approve", "reject", "revise"}:
            raise ValueError("invalid action approval")
        if not isinstance(manifest, dict):
            raise ValueError("approval manifest must be an object")
        manifest_json, manifest_hash = _json(manifest), _hash(manifest)
        approval_id = "approval:" + _hash([run_id, plan_hash, decision, manifest_hash])[:32]
        with self._connect(write=True) as db:
            self._run(db, run_id)
            db.execute("INSERT OR IGNORE INTO action_approvals VALUES(?,?,?,?,?,?,?)", (
                approval_id, run_id, plan_hash, decision, manifest_json, manifest_hash, _now()))
            row = db.execute("SELECT * FROM action_approvals WHERE approval_id=?", (approval_id,)).fetchone()
            return {**dict(row), "manifest": json.loads(row["manifest_json"])}

    def approvals(self, run_id):
        _identifier(run_id, "run ID")
        with self._connect() as db:
            return [{**dict(row), "manifest": json.loads(row["manifest_json"])} for row in db.execute(
                "SELECT * FROM action_approvals WHERE run_id=? ORDER BY created_at,approval_id", (run_id,))]

    @staticmethod
    def _event(row):
        return {"event_id": row["event_id"], "revision": row["event_revision"], "run_id": row["run_id"],
                "gate": row["gate"], "status": row["status"], "idempotency_key": row["idempotency_key"],
                "receipt": json.loads(row["receipt_json"]), "payload": json.loads(row["payload_json"]),
                "payload_hash": row["payload_hash"], "created_at": row["created_at"]}

    def record_event(self, run_id: str, gate: str, receipt: dict, payload: dict) -> dict:
        """Commit one observed simulated receipt, checking exact payload/artifacts."""
        if gate not in {"application", "outreach", "storage", "commit", "delivery"} or not isinstance(receipt, dict) or not isinstance(payload, dict):
            raise ValueError("invalid simulated event")
        fingerprint = FakeProvider._fingerprint(gate, payload)
        if (receipt.get("gate") != gate or receipt.get("status") not in {"PENDING", "VERIFIED"}
                or not str(receipt.get("receipt_id", "")).startswith("sim:")
                or not str(receipt.get("idempotency_key", "")).startswith("sim-key:")
                or receipt.get("payload_hash") != fingerprint):
            raise IntegrityError("receipt does not verify the exact simulated event payload")
        body = payload.get("payload", payload)
        if not isinstance(body, dict):
            raise ValueError("event payload must be an object")
        identity = payload.get("identity") or body.get("job_identity")
        if not isinstance(identity, str) or not identity.strip() or (body.get("job_identity") is not None and body["job_identity"] != identity):
            raise IntegrityError("event target identity is missing or inconsistent")
        references = body.get("artifacts", [])
        if not isinstance(references, list) or (gate in {"application", "outreach", "storage"} and not references):
            raise IntegrityError("dependent event requires registered artifact references")
        with self._connect(write=True) as db:
            self._run(db, run_id)
            previous = db.execute("SELECT * FROM event_ledger WHERE run_id=? AND gate=? AND idempotency_key=? ORDER BY event_revision DESC LIMIT 1",
                (run_id, gate, receipt["idempotency_key"])).fetchone()
            if previous:
                if previous["payload_hash"] != fingerprint or json.loads(previous["receipt_json"])["receipt_id"] != receipt["receipt_id"]:
                    raise IntegrityError("event identity cannot be rebound to changed evidence")
            other = db.execute("SELECT payload_json FROM event_ledger WHERE run_id=? LIMIT 1", (run_id,)).fetchone()
            if other:
                original = json.loads(other["payload_json"])
                original_identity = original.get("identity") or original.get("payload", original).get("job_identity")
                if original_identity != identity:
                    raise IntegrityError("run events cannot change their reviewed target identity")
            artifact_ids = []
            for reference in references:
                digest = reference.get("sha256") if isinstance(reference, dict) else reference
                if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise IntegrityError("invalid event artifact byte digest")
                rows = db.execute("SELECT * FROM artifacts WHERE run_id=? AND digest=?", (run_id, digest)).fetchall()
                matching = [row for row in rows if not isinstance(reference, dict) or (
                    ("kind" not in reference or reference["kind"] == row["kind"]) and
                    ("version" not in reference or reference["version"] == row["version"]) and
                    ("byte_size" not in reference or reference["byte_size"] == row["byte_size"]) and
                    ("content_type" not in reference or reference["content_type"] == row["content_type"]))]
                if not matching:
                    raise IntegrityError("event artifact/version is not registered for this run")
                metadata_identity = json.loads(matching[0]["metadata_json"]).get("job_identity")
                if metadata_identity is not None and metadata_identity != identity:
                    raise IntegrityError("event artifact belongs to a different reviewed target")
                try:
                    content = (self.artifact_root / matching[0]["digest"]).read_bytes()
                except OSError:
                    raise IntegrityError("registered event artifact bytes are unavailable") from None
                if hashlib.sha256(content).hexdigest() != matching[0]["digest"]:
                    raise IntegrityError("event artifact bytes failed verification")
                artifact_ids.append(matching[0]["artifact_id"])
            if previous and (previous["status"] == receipt["status"] or previous["status"] == "VERIFIED"):
                return self._event(previous)
            revision = self._advance(db, "ledger_revision")
            event_id = "event:" + _hash([run_id, gate, receipt["idempotency_key"], receipt["status"]])[:32]
            db.execute("INSERT INTO event_ledger VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, revision, run_id, gate,
                receipt["idempotency_key"], receipt["status"], _json(receipt), _json(payload), fingerprint, _now()))
            for artifact_id in set(artifact_ids):
                db.execute("INSERT INTO event_artifacts VALUES(?,?)", (event_id, artifact_id))
            return self._event(db.execute("SELECT * FROM event_ledger WHERE event_id=?", (event_id,)).fetchone())

    def events(self, run_id: str | None = None, include_history=False) -> list[dict]:
        if run_id is not None:
            _identifier(run_id, "run ID")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM event_ledger" + (" WHERE run_id=?" if run_id else "") +
                              " ORDER BY event_revision", (run_id,) if run_id else ()).fetchall()
            events = [self._event(row) for row in rows]
            if include_history:
                return events
            latest = {(event["run_id"], event["gate"], event["idempotency_key"]): event for event in events}
            return sorted(latest.values(), key=lambda event: event["revision"])

    def project(self) -> dict:
        """Rebuild reporting from committed events; never repeats provider actions."""
        with self._connect(write=True) as db:
            rows = db.execute("SELECT * FROM event_ledger ORDER BY event_revision").fetchall()
            latest = {}
            for row in rows:
                latest[(row["run_id"], row["gate"], row["idempotency_key"])] = self._event(row)
            runs = {}
            for event in latest.values():
                run = runs.setdefault(event["run_id"], {"run_id": event["run_id"], "gates": {}, "job_identity": None})
                payload = event["payload"]
                run["job_identity"] = payload.get("identity") or payload.get("payload", {}).get("job_identity")
                run["gates"][event["gate"]] = run["gates"].get(event["gate"], True) and event["status"] == "VERIFIED"
            for run in runs.values():
                run["complete"] = all(run["gates"].get(gate, False) for gate in ("application", "outreach", "storage", "commit", "delivery"))
            revision = self._revision(db, "ledger_revision")
            result = {"schema_version": 1, "revision": revision, "members": [row["event_id"] for row in rows],
                      "runs": sorted(runs.values(), key=lambda run: run["run_id"]),
                      "complete_units": len({run["job_identity"] or run["run_id"] for run in runs.values() if run["complete"]}),
                      "event_count": len(rows), "effects": "SIMULATION", "projected_at": _now()}
            db.execute("INSERT INTO reporting_projection VALUES(1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json,created_at=excluded.created_at",
                       (revision, _json(result), _now()))
        return self.projection()

    def projection(self) -> dict:
        """Read back separate projection revision AND exact event membership."""
        with self._connect() as db:
            row = db.execute("SELECT payload_json FROM reporting_projection WHERE singleton=1").fetchone()
            result = json.loads(row[0]) if row else {"schema_version": 1, "revision": 0, "members": [], "runs": [], "complete_units": 0, "event_count": 0, "effects": "SIMULATION"}
            expected = {row[0] for row in db.execute("SELECT event_id FROM event_ledger")}
            actual = set(result["members"])
            ledger_revision = self._revision(db, "ledger_revision")
            return {**result, "ledger_revision": ledger_revision,
                    "up_to_date": result["revision"] == ledger_revision and actual == expected,
                    "missing_event_ids": sorted(expected - actual), "unexpected_event_ids": sorted(actual - expected)}

    def dashboard(self) -> dict:
        return self.projection()
