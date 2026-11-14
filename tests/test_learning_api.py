"""Teaching resources are allowlisted, real files; reading is not mastery."""
import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from l1_lab import learning_api

pytestmark = pytest.mark.infrastructure


@pytest.fixture
def client(tmp_path, monkeypatch):
    lessons = tmp_path / "learning"
    diagrams = tmp_path / "architecture"
    package = tmp_path / "package"
    for folder in (lessons, diagrams, package): folder.mkdir()
    (lessons / "contracts.md").write_text("# Contracts\nTrace one JSON input, then test its boundary.", encoding="utf-8")
    (diagrams / "system-anatomy.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Contracts</text></svg>', encoding="utf-8")
    (package / "contracts.py").write_text('def parse_job(raw):\n    """A real source symbol."""\n    return raw\n', encoding="utf-8")
    index = {"schema_version": 1, "project": {"title": "LinkedIn Agent Development Lab"}, "lessons": [
        {"id": "CONTRACTS-01", "title": "Python contracts", "path": "docs/learning/contracts.md",
         "symbols": [{"file": "src/l1_lab/contracts.py", "symbol": "parse_job"}],
         "tests": ["tests/test_contracts.py::test_valid_job"], "diagrams": ["docs/architecture/system-anatomy.svg"]}]}
    (lessons / "lesson-index.json").write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setattr(learning_api, "LEARNING_DIR", lessons)
    monkeypatch.setattr(learning_api, "ARCHITECTURE_DIR", diagrams)
    monkeypatch.setattr(learning_api, "PACKAGE_DIR", package)
    app = FastAPI()
    learning_api.install_learning(app)
    return TestClient(app)


def test_lesson_returns_actual_content_source_and_declared_diagram(client):
    index = client.get("/api/learning").json()
    assert index["lessons"][0]["id"] == "CONTRACTS-01"
    response = client.get("/api/learning/CONTRACTS-01")
    assert response.status_code == 200
    data = response.json()
    assert "Trace one JSON input" in data["content"]
    assert data["source_excerpts"][0]["content"].startswith("def parse_job(raw):")
    assert data["diagram_url"] == "/api/diagrams/system-anatomy.svg"
    assert "no learner grade" in data["learning_evidence"]
    image = client.get(data["diagram_url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/svg+xml")


@pytest.mark.parametrize("path", ["/api/learning/UNKNOWN-01", "/api/diagrams/unknown.svg", "/api/diagrams/README.md", "/api/diagrams/..%5Csecret.svg"])
def test_unknown_or_path_like_identifiers_are_not_read(client, path):
    assert client.get(path).status_code == 404


def test_bad_manifest_fails_closed_without_host_paths(client, monkeypatch, tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "lesson-index.json").write_text(json.dumps({"schema_version": 1, "lessons": [
        {"id": "ESCAPE-01", "path": "docs/learning/../../private.md", "symbols": [], "diagrams": []}]}))
    monkeypatch.setattr(learning_api, "LEARNING_DIR", bad)
    response = client.get("/api/learning")
    assert response.status_code == 503
    assert str(tmp_path) not in response.text
