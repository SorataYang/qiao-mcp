"""假 QtServer 离线集成测试。

不同于签名契约测试（静态校验参数可绑定），本测试驱动**真实的 qtmodel API**
经真实 provider、经 envelope 包装的真实工具，一路到 qtmodel 的唯一 HTTP 出口
QtServer.send_command，拦截并断言真正下发的 header 与 JSON payload。

这能捕获契约测试看不到的下发形状错误（参数被漏发/错发/类型转换错误），
且完全离线——不需要桥通软件。
"""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from qiao_mcp.tools.envelope import register_tools_with_envelope
from qiao_mcp.tools.moving_load import register_moving_load_tools
from qiao_mcp.tools.tendon import register_tendon_tools
from conftest import ready_model_state


class RecordingQtServer:
    """拦截 QtServer.send_command 的假服务端，记录 (header, payload)。"""

    def __init__(self, response=""):
        self.requests = []
        self._response = response

    def send_command(self, command="", header="", read_timeout=600):
        payload = None
        if command:
            try:
                payload = json.loads(command)
            except json.JSONDecodeError:
                payload = command
        self.requests.append((header, payload))
        return self._response

    def by_header(self, header):
        return [p for h, p in self.requests if h == header]


@pytest.fixture
def wire(monkeypatch):
    """真实 provider + 真实 qtmodel，HTTP 出口被拦截。返回 recorder。"""
    from qtmodel.core.qt_server import QtServer

    rec = RecordingQtServer(response="")
    monkeypatch.setattr(QtServer, "send_command", staticmethod(rec.send_command))
    return rec


def _real_provider():
    """真实 QtModelProvider，跳过软件连接探测但保留真实 mdb/odb/cdb。"""
    import qtmodel

    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = qtmodel.mdb
    p._odb = qtmodel.odb
    p._cdb = qtmodel.cdb
    p.get_model_state = ready_model_state
    return p


def _tools(register, provider):
    mcp = FastMCP("t")
    register_tools_with_envelope(mcp, register, provider)
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


# ── 建模：批量节点/单元的真实下发 ─────────────────────────────────────


def test_create_nodes_linear_emits_full_coordinate_payload(wire):
    fns = _tools(register_modeling_tools, _real_provider())
    fns["create_nodes_linear"](count=3, start_x=0.0, spacing_x=1.0, start_id=1)

    add = wire.by_header("ADD-NODES")
    assert add, "应下发 ADD-NODES 请求"
    node_data = add[0]["node_data"]
    assert node_data == [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]


def test_create_beam_elements_linear_wires_node_pairs(wire):
    fns = _tools(register_modeling_tools, _real_provider())
    fns["create_beam_elements_linear"](
        node_id_start=1, count=2, mat_id=1, sec_id=1
    )
    add = wire.by_header("ADD-ELEMENTS")
    assert add, "应下发 ADD-ELEMENTS 请求"
    ele = add[0]["ele_data"]
    # [id, type, mat, sec, beta, nodeI, nodeJ, initType, initVal]
    assert ele[0][5:7] == [1, 2]
    assert ele[1][5:7] == [2, 3]


# ── 高级边界：参数名映射真实到达 qtmodel ──────────────────────────────


def test_master_slave_link_wire_uses_slave_id(wire):
    fns = _tools(register_advanced_boundary_tools, _real_provider())
    fns["add_master_slave_link"](
        master_node_id=1, slave_node_ids=[2, 3],
        dof_constraints=[True, True, True, False, False, False],
    )
    req = wire.by_header("ADD-MASTER-SLAVE-LINK")
    assert req, "应下发主从约束请求"
    payload = req[0]
    assert payload["master_id"] == 1
    assert payload["slave_id"] == [2, 3], "wire 上必须是 slave_id（单数）"
    assert payload["boundary_info"] == [True, True, True, False, False, False]


def test_elastic_support_wire_uses_boundary_info(wire):
    fns = _tools(register_advanced_boundary_tools, _real_provider())
    fns["add_elastic_support"](node_id=1, spring_values=[3, 1e6], support_type=3)
    req = wire.by_header("ADD-ELASTIC-SUPPORT")
    assert req
    assert req[0]["support_type"] == 3
    assert req[0]["boundary_info"] == [3, 1e6]


# ── 钢束：具名参数组装为真实 steel_detail/slip_info ──────────────────


def test_tendon_property_wire_builds_steel_detail(wire):
    fns = _tools(register_tendon_tools, _real_provider())
    fns["create_tendon_property"](
        name="15-10", material_name="钢绞线",
        area=0.00139, duct_diameter=0.09, friction=0.22, deviation=0.0015,
    )
    req = wire.by_header("ADD-TENDON-PROPERTY")
    assert req
    assert req[0]["steel_detail"] == [0.00139, 0.09, 0.22, 0.0015]
    assert req[0]["material_name"] == "钢绞线"


# ── 移动荷载：完整工作流真实下发到各自 header ─────────────────────────


def test_moving_load_workflow_wire_headers(wire):
    fns = _tools(register_moving_load_tools, _real_provider())
    fns["add_node_tandem"](name="纵列1", node_ids="1to5")
    fns["add_influence_plane"](name="影响面1", tandem_names=["纵列1"])
    fns["add_traffic_lane"](name="车道1", influence_name="影响面1", tandem_name="纵列1")

    assert wire.by_header("ADD-NODE-TANDEM")[0]["name"] == "纵列1"
    assert wire.by_header("ADD-INFLUENCE-PLANE")[0]["tandem_names"] == ["纵列1"]
    lane = wire.by_header("ADD-LANE-LINE")[0]
    assert lane["influence_name"] == "影响面1"
    assert lane["tandem_name"] == "纵列1"


# ── 只读查询：真实解析 QtServer 响应 ──────────────────────────────────


def test_get_nodes_parses_server_response(monkeypatch):
    from qtmodel.core.qt_server import QtServer

    from qiao_mcp.tools.queries import register_query_tools

    canned = json.dumps([{"node_id": 1, "x": 0.0, "y": 0.0, "z": 0.0}])
    monkeypatch.setattr(
        QtServer, "send_command",
        staticmethod(lambda command="", header="", read_timeout=600: canned),
    )
    fns = _tools(register_query_tools, _real_provider())
    result = fns["get_model_data"](kind="nodes")
    text = result["message"] if isinstance(result, dict) else str(result)
    assert '"node_id": 1' in text or "'node_id': 1" in text


def test_node_objects_are_normalized_to_dicts(wire, monkeypatch):
    """回归：qtmodel 的 Node/Element __repr__ 返回 dict，
    provider 必须用 to_dict() 拍平，否则 JSON 序列化崩溃。"""
    import json as _json

    from qtmodel.core.qt_server import QtServer

    canned = _json.dumps([{"node_id": 1, "x": 1.0, "y": 2.0, "z": 3.0}])
    monkeypatch.setattr(
        QtServer, "send_command",
        staticmethod(lambda command="", header="", read_timeout=600: canned),
    )
    provider = _real_provider()
    data = provider.get_node_data()
    assert data == [{"node_id": 1, "x": 1.0, "y": 2.0, "z": 3.0}]
    # 必须可被 json 序列化（工具层 _fmt 依赖此）
    _json.dumps(data)
