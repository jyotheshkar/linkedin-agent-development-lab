from types import SimpleNamespace
import pytest
from l1_lab.openai_adapter import OpenAIPlanner, OpenAIAnswerGenerator, Plan, Proposal

pytestmark = pytest.mark.infrastructure

class FakeResponses:
    def __init__(self,parsed): self.parsed=parsed; self.kwargs=None
    def parse(self,**kwargs):
        self.kwargs=kwargs
        return SimpleNamespace(output_parsed=self.parsed,usage=None)

def test_live_plan_contract_without_network():
    responses=FakeResponses(Plan(steps=[Proposal(tool="retrieve_evidence",arguments_json='{"query":"Python"}')]))
    planner=OpenAIPlanner(client=SimpleNamespace(responses=responses),model="fake-contract")
    assert planner.plan("inspect Python") == [{"tool":"retrieve_evidence","args":{"query":"Python"}}]
    assert responses.kwargs['store'] is False
    assert responses.kwargs['max_output_tokens']==1800

def test_refusal_is_not_success():
    planner=OpenAIPlanner(client=SimpleNamespace(responses=FakeResponses(None)),model="fake-contract")
    with pytest.raises(ValueError): planner.plan("inspect")

def test_private_evidence_not_sent():
    responses=FakeResponses(None)
    adapter=OpenAIAnswerGenerator(client=SimpleNamespace(responses=responses),model="fake-contract")
    with pytest.raises(ValueError): adapter.generate("x",[{"source_ref":"atlas:private"}])
    assert responses.kwargs is None
