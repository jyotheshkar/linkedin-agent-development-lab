"""Stateless hosted *offline* retrieval with no Qdrant, ONNX or file writes.

This is a deployment adapter for the explicitly labelled deterministic test
double. It is not hosted semantic retrieval. The local lab's FastEmbed/Qdrant
path remains the semantic exercise. Neither a vector cache nor cosine ranking
turns hashed word counts into learned embeddings.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from .knowledge import _no_sensitive_keys
from .retrieval import HashEmbedding, rank_hits


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _validate_chunks(chunks: list[dict]) -> list[dict]:
    if not isinstance(chunks, list) or len(chunks) > 2000:
        raise ValueError("hosted chunks must be a list of at most 2000 items")
    _no_sensitive_keys(chunks)
    ids: set[str] = set()
    revisions: set[int] = set()
    source_versions: dict[tuple[str, str], tuple[int, str]] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("each chunk must be an object")
        for name in ("chunk_id", "record_id", "text", "content_hash", "source_ref"):
            if not isinstance(chunk.get(name), str) or not chunk[name].strip():
                raise ValueError(f"hosted chunk requires {name}")
        if chunk["chunk_id"] in ids:
            raise ValueError("duplicate hosted chunk ID")
        ids.add(chunk["chunk_id"])
        if chunk.get("approval_status") != "APPROVED" or chunk.get("superseded", False):
            raise ValueError("hosted retrieval accepts selected approved chunks only")
        if chunk.get("table") not in ("Candidate_Facts", "Project_Registry"):
            raise ValueError("unsupported hosted source table")
        if not chunk["source_ref"].startswith("synthetic:fixture:"):
            raise ValueError("public hosted demonstrations accept synthetic fixture evidence only")
        if not re.fullmatch(r"[0-9a-f]{64}", chunk["content_hash"]) or len(chunk["text"]) > 4000:
            raise ValueError("hosted source hash or text bound is invalid")
        if not isinstance(chunk.get("metadata", {}), dict):
            raise ValueError("hosted metadata must be an object")
        if type(chunk.get("record_version")) is not int or chunk["record_version"] < 1:
            raise ValueError("invalid hosted source record version")
        source_identity = (chunk["table"], chunk["record_id"])
        source_version = (chunk["record_version"], chunk["content_hash"])
        if source_identity in source_versions and source_versions[source_identity] != source_version:
            raise ValueError("mixed versions or hashes for the same hosted source record")
        source_versions[source_identity] = source_version
        if type(chunk.get("snapshot_revision")) is not int or chunk["snapshot_revision"] < 0:
            raise ValueError("invalid hosted snapshot revision")
        revisions.add(chunk["snapshot_revision"])
        actual_text_hash = hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest()
        if chunk.get("chunk_text_hash") != actual_text_hash:
            raise ValueError("hosted chunk text does not match its frozen hash")
    if len(revisions) > 1:
        raise ValueError("mixed snapshot revisions in hosted chunks")
    return deepcopy(chunks)


def build_offline_cache(chunks: list[dict]) -> dict:
    """Build a reproducible synthetic cache; never calls a remote API."""
    selected = _validate_chunks(chunks)
    adapter = HashEmbedding()
    return {
        "schema_version": 1,
        "mode": "offline",
        "source_kind": "synthetic",
        "semantic_embeddings": False,
        "model_id": adapter.model_id,
        "dimension": adapter.dimension,
        "normalization": adapter.normalization,
        "chunks_fingerprint": hashlib.sha256(_canonical(selected).encode("utf-8")).hexdigest(),
        "chunk_ids": [chunk["chunk_id"] for chunk in selected],
        "vectors": adapter.embed([chunk["text"] for chunk in selected]),
    }


class ImmutableVectorIndex:
    """Read-only in-memory cosine search for general offline questions.

    The already-selected chunks are frozen at construction. A cached artifact
    must exactly match their current version/provenance/text fingerprint. Removed
    or revoked chunks therefore invalidate an old cache; rebuild the artifact
    from the new selected snapshot. This does not poll or synchronize Atlas.
    """

    def __init__(self, chunks: list[dict], mode: str = "offline", path: str | Path | None = None,
                 cache_path: str | Path | None = None):
        if mode != "offline":
            raise ValueError("hosted immutable retrieval supports offline test-double mode only; semantic retrieval uses the local lab")
        if path is not None:
            raise ValueError("stateless hosted retrieval has no writable database path")
        self._chunks = _validate_chunks(chunks)
        self.embedding = HashEmbedding()
        expected = build_offline_cache(self._chunks)
        artifact = expected
        if cache_path is not None:
            cache_path = Path(cache_path)
            if cache_path.stat().st_size > 10_000_000:
                raise ValueError("vector cache exceeds hosted lab limit")
            artifact = json.loads(cache_path.read_text(encoding="utf-8"))
            # Deterministic vectors are cheap to recompute, allowing corruption
            # checks as well as stale-source checks without trusting cache labels.
            if _canonical(artifact) != _canonical(expected):
                raise ValueError("vector cache is stale, corrupted or uses a different model; rebuild it")
        self._vectors = deepcopy(artifact["vectors"])
        self.chunk_count = len(self._chunks)
        self.manifest = {
            "mode": "offline",
            "model_id": self.embedding.model_id,
            "dimension": self.embedding.dimension,
            "normalization": self.embedding.normalization,
            "vector_store": "immutable-in-memory-cosine",
            "backend": "stateless-standard-library",
            "source_kind": "synthetic",
            "semantic_embeddings": False,
            "query_embedding": "deterministic hashed word counts, not semantic inference",
            "generation": "not configured by retrieval",
            "chunks_fingerprint": expected["chunks_fingerprint"],
            "cache_loaded": cache_path is not None,
        }

    def search(self, query: str, top_k: int = 3, min_score: float = .2,
               filters: dict | None = None) -> list[dict]:
        rank_hits([], top_k=top_k, min_score=min_score, filters=filters)
        if not isinstance(query, str) or not query.strip() or len(query) > 10_000:
            raise ValueError("query must contain 1..10000 characters")
        query_vector = self.embedding.embed([query])[0]
        hits = []
        for chunk, vector in zip(self._chunks, self._vectors):
            score = math.fsum(left * right for left, right in zip(vector, query_vector))
            # Roundoff can exceed 1 by a few ulps for normalized identical text.
            hits.append({**deepcopy(chunk), "score": max(-1., min(1., score))})
        return rank_hits(hits, top_k=top_k, min_score=min_score, filters=filters)

    def rebuild(self, _chunks: list[dict]) -> None:
        raise ValueError("immutable hosted index cannot be rebuilt in a request; construct it from a new snapshot")

    def close(self) -> None:
        pass

    def __enter__(self) -> "ImmutableVectorIndex":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
