"""Real database tests run with TEST_DATABASE_URL; no connection is invented."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import threading
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

from l1_lab.agent import GuardrailError, UnknownOutcome
from l1_lab.postgres_store import (BudgetExceeded, DurableBudget, PostgresJournal,
    PostgresProvider, PostgresStoreError, RunBusyError, migrate)


class StoreConfig:
    # Default object repr never exposes its private database URL in failures.
    def __init__(self, url):
        self._url = url


@pytest.fixture(scope="session")
def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for real PostgreSQL verification")
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_deployment.sql"
    try:
        migrate(url, migration)
    except PostgresStoreError:
        pytest.fail("test database migration unavailable; verify the service and migration role", pytrace=False)
    return StoreConfig(url)


@pytest.fixture
def stores(database):
    namespace = "test-" + uuid4().hex
    journal = PostgresJournal(database._url, namespace)
    provider = PostgresProvider(database._url, namespace)
    budget = DurableBudget(database._url, namespace)
    yield journal, provider, budget
    with journal._connect() as db:
        for table in ("l1lab_runs", "l1lab_sim_receipts", "l1lab_action_budgets"):
            # Names are a fixed developer-owned tuple, never caller input.
            db.execute(f"DELETE FROM public.{table} WHERE namespace=%s", (namespace,))


@pytest.mark.infrastructure
def test_postgres_constructors_never_run_ddl_or_connect(monkeypatch):
    def forbidden_connect(*args, **kwargs):
        raise AssertionError("constructor attempted database access")
    monkeypatch.setattr(psycopg, "connect", forbidden_connect)
    url = "postgresql://example:synthetic-secret@localhost/example"
    PostgresJournal(url)
    PostgresProvider(url)
    DurableBudget(url)


@pytest.mark.infrastructure
def test_database_errors_omit_driver_credentials(monkeypatch):
    def broken_connect(*args, **kwargs):
        raise psycopg.OperationalError("connection failed password=synthetic-secret")
    monkeypatch.setattr(psycopg, "connect", broken_connect)
    with pytest.raises(PostgresStoreError) as caught:
        PostgresJournal("postgresql://example:synthetic-secret@localhost/example").exists("example")
    assert str(caught.value) == "durable store operation unavailable"
    assert "synthetic-secret" not in repr(caught.value)
    assert caught.value.__suppress_context__


@pytest.mark.infrastructure
def test_provider_database_uncertainty_keeps_reconciliation_required(monkeypatch):
    def broken_connect(*args, **kwargs):
        raise psycopg.OperationalError("database transport unavailable")
    monkeypatch.setattr(psycopg, "connect", broken_connect)
    provider = PostgresProvider("postgresql://unused")
    with pytest.raises(UnknownOutcome) as caught:
        provider.execute("application", {"identity": "one"}, "sim-key:uncertain")
    assert "reconcile before retry" in str(caught.value)


@pytest.mark.infrastructure
@pytest.mark.parametrize("state", [[], {}, {"run_id": "../escape"}, {"run_id": "nan", "score": float("nan")}])
def test_invalid_journal_state_fails_before_connect(state, monkeypatch):
    def forbidden_connect(*args, **kwargs):
        raise AssertionError("invalid state reached database")
    monkeypatch.setattr(psycopg, "connect", forbidden_connect)
    with pytest.raises(ValueError):
        PostgresJournal("postgresql://unused").save(state)


@pytest.mark.postgres
def test_journal_survives_rebuild_and_returns_detached_state(stores, database):
    journal, _, _ = stores
    assert not journal.exists("restart")
    expected = {"run_id": "restart", "schema_version": 1, "status": "pending", "calls": 3,
                "trace": [{"status": "UNKNOWN_OUTCOME"}], "in_flight": {"key": "sim-key:restart"}}
    with journal.run_lock("restart"):
        journal.save(expected)
    restarted = PostgresJournal(database._url, journal.namespace)
    assert restarted.exists("restart") and restarted.load("restart") == expected
    loaded = restarted.load("restart")
    loaded["trace"].clear()
    assert restarted.load("restart") == expected
    expected["status"] = "completed"
    with restarted.run_lock("restart"):
        restarted.save(expected)
    assert journal.load("restart")["status"] == "completed"
    with pytest.raises(FileNotFoundError):
        journal.load("absent")


@pytest.mark.postgres
def test_same_run_lock_contends_and_releases_on_exception(stores, database):
    journal, _, _ = stores
    second = PostgresJournal(database._url, journal.namespace)
    with journal.run_lock("locked"):
        with pytest.raises(RunBusyError):
            with second.run_lock("locked"):
                pytest.fail("second same-run execution acquired the lock")
        # Different run identity can execute concurrently.
        with second.run_lock("another"):
            second.save({"run_id": "another", "status": "prepared"})
    with second.run_lock("locked"):
        pass
    with pytest.raises(RuntimeError):
        with journal.run_lock("locked"):
            raise RuntimeError("simulated request crash")
    with second.run_lock("locked"):
        pass


@pytest.mark.postgres
def test_namespace_isolation_for_run_locks_and_journal(stores, database):
    journal, _, _ = stores
    other = PostgresJournal(database._url, "other-" + uuid4().hex)
    with journal.run_lock("same"):
        with other.run_lock("same"):
            assert not other.exists("same")


@pytest.mark.postgres
def test_lost_lock_session_cannot_fall_back_to_unlocked_journal_write(stores):
    journal, _, _ = stores
    with journal.run_lock("lost-session"):
        connection = journal._active_session.get()[1]
        connection.close()
        with pytest.raises(PostgresStoreError):
            journal.save({"run_id": "lost-session", "status": "unlocked-write-must-fail"})
    assert not journal.exists("lost-session")


@pytest.mark.postgres
def test_concurrent_receipt_requests_commit_one_payload_bound_receipt(stores, database):
    journal, provider, _ = stores
    barrier = threading.Barrier(8)
    class RacingProvider(PostgresProvider):
        def reconcile(self, key):
            result = super().reconcile(key)
            barrier.wait(timeout=15)
            return result
    def execute(_):
        return RacingProvider(database._url, journal.namespace).execute(
            "application", {"identity": "same-role", "payload": {"kind": "synthetic"}}, "sim-key:race")
    with ThreadPoolExecutor(max_workers=8) as executor:
        receipts = list(executor.map(execute, range(8)))
    assert all(receipt == receipts[0] for receipt in receipts)
    assert provider.effect_count() == 1
    restarted = PostgresProvider(database._url, journal.namespace)
    assert restarted.reconcile("sim-key:race") == receipts[0]
    with pytest.raises(GuardrailError):
        restarted.execute("application", {"identity": "changed"}, "sim-key:race")
    assert restarted.effect_count() == 1


@pytest.mark.postgres
def test_concurrent_changed_payload_cannot_overwrite_first_receipt(stores, database):
    journal, provider, _ = stores
    barrier = threading.Barrier(2)
    class RacingProvider(PostgresProvider):
        def reconcile(self, key):
            result = super().reconcile(key)
            barrier.wait(timeout=15)
            return result
    def execute(version):
        try:
            receipt = RacingProvider(database._url, journal.namespace).execute(
                "application", {"identity": "same-role", "payload": {"version": version}}, "sim-key:payload-race")
            return "accepted", receipt
        except GuardrailError:
            return "rejected", None
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(execute, ("A", "B")))
    assert sorted(status for status, _ in outcomes) == ["accepted", "rejected"]
    accepted = next(receipt for status, receipt in outcomes if status == "accepted")
    assert provider.reconcile("sim-key:payload-race") == accepted
    assert provider.effect_count() == 1


@pytest.mark.postgres
def test_committed_receipt_survives_missing_followup_journal_write(stores, database):
    journal, provider, _ = stores
    key = "sim-key:lost-response"
    payload = {"identity": "example-role", "payload": {"kind": "synthetic"}}
    with journal.run_lock("unknown"):
        journal.save({"run_id": "unknown", "status": "pending", "in_flight": {"key": key}})
        provider.inject("application", "unknown_after")
        with pytest.raises(UnknownOutcome):
            provider.execute("application", payload, key)
        # The request stops here: no success is written to the journal.
    restarted_journal = PostgresJournal(database._url, journal.namespace)
    restarted_provider = PostgresProvider(database._url, journal.namespace)
    assert restarted_journal.load("unknown")["status"] == "pending"
    receipt = restarted_provider.reconcile(key)
    assert receipt["status"] == "VERIFIED" and receipt["receipt_id"].startswith("sim:")
    assert restarted_provider.execute("application", payload, key) == receipt
    assert restarted_provider.effect_count() == 1


@pytest.mark.postgres
def test_pending_receipt_requires_explicit_finalize_and_reconciliation(stores, database):
    journal, provider, _ = stores
    provider.inject("delivery", "pending_after")
    pending = provider.execute("delivery", {"identity": "one"}, "sim-key:pending")
    assert pending["status"] == "PENDING"
    restarted = PostgresProvider(database._url, journal.namespace)
    assert restarted.reconcile("sim-key:pending")["status"] == "PENDING"
    verified = restarted.finalize("sim-key:pending")
    assert verified["status"] == "VERIFIED"
    assert provider.reconcile("sim-key:pending") == verified and provider.effect_count() == 1


def _stable_window(store):
    # Choose a long DB-clock window away from rollover so concurrency tests do
    # not intermittently count requests in two valid adjacent windows.
    with store._connect() as db:
        epoch = int(db.execute("SELECT extract(epoch FROM statement_timestamp())").fetchone()[0])
    for window in (3600, 3599, 3593, 3581):
        if window - epoch % window > 30:
            return window
    pytest.skip("database clock is too close to all selected budget boundaries")


@pytest.mark.postgres
def test_durable_budget_is_atomic_across_concurrent_clients(stores, database):
    journal, _, budget = stores
    window = _stable_window(budget)
    def consume(_):
        client = DurableBudget(database._url, journal.namespace)
        try:
            return client.consume("synthetic-user", "workflow:start", 3, window_seconds=window)
        except BudgetExceeded:
            return None
    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(consume, range(8)))
    accepted = [outcome for outcome in outcomes if outcome is not None]
    assert len(accepted) == 3 and sorted(outcome["used"] for outcome in accepted) == [1, 2, 3]
    restarted = DurableBudget(database._url, journal.namespace)
    with pytest.raises(BudgetExceeded):
        restarted.consume("synthetic-user", "workflow:start", 3, window_seconds=window)
    assert restarted.consume("another-user", "workflow:start", 3, window_seconds=window)["used"] == 1


@pytest.mark.postgres
def test_budget_validation_and_action_scopes(stores):
    _, _, budget = stores
    window = _stable_window(budget)
    assert budget.consume("same-user", "preview", 1, window_seconds=window)["remaining"] == 0
    with pytest.raises(BudgetExceeded):
        budget.consume("same-user", "preview", 1, window_seconds=window)
    assert budget.consume("same-user", "resume", 1, window_seconds=window)["used"] == 1
    for kwargs in ({"limit": True}, {"limit": 0}, {"limit": 1, "cost": True}, {"limit": 1, "window_seconds": 0}):
        with pytest.raises(ValueError):
            budget.consume("same-user", "bad-policy", **kwargs)
