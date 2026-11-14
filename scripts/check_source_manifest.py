"""Check saved source bytes against the final verification manifest."""
import hashlib
import json
from pathlib import Path


def digest(path: Path, encoding: str) -> str:
    content = path.read_bytes()
    if encoding == "utf8-lf-final-newline":
        content = (content.decode("utf-8").replace("\r\n", "\n").rstrip("\n") + "\n").encode("utf-8")
    return hashlib.sha256(content).hexdigest()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "verification/source-manifest.json").read_text())
    failures = [row["path"] for row in manifest["files"]
                if digest(root / row["path"], row["encoding"]) != row["sha256"]]
    if failures:
        raise SystemExit("Source differs from verified snapshot: " + ", ".join(failures))
    print(json.dumps({"status": "verified", "files": len(manifest["files"]),
                      "scope": "saved bytes only; not execution or unsaved editor state"}))
