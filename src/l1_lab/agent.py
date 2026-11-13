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
    raise NotImplementedError("M2: implement validate_tool_call")


def retry_allowed(error: Exception, attempt: int, max_retries: int) -> bool:
    """M2: only declared pre-effect transient failures may retry.

    attempt=1 is the initial execution; max_retries counts additional
    executions. Unknown outcomes must be reconciled, never blindly retried.
    """
    raise NotImplementedError("M2: implement retry_allowed")


def completion_gates(receipts: dict) -> dict:
    """M6: five independent verified sim receipts are required for completion.

    Each receipt needs the matching gate, VERIFIED status, and sim: ID.
    A pending or absent receipt never earns completion credit.
    """
    raise NotImplementedError("M6: implement completion_gates")
