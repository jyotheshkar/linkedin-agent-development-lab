"""Create an inspectable OFFLINE vector cache from approved synthetic records.

Run on coach-reference, or after implementing M3:
    uv run python scripts/build_vector_cache.py

The result remains an explicitly labelled test double. Genuine semantic local
retrieval uses FastEmbed/Qdrant; hosted semantic query inference is not supplied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from l1_lab.deploy_retrieval import build_offline_cache
from l1_lab.knowledge import chunk_records, load_snapshot, select_records


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build offline hashed-vector cache; no API keys or network")
    parser.add_argument("--snapshot", type=Path, default=root / "data" / "synthetic_snapshot.json")
    parser.add_argument("--output", type=Path, default=root / ".lab" / "vector_cache.json")
    args = parser.parse_args(argv)
    snapshot = load_snapshot(args.snapshot)
    if snapshot["kind"] != "synthetic":
        raise ValueError("hosted cache builder accepts only the synthetic fixture")
    cache = build_offline_cache(chunk_records(select_records(snapshot)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cache, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(args.output), "mode": cache["mode"],
                      "semantic_embeddings": False, "chunk_count": len(cache["chunk_ids"]),
                      "model_id": cache["model_id"], "dimension": cache["dimension"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
