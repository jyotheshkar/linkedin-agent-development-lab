"""Verify the real CLI across fresh processes; all provider effects are simulated."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def verify(root: Path) -> dict:
    root = root.resolve()
    def cli(*arguments):
        result = subprocess.run([sys.executable, "-m", "l1_lab.cli", *arguments,
                                 "--root", str(root)], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    cli("seed")
    knowledge = cli("knowledge")
    assert knowledge["records"], "seed must populate the application's Atlas store"
    prepared = cli("run")
    run = prepared["run"]
    assert run["status"] == "awaiting_review"
    assert len(prepared["artifacts"]) == 2
    before = cli("dashboard")
    assert before["event_count"] == 0
    completed = cli("resume", run["run_id"], "--decision", "approve", "--plan-hash", run["plan_hash"])
    assert completed["gates"]["complete"] is True
    assert completed["reporting"]["status"] == "verified"
    for artifact in completed["artifacts"]:
        assert artifact["stored"] is True and artifact["integrity"] == "verified"
        stored = root / "atlas" / "artifacts" / artifact["sha256"]
        content = stored.read_bytes()
        assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
        assert content == artifact["content"].encode("utf-8")
    recovered = cli("resume", run["run_id"])
    assert recovered["gates"] == completed["gates"]
    trace = cli("trace", run["run_id"])
    assert trace
    dashboard = cli("dashboard")
    assert dashboard["up_to_date"] and dashboard["complete_units"] == 1
    assert dashboard["event_count"] == len(dashboard["members"]) == 5
    with sqlite3.connect(root / "provider.sqlite3") as db:
        effects = db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
    assert effects == 5, "fresh-process recovery must not repeat provider effects"
    return {"status": "verified", "effects": "SIMULATION", "commands": 8,
            "fresh_process_recovery": True, "artifact_count": 2,
            "provider_receipts": effects, "ledger_members": 5, "complete_units": 1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".lab") / (
        "cli-verification-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")))
    args = parser.parse_args()
    print(json.dumps(verify(args.root), indent=2))
