"""Executable SQLite contracts; no model, network or operational Atlas needed."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from l1_lab.atlas_lab import AtlasLab, IntegrityError, ReadOnlySource, VersionConflict
from l1_lab.provider import FakeProvider


def record(record_id="fact:one", version=1, status="APPROVED", text="Synthetic Python evaluation evidence.", revision=10):
    return {"record_id": record_id, "record_version": version, "approval_status": status,
        "table": "Candidate_Facts", "source_ref": "synthetic:fixture:" + record_id,
        "source_version": "source-" + str(version), "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "text": text, "snapshot_revision": revision, "retrieved_at": "2026-11-14T12:00:00Z",
        "metadata": {"topic": "python"}}


def snapshot(records=None, revision=10, kind="synthetic"):
    return {"schema_version": 1, "kind": kind, "revision": revision,
            "retrieved_at": "2026-11-14T12:00:00Z", "records": records if records is not None else [record(revision=revision)]}


class AtlasLabTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.lab = AtlasLab(self.root / "atlas")
        self.provider = FakeProvider(self.root / "provider.sqlite3")

    def tearDown(self):
        self.temporary.cleanup()

    def artifact(self, run_id="run_1", identity="example::req-1", content=b"# SIMULATION\nEvidence-backed draft.\n"):
        return self.lab.store_artifact(run_id, "application_brief", content, {
            "content_type": "text/markdown", "job_identity": identity,
            "evidence_ids": ["synthetic:chunk"], "generation_mode": "offline-extractive", "review_state": "approved"})

    def event(self, gate, run_id="run_1", identity="example::req-1", artifact=None, suffix="one", mode=None):
        artifact = artifact or self.artifact(run_id, identity)
        payload = {"identity": identity, "payload": {"job_identity": identity, "action": gate,
            "artifacts": [{key: artifact[key] for key in ("kind", "version", "sha256", "content_type", "byte_size")}],
            "source_bindings": [{"record_id": "synthetic:one", "record_version": 1}], "policy_version": "lab-v1"}}
        if mode:
            self.provider.inject(gate, mode)
        receipt = self.provider.execute(gate, payload, "sim-key:" + gate + "-" + suffix)
        return self.lab.record_event(run_id, gate, receipt, payload), receipt, payload

    def test_seed_does_not_overwrite_synthetic_review_on_restart(self):
        self.lab.seed_snapshot(snapshot())
        self.lab.revoke("fact:one", 1)
        self.assertEqual(self.lab.snapshot()["records"], [])
        rebuilt = AtlasLab(self.lab.root)
        self.assertFalse(rebuilt.seed_snapshot(snapshot())["seeded"])
        self.assertEqual(rebuilt.snapshot()["records"], [])
        self.assertEqual(rebuilt.list_records()[0]["approval_status"], "ARCHIVED")

    def test_synthetic_create_edit_review_and_revoke_are_immutable_versions(self):
        created = self.lab.put_synthetic({"record_id": "synthetic:new", "text": "Small Python prototype."})
        self.assertEqual(created["approval_status"], "REVIEW_REQUIRED")
        self.assertEqual(self.lab.snapshot()["records"], [])
        approved = self.lab.review("synthetic:new", 1, "APPROVED")
        self.assertEqual(approved["record_version"], 2)
        self.assertEqual(len(self.lab.snapshot()["records"]), 1)
        with self.assertRaises(VersionConflict):
            self.lab.put_synthetic({"record_id": "synthetic:new", "text": "Changed"}, expected_version=1)
        edited = self.lab.put_synthetic({"record_id": "synthetic:new", "text": "Changed contribution."}, expected_version=2)
        self.assertEqual(edited["record_version"], 3)
        self.assertEqual(self.lab.snapshot()["records"], [])
        self.lab.review("synthetic:new", 3, "APPROVED")
        self.lab.revoke("synthetic:new", 4)
        history = self.lab.list_records(include_history=True)
        self.assertEqual([item["record_version"] for item in history], [1, 2, 3, 4, 5])
        self.assertEqual(history[0]["text"], "Small Python prototype.")
        self.assertEqual(self.lab.snapshot()["records"], [])

    def test_imported_source_is_read_only_and_native_hash_stays_distinct(self):
        native = record()
        native["content_hash"] = "a" * 64  # Source hash is not the sanitized text hash.
        self.lab.import_snapshot(snapshot([native], kind="atlas_snapshot"))
        with self.assertRaises(ReadOnlySource):
            self.lab.review(native["record_id"], 1, "APPROVED")
        with self.assertRaises(ReadOnlySource):
            self.lab.put_synthetic({"record_id": native["record_id"], "text": "rewrite"}, expected_version=1)
        exported = self.lab.snapshot()["records"][0]
        self.assertEqual(exported["content_hash"], "a" * 64)
        self.assertNotEqual(exported["export_text_hash"], exported["content_hash"])
        self.assertEqual(exported["metadata"]["source_snapshot_revision"], 10)
        self.assertTrue(self.lab.list_records()[0]["read_only"])
        fork = self.lab.put_synthetic({"record_id": "synthetic:fork", "text": native["text"]})
        self.assertTrue(fork["source_ref"].startswith("synthetic:atlas-lab:"))
        self.assertEqual(fork["approval_status"], "REVIEW_REQUIRED")

    def test_atomic_refresh_removes_missing_revoked_and_unapproved_records(self):
        self.lab.import_snapshot(snapshot([record("fact:a"), record("fact:b")], kind="atlas_snapshot"))
        self.assertEqual(len(self.lab.snapshot()["records"]), 2)
        refreshed = snapshot([record("fact:a", revision=11),
            record("fact:a", version=2, status="ARCHIVED", revision=11),
            record("fact:c", status="REVIEW_REQUIRED", revision=11)], revision=11, kind="atlas_snapshot")
        self.lab.import_snapshot(refreshed)
        self.assertEqual(self.lab.snapshot()["records"], [])
        self.assertEqual({item["record_id"] for item in self.lab.list_records()}, {"fact:a", "fact:c"})
        self.assertEqual(len(self.lab.list_records(include_history=True)), 4)

    def test_conflicting_refresh_rolls_back_all_membership_and_revision_changes(self):
        self.lab.import_snapshot(snapshot(kind="atlas_snapshot"))
        before = self.lab.snapshot()
        conflicting = snapshot([record(text="Conflicting same native version", revision=11)], revision=11, kind="atlas_snapshot")
        with self.assertRaises(VersionConflict):
            self.lab.import_snapshot(conflicting)
        after = self.lab.snapshot()
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(after["records"], before["records"])
        self.assertEqual(len(self.lab.imports()), 1)

    def test_same_source_version_can_have_a_new_observation_without_rewriting_history(self):
        self.lab.import_snapshot(snapshot(kind="atlas_snapshot"))
        refreshed = record(revision=11)
        refreshed["retrieved_at"] = "2026-11-14T13:00:00Z"
        self.lab.import_snapshot(snapshot([refreshed], revision=11, kind="atlas_snapshot"))
        self.assertEqual(len(self.lab.list_records(include_history=True)), 1)
        self.assertEqual(self.lab.list_records(include_history=True)[0]["snapshot_revision"], 10)
        self.assertEqual(self.lab.list_records()[0]["snapshot_revision"], 11)
        exported = self.lab.snapshot()
        self.assertEqual(exported["records"][0]["snapshot_revision"], exported["revision"])
        self.assertEqual(exported["records"][0]["metadata"]["source_snapshot_revision"], 11)

    def test_stale_snapshot_or_record_version_cannot_resurrect_approved_evidence(self):
        self.lab.import_snapshot(snapshot([record(version=2, status="ARCHIVED", revision=11)], revision=11, kind="atlas_snapshot"))
        for stale in (snapshot(kind="atlas_snapshot"), snapshot([record(revision=12)], revision=12, kind="atlas_snapshot")):
            with self.assertRaises(VersionConflict):
                self.lab.import_snapshot(stale)
        self.assertEqual(self.lab.snapshot()["records"], [])

    def test_optimistic_collection_revision_and_malformed_source_validation(self):
        self.lab.import_snapshot(snapshot())
        with self.assertRaises(VersionConflict):
            self.lab.import_snapshot(snapshot(), expected_revision=0)
        bad = snapshot()
        bad["revision"] = True
        with self.assertRaises(ValueError):
            self.lab.import_snapshot(bad)
        bad = snapshot()
        bad["records"][0]["metadata"]["api_key"] = "synthetic-disallowed-field"
        with self.assertRaises(ValueError):
            self.lab.import_snapshot(bad)
        with self.assertRaises(ValueError):
            self.lab.put_synthetic({"record_id": "new", "text": "text"}, expected_version=True)

    def test_artifact_bytes_versions_and_retry_are_immutable_and_restart_safe(self):
        first = self.artifact()
        repeated = self.artifact()
        self.assertEqual(first, repeated)
        changed = self.artifact(content=b"# SIMULATION\nRevised supported draft.\n")
        self.assertEqual((first["version"], changed["version"]), (1, 2))
        self.assertNotEqual(first["sha256"], changed["sha256"])
        rebuilt = AtlasLab(self.lab.path)
        content = rebuilt.get_artifact(first["sha256"])
        self.assertEqual(hashlib.sha256(content).hexdigest(), first["sha256"])
        self.assertEqual(len(rebuilt.artifacts("run_1")), 2)
        with self.assertRaises(ValueError):
            rebuilt.get_artifact("../atlas.sqlite3")

    def test_tampered_artifact_is_detected_without_overwriting_it(self):
        manifest = self.artifact()
        target = self.lab.artifact_root / manifest["sha256"]
        target.write_bytes(b"tampered bytes")
        with self.assertRaises(IntegrityError):
            self.lab.get_artifact(manifest["sha256"])
        with self.assertRaises(IntegrityError):
            self.artifact()
        self.assertEqual(target.read_bytes(), b"tampered bytes")

    def test_invalid_artifact_bytes_and_private_metadata_are_rejected(self):
        for content in (b"", "not bytes"):
            with self.assertRaises(ValueError):
                self.lab.store_artifact("run_1", "brief", content)
        with self.assertRaises(ValueError):
            self.lab.store_artifact("run_1", "brief", b"text", [])
        with self.assertRaises(ValueError):
            self.lab.store_artifact("run_1", "brief", b"text", {"password": "not-allowed"})

    def test_five_distinct_events_need_separate_projection_membership_readback(self):
        event_ids = []
        for gate in ("storage", "application", "outreach", "commit", "delivery"):
            event, receipt, payload = self.event(gate)
            event_ids.append(event["event_id"])
            self.assertEqual(self.lab.record_event("run_1", gate, receipt, payload)["event_id"], event["event_id"])
        before = self.lab.projection()
        self.assertFalse(before["up_to_date"])
        self.assertEqual(before["ledger_revision"], 5)
        self.assertEqual(set(before["missing_event_ids"]), set(event_ids))
        after = self.lab.project()
        self.assertTrue(after["up_to_date"])
        self.assertEqual(set(after["members"]), set(event_ids))
        self.assertEqual(after["complete_units"], 1)
        self.assertEqual(self.provider.effect_count(), 5)

    def test_projection_failure_or_same_revision_membership_corruption_repairs_without_effect_repeat(self):
        event, _, _ = self.event("storage")
        with patch.object(self.lab, "project", side_effect=OSError("simulated projection failure")):
            with self.assertRaises(OSError):
                self.lab.project()
        rebuilt = AtlasLab(self.lab.path)
        self.assertEqual(rebuilt.events("run_1")[0]["event_id"], event["event_id"])
        projected = rebuilt.project()
        with rebuilt._connect(write=True) as db:
            corrupted = deepcopy(projected)
            corrupted["members"] = []
            db.execute("UPDATE reporting_projection SET payload_json=? WHERE singleton=1", (json.dumps(corrupted),))
        readback = rebuilt.projection()
        self.assertEqual(readback["revision"], readback["ledger_revision"])
        self.assertFalse(readback["up_to_date"])
        self.assertEqual(readback["missing_event_ids"], [event["event_id"]])
        self.assertTrue(rebuilt.project()["up_to_date"])
        self.assertEqual(len(rebuilt.events()), 1)
        self.assertEqual(self.provider.effect_count(), 1)

    def test_pending_delivery_is_not_complete_and_verified_observation_keeps_history(self):
        for gate in ("storage", "application", "outreach", "commit"):
            self.event(gate)
        pending, receipt, payload = self.event("delivery", mode="pending_after")
        self.assertEqual(self.lab.project()["complete_units"], 0)
        verified = self.provider.finalize(receipt["idempotency_key"])
        self.lab.record_event("run_1", "delivery", verified, payload)
        result = self.lab.project()
        self.assertEqual(result["complete_units"], 1)
        self.assertEqual(result["event_count"], 6)
        self.assertEqual(len(self.lab.events("run_1")), 5)
        self.assertEqual(len(self.lab.events("run_1", include_history=True)), 6)
        self.assertEqual(self.provider.effect_count(), 5)

    def test_event_cannot_rebind_changed_payload_or_unregistered_artifact_version(self):
        manifest = self.artifact()
        payload = {"identity": "example::req-1", "payload": {"job_identity": "example::req-1",
            "artifacts": [{"sha256": manifest["sha256"], "version": 99}]}}
        receipt = self.provider.execute("application", payload, "sim-key:bad-version")
        with self.assertRaises(IntegrityError):
            self.lab.record_event("run_1", "application", receipt, payload)
        payload["payload"]["artifacts"][0]["version"] = 1
        with self.assertRaises(IntegrityError):
            self.lab.record_event("run_1", "application", receipt, payload)
        self.assertEqual(self.lab.events(), [])
        self.assertEqual(self.lab.projection()["ledger_revision"], 0)

    def test_event_repair_rechecks_byte_hash_and_preserves_committed_evidence(self):
        event, receipt, payload = self.event("storage")
        digest = payload["payload"]["artifacts"][0]["sha256"]
        (self.lab.artifact_root / digest).write_bytes(b"corrupted")
        with self.assertRaises(IntegrityError):
            self.lab.record_event("run_1", "storage", receipt, payload)
        self.assertEqual(len(self.lab.events()), 1)
        self.assertEqual(self.lab.events()[0]["event_id"], event["event_id"])

    def test_concurrent_event_logging_has_one_canonical_event_and_revision(self):
        event, receipt, payload = self.event("storage")
        def log(_):
            return AtlasLab(self.lab.path).record_event("run_1", "storage", receipt, payload)
        with ThreadPoolExecutor(max_workers=6) as executor:
            outputs = list(executor.map(log, range(12)))
        self.assertEqual({item["event_id"] for item in outputs}, {event["event_id"]})
        self.assertEqual(len(self.lab.events()), 1)
        self.assertEqual(self.lab.projection()["ledger_revision"], 1)

    def test_action_approval_is_separate_from_knowledge_approval(self):
        self.lab.put_synthetic({"record_id": "synthetic:pending", "text": "A prototype claim."})
        manifest = {"target": "example::req-1", "artifacts": [self.artifact()["sha256"]], "policy": "lab-v1"}
        first = self.lab.save_approval("run_1", "a" * 64, "approve", manifest)
        self.assertEqual(self.lab.save_approval("run_1", "a" * 64, "approve", manifest)["approval_id"], first["approval_id"])
        rejected = self.lab.save_approval("run_1", "a" * 64, "reject", manifest)
        self.assertNotEqual(first["approval_id"], rejected["approval_id"])
        self.assertEqual(len(self.lab.approvals("run_1")), 2)
        self.assertEqual(self.lab.snapshot()["records"], [])
        self.assertEqual(self.lab.list_records()[0]["approval_status"], "REVIEW_REQUIRED")

    def test_generated_artifacts_and_events_never_enter_candidate_knowledge(self):
        self.lab.seed_snapshot(snapshot())
        before = self.lab.snapshot()["records"]
        self.event("application")
        self.lab.project()
        self.assertEqual(self.lab.snapshot()["records"], before)
        self.assertEqual(len(self.lab.artifacts()), 1)
        self.assertEqual(len(self.lab.events()), 1)


if __name__ == "__main__":
    unittest.main()
