"""Exercise SDK 2.x dispatch semantics rather than calling tool functions directly."""

import asyncio
import sys
import threading
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver import Context

from qiao_mcp.registration import OperationServer
from qiao_mcp.tools.envelope import register_tools_with_envelope


def test_sync_calls_keep_the_request_thread_and_do_not_interleave():
    events = []
    server = OperationServer("serialization-test")
    context = Context(mcp_server=server)

    def register(mcp, provider):
        @mcp.tool()
        def mutate(value: int, ctx: Context) -> dict:
            assert ctx is context
            events.append(("start", value, threading.get_ident()))
            time.sleep(0.01)
            events.append(("end", value, threading.get_ident()))
            return {"value": value}

    register_tools_with_envelope(server, register, None)

    async def invoke():
        return await asyncio.gather(*(
            server.call_tool("mutate", {"value": value}, context)
            for value in (1, 2)
        ))

    results = asyncio.run(invoke())
    assert [result.structured_content for result in results] == [
        {"status": "success", "value": 1}, {"status": "success", "value": 2},
    ]
    assert events == [
        (phase, value, threading.get_ident())
        for value in (1, 2) for phase in ("start", "end")
    ]


def test_stdio_progress_reaches_the_same_request_through_all_dispatch_routes():
    async def inspect():
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).with_name("mcpserver_stdio_fixture.py"))],
            env={"QIAOTONG_HTTP_URL": "http://localhost:1/pythonForQt/"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for name, arguments in (
                    ("run_analysis", {"read_timeout": 60}),
                    ("analyze_model", {"request": {"operation": "run_analysis", "read_timeout": 60}}),
                    ("execute_operation", {"operation": "run_analysis", "arguments": {"read_timeout": 60}}),
                ):
                    progress = []

                    async def on_progress(value, total, message, progress=progress):
                        progress.append((value, total, message))

                    result = await session.call_tool(name, arguments, progress_callback=on_progress)
                    assert not result.is_error, result
                    assert result.structured_content["status"] == "success"
                    assert progress and progress[0][0] > 0
                    assert all(total == 60 for _, total, _ in progress)
                invalid = await session.call_tool("execute_operation", {
                    "operation": "create_nodes_linear", "arguments": {"count": 0},
                })
                assert invalid.is_error
                unknown = await session.call_tool("get_operation_schema", {"operation": "absent"})
                assert unknown.is_error and "Unknown operation" in unknown.content[0].text
                # A tool error must not terminate the stdio session.
                state = await session.call_tool("get_model_status", {})
                assert not state.is_error and state.structured_content["status"] == "model_state"

    asyncio.run(asyncio.wait_for(inspect(), timeout=30))


def test_job_survives_stdio_restart_and_status_disconnect_without_resubmission(tmp_path):
    database = tmp_path / "jobs.db"
    offline = Path(str(database) + ".offline")
    submissions = Path(str(database) + ".submissions")

    async def inspect():
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).with_name("mcpserver_stdio_fixture.py"))],
            env={"QIAOTONG_HTTP_URL": "http://localhost:1/pythonForQt/", "QIAO_MCP_JOB_DB": str(database)},
        )
        request = {"operation": "start_analysis_job", "arguments": {"request_id": "stdio-restart-test"}}
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                first = await session.call_tool("execute_operation", request)
                assert not first.is_error, first
                job = first.structured_content["job"]
                assert job["state"] == "running"

        # Restart the MCP process with the same durable store and a failed
        # desktop status read. An uncertain poll must not submit another solve.
        offline.touch()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                polled = await session.call_tool("get_analysis_job", {"job_id": job["job_id"]})
                assert not polled.is_error, polled
                assert polled.structured_content["job"]["state"] == "unknown"
                offline.unlink()
                replayed = await session.call_tool("execute_operation", request)
                assert not replayed.is_error, replayed
                assert replayed.structured_content["job"]["job_id"] == job["job_id"]
                completed = await session.call_tool("get_analysis_job", {"job_id": job["job_id"]})
                restored = completed.structured_content["job"]
                assert not completed.is_error and restored["state"] == "completed"
                assert restored["backend_started_at"] == job["backend_started_at"]
                assert restored["model_instance_id"] == job["model_instance_id"]
        assert submissions.read_text().splitlines() == ["submitted"]

    asyncio.run(asyncio.wait_for(inspect(), timeout=30))
