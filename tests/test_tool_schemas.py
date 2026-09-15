"""Public FastMCP catalog, validation and response contracts."""

import asyncio
import base64
from unittest.mock import Mock

import pytest
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import ToolError


@pytest.fixture
def catalog(fake_provider):
    mcp = FastMCP("catalog-test")
    register_tool_catalog(mcp, fake_provider)
    return mcp


def test_complete_catalog_has_documented_inputs_and_output_contracts(catalog):
    tools = asyncio.run(catalog.list_tools())
    assert len(tools) == 133
    image_tools = {"save_model_screenshot", "plot_analysis_result"}
    for tool in tools:
        assert tool.description
        assert tool.annotations is not None
        properties = tool.inputSchema.get("properties", {})
        assert "ctx" not in properties
        for name, schema in properties.items():
            assert schema.get("description"), f"{tool.name}.{name} lacks a description"
        if tool.name in image_tools:
            assert tool.outputSchema is None
        else:
            assert tool.outputSchema is not None, tool.name
            assert "status" in tool.outputSchema["properties"], tool.name


def test_schema_exposes_ranges_enums_lengths_and_workflow_fields(catalog):
    tools = {tool.name: tool for tool in asyncio.run(catalog.list_tools())}
    query = tools["get_model_data"].inputSchema["properties"]
    assert "materials" in query["kind"]["enum"]
    assert (query["limit"]["minimum"], query["limit"]["maximum"]) == (1, 500)
    assert query["offset"]["minimum"] == 0
    release = tools["add_beam_constraint"].inputSchema["properties"]["release_i"]["anyOf"]
    assert any(item.get("minItems") == item.get("maxItems") == 6 for item in release)
    workflow = tools["create_simple_beam_bridge"].outputSchema["properties"]
    assert {"node_ids", "element_ids", "support_node_ids", "material_id", "section_id"} <= workflow.keys()
    assert tools["manage_check_stirrup"].inputSchema["properties"]["action"]["enum"] == ["update", "remove"]
    assert "custom" in tools["set_view_angle"].inputSchema["properties"]["angle_preset"]["enum"]
    boundary_kinds = tools["remove_boundary"].inputSchema["properties"]["kind"]["enum"]
    assert {"support", "一般支承", "beam_constraint", "梁端约束"} <= set(boundary_kinds)
    for name in ("manage_check_stirrup", "assign_element_stirrup", "manage_check_case_file"):
        assert tools[name].annotations.destructiveHint is True


