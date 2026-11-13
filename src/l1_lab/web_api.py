"""Same-origin console API. Every provider effect remains explicitly simulated."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import hashlib
import hmac
import json
from pathlib import Path
import re
import threading
import time
import weakref
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .agent import GuardrailError
from .contracts import Job
from .deployment import ROOT, Settings, unfinished_tasks
from .resources import DATA_DIR

router = APIRouter()
WEB = Path(__file__).with_name("web")
_mutex = threading.RLock()
_local_locks = weakref.WeakValueDictionary()
_local_usage: dict[tuple, int] = defaultdict(int)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    goal: str = Field(min_length=1, max_length=2000)
    job: Job | None = None


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    approve: bool = False
    plan_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


def authorize(authorization: str | None = Header(default=None)) -> Settings:
    settings = Settings.read()
    # Check configuration before opening storage; no writable /tmp fallback.
    if settings.blockers():
        raise HTTPException(503, "Deployment configuration is incomplete. See /api/config.")
    if settings.token and (not authorization or
            not hmac.compare_digest(authorization.encode("utf-8"), ("Bearer " + settings.token).encode("utf-8"))):
        raise HTTPException(401, "Enter the configured API token.", headers={"WWW-Authenticate": "Bearer"})
    return settings


def consume(settings: Settings, action: str, limit: int):
    # One owner API key, with a shared budget across replicas, never per-client IP.
    subject = hashlib.sha256((settings.token or "local-owner").encode()).hexdigest()
    if settings.backend == "postgres":
        from .postgres_store import DurableBudget, BudgetExceeded
        try:
            return DurableBudget(settings.database_url, namespace=settings.namespace).consume(subject, action, limit)
        except BudgetExceeded as exc:
            raise HTTPException(429, "Request budget reached; retry in one minute.", headers={"Retry-After": "60"}) from exc
    bucket = int(time.time() // 60)
    key = (subject, action, bucket)
    with _mutex:
        for old in list(_local_usage):
            if old[2] < bucket:
                del _local_usage[old]
        if _local_usage[key] >= limit:
            raise HTTPException(429, "Request budget reached; retry in one minute.", headers={"Retry-After": "60"})
        _local_usage[key] += 1


def stores(settings):
    if settings.backend == "postgres":
        from .postgres_store import PostgresJournal, PostgresProvider
        return (PostgresJournal(settings.database_url, namespace=settings.namespace,
                                lock_database_url=settings.lock_database_url or None),
                PostgresProvider(settings.database_url, namespace=settings.namespace))
    from .journal import Journal
    from .provider import FakeProvider
    return Journal(settings.root / "runs"), FakeProvider(settings.root / "provider.sqlite3")


@contextmanager
def run_lock(journal, run_id):
    if hasattr(journal, "run_lock"):
        with journal.run_lock(run_id):
            yield
        return
    key = str(journal.root.resolve()) + ":" + run_id
    with _mutex:
        lock = _local_locks.setdefault(key, threading.Lock())
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "This run is already executing; reload it shortly.")
    try:
        yield
    finally:
        lock.release()


def valid_id(run_id):
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise HTTPException(422, "Invalid run ID.")


def result(run):
    evidence = next((o["evidence"] for o in run["outputs"] if "evidence" in o), None)
    return {"run": run, "evidence": evidence}


@contextmanager
def mapped_errors():
    try:
        yield
    except HTTPException:
        raise
    except NotImplementedError as exc:
        raise HTTPException(409, "Unfinished student task: " + str(exc)) from exc
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(404, "Saved run not found.") from exc
    except GuardrailError as exc:
        raise HTTPException(422, "The request failed the workflow's validation rules.") from exc
    except ValueError as exc:
        raise HTTPException(422, "Invalid workflow request.") from exc
    except Exception as exc:
        # Database errors can contain hosts, credentials or SQL. Never echo them.
        if type(exc).__name__ == "RunBusyError":
            raise HTTPException(409, "This run is already executing; reload it shortly.") from exc
        raise HTTPException(503, "Storage or workflow service unavailable; retry or inspect server configuration.") from exc


@router.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/console", status_code=307)


@router.get("/console", include_in_schema=False)
def console():
    return FileResponse(WEB / "index.html")


@router.get("/assets/{asset}", include_in_schema=False)
def asset(asset: str):
    if asset not in {"app.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(WEB / asset, media_type="text/javascript" if asset.endswith("js") else "text/css")


@router.get("/api/config")
def config():
    settings = Settings.read()
    tasks = unfinished_tasks()
    return {"mode": "student" if tasks else "reference", "effects": "simulated", "source": "synthetic",
            "retrieval": "offline hash test double", "generation": "offline extractive", "planner": "offline fixture",
            "storage": settings.backend, "auth_required": bool(settings.token) or settings.cloud,
            "unfinished_tasks": tasks, "release_ready": False,
            "configuration_ready": not settings.blockers(), "blockers": settings.blockers(),
            "release_note": "Configuration is not release or interview-readiness evidence; run the release checks after simulation."}


@router.get("/api/practice")
def practice(settings: Settings = Depends(authorize)):
    return json.loads((DATA_DIR / "interview_questions.json").read_text(encoding="utf-8"))


@router.post("/api/runs", status_code=201)
def create_run(request: RunRequest, settings: Settings = Depends(authorize)):
    from .deploy_retrieval import ImmutableVectorIndex
    from .service import RAGService, workflow
    with mapped_errors():
        consume(settings, "create", 10)
        journal, provider = stores(settings)
        run_id = uuid4().hex
        with run_lock(journal, run_id):
            rag = RAGService(index_factory=ImmutableVectorIndex)
            try:
                engine = workflow(settings.root, request.goal, request.job, rag=rag,
                                  journal=journal, provider=provider, capture_evidence=True)
                return result(engine.start(request.goal, run_id=run_id))
            finally:
                rag.close()


@router.get("/api/runs/{run_id}")
def read_run(run_id: str, settings: Settings = Depends(authorize)):
    valid_id(run_id)
    with mapped_errors():
        consume(settings, "read", 60)
        journal, _ = stores(settings)
        return result(journal.load(run_id))


@router.post("/api/runs/{run_id}/resume")
def resume_run(run_id: str, request: ResumeRequest, settings: Settings = Depends(authorize)):
    from .workflow import Workflow
    valid_id(run_id)
    with mapped_errors():
        consume(settings, "resume", 20)
        journal, provider = stores(settings)
        with run_lock(journal, run_id):
            run = journal.load(run_id)
            if not hmac.compare_digest(run["plan_hash"], request.plan_hash):
                raise HTTPException(409, "The reviewed plan has changed; reload before approving.")
            # API runs always finish retrieval/drafting before first pause. Never
            # resume a partial read using an accidental default fake adapter.
            if run["index"] < 2 and run["status"] != "completed":
                raise HTTPException(409, "This run stopped before review. Inspect its error and create a fresh run.")
            engine = Workflow(settings.root, journal=journal, provider=provider)
            return result(engine.resume(run_id, approved=request.approve))


class ConsoleBoundary:
    """Bound actual request bytes, disable cross-origin writes, add safe headers."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            if headers.get(b"sec-fetch-site") == b"cross-site":
                return await JSONResponse({"detail": "Use the same-origin console."}, status_code=403)(scope, receive, send)
            messages, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > 65536:
                    return await JSONResponse({"detail": "Request exceeds 64 KiB."}, status_code=413)(scope, receive, send)
                messages.append(message)
                if not message.get("more_body", False):
                    break
            async def bounded_receive():
                return messages.pop(0) if messages else await receive()
        else:
            bounded_receive = receive
        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]
            await send(message)
        await self.app(scope, bounded_receive, secure_send)


def install_console(app):
    app.include_router(router)
    app.add_middleware(ConsoleBoundary)
