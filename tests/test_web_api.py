"""Console boundaries on both branches; integrated behavior on the reference.

Infrastructure checks never execute unfinished student functions. Tests marked
web + m6 exercise the complete reference contracts and honestly fail while the
student implementation is incomplete.
"""

from __future__ import annotations

import inspect
import json

from fastapi.testclient import TestClient
import pytest

from l1_lab.api import app
from l1_lab import deployment, web_api


ENVIRONMENT = (
    "VERCEL", "LAB_API_TOKEN", "DATABASE_URL", "DATABASE_LOCK_URL",
    "LAB_RELEASE_READY", "LAB_STATE_BACKEND", "LAB_NAMESPACE", "LAB_STATE_DIR",
    "OPENAI_API_KEY", "OPENAI_MODEL",
)


@pytest.fixture(autouse=True)
def isolated_local_configuration(monkeypatch, tmp_path):
    for name in ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LAB_STATE_BACKEND", "local")
    monkeypatch.setenv("LAB_STATE_DIR", str(tmp_path / "web-state"))
    monkeypatch.setenv("LAB_NAMESPACE", "test-console")
    with web_api._mutex:
        web_api._local_usage.clear()
        web_api._local_locks.clear()
    yield tmp_path / "web-state"
    with web_api._mutex:
        web_api._local_usage.clear()
        web_api._local_locks.clear()


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def no_storage(_settings):
    raise AssertionError("request reached storage before its boundary check")


@pytest.mark.infrastructure
def test_config_reports_branch_tasks_and_keeps_readiness_honest(client):
    from l1_lab.contracts import parse_job

    response = client.get("/api/config")
    assert response.status_code == 200
    config = response.json()
    student = "raise NotImplementedError" in inspect.getsource(parse_job)
    assert config["mode"] == ("student" if student else "complete")
    assert len(config["unfinished_tasks"]) == (12 if student else 0)
    assert config["effects"] == "simulated"
    assert config["source"] == "synthetic"
    assert config["retrieval"] == "offline hash test double"
    assert config["release_ready"] is False
    assert config["configuration_ready"] is True
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


