import json
import pytest
from fastapi.testclient import TestClient
from l1_lab.api import app
from l1_lab.cli import main
from l1_lab.knowledge import load_snapshot
from l1_lab.service import FIXTURE

pytestmark=pytest.mark.infrastructure

def test_doctor(capsys):
    assert main(["doctor"])==0
    assert json.loads(capsys.readouterr().out)["default_data"]=="synthetic"

def test_health_and_rest_validation():
    client=TestClient(app)
    assert client.get('/health').json()['effects']=='simulated'
    assert client.post('/fit',json={'job':{'max_calls':True}}).status_code==422

def test_auth_before_retrieval(monkeypatch):
    monkeypatch.setenv('LAB_API_TOKEN','test-only-token')
    response=TestClient(app).post('/fit',json={'job':{'title':'AI','company':'Example','requisition_id':'x','skills':['Python']}})
    assert response.status_code==401

def test_fixture_is_synthetic():
    assert load_snapshot(FIXTURE)['kind']=='synthetic'
