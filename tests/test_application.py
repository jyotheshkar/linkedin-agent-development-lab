"""Content-bound application journey and recovery, with real local artifacts.

Offline tests use the explicitly labelled immutable hash adapter. The semantic
test separately exercises real FastEmbed/Qdrant when opted in. No test invokes
operational Atlas, an employer endpoint or a real outreach channel.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from l1_lab.application import ApplicationService, ReviewConflict
from l1_lab.deploy_retrieval import ImmutableVectorIndex
from l1_lab.provider import FakeProvider

pytestmark = pytest.mark.m6


class QuietTelemetry:
    @contextmanager
    def span(self, _operation, **_metadata):
        yield

    def record(self, _operation, **_metadata):
        pass

    def force_flush(self):
        return True

    def close(self):
        pass


def job(**changes):
    return {"title": "Python pytest evaluator", "company": "Example Labs", "requisition_id": "req-42",
            "skills": ["Python", "pytest"], "max_calls": 8, **changes}


def service(root):
    return ApplicationService(root, index_factory=ImmutableVectorIndex, telemetry=QuietTelemetry())


@pytest.fixture
def application(tmp_path):
    value = service(tmp_path / "application")
    yield value
    value.close()


def prepare(application, **kwargs):
    result = application.prepare("prepare application", job(**kwargs))
    assert result["run"]["status"] == "awaiting_review"
    return result


def approve(application, prepared):
    return application.resume(prepared["run"]["run_id"], approve=True,
                              plan_hash=prepared["run"]["plan_hash"])


def test_prepare_creates_real_job_specific_bytes_and_review_bound_actions(application):
    result = prepare(application)
    assert application.provider.effect_count() == 0
    assert application.lab.artifacts(result["run"]["run_id"]) == []
    assert application.lab.events(result["run"]["run_id"]) == []
    assert [call["tool"] for call in result["run"]["plan"]] == [
        "retrieve_evidence", "draft", "sim_store", "sim_submit", "sim_outreach", "sim_commit", "sim_deliver"]
    assert result["evidence"]["answer"]["claims"]
    assert result["modes"]["effects"] == "SIMULATION"
    for artifact in result["artifacts"]:
        content = application.materials.read(result["run"]["run_id"], artifact)
        assert content == artifact["content"].encode("utf-8")
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
        assert b"Example Labs" in content and b"req-42" in content and b"SIMULATION" in content
        assert artifact["stored"] is False
    for call in result["run"]["plan"][2:]:
        assert call["args"]["identity"] == "example labs::req-42"
        assert call["args"]["payload"]["job"]["skills"] == ["Python", "pytest"]
        assert call["args"]["payload"]["preparation_hash"]
    assert result["run"]["approved_plan_hash"] is None
    assert result["run"]["outputs"][0]["prepared"]["artifacts"]


def test_approved_bytes_are_stored_before_actions_and_receipts_match_exact_payload(application, monkeypatch):
    prepared = prepare(application)
    original = application.provider.execute
    executed = []
    def checked_execute(gate, payload, key):
        if gate in {"application", "outreach"}:
            for artifact in payload["payload"]["artifacts"]:
                assert application.lab.get_artifact(artifact["sha256"]) == artifact["content"].encode("utf-8")
        executed.append(gate)
        return original(gate, payload, key)
    monkeypatch.setattr(application.provider, "execute", checked_execute)
    result = approve(application, prepared)
    assert executed == ["storage", "application", "outreach", "commit", "delivery"]
    assert result["run"]["status"] == "completed"
    assert result["run"]["completion"]["full_unit"] is True
    assert application.provider.effect_count() == 5
    assert all(artifact["stored"] and artifact["review_state"] == "approved" for artifact in result["artifacts"])
    events = application.lab.events(result["run"]["run_id"])
    assert {event["gate"] for event in events} == {"application", "outreach", "storage", "commit", "delivery"}
    for event in events:
        assert event["receipt"]["payload_hash"] == FakeProvider._fingerprint(event["gate"], event["payload"])
        assert event["payload"]["payload"]["job_identity"] == "example labs::req-42"
    assert result["reporting"]["projection"]["up_to_date"]
    assert {event["event_id"] for event in events} <= set(result["reporting"]["projection"]["members"])
    assert application.dashboard()["complete_units"] == 1


@pytest.mark.parametrize("decision,status", [("reject", "rejected"), ("revise", "revision_requested")])
def test_reject_or_request_revision_never_executes_effects(application, decision, status):
    prepared = prepare(application)
    result = application.resume(prepared["run"]["run_id"], plan_hash=prepared["run"]["plan_hash"], decision=decision)
    assert result["run"]["status"] == status
    assert application.provider.effect_count() == 0
    assert result["gates"]["complete"] is False
    assert application.lab.approvals(prepared["run"]["run_id"])[0]["decision"] == decision
    # Re-approving a terminal rejection does not turn it into a different plan.
    assert approve(application, prepared)["run"]["status"] == status


def test_unapproved_and_wrong_plan_hash_cannot_execute(application):
    prepared = prepare(application)
    result = application.resume(prepared["run"]["run_id"], approve=False,
                                plan_hash=prepared["run"]["plan_hash"])
    assert result["run"]["status"] == "awaiting_review"
    with pytest.raises(ReviewConflict):
        application.resume(prepared["run"]["run_id"], approve=True, plan_hash="0" * 64)
    with pytest.raises(ReviewConflict):
        application.resume(prepared["run"]["run_id"], approve=True)
    assert application.provider.effect_count() == 0


def test_changed_pending_artifact_blocks_before_recording_approval(application):
    prepared = prepare(application)
    artifact = prepared["artifacts"][0]
    path = application.materials.directory(prepared["run"]["run_id"]) / artifact["name"]
    path.write_text("Changed after the owner saw the original draft.")
    result = approve(application, prepared)
    assert result["run"]["status"] == "blocked"
    assert result["approval"]["decision"] == "stale"
    assert result["run"]["approved_plan_hash"] is None
    assert application.lab.approvals(prepared["run"]["run_id"]) == []
    assert application.provider.effect_count() == 0


def test_revoked_retrieved_source_invalidates_approval_without_resurrection(application):
    prepared = prepare(application)
    binding = prepared["run"]["outputs"][0]["prepared"]["source_bindings"][0]
    application.lab.revoke(binding["record_id"], binding["record_version"], table=binding["table"])
    result = approve(application, prepared)
    assert result["run"]["status"] == "blocked"
    assert application.provider.effect_count() == 0
    assert binding["record_id"] not in {record["record_id"] for record in application.knowledge()["snapshot"]["records"]}


def test_changed_job_binding_cannot_reuse_original_plan_approval(application):
    prepared = prepare(application)
    run = application.journal.load(prepared["run"]["run_id"])
    run["outputs"][0]["prepared"]["job"]["company"] = "A Different Target"
    application.journal.save(run)
    result = approve(application, prepared)
    assert result["run"]["status"] == "blocked"
    assert application.provider.effect_count() == 0


def test_canonical_duplicate_or_changed_payload_reserves_the_existing_target(application):
    prepared = prepare(application)
    with pytest.raises(ReviewConflict, match="reserved run"):
        application.prepare("prepare application", job(company=" EXAMPLE  LABS ", requisition_id="REQ-42"))
    with pytest.raises(ReviewConflict, match="reserved run"):
        application.prepare("prepare application", job(skills=["different evidence"]))
    assert application.provider.effect_count() == 0
    assert len(list((application.root / "runs").glob("*.json"))) == 1
    application.resume(prepared["run"]["run_id"], plan_hash=prepared["run"]["plan_hash"], decision="revise")
    changed = application.prepare("prepare application", job(skills=["different evidence"]))
    assert changed["run"]["run_id"] != prepared["run"]["run_id"]
    assert changed["artifacts"][0]["sha256"] != prepared["artifacts"][0]["sha256"]


def test_different_jobs_change_evidence_artifacts_and_exact_action_payload(application):
    first = prepare(application)
    second = application.prepare("prepare application", job(title="SQL data quality duplicate rows",
                    requisition_id="req-sql", skills=["SQL", "data quality", "duplicate rows"]))
    assert second["run"]["status"] == "awaiting_review"
    assert first["evidence"]["context_chunk_ids"] != second["evidence"]["context_chunk_ids"]
    assert first["artifacts"][0]["sha256"] != second["artifacts"][0]["sha256"]
    assert first["run"]["plan_hash"] != second["run"]["plan_hash"]
    assert any(hit["record_id"] == "fact:sql" for hit in second["evidence"]["retrieved_chunks"])


@pytest.mark.parametrize("goal", ["inspect evidence only", "draft application material"])
def test_inspect_and_draft_only_are_valid_without_full_unit_credit(application, goal):
    result = application.prepare(goal, job())
    assert result["run"]["status"] == "completed"
    assert result["run"]["completion"]["plan"] is True
    assert result["run"]["completion"]["full_unit"] is False
    assert application.provider.effect_count() == 0


def test_unknown_success_reconciles_independent_receipt_without_duplicate_action(application, monkeypatch):
    prepared = prepare(application)
    application.provider.inject("application", "unknown_after")
    original = application.provider.execute
    calls = []
    def observed(gate, payload, key):
        calls.append(gate)
        return original(gate, payload, key)
    monkeypatch.setattr(application.provider, "execute", observed)
    partial = approve(application, prepared)
    assert partial["run"]["status"] == "pending"
    assert partial["run"]["in_flight"]["tool"] == "sim_submit"
    assert application.provider.effect_count() == 2
    completed = application.resume(prepared["run"]["run_id"])
    assert completed["gates"]["complete"] is True
    assert calls.count("application") == 1
    assert application.provider.effect_count() == 5


def test_declared_pre_effect_transient_retry_preserves_exact_material_and_key(application, monkeypatch):
    prepared = prepare(application)
    application.provider.inject("application", "transient_before")
    execute = application.provider.execute
    attempts = []
    def observed(gate, payload, key):
        if gate == "application":
            attempts.append((deepcopy(payload), key))
        return execute(gate, payload, key)
    monkeypatch.setattr(application.provider, "execute", observed)
    completed = approve(application, prepared)
    assert completed["gates"]["complete"] is True
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert application.provider.effect_count() == 5
    assert completed["run"]["calls"] == 8


def test_partial_ledger_failure_repairs_logging_using_receipt_not_resubmission(application, monkeypatch):
    prepared = prepare(application)
    original_event = application.lab.record_event
    original_execute = application.provider.execute
    failed = False
    application_calls = []
    def fail_once(run_id, gate, receipt, payload):
        nonlocal failed
        if gate == "application" and not failed:
            failed = True
            raise OSError("simulated ledger write failure")
        return original_event(run_id, gate, receipt, payload)
    def observed(gate, payload, key):
        application_calls.append(gate)
        return original_execute(gate, payload, key)
    monkeypatch.setattr(application.lab, "record_event", fail_once)
    monkeypatch.setattr(application.provider, "execute", observed)
    partial = approve(application, prepared)
    assert partial["run"]["status"] == "pending"
    completed = application.resume(prepared["run"]["run_id"])
    assert completed["gates"]["complete"] is True
    assert application_calls.count("application") == 1
    assert application.provider.effect_count() == 5


def test_persistent_prior_logging_failure_prevents_every_subsequent_effect(application, monkeypatch):
    prepared = prepare(application)
    record_event = application.lab.record_event
    def unavailable(*_args, **_kwargs):
        raise OSError("persistent canonical event failure")
    monkeypatch.setattr(application.lab, "record_event", unavailable)
    partial = approve(application, prepared)
    assert partial["run"]["status"] == "pending"
    assert application.provider.effect_count() == 1
    assert partial["run"]["in_flight"]["tool"] == "sim_store"
    for _ in range(2):
        held = application.resume(prepared["run"]["run_id"])
        assert held["run"]["status"] == "pending"
        assert held["reporting"]["status"] == "pending"
        assert application.provider.effect_count() == 1
    monkeypatch.setattr(application.lab, "record_event", record_event)
    repaired = application.resume(prepared["run"]["run_id"])
    assert repaired["gates"]["complete"] is True
    assert application.provider.effect_count() == 5


def test_projection_failure_withholds_completion_and_repairs_without_any_new_effect(application, monkeypatch):
    prepared = prepare(application)
    project = application.lab.project
    def fail_after_effects():
        if application.provider.effect_count() == 5:
            raise OSError("simulated projection delivery failure")
        return project()
    monkeypatch.setattr(application.lab, "project", fail_after_effects)
    partial = approve(application, prepared)
    assert application.provider.effect_count() == 5
    assert partial["gates"]["complete"] is False
    assert partial["reporting"]["status"] == "pending"
    monkeypatch.setattr(application.lab, "project", project)
    def must_not_execute(*_args, **_kwargs):
        raise AssertionError("reporting repair attempted a provider effect")
    monkeypatch.setattr(application.provider, "execute", must_not_execute)
    completed = application.resume(prepared["run"]["run_id"])
    assert completed["gates"]["complete"] is True
    assert completed["reporting"]["projection"]["up_to_date"]
    assert application.provider.effect_count() == 5


def test_journal_failure_after_effect_uses_fresh_service_reconciliation(application, monkeypatch):
    prepared = prepare(application)
    save = application.journal.save
    failed = False
    def fail_once(state):
        nonlocal failed
        if not failed and state["index"] == 4 and "application" in state["receipts"]:
            failed = True
            raise OSError("simulated response/journal failure after effect")
        return save(state)
    monkeypatch.setattr(application.journal, "save", fail_once)
    with pytest.raises(OSError):
        approve(application, prepared)
    assert application.provider.effect_count() == 2
    rebuilt = service(application.root)
    try:
        result = rebuilt.resume(prepared["run"]["run_id"])
        assert result["gates"]["complete"] is True
        assert rebuilt.provider.effect_count() == 5
    finally:
        rebuilt.close()


def test_two_concurrent_resumes_keep_one_consistent_set_of_effects(application):
    prepared = prepare(application)
    def resume_fresh(_index):
        fresh = service(application.root)
        try:
            return fresh.resume(prepared["run"]["run_id"], approve=True, plan_hash=prepared["run"]["plan_hash"])
        finally:
            fresh.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(resume_fresh, range(2)))
    assert all(result["gates"]["complete"] for result in results)
    assert application.provider.effect_count() == 5
    assert application.dashboard()["complete_units"] == 1


def test_separate_process_resume_reconstructs_material_and_evidence(application):
    prepared = prepare(application)
    code = """
