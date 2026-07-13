"""共享测试设施：假 qtmodel 数据库对象与脱离真实连接的 provider。"""

import pytest
from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers.qtmodel_provider import QtModelProvider


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
    return p


def tool_fns(register, provider):
    """注册工具到临时 FastMCP 实例并返回 {工具名: 可调用函数}。"""
    mcp = FastMCP("test")
    register(mcp, provider)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}
