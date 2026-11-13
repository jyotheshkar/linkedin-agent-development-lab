import json
import pytest
from fastapi.testclient import TestClient
from l1_lab.api import app
from l1_lab.service import RAGService, workflow
from l1_lab.contracts import Job

pytestmark=pytest.mark.m6

def test_context_budget_only_retained_citations():
    rag=RAGService()
    try:
        result=rag.answer('Python evaluation',max_chars=1)
        assert result['context_chunk_ids']==[]
        assert result['answer']['status']=='abstain'
    finally: rag.close()

def test_integrated_evidence_workflow_pauses(tmp_path):
    rag=RAGService()
    try:
        job=Job(title='AI',company='Example',requisition_id='x',skills=['Python'])
        runner=workflow(tmp_path,'prepare Python evaluation application',job,rag=rag)
        pending=runner.start('prepare Python evaluation application')
        assert pending['status']=='awaiting_review'
        assert pending['outputs'][0]['source_ids']
        assert pending['outputs'][1]['draft']['claims']
        done=runner.resume(pending['run_id'],approved=True)
        assert done['completion']['full_unit'] is True
        assert runner.provider.effect_count()==5
    finally: rag.close()

def test_fit_endpoint(monkeypatch):
    monkeypatch.delenv('LAB_API_TOKEN',raising=False)
    response=TestClient(app).post('/fit',json={'job':{'title':'AI','company':'Example','requisition_id':'x','skills':['Python']}})
    assert response.status_code==200
    assert response.json()['source_kind']=='synthetic'
    assert response.json()['review_required'] is True