@pytest.mark.infrastructure
def test_config_and_settings_repr_never_expose_credentials(client, monkeypatch):
    secrets = {
        "LAB_API_TOKEN": "test-owner-token-which-must-stay-private",
        "DATABASE_URL": "postgresql://user:private-db-password@invalid.example/lab",
        "DATABASE_LOCK_URL": "postgresql://user:private-lock-password@invalid.example/lab",
        "OPENAI_API_KEY": "test-openai-key-do-not-expose",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["auth_required"] is True
    serialized = response.text + repr(deployment.Settings.read())
    assert all(secret not in serialized for secret in secrets.values())


@pytest.mark.infrastructure
def test_authentication_happens_before_storage_or_work(client, monkeypatch):
    monkeypatch.setenv("LAB_API_TOKEN", "owner-test-token")
    monkeypatch.setattr(web_api, "stores", no_storage)
    for headers in ({}, {"Authorization": "Bearer wrong-token"}):
        response = client.post("/api/runs", json={"goal": "Python evaluation"}, headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.infrastructure
def test_non_ascii_credentials_are_rejected_without_server_error(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setenv("LAB_API_TOKEN", "owner-test-token")
    with pytest.raises(HTTPException) as caught:
        web_api.authorize("Bearer \u00e9")
    assert caught.value.status_code == 401


@pytest.mark.infrastructure
def test_legacy_fit_budget_failure_is_sanitized(client, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("postgresql://secret-password@private-host")
    monkeypatch.setattr(web_api, "consume", unavailable)
    response = client.post("/fit", json={"job": {"title": "AI", "company": "Example",
        "requisition_id": "test-1", "skills": ["Python"]}})
    assert response.status_code == 503
    assert "secret-password" not in response.text


@pytest.mark.infrastructure
def test_practice_context_requires_configured_auth(client, monkeypatch):
    monkeypatch.setenv("LAB_API_TOKEN", "owner-test-token")
    assert client.get("/api/practice").status_code == 401
    assert client.get("/api/practice", headers={"Authorization": "Bearer owner-test-token"}).status_code == 200


@pytest.mark.infrastructure
@pytest.mark.parametrize("missing,expected", [
    ("LAB_STATE_BACKEND", "durable Postgres"),
    ("LAB_API_TOKEN", "API token"),
    ("DATABASE_URL", "DATABASE_URL"),
    ("DATABASE_LOCK_URL", "DATABASE_LOCK_URL"),
    ("LAB_RELEASE_READY", "release verification"),
    ("student_tasks", "student tasks"),
])
def test_cloud_configuration_fails_closed_before_opening_storage(client, monkeypatch, missing, expected):
    for name, value in {
        "VERCEL": "1", "LAB_STATE_BACKEND": "postgres", "LAB_API_TOKEN": "x" * 32,
        "DATABASE_URL": "postgresql://test:secret@invalid.example/db",
        "DATABASE_LOCK_URL": "postgresql://test:secret@invalid.example/db",
        "LAB_RELEASE_READY": "true",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(deployment, "unfinished_tasks", lambda: [] if missing != "student_tasks" else [{"function": "pending"}])
    if missing == "LAB_STATE_BACKEND":
        monkeypatch.setenv(missing, "local")
    elif missing != "student_tasks":
        monkeypatch.delenv(missing)
    monkeypatch.setattr(web_api, "stores", no_storage)
    response = client.post("/api/runs", json={"goal": "Python evaluation"},
                           headers={"Authorization": "Bearer " + "x" * 32})
    assert response.status_code == 503
    blockers = client.get("/api/config").json()["blockers"]
    assert any(expected in item for item in blockers)


@pytest.mark.infrastructure
def test_body_limit_counts_actual_bytes_before_json_or_work(client, monkeypatch):
    monkeypatch.setattr(web_api, "stores", no_storage)
    response = client.post("/api/runs", content=b" " * 65537,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert "64 KiB" in response.json()["detail"]


@pytest.mark.infrastructure
@pytest.mark.parametrize("body", [
    {}, {"goal": 42}, {"goal": ""}, {"goal": "x" * 2001},
    {"goal": "Python", "unexpected": True},
    {"goal": "Python", "job": {"title": "AI", "company": "Example", "requisition_id": "req-1", "skills": ["Python"], "max_calls": True}},
])
def test_strict_request_validation_returns_422_before_storage(client, monkeypatch, body):
    monkeypatch.setattr(web_api, "stores", no_storage)
    assert client.post("/api/runs", json=body).status_code == 422


@pytest.mark.infrastructure
def test_resume_validation_and_invalid_run_identity(client, monkeypatch):
    monkeypatch.setattr(web_api, "stores", no_storage)
    assert client.get("/api/runs/not-a-run-id").status_code == 422
    assert client.post("/api/runs/" + "a" * 32 + "/resume",
                       json={"approve": "true", "plan_hash": "b" * 64}).status_code == 422
    assert client.post("/api/runs/" + "a" * 32 + "/resume",
                       json={"approve": True, "plan_hash": "not-a-hash"}).status_code == 422


@pytest.mark.infrastructure
def test_cross_site_write_is_rejected_before_body_or_work(client, monkeypatch):
    monkeypatch.setattr(web_api, "stores", no_storage)
    response = client.post("/api/runs", json={"goal": "Python evaluation"},
                           headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Use the same-origin console."


@pytest.mark.infrastructure
def test_asset_allowlist_and_console_redirect(client):
    assert client.get("/", follow_redirects=False).headers["location"] == "/console"
    assert client.get("/console").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    assert "javascript" in client.get("/assets/app.js").headers["content-type"]
    assert client.get("/assets/styles.css").status_code == 200
    for path in ("/assets/private.json", "/assets/contracts.py", "/assets/%2e%2e%2fcontracts.py"):
        assert client.get(path).status_code == 404


@pytest.mark.infrastructure
def test_sixteen_original_practice_questions_expose_no_answer_key(client):
    bank = client.get("/api/practice").json()
    questions = bank["questions"]
    assert len(questions) == 16
    assert len({item["id"] for item in questions}) == 16
    assert all(isinstance(item["prompt"], str) and item["prompt"].strip() for item in questions)
    forbidden = {"answer", "answers", "expected_answer", "reference_answer", "solution", "correct_option", "correct_answers"}
    def inspect_keys(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                inspect_keys(child)
        elif isinstance(value, list):
            for child in value:
                inspect_keys(child)
    inspect_keys(bank)


@pytest.mark.infrastructure
def test_provider_or_database_error_is_generic_and_does_not_leak_details(client, monkeypatch):
    private_error = "postgresql://owner:secret-password@private-host/db SELECT secret FROM users"
    def unavailable(_settings):
        raise RuntimeError(private_error)
    monkeypatch.setattr(web_api, "stores", unavailable)
    response = client.post("/api/runs", json={"goal": "Python evaluation"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Storage or workflow service unavailable; retry or inspect server configuration."
    assert "secret-password" not in response.text and "private-host" not in response.text


@pytest.mark.infrastructure
def test_read_budget_is_owner_shared_across_new_clients_and_requires_token(monkeypatch):
    monkeypatch.setenv("LAB_API_TOKEN", "budget-owner-token")
    monkeypatch.setattr(web_api.time, "time", lambda: 1_000_000)
    class MissingJournal:
        def load(self, _run_id):
            raise FileNotFoundError("not found")
    monkeypatch.setattr(web_api, "stores", lambda _settings: (MissingJournal(), object()))
    path = "/api/runs/" + "a" * 32
    headers = {"Authorization": "Bearer budget-owner-token"}
    with TestClient(app) as first:
        assert first.get(path).status_code == 401
        for _ in range(30):
            assert first.get(path, headers=headers).status_code == 404
    with TestClient(app) as second:
        assert second.get(path).status_code == 401
        for _ in range(30):
            assert second.get(path, headers=headers).status_code == 404
        response = second.get(path, headers=headers)
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"


def create_reference_run(client):
    response = client.post("/api/runs", json={"goal": "Python evaluation"})
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["run"]["status"] == "awaiting_review"
    assert payload["run"]["index"] == 2
    assert payload["run"]["approved_plan_hash"] is None
    return payload


@pytest.mark.web
@pytest.mark.m6
def test_reference_run_exposes_grounded_evidence_and_pauses_before_effects(client, isolated_local_configuration):
    from l1_lab.provider import FakeProvider

    payload = create_reference_run(client)
    run, evidence = payload["run"], payload["evidence"]
    assert FakeProvider(isolated_local_configuration / "provider.sqlite3").effect_count() == 0
    assert evidence["source_kind"] == "synthetic"
    assert evidence["retrieval"]["semantic_embeddings"] is False
    # The default controlled Python fixture has matching approved evidence.
    # Separate application tests retain gaps/abstention for unsupported jobs.
    assert evidence["answer"]["status"] == "supported"
    cited = {cid for claim in evidence["answer"]["claims"] for cid in claim["evidence_ids"]}
    assert cited and cited <= set(evidence["context_chunk_ids"])
    accepted_sources = {cid for event in run["trace"] for cid in event["source_ids"]}
    assert cited <= accepted_sources
    assert any(event["status"] == "REVIEW_REQUIRED" for event in run["trace"])
    assert run["receipts"] == {}


@pytest.mark.web
@pytest.mark.m6
def test_plan_bound_approval_then_fresh_handler_resume_is_durable_and_idempotent(client, isolated_local_configuration):
    from l1_lab.provider import FakeProvider

    payload = create_reference_run(client)
    run = payload["run"]
    path = "/api/runs/" + run["run_id"]
    bad_hash = ("0" if run["plan_hash"][0] != "0" else "1") + run["plan_hash"][1:]
    assert client.post(path + "/resume", json={"approve": True, "plan_hash": bad_hash}).status_code == 409
    paused = client.post(path + "/resume", json={"approve": False, "plan_hash": run["plan_hash"]})
    assert paused.status_code == 200
    assert paused.json()["run"]["status"] == "awaiting_review"
    assert FakeProvider(isolated_local_configuration / "provider.sqlite3").effect_count() == 0

    # A new client causes fresh journal/provider/engine objects to read the same
    # persistent local state. This is not a claim of a cloud process restart.
    with TestClient(app) as fresh:
        restored = fresh.get(path)
        assert restored.status_code == 200
        assert restored.json()["run"]["plan_hash"] == run["plan_hash"]
        completed = fresh.post(path + "/resume", json={"approve": True, "plan_hash": run["plan_hash"]})
        assert completed.status_code == 200, completed.text
        final = completed.json()["run"]
        assert final["status"] == "completed"
        assert final["completion"]["full_unit"] is True
        assert final["gates"]["complete"] is True
        assert len(final["receipts"]) == 5
        assert all(receipt["receipt_id"].startswith("sim:") for receipt in final["receipts"].values())
        for _ in range(2):
            repeated = fresh.post(path + "/resume", json={"approve": True, "plan_hash": run["plan_hash"]})
            assert repeated.status_code == 200
            assert repeated.json()["run"]["receipts"] == final["receipts"]
        assert fresh.get(path).json()["run"]["status"] == "completed"
    assert FakeProvider(isolated_local_configuration / "provider.sqlite3").effect_count() == 5
    saved = json.loads((isolated_local_configuration / "runs" / (run["run_id"] + ".json")).read_text())
    assert saved["receipts"] == final["receipts"]


@pytest.mark.web
@pytest.mark.m6
def test_new_same_target_run_is_reserved_without_repeating_effects(client, isolated_local_configuration):
    from l1_lab.provider import FakeProvider

    receipt_sets = []
    run_ids = []
    for _ in range(1):
        payload = create_reference_run(client)
        run = payload["run"]
        run_ids.append(run["run_id"])
        response = client.post("/api/runs/" + run["run_id"] + "/resume",
                               json={"approve": True, "plan_hash": run["plan_hash"]})
        assert response.status_code == 200, response.text
        assert response.json()["run"]["completion"]["full_unit"] is True
        receipt_sets.append(response.json()["run"]["receipts"])
    duplicate = client.post("/api/runs", json={"goal": "Python evaluation"})
    assert duplicate.status_code == 409
    assert FakeProvider(isolated_local_configuration / "provider.sqlite3").effect_count() == 5
