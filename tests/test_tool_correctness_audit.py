"""Regression cases found by tracing tools to real qtmodel request constructors."""

from unittest.mock import Mock

import pytest
from conftest import tool_fns

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


