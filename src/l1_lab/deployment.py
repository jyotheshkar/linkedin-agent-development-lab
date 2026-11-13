"""Configuration and release boundaries for the single-owner simulation console."""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .resources import ROOT, DATA_DIR, PACKAGE_DIR


def unfinished_tasks(root: Path | None = None) -> list[dict]:
    """Inspect declared exercise bodies; do not run or fill student functions."""
    manifest = root / "data/student_tasks.json" if root else DATA_DIR / "student_tasks.json"
    tasks = json.loads(manifest.read_text(encoding="utf-8"))["tasks"]
    remaining = []
    for task in tasks:
        source = root / task["file"] if root else PACKAGE_DIR / Path(task["file"]).name
        tree = ast.parse(source.read_text(encoding="utf-8"))
        functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == task["function"]]
        if len(functions) != 1:
            remaining.append(task)
            continue
        if any(isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
               and isinstance(n.exc.func, ast.Name) and n.exc.func.id == "NotImplementedError"
               for n in ast.walk(functions[0])):
            remaining.append(task)
    return remaining


@dataclass(frozen=True)
class Settings:
    cloud: bool
    backend: str
    token: str = field(repr=False)
    database_url: str = field(repr=False)
    lock_database_url: str = field(repr=False)
    namespace: str
    root: Path
    acknowledged: bool

    @classmethod
    def read(cls):
        return cls(bool(os.getenv("VERCEL")), os.getenv("LAB_STATE_BACKEND", "local"),
                   os.getenv("LAB_API_TOKEN", ""), os.getenv("DATABASE_URL", ""),
                   os.getenv("DATABASE_LOCK_URL", ""), os.getenv("LAB_NAMESPACE", "l1-lab"),
                   Path(os.getenv("LAB_STATE_DIR", ".lab/web")),
                   os.getenv("LAB_RELEASE_READY", "").lower() == "true")

    def blockers(self) -> list[str]:
        problems = []
        if self.backend not in {"local", "postgres"}:
            problems.append("Choose local or postgres storage.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.namespace):
            problems.append("Use a valid storage namespace.")
        if self.backend == "postgres" and not self.database_url:
            problems.append("Configure DATABASE_URL securely.")
        if self.cloud:
            if self.backend != "postgres":
                problems.append("Vercel requires durable Postgres storage.")
            if len(self.token) < 32:
                problems.append("Configure an API token with at least 32 characters.")
            if not self.lock_database_url:
                problems.append("Configure a direct/session-pool DATABASE_LOCK_URL.")
            if not self.acknowledged:
                problems.append("Complete release verification before enabling LAB_RELEASE_READY.")
            if unfinished_tasks():
                problems.append("Complete the declared student tasks before deployment.")
        return problems