@pytest.mark.parametrize("name, arguments", [
    ("create_material", {"name": "Invalid", "mat_type": 99}),
    ("create_nodes_linear", {"count": 0}),
    ("get_model_data", {"kind": "unknown"}),
    ("get_model_data", {"kind": "nodes", "limit": 501}),
    ("get_model_data", {"kind": "nodes", "offset": -1}),
    ("add_beam_constraint", {"beam_id": 1, "release_i": [False] * 5}),
    ("add_master_slave_link", {"master_node_id": 1, "slave_node_ids": [2], "dof_constraints": [True]}),
    ("call_qtmodel_api", {"api_object": "invalid", "method": "get_node_data"}),
    ("create_continuous_beam_bridge", {"spans": []}),
    ("create_simple_beam_bridge", {"section_height": 0}),
    ("run_analysis", {"read_timeout": 0}),
    ("apply_prestress", {"case_name": "P", "tendon_name": [], "force": 1000}),
    ("apply_prestress", {"case_name": "P", "tendon_name": "T1", "force": 1000, "tension_type": 3}),
    ("add_load_combine", {"name": "C", "combine_info": [["Dead", "ST", 1.2]]}),
    ("create_polygon_section", {"name": "S", "loop_segments": {"main": [[0, 0, 0], [1, 0], [1, 1]]}}),
    ("create_nodes", {"node_data": []}),
    ("create_nodes", {"node_data": [[0, 0, 0], [1, 2]]}),
    ("create_material", {"name": "M", "mat_type": 5, "data_info": [1, 2, 3]}),
    ("create_line_width_section", {"name": "S", "sec_lines": [[0, 0, 1, 1]]}),
    ("add_spectrum_case", {"name": "RS", "info_x": ["F"]}),
    ("add_time_history_function", {"name": "TH", "function_info": [[0, 0, 1]]}),
    ("add_creep_function", {"name": "C", "creep_data": [[0, float("nan")]]}),
    ("add_distribute_plane_load", {"index": -1, "case_name": "L", "type_name": "P", "point1": [0, 0]}),
    ("create_tendon_2d", {"name": "T", "property_name": "P", "control_points": [[0, 0, 0]], "point_insert": [0, 0]}),
    ("add_tendon_3d", {"name": "T", "property_name": "P", "control_points": [[0, 0, 0]], "point_insert": [0, 0, 0]}),
    ("add_constraint_equation", {"name": "CE", "slave_node": 1, "master_info": [[2, 7, 1.0]]}),
    ("add_beam_section_temperature", {"element_id": 1, "case_name": "T", "sec_type": 3}),
    ("remove_boundary", {"remove_id": 1, "kind": "unknown"}),
    ("update_element", {"old_id": 1, "ele_type": 5}),
    ("set_view_angle", {"angle_preset": "unknown"}),
    ("manage_check_stirrup", {"action": "unknown"}),
    ("assign_element_stirrup", {"action": "unknown"}),
    ("manage_check_case_file", {"action": "unknown"}),
])
def test_invalid_inputs_are_rejected_before_state_probe_or_backend(
    catalog, fake_provider, monkeypatch, name, arguments,
):
    guard = Mock()
    monkeypatch.setattr(fake_provider, "ensure_operation_allowed", guard)
    with pytest.raises(ToolError):
        asyncio.run(catalog.call_tool(name, arguments))
    guard.assert_not_called()
    assert fake_provider._mdb.calls == fake_provider._odb.calls == fake_provider._cdb.calls == []


def test_spring_type_and_direction_are_validated_before_writing(catalog, fake_provider):
    for values in ([1, 2, 3, 4, 5, 6], [9, 1000]):
        with pytest.raises(ToolError):
            asyncio.run(catalog.call_tool("add_elastic_support", {
                "node_id": 1, "support_type": 2, "spring_values": values,
            }))
    assert fake_provider._mdb.count("add_elastic_support") == 0


def test_combination_keeps_native_type_name_factor_order(catalog, fake_provider):
    _, result = asyncio.run(catalog.call_tool("add_load_combine", {
        "name": "Envelope", "combine_type": 3,
        "combine_info": [["ST", "Dead", 1.2], ["CS", "合计值", 1.0]],
    }))
    assert result["status"] == "success"
    kwargs = fake_provider._mdb.last("add_load_combine")[2]
    assert kwargs["combine_type"] == 3
    assert kwargs["combine_info"] == [("ST", "Dead", 1.2), ("CS", "合计值", 1.0)]


@pytest.mark.parametrize("node_data", [
    [[0, 0, 0], [1, 0, 0]],
    [[10, 0, 0, 0], [20, 1, 0, 0]],
])
def test_both_native_node_coordinate_formats_remain_accepted(catalog, fake_provider, node_data):
    _, result = asyncio.run(catalog.call_tool("create_nodes", {"node_data": node_data}))
    assert result["status"] == "success"
    assert fake_provider._mdb.last("add_nodes")[2]["node_data"] == node_data


