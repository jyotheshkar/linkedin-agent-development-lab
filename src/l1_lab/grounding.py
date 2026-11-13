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
    raise NotImplementedError("M5: implement build_context")


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
    raise NotImplementedError("M5: implement validate_answer")


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
