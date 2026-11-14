# LEARN: WORKFLOW-01
# ROLE: Execute a bounded LangGraph loop with persisted intents and human review.
# FLOW: Validated plan -> journal -> independent provider -> completion.
# WHY: Unknown outcomes require reconciliation; retry only declared pre-effect transients.
# L1: Trace one input and its failure path, then run tests/test_workflow.py.
# L2: Defend this boundary and one alternative; inspect docs/learning/lesson-index.json.
# PYTHON: Type hints describe contracts; exceptions propagate unless explicitly handled.
"""A thin LangGraph plan/execute loop with explicit persisted Python state."""
from __future__ import annotations

from asyncio import CancelledError
import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter, sleep
from copy import deepcopy
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .agent import (DraftArgs, EffectArgs, GuardrailError, QueryArgs, ToolSpec,
                    UnknownOutcome, completion_gates, retry_allowed, validate_tool_call)
from .journal import Journal
from .planner import OfflinePlanner
from .provider import FakeProvider


class GraphState(TypedDict):
    run: dict


def _plan_hash(plan: list[dict]) -> str:
    return hashlib.sha256(json.dumps(plan, sort_keys=True, allow_nan=False).encode()).hexdigest()


class Workflow:
    def __init__(self, root: Path, planner=None, max_calls: int = 8, max_retries: int = 1,
                 provider: FakeProvider | None = None, evidence_fn=None, draft_fn=None, journal=None):
        if type(max_calls) is not int or not 1 <= max_calls <= 32:
            raise ValueError("max_calls must be an integer from 1 to 32")
        if type(max_retries) is not int or not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be an integer from 0 to 3")
        self.root = Path(root)
        self.planner = planner or OfflinePlanner()
        self.max_calls, self.max_retries = max_calls, max_retries
        self.journal = journal if journal is not None else Journal(self.root / "runs")
        self.provider = provider or FakeProvider(self.root / "provider.sqlite3")
        retrieve = evidence_fn or (lambda args, key: {"source_ids": ["synthetic-eval-001"], "kind": "synthetic", "query": args["query"]})
        self.registry = {
            "retrieve_evidence": ToolSpec(QueryArgs, retrieve),
            "draft": ToolSpec(DraftArgs, draft_fn or (lambda args, key: {"draft": args["text"], "review_required": True})),
        }
        for name, gate in (("submit", "application"), ("outreach", "outreach"),
                           ("store", "storage"), ("commit", "commit"), ("deliver", "delivery")):
            self.registry["sim_" + name] = ToolSpec(
                EffectArgs, lambda args, key, gate=gate: self.provider.execute(gate, args, key),
                is_effect=True, gate=gate)
        self.allowed_tools = set(self.registry)
        graph = StateGraph(GraphState)
        graph.add_node("execute_step", self._graph_step)
        graph.add_edge(START, "execute_step")
        graph.add_conditional_edges("execute_step", lambda s: "next" if s["run"]["status"] == "running" else "stop",
                                    {"next": "execute_step", "stop": END})
        self.graph = graph.compile()

    def start(self, goal: str, run_id: str | None = None) -> dict:
        run_id = run_id or uuid4().hex
        if self.journal.exists(run_id):
            raise ValueError("run ID already exists; use resume")
        plan = self.planner.plan(goal)
        if not isinstance(plan, list) or not plan or len(plan) > self.max_calls:
            raise GuardrailError("plan must be a nonempty list within the tool-call budget")
        # Shape checks happen before any provider effect, including later calls.
        plan = [validate_tool_call(call, self.registry, self.allowed_tools, self.max_calls) for call in plan]
        run = {"schema_version": 1, "run_id": run_id, "goal": goal, "plan": plan,
               "plan_hash": _plan_hash(plan), "approved_plan_hash": None,
               "max_calls": self.max_calls, "max_retries": self.max_retries,
               "index": 0, "calls": 0, "attempts": {}, "outputs": [], "receipts": {},
               "in_flight": None, "trace": [], "status": "running", "error": None}
        self.journal.save(run)
        return self._invoke(run)

    def resume(self, run_id: str, approved: bool = False) -> dict:
        if type(approved) is not bool:
            raise ValueError("approved must be a boolean")
        run = self.journal.load(run_id)
        if run["status"] == "completed":
            return run
        if _plan_hash(run["plan"]) != run["plan_hash"]:
            run["status"], run["error"] = "blocked", "persisted plan changed; start a new reviewed run"
            self.journal.save(run)
            return run
        if approved:
            run["approved_plan_hash"] = run["plan_hash"]
            self._trace(run, "human_review", "APPROVED", None, 0)
        if run.get("in_flight"):
            pending = run["in_flight"]
            receipt = self.provider.reconcile(pending["key"])
            if receipt is None or receipt.get("status") != "VERIFIED":
                run["status"] = "pending"
                self._trace(run, pending["tool"], "RECONCILIATION_PENDING", pending["step_id"], pending["attempt"])
                self.journal.save(run)
                return run
            spec = self.registry[pending["tool"]]
            try:
                self._validate_output(receipt, spec, pending["key"], run["plan"][run["index"]]["args"])
            except GuardrailError:
                run["status"], run["error"] = "blocked", "reconciled receipt does not match the persisted request"
                self._trace(run, pending["tool"], "RECONCILIATION_BLOCKED", pending["step_id"], pending["attempt"])
                self.journal.save(run)
                return run
            self._accept(run, pending["tool"], spec, receipt, pending["attempt"], reconciled=True)
        elif run["status"] == "blocked":
            return run
        run["status"], run["error"] = "running", None
        self.journal.save(run)
        return self._invoke(run)

    def _invoke(self, run: dict) -> dict:
        # One graph node is ordinary Python; transitions repeat only while running.
        try:
            return self.graph.invoke({"run": run}, {"recursion_limit": 80})["run"]
        except (KeyboardInterrupt, CancelledError):
            # Cancellation cannot prove that a synchronous provider did nothing.
            # Reload its durable intent rather than clearing it or retrying.
            # If the provider committed, resume reconciles that same key first.
            try:
                interrupted = self.journal.load(run["run_id"])
                pending = interrupted.get("in_flight")
                interrupted["status"] = "pending" if pending else "cancelled"
                interrupted["error"] = ("execution interrupted; reconcile the reserved outcome before continuing"
                                        if pending else "execution interrupted at a safe pre-effect boundary")
                self._trace(interrupted, pending["tool"] if pending else "workflow",
                            "INTERRUPTED_PENDING_RECONCILIATION" if pending else "CANCELLED",
                            pending["step_id"] if pending else f"step_{interrupted['index']}",
                            pending["attempt"] if pending else 0)
                self.journal.save(interrupted)
            except Exception:
                # A second storage failure must not disguise the cancellation.
                # The pre-call intent was already persisted before execution.
                pass
            raise

    @staticmethod
    def _trace(run: dict, tool: str, status: str, step_id: str | None, attempt: int, source_ids=None) -> None:
        run["trace"].append({"run_id": run["run_id"], "step_id": step_id,
                             "tool": tool, "status": status, "attempt": attempt,
                             "source_ids": list(source_ids or []),
                             "timestamp": datetime.now(timezone.utc).isoformat()})

    @staticmethod
    def _validate_output(result: dict, spec: ToolSpec, key: str, args: dict) -> None:
        if not isinstance(result, dict):
            raise GuardrailError("tool output must be an object")
        if spec.is_effect:
            if (result.get("gate") != spec.gate or result.get("status") not in {"VERIFIED", "PENDING"}
                    or not isinstance(result.get("receipt_id"), str)
                    or not result["receipt_id"].startswith("sim:") or result.get("idempotency_key") != key
                    or result.get("payload_hash") != FakeProvider._fingerprint(spec.gate, args)):
                raise GuardrailError("provider receipt failed output validation")
        json.dumps(result, allow_nan=False)

    def _accept(self, run: dict, name: str, spec: ToolSpec, result: dict, attempt: int, reconciled=False) -> None:
        if spec.is_effect:
            run["receipts"][spec.gate] = deepcopy(result)
        run["outputs"].append(deepcopy(result))
        self._trace(run, name, "RECONCILED" if reconciled else "ACCEPTED",
                    f"step_{run['index']}", attempt, result.get("source_ids", []))
        run["in_flight"] = None
        run["index"] += 1
        self.journal.save(run)

    def _graph_step(self, state: GraphState) -> GraphState:
        run = deepcopy(state["run"])
        if run["index"] >= len(run["plan"]):
            run["gates"] = completion_gates(run["receipts"])
            run["completion"] = {"plan": True, "full_unit": run["gates"]["complete"]}
            run["status"] = "completed"
            self.journal.save(run)
            return {"run": run}
        call = run["plan"][run["index"]]
        step_id = f"step_{run['index']}"
        try:
            call = validate_tool_call(call, self.registry, self.allowed_tools, run["max_calls"] - run["calls"])
            name, args = call["tool"], call["args"]
            spec = self.registry[name]
            if spec.is_effect and run["approved_plan_hash"] != run["plan_hash"]:
                run["status"] = "awaiting_review"
                self._trace(run, name, "REVIEW_REQUIRED", step_id, 0)
                self.journal.save(run)
                return {"run": run}
        except GuardrailError as exc:
            run["status"], run["error"] = "blocked", str(exc)
            self._trace(run, str(call.get("tool", "unknown")), "VALIDATION_BLOCKED", step_id, 0)
            self.journal.save(run)
            return {"run": run}
        # Effects use the canonical target/action identity across run IDs.
        # Provider additionally binds the exact payload fingerprint to it;
        # computing a hash alone does not provide exactly-once semantics.
        logical_identity = f"{spec.gate}:{args['identity']}" if spec.is_effect else f"{run['run_id']}:{step_id}"
        key = "sim-key:" + hashlib.sha256(logical_identity.encode()).hexdigest()
        while True:
            attempt = run["attempts"].get(step_id, 0) + 1
            run["attempts"][step_id] = attempt
            run["calls"] += 1
            run["in_flight"] = {"key": key, "step_id": step_id, "tool": name, "attempt": attempt} if spec.is_effect else None
            self._trace(run, name, "ATTEMPT", step_id, attempt)
            self.journal.save(run)  # durable intent before provider action
            try:
                started = perf_counter()
                result = spec.fn(deepcopy(args), key)
                self._validate_output(result, spec, key, args)
            except UnknownOutcome:
                run["status"], run["error"] = "pending", "unknown outcome; capacity reserved pending reconciliation"
                self._trace(run, name, "UNKNOWN_OUTCOME", step_id, attempt)
                self.journal.save(run)
                return {"run": run}
            except Exception as exc:
                self._trace(run, name, type(exc).__name__, step_id, attempt)
                # An invalid result may follow an effect. Preserve its intent so
                # an explicit resume can consult the provider before any repeat.
                if not isinstance(exc, GuardrailError):
                    run["in_flight"] = None
                if retry_allowed(exc, attempt, run["max_retries"]) and run["calls"] < run["max_calls"]:
                    # Fixed, capped exponential backoff keeps this local lab
                    # deterministic: at most 50+100+200ms for three retries.
                    # It never applies to validation or uncertain outcomes.
                    delay = min(.05 * (2 ** (attempt - 1)), .2)
                    self._trace(run, name, "RETRY_BACKOFF", step_id, attempt)
                    run["trace"][-1]["backoff_seconds"] = delay
                    self.journal.save(run)
                    sleep(delay)
                    continue
                run["status"], run["error"] = "blocked", type(exc).__name__
                self.journal.save(run)
                return {"run": run}
            if spec.is_effect and result["status"] == "PENDING":
                run["status"], run["error"] = "pending", "provider receipt pending; full completion withheld"
                self._trace(run, name, "PROVIDER_PENDING", step_id, attempt)
                self.journal.save(run)
                return {"run": run}
            self._accept(run, name, spec, result, attempt)
            run["trace"][-1]["duration_seconds"] = perf_counter() - started
            self.journal.save(run)
            return {"run": run}
