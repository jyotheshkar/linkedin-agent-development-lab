"""Inspect retrieval, structural citations and labelled support separately.

No lexical score here is advertised as semantic entailment. The evaluation bank
is a developer-authored oracle, not an independent expert assessment.
"""
from __future__ import annotations

import math
import time
from typing import Any


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number, not a Boolean")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _case_scores(records: list[dict]) -> dict[str, float]:
    result: dict[str, float] = {}
    for record in records:
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("every evaluation score needs a nonempty case_id")
        if case_id in result:
            raise ValueError(f"duplicate case_id: {case_id}")
        result[case_id] = _finite_number(record.get("score"), "score")
    return result


def compare_runs(baseline: list[dict], current: list[dict], tolerance: float = .05) -> dict:
    """M6 task: compare finite scores by case ID, reporting missing/new IDs.

    A decrease strictly greater than tolerance is a regression. Decimal
    boundaries receive a 1e-12 floating-point allowance; missing cases are
    never silently paired with a different case.
    """
    raise NotImplementedError("M6: implement compare_runs")


def _fraction(numerator: int, denominator: int) -> dict:
    return {"value": numerator / denominator if denominator else None,
            "numerator": numerator, "denominator": denominator}


def evaluate(index: Any, generator: Any, cases: list[dict]) -> dict:
    """Run a labelled bank; observe elapsed time only around executed calls.

    Recall denominator is expected evidence IDs across answerable cases.
    Citation validity counts citation references, including repetitions.
    Answer support is a labelled extractive proxy: claim text must occur in a
    cited expected source, use only retrieved chunk citations and avoid
    case-specific prohibited strings.
    This checks agreement with the small bank, not open-ended truth.
    """
    seen: set[str] = set()
    rows = []
    recall_hits = recall_total = valid_citations = citation_total = 0
    supported_claims = total_claims = correct_abstentions = negative_cases = 0
    answerable_covered = answerable_cases = expected_review_correct = review_cases = 0
    started = time.perf_counter()
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("case IDs must be nonempty and unique")
        seen.add(case_id)
        if not isinstance(case.get("answerable"), bool):
            raise ValueError(f"{case_id}: answerable must be Boolean")
        expected = set(case.get("expected_record_ids", []))
        if case["answerable"] and not expected:
            raise ValueError(f"{case_id}: answerable case needs expected evidence")
        query = case.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{case_id}: query must be nonempty")
        case_start = time.perf_counter()
        hits = index.search(query, top_k=case.get("top_k", 3),
                            min_score=case.get("min_score", .2), filters=case.get("filters"))
        answer = generator.generate(query, hits)
        if not isinstance(answer, dict) or not isinstance(answer.get("claims", []), list):
            raise ValueError(f"{case_id}: malformed generator answer")
        retrieved_records = {hit["record_id"] for hit in hits}
        chunk_to_record = {hit["chunk_id"]: hit["record_id"] for hit in hits}
        citation_map = chunk_to_record
        source_text = {hit["chunk_id"]: hit["text"] for hit in hits}
        case_valid = case_citations = case_supported = 0
        claims = answer.get("claims", [])
        for claim in claims:
            if not isinstance(claim, dict) or not isinstance(claim.get("text"), str):
                raise ValueError(f"{case_id}: claim must contain text")
            citations = claim.get("evidence_ids", [])
            if not isinstance(citations, list) or any(not isinstance(cid, str) for cid in citations):
                raise ValueError(f"{case_id}: evidence_ids must be a string list")
            case_citations += len(citations)
            case_valid += sum(cid in citation_map for cid in citations)
            prohibited = any(str(term).casefold() in claim["text"].casefold()
                             for term in case.get("prohibited_claims", []))
            labelled = bool(citations) and all(cid in citation_map for cid in citations)
            labelled = labelled and any(citation_map[cid] in expected
                                        and claim["text"] in source_text[cid] for cid in citations)
            if labelled and not prohibited:
                case_supported += 1
        answerable_cases += int(case["answerable"])
        answerable_covered += int(case["answerable"] and case_supported > 0
                                  and answer.get("status") == "supported")
        if case["answerable"]:
            recall_hits += len(expected & retrieved_records)
            recall_total += len(expected)
        else:
            negative_cases += 1
            correct_abstentions += int(answer.get("status") == "abstain" and not claims)
        if "expected_status" in case:
            review_cases += 1
            expected_review_correct += int(answer.get("status") == case["expected_status"])
        valid_citations += case_valid
        citation_total += case_citations
        supported_claims += case_supported
        total_claims += len(claims)
        rows.append({"case_id": case_id, "expected_record_ids": sorted(expected),
                     "retrieved_record_ids": sorted(retrieved_records),
                     "retrieved_chunk_ids": [hit["chunk_id"] for hit in hits],
                     "answer": answer, "valid_citations": case_valid,
                     "citation_count": case_citations, "label_supported_claims": case_supported,
                     "claim_count": len(claims), "latency_ms": (time.perf_counter() - case_start) * 1000})
    return {"schema_version": 1, "case_count": len(rows), "cases": rows,
            "metrics": {"retrieval_recall_at_k": _fraction(recall_hits, recall_total),
                        "citation_validity": _fraction(valid_citations, citation_total),
                        "answer_support": _fraction(supported_claims, total_claims),
                        "abstention_accuracy": _fraction(correct_abstentions, negative_cases),
                        "answerable_coverage": _fraction(answerable_covered, answerable_cases),
                        "expected_status_accuracy": _fraction(expected_review_correct, review_cases)},
            "latency_ms": (time.perf_counter() - started) * 1000,
            "support_method": "developer-labelled expected evidence, exact extractive text and prohibited strings; not semantic entailment",
            "token_usage": None, "cost": None}
