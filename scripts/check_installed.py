"""Exercise the noneditable production wheel outside its repository directory."""
import importlib.util
import os
import tempfile

for name in ("VERCEL", "LAB_API_TOKEN", "LAB_STATE_BACKEND", "DATABASE_URL", "DATABASE_LOCK_URL"):
    os.environ.pop(name, None)
with tempfile.TemporaryDirectory() as scratch:
    os.chdir(scratch)
    os.environ["LAB_STATE_DIR"] = scratch
    from fastapi.testclient import TestClient
    from l1_lab.api import app
    from l1_lab.resources import DATA_DIR, MIGRATIONS_DIR
    assert "_data" in str(DATA_DIR), "wheel data was not packaged"
    assert (MIGRATIONS_DIR / "001_deployment.sql").is_file()
    assert importlib.util.find_spec("fastembed") is None, "production wheel must not install ONNX"
    assert importlib.util.find_spec("qdrant_client") is None, "production adapter has no Qdrant dependency"
    client = TestClient(app)
    config = client.get("/api/config")
    assert config.status_code == 200, config.text
    assert client.get("/api/practice").status_code == 200
    assert client.get("/console").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    response = client.post("/api/runs", json={"goal": "prepare Python evaluation application"})
    student = bool(config.json()["unfinished_tasks"])
    assert response.status_code == (409 if student else 201), response.text
    if not student:
        run = response.json()["run"]
        assert run["status"] == "awaiting_review"
        assert len(response.json()["artifacts"]) == 2
        done = client.post(f"/api/runs/{run['run_id']}/resume", json={"approve": True, "plan_hash": run["plan_hash"]})
        assert done.status_code == 200, done.text
        assert done.json()["run"]["completion"]["full_unit"] is True
        assert done.json()["reporting"]["projection"]["up_to_date"] is True
        assert client.get("/api/knowledge").status_code == 200
        assert client.get("/api/learning/CONTRACTS-01").status_code == 200
    print({"wheel_resources": "verified", "student": student, "heavy_runtime_dependencies": False,
           "api_flow": "unfinished task honestly blocked" if student else "review and five simulated receipts"})
