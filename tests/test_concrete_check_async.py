"""The concrete-check worker preserves context and never blocks the MCP loop."""

import asyncio
import threading
from contextvars import ContextVar

import pytest
from conftest import tool_fns

from qiao_mcp.tools.checking import register_checking_tools


@pytest.mark.parametrize("cancel", [False, True])
def test_check_wait_is_responsive_and_context_is_inherited(fake_provider, monkeypatch, cancel):
    marker = ContextVar("check-marker", default="missing")
    release = threading.Event()
    entered = threading.Event()
    seen = []
    progress = []

    def solve(**kwargs):
        seen.append(marker.get())
        entered.set()
        assert release.wait(2), "event loop did not release the worker"
        return {"state": "succeeded"}

    class Context:
        async def report_progress(self, **kwargs):
            progress.append(kwargs)

    fake_provider.solve_concrete_check = solve
    monkeypatch.setattr("qiao_mcp.execution.HEARTBEAT_SECONDS", 0.01)
    fn = tool_fns(register_checking_tools, fake_provider)["run_concrete_check"]

    async def scenario():
        token = marker.set("protected-instance")
        try:
            task = asyncio.create_task(fn(ctx=Context(), name="C1"))
            try:
                for _ in range(100):
                    if entered.is_set() and progress:
                        break
                    await asyncio.sleep(0.005)
                assert entered.is_set() and progress
                if cancel:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    assert not release.is_set()
                release.set()
                if not cancel:
                    assert (await task)["status"] == "success"
            finally:
                release.set()
        finally:
            marker.reset(token)

    asyncio.run(scenario())
    assert seen == ["protected-instance"]