@pytest.mark.parametrize("name, points", [
    ("create_tendon_2d", [[0, -1, 0], [10, -1, 0]]),
    ("add_tendon_3d", [[0, 0, -1, 0], [10, 0, -1, 0]]),
])
def test_tendon_schemas_keep_track_positioning_and_native_point_order(
    catalog, fake_provider, name, points,
):
    _, result = asyncio.run(catalog.call_tool(name, {
        "name": "T", "property_name": "P", "control_points": points,
        "position_type": 2, "point_insert": [2, 1, 37],
    }))
    assert result["status"] == "success"
    method = "add_tendon_2d" if name == "create_tendon_2d" else "add_tendon_3d"
    kwargs = fake_provider._mdb.last(method)[2]
    assert kwargs["point_insert"] == (2, 1, 37)
    assert kwargs["control_points"] == [tuple(point) for point in points]


def test_spectrum_function_reference_keeps_name_factor_order(catalog, fake_provider):
    _, result = asyncio.run(catalog.call_tool("add_spectrum_case", {
        "name": "RS", "info_x": ["Spectrum", 1.25],
    }))
    assert result["status"] == "success"
    assert fake_provider._mdb.last("add_spectrum_case")[2]["info_x"] == ("Spectrum", 1.25)


@pytest.mark.parametrize("kind", ["beam_constraint", "梁端约束"])
def test_boundary_enum_keeps_english_and_native_chinese_names(catalog, fake_provider, kind):
    _, result = asyncio.run(catalog.call_tool("remove_boundary", {"remove_id": 7, "kind": kind}))
    assert result["status"] == "success"
    assert fake_provider._mdb.last("remove_boundary")[2]["kind"] == "梁端约束"


def test_api_object_normalization_precedes_enum_validation(catalog, fake_provider):
    _, result = asyncio.run(catalog.call_tool("call_qtmodel_api", {
        "api_object": " MDB ", "method": "get_node_data", "kwargs": {},
    }))
    assert result["status"] == "success"
    assert fake_provider._mdb.count("get_node_data") == 1


def test_connection_result_has_structured_fields_and_preserves_text(catalog, fake_provider, monkeypatch):
    monkeypatch.setattr(fake_provider, "get_connection_status", lambda: {
        "status": "software_not_running", "connected": False, "compatible": None,
        "message": "Start QiaoTong", "action": "Start the application", "client": {}, "server": {},
    })
    content, structured = asyncio.run(catalog.call_tool("check_qiaotong_connection", {}))
    assert content[0].type == "text"
    assert structured["status"] == "success"
    assert structured["connection_status"] == "software_not_running"
    assert structured["connected"] is False
    assert "Start QiaoTong" in structured["message"]


def test_readonly_state_keeps_backend_status_in_structured_content(catalog):
    _, structured = asyncio.run(catalog.call_tool("get_model_status", {}))
    assert structured["status"] == "model_state"
    assert structured["model_state"]["capabilities"]["modify_model"] is True


def test_state_schema_preserves_new_backend_fields(catalog, fake_provider, monkeypatch):
    monkeypatch.setattr(fake_provider, "get_model_state", lambda: {
        "status": "state_unknown", "connected": True,
        "model_state_schema": 2, "reason": {"code": "desktop_too_old"},
    })
    _, result = asyncio.run(catalog.call_tool("get_model_status", {}))
    assert result["status"] == "state_unknown"
    assert result["model_state_schema"] == 2
    assert result["reason"] == {"code": "desktop_too_old"}


@pytest.mark.parametrize("name, arguments, method", [
    ("save_model_screenshot", {"view_angle": "current"}, "save_model_image"),
    ("plot_analysis_result", {"result_type": "displacement"}, "plot_result"),
])
def test_image_survives_sdk_serialization(
    catalog, fake_provider, monkeypatch, tmp_path, name, arguments, method,
):
    path = tmp_path / "model.png"
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg=="
    )
    monkeypatch.setattr(fake_provider, method, lambda **kwargs: path.write_bytes(png))
    content = asyncio.run(catalog.call_tool(name, {
        "file_path": str(path), "return_image": True, **arguments,
    }))
    assert content[0].type == "image"
    assert content[0].mimeType == "image/png"
    assert base64.b64decode(content[0].data) == png
