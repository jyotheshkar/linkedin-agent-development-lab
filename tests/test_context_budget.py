import pytest
from l1_lab.context_budget import ContextBudget

def test_unicode_bytes_and_output_headroom_are_accounted_for():
    result = ContextBudget(100, 20, 10).check("safe", "\u4e2d" * 10)
    assert result["input_estimate_upper_bound"] == 34
    assert result["observed_input_tokens"] is None
    with pytest.raises(ValueError):
        ContextBudget(100, 20, 10).check("safe", "\u4e2d" * 30)

@pytest.mark.parametrize("values", [(True, 1, 1), (10, 10, 1), (100, 0, 10)])
def test_invalid_or_exhausted_budget_is_rejected(values):
    with pytest.raises(ValueError):
        ContextBudget(*values).check("x", "y")
