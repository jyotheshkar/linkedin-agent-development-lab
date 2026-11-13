"""Budgeted untrusted evidence and inspectable, structural answer checks.

These checks prove membership and exact quotation only. They do not prove that
a citation entails a claim, that the source is true, or that a task succeeded.
No document is interpreted as executable instructions by this module.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


def _context_hit(hit: dict) -> dict[str, str]:
    if not isinstance(hit, dict):
        raise ValueError("each context hit must be an object")
    item = {}
    for key in ("chunk_id", "record_id", "text"):
        value = hit.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"context hit requires nonempty {key}")
        item[key] = value
    metadata = hit.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("hit metadata must be an object")
    group = metadata.get("conflict_group")
    if group is not None and (not isinstance(group, str) or not group.strip()):
        raise ValueError("conflict_group must be a nonempty string")
    return item


def _encode_context(chunks: list[dict]) -> str:
    return json.dumps(
        {"kind": "UNTRUSTED_EVIDENCE", "chunks": chunks},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _conflicting_groups(hits: list[dict]) -> set[str]:
    groups: dict[str, set[str]] = {}
    for hit in hits:
        metadata = hit.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("hit metadata must be an object")
        group = metadata.get("conflict_group")
        if group is not None:
            if not isinstance(group, str) or not group.strip():
                raise ValueError("conflict_group must be a nonempty string")
            # A curated conflict label is evidence for review, not a semantic
            # contradiction detector. A different value in the same group is
            # deliberately conservative and never grants tool permissions.
            value = metadata.get("claim_value", hit["text"])
            groups.setdefault(group, set()).add(
                json.dumps(value, ensure_ascii=False, sort_keys=True)
            )
    return {group for group, values in groups.items() if len(values) > 1}


def build_context(hits: list[dict], max_chars: int = 3000) -> str:
    """M5 task: encode whole retrieved chunks inside an exact character budget.

    Inputs are ranked hit dictionaries with nonempty chunk_id, record_id, text.
    max_chars is a non-Boolean integer from 1 to 1_000_000. Preserve rank order;
    skip a chunk that cannot fit, rather than truncate its source text or IDs.
    Return a JSON UNTRUSTED_EVIDENCE envelope, or '' when no chunk fits. Its
    length includes JSON escaping and all envelope/citation characters. Duplicate
    chunk IDs and malformed inputs raise ValueError. Never mutate input hits.
    The budget is characters, not a model token-limit guarantee.
    """
    if type(max_chars) is not int or not 1 <= max_chars <= 1_000_000:
        raise ValueError("max_chars must be an integer from 1 to 1000000")
    if not isinstance(hits, list):
        raise ValueError("hits must be a list")
    selected: list[dict] = []
    seen: set[str] = set()
    for hit in hits:
        item = _context_hit(hit)
        if item["chunk_id"] in seen:
            raise ValueError("duplicate context chunk_id")
        seen.add(item["chunk_id"])
        if len(_encode_context([*selected, item])) <= max_chars:
            selected.append(item)
    return _encode_context(selected) if selected else ""


def validate_answer(answer: dict, hits: list[dict]) -> dict:
    """M5 task: check structured output against the *provided context* hits.

    Require exactly status, claims, gaps. Status is supported/review/abstain.
    Each claim has nonempty text, unique nonempty evidence_ids drawn from
    context chunk IDs, and optionally a nonempty exact quote occurring in at
    least one cited chunk. Gaps are nonempty strings. Supported requires claims
    and no gaps; abstain requires no claims and at least one gap; review requires
    at least one gap. A cited curated conflict group with different values in
    retrieved context cannot be supported. Malformed output, unknown IDs or
    invalid quotes raise ValueError. Return a deep copy without changing inputs.
    This is structural support validation, never semantic entailment checking.
    """
    if not isinstance(answer, dict) or set(answer) != {"status", "claims", "gaps"}:
        raise ValueError("answer requires exactly status, claims and gaps")
    if not isinstance(hits, list):
        raise ValueError("hits must be a list")
    context: dict[str, dict] = {}
    for hit in hits:
        item = _context_hit(hit)
        if item["chunk_id"] in context:
            raise ValueError("duplicate context chunk_id")
        context[item["chunk_id"]] = hit
    status = answer["status"]
    if status not in ("supported", "review", "abstain"):
        raise ValueError("invalid answer status")
    claims, gaps = answer["claims"], answer["gaps"]
    if not isinstance(claims, list) or not isinstance(gaps, list):
        raise ValueError("claims and gaps must be lists")
    if any(not isinstance(gap, str) or not gap.strip() for gap in gaps):
        raise ValueError("gaps must contain nonempty strings")
    cited_groups: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be an object")
        if not {"text", "evidence_ids"} <= set(claim) or set(claim) - {
            "text", "evidence_ids", "quote"
        }:
            raise ValueError("claim requires text, evidence_ids and optional quote")
        if not isinstance(claim["text"], str) or not claim["text"].strip():
            raise ValueError("claim text must be nonempty")
        ids = claim["evidence_ids"]
        if not isinstance(ids, list) or not ids:
            raise ValueError("each claim requires evidence_ids")
        if any(not isinstance(item, str) or not item for item in ids):
            raise ValueError("evidence IDs must be nonempty strings")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate claim evidence ID")
        if any(item not in context for item in ids):
            raise ValueError("citation is outside retrieved context")
        if "quote" in claim:
            quote = claim["quote"]
            if not isinstance(quote, str) or not quote.strip():
                raise ValueError("quote must be a nonempty string")
            if not any(quote in context[item]["text"] for item in ids):
                raise ValueError("quote is not exact cited source text")
        for item in ids:
            group = context[item].get("metadata", {}).get("conflict_group")
            if group is not None:
                cited_groups.add(group)
    if status == "supported" and (not claims or gaps):
        raise ValueError("supported requires claims and no unresolved gaps")
    if status == "abstain" and (claims or not gaps):
        raise ValueError("abstain requires no claims and at least one gap")
    if status == "review" and not gaps:
        raise ValueError("review requires an unresolved gap")
    if status == "supported" and cited_groups & _conflicting_groups(hits):
        raise ValueError("conflicting context requires review")
    return deepcopy(answer)


class OfflineGenerator:
    """Deterministic extractive test adapter, not a live model or truth judge."""

    mode = "offline-extractive"

    def generate(self, query: str, hits: list[dict]) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a nonempty string")
        if not hits:
            return {
                "status": "abstain",
                "claims": [],
                "gaps": ["No relevant approved evidence was retrieved."],
            }
        item = _context_hit(hits[0])
        group = hits[0].get("metadata", {}).get("conflict_group")
        conflict = group is not None and group in _conflicting_groups(hits)
        injection = hits[0].get("metadata", {}).get("instruction_in_document", False)
        answer = {
            "status": "review" if conflict or injection else "supported",
            "claims": [{
                "text": item["text"],
                "evidence_ids": [item["chunk_id"]],
                "quote": item["text"],
            }],
            "gaps": (["Retrieved sources conflict; human review is required."] if conflict else
                     ["Document contains instructions; treat as untrusted evidence for review."] if injection else []),
        }
        return validate_answer(answer, hits)
