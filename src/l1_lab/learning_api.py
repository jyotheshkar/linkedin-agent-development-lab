"""Read-only, allowlisted teaching resources for the browser console.

LEARN: ANATOMY-01 and DELIVERY-01. A lesson links a real source symbol, tests,
and an experiment. Reading a lesson is reference exposure, not a graded attempt.
The API accepts lesson IDs and declared diagram names, never arbitrary paths.
Packaged resources support the same routes after a noneditable wheel install.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .resources import PACKAGE_DIR, ROOT

LEARNING_DIR = PACKAGE_DIR / "_learning" if (PACKAGE_DIR / "_learning").is_dir() else ROOT / "docs" / "learning"
ARCHITECTURE_DIR = PACKAGE_DIR / "_architecture" if (PACKAGE_DIR / "_architecture").is_dir() else ROOT / "docs" / "architecture"
router = APIRouter()
MAX_RESOURCE_BYTES = 300_000


def _read(path: Path) -> str:
    """Read one bounded, previously allowlisted UTF-8 resource; no mutation."""
    if not path.is_file() or path.stat().st_size > MAX_RESOURCE_BYTES:
        raise ValueError("teaching resource is absent or too large")
    return path.read_text(encoding="utf-8")


def _relative(path: str, prefix: str, suffix: str, base: Path) -> Path:
    """Map a manifest-owned repository path into a fixed resource directory."""
    if not isinstance(path, str) or "\\" in path:
        raise ValueError("invalid teaching resource path")
    relative = PurePosixPath(path).relative_to(prefix)
    if not relative.parts or any(part in {".", ".."} for part in relative.parts) or relative.suffix != suffix:
        raise ValueError("invalid teaching resource path")
    target = (base / Path(*relative.parts)).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("teaching resource leaves its allowlist")
    return target


def _manifest() -> dict:
    """Load the versioned teaching map without executing source or lessons."""
    data = json.loads(_read(LEARNING_DIR / "lesson-index.json"))
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or not isinstance(data.get("lessons"), list):
        raise ValueError("invalid lesson index")
    if not 1 <= len(data["lessons"]) <= 100:
        raise ValueError("invalid lesson count")
    seen = set()
    diagram_names = {}
    for lesson in data["lessons"]:
        lesson_id = lesson.get("id")
        if not isinstance(lesson_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9-]{1,63}", lesson_id) or lesson_id in seen:
            raise ValueError("invalid or duplicate lesson ID")
        seen.add(lesson_id)
        _relative(lesson["path"], "docs/learning", ".md", LEARNING_DIR)
        if not isinstance(lesson.get("diagrams", []), list) or not isinstance(lesson.get("symbols", []), list):
            raise ValueError("invalid lesson links")
        for diagram in lesson.get("diagrams", []):
            _relative(diagram, "docs/architecture", ".svg", ARCHITECTURE_DIR)
            name = PurePosixPath(diagram).name
            if name in diagram_names and diagram_names[name] != diagram:
                raise ValueError("ambiguous diagram name")
            diagram_names[name] = diagram
        for item in lesson.get("symbols", []):
            if not isinstance(item, dict) or not isinstance(item.get("symbol"), str):
                raise ValueError("invalid source-symbol link")
            _relative(item["file"], "src/l1_lab", ".py", PACKAGE_DIR)
    return data


def _excerpt(item: dict) -> dict:
    """Return the exact linked symbol from current readable source, capped small.

    The content comes from installed/check-out source at request time; this API
    does not claim that unsaved edits were committed to GitHub.
    """
    path = _relative(item["file"], "src/l1_lab", ".py", PACKAGE_DIR)
    source = _read(path)
    module = ast.parse(source)
    parts = item["symbol"].split(".")
    nodes = module.body
    selected = None
    for part in parts:
        selected = next((node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == part), None)
        if selected is None:
            raise ValueError("linked source symbol is absent")
        nodes = selected.body
    lines = source.splitlines()
    start = min([selected.lineno] + [node.lineno for node in selected.decorator_list])
    text = "\n".join(lines[start - 1:selected.end_lineno])
    return {"path": item["file"], "symbol": item["symbol"],
            "content": text[:24_000], "truncated": len(text) > 24_000,
            "source_kind": "source_read_at_request_time"}


def _unavailable(exc: Exception):
    raise HTTPException(503, "The teaching resources are incomplete. Check the lesson manifest and packaged files.") from exc


@router.get("/api/learning")
def learning_index():
    """Return the real versioned lesson index; no progress is inferred."""
    try:
        return _manifest()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _unavailable(exc)


@router.get("/api/learning/{lesson_id}")
def learning_lesson(lesson_id: str):
    """Resolve one lesson, its declared diagrams, and exact source excerpts."""
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{1,63}", lesson_id):
        raise HTTPException(404, "Unknown lesson.")
    try:
        lesson = next((item for item in _manifest()["lessons"] if item["id"] == lesson_id), None)
        if lesson is None:
            raise HTTPException(404, "Unknown lesson.")
        diagrams = [{"name": PurePosixPath(path).name,
                     "url": "/api/diagrams/" + PurePosixPath(path).name}
                    for path in lesson.get("diagrams", [])]
        return {"lesson": lesson,
                "content": _read(_relative(lesson["path"], "docs/learning", ".md", LEARNING_DIR)),
                "diagram_url": diagrams[0]["url"] if diagrams else None,
                "diagrams": diagrams,
                "source_excerpts": [_excerpt(item) for item in lesson.get("symbols", [])],
                "read_at": datetime.now(timezone.utc).isoformat(),
                "learning_evidence": "Reference material; no learner grade or mastery was assigned."}
    except HTTPException:
        raise
    except (OSError, ValueError, TypeError, KeyError, SyntaxError) as exc:
        _unavailable(exc)


@router.get("/api/diagrams/{name}", include_in_schema=False)
def learning_diagram(name: str):
    """Serve only SVG names declared by the lesson index, never a raw path."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}\.svg", name):
        raise HTTPException(404, "Unknown diagram.")
    try:
        allowed = {PurePosixPath(path).name: path
                   for lesson in _manifest()["lessons"] for path in lesson.get("diagrams", [])}
        if name not in allowed:
            raise HTTPException(404, "Unknown diagram.")
        path = _relative(allowed[name], "docs/architecture", ".svg", ARCHITECTURE_DIR)
        _read(path)
        return FileResponse(path, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
    except HTTPException:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _unavailable(exc)


def install_learning(app):
    """Wire the read-only teaching router into the shared application."""
    app.include_router(router)
