"""The shared application journey used by CLI, API and recovery tests.

@concept A prepared run contains real, reviewable bytes and source references.
The existing LangGraph Workflow still validates and executes every proposal.
Atlas Lab records observed provider receipts; its projection is a separate gate.
@invariant No action in this module contacts an employer or operational Atlas.
@invariant Resumption reads persisted preparation, never an in-memory RAG cache.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .agent import GuardrailError, PermanentError, ToolSpec, UnknownOutcome, completion_gates, validate_tool_call
from .atlas_lab import AtlasLab
from .contracts import Job, normalize_identity, parse_job
from .grounding import validate_answer
from .journal import Journal
from .knowledge import load_snapshot, select_records
from .materials import PendingMaterials, canonical, digest
from .planner import OfflinePlanner
from .provider import FakeProvider
from .service import FIXTURE, RAGService
from .workflow import Workflow, _plan_hash

POLICY = "application-materials-v1"
EFFECTS = {"sim_store": "storage", "sim_submit": "application", "sim_outreach": "outreach",
           "sim_commit": "commit", "sim_deliver": "delivery"}
ORDER = ("sim_store", "sim_submit", "sim_outreach", "sim_commit", "sim_deliver")


class ReviewConflict(ValueError):
    """The exact reviewed material/target is stale, reserved or changed."""


class ReportingPending(PermanentError):
    """Known pre-effect pause: prior receipt logging needs repair first."""


class PreparedPlanner:
    """An immutable, content-bound plan handed to the ordinary executor."""
    mode = "prepared-content-plan"

    def __init__(self, calls: list[dict]):
        self.calls = deepcopy(calls)

    def plan(self, _goal: str) -> list[dict]:
        return deepcopy(self.calls)


def _artifact_reference(artifact: dict, *, content=False) -> dict:
    reference = {key: artifact[key] for key in ("kind", "version", "sha256", "content_type", "byte_size")}
    if content:
        reference["content"] = artifact["content"]
    return reference


def _binding(prepared: dict) -> dict:
    return {"policy_version": prepared["policy_version"], "job": prepared["job"],
            "job_identity": prepared["job_identity"], "source_bindings": prepared["source_bindings"],
            "artifacts": [_artifact_reference(artifact) for artifact in prepared["artifacts"]],
            "retrieval_model": prepared["evidence"]["retrieval"]["model_id"],
            "generation": prepared["evidence"]["generation"]}


class ApplicationService:
    """Local Atlas Lab application service; no ephemeral cloud fallback.

    Full local artifacts/ledger are SQLite backed. Existing legacy Postgres
    workflow adapters remain separate until they implement this artifact store.
    A deployment must not silently mix durable runs with ephemeral material.
    """
    def __init__(self, root: str | Path, *, lab=None, journal=None, provider=None,
                 index_factory=None, telemetry=None, seed: str | Path | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal = journal if journal is not None else Journal(self.root / "runs")
        self.provider = provider if provider is not None else FakeProvider(self.root / "provider.sqlite3")
        self.lab = lab if lab is not None else AtlasLab(self.root / "atlas")
        self.materials = PendingMaterials(self.root / "pending_materials")
        self.index_factory = index_factory
        if telemetry is None:
            from .observability import LocalTelemetry
            telemetry = LocalTelemetry(self.root / "telemetry" / "events.jsonl")
        self.telemetry = telemetry
        with self._locked():
            self.lab.seed_snapshot(load_snapshot(seed or FIXTURE))

    @contextmanager
    def _locked(self):
        """One local transaction lock spans read/approve/execute across processes.

        This lock database is deliberately independent of provider and Atlas
        transactions, so neither can erase the other's evidence on a crash.
        """
        db = sqlite3.connect(self.root / "application_lock.sqlite3", timeout=15, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield
            db.commit()
        except sqlite3.OperationalError as exc:
            db.rollback()
            raise ReviewConflict("another application request is executing; retry the saved run") from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _reserved(self, identity: str) -> None:
        """Pending/verified effects reserve a target; a new run is not recovery."""
        root = getattr(self.journal, "root", self.root / "runs")
        for path in Path(root).glob("*.json"):
            run = self.journal.load(path.stem)
            matching = any(call.get("args", {}).get("identity") == identity
                           for call in run.get("plan", []) if call.get("tool") in EFFECTS)
            if matching and (run.get("receipts") or run.get("in_flight") or run.get("status") in {"awaiting_review", "running", "pending"}):
                raise ReviewConflict("target already has a reserved run; inspect or resume " + run["run_id"])

    def prepare(self, goal: str, job: Job | dict | str, modes: dict | None = None, *,
                retrieval="offline", planner="offline", generation="offline") -> dict:
        """Validate -> retrieve -> draft bytes -> execute to a review boundary.

        Planning and generation modes are independent of retrieval. Live mode
        is explicit and optional; no adapter silently falls back on failure.
        """
        if modes is not None and not isinstance(modes, dict):
            raise ValueError("application modes must be an object")
        if modes:
            if set(modes) - {"retrieval", "planner", "generation"}:
                raise ValueError("unknown application mode")
            retrieval, planner, generation = (modes.get("retrieval", retrieval), modes.get("planner", planner), modes.get("generation", generation))
        if retrieval not in ("offline", "semantic") or planner not in ("offline", "live") or generation not in ("offline", "live"):
            raise ValueError("unsupported retrieval, planner or generation mode")
        raw = job.model_dump() if isinstance(job, Job) else job
        validated_job = parse_job(raw if isinstance(raw, str) else canonical(raw))
        identity = normalize_identity(validated_job.company, validated_job.requisition_id)
        job_data = validated_job.model_dump()
        allowed = OfflinePlanner(target_identity=identity).plan(goal)
        if planner == "offline" and len(allowed) > validated_job.max_calls:
            raise GuardrailError("requested workflow exceeds the supplied tool-call budget")
        with self._locked(), self.telemetry.span("application.start", adapter="application-service"):
            if any(call["tool"] in EFFECTS for call in allowed):
                self._reserved(identity)
            run_id = uuid4().hex
            snapshot = self.lab.snapshot()
            snapshot_path = self.root / "snapshots" / (run_id + ".json")
            snapshot_path.parent.mkdir(exist_ok=True)
            snapshot_path.write_text(canonical(snapshot), encoding="utf-8")
            # The actual job drives the query. Job/document text remains data;
            # only the executor owns permission, review and budget decisions.
            query = " ".join([*validated_job.skills, validated_job.title])
            if job_data.get("description"):
                query += " " + job_data["description"]
            rag = RAGService(snapshot_path, mode=retrieval, generation=generation, index_factory=self.index_factory)
            try:
                with self.telemetry.span("rag.retrieve", run_id=run_id, adapter=retrieval):
                    evidence = rag.answer(query[:2000])
            finally:
                rag.close()
            used = [hit for hit in evidence["retrieved_chunks"] if hit["chunk_id"] in evidence["context_chunk_ids"]]
            gaps = list(evidence["answer"]["gaps"])
            assessments = []
            for skill in validated_job.skills:
                matches = [hit["chunk_id"] for hit in used if skill.casefold() in hit["text"].casefold()]
                assessments.append({"requirement": skill, "evidence_ids": matches,
                                    "status": "evidence_found" if matches else "gap",
                                    "method": "literal requirement mention; not a proficiency or entailment score"})
                if not matches:
                    gaps.append(f"No matching approved evidence was found for requirement: {skill}.")
            answer = deepcopy(evidence["answer"])
            answer["gaps"] = list(dict.fromkeys(gaps))
            if answer["gaps"] and answer["claims"]:
                answer["status"] = "review"
            evidence["answer"] = validate_answer(answer, used)
            evidence["requirements"] = assessments
            mode_data = {"retrieval": retrieval, "planner": planner, "generation": generation}
            artifacts = self.materials.write(run_id, job_data, identity, goal, evidence, mode_data)
            source_bindings = [{key: hit[key] for key in ("table", "record_id", "record_version", "content_hash", "source_ref", "source_version", "chunk_id", "chunk_text_hash", "export_text_hash")}
                               for hit in used]
            prepared = {"schema_version": 1, "policy_version": POLICY, "run_id": run_id,
                        "goal": goal, "job": job_data, "job_identity": identity, "modes": mode_data,
                        "evidence": evidence, "source_bindings": sorted(source_bindings, key=lambda item: item["chunk_id"]),
                        "artifacts": artifacts, "review_state": "pending"}
            prepared["preparation_hash"] = digest(_binding(prepared))
            proposals = allowed
            if planner == "live":
                from .openai_adapter import OpenAIPlanner
                model_planner = OpenAIPlanner()
                proposals = model_planner.plan(canonical({"goal": goal, "job": job_data})[:2000])
                prepared["planning"] = {"mode": model_planner.mode, "usage": model_planner.last_usage}
            else:
                prepared["planning"] = {"mode": "offline-fixture-planner", "usage": None}
            prepared["calls"] = self._bound_calls(prepared, proposals, allowed)
            if len(prepared["calls"]) > validated_job.max_calls:
                raise GuardrailError("prepared plan exceeds the supplied tool-call budget")
            self.materials.save_preparation(run_id, prepared)
            run = self._engine(run_id, prepared).start(goal, run_id=run_id)
            reporting = self._synchronize(run)
            self._trace_events(run, 0)
            return self._result(run, prepared, reporting)

    def _bound_calls(self, prepared, proposals, allowed):
        # Validate model proposals before replacing their arguments with exact
        # approved-domain material. A model-supplied approval flag is not used.
        checking = Workflow(self.root, provider=self.provider, journal=self.journal)
        allowed_names = {call["tool"] for call in allowed}
        if not isinstance(proposals, list) or not 1 <= len(proposals) <= 32:
            raise GuardrailError("planner must return a bounded nonempty proposal list")
        checked = [validate_tool_call(call, checking.registry, allowed_names, prepared["job"]["max_calls"]) for call in proposals]
        names = [call["tool"] for call in checked]
        if not names or names[0] != "retrieve_evidence" or len(names) != len(set(names)):
            raise GuardrailError("plan must start with one retrieval and cannot repeat logical actions")
        if len(names) > 1 and (len(names) < 2 or names[1] != "draft"):
            raise GuardrailError("material preparation must precede simulated actions")
        effects = set(names) & set(EFFECTS)
        if effects and "sim_store" not in effects:
            raise GuardrailError("reviewed material storage is required before dependent actions")
        if "sim_commit" in effects and not {"sim_submit", "sim_outreach"} <= effects:
            raise GuardrailError("a full-unit commit requires separate application and outreach")
        if "sim_deliver" in effects and "sim_commit" not in effects:
            raise GuardrailError("reporting delivery requires a commit")
        calls = [{"tool": "retrieve_evidence", "args": {"query": prepared["evidence"]["query"]}}]
        if "draft" in names:
            calls.append({"tool": "draft", "args": {"text": "Inspect the persisted job-specific brief and outreach draft."}})
        for name in ORDER:
            if name not in effects:
                continue
            chosen = prepared["artifacts"]
            if name == "sim_submit":
                chosen = [artifact for artifact in chosen if artifact["kind"] == "application_brief"]
            elif name == "sim_outreach":
                chosen = [artifact for artifact in chosen if artifact["kind"] == "outreach_draft"]
            payload = {**_binding(prepared), "preparation_hash": prepared["preparation_hash"],
                       "action": EFFECTS[name], "effects": "SIMULATION",
                       "artifacts": [_artifact_reference(artifact, content=name in {"sim_store", "sim_submit", "sim_outreach"}) for artifact in chosen]}
            calls.append({"tool": name, "args": {"identity": prepared["job_identity"], "payload": payload}})
        return calls

    def _prepared(self, run: dict) -> dict:
        prepared = next((output["prepared"] for output in run.get("outputs", []) if "prepared" in output), None)
        return deepcopy(prepared) if prepared is not None else self.materials.load_preparation(run["run_id"])

    def _validate_preparation(self, prepared: dict, run: dict, *, sources=True) -> None:
        if prepared["policy_version"] != POLICY or digest(_binding(prepared)) != prepared["preparation_hash"]:
            raise ReviewConflict("prepared material or policy changed; fresh review is required")
        if _plan_hash(run["plan"]) != run["plan_hash"] or run["plan"] != prepared["calls"]:
            raise ReviewConflict("the exact action plan changed; fresh review is required")
        for call in run["plan"]:
            if call["tool"] in EFFECTS and call["args"]["payload"].get("preparation_hash") != prepared["preparation_hash"]:
                raise ReviewConflict("action payload is not bound to the reviewed material")
        registered = {item["sha256"] for item in self.lab.artifacts(run["run_id"])}
        for artifact in prepared["artifacts"]:
            if artifact["sha256"] in registered:
                content = self.lab.get_artifact(artifact["sha256"])
                if len(content) != artifact["byte_size"] or content.decode("utf-8") != artifact["content"]:
                    raise ReviewConflict("stored artifact differs from the reviewed exact payload")
            else:
                self.materials.read(run["run_id"], artifact)
        if sources:
            current = {(record["table"], record["record_id"]): record for record in select_records(self.lab.snapshot())}
            for binding in prepared["source_bindings"]:
                record = current.get((binding["table"], binding["record_id"]))
                if not record or any(record.get(key) != binding[key] for key in ("record_version", "content_hash", "source_ref", "source_version", "export_text_hash")):
                    raise ReviewConflict("reviewed evidence changed or was revoked; create a fresh reviewed run")

    def _engine(self, run_id: str, prepared: dict) -> Workflow:
        def retrieve(_args, _key):
            # These validated outputs are persisted in the journal; recovery
            # does not depend on the Python object that performed retrieval.
            return {"prepared": deepcopy(prepared), "evidence": deepcopy(prepared["evidence"]),
                    "source_ids": prepared["evidence"]["context_chunk_ids"]}
        def draft(_args, _key):
            for artifact in prepared["artifacts"]:
                self.materials.read(run_id, artifact)
            return {"artifacts": deepcopy(prepared["artifacts"]), "review_required": True,
                    "source_ids": prepared["evidence"]["context_chunk_ids"]}
        engine = Workflow(self.root, planner=PreparedPlanner(prepared["calls"]),
                          provider=self.provider, journal=self.journal,
                          max_calls=prepared["job"]["max_calls"], evidence_fn=retrieve, draft_fn=draft)
        for name, gate in EFFECTS.items():
            original = engine.registry[name]
            def execute(args, key, gate=gate, name=name):
                run = self.journal.load(run_id)
                if not any(item["plan_hash"] == run["plan_hash"] and item["decision"] == "approve"
                           for item in self.lab.approvals(run_id)):
                    raise GuardrailError("simulated action requires its persisted exact-material approval")
                prior_reporting = self._synchronize(run)
                if run.get("receipts") and prior_reporting["status"] != "verified":
                    raise ReportingPending("repair prior event/projection before any new simulated action")
                self._validate_preparation(prepared, run, sources=gate in {"storage", "application", "outreach"})
                if gate == "storage":
                    for artifact in prepared["artifacts"]:
                        content = self.materials.read(run_id, artifact)
                        stored = self.lab.store_artifact(run_id, artifact["kind"], content,
                            {"content_type": artifact["content_type"], "job_identity": prepared["job_identity"],
                             "evidence_ids": prepared["evidence"]["context_chunk_ids"],
                             "generation": prepared["evidence"]["generation"], "review_state": "approved",
                             "plan_hash": run["plan_hash"]})
                        if stored["sha256"] != artifact["sha256"] or stored["version"] != artifact["version"]:
                            raise GuardrailError("immutable artifact did not match the reviewed version")
                else:
                    for artifact in prepared["artifacts"]:
                        if hashlib.sha256(self.lab.get_artifact(artifact["sha256"])).hexdigest() != artifact["sha256"]:
                            raise GuardrailError("dependent action requires exact stored reviewed bytes")
                if gate in {"commit", "delivery"}:
                    reporting = self._synchronize(run)
                    if reporting["status"] != "verified":
                        raise GuardrailError("repair committed events/projection before continuing reporting")
                receipt = self.provider.execute(gate, deepcopy(args), key)
                try:
                    with self.telemetry.span("atlas.commit", run_id=run_id, tool=name):
                        self.lab.record_event(run_id, gate, receipt, deepcopy(args))
                    self.lab.project()
                except Exception as exc:
                    # The provider transaction already succeeded. Preserve the
                    # intent and reconcile its receipt instead of repeating it.
                    raise UnknownOutcome("simulated effect recorded independently; Atlas reporting needs repair") from exc
                return receipt
            engine.registry[name] = ToolSpec(original.args_model, execute, is_effect=True, gate=gate)
        return engine

    def _synchronize(self, run: dict) -> dict:
        """Repair only logging/projection using existing independent receipts."""
        events = []
        try:
            candidates = dict(run.get("receipts", {}))
            pending = run.get("in_flight")
            if pending:
                receipt = self.provider.reconcile(pending["key"])
                if receipt:
                    candidates[receipt["gate"]] = receipt
            for gate, receipt in candidates.items():
                call = next((call for call in run["plan"] if EFFECTS.get(call["tool"]) == gate), None)
                if call is None or receipt.get("payload_hash") != FakeProvider._fingerprint(gate, call["args"]):
                    raise ReviewConflict("provider receipt does not match the persisted action payload")
                events.append(self.lab.record_event(run["run_id"], gate, receipt, deepcopy(call["args"])))
            if candidates:
                self.lab.project()
            projection = self.lab.projection()
            members = {event["event_id"] for event in events}
            verified = projection["up_to_date"] and members <= set(projection["members"])
            return {"status": "verified" if verified else "pending", "events": [event["event_id"] for event in events],
                    "projection": projection, "error_type": None}
        except Exception as exc:
            return {"status": "pending", "events": [event["event_id"] for event in events],
                    "projection": None, "error_type": type(exc).__name__}

    def resume(self, run_id: str, approve: bool = False, plan_hash: str | None = None,
               decision: str | None = None) -> dict:
        """Review exact persisted bytes or reconcile the existing partial run."""
        if type(approve) is not bool or decision not in {None, "approve", "reject", "revise"}:
            raise ValueError("invalid review decision")
        if approve and decision in {"reject", "revise"}:
            raise ValueError("approval and rejection flags conflict")
        approve = approve or decision == "approve"
        with self._locked(), self.telemetry.span("application.resume", run_id=run_id):
            run = self.journal.load(run_id)
            prepared = self._prepared(run)
            before = len(run["trace"])
            if plan_hash is not None and plan_hash != run["plan_hash"]:
                raise ReviewConflict("the reviewed plan hash changed; reload before deciding")
            if (approve or decision in {"reject", "revise"}) and plan_hash is None:
                raise ReviewConflict("review requires the exact displayed plan hash")
            if run["status"] in {"rejected", "revision_requested"}:
                return self._result(run, prepared, self._synchronize(run))
            if decision in {"reject", "revise"}:
                if run.get("receipts") or run.get("in_flight"):
                    raise ReviewConflict("observed effects cannot be undone by rejecting a later review")
                self.lab.save_approval(run_id, run["plan_hash"], decision, _binding(prepared))
                run["status"] = "rejected" if decision == "reject" else "revision_requested"
                run["review_decision"] = decision
                self.journal.save(run)
                return self._result(run, prepared, self._synchronize(run))
            if approve and run["status"] != "completed":
                try:
                    self._validate_preparation(prepared, run, sources=not bool(run.get("in_flight")))
                except (ValueError, OSError) as exc:
                    run["status"], run["error"], run["review_decision"] = "blocked", "reviewed artifact or source changed; fresh review required", "stale"
                    self.journal.save(run)
                    return self._result(run, prepared, self._synchronize(run))
                self.lab.save_approval(run_id, run["plan_hash"], "approve", _binding(prepared))
                run["review_decision"] = "approve"
                self.journal.save(run)
            # Repair the existing event/projection state first, without model
            # calls or provider execution. Workflow reconciles unknown outcomes.
            prior_reporting = self._synchronize(run)
            if prior_reporting["status"] != "verified" and (run.get("receipts") or run.get("in_flight")):
                run["status"] = "pending"
                self.journal.save(run)
                return self._result(run, prepared, prior_reporting)
            run = self._engine(run_id, prepared).resume(run_id, approved=approve)
            if run.get("error") == "ReportingPending":
                run["status"] = "pending"
                self.journal.save(run)
            reporting = self._synchronize(run)
            self._trace_events(run, before)
            return self._result(run, prepared, reporting)

    def _trace_events(self, run, start):
        for event in run["trace"][start:]:
            self.telemetry.record("workflow.step", **{key: event.get(key) for key in
                                  ("run_id", "step_id", "tool", "status", "attempt", "source_ids")})
        self.telemetry.force_flush()

    def _result(self, run: dict, prepared: dict, reporting: dict) -> dict:
        output = deepcopy(run)
        artifacts = deepcopy(prepared["artifacts"])
        registered = {artifact["sha256"]: artifact for artifact in self.lab.artifacts(run["run_id"])}
        storage_ok = True
        for artifact in artifacts:
            item = registered.get(artifact["sha256"])
            artifact["stored"] = bool(item)
            if item:
                artifact["artifact_id"] = item["artifact_id"]
            try:
                if item:
                    content = self.lab.get_artifact(artifact["sha256"])
                    if content.decode("utf-8") != artifact["content"] or len(content) != artifact["byte_size"]:
                        raise ValueError("stored material changed")
                else:
                    self.materials.read(run["run_id"], artifact)
                    storage_ok = False
                artifact["integrity"] = "verified"
            except (ValueError, OSError, KeyError):
                artifact["integrity"] = "changed_or_unavailable"
                storage_ok = False
            artifact["review_state"] = ({"approve": "approved", "reject": "rejected", "revise": "revision_requested", "stale": "stale"}.get(run.get("review_decision"), "pending"))
        gates = completion_gates(run.get("receipts", {}))
        gates["storage"] = gates["storage"] and storage_ok
        gates["commit"] = gates["commit"] and reporting["status"] == "verified"
        gates["delivery"] = gates["delivery"] and reporting["status"] == "verified"
        gates["complete"] = all(gates[gate] for gate in ("application", "outreach", "storage", "commit", "delivery"))
        output["gates"] = gates
        output["completion"] = {"plan": run["status"] == "completed", "full_unit": gates["complete"]}
        if output["status"] == "completed" and any(call["tool"] in EFFECTS for call in output["plan"]) and not gates["complete"]:
            output["status"] = "pending"
        return {"run": output, "job": deepcopy(prepared["job"]), "evidence": deepcopy(prepared["evidence"]),
                "artifacts": artifacts, "gates": gates, "reporting": reporting,
                "approval": {"plan_hash": run["plan_hash"], "policy_version": POLICY,
                             "decision": run.get("review_decision"), "scope": "exact displayed material and simulated actions only"},
                "modes": {**prepared["modes"], "effects": "SIMULATION", "data": prepared["evidence"]["source_kind"]}}

    def get(self, run_id: str) -> dict:
        with self._locked():
            run = self.journal.load(run_id)
            prepared = self._prepared(run)
            projection = self.lab.projection()
            events = self.lab.events(run_id)
            current = projection["up_to_date"] and {event["event_id"] for event in events} <= set(projection["members"])
            return self._result(run, prepared, {"status": "verified" if current else "pending",
                "events": [event["event_id"] for event in events], "projection": projection, "error_type": None})

    get_run = get

    def knowledge(self) -> dict:
        return {"records": self.lab.list_records(), "snapshot": self.lab.snapshot(), "source": "isolated Atlas Lab; no live synchronization"}

    def dashboard(self) -> dict:
        return self.lab.dashboard()

    def artifact(self, run_id: str, kind: str) -> tuple[dict, bytes]:
        result = self.get(run_id)
        artifact = next((item for item in result["artifacts"] if item["kind"] == kind), None)
        if artifact is None:
            raise KeyError(kind)
        content = self.lab.get_artifact(artifact["sha256"]) if artifact["stored"] else self.materials.read(run_id, artifact)
        return artifact, content

    def close(self):
        self.telemetry.close()
