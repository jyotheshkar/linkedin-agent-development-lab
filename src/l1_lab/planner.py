"""Planner proposals are data: deterministic execution validates every call."""
from __future__ import annotations

from typing import Protocol
import hashlib
import unicodedata

from .agent import GuardrailError


class Planner(Protocol):
    def plan(self, goal: str) -> list[dict]: ...


class OfflinePlanner:
    """Fixture policy for offline teaching; this is not an LLM agent."""

    mode = "offline-fixture-planner"

    def __init__(self, target_identity: str | None = None):
        self.target_identity = target_identity

    def plan(self, goal: str) -> list[dict]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
            raise GuardrailError("goal must be a nonempty string up to 2000 characters")
        query = {"tool": "retrieve_evidence", "args": {"query": goal.strip()}}
        if "inspect" in goal.casefold() or "evidence only" in goal.casefold():
            return [query]
        draft = {"tool": "draft", "args": {"text": "Synthetic draft for human review."}}
        if "draft" in goal.casefold() and "apply" not in goal.casefold():
            return [query, draft]
        identity = self.target_identity or "synthetic-" + hashlib.sha256(
            " ".join(unicodedata.normalize("NFKC", goal).split()).casefold().encode()
        ).hexdigest()[:16]
        return [query, draft] + [
            {"tool": "sim_" + name,
             "args": {"identity": identity, "payload": {"kind": "synthetic"}}}
            for name in ("submit", "outreach", "store", "commit", "deliver")
        ]
