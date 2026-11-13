"""Explicit migration, executed once against the chosen dedicated database."""
import os
from l1_lab.postgres_store import migrate

if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Configure DATABASE_URL securely before migrating.")
    try:
        migrate(url)
    except Exception:
        raise SystemExit("Migration failed. Check database connectivity and permissions; no secret values were printed.") from None
    print("Deployment schema migration completed.")
