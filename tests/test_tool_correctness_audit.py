"""Regression cases found by tracing tools to real qtmodel request constructors."""

import asyncio
from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.group_management import register_group_tools
from qiao_mcp.tools.moving_load import register_moving_load_tools
from qiao_mcp.tools.tendon import register_tendon_tools


@pytest.mark.parametrize("tool, arguments, header", [
    ("add_node_tandem", {"name": "T", "node_ids": [1, 2]}, "ADD-NODE-TANDEM"),
    ("add_influence_plane", {"name": "P", "tandem_names": ["T"]}, "ADD-INFLUENCE-PLANE"),
])
def test_moving_load_geometry_is_committed_once(qtmodel_wire, tool, arguments, header):
    provider, requests = qtmodel_wire
    tool_fns(register_moving_load_tools, provider)[tool](**arguments)
    assert [command for command, _ in requests] == [header, "UPDATE"]


@pytest.mark.parametrize("sub_cases", [
    [["V", 1.0, "Lane"]], [["V", 1.0, [12]]], [["V", 1.0]],
    [["V", True, ["Lane"]]], [["V", float("inf"), ["Lane"]]],
])
def test_live_subcases_reject_bad_rows_before_writing(fake_provider, sub_cases):
    functions = tool_fns(register_moving_load_tools, fake_provider)
    with pytest.raises(ToolInputError, match="sub_cases"):
        functions["create_live_load_case"](name="MV", influence_plane="P", span=10, sub_cases=sub_cases)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("result_type", ["force", "stress", "deformation"])
@pytest.mark.parametrize("extreme", [1, 2])
def test_live_results_request_the_selected_extreme(qtmodel_wire, result_type, extreme):
    import qtmodel

    provider, requests = qtmodel_wire
    provider._odb = qtmodel.odb
    functions = tool_fns(register_moving_load_tools, provider)
    functions["get_live_load_results"](
        case_name="Verified result name", result_type=result_type, element_ids=[7], envelope_type=extreme,
    )
    assert len(requests) == 1
    payload = requests[0][1]
    assert payload["case_name"] == "Verified result name"
    assert payload["stage_id"] == -1
    assert payload["envelop_type"] == extreme


def node(nid, x):
    return {"node_id": nid, "x": x, "y": 0.0, "z": 0.0}


def test_node_resolution_does_not_choose_a_nearby_old_node(fake_provider):
    fake_provider._mdb.get_node_data = lambda: [node(7, 0.008), node(91, 0.0)]
    assert fake_provider.add_nodes_returning_ids(
        [[0, 0, 0]], is_merged=True, merge_error=0.001,
    ) == [91]


def test_node_resolution_does_not_expand_the_merge_tolerance(fake_provider):
    fake_provider._mdb.get_node_data = lambda: [node(7, 0.008)]
    assert fake_provider.add_nodes_returning_ids(
        [[0, 0, 0]], is_merged=True, merge_error=0.001,
    ) == []


@pytest.mark.parametrize("tolerance", [0.0, 1e-12])
def test_explicit_small_merge_radius_is_not_replaced_by_a_larger_floor(fake_provider, tolerance):
    fake_provider._mdb.get_node_data = lambda: [node(7, 1e-10)]
    assert fake_provider.add_nodes_returning_ids(
        [[0, 0, 0]], is_merged=True, merge_error=tolerance,
    ) == []


def test_unmerged_nodes_resolve_to_new_ids_at_existing_coordinates(fake_provider):
    fake_provider._mdb.get_node_data = Mock(side_effect=[
        [node(7, 0.0)], [node(7, 0.0), node(91, 0.0)],
    ])
    assert fake_provider.add_nodes_returning_ids([[0, 0, 0]], is_merged=False) == [91]


def test_merged_repeated_coordinates_preserve_one_id_per_coordinate(fake_provider):
    fake_provider._mdb.get_node_data = lambda: [node(7, 0.0)]
    assert fake_provider.add_nodes_returning_ids(
        [[0, 0, 0], [0, 0, 0]], is_merged=True,
    ) == [7, 7]


@pytest.mark.parametrize("rows", [
    [node(7, 0.0), node(8, 0.0)],  # two possible identities
    [node(7, 0.0), node(8, 2.0)],  # the middle coordinate has no identity
])
def test_node_resolution_does_not_return_an_ambiguous_or_shortened_chain(fake_provider, rows):
    fake_provider._mdb.get_node_data = lambda: rows
    assert fake_provider.add_nodes_returning_ids(
        [[0, 0, 0], [1, 0, 0], [2, 0, 0]], is_merged=True,
    ) == []


@pytest.mark.parametrize("tool, arguments", [
    ("create_section", {"sec_type": "矩形", "sec_info": [2, 3]}),
    ("create_polygon_section", {"loop_segments": {"main": [[0, 0], [2, 0], [0, 1]]}}),
    ("create_line_width_section", {"sec_lines": [[0, 0, 0, 2, 0.1]]}),
    ("create_section_from_properties", {"area": 6, "ix": 1, "iy": 2, "iz": 3}),
])
def test_all_section_creation_tools_request_automatic_numbering(qtmodel_wire, tool, arguments):
    provider, requests = qtmodel_wire
    functions = tool_fns(register_modeling_tools, provider)
    functions[tool](name="New section", **arguments)
    payload = next(payload for header, payload in requests if header == "ADD-SECTION")
    assert payload["index"] == -1, "Creating a section must not target existing section 1"
    if tool == "create_section_from_properties":
        from qtmodel.core.section_db import SectionProperty

        # The SDK's C# field layout is the independent source of truth.
        assert payload["sec_property"] == SectionProperty(Ax=6, Ix=1, Iy=2, Iz=3).to_list()


