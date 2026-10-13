"""Regression cases found by tracing tools to real qtmodel request constructors."""


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


