"""共享测试设施：假 qtmodel 数据库对象与脱离真实连接的 provider。"""

import pytest
from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers.qtmodel_provider import QtModelProvider


def ready_model_state():
    """Stable open/base fixture state for provider-level tool unit tests."""
    return {
        "status": "model_state",
        "connected": True,
        "compatible": True,
        "model_state_schema": 1,
        "model_state": {
            "model_opened": True,
            "phase": "preprocessing",
            "application_stage": "PreStage",
            "stage_name": "基本",
            "is_base_stage": True,
            "is_solving": False,
            "has_result_data": False,
            "capabilities": {
                "read_model": True,
                "modify_model": True,
                "modify_stage_data": True,
                "query_results": True,
                "check_model": True,
                "run_check": True,
                "run_analysis": True,
                "view_model": True,
            },
        },
    }


class FakeDb:
    """记录全部方法调用的假 mdb/odb/cdb。"""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def last(self, name):
        matched = [c for c in self.calls if c[0] == name]
        assert matched, f"no call to {name}"
        return matched[-1]

    def count(self, name):
        return sum(1 for c in self.calls if c[0] == name)


@pytest.fixture
def fake_provider():
    """跳过 __init__ 的 import 探测，注入假数据库对象。"""
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeDb()
    p._odb = FakeDb()
    p._cdb = FakeDb()
    p.get_model_state = ready_model_state
    return p


def tool_fns(register, provider, wrap=True):
    """注册工具到临时 FastMCP 实例并返回 {工具名: 可调用函数}。

    wrap=True（默认）返回经 envelope 包装的函数，与生产一致：
    成功返回 dict，失败/校验抛 ToolError/ToolInputError。
    """
    from qiao_mcp.tools.envelope import register_tools_with_envelope

    # Existing unit tests use in-memory qtmodel facades and intentionally do
    # not connect to a running bridge. Give those facades a deterministic open
    # base-stage snapshot unless a test supplied its own state method.
    if isinstance(provider, QtModelProvider) and "get_model_state" not in vars(provider):
        provider.get_model_state = ready_model_state

    mcp = FastMCP("test")
    if wrap:
        register_tools_with_envelope(mcp, register, provider)
    else:
        register(mcp, provider)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


def tool_text(result):
    """从 envelope 结果中取出可读文本，便于断言。

    成功工具返回 dict（{status, message?, ...}）；此函数把它拍平成字符串。
    """
    if isinstance(result, dict):
        parts = [str(v) for k, v in result.items() if k != "status"]
        return " ".join(parts) if parts else str(result)
    return str(result)