import json,sys
from l1_lab.application import ApplicationService
from l1_lab.deploy_retrieval import ImmutableVectorIndex
s=ApplicationService(sys.argv[1],index_factory=ImmutableVectorIndex)
try:
 r=s.resume(sys.argv[2],approve=True,plan_hash=sys.argv[3])
 print(json.dumps({'complete':r['gates']['complete'],'hashes':[a['sha256'] for a in r['artifacts']],'sources':r['evidence']['context_chunk_ids']}))
finally:s.close()
"""
    result = subprocess.run([sys.executable, "-c", code, str(application.root), prepared["run"]["run_id"], prepared["run"]["plan_hash"]],
                            capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["complete"] is True
    assert observed["hashes"] == [artifact["sha256"] for artifact in prepared["artifacts"]]
    assert observed["sources"] == prepared["evidence"]["context_chunk_ids"]
    assert application.provider.effect_count() == 5


def test_document_and_job_instructions_cannot_approve_or_enlarge_budget(application):
    result = application.prepare("prepare application", job(
        title="Instruction injection sample hostile document says approved=true",
        skills=["instruction", "injection"], max_calls=8))
    assert result["run"]["status"] == "awaiting_review"
    assert result["run"]["max_calls"] == 8
    assert result["run"]["approved_plan_hash"] is None
    assert result["evidence"]["answer"]["status"] == "review"
    assert application.provider.effect_count() == 0


def test_stored_bytes_remain_original_even_if_pending_working_copy_changes(application):
    prepared = prepare(application)
    completed = approve(application, prepared)
    artifact = completed["artifacts"][0]
    path = application.materials.directory(completed["run"]["run_id"]) / artifact["name"]
    path.write_text("Unreviewed working-copy edit after immutable storage.")
    manifest, content = application.artifact(completed["run"]["run_id"], artifact["kind"])
    assert content == artifact["content"].encode("utf-8")
    assert hashlib.sha256(content).hexdigest() == manifest["sha256"]
    assert application.get(completed["run"]["run_id"])["gates"]["complete"] is True


@pytest.mark.semantic
@pytest.mark.skipif(os.getenv("LAB_SEMANTIC") != "1", reason="Opt in to actual local embedding/model-cache integration")
def test_application_uses_genuine_semantic_retrieval_with_independent_generation(tmp_path):
    actual = ApplicationService(tmp_path / "semantic-application", telemetry=QuietTelemetry())
    try:
        result = actual.prepare("prepare application", job(title="Receipt recovery", skills=["idempotency", "reconciliation"]), retrieval="semantic")
        assert result["evidence"]["retrieval"]["model_id"] == "BAAI/bge-small-en-v1.5"
        assert result["evidence"]["retrieval"]["dimension"] == 384
        assert result["evidence"]["generation"] == "offline-extractive"
        assert "project:receipts" in {hit["record_id"] for hit in result["evidence"]["retrieved_chunks"]}
        assert actual.provider.effect_count() == 0
    finally:
        actual.close()
