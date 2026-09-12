"""qtmodel 求解语义迁移测试。

do_solve 的默认行为已被上游反转过两次，签名都仍能绑定（新增参数全部可选），
契约测试无法察觉，故在此用假 mdb 锁住 provider 实际传入的关键字：

- 2.3.3：`do_solve(read_timeout=600)` 同步阻塞，返回即代表求解完成
- 2.5.0：`do_solve(..., wait=False, sync=False)` 默认只**启动**后台求解便返回。
  若不显式传 wait=True，run_analysis 会在求解仍在后台运行时就宣告"分析完成"。
- 2.6.3–2.8.2：`do_solve(..., wait=True, sync=True)`。sync=True 让 C# 在本次
  HTTP 请求内阻塞到求解完成，源码 ``if wait and not sync`` 使 wait/max_wait/
  poll_interval **全部失效**，实际时限退化为该请求的 read_timeout（默认 600 s）。
  若不显式传 sync=False，用户给的 3600 s 预算形同虚设，600 s 一到就报超时。
"""

from __future__ import annotations

import asyncio

import pytest
from conftest import FakeDb, ready_model_state, tool_text
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope


class _Ctx:
    async def report_progress(self, progress, total=None, message=None):
        pass


@pytest.fixture
def provider():
    from qiao_mcp.providers.qtmodel_provider import QtModelProvider

    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeDb()
    p._odb = FakeDb()
    p._cdb = FakeDb()
    p.get_model_state = ready_model_state
    return p


@pytest.fixture
def run_analysis(provider):
    mcp = FastMCP("t")
    register_tools_with_envelope(mcp, register_modeling_tools, provider)
    fn = {t.name: t.fn for t in mcp._tool_manager.list_tools()}["run_analysis"]
    return fn


def test_solve_waits_for_completion(run_analysis, provider):
    """必须显式 wait=True，否则只是启动后台任务就报完成。"""
    asyncio.run(run_analysis(ctx=_Ctx()))
    _, _, kw = provider._mdb.last("do_solve")
    assert kw.get("wait") is True, (
        "2.5.0 的 do_solve 默认 wait=False 只启动后台求解；"
        "不传 wait=True 会导致求解未完成就宣告分析完成"
    )


def test_read_timeout_becomes_total_solve_budget(run_analysis, provider):
    """read_timeout 应作为求解总时限 max_wait，而非单次 HTTP 超时。"""
    asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=120))
    _, _, kw = provider._mdb.last("do_solve")
    assert kw.get("max_wait") == 120
    # 单次状态查询超时应独立于总时限，不能把 3600 塞进每次查询
    assert kw.get("status_read_timeout", 30) <= 60


def test_solve_runs_as_background_task_so_max_wait_applies(run_analysis, provider):
    """必须显式 sync=False，否则 2.6.3+ 的 sync=True 默认值会让 max_wait 失效。

    do_solve 源码：``if wait and not sync: return wait_solve(...)``。
    sync=True 时 C# 在 HTTP 请求内阻塞，wait/max_wait 都不会被读取，
    实际时限是该请求的 read_timeout（默认 600 s）——上一条测试断言的 max_wait
    只有在 sync=False 下才真正生效。
    """
    asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=3600))
    _, _, kw = provider._mdb.last("do_solve")
    assert kw.get("sync") is False, (
        "2.6.3 起 do_solve 默认 sync=True，C# 同步阻塞且忽略 wait/max_wait；"
        "不传 sync=False 会让 3600 s 预算退化为 600 s 的 HTTP 读超时"
    )
    assert kw.get("wait") is True


def test_solve_failure_propagates_as_tool_error(provider, run_analysis):
    """qtmodel 在求解 failed/canceled 时抛 RuntimeError，应转为 ToolError。"""

    def boom(**kwargs):
        raise RuntimeError("Project solve failed: 刚度矩阵奇异")

    provider._mdb.do_solve = boom
    with pytest.raises(ToolError) as exc:
        asyncio.run(run_analysis(ctx=_Ctx()))
    assert "刚度矩阵奇异" in str(exc.value)


def test_solve_timeout_propagates_as_tool_error(provider, run_analysis):
    """超过 max_wait 时 qtmodel 抛 TimeoutError，应转为 ToolError 而非静默成功。"""

    def slow(**kwargs):
        raise TimeoutError("Project solve did not finish within 120 seconds.")

    provider._mdb.do_solve = slow
    with pytest.raises(ToolError) as exc:
        asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=120))
    assert "did not finish" in str(exc.value)


def test_success_message_only_after_solve_returns(run_analysis, provider):
    result = asyncio.run(run_analysis(ctx=_Ctx()))
    assert "completed" in tool_text(result).lower()
    assert provider._mdb.count("do_solve") == 1


def test_show_view_is_independent_of_background_solve_options(run_analysis, provider):
    asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=120, show_view=True))
    kwargs = provider._mdb.last("do_solve")[2]
    assert kwargs["show_view"] is True
    assert kwargs["sync"] is False
    assert kwargs["wait"] is True
    assert kwargs["max_wait"] == 120
    assert kwargs["status_read_timeout"] == 30


@pytest.mark.parametrize("show_view", [False, True])
def test_legacy_solve_rejects_window_request_before_starting(provider, run_analysis, show_view):
    calls = []

    def legacy_solve(wait, sync, poll_interval, max_wait, status_read_timeout):
        calls.append({"wait": wait, "sync": sync, "max_wait": max_wait})

    provider._mdb.do_solve = legacy_solve
    if show_view:
        with pytest.raises(ToolError, match="does not support.*show_view"):
            asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=120, show_view=show_view))
        assert calls == []
    else:
        asyncio.run(run_analysis(ctx=_Ctx(), read_timeout=120, show_view=show_view))
        assert calls == [{"wait": True, "sync": False, "max_wait": 120}]
