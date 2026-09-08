"""假 QtServer 离线集成测试。

不同于签名契约测试（静态校验参数可绑定），本测试驱动**真实的 qtmodel API**
经真实 provider、经 envelope 包装的真实工具，一路到 qtmodel 的唯一 HTTP 出口
QtServer.send_command，拦截并断言真正下发的 header 与 JSON payload。

这能捕获契约测试看不到的下发形状错误（参数被漏发/错发/类型转换错误），
且完全离线——不需要桥通软件。
"""

import asyncio
import inspect
import json
from unittest.mock import Mock

import pytest
from conftest import ready_model_state
from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.resources import register_resources
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope
from qiao_mcp.tools.moving_load import register_moving_load_tools
from qiao_mcp.tools.queries import register_query_tools
from qiao_mcp.tools.tendon import register_tendon_tools


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


@pytest.mark.parametrize(("kind", "header", "row"), [
    ("materials", "GET-MATERIAL-DATA", {
        "index": 7, "name": "C50", "mat_type": 1, "future_server_field": "kept",
    }),
    ("thickness", "GET-THICKNESS-DATA", {"thick_id": 1, "name": "顶板", "t": 0.3}),
    ("nodal_force_loads", "GET-NODAL-FORCE-LOAD", {
        "index": 2, "node_id": 1, "case_name": "恒载", "load_info": [0, 0, -10, 0, 0, 0],
    }),
    ("tendon_properties", "GET-TENDON-PROPERTY-DATA", {"name": "15-12", "tendon_type": 1}),
    ("pre_stress_loads", "GET-PRE-STRESS-LOAD", {
        "case_name": "预应力", "tendon_name": "T1", "tendon_type": 2, "force": 1200.0,
    }),
    ("node_masses", "GET-NODE-MASS-DATA", {"node_id": 1, "mass_info": [10, 1, 1, 1]}),
    ("constraint_equations", "GET-CONSTRAINT-EQUATION-DATA", {
        "index": 6, "name": "CE1", "sec_node": 15, "sec_dof": 1,
        "master_info": [[16, 1, 1.0]],
    }),
    ("structure_group_summaries", "GET-STRUCTURE-GROUP-SUMMARIES", {
        "group_id": 1, "name": "主梁", "node_count": 4, "element_count": 3,
    }),
])
def test_typed_model_queries_preserve_wire_fields_in_tool_json(wire, kind, header, row):
    wire._response = json.dumps([row])
    functions = _tools(register_query_tools, _real_provider())
    result = functions["get_model_data"](kind=kind)
    assert json.loads(result["message"].split("\n", 2)[2]) == [row]
    assert wire.requests == [(header, None)]


def test_material_resource_serializes_typed_records(wire):
    row = {"index": 7, "name": "C50", "mat_type": 1, "future_server_field": "kept"}
    wire._response = json.dumps([row])
    server = FastMCP("resource-test")
    register_resources(server, _real_provider())
    contents = list(asyncio.run(server.read_resource("bridge://model/materials")))
    assert json.loads(contents[0].content) == [row]


def test_model_section_shape_keeps_wire_command(wire):
    wire._response = json.dumps({"section_type": "矩形", "parts": []})
    result = _real_provider().get_section_shape(12)
    assert isinstance(result, dict)
    json.dumps(result)
    assert len(wire.requests) == 1
    assert wire.by_header("GET-SECTION-SHAPE")[0]["sec_id"] == 12


def test_gateway_serializes_real_typed_model_records(wire):
    row = {"index": 7, "name": "C50", "mat_type": 1}
    wire._response = json.dumps([row])
    provider = _real_provider()
    api_object = "mdb" if hasattr(provider._mdb, "get_material_data") else "odb"
    functions = _tools(register_api_gateway_tools, provider)
    result = functions["call_qtmodel_api"](api_object=api_object, method="get_material_data")
    assert json.loads(result["message"].split("\n", 1)[1]) == [row]
    assert wire.requests == [("GET-MATERIAL-DATA", None)]


@pytest.mark.parametrize("t_out", [None, 0.0, 0.4])
def test_thickness_option_uses_real_signature_and_wire_payload(wire, t_out):
    provider = _real_provider()
    functions = _tools(register_modeling_tools, provider)
    supported = "t_out" in inspect.signature(provider._mdb.add_thickness).parameters
    if t_out is not None and not supported:
        with pytest.raises(ToolError, match="does not support.*t_out"):
            functions["add_thickness"](name="桥面板", t=0.2, t_out=t_out)
        assert wire.requests == []
        return

    functions["add_thickness"](name="桥面板", t=0.2, t_out=t_out)
    payload = wire.by_header("ADD-THICKNESS")[0]
    assert payload["t"] == 0.2
    assert payload["thick_type"] == 0
    if t_out is None:
        assert "t_out" not in payload
    else:
        assert payload["t_out"] == t_out


@pytest.mark.parametrize("show_view", [False, True])
def test_solve_window_option_preserves_real_background_protocol(wire, monkeypatch, show_view):
    from qtmodel.mdb.mdb_project import MdbProject

    provider = _real_provider()
    wait = Mock(return_value={"state": "succeeded"})
    monkeypatch.setattr(MdbProject, "wait_solve", wait)
    supported = "show_view" in inspect.signature(provider._mdb.do_solve).parameters
    if show_view and not supported:
        with pytest.raises(ValueError, match="does not support.*show_view"):
            provider.run_analysis(read_timeout=120, show_view=show_view)
        assert wire.requests == []
        wait.assert_not_called()
        return

    provider.run_analysis(read_timeout=120, show_view=show_view)
    payload = wire.by_header("DO-SOLVE")[0] or {}
    assert payload.get("sync", False) is False
    if supported:
        assert payload["show_view"] is show_view
    else:
        assert "show_view" not in payload
    wait.assert_called_once_with(poll_interval=2.0, max_wait=120, read_timeout=30)


@pytest.mark.parametrize("method", [
    "reset_global_setting", "reset_construction_stage_setting", "reset_operation_stage_setting",
    "reset_self_vibration_setting", "reset_live_load_setting", "reset_elastic_buckling_setting",
    "reset_non_linear_setting", "reset_track_geometry_setting", "reset_dynamic_analysis_setting",
    "reset_time_history_setting", "reset_response_spectrum_setting", "reset_all_setting",
    "copy_thicknesses", "arrange_thickness_ids", "remove_thicknesses",
])
def test_new_management_apis_are_discoverable_and_callable_through_gateway(wire, method):
    provider = _real_provider()
    functions = _tools(register_api_gateway_tools, provider)
    kwargs = {"ids": [5, 2, 5]} if method in {"copy_thicknesses", "remove_thicknesses"} else {}
    listed = {entry["method"] for entry in provider.list_api_methods("mdb")}
    if not hasattr(provider._mdb, method):
        assert method not in listed
        with pytest.raises(ToolError, match="has no method"):
            functions["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
        assert wire.requests == []
        return

    assert method in listed
    functions["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    payloads = wire.by_header(method.replace("_", "-").upper())
    assert len(payloads) == 1
    if kwargs:
        assert payloads[0]["ids"] == [5, 2]
