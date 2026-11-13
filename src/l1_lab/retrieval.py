"""Two explicitly labelled embedding modes, one Qdrant local vector store.

offline = deterministic hashed word-count test double, NOT semantic evidence.
semantic = FastEmbed ONNX BAAI/bge-small-en-v1.5, no paid model API.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
import uuid


def _positive_int(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


class HashEmbedding:
    """Deterministic unit-test double; cosine here measures hashed token overlap."""

    model_id = "test-double:sha256-word-count-v1"
    dimension = 256
    normalization = "l2"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in re.findall(r"\b\w+\b", text.casefold()):
                position = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % self.dimension
                vector[position] += 1.0
            vectors.append(_normalize(vector))
        return vectors


class FastEmbedEmbedding:
    """Actual local ONNX model. First construction may download model weights."""

    model_id = "BAAI/bge-small-en-v1.5"
    dimension = 384
    normalization = "l2"

    def __init__(self, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=self.model_id, cache_dir=cache_dir, threads=2)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = [_normalize(vector.tolist()) for vector in self.model.embed(texts)]
        if any(len(vector) != self.dimension or not all(math.isfinite(v) for v in vector) for vector in result):
            raise ValueError("embedding model returned invalid dimensions or values")
        return result


def rank_hits(hits: list[dict], top_k: int = 3, min_score: float = 0.2, filters: dict | None = None) -> list[dict]:
    """M4: Filter and rank copied hits with deterministic tie-breaking.

    Accept finite cosine scores in [-1,1] and a finite threshold in [-1,1];
    Booleans are invalid numbers. Require chunk_id/record_id/text and score.
    Filters are exact equality on top-level provenance or metadata keys.
    Reject duplicate chunk IDs, then filter by score >= threshold and all filters;
    order by descending score, ascending chunk_id, return at most top_k copies.
    This relevance rule is calibrated only on the small labelled fixture set.
    """
    raise NotImplementedError("M4: implement rank_hits")


class VectorIndex:
    """Qdrant local only: no URL, endpoint, cloud API key or remote writes.

    Rebuild replaces the entire collection so removed/revoked/superseded records
    cannot linger. One process owns a disk path at a time; close before reopening.
    """

    collection_name = "l1_evidence"

    def __init__(self, chunks: list[dict], mode: str = "offline", path: str | Path | None = None):
        if mode not in {"offline", "semantic"}:
            raise ValueError("retrieval mode must be offline or semantic")
        from qdrant_client import QdrantClient

        self.mode = mode
        self.embedding = HashEmbedding() if mode == "offline" else FastEmbedEmbedding()
        self.client = QdrantClient(":memory:") if path is None else QdrantClient(path=str(path))
        self.manifest = {
            "mode": mode, "model_id": self.embedding.model_id,
            "dimension": self.embedding.dimension, "normalization": self.embedding.normalization,
            "vector_store": "qdrant-local", "generation": "not configured by retrieval",
        }
        self.rebuild(chunks)

    def rebuild(self, chunks: list[dict]) -> None:
        from qdrant_client import models

        if not isinstance(chunks, list):
            raise ValueError("chunks must be a list")
        ids = [chunk["chunk_id"] for chunk in chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate chunks")
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(self.collection_name, vectors_config=models.VectorParams(size=self.embedding.dimension, distance=models.Distance.COSINE))
        vectors = self.embedding.embed([chunk["text"] for chunk in chunks])
        if chunks:
            self.client.upsert(self.collection_name, points=[models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"])),
                vector=vector, payload=deepcopy(chunk),
            ) for chunk, vector in zip(chunks, vectors)], wait=True)
        self.chunk_count = len(chunks)

    def search(self, query: str, top_k: int = 3, min_score: float = 0.2, filters: dict | None = None) -> list[dict]:
        # Validate even when the collection is empty; keep the same M4 contract.
        rank_hits([], top_k=top_k, min_score=min_score, filters=filters)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be nonempty text")
        if not self.chunk_count:
            return []
        query_vector = self.embedding.embed([query])[0]
        points = self.client.query_points(collection_name=self.collection_name, query=query_vector, limit=self.chunk_count, with_payload=True).points
        return rank_hits([{**point.payload, "score": float(point.score)} for point in points], top_k=top_k, min_score=min_score, filters=filters)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "VectorIndex":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
