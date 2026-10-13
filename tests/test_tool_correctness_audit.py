"""Regression cases found by tracing tools to real qtmodel request constructors."""

from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.group_management import register_group_tools
from qiao_mcp.tools.moving_load import register_moving_load_tools


@pytest.mark.parametrize("tool, arguments, header", [
    ("add_node_tandem", {"name": "T", "node_ids": [1, 2]}, "ADD-NODE-TANDEM"),
    ("add_influence_plane", {"name": "P", "tandem_names": ["T"]}, "ADD-INFLUENCE-PLANE"),
])
def test_moving_load_geometry_is_committed_once(qtmodel_wire, tool, arguments, header):
    provider, requests = qtmodel_wire
    tool_fns(register_moving_load_tools, provider)[tool](**arguments)
    assert [command for command, _ in requests] == [header, "UPDATE"]


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


