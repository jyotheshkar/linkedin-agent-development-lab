"""The public commands must share one store and survive a process boundary."""
import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.m6


def test_real_cli_prepare_approve_recover_and_dashboard_share_state(tmp_path):
    spec = importlib.util.spec_from_file_location("verify_cli_journey", Path(__file__).parents[1] / "scripts" / "verify_cli_journey.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.verify(tmp_path / "cli")
    assert report["status"] == "verified"
    assert report["provider_receipts"] == report["ledger_members"] == 5
