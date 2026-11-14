"""Real HTTP -> workflow -> PostgreSQL durability on the complete reference.

Set TEST_DATABASE_URL to a dedicated synthetic test database. These tests use
the real task implementations and stores; only explicit fake-provider failure
injection and a request-start barrier are wrapped for the recovery scenarios.
No employer, Gmail, Atlas or model-provider connection is exercised.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import threading
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

pytest.importorskip("psycopg")

from l1_lab.api import app
from l1_lab import web_api
from l1_lab.postgres_store import PostgresJournal, PostgresProvider, PostgresStoreError, migrate


pytestmark = [pytest.mark.postgres, pytest.mark.web]


class HTTPStore:
    # Keep the database URL out of fixture representations and assertion text.
    def __init__(self, database_url: str, namespace: str, local_path: Path):
        self._database_url = database_url
        self.namespace = namespace
        self.local_path = local_path
        self.headers = {"Authorization": "Bearer " + "x" * 32}
        self.journal = PostgresJournal(database_url, namespace)
        self.provider = PostgresProvider(database_url, namespace)

    def row_counts(self) -> dict:
        with self.journal._connect() as db:
            return {
                table: db.execute(f"SELECT count(*) FROM public.{table} WHERE namespace=%s",
                                  (self.namespace,)).fetchone()[0]
                for table in ("l1lab_runs", "l1lab_sim_receipts", "l1lab_action_budgets")
            }


@pytest.fixture
def postgres_http(monkeypatch, tmp_path):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for real PostgreSQL HTTP verification")
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_deployment.sql"
    try:
        migrate(database_url, migration)
    except PostgresStoreError:
        pytest.fail("test database migration unavailable; verify the service and migration role", pytrace=False)
    namespace = "http-" + uuid4().hex
    local_path = tmp_path / "must-not-be-used-as-durable-storage"
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        # Narrow Postgres engine tests run locally. The complete Atlas artifact
        # service intentionally blocks cloud release until durable parity exists.
        "LAB_STATE_BACKEND": "postgres",
        "DATABASE_URL": database_url,
        "DATABASE_LOCK_URL": database_url,
        "LAB_NAMESPACE": namespace,
        "LAB_STATE_DIR": str(local_path),
        "LAB_API_TOKEN": "x" * 32,
        "LAB_RELEASE_READY": "true",
    }.items():
        monkeypatch.setenv(name, value)
    store = HTTPStore(database_url, namespace, local_path)
    yield store
    with store.journal._connect() as db:
        for table in ("l1lab_runs", "l1lab_sim_receipts", "l1lab_action_budgets"):
            # Cleanup is scoped to this test's generated namespace only.
            db.execute(f"DELETE FROM public.{table} WHERE namespace=%s", (namespace,))


def create_review_run(client: TestClient, store: HTTPStore) -> dict:
    response = client.post("/api/runs", json={"goal": "Python evaluation"}, headers=store.headers)
    assert response.status_code == 201, response.text
    payload = response.json()
    run = payload["run"]
    assert run["status"] == "awaiting_review" and run["index"] == 2
    assert run["approved_plan_hash"] is None and run["receipts"] == {}
    assert payload["evidence"]["source_kind"] == "synthetic"
    assert payload["evidence"]["answer"]["status"] == "supported"
    assert store.provider.effect_count() == 0
    assert not store.local_path.exists()
    return payload


def assert_completed(run: dict, provider: PostgresProvider) -> None:
    assert run["status"] == "completed"
    assert run["completion"] == {"plan": True, "full_unit": True}
    assert run["gates"]["complete"] is True and len(run["receipts"]) == 5
    ids = {receipt["receipt_id"] for receipt in run["receipts"].values()}
    assert len(ids) == 5 and all(value.startswith("sim:") for value in ids)
    assert provider.effect_count() == 5


def test_postgres_http_auth_then_fresh_client_review_resume(postgres_http):
    store = postgres_http
    with TestClient(app) as first:
        for headers in ({}, {"Authorization": "Bearer wrong-token"}):
            rejected = first.post("/api/runs", json={"goal": "Python evaluation"}, headers=headers)
            assert rejected.status_code == 401
        assert first.get("/api/runs/" + "a" * 32).status_code == 401
        assert all(value == 0 for value in store.row_counts().values())
        paused = create_review_run(first, store)["run"]
    path = "/api/runs/" + paused["run_id"]
    # Fresh HTTP handlers construct new journal/provider/engine objects. State
    # and receipts come from PostgreSQL, not an in-memory TestClient session.
    with TestClient(app) as fresh:
        restored = fresh.get(path, headers=store.headers)
        assert restored.status_code == 200
        assert restored.json()["run"] == paused
        wrong_hash = ("0" if paused["plan_hash"][0] != "0" else "1") + paused["plan_hash"][1:]
        assert fresh.post(path + "/resume", headers=store.headers,
                          json={"approve": True, "plan_hash": wrong_hash}).status_code == 409
        no_approval = fresh.post(path + "/resume", headers=store.headers,
                                 json={"approve": False, "plan_hash": paused["plan_hash"]})
        assert no_approval.status_code == 200
        assert no_approval.json()["run"]["status"] == "awaiting_review"
        assert store.provider.effect_count() == 0
        response = fresh.post(path + "/resume", headers=store.headers,
                              json={"approve": True, "plan_hash": paused["plan_hash"]})
        assert response.status_code == 200, response.text
        final = response.json()["run"]
        assert_completed(final, store.provider)
        repeated = fresh.post(path + "/resume", headers=store.headers,
                              json={"approve": True, "plan_hash": paused["plan_hash"]})
        assert repeated.status_code == 200 and repeated.json()["run"] == final
    rebuilt = PostgresJournal(store._database_url, store.namespace)
    assert rebuilt.load(paused["run_id"]) == final
    assert not store.local_path.exists()


def test_postgres_http_unknown_outcome_survives_fresh_request_and_reconciles(postgres_http, monkeypatch):
    store = postgres_http
    original_stores = web_api.stores
    injection_lock = threading.Lock()
    armed = False
    injected = False

    def failure_stores(settings):
        nonlocal injected
        journal, provider = original_stores(settings)
        with injection_lock:
            if armed and not injected:
                provider.inject("application", "unknown_after")
                injected = True
        return journal, provider

    monkeypatch.setattr(web_api, "stores", failure_stores)
    with TestClient(app) as first:
        paused = create_review_run(first, store)["run"]
        path = "/api/runs/" + paused["run_id"]
        armed = True
        response = first.post(path + "/resume", headers=store.headers,
                              json={"approve": True, "plan_hash": paused["plan_hash"]})
        assert response.status_code == 200, response.text
        pending = response.json()["run"]
        assert injected and pending["status"] == "pending"
        assert pending["index"] == 2 and pending["calls"] == 3
        assert pending["receipts"] == {} and pending["in_flight"]["tool"] == "sim_submit"
        assert pending["approved_plan_hash"] == pending["plan_hash"]
        assert store.provider.effect_count() == 1
    with TestClient(app) as fresh:
        restored = fresh.get(path, headers=store.headers)
        assert restored.status_code == 200 and restored.json()["run"] == pending
        response = fresh.post(path + "/resume", headers=store.headers,
                              json={"approve": False, "plan_hash": paused["plan_hash"]})
        assert response.status_code == 200, response.text
        final = response.json()["run"]
        assert_completed(final, store.provider)
        assert final["calls"] == 7 and final["attempts"]["step_2"] == 1
        reconciled = [event for event in final["trace"] if event["status"] == "RECONCILED"]
        assert len(reconciled) == 1 and reconciled[0]["tool"] == "sim_submit"
        assert final["in_flight"] is None
    assert PostgresJournal(store._database_url, store.namespace).load(paused["run_id"]) == final
    assert not store.local_path.exists()


def test_postgres_http_concurrent_approvals_preserve_one_execution_trace(postgres_http, monkeypatch):
    store = postgres_http
    with TestClient(app) as first:
        paused = create_review_run(first, store)["run"]
    path = "/api/runs/" + paused["run_id"]
    original_stores = web_api.stores
    barrier = threading.Barrier(2)
    synchronize = threading.Event()

    def simultaneous_stores(settings):
        journal, provider = original_stores(settings)
        if synchronize.is_set():
            barrier.wait(timeout=15)
        return journal, provider

    monkeypatch.setattr(web_api, "stores", simultaneous_stores)

    def approve(_):
        with TestClient(app) as concurrent_client:
            response = concurrent_client.post(path + "/resume", headers=store.headers,
                json={"approve": True, "plan_hash": paused["plan_hash"]})
            return response.status_code, response.json()

    synchronize.set()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(approve, range(2)))
    finally:
        synchronize.clear()
    statuses = [status for status, _ in outcomes]
    assert all(status in {200, 409} for status in statuses)
    assert 200 in statuses
    with TestClient(app) as fresh:
        response = fresh.get(path, headers=store.headers)
        assert response.status_code == 200
        final = response.json()["run"]
        assert_completed(final, store.provider)
        assert final["calls"] == 7 and len(final["outputs"]) == 7
        assert len([event for event in final["trace"] if event["status"] == "APPROVED"]) == 1
        for tool in ("sim_submit", "sim_outreach", "sim_store", "sim_commit", "sim_deliver"):
            attempts = [event for event in final["trace"] if event["tool"] == tool and event["status"] == "ATTEMPT"]
            assert len(attempts) == 1 and attempts[0]["attempt"] == 1
        assert all(event["run_id"] == paused["run_id"] for event in final["trace"])
        stable_trace = final["trace"]
        repeated = fresh.post(path + "/resume", headers=store.headers,
                              json={"approve": True, "plan_hash": paused["plan_hash"]})
        assert repeated.status_code == 200 and repeated.json()["run"]["trace"] == stable_trace
    assert PostgresJournal(store._database_url, store.namespace).load(paused["run_id"])["trace"] == stable_trace
    assert not store.local_path.exists()
