"""Opt-in genuine ONNX embeddings plus local Qdrant, not fixed-vector proof."""
import os
from pathlib import Path
import pytest

from l1_lab.knowledge import chunk_records, load_snapshot, select_records
from l1_lab.retrieval import VectorIndex


@pytest.mark.semantic
@pytest.mark.skipif(os.getenv("LAB_SEMANTIC") != "1", reason="Set LAB_SEMANTIC=1 to download/use real local model weights")
def test_actual_fastembed_and_qdrant_semantic_path():
    fixture=Path(__file__).resolve().parents[1]/"data"/"synthetic_snapshot.json"
    chunks=chunk_records(select_records(load_snapshot(fixture)))
    with VectorIndex(chunks,mode="semantic") as index:
        hits=index.search("How are duplicate actions prevented after a network timeout?",top_k=3,min_score=.3)
        assert "project:receipts" in {hit["record_id"] for hit in hits}
        assert index.manifest["model_id"]=="BAAI/bge-small-en-v1.5"
        assert index.manifest["dimension"]==384
        assert index.manifest["normalization"]=="l2"
