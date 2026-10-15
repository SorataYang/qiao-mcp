"""Durable solves correlate instance + native start time and never replay writes."""

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.jobs import JobStore, refresh_job, start_job
from qiao_mcp.tools.jobs import register_job_tools

PARAMS = {"kind": "analysis", "name": "", "show_view": False}


@pytest.fixture
def backend(fake_provider):
    state = ready_model_state()
    state["model_state"].update(model_instance_id="model-1", model_revision="revision-1")
    state["server"] = {"model_instance_guard": 1}
    fake_provider.get_model_state = lambda: copy.deepcopy(state)
    fake_provider.ensure_analysis_job_supported = Mock()
    fake_provider.start_analysis_job = Mock(return_value={"state": "running", "started_at": "T1", "is_running": True})
    fake_provider.get_analysis_job_status = Mock(return_value={"state": "succeeded", "started_at": "T1", "is_running": False})
    return fake_provider


def test_handle_survives_store_restart_and_repeated_request_does_not_solve(tmp_path, backend):
    path = tmp_path / "jobs.db"
    first = start_job(JobStore(path), backend, "request-one", PARAMS)
    second = start_job(JobStore(path), backend, "request-one", PARAMS)
    assert second["job_id"] == first["job_id"]
    assert backend.start_analysis_job.call_count == 1
    final = refresh_job(JobStore(path), backend, first["job_id"])
    assert final["state"] == "completed"
    backend.get_model_state = Mock(side_effect=ConnectionError("offline"))
    assert refresh_job(JobStore(path), backend, first["job_id"])["result"] == final["result"]
    assert start_job(JobStore(path), backend, "request-one", PARAMS)["job_id"] == first["job_id"]


def test_request_id_conflict_and_active_model_reservation(tmp_path, backend):
    store = JobStore(tmp_path / "jobs.db")
    start_job(store, backend, "request-one", PARAMS)
    with pytest.raises(ValueError, match="different parameters"):
        start_job(store, backend, "request-one", {**PARAMS, "show_view": True})
    with pytest.raises(ValueError, match="already active"):
        start_job(store, backend, "request-two", PARAMS)
    assert backend.start_analysis_job.call_count == 1


def test_parallel_retry_reserves_one_submission(tmp_path, backend):
    path = tmp_path / "jobs.db"
    with ThreadPoolExecutor(4) as pool:
        jobs = list(pool.map(lambda _: start_job(JobStore(path), backend, "same-request", PARAMS), range(4)))
    assert len({job["job_id"] for job in jobs}) == 1
    assert backend.start_analysis_job.call_count == 1


@pytest.mark.parametrize("state,expected", [("succeeded", "completed"), ("failed", "failed"), ("canceled", "cancelled")])
def test_terminal_states_are_not_confused(tmp_path, backend, state, expected):
    store = JobStore(tmp_path / "jobs.db")
    job = start_job(store, backend, "request-one", PARAMS)
    backend.get_analysis_job_status.return_value = {"state": state, "started_at": "T1", "is_running": False}
    assert refresh_job(store, backend, job["job_id"])["state"] == expected


def test_disconnection_is_recoverable_and_newer_solve_is_not_this_job(tmp_path, backend):
    store = JobStore(tmp_path / "jobs.db")
    job = start_job(store, backend, "request-one", PARAMS)
    backend.get_analysis_job_status.side_effect = ConnectionError("lost connection")
    assert refresh_job(store, backend, job["job_id"])["state"] == "unknown"
    assert store.get(job["job_id"])["state"] == "running"
    backend.get_analysis_job_status.side_effect = None
    backend.get_analysis_job_status.return_value = {"state": "succeeded", "started_at": "T2"}
    assert refresh_job(store, backend, job["job_id"])["state"] == "unknown"
    assert backend.start_analysis_job.call_count == 1


def test_switched_model_does_not_poll_foreign_results(tmp_path, backend):
    store = JobStore(tmp_path / "jobs.db")
    job = start_job(store, backend, "request-one", PARAMS)
    state = backend.get_model_state()
    state["model_state"]["model_instance_id"] = "other-model"
    backend.get_model_state = lambda: state
    result = refresh_job(store, backend, job["job_id"])
    assert result["state"] == "unknown" and "MODEL_INSTANCE_MISMATCH" in result["error"]
    backend.get_analysis_job_status.assert_not_called()


@pytest.mark.parametrize("reply", [None, {"state": "running"}, TimeoutError("reply lost")])
def test_uncertain_submission_returns_saved_handle_and_never_replays(tmp_path, backend, reply):
    store = JobStore(tmp_path / "jobs.db")
    if isinstance(reply, Exception):
        backend.start_analysis_job.side_effect = reply
    else:
        backend.start_analysis_job.return_value = reply
    first = start_job(store, backend, "request-one", PARAMS)
    assert first["state"] == "unknown"
    assert start_job(JobStore(store.path), backend, "request-one", PARAMS)["job_id"] == first["job_id"]
    assert backend.start_analysis_job.call_count == 1


def test_dead_submission_owner_becomes_unknown_without_replay(tmp_path, backend, monkeypatch):
    store = JobStore(tmp_path / "jobs.db")
    job, _ = store.reserve("request-one", PARAMS, "model-1", "r1")
    import psutil
    monkeypatch.setattr(psutil, "Process", Mock(side_effect=psutil.NoSuchProcess(123)))
    restored = refresh_job(JobStore(store.path), backend, job["job_id"])
    assert restored["state"] == "unknown"
    backend.start_analysis_job.assert_not_called()


def test_job_tools_return_typed_handles_and_offline_listing(tmp_path, backend, monkeypatch):
    monkeypatch.setenv("QIAO_MCP_JOB_DB", str(tmp_path / "jobs.db"))
    fns = tool_fns(register_job_tools, backend)
    result = asyncio.run(fns["start_analysis_job"](request_id="request-one"))
    assert result["job"]["state"] == "running"
    final = asyncio.run(fns["get_analysis_job"](job_id=result["job"]["job_id"]))
    assert final["job"]["state"] == "completed"
    backend.get_model_state = Mock(side_effect=AssertionError("must be local"))
    listed = asyncio.run(fns["list_analysis_jobs"]())
    assert len(listed["jobs"]) == 1 and listed["next_offset"] is None


@pytest.mark.parametrize("kind", ["analysis", "concrete_check"])
def test_provider_submits_without_waiting_and_does_not_reuse_native_job(fake_provider, kind):
    # Exercise the real provider, separate from the store's backend stub.
    fake_provider.get_analysis_job_status = Mock(return_value={"state": "idle", "started_at": "old"})
    native = {"state": "running", "started_at": "new"}
    if kind == "analysis":
        fake_provider._mdb.do_solve = Mock(return_value=native)
    else:
        fake_provider._cdb.solve_concrete_check = Mock(return_value=native)
    assert fake_provider.start_analysis_job(kind, name="C1") == native
    if kind == "analysis":
        fake_provider._mdb.do_solve.assert_called_once_with(sync=False, wait=False, read_timeout=30)
    else:
        fake_provider._cdb.solve_concrete_check.assert_called_once_with(wait=False, read_timeout=30)
        assert fake_provider._cdb.last("import_concrete_check_case")[2] == {"case_name": "C1"}
    fake_provider.get_analysis_job_status.return_value = native
    with pytest.raises(ValueError, match="already running"):
        fake_provider.start_analysis_job(kind, name="C1")
