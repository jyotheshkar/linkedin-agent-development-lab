import math

import pytest

from l1_lab.evaluation import compare_runs, evaluate

pytestmark = pytest.mark.m6


def test_regression_aligns_ids_and_reports_missing_new():
    result = compare_runs([{"case_id": "a", "score": .9}, {"case_id": "b", "score": .5},
                           {"case_id": "missing", "score": 1}],
                          [{"case_id": "b", "score": .6}, {"case_id": "new", "score": 1},
                           {"case_id": "a", "score": .7}])
    assert result["compared_count"] == 2
    assert result["missing_case_ids"] == ["missing"]
    assert result["new_case_ids"] == ["new"]
    assert [r["case_id"] for r in result["per_case"]] == ["a", "b"]
    assert result["regression_count"] == 1
    assert result["regression_rate"] == .5
    assert result["mean_delta"] == pytest.approx(-.05)


def test_exact_decimal_tolerance_and_all_improved():
    boundary = compare_runs([{"case_id": "x", "score": .9}], [{"case_id": "x", "score": .85}])
    assert boundary["regression_count"] == 0
    improved = compare_runs([{"case_id": "x", "score": .5}], [{"case_id": "x", "score": .7}])
    assert improved["worst_delta"] == pytest.approx(.2)


def test_empty_regression_denominators_are_na():
    result = compare_runs([], [])
    assert result["regression_rate"] is None
    assert result["worst_delta"] is None


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -float("inf"), "0.9", None])
def test_regression_rejects_invalid_scores(value):
    with pytest.raises(ValueError):
        compare_runs([{"case_id": "x", "score": value}], [])


@pytest.mark.parametrize("tolerance", [True, -.01, float("nan"), float("inf")])
def test_regression_rejects_invalid_tolerance(tolerance):
    with pytest.raises(ValueError):
        compare_runs([], [], tolerance)


def test_duplicate_ids_are_not_silently_overwritten():
    with pytest.raises(ValueError, match="duplicate"):
        compare_runs([{"case_id": "x", "score": .5}, {"case_id": "x", "score": .8}], [])


class FakeIndex:
    def search(self, query, **kwargs):
        if query == "empty":
            return []
        return [{"record_id": "r1", "chunk_id": "c1", "text": "Synthetic prototype"}]


class FakeGenerator:
    def generate(self, query, hits):
        if not hits:
            return {"status": "abstain", "claims": [], "gaps": ["No evidence"]}
        if query == "invalid":
            return {"status": "supported", "claims": [{"text": "Production deployment", "evidence_ids": ["forged"]}]}
        return {"status": "supported", "claims": [{"text": "Synthetic prototype", "evidence_ids": ["c1"]}]}


def test_separate_evaluation_denominators_and_observed_latency():
    cases = [{"case_id": "a", "query": "good", "expected_record_ids": ["r1", "r2"], "answerable": True},
             {"case_id": "b", "query": "empty", "expected_record_ids": [], "answerable": False},
             {"case_id": "c", "query": "invalid", "expected_record_ids": ["r1"], "answerable": True,
              "prohibited_claims": ["production deployment"]}]
    result = evaluate(FakeIndex(), FakeGenerator(), cases)
    assert result["metrics"]["retrieval_recall_at_k"] == {"value": 2 / 3, "numerator": 2, "denominator": 3}
    assert result["metrics"]["citation_validity"]["value"] == .5
    assert result["metrics"]["answer_support"]["value"] == .5
    assert result["metrics"]["abstention_accuracy"]["value"] == 1
    assert result["metrics"]["answerable_coverage"]["value"] == .5
    assert result["latency_ms"] >= 0
    assert result["token_usage"] is None and result["cost"] is None


def test_citation_validity_does_not_prove_labelled_support():
    result = evaluate(FakeIndex(), FakeGenerator(), [
        {"case_id": "a", "query": "good", "expected_record_ids": ["other"], "answerable": True}])
    assert result["metrics"]["citation_validity"]["value"] == 1
    assert result["metrics"]["answer_support"]["value"] == 0
    assert result["metrics"]["retrieval_recall_at_k"]["value"] == 0


def test_valid_citation_with_fabricated_claim_fails_extractive_support_proxy():
    class Fabrication:
        def generate(self, query, hits):
            return {"status": "supported", "claims": [{"text": "This was deployed to production", "evidence_ids": ["c1"]}]}
    result = evaluate(FakeIndex(), Fabrication(), [
        {"case_id": "a", "query": "good", "expected_record_ids": ["r1"], "answerable": True}])
    assert result["metrics"]["citation_validity"]["value"] == 1
    assert result["metrics"]["answer_support"]["value"] == 0


def test_no_cases_is_not_perfect_quality():
    result = evaluate(FakeIndex(), FakeGenerator(), [])
    assert all(metric["value"] is None for metric in result["metrics"].values())


def test_duplicate_evaluation_case_rejected():
    case = {"case_id": "a", "query": "empty", "expected_record_ids": [], "answerable": False}
    with pytest.raises(ValueError, match="unique"):
        evaluate(FakeIndex(), FakeGenerator(), [case, case])
