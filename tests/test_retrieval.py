from copy import deepcopy
from pathlib import Path
import math
import pytest

from l1_lab.knowledge import chunk_records, load_snapshot, select_records
from l1_lab.retrieval import HashEmbedding, VectorIndex, rank_hits

pytestmark = pytest.mark.m4
FIXTURE = Path(__file__).resolve().parents[1] / "data" / "synthetic_snapshot.json"


def hit(cid, score, **metadata):
    return {"chunk_id": cid, "record_id": "r:" + cid, "text": "Evidence " + cid, "score": score, "metadata": metadata}


def test_rank_filters_before_top_k_and_ties_are_stable():
    hits = [hit("b", .9, topic="python"), hit("a", .9, topic="python"), hit("z", .99, topic="sql"), hit("c", .1, topic="python")]
    before = deepcopy(hits)
    assert [item["chunk_id"] for item in rank_hits(hits, 1, .2, {"topic": "python"})] == ["a"]
    assert hits == before


@pytest.mark.parametrize("score", [True, float("nan"), float("inf"), 1.5, "0.9"])
def test_invalid_scores(score):
    with pytest.raises(ValueError):
        rank_hits([hit("a", score)])


@pytest.mark.parametrize("top_k,min_score", [(True,.2),(0,.2),(101,.2),(2,True),(2,float("nan")),(2,-2)])
def test_invalid_rank_parameters(top_k,min_score):
    with pytest.raises(ValueError):
        rank_hits([],top_k,min_score)


def test_duplicate_ids_and_unknown_filter_return_empty():
    with pytest.raises(ValueError, match="duplicate"):
        rank_hits([hit("a", .8), hit("a", .7)])
    assert rank_hits([hit("a", .8)], filters={"maturity": "deployed"}) == []


@pytest.mark.infrastructure
def test_hash_embedding_is_normalized_deterministic_test_double():
    adapter = HashEmbedding()
    vectors = adapter.embed(["Python test", "Python test", ""])
    assert vectors[0] == vectors[1]
    assert math.isclose(sum(value*value for value in vectors[0]), 1)
    assert all(value == 0 for value in vectors[2])
    assert adapter.model_id.startswith("test-double:")


def test_qdrant_offline_expected_retrieval_and_abstention():
    chunks = chunk_records(select_records(load_snapshot(FIXTURE)))
    with VectorIndex(chunks) as index:
        results = index.search("SQL operational tables duplicate rows data quality", top_k=1)
        assert results[0]["record_id"] == "fact:sql"
        assert index.search("Astrophysics gravitational redshift galaxies cosmology", min_score=.7) == []
        assert index.manifest["mode"] == "offline"
        assert index.manifest["vector_store"] == "qdrant-local"


def test_rebuild_removes_old_evidence_and_disk_local_reopens(tmp_path):
    chunks = chunk_records(select_records(load_snapshot(FIXTURE)))
    path = tmp_path / "vectors"
    with VectorIndex(chunks, path=path) as index:
        assert index.search("SQL operational tables", filters={"topic": "sql"})
        index.rebuild([chunk for chunk in chunks if chunk["record_id"] != "fact:sql"])
        assert index.search("SQL operational tables", filters={"topic": "sql"}) == []
    with VectorIndex([],path=path) as index:
        assert index.search("SQL") == []


def test_retrieval_refuses_live_or_remote_configuration():
    with pytest.raises(ValueError, match="mode"):
        VectorIndex([], mode="live")
