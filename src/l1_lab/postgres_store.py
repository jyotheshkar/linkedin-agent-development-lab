"""Durable deployment stores for the simulated workflow.

No constructor performs DDL. Run the explicit migration with a migration role
before serving requests. Receipts use a different connection/transaction from
journal writes, so a journal rollback cannot erase a committed fake effect.

Session advisory locks require a direct or session-pooled PostgreSQL URL.
Transaction-mode pooling is unsuitable for the lock connection. The caller
must hold ``journal.run_lock(run_id)`` around the complete start/resume action.
All errors exposed here omit connection strings and driver exception text.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Iterator

import psycopg
from psycopg.types.json import Jsonb

from .agent import GATES, GuardrailError, PermanentError, TransientError, UnknownOutcome
from .provider import FakeProvider


class PostgresStoreError(RuntimeError):
    """Generic availability error, safe to return without driver details."""


class RunBusyError(RuntimeError):
    """Another process holds the same namespace/run execution lock."""


class BudgetExceeded(RuntimeError):
    """The durable action budget for this window has been consumed."""


def _positive_int(value: int, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")


def _run_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("invalid run ID")
    return value


def _json_copy(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("stored state must be an object")
    try:
        encoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError):
        raise ValueError("stored state must contain finite JSON values") from None
    if len(encoded.encode("utf-8")) > 1_048_576:
        raise ValueError("stored state exceeds the one MiB bound")
    return json.loads(encoded)


class _Database:
    def __init__(self, database_url: str, namespace: str = "lab", *, connect_timeout: int = 5,
                 statement_timeout_ms: int = 5000):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database URL is required")
        if not isinstance(namespace, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", namespace):
            raise ValueError("invalid store namespace")
        _positive_int(connect_timeout, "connect_timeout", 1, 15)
        _positive_int(statement_timeout_ms, "statement_timeout_ms", 100, 30000)
        self._database_url = database_url
        self.namespace = namespace
        self.connect_timeout = connect_timeout
        self.statement_timeout_ms = statement_timeout_ms

    @contextmanager
    def _connect(self, *, autocommit: bool = False, database_url: str | None = None) -> Iterator:
        try:
            with psycopg.connect(database_url or self._database_url,
                                 connect_timeout=self.connect_timeout,
                                 autocommit=autocommit) as db:
                if not autocommit:
                    db.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                # Local settings stay with the short write transaction, which
                # works with transaction-mode pools. Session settings are used
                # only on the dedicated direct/session-pooled lock connection.
                db.execute(
                    "SELECT set_config('statement_timeout',%s,%s), "
                    "set_config('lock_timeout',%s,%s), "
                    "set_config('idle_in_transaction_session_timeout','10000',%s)",
                    (str(self.statement_timeout_ms), not autocommit,
                     str(self.statement_timeout_ms), not autocommit, not autocommit))
                yield db
        except psycopg.Error:
            raise PostgresStoreError("durable store operation unavailable") from None


class PostgresJournal(_Database):
    """Journal-compatible JSONB store; safe coordination requires run_lock."""

    def __init__(self, database_url: str, namespace: str = "lab", *,
                 lock_database_url: str | None = None, **kwargs):
        super().__init__(database_url, namespace, **kwargs)
        if lock_database_url is not None and (not isinstance(lock_database_url, str) or not lock_database_url.strip()):
            raise ValueError("lock database URL must be nonempty")
        self._lock_database_url = lock_database_url or database_url
        self._active_session = ContextVar(f"l1lab-journal-{id(self)}", default=None)

    @contextmanager
    def _journal_connection(self, run_id: str) -> Iterator:
        active = self._active_session.get()
        if active is not None and active[0] == run_id:
            # Journal statements use the lock-holding session itself. If that
            # connection is lost, fail rather than writing on an unlocked new
            # connection. Each statement autocommits; provider effects still
            # commit on independent connections.
            try:
                yield active[1]
            except psycopg.Error:
                raise PostgresStoreError("durable store operation unavailable") from None
        else:
            with self._connect() as db:
                yield db

    def save(self, state: dict) -> None:
        state = _json_copy(state)
        run_id = _run_id(state.get("run_id"))
        with self._journal_connection(run_id) as db:
            db.execute(
                "INSERT INTO public.l1lab_runs(namespace,run_id,state) VALUES (%s,%s,%s) "
                "ON CONFLICT(namespace,run_id) DO UPDATE SET state=EXCLUDED.state, "
                "revision=l1lab_runs.revision+1, updated_at=statement_timestamp()",
                (self.namespace, run_id, Jsonb(state)))

    def load(self, run_id: str) -> dict:
        run_id = _run_id(run_id)
        with self._journal_connection(run_id) as db:
            row = db.execute("SELECT state FROM public.l1lab_runs WHERE namespace=%s AND run_id=%s",
                             (self.namespace, run_id)).fetchone()
        if row is None:
            raise FileNotFoundError("run not found")
        return deepcopy(row[0])

    def exists(self, run_id: str) -> bool:
        run_id = _run_id(run_id)
        with self._journal_connection(run_id) as db:
            return db.execute("SELECT 1 FROM public.l1lab_runs WHERE namespace=%s AND run_id=%s",
                              (self.namespace, run_id)).fetchone() is not None

    @contextmanager
    def run_lock(self, run_id: str) -> Iterator[None]:
        """Try one session lock without waiting; close releases it after a crash.

        The dedicated session stays open and journal statements autocommit on
        that lock-holding connection. Provider receipts commit independently
        on other connections. A busy run raises RunBusyError immediately.
        """
        run_id = _run_id(run_id)
        if self._active_session.get() is not None:
            raise RunBusyError("nested run execution is not supported")
        lock_id = int.from_bytes(hashlib.sha256(
            f"l1lab:{self.namespace}:{run_id}".encode()).digest()[:8], "big", signed=True)
        with self._connect(autocommit=True, database_url=self._lock_database_url) as db:
            acquired = db.execute("SELECT pg_try_advisory_lock(%s)", (lock_id,)).fetchone()[0]
            if not acquired:
                raise RunBusyError("run is already executing")
            token = self._active_session.set((run_id, db))
            try:
                yield
            finally:
                self._active_session.reset(token)
                # Closing the dedicated connection is the fallback release.
                with suppress(psycopg.Error):
                    db.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))


class PostgresProvider(_Database):
    """Independent, persistent simulated receipt service. No employer effects."""

    def __init__(self, database_url: str, namespace: str = "lab", **kwargs):
        super().__init__(database_url, namespace, **kwargs)
        self.failures: dict[str, list[str]] = defaultdict(list)
        self._failure_lock = threading.Lock()

    _fingerprint = staticmethod(FakeProvider._fingerprint)

    def inject(self, gate: str, *modes: str) -> None:
        if gate not in GATES or any(mode not in {
            "transient_before", "unknown_after", "pending_after", "permanent", "invalid_output"
        } for mode in modes):
            raise ValueError("unknown fake failure scenario")
        with self._failure_lock:
            self.failures[gate].extend(modes)

    def execute(self, gate: str, payload: dict, key: str) -> dict:
        try:
            return self._execute(gate, payload, key)
        except PostgresStoreError:
            # A failed commit acknowledgement may still follow a committed
            # receipt. Preserve the workflow's in-flight identity and require
            # reconciliation instead of clearing it as a safe pre-effect error.
            raise UnknownOutcome("simulated receipt outcome uncertain; reconcile before retry") from None

    def _execute(self, gate: str, payload: dict, key: str) -> dict:
        if gate not in GATES or not isinstance(key, str) or not key.startswith("sim-key:") or len(key) > 200:
            raise GuardrailError("only simulated provider operations are supported")
        payload = _json_copy(payload)
        fingerprint = self._fingerprint(gate, payload)
        existing = self.reconcile(key)
        if existing is not None:
            if existing.get("payload_hash") != fingerprint:
                raise GuardrailError("idempotency key reused with a changed payload")
            return existing
        with self._failure_lock:
            mode = self.failures[gate].pop(0) if self.failures[gate] else None
        if mode == "transient_before":
            raise TransientError("simulated pre-effect transport failure")
        if mode == "permanent":
            raise PermanentError("simulated permanent failure")
        receipt = {"receipt_id": "sim:" + hashlib.sha256(key.encode()).hexdigest()[:20],
                   "gate": gate, "status": "PENDING" if mode == "pending_after" else "VERIFIED",
                   "idempotency_key": key, "payload_hash": fingerprint}
        with self._connect() as db:
            row = db.execute(
                "INSERT INTO public.l1lab_sim_receipts(namespace,idempotency_key,fingerprint,receipt) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(namespace,idempotency_key) DO NOTHING "
                "RETURNING receipt,fingerprint",
                (self.namespace, key, fingerprint, Jsonb(receipt))).fetchone()
            inserted = row is not None
            if row is None:
                # READ COMMITTED gives this second statement visibility of the
                # competing insert after the unique-key conflict has waited.
                row = db.execute(
                    "SELECT receipt,fingerprint FROM public.l1lab_sim_receipts "
                    "WHERE namespace=%s AND idempotency_key=%s FOR UPDATE",
                    (self.namespace, key)).fetchone()
            if row is None or row[1] != fingerprint:
                raise GuardrailError("idempotency key reused with a changed payload")
            receipt = deepcopy(row[0])
        # The receipt transaction has committed before a simulated lost reply.
        if inserted and mode == "unknown_after":
            raise UnknownOutcome("effect committed but response timed out")
        if inserted and mode == "invalid_output":
            return {"status": "VERIFIED", "receipt_id": "untrusted:invalid"}
        return receipt

    def reconcile(self, key: str) -> dict | None:
        if not isinstance(key, str) or len(key) > 200:
            raise ValueError("invalid receipt key")
        with self._connect() as db:
            row = db.execute("SELECT receipt FROM public.l1lab_sim_receipts "
                             "WHERE namespace=%s AND idempotency_key=%s", (self.namespace, key)).fetchone()
        return deepcopy(row[0]) if row else None

    def finalize(self, key: str) -> dict:
        if not isinstance(key, str) or len(key) > 200:
            raise ValueError("invalid receipt key")
        with self._connect() as db:
            row = db.execute(
                "UPDATE public.l1lab_sim_receipts SET receipt="
                "jsonb_set(receipt,'{status}','\"VERIFIED\"'::jsonb) "
                "WHERE namespace=%s AND idempotency_key=%s RETURNING receipt",
                (self.namespace, key)).fetchone()
        if row is None:
            raise KeyError("receipt not found")
        return deepcopy(row[0])

    def effect_count(self) -> int:
        with self._connect() as db:
            return db.execute("SELECT count(*) FROM public.l1lab_sim_receipts WHERE namespace=%s",
                              (self.namespace,)).fetchone()[0]


class DurableBudget(_Database):
    """Atomic fixed-window request/action budget using the database clock."""

    def consume(self, subject: str, action: str, limit: int, *, window_seconds: int = 60,
                cost: int = 1) -> dict:
        if not isinstance(subject, str) or not subject or len(subject) > 500:
            raise ValueError("invalid budget subject")
        if not isinstance(action, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,100}", action):
            raise ValueError("invalid budget action")
        _positive_int(limit, "limit", 1, 10000)
        _positive_int(window_seconds, "window_seconds", 1, 3600)
        _positive_int(cost, "cost", 1, 10000)
        if cost > limit:
            raise BudgetExceeded("action budget exhausted")
        subject_hash = hashlib.sha256(subject.encode()).hexdigest()
        with self._connect() as db:
            row = db.execute(
                "INSERT INTO public.l1lab_action_budgets "
                "(namespace,subject_hash,action,window_seconds,bucket_epoch,used) "
                "VALUES (%s,%s,%s,%s, "
                "floor(extract(epoch FROM statement_timestamp()) / %s)::bigint * %s, %s) "
                "ON CONFLICT(namespace,subject_hash,action,window_seconds,bucket_epoch) "
                "DO UPDATE SET used=l1lab_action_budgets.used+EXCLUDED.used "
                "WHERE l1lab_action_budgets.used+EXCLUDED.used <= %s RETURNING used,bucket_epoch",
                (self.namespace, subject_hash, action, window_seconds, window_seconds,
                 window_seconds, cost, limit)).fetchone()
            if row is None:
                raise BudgetExceeded("action budget exhausted")
        return {"used": row[0], "limit": limit, "remaining": limit - row[0],
                "reset_at_epoch": row[1] + window_seconds, "window_seconds": window_seconds}


def migrate(database_url: str, migration_path: str | Path | None = None) -> dict:
    """Explicit idempotent schema migration; use a deployment migration role."""
    from .resources import MIGRATIONS_DIR
    path = Path(migration_path) if migration_path is not None else MIGRATIONS_DIR / "001_deployment.sql"
    script = path.read_text(encoding="utf-8")
    store = _Database(database_url, statement_timeout_ms=30000)
    with store._connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(%s)", (727011106921,))
        db.execute(script, prepare=False)
    return {"schema_version": 1, "migration": path.name}


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit durable simulation-store migration")
    parser.add_argument("command", choices=["migrate"])
    parser.add_argument("--file", type=Path, default=None)
    args = parser.parse_args()
    database_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("set MIGRATION_DATABASE_URL or DATABASE_URL")
    try:
        result = migrate(database_url, args.file)
    except (PostgresStoreError, OSError, ValueError):
        parser.exit(1, "Migration failed; verify database access and migration privileges.\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
