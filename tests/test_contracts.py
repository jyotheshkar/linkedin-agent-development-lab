import json
import pytest
from l1_lab.contracts import parse_job, normalize_identity

pytestmark = pytest.mark.m1
JOB = dict(title="AI Engineer", company="Example Labs", requisition_id="R-1", skills=["Python"])

def test_valid_job():
    assert parse_job(json.dumps(JOB)).skills == ["Python"]

@pytest.mark.parametrize("raw", ["{", "[]", "null", "true", "42", '{"title":NaN}', '{}'])
def test_bad_json_and_shapes(raw):
    with pytest.raises(ValueError): parse_job(raw)

@pytest.mark.parametrize("budget", [True, False, 0, -1, 21, 2.5, "3"])
def test_strict_budget(budget):
    with pytest.raises(ValueError): parse_job(json.dumps({**JOB,"max_calls":budget}))

def test_duplicate_normalized_identity():
    identity = normalize_identity("  EXAMPLE   Labs ", "Ｒ-1")
    assert identity == "example labs::r-1"
    seen = {identity}
    with pytest.raises(ValueError): normalize_identity("Example Labs", "R-1", seen)
    assert seen == {identity}

@pytest.mark.parametrize("a,b", [("", "x"),("a", " "),("a::b","x"),(True,"x")])
def test_ambiguous_identity(a,b):
    with pytest.raises(ValueError): normalize_identity(a,b)
