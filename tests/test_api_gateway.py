"""逃生舱工具行为测试：方法发现、签名先验校验、危险方法拦截。"""

import pytest

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError

from conftest import tool_fns, tool_text


class RealSigMdb:
    """带真实签名的假 mdb，用于验证签名先验校验。"""

    def __init__(self):
        self.calls = []

    def add_tendon_group(self, name: str = ""):
        self.calls.append(("add_tendon_group", {"name": name}))

    def update_model(self):
        self.calls.append(("update_model", {}))

    def initial(self):  # 危险方法
        self.calls.append(("initial", {}))


@pytest.fixture
def gateway_provider():
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = RealSigMdb()
    p._odb = None
    p._cdb = None
    return p


def test_list_api_filters_by_pattern(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    text = tool_text(fns["list_qtmodel_api"](api_object="mdb", pattern="tendon"))
    assert "add_tendon_group(name: str = '')" in text
    assert "update_model" not in text


def test_call_api_dispatches_and_refreshes(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    result = fns["call_qtmodel_api"](
        api_object="mdb", method="add_tendon_group", kwargs={"name": "钢束组1"}
    )
    assert "successfully" in tool_text(result)
    calls = gateway_provider._mdb.calls
    assert ("add_tendon_group", {"name": "钢束组1"}) in calls
    assert ("update_model", {}) in calls, "mdb 的 add_* 调用后应刷新模型"


def test_call_api_rejects_wrong_kwargs_before_dispatch(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](
            api_object="mdb", method="add_tendon_group", kwargs={"nameX": "x"}
        )
    msg = str(exc.value)
    assert "参数不匹配" in msg
    assert "add_tendon_group(name: str = '')" in msg, "报错须回显真实签名"
    assert gateway_provider._mdb.calls == [], "校验失败不得下发"


def test_call_api_blocks_dangerous_methods(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](api_object="mdb", method="initial")
    msg = str(exc.value)
    assert "not callable via the gateway" in msg or "逃生舱" in msg
    assert gateway_provider._mdb.calls == []


def test_call_api_unknown_method(gateway_provider):
    fns = tool_fns(register_api_gateway_tools, gateway_provider)
    with pytest.raises(ToolError) as exc:
        fns["call_qtmodel_api"](api_object="mdb", method="no_such_method")
    assert "no method" in str(exc.value)
