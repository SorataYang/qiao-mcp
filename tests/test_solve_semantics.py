"""qtmodel 2.5.0 求解语义迁移测试。

2.5.0 把 do_solve 的默认行为**反转**了：

- 2.3.3：`do_solve(read_timeout=600)` 同步阻塞，返回即代表求解完成
- 2.5.0：`do_solve(..., wait=False, ...)` 默认只**启动**后台求解，sleep(3) 后返回

签名仍能绑定（新增参数全部可选），契约测试无法察觉；若不显式传 wait=True，
run_analysis 会在求解仍在后台运行时就宣告"分析完成"，
后续 get_analysis_results 取到的是上一次的结果或空结果。
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
