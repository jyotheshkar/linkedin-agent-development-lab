# LEARN: WORKFLOW-01
# ROLE: Model an independent receipt service without contacting employers.
# FLOW: Exact approved payload -> unique simulated receipt -> reconciliation.
# WHY: Uniqueness plus payload binding matters; a hash by itself provides no exactly-once guarantee.
# L1: Trace one input and its failure path, then run tests/test_workflow.py.
# L2: Defend this boundary and one alternative; inspect docs/learning/lesson-index.json.
# PYTHON: Type hints describe contracts; exceptions propagate unless explicitly handled.
"""Persistent fake provider: no network, email, employer or Atlas adapters."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from .agent import GuardrailError, PermanentError, TransientError, UnknownOutcome, GATES


class FakeProvider:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.failures: dict[str, list[str]] = defaultdict(list)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS receipts (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def inject(self, gate: str, *modes: str) -> None:
        """Queue transient_before, unknown_after, pending_after or permanent."""
        if gate not in GATES or any(x not in {"transient_before", "unknown_after", "pending_after", "permanent", "invalid_output"} for x in modes):
            raise ValueError("unknown fake failure scenario")
        self.failures[gate].extend(modes)

    @staticmethod
    def _fingerprint(gate: str, payload: dict) -> str:
        encoded = json.dumps({"gate": gate, "payload": payload}, sort_keys=True, allow_nan=False)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def execute(self, gate: str, payload: dict, key: str) -> dict:
        if gate not in GATES or not key.startswith("sim-key:"):
            raise GuardrailError("only simulated provider operations are supported")
        fingerprint = self._fingerprint(gate, payload)
        existing = self.reconcile(key)
        if existing:
            with self._connect() as db:
                stored = db.execute("SELECT fingerprint FROM receipts WHERE key=?", (key,)).fetchone()[0]
            if stored != fingerprint:
                raise GuardrailError("idempotency key reused with a changed payload")
            return existing
        mode = self.failures[gate].pop(0) if self.failures[gate] else None
        if mode == "transient_before":
            raise TransientError("simulated pre-effect transport failure")
        if mode == "permanent":
            raise PermanentError("simulated permanent failure")
        receipt = {"receipt_id": "sim:" + hashlib.sha256(key.encode()).hexdigest()[:20],
                   "gate": gate, "status": "PENDING" if mode == "pending_after" else "VERIFIED",
                   "idempotency_key": key, "payload_hash": fingerprint}
        with self._connect() as db:
            db.execute("INSERT INTO receipts VALUES (?,?,?)", (key, fingerprint, json.dumps(receipt)))
        if mode == "unknown_after":
            raise UnknownOutcome("effect committed but response timed out")
        if mode == "invalid_output":
            return {"status": "VERIFIED", "receipt_id": "untrusted:invalid"}
        return receipt

    def reconcile(self, key: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT receipt FROM receipts WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def finalize(self, key: str) -> dict:
        receipt = self.reconcile(key)
        if receipt is None:
            raise KeyError(key)
        receipt["status"] = "VERIFIED"
        with self._connect() as db:
            db.execute("UPDATE receipts SET receipt=? WHERE key=?", (json.dumps(receipt), key))
        return receipt

    def effect_count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
