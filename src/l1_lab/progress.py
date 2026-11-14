# LEARN: EVALUATION-01
# ROLE: Compute learning evidence from explicit graded, assistance-aware attempts.
# FLOW: Private attempts -> rubric metrics -> portable checkpoint.
# WHY: Builder tests cannot establish learner mastery; missing independence evidence is not a pass.
# L1: Trace one input and its failure path, then run tests/test_progress.py.
# L2: Defend this boundary and one alternative; inspect docs/learning/lesson-index.json.
# PYTHON: Type hints describe contracts; exceptions propagate unless explicitly handled.
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
    if len(set(concepts)) != len(concepts) or any(not isinstance(c, str) or not c for c in concepts):
        raise ValueError("concepts must be distinct nonempty strings")
    scored = []
    attempt_ids: set[str] = set()
    first: dict[str, tuple] = {}
    evidence: dict[str, dict[tuple[str, str], bool]] = {topic: {} for topic in concepts}
    topic_scores: dict[str, list[float]] = {}
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError("attempts must contain objects")
        if "graded" in attempt and not isinstance(attempt["graded"], bool):
            raise ValueError("graded must be Boolean")
        if "attempt_id" in attempt:
            aid = attempt["attempt_id"]
            if not isinstance(aid, str) or not aid or aid in attempt_ids:
                raise ValueError("attempt_id must be nonempty and unique")
            attempt_ids.add(aid)
        if not _eligible(attempt):
            continue
        points, independent, fully_correct = _scored(attempt)
        item = (attempt, points, independent, fully_correct)
        scored.append(item)
        first.setdefault(attempt["question_id"], item)
        topic = attempt["topic"]
        topic_scores.setdefault(topic, []).append(points)
        evidence.setdefault(topic, {})
        if attempt.get("critical_misconception", False):
            evidence[topic].clear()
        elif independent and fully_correct:
            key = (attempt["question_id"], attempt["variant_id"])
            evidence[topic][key] = evidence[topic].get(key, False) or attempt.get("is_transfer", False)
    independent_items = [item for item in scored if item[2]]
    first_items = list(first.values())
    independent_first = [item for item in first_items if item[2]]
    mastered = [topic for topic in concepts
                if len(evidence[topic]) >= 2 and any(evidence[topic].values())]
    covered = [topic for topic in concepts if topic in topic_scores]
    return {"graded_attempt_count": len(scored), "ungraded_attempt_count": len(attempts) - len(scored),
            "assisted_attempt_count": len(scored) - len(independent_items),
            "assisted_first_attempt_count": sum(not item[2] for item in first_items),
            "knowledge_accuracy": _percent(sum(i[1] for i in scored), 10 * len(scored)),
            "independent_knowledge_accuracy": _percent(sum(i[1] for i in independent_items), 10 * len(independent_items)),
            "first_attempt_accuracy": _percent(sum(i[3] for i in first_items), len(first_items)),
            "independent_first_attempt_accuracy": _percent(sum(i[3] for i in independent_first), len(independent_first)),
            "cumulative_attempt_accuracy": _percent(sum(i[3] for i in scored), len(scored)),
            "coverage": _percent(len(covered), len(concepts)), "mastery": _percent(len(mastered), len(concepts)),
            "mastered_topics": mastered, "covered_topics": covered,
            "topic_accuracy": {topic: _percent(sum(values), 10 * len(values)) for topic, values in topic_scores.items()},
            "llm_knowledge_accuracy": _percent(sum(topic_scores.get("llm", [])), 10 * len(topic_scores.get("llm", []))),
            "mastery_evidence": {topic: [{"question_id": qid, "variant_id": vid, "is_transfer": transfer}
                                          for (qid, vid), transfer in scenarios.items()]
                                 for topic, scenarios in evidence.items()},
            "readiness": "unmeasured" if not scored else "practice evidence only; not a hiring probability"}


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

