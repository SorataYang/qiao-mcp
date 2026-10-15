"""Offline desktop facade for testing the real MCPServer stdio request context."""

import time
from pathlib import Path

from conftest import FakeDb, ready_model_state

from qiao_mcp.domain_server import DomainMCPServer
from qiao_mcp.jobs import JobStore
from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools.catalog import register_tool_catalog


def main():
    provider = QtModelProvider.__new__(QtModelProvider)
    provider._available = True
    provider._unavailable_reason = ""
    provider._mdb = FakeDb()
    provider._odb = FakeDb()
    provider._cdb = FakeDb()
    def state():
        snapshot = ready_model_state()
        snapshot["model_state"].update(model_instance_id="stdio-test-model", model_revision="r1")
        snapshot["server"] = {"model_instance_guard": 1}
        return snapshot

    provider.get_model_state = state
    provider.ensure_analysis_job_supported = lambda *args: None

    def start_job(**kwargs):
        with Path(str(JobStore().path) + ".submissions").open("a") as stream:
            stream.write("submitted\n")
        return {"state": "running", "started_at": "stdio-test-start", "is_running": True}

    def job_status(kind):
        if Path(str(JobStore().path) + ".offline").exists():
            raise ConnectionError("test desktop status connection lost")
        return {"state": "succeeded", "started_at": "stdio-test-start", "is_running": False}

    provider.start_analysis_job = start_job
    provider.get_analysis_job_status = job_status

    def solve(**kwargs):
        time.sleep(5.1)
        return {"state": "succeeded", "is_running": False}

    provider.run_analysis = solve
    server = DomainMCPServer("stdio-context-test", version="test")
    register_tool_catalog(server, provider)
    server.run()


if __name__ == "__main__":
    main()
