"""run_analysis 异步化测试：长求解在工作线程执行、周期上报进度。"""

import asyncio
import threading
import time

import pytest
from conftest import FakeDb, tool_text
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import register_tools_with_envelope


class RecordingContext:
    """记录 report_progress 调用的假 Context。"""

    def __init__(self):
        self.progress_calls = []

    async def report_progress(self, progress, total=None, message=None):
        self.progress_calls.append((progress, total, message))


def _provider_with_solve(solve_fn):
    from qiao_mcp.providers.qtmodel_provider import QtModelProvider

    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeDb()
    p._odb = FakeDb()
    p._cdb = FakeDb()
    p._mdb.do_solve = solve_fn
    return p


def _run_analysis_fn(provider):
    mcp = FastMCP("t")
    register_tools_with_envelope(mcp, register_modeling_tools, provider)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}["run_analysis"]


def test_solve_runs_in_worker_thread_not_event_loop():
    solve_thread = {}

    def solve(read_timeout):
        solve_thread["name"] = threading.current_thread().name
        time.sleep(0.05)

    provider = _provider_with_solve(solve)
    fn = _run_analysis_fn(provider)
    result = asyncio.run(fn(ctx=RecordingContext()))
    assert tool_text(result).startswith("Analysis successfully completed")
    assert solve_thread["name"] != threading.current_thread().name, (
        "求解必须在工作线程执行，不得阻塞事件循环"
    )


def test_read_timeout_forwarded_to_solve():
    seen = {}

    def solve(read_timeout):
        seen["timeout"] = read_timeout

    provider = _provider_with_solve(solve)
    fn = _run_analysis_fn(provider)
    asyncio.run(fn(ctx=RecordingContext(), read_timeout=120))
    assert seen["timeout"] == 120


def test_progress_reported_for_long_solve():
    # 求解 >5s 才会触发首次心跳；用一个略超 5s 的假求解验证
    def solve(read_timeout):
        time.sleep(5.2)

    provider = _provider_with_solve(solve)
    fn = _run_analysis_fn(provider)
    ctx = RecordingContext()
    asyncio.run(fn(ctx=ctx))
    assert ctx.progress_calls, "耗时超过一个心跳周期时应至少上报一次进度"
    assert ctx.progress_calls[0][0] == 5


def test_solve_exception_propagates_as_error():
    def solve(read_timeout):
        raise RuntimeError("求解器崩溃")

    provider = _provider_with_solve(solve)
    fn = _run_analysis_fn(provider)
    from qiao_mcp.tools.envelope import ToolError

    with pytest.raises(ToolError) as exc:
        asyncio.run(fn(ctx=RecordingContext()))
    assert "求解器崩溃" in str(exc.value)
