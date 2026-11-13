"""Hosted offline adapter tests; no Qdrant client or FastEmbed runtime needed."""

from copy import deepcopy
import hashlib
import json
import pytest

from l1_lab.deploy_retrieval import ImmutableVectorIndex, build_offline_cache


def chunk(cid="chunk:a", text="Python pytest structured JSON validation.", topic="python"):
    return {"chunk_id": cid, "record_id": "record:" + cid, "record_version": 1,
            "approval_status": "APPROVED", "table": "Candidate_Facts",
            "source_ref": "synthetic:fixture:" + cid, "source_version": "fixture-1",
            "content_hash": hashlib.sha256(("native:" + text).encode()).hexdigest(),
            "chunk_text_hash": hashlib.sha256(text.encode()).hexdigest(),
            "text": text, "snapshot_revision": 1,
            "retrieved_at": "2026-11-13T00:00:00Z", "metadata": {"topic": topic}}


@pytest.mark.infrastructure
def test_manifest_is_explicitly_nonsemantic_and_constructor_writes_nothing(tmp_path):
    with ImmutableVectorIndex([chunk()]) as index:
        assert index.manifest["semantic_embeddings"] is False
        assert index.manifest["mode"] == "offline"
        assert index.manifest["model_id"].startswith("test-double:")
        assert index.manifest["vector_store"] == "immutable-in-memory-cosine"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.infrastructure
@pytest.mark.parametrize("change", [
    {"approval_status": "REJECTED"}, {"superseded": True},
    {"source_ref": "atlas:private-record"}, {"record_version": True},
    {"table": "Outreach_Log"}, {"chunk_text_hash": "wrong"},
])
def test_hosted_source_selection_fails_closed(change):
    evidence = chunk()
    evidence.update(change)
    with pytest.raises(ValueError):
        ImmutableVectorIndex([evidence])


@pytest.mark.infrastructure
def test_no_semantic_or_writable_database_substitution():
    with pytest.raises(ValueError, match="offline"):
        ImmutableVectorIndex([], mode="semantic")
    with pytest.raises(ValueError, match="database"):
        ImmutableVectorIndex([], path="mutable-db")


@pytest.mark.infrastructure
def test_mixed_record_versions_cannot_bypass_prior_source_selection():
    first = chunk()
    second = {**deepcopy(first), "chunk_id": "chunk:next-version", "record_version": 2}
    with pytest.raises(ValueError, match="mixed versions"):
        ImmutableVectorIndex([first, second])


@pytest.mark.infrastructure
def test_cache_rejects_revoked_removed_version_changed_or_corrupt_sources(tmp_path):
    evidence = [chunk(), chunk("chunk:b", "SQL data quality joins.", "sql")]
    path = tmp_path / "vectors.json"
    cache = build_offline_cache(evidence)
    path.write_text(json.dumps(cache))
    assert ImmutableVectorIndex(evidence, cache_path=path).manifest["cache_loaded"]
    with pytest.raises(ValueError, match="stale"):
        ImmutableVectorIndex(evidence[:1], cache_path=path)
    newer = deepcopy(evidence)
    newer[0]["record_version"] = 2
    with pytest.raises(ValueError, match="stale"):
        ImmutableVectorIndex(newer, cache_path=path)
    cache["vectors"][0][0] += .01
    path.write_text(json.dumps(cache))
    with pytest.raises(ValueError, match="corrupted"):
        ImmutableVectorIndex(evidence, cache_path=path)


@pytest.mark.m4
def test_general_query_ranking_filtering_and_no_input_mutation():
    evidence = [chunk(), chunk("chunk:b", "SQL data quality joins.", "sql")]
    before = deepcopy(evidence)
    with ImmutableVectorIndex(evidence) as index:
        assert index.search("Python pytest JSON", top_k=1)[0]["chunk_id"] == "chunk:a"
        assert index.search("Python pytest JSON", filters={"topic": "sql"}, min_score=.8) == []
        assert index.search("SQL data quality joins", top_k=1)[0]["record_id"] == "record:chunk:b"
        with pytest.raises(ValueError, match="immutable"):
            index.rebuild([])
    assert evidence == before


@pytest.mark.m5
def test_returned_evidence_citations_validate_against_frozen_selected_context():
    from l1_lab.grounding import OfflineGenerator, validate_answer

    with ImmutableVectorIndex([chunk()]) as index:
        hits = index.search("Python pytest JSON")
        answer = OfflineGenerator().generate("Python pytest JSON", hits)
        assert answer["claims"][0]["evidence_ids"] == ["chunk:a"]
        assert validate_answer(answer, hits)["status"] == "supported"
