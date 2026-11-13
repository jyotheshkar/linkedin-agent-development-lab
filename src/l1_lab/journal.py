"""Atomic local run journal. Provider receipts live in a separate database."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


class Journal:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
            raise ValueError("invalid run ID")
        return self.root / f"{run_id}.json"

    def save(self, state: dict) -> None:
        path = self._path(state["run_id"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(temporary, path)

    def load(self, run_id: str) -> dict:
        return json.loads(self._path(run_id).read_text(encoding="utf-8"))

    def exists(self, run_id: str) -> bool:
        return self._path(run_id).exists()
