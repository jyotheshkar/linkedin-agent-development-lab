"""M1 edit boundaries: parse_job and normalize_identity only."""
from __future__ import annotations

import json
import unicodedata
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    requisition_id: str = Field(min_length=1, max_length=100)
    skills: list[str] = Field(min_length=1, max_length=20)
    max_calls: StrictInt = Field(default=8, ge=1, le=20)

    @field_validator("title", "company", "requisition_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @field_validator("skills")
    @classmethod
    def skill_values(cls, values: list[str]) -> list[str]:
        if any(not v.strip() for v in values):
            raise ValueError("skills must not be blank")
        return list(dict.fromkeys(v.strip() for v in values))


def parse_job(raw: str) -> Job:
    """M1: JSON object -> strict Job; malformed/nonobject input raises ValueError.

    Reject non-finite JSON numbers and Boolean-as-integer budgets. Do not coerce
    arbitrary string input into lists or numbers. Unknown fields are errors.
    """
    def invalid_constant(value: str):
        raise ValueError("non-finite JSON number: " + value)
    data = json.loads(raw, parse_constant=invalid_constant)
    if not isinstance(data, dict):
        raise ValueError("job must be a JSON object")
    return Job.model_validate(data)


def normalize_identity(company: str, requisition_id: str,
                       seen: set[str] | None = None) -> str:
    """M1: NFKC, trim/collapse whitespace and casefold both identity parts.

    Join with '::'; reject blanks, delimiter ambiguity and duplicate identities.
    `seen` is read-only: successful validation must not modify it.
    """
    parts = []
    for value in (company, requisition_id):
        if not isinstance(value, str):
            raise ValueError("identity parts must be strings")
        part = " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
        if not part or "::" in part:
            raise ValueError("empty or ambiguous identity")
        parts.append(part)
    identity = "::".join(parts)
    if seen is not None and identity in seen:
        raise ValueError("duplicate identity: " + identity)
    return identity
