"""Durable handles for desktop-owned solves; never replay an uncertain submission."""

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psutil

from qiao_mcp.providers import BridgeProvider

SUCCESS = {"succeeded", "success", "completed", "complete"}
ACTIVE = {"submitting", "running"}


class JobStore:
    """SQLite records outlive MCP connections and processes; the desktop owns execution.

    Records and request-ID tombstones are retained until the user removes the DB.
    Connections are per operation, so thread/process callers share transactions.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.environ.get("QIAO_MCP_JOB_DB", str(Path.home() / ".qiao-mcp/jobs.sqlite3")))
        self.owner = uuid.uuid4().hex

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, body TEXT NOT NULL)")
            with db:
                yield db
        finally:
            db.close()

    def _find(self, column: str, value: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(f"SELECT body FROM jobs WHERE {column}=?", (value,)).fetchone()
        return json.loads(row[0]) if row else None

    def get(self, job_id: str) -> dict:
        job = self._find("id", job_id)
        if job is None:
            raise ValueError(f"Unknown job_id: {job_id}")
        return job

    def by_request(self, request_id: str, parameters: dict) -> dict | None:
        job = self._find("request_id", request_id)
        if job and job["parameters"] != parameters:
            raise ValueError("request_id already belongs to different parameters; do not reuse it")
        return job

    def save(self, job: dict) -> dict:
        job["updated_at"] = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM jobs WHERE id=?", (job["job_id"],)).fetchone()
            if row:
                current = json.loads(row[0])
                if current["state"] in {"completed", "failed", "cancelled"}:
                    return current  # A slower concurrent poll cannot regress a terminal result.
            db.execute("UPDATE jobs SET body=? WHERE id=?", (json.dumps(job, allow_nan=False), job["job_id"]))
        return job

    def list(self, limit: int, offset: int) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT body FROM jobs ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def reserve(self, request_id: str, parameters: dict, identity: str, revision: Any) -> tuple[dict, bool]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM jobs WHERE request_id=?", (request_id,)).fetchone()
            if row:
                job = json.loads(row[0])
                if job["parameters"] != parameters:
                    raise ValueError("request_id already belongs to different parameters")
                return job, False
            for (body,) in db.execute("SELECT body FROM jobs"):
                previous = json.loads(body)
                if previous["model_instance_id"] == identity and previous["state"] in ACTIVE:
                    raise ValueError(f"A job is already active for this model: {previous['job_id']}; inspect it first")
            job = {
                "job_id": uuid.uuid4().hex, "request_id": request_id,
                "parameters": parameters, "model_instance_id": identity,
                "submitted_model_revision": revision, "state": "submitting",
                "created_at": time.time(), "updated_at": time.time(),
                "backend_started_at": None, "result": None, "error": None,
                "owner": self.owner,
                "owner_pid": os.getpid(), "owner_started_at": psutil.Process().create_time(),
            }
            db.execute("INSERT INTO jobs VALUES (?, ?, ?)", (job["job_id"], request_id, json.dumps(job)))
            return job, True


def _identity(snapshot: dict) -> str:
    state = snapshot.get("model_state") or {}
    identity = state.get("model_instance_id")
    if snapshot.get("connected") is not True or not isinstance(identity, str) or not identity.strip():
        raise ValueError("Durable analysis requires a connected desktop with model_instance_id; use legacy run tools otherwise")
    return identity


def _terminal(job: dict, status: Any) -> dict:
    if not isinstance(status, dict):
        raise ValueError("Backend returned no task status")
    state = str(status.get("state", "")).lower()
    job["result"] = status
    if state in SUCCESS and status.get("ok") is not False and str(status.get("is_running")).lower() != "true":
        job["state"] = "completed"
    elif state in {"canceled", "cancelled"}:
        job["state"] = "cancelled"
    elif state == "failed" or status.get("ok") is False:
        job["state"] = "failed"
    elif state == "running" or status.get("is_running") is True:
        job["state"] = "running"
    else:
        raise ValueError(f"Unconfirmed backend task state: {state}")
    return job


def start_job(store: JobStore, provider: BridgeProvider, request_id: str, parameters: dict) -> dict:
    existing = store.by_request(request_id, parameters)
    if existing:
        return existing  # Idempotency also works while disconnected or no longer editable.
    snapshot = provider.get_model_state()
    identity = _identity(snapshot)
    server = snapshot.get("server") or {}
    if server.get("model_instance_guard", snapshot.get("model_instance_guard")) != 1:
        raise ValueError("Durable submission requires desktop model_instance_guard=1")
    kind = parameters["kind"]
    operation = "analysis_run" if kind == "analysis" else "check_run"
    # Validate backend support before reserving an operation that might mutate.
    provider.ensure_operation_allowed(operation)
    provider.ensure_analysis_job_supported(kind, parameters["show_view"])
    job, created = store.reserve(request_id, parameters, identity, snapshot["model_state"].get("model_revision"))
    if not created:
        return job
    try:
        with provider.operation_context(operation):
            # Bind/check again because another client may have switched projects
            # between reservation and entry into the SDK's mutation context.
            if _identity(provider.get_model_state()) != identity:
                raise ValueError("MODEL_INSTANCE_MISMATCH before job submission")
            status = provider.start_analysis_job(**parameters)
            if not isinstance(status, dict) or not status.get("started_at"):
                raise ValueError("No backend started_at token; cannot safely correlate later status")
            job["backend_started_at"] = status["started_at"]
            _terminal(job, status)
    except Exception as exc:
        # Even an error may follow a partially applied import/start. Preserve
        # the handle and uncertainty, not a retryable tools/call failure.
        job["state"] = "unknown"
        job["error"] = f"{type(exc).__name__}: {exc}. Do not resubmit; inspect the desktop."
    return store.save(job)


def refresh_job(store: JobStore, provider: BridgeProvider, job_id: str) -> dict:
    job = store.get(job_id)
    if job["state"] not in ACTIVE:
        return job
    if job["state"] == "submitting":
        try:
            alive = psutil.Process(job["owner_pid"]).create_time() == job["owner_started_at"]
        except psutil.NoSuchProcess:
            alive = False
        except psutil.AccessDenied:
            alive = True  # Insufficient information is not evidence of death.
        if not alive:
            # No durable start receipt: never identify a task merely by its
            # current 'succeeded' status, or relaunch after a server restart.
            job.update(state="unknown", error="Submission process ended without a durable start receipt. Do not resubmit.")
            return store.save(job)
        return job
    try:
        if _identity(provider.get_model_state()) != job["model_instance_id"]:
            raise ValueError("MODEL_INSTANCE_MISMATCH: inspect the original model")
        status = provider.get_analysis_job_status(job["parameters"]["kind"])
        if _identity(provider.get_model_state()) != job["model_instance_id"]:
            raise ValueError("MODEL_INSTANCE_MISMATCH during status read")
        if not isinstance(status, dict) or status.get("started_at") != job["backend_started_at"]:
            job["state"] = "unknown"
            job["error"] = "Backend latest task does not match this job; its result cannot be attributed safely"
            return store.save(job)
        job["error"] = None
        return store.save(_terminal(job, status))
    except Exception as exc:
        # Temporary disconnection / other open model should be recoverable.
        # Return an observation error without overwriting the durable state.
        return {**job, "state": "unknown", "error": f"Status unavailable: {exc}; reconnect to the original model and query this job again"}
