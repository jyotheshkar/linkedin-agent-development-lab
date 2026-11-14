"""LEARN: ANATOMY-01 — portable, bounded context for a private coaching chat.

Only manifest-selected source, tests and lessons are exported. A repository URL
does not grant a future assistant access; this JSON is the explicit fallback.
Secrets and private operational data never belong in the teaching manifest.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .resources import ROOT

MAX_FILE_BYTES = 100_000
MAX_EXPORT_BYTES = 600_000
SAFE_PREFIXES = ("src/l1_lab/", "tests/", "docs/learning/")


def redact(text: str) -> str:
    """Remove common credential/contact patterns without inspecting env files."""
    text = re.sub(r"sk-[A-Za-z0-9_-]{16,}", "[REDACTED_KEY]", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]{12,}", r"\1[REDACTED]", text)
    text = re.sub(r"postgres(?:ql)?://[^\s'\"]+", "[REDACTED_DATABASE_URL]", text)
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_CONTACT]", text)


def _read(root: Path, relative: str) -> str:
    candidate = root / relative
    if not relative.startswith(SAFE_PREFIXES) or candidate.is_symlink():
        raise ValueError("context path is outside the teaching allowlist")
    path = candidate.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("context path missing, oversized or outside the repository")
    return path.read_text(encoding="utf-8")


def validate_lessons(root: Path = ROOT) -> dict:
    """Check schema, concrete symbols, test targets, diagrams and lesson links."""
    from jsonschema import Draft202012Validator
    index = json.loads((root / "docs/learning/lesson-index.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "docs/learning/lesson-index.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(index)
    ids = [lesson["id"] for lesson in index["lessons"]]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate lesson IDs")
    for lesson in index["lessons"]:
        _read(root, lesson["path"])
        if any(item not in ids for item in lesson["prerequisites"]):
            raise ValueError("unknown prerequisite")
        for relative in lesson["source_files"]:
            _read(root, relative)
        for item in lesson["symbols"]:
            tree = ast.parse(_read(root, item["file"]))
            parts = item["symbol"].split(".")
            nodes = tree.body
            for part in parts:
                found = next((n for n in nodes if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == part), None)
                if found is None:
                    raise ValueError("lesson references missing symbol: " + item["symbol"])
                nodes = found.body
        for target in lesson["tests"]:
            relative, *names = target.split("::")
            tree = ast.parse(_read(root, relative))
            if names and names[-1] not in {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}:
                raise ValueError("lesson references missing test: " + target)
        for relative in lesson["diagrams"]:
            path = root / relative
            if not relative.startswith("docs/architecture/") or not path.is_file() or path.is_symlink():
                raise ValueError("lesson references missing diagram")
    return index


def export_context(lesson_id: str, output: Path, root: Path = ROOT) -> dict:
    """Write one lesson's source/test context; private checkpoints are excluded.

    Source hashes identify pre-redaction bytes. This exports committed or local
    files explicitly, recording dirty status rather than pretending they match.
    """
    root = root.resolve()
    index = validate_lessons(root)
    lesson = next((x for x in index["lessons"] if x["id"] == lesson_id), None)
    if lesson is None:
        raise ValueError("unknown lesson ID")
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    paths = sorted(set(lesson["source_files"] + [x.split("::")[0] for x in lesson["tests"]] + [lesson["path"]]))
    files = []
    for relative in paths:
        original = _read(root, relative)
        files.append({"path": relative, "source_sha256": hashlib.sha256(original.encode()).hexdigest(), "content": redact(original)})
    result = {"schema_version": 1, "kind": "coaching_context", "created_at": datetime.now(timezone.utc).isoformat(),
              "project": index["project"], "commit": commit, "worktree_dirty": dirty,
              "lesson": lesson, "files": files,
              "checkpoint": {"attempts": [], "readiness": "unmeasured", "next_action": "Trace one input and choose a small experiment"},
              "privacy": {"allowlisted": True, "private_data_included": False, "redaction": "credential/contact patterns"}}
    raw = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if len(raw.encode()) > MAX_EXPORT_BYTES:
        raise ValueError("context bundle exceeds size limit")
    output = Path(output)
    if output.is_symlink() or output.suffix != ".json" or any(p in {".git", "private"} or p.startswith(".env") for p in output.parts):
        raise ValueError("choose a safe JSON output, normally .lab/context.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(raw, encoding="utf-8")
    return result