def test_custom_temperature_rejects_missing_reference_before_any_write(fake_provider):
    functions = tool_fns(register_modeling_tools, fake_provider)
    with pytest.raises(ToolInputError, match="three|三列"):
        functions["add_custom_temperature"](
            element_id=1, case_name="TEMP", temperature_data=[(0.25, 12.5)],
        )
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("enabled, solver", [(False, 1), (True, 0)])
def test_analysis_configuration_applies_false_and_selected_solver(qtmodel_wire, enabled, solver):
    provider, requests = qtmodel_wire
    functions = tool_fns(register_modeling_tools, provider)
    functions["configure_analysis"](do_vibration=enabled, vibration_modes=7, solver_type=solver)
    payloads = dict(requests)
    assert payloads["UPDATE-SELF-VIBRATION-SETTING"]["do_analysis"] is enabled
    assert payloads["UPDATE-SELF-VIBRATION-SETTING"]["mode_num"] == 7
    assert payloads["UPDATE-GLOBAL-SETTING"]["solver_type"] == solver


@pytest.mark.parametrize("status", [
    {"is_running": False},
    {"state": "", "is_running": False},
    {"state": "succeeded", "ok": False, "is_running": False},
    {"state": "succeeded", "ok": True, "is_running": True},
])
def test_real_sdk_waiter_return_is_not_itself_proof_of_success(fake_provider, monkeypatch, status):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    sent = []

    def reply(header="", payload=None, **kwargs):
        sent.append(header)
        return status if header == "GET-PROJECT-SOLVE-STATUS" else None

    monkeypatch.setattr(QtServer, "send_dict", reply)
    fake_provider._mdb = qtmodel.mdb
    functions = tool_fns(register_modeling_tools, fake_provider)
    with pytest.raises(ToolError, match="not confirmed"):
        asyncio.run(functions["run_analysis"](ctx=None))
    assert sent.count("DO-SOLVE") == 1
    assert "GET-PROJECT-SOLVE-STATUS" in sent


@pytest.mark.parametrize("status", [None, {}, "", "success"])
def test_missing_structured_solve_status_is_not_success(fake_provider, status):
    fake_provider._mdb.do_solve = lambda **kwargs: status
    functions = tool_fns(register_modeling_tools, fake_provider)
    with pytest.raises(ToolError, match="state=unknown"):
        asyncio.run(functions["run_analysis"](ctx=None))


@pytest.mark.parametrize("kind, count, header", [
    ("boundary", 6, "QUERY-BOUNDARIES"), ("load", 7, "QUERY-LOADS"),
])
def test_group_member_queries_filter_the_requested_group(fake_provider, monkeypatch, kind, count, header):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def send(command, payload):
        requests.append((command, payload))
        return {"items": [{"group_name": "Chosen", "id": 7}], "has_more": False}

    monkeypatch.setattr(QtServer, "send_dict", send)
    fake_provider._mdb = qtmodel.mdb
    fake_provider._odb = qtmodel.odb
    functions = tool_fns(register_group_tools, fake_provider)
    method = "query_boundary_data" if kind == "boundary" else "query_load_data"
    if not callable(fake_provider._model_query_method(method)):
        with pytest.raises(ToolError, match=f"qtmodel has no model query '{method}'"):
            functions["list_group_members"](group_type=kind, name="Chosen", limit=3, offset=2)
        assert requests == []
        return
    result = functions["list_group_members"](group_type=kind, name="Chosen", limit=3, offset=2)
    assert "Chosen" in result["message"]
    assert len(requests) == count
    for command, payload in requests:
        assert command == header
        assert payload["group_names"] == ["Chosen"]
        assert (payload["limit"], payload["offset"]) == (3, 2)


def test_structure_members_include_independent_nodes(fake_provider):
    fake_provider._mdb.get_structure_group_names = lambda: ["Chosen"]
    fake_provider._mdb.get_group_elements = lambda **kwargs: [9]
    fake_provider._mdb.get_group_nodes = lambda **kwargs: [7, 8]
    functions = tool_fns(register_group_tools, fake_provider)
    result = functions["list_group_members"](group_type="structure", name="Chosen")
    assert all(value in result["message"] for value in ("nodes", "elements", "7", "8", "9"))


@pytest.mark.parametrize("steel_type, detail", [(2, None), (2, [1, 2, 3, 4]), (1, [1] * 6)])
def test_tendon_property_rejects_wrong_steel_layout_before_writing(fake_provider, steel_type, detail):
    functions = tool_fns(register_tendon_tools, fake_provider)
    with pytest.raises(ToolInputError, match="steel_detail"):
        functions["create_tendon_property"](
            name="T", material_name="Steel", steel_type=steel_type, steel_detail=detail,
        )
    assert fake_provider._mdb.calls == []


def test_threaded_bar_sends_six_fields_through_real_sdk(qtmodel_wire):
    provider, requests = qtmodel_wire
    functions = tool_fns(register_tendon_tools, provider)
    detail = [0.032, 0.000804, 0.05, 0.25, 0.0015, 2]
    functions["create_tendon_property"](
        name="Bar", material_name="Steel", steel_type=2, steel_detail=detail,
    )
    payload = next(p for h, p in requests if h == "ADD-TENDON-PROPERTY")
    assert payload["steel_type"] == 2
    assert payload["steel_detail"] == detail
