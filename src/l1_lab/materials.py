"""Real draft bytes, persisted before review and verified again before effects.

Pending files are working material, not approved artifacts. Atlas Lab receives
the reviewed immutable bytes only after the owner approves the bound plan.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


KINDS = {"application_brief": "application_brief.md", "outreach_draft": "outreach_draft.md"}


def canonical(value: object) -> str:
    """Stable JSON for fingerprints, never a credential or a permission grant."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class PendingMaterials:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, run_id: str) -> Path:
        if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("invalid material run ID")
        path = self.root / run_id
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("material path escaped its root")
        return path

    @staticmethod
    def _atomic(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, path)

    def write(self, run_id: str, job: dict, identity: str, goal: str,
              evidence: dict, modes: dict) -> list[dict]:
        """Render actual supplied job/evidence into two inspectable draft files.

        The offline wording is an extractive application aid, never invented
        candidate history. IDs and uncertainty remain visible in both drafts.
        """
        directory = self.directory(run_id)
        if directory.exists():
            raise ValueError("prepared material already exists; use the saved run")
        answer = evidence["answer"]
        claims = "\n".join(
            "- " + claim["text"] + " [" + ", ".join(claim["evidence_ids"]) + "]"
            for claim in answer["claims"]
        ) or "- No supported candidate claim is available."
        gaps = "\n".join("- " + gap for gap in answer["gaps"]) or "- No additional gap was identified by this limited check."
        source_lines = "\n".join(
            f"- {hit['chunk_id']}: {hit['record_id']} v{hit['record_version']}; {hit['source_ref']}"
            for hit in evidence["retrieved_chunks"] if hit["chunk_id"] in evidence["context_chunk_ids"]
        ) or "- No evidence in final context."
        target = f"{job['title']} — {job['company']} ({job['requisition_id']})"
        common = (f"Target: {target}\n\nCanonical job: {identity}\n\n"
                  f"Data: {evidence['source_kind']}; retrieval: {evidence['retrieval']['mode']}; "
                  f"generation: {evidence['generation']}\n\n")
        contents = {
            "application_brief": ("# SIMULATION — Application brief\n\n" + common +
                "## Supplied requirement\n\n" + ", ".join(job["skills"]) +
                "\n\n## Evidence-backed points\n\n" + claims +
                "\n\n## Gaps and uncertainty\n\n" + gaps +
                "\n\n## Source references\n\n" + source_lines +
                "\n\nThis is a lab artifact. It does not establish production ownership, employer acceptance or independent learner competence.\n"),
            "outreach_draft": ("# SIMULATION — Outreach draft\n\n" + common +
                "To: simulated hiring team; no real recipient is selected.\n\n" +
                f"Hello hiring team,\n\nI am exploring the {job['title']} requirement. " +
                "The approved lab evidence supports these points:\n\n" + claims +
                "\n\nBefore making any stronger statement, these gaps need review:\n\n" + gaps +
                "\n\nThank you for reviewing this simulated introduction.\n\n" +
                "## Evidence references\n\n" + source_lines +
                "\n\nDRAFT ONLY — this lab never sends employer messages.\n"),
        }
        result = []
        for kind, name in KINDS.items():
            content = contents[kind].encode("utf-8")
            self._atomic(directory / name, content)
            result.append({"kind": kind, "name": name, "version": 1,
                           "content_type": "text/markdown", "sha256": hashlib.sha256(content).hexdigest(),
                           "byte_size": len(content), "content": content.decode("utf-8"),
                           "review_state": "pending", "stored": False})
        return result

    def read(self, run_id: str, artifact: dict) -> bytes:
        """Compare physical bytes to the reviewed manifest; do not regenerate."""
        kind = artifact.get("kind")
        if kind not in KINDS or artifact.get("name") != KINDS[kind]:
            raise ValueError("unknown material kind or filename")
        path = self.directory(run_id) / KINDS[kind]
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError("material path escaped its root")
        content = path.read_bytes()
        if (len(content) != artifact["byte_size"] or hashlib.sha256(content).hexdigest() != artifact["sha256"]
                or content.decode("utf-8") != artifact["content"]):
            raise ValueError("draft artifact bytes changed; fresh review is required")
        return content

    def save_preparation(self, run_id: str, prepared: dict) -> None:
        self._atomic(self.directory(run_id) / "preparation.json", canonical(prepared).encode("utf-8"))

    def load_preparation(self, run_id: str) -> dict:
        return json.loads((self.directory(run_id) / "preparation.json").read_text(encoding="utf-8"))
