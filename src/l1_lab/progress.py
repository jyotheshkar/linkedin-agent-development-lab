"""Objective learning records. Tests never fill explanation/independence scores."""
from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUBRIC = {"correctness": 4, "reasoning": 2, "boundaries": 2, "explanation": 2}
DEFAULT_CONCEPTS = ["python_contracts", "agent_control", "knowledge_ingestion",
                    "retrieval", "grounded_responses", "integration_evaluation"]


def _percent(numerator: float, denominator: float) -> dict:
    return {"value": 100 * numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator}


def _eligible(attempt: dict) -> bool:
    return attempt.get("graded", True) is not False and attempt.get("rubric") is not None


def _scored(attempt: dict) -> tuple[float, bool, bool]:
    for field in ("question_id", "variant_id", "topic"):
        if not isinstance(attempt.get(field), str) or not attempt[field].strip():
            raise ValueError(f"graded attempt needs {field}")
    if "assisted" not in attempt or not isinstance(attempt["assisted"], bool):
        raise ValueError("graded attempt requires an explicit assisted Boolean")
    rubric = attempt.get("rubric")
    if not isinstance(rubric, dict) or set(rubric) != set(RUBRIC):
        raise ValueError("rubric needs exactly correctness, reasoning, boundaries, explanation")
    for name, maximum in RUBRIC.items():
        value = rubric[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric")
        if not math.isfinite(value) or not 0 <= value <= maximum:
            raise ValueError(f"{name} is outside its rubric range")
    for flag in ("assisted", "assistance", "reference_exposed", "copied_reference", "is_transfer", "critical_misconception"):
        if flag in attempt and not isinstance(attempt[flag], bool):
            raise ValueError(f"{flag} must be Boolean")
    hints = attempt.get("hints", False)
    if not isinstance(hints, (bool, list)) or (isinstance(hints, list) and any(not isinstance(h, str) for h in hints)):
        raise ValueError("hints must be Boolean or a list of strings")
    if attempt.get("critical_misconception", False) and rubric["correctness"] == 4:
        raise ValueError("a critical misconception cannot receive full correctness points")
    points = sum(rubric.values())
    independent = not any((attempt["assisted"], attempt.get("assistance", False), attempt.get("hints", False),
                           attempt.get("reference_exposed", False), attempt.get("copied_reference", False)))
    fully_correct = points == 10 and not attempt.get("critical_misconception", False)
    return points, independent, fully_correct


def compute_metrics(attempts: list[dict], concepts: list[str]) -> dict:
    """M6 task: compute inspectable metrics, retaining assistance and resets.

    List order is the chronological attempt order. Ungraded attempts have no
    denominator. A critical misconception resets mastery evidence for its
    topic. Two distinct independently correct scenarios, one transfer, are
    required for mastery. Repeating one scenario cannot establish mastery.
    Every graded attempt requires an explicit assisted Boolean. Missing
    assistance evidence is rejected, never inferred to mean independent.
    """
    raise NotImplementedError("M6: implement compute_metrics")


def export_checkpoint(path: str | Path, attempts: list[dict] | None = None,
                      next_action: str = "M1 parse_job", concepts: list[str] | None = None) -> dict:
    """Atomically save a portable raw-attempt checkpoint and derived metrics.

    Explicit attempts are caller-owned evidence; this function never invents
    scored attempts from a passing test or changes a remote learning store.
    """
    attempts = [] if attempts is None else attempts
    concepts = DEFAULT_CONCEPTS if concepts is None else concepts
    checkpoint = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                  "concepts": concepts, "attempts": attempts,
                  "metrics": compute_metrics(attempts, concepts), "next_action": next_action,
                  "source_ids": [], "reference_exposure": []}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)
    return checkpoint
