import pytest
from l1_lab.agent import GuardrailError
from l1_lab.planner import OfflinePlanner


@pytest.mark.infrastructure
def test_different_goals_select_different_fixture_plans():
    planner = OfflinePlanner()
    assert [c["tool"] for c in planner.plan("inspect evidence")] == ["retrieve_evidence"]
    assert [c["tool"] for c in planner.plan("draft a fit explanation")] == ["retrieve_evidence", "draft"]
    assert len(planner.plan("apply using a synthetic workflow")) == 7


@pytest.mark.infrastructure
@pytest.mark.parametrize("goal", [None, "", "   ", "x" * 2001])
def test_planner_rejects_invalid_goal(goal):
    with pytest.raises(GuardrailError):
        OfflinePlanner().plan(goal)
