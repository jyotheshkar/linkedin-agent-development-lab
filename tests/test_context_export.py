import json
from pathlib import Path
import pytest
from l1_lab.context_export import export_context, redact, validate_lessons

def test_manifest_references_real_symbols_tests_and_diagrams():
    assert len(validate_lessons()["lessons"]) >= 8

def test_one_lesson_export_is_bounded_and_private_files_are_absent(tmp_path):
    output = tmp_path / "context.json"
    result = export_context("CONTRACTS-01", output)
    assert json.loads(output.read_text())["kind"] == "coaching_context"
    assert any(f["path"].endswith("contracts.py") for f in result["files"])
    assert all(f["path"].startswith(("src/l1_lab/", "tests/", "docs/learning/")) for f in result["files"])
    assert result["checkpoint"]["readiness"] == "unmeasured"
    assert output.stat().st_size < 600000

def test_export_rejects_unknown_lesson_and_sensitive_output(tmp_path):
    with pytest.raises(ValueError):
        export_context("NOT-A-LESSON", tmp_path / "x.json")
    with pytest.raises(ValueError):
        export_context("CONTRACTS-01", tmp_path / "private" / "x.json")

def test_redaction_removes_credential_and_contact_values():
    value = redact("sk-abcdefghijklmnopqrstuvwxyz test@example.invalid postgresql://user:secret@host/db Bearer abcdefghijklmnop")
    assert "secret" not in value and "test@example" not in value and "abcdefghijklmnop" not in value
