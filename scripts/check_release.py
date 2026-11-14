"""Release rehearsal. Never interprets builder tests as learner competence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from l1_lab.deployment import unfinished_tasks

if __name__ == "__main__":
    tasks = unfinished_tasks()
    if tasks:
        print(json.dumps({"ready": False, "reason": "unfinished student tasks", "tasks": tasks}, indent=2))
        raise SystemExit(2)
    if not os.environ.get("TEST_DATABASE_URL"):
        raise SystemExit("Configure TEST_DATABASE_URL for a disposable database. Release verification requires actual Postgres tests.")
    root = Path(__file__).resolve().parents[1]
    for expression in ("not semantic and not live and not postgres", "postgres"):
        result = subprocess.run([sys.executable, "-m", "pytest", "-m", expression], cwd=root)
        if result.returncode:
            raise SystemExit(result.returncode)
    print(json.dumps({"local_checks_passed": True, "deployed": False,
                      "hosting_ready": False,
                      "hosting_blockers": ["Durable Atlas knowledge/artifact/event storage parity", "Hosted semantic retrieval architecture and verification"],
                      "scope": "local complete MVP + narrow Postgres adapter tests", "learner_competence": "not assessed"}))
