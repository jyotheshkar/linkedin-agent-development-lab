import pytest
from pydantic import BaseModel, ConfigDict, Field

from l1_lab.agent import (DraftArgs, GuardrailError, PermanentError, QueryArgs, ToolSpec,
                          TransientError, UnknownOutcome, completion_gates, retry_allowed,
                          validate_tool_call)


@pytest.fixture
def registry():
    return {"search": ToolSpec(QueryArgs, lambda a, k: a)}


@pytest.mark.m2
@pytest.mark.parametrize("call", [None, [], {}, {"tool": "search"},
    {"tool": "search", "args": [],},
    {"tool": "search", "args": {"query": "x"}, "approve": True},
    {"tool": "mail.send", "args": {}}, {"tool": "search", "args": {"query": True}},
    {"tool": "search", "args": {"query": "x", "unknown": 1}}])
def test_invalid_call_shapes_and_arguments(registry, call):
    with pytest.raises(GuardrailError):
        validate_tool_call(call, registry, {"search"}, 2)


@pytest.mark.m2
@pytest.mark.parametrize("budget", [True, False, 0, -1, 1.5])
def test_budget_is_positive_integer(registry, budget):
    with pytest.raises(GuardrailError):
        validate_tool_call({"tool": "search", "args": {"query": "x"}}, registry, {"search"}, budget)


@pytest.mark.m2
def test_permissions_and_detached_arguments(registry):
    proposal = {"tool": "search", "args": {"query": "source"}}
    with pytest.raises(GuardrailError):
        validate_tool_call(proposal, registry, set(), 1)
    result = validate_tool_call(proposal, registry, {"search"}, 1)
    result["args"]["query"] = "changed"
    assert proposal["args"]["query"] == "source"


@pytest.mark.m2
def test_strict_numeric_contract(registry):
    class Numeric(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        count: int = Field(ge=1)
        score: float = Field(allow_inf_nan=False)
    registry["numeric"] = ToolSpec(Numeric, lambda a, k: a)
    for args in ({"count": True, "score": .5}, {"count": 1, "score": float("nan")},
                 {"count": 1, "score": float("inf")}, {"count": "1", "score": .5}):
        with pytest.raises(GuardrailError):
            validate_tool_call({"tool": "numeric", "args": args}, registry, {"numeric"}, 1)


@pytest.mark.m2
def test_retry_attempts_vs_additional_retries():
    assert retry_allowed(TransientError(), attempt=1, max_retries=1)
    assert not retry_allowed(TransientError(), attempt=2, max_retries=1)
    assert not retry_allowed(TransientError(), attempt=1, max_retries=0)
    for error in (GuardrailError(), UnknownOutcome(), PermanentError(), ValueError()):
        assert not retry_allowed(error, 1, 3)


@pytest.mark.m2
@pytest.mark.parametrize("attempt,retries", [(True, 1), (0, 1), (1, -1), (1, True)])
def test_invalid_retry_policy(attempt, retries):
    with pytest.raises(ValueError):
        retry_allowed(TransientError(), attempt, retries)


@pytest.mark.m6
def test_all_five_receipts_required_and_pending_is_not_complete():
    gates = ("application", "outreach", "storage", "commit", "delivery")
    receipts = {g: {"gate": g, "status": "VERIFIED", "receipt_id": "sim:" + g} for g in gates}
    assert completion_gates(receipts)["complete"]
    receipts["delivery"]["status"] = "PENDING"
    assert not completion_gates(receipts)["complete"]
    receipts["delivery"]["status"] = "VERIFIED"
    receipts["commit"]["receipt_id"] = "invented:hash"
    assert not completion_gates(receipts)["complete"]
    assert not completion_gates({})["complete"]


@pytest.mark.m6
def test_receipt_gate_cannot_be_reused_for_another_gate():
    receipt = {"gate": "application", "status": "VERIFIED", "receipt_id": "sim:one"}
    result = completion_gates({g: receipt for g in ("application", "outreach", "storage", "commit", "delivery")})
    assert not result["outreach"] and not result["complete"]


@pytest.mark.m6
def test_receipt_identifiers_must_be_independent():
    receipts = {g: {"gate": g, "status": "VERIFIED", "receipt_id": "sim:reused"}
                for g in ("application", "outreach", "storage", "commit", "delivery")}
    assert not completion_gates(receipts)["complete"]
