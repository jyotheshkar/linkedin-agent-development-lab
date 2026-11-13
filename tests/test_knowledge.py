from copy import deepcopy
import json
from pathlib import Path
import pytest

from l1_lab.knowledge import AtlasSnapshotSource, chunk_records, load_snapshot, select_records

FIXTURE = Path(__file__).resolve().parents[1] / "data" / "synthetic_snapshot.json"
pytestmark = pytest.mark.m3


def snapshot():
    return load_snapshot(FIXTURE)


def test_latest_revocation_does_not_resurrect_old_approval():
    records = select_records(snapshot())
    assert "fact:retired" not in {record["record_id"] for record in records}
    assert "fact:unapproved" not in {record["record_id"] for record in records}
    assert len(records) == 11


def test_equal_duplicate_collapses_but_conflicting_same_version_fails():
    data = snapshot()
    data["records"].append(deepcopy(data["records"][0]))
    assert len(select_records(data)) == 11
    data["records"][-1]["text"] = "A different claim at the same version"
    with pytest.raises(ValueError, match="contradictory"):
        select_records(data)


def test_selection_preserves_native_hash_and_keeps_text_hash_separate():
    data = snapshot()
    before = deepcopy(data)
    selected = select_records(data)
    assert selected[0]["content_hash"] != selected[0]["export_text_hash"]
    assert data == before
    selected[0]["metadata"]["changed"] = True
    assert data == before


@pytest.mark.parametrize("field,value", [("record_version", True), ("record_version", 0), ("table", "Outreach_Log"), ("content_hash", "fake"), ("text", "")])
def test_bad_record_contract(field, value):
    data = snapshot()
    data["records"][0][field] = value
    with pytest.raises(ValueError):
        select_records(data)


def test_mixed_revisions_fail_and_sensitive_metadata_is_rejected():
    data = snapshot()
    data["records"][0]["snapshot_revision"] = 2
    with pytest.raises(ValueError, match="mixed"):
        select_records(data)
    data = snapshot()
    data["records"][0]["metadata"]["recipient"] = "not copied"
    with pytest.raises(ValueError, match="sensitive"):
        select_records(data)


def test_chunks_retain_provenance_and_change_identity_with_version():
    records = select_records(snapshot())[:1]
    before = deepcopy(records)
    chunks = chunk_records(records, max_chars=80)
    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 80 for chunk in chunks)
    assert all(chunk["content_hash"] == records[0]["content_hash"] for chunk in chunks)
    assert all(chunk["source_ref"] == records[0]["source_ref"] for chunk in chunks)
    assert chunks == chunk_records(records, max_chars=80)
    records[0]["record_version"] += 1
    assert chunks[0]["chunk_id"] != chunk_records(records, max_chars=80)[0]["chunk_id"]
    assert before[0]["text"] == records[0]["text"]


@pytest.mark.parametrize("size", [True, 0, 39, 4001])
def test_bad_chunk_size(size):
    with pytest.raises(ValueError):
        chunk_records([], max_chars=size)


def test_empty_and_duplicate_chunk_records():
    assert chunk_records([]) == []
    records = select_records(snapshot())[:1]
    with pytest.raises(ValueError, match="duplicate"):
        chunk_records(records + records)


def test_nonapproved_chunk_input_fails():
    record = snapshot()["records"][0]
    record["approval_status"] = "REJECTED"
    with pytest.raises(ValueError, match="approved"):
        chunk_records([record])


@pytest.mark.infrastructure
def test_file_source_is_explicit_snapshot_not_live():
    assert AtlasSnapshotSource(FIXTURE).load()["kind"] == "synthetic"


@pytest.mark.infrastructure
def test_bad_envelopes_and_live_kind(tmp_path):
    for value in ([], {"schema_version": True}, {"schema_version": 1, "kind": "live"}):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(value))
        with pytest.raises(ValueError):
            load_snapshot(path)
