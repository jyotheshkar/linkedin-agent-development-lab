# LEARN: AGENT-01
# ROLE: Define allowed tools, retry categories and verified completion.
# FLOW: Planner proposals -> validation -> Workflow; receipts -> completion gates.
# WHY: A registry keeps permission checks in code; arbitrary model-selected functions are excluded.
# L1: Trace one input and its failure path, then run tests/test_agent.py.
# L2: Defend this boundary and one alternative; inspect docs/learning/lesson-index.json.
# PYTHON: Type hints describe contracts; exceptions propagate unless explicitly handled.
"""Tool contracts and the three small agent-control student tasks."""
from __future__ import annotations

from copy import deepcopy
from collections import Counter
from dataclasses import dataclass
from typing import Callable
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class GuardrailError(ValueError):
    """A deterministic validation or permission failure; never retry it."""


class TransientError(RuntimeError):
    """A declared failure known to occur before a simulated effect."""


class UnknownOutcome(RuntimeError):
    """The provider may have committed an effect; reconcile before retrying."""


class PermanentError(RuntimeError):
    """A failure requiring review rather than automatic retries."""


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=2000)


class DraftArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1, max_length=4000)


class EffectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    identity: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)

    @field_validator("identity")
    @classmethod
    def canonical_identity(cls, value: str) -> str:
        value = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
        if not value:
            raise ValueError("identity must not be blank")
        return value


@dataclass(frozen=True)
class ToolSpec:
    args_model: type[BaseModel]
    fn: Callable[[dict, str], dict]
    is_effect: bool = False
    gate: str | None = None


GATES = ("application", "outreach", "storage", "commit", "delivery")


def validate_tool_call(call: dict, registry: dict, allowed_tools: set[str], remaining_budget: int) -> dict:
    """M2: validate shape, known/permitted name, strict schema and budget.

    Return a detached {tool, args} dictionary. Invalid calls raise
    GuardrailError. A boolean is not an integer budget. No execution occurs.
    """
    if type(remaining_budget) is not int or remaining_budget <= 0:
        raise GuardrailError("tool-call budget exhausted or invalid")
    if not isinstance(call, dict) or set(call) != {"tool", "args"}:
        raise GuardrailError("tool proposal must contain only tool and args")
    name = call["tool"]
    if not isinstance(name, str) or name not in registry:
        raise GuardrailError("unknown tool")
    if name not in allowed_tools:
        raise GuardrailError("tool is not permitted")
    if not isinstance(call["args"], dict):
        raise GuardrailError("tool arguments must be an object")
    try:
        args = registry[name].args_model.model_validate(call["args"]).model_dump()
    except ValidationError as exc:
        raise GuardrailError("tool argument schema rejected") from exc
    return {"tool": name, "args": deepcopy(args)}


def retry_allowed(error: Exception, attempt: int, max_retries: int) -> bool:
    """M2: only declared pre-effect transient failures may retry.

    attempt=1 is the initial execution; max_retries counts additional
    executions. Unknown outcomes must be reconciled, never blindly retried.
    """
    if type(attempt) is not int or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("max_retries must be a nonnegative integer")
    return isinstance(error, TransientError) and attempt <= max_retries


def completion_gates(receipts: dict) -> dict:
    """M6: five independent verified sim receipts are required for completion.

    Each receipt needs the matching gate, VERIFIED status, and sim: ID.
    A pending or absent receipt never earns completion credit.
    """
    identifiers = Counter(
        receipt.get("receipt_id") for receipt in receipts.values()
        if isinstance(receipt, dict) and isinstance(receipt.get("receipt_id"), str)
    )
    result = {}
    for gate in GATES:
        receipt = receipts.get(gate)
        result[gate] = bool(
            isinstance(receipt, dict)
            and receipt.get("gate") == gate
            and receipt.get("status") == "VERIFIED"
            and isinstance(receipt.get("receipt_id"), str)
            and receipt["receipt_id"].startswith("sim:")
            and identifiers[receipt["receipt_id"]] == 1
        )
    result["complete"] = all(result.values())
    return result

