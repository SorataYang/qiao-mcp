"""Keep numeric legacy masses when the desktop sends .NET tuple objects."""

import json

import pytest
from conftest import tool_fns
from qtmodel.core.qt_server import QtServer

from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.queries import register_query_tools


@pytest.mark.parametrize("mass_info", [
    [12.5, 1.0, 2.0, 3.0],
    {"Item3": 2.0, "Item1": 12.5, "Item4": 3.0, "Item2": 1.0},
])
def test_nodal_mass_wire_tuple_preserves_values_and_extra_fields(fake_provider, monkeypatch, mass_info):
    requests = []

    def send(command="", header="", read_timeout=600):
        requests.append((header, command))
        return json.dumps([{"node_id": 7, "mass_info": mass_info, "future_field": "kept"}])

    monkeypatch.setattr(QtServer, "send_command", send)
    result = tool_fns(register_query_tools, fake_provider)["get_model_data"](kind="node_masses")
    assert result["data"] == [{
        "node_id": 7, "mass_info": [12.5, 1.0, 2.0, 3.0], "future_field": "kept",
    }]
    assert requests == [("GET-NODE-MASS-DATA", "")]


def test_unknown_mass_tuple_fails_without_fabricating_values(fake_provider, monkeypatch):
    monkeypatch.setattr(QtServer, "send_command", lambda **kwargs: json.dumps([
        {"node_id": 7, "mass_info": {"Item1": 12.5}},
    ]))
    with pytest.raises(ToolError, match="Unrecognized nodal mass tuple"):
        tool_fns(register_query_tools, fake_provider)["get_model_data"](kind="node_masses")
