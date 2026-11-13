import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from l1_lab.progress import compute_metrics, export_checkpoint

pytestmark = pytest.mark.m6


def attempt(q="q1", v="v1", topic="agent_control", score=10, **kwargs):
    rubric = {"correctness": 4, "reasoning": 2, "boundaries": 2, "explanation": 2}
    rubric["correctness"] -= 10 - score
    return {"question_id": q, "variant_id": v, "topic": topic, "rubric": rubric,
            "assisted": False, "is_transfer": False, "critical_misconception": False, **kwargs}


def test_no_attempts_have_no_accuracy_or_mastery_evidence():
    result = compute_metrics([], ["agent_control", "retrieval"])
    assert result["knowledge_accuracy"]["value"] is None
    assert result["first_attempt_accuracy"]["value"] is None
    assert result["mastery"]["value"] == 0
    assert result["readiness"] == "unmeasured"


def test_assisted_attempt_not_independent_and_ungraded_not_zero():
    result = compute_metrics([attempt(score=8), attempt(q="q2", assisted=True),
                              {"question_id": "ungraded", "test_evidence": ["pytest passed"]}], ["agent_control"])
    assert result["knowledge_accuracy"] == {"value": 90, "numerator": 18, "denominator": 20}
    assert result["independent_knowledge_accuracy"]["value"] == 80
    assert result["first_attempt_accuracy"]["value"] == 50
    assert result["independent_first_attempt_accuracy"]["value"] == 0
    assert result["assisted_attempt_count"] == 1
    assert result["ungraded_attempt_count"] == 1


def test_mastery_requires_distinct_scenarios_and_transfer():
    scenarios = [attempt(), attempt(), attempt(q="q2", v="changed", is_transfer=True)]
    result = compute_metrics(scenarios, ["agent_control", "retrieval"])
    assert result["mastery"]["value"] == 50
    assert result["mastered_topics"] == ["agent_control"]
    assert len(result["mastery_evidence"]["agent_control"]) == 2
    assert result["coverage"]["value"] == 50


def test_later_critical_misconception_resets_topic_evidence():
    scenarios = [attempt(), attempt(q="q2", is_transfer=True),
                 attempt(q="q3", score=8, critical_misconception=True), attempt(q="q4", is_transfer=True)]
    result = compute_metrics(scenarios, ["agent_control"])
    assert result["mastery"]["value"] == 0
    assert result["cumulative_attempt_accuracy"]["value"] == 75
    assert result["mastery_evidence"]["agent_control"] == [{"question_id": "q4", "variant_id": "v1", "is_transfer": True}]


@pytest.mark.parametrize("flags", [{"hints": ["look at bounds"]}, {"reference_exposed": True}, {"copied_reference": True}])
def test_assistance_flags_never_produce_independent_mastery(flags):
    result = compute_metrics([attempt(**flags), attempt(q="q2", is_transfer=True, **flags)], ["agent_control"])
    assert result["mastered_topics"] == []
    assert result["independent_knowledge_accuracy"]["value"] is None


def test_first_attempt_is_per_question_not_last_corrected_variant():
    result = compute_metrics([attempt(score=8), attempt(v="retry", is_transfer=True)], ["agent_control"])
    assert result["first_attempt_accuracy"]["value"] == 0
    assert result["cumulative_attempt_accuracy"]["value"] == 50


def test_missing_assistance_declaration_cannot_establish_independent_mastery():
    first, changed = attempt(), attempt(q="q2", v="changed", is_transfer=True)
    first.pop("assisted")
    changed.pop("assisted")
    with pytest.raises(ValueError, match="explicit assisted Boolean"):
        compute_metrics([first, changed], ["agent_control"])


@pytest.mark.parametrize("value", [None, 0, 1, "false", [], {}])
def test_assisted_declaration_requires_actual_boolean(value):
    with pytest.raises(ValueError, match="explicit assisted Boolean"):
        compute_metrics([attempt(assisted=value)], ["agent_control"])


def test_legacy_assistance_flag_cannot_override_disqualifying_evidence():
    result = compute_metrics([attempt(assisted=False, assistance=True)], ["agent_control"])
    assert result["independent_knowledge_accuracy"]["value"] is None


def test_ungraded_record_need_not_claim_assistance_or_independence():
    result = compute_metrics([{"question_id": "ungraded", "graded": False}], ["agent_control"])
    assert result["graded_attempt_count"] == 0
    assert result["independent_knowledge_accuracy"]["value"] is None


def test_checkpoint_schema_requires_explicit_assisted_for_graded_rubric():
    schema = json.loads((Path(__file__).parents[1] / "data" / "progress.schema.json").read_text())
    validator = Draft202012Validator(schema["$defs"]["attempt"])
    raw = attempt()
    raw.pop("assisted")
    assert any("assisted" in error.message for error in validator.iter_errors(raw))
    assert not list(validator.iter_errors({**raw, "assisted": False}))
    assert not list(validator.iter_errors({**raw, "graded": False}))


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), 5, -1, "4"])
def test_invalid_rubric_rejected(value):
    item = attempt()
    item["rubric"]["correctness"] = value
    with pytest.raises(ValueError):
        compute_metrics([item], ["agent_control"])


def test_duplicate_attempt_id_rejected():
    with pytest.raises(ValueError, match="attempt_id"):
        compute_metrics([attempt(attempt_id="one"), attempt(q="q2", attempt_id="one")], ["agent_control"])


def test_inconsistent_critical_grade_rejected_instead_of_silently_repaired():
    with pytest.raises(ValueError, match="critical misconception"):
        compute_metrics([attempt(critical_misconception=True)], ["agent_control"])


def test_llm_specific_accuracy_does_not_mix_other_topics():
    result = compute_metrics([attempt(score=8, topic="llm"), attempt(q="q2")], ["agent_control", "llm"])
    assert result["llm_knowledge_accuracy"]["value"] == 80
    assert result["knowledge_accuracy"]["value"] == 90


def test_checkpoint_preserves_raw_attempts_and_export_is_local(tmp_path):
    raw = [attempt(test_evidence=[{"command": "pytest -m m2", "result": "passed"}], next_action="fresh failure variant")]
    result = export_checkpoint(tmp_path / ".lab" / "checkpoint.json", raw, "explain retry boundary", ["agent_control"])
    saved = json.loads((tmp_path / ".lab" / "checkpoint.json").read_text())
    assert saved == result
    assert saved["attempts"] == raw
    assert saved["next_action"] == "explain retry boundary"
    assert saved["schema_version"] == 1


def test_checkpoint_does_not_invent_attempts(tmp_path):
    result = export_checkpoint(tmp_path / "progress.json")
    assert result["attempts"] == []
    assert result["metrics"]["readiness"] == "unmeasured"
