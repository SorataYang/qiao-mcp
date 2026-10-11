"""Transversal definitions: transport from C# exports, exact IDs and read guards."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope
from qiao_mcp.tools.transversal import register_transversal_tools

FIXTURE = json.loads((Path(__file__).parent / "fixtures/transversal_definitions.json").read_text())
DEFINITIONS = FIXTURE["definitions"]


def request_for(kind, action="add"):
    definition = dict(DEFINITIONS[kind])
    if kind == "lane":
        definition["distribution_widths"] = definition.pop("load_factors")
    return {"action": action, **definition}


@pytest.mark.parametrize("kind", ["vehicle", "lane"])
@pytest.mark.parametrize("action", ["add", "update"])
def test_real_export_fields_and_one_commit(fake_provider, monkeypatch, kind, action):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, f"{action}_transversal_{kind}", None)):
        pytest.skip("Installed qtmodel lacks transversal definitions")
    request = request_for(kind, action)
    expected = dict(DEFINITIONS[kind])
    if action == "update":
        request["new_name"] = "改名后的对象"
        expected["new_name"] = request["new_name"]
    readback = {**DEFINITIONS[kind], "name": request.get("new_name", request["name"]), "extension": {"kept": True}}
    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        return json.dumps([readback]) if header.startswith("GET-") else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    result = tool_fns(register_transversal_tools, fake_provider)[f"set_transversal_{kind}"](request=request)
    assert result == {"status": "success", "committed": True, "data": readback}
    assert [h for h, _ in calls] == [f"{action.upper()}-TRANSVERSAL-{kind.upper()}", "UPDATE", f"GET-TRANSVERSAL-{kind.upper()}S"]
    calls[0][1].pop("version", None)
    assert calls[0][1] == expected
    assert calls[2][1]["name"] == readback["name"]
    assert calls[2][1]["index"] == readback["index"]


@pytest.mark.parametrize("kind", ["vehicle", "lane"])
def test_auto_id_is_read_not_guessed(fake_provider, kind):
    request = request_for(kind)
    del request["index"]
    readback = {**DEFINITIONS[kind], "index": 93}
    getter = Mock(return_value=[readback])
    setattr(fake_provider._mdb, f"get_transversal_{kind}s", getter)
    result = tool_fns(register_transversal_tools, fake_provider)[f"set_transversal_{kind}"](request=request)
    assert result["data"]["index"] == 93
    assert fake_provider._mdb.last(f"add_transversal_{kind}")[2]["index"] == -1
    getter.assert_called_once_with(name=request["name"], index=-1)
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("kind, patch", [
    ("vehicle", {"wheel_load": True}), ("vehicle", {"wheel_load": 0}),
    ("vehicle", {"wheel_distance": float("inf")}), ("vehicle", {"left_lane_count": 0, "has_medial_divider": False}),
    ("vehicle", {"has_medial_divider": 1}), ("vehicle", {"index": 0}),
    ("vehicle", {"new_name": "新增不能改名"}), ("vehicle", {"unknown": 1}),
    ("lane", {"node_ids": [1]}), ("lane", {"node_ids": [1, 1, 2]}),
    ("lane", {"node_ids": [True, 2, 3]}), ("lane", {"distribution_widths": [1]}),
    ("lane", {"distribution_widths": [0, 0, 0]}), ("lane", {"distribution_widths": [1, -1, 1]}),
    ("lane", {"distribution_widths": [1, False, 1]}),
])
def test_invalid_definition_fails_before_guard(fake_provider, kind, patch):
    mcp = FastMCP("transversal")
    register_tools_with_envelope(mcp, register_transversal_tools, fake_provider)
    guard = Mock()
    fake_provider.ensure_operation_allowed = guard
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool(f"set_transversal_{kind}", {"request": {**request_for(kind), **patch}}))
    guard.assert_not_called()
    assert fake_provider._mdb.calls == []


def test_full_vehicle_requires_every_physical_field(fake_provider):
    request = request_for("vehicle", "update")
    del request["wheel_margin"]
    with pytest.raises(ToolError, match="wheel_margin"):
        tool_fns(register_transversal_tools, fake_provider)["set_transversal_vehicle"](request=request)
    assert fake_provider._mdb.calls == []


def test_missing_readback_capability_blocks_before_write(fake_provider):
    writer, commit = Mock(), Mock()
    fake_provider._mdb = SimpleNamespace(add_transversal_vehicle=writer, update_model=commit)
    with pytest.raises(ToolError, match="does not support"):
        tool_fns(register_transversal_tools, fake_provider)["set_transversal_vehicle"](request=request_for("vehicle"))
    writer.assert_not_called()
    commit.assert_not_called()


@pytest.mark.parametrize("records", [[], [{"name": "wrong", "index": 9}], [{"name": DEFINITIONS["vehicle"]["name"], "index": True}]])
def test_unconfirmed_readback_reports_committed_write(fake_provider, records):
    fake_provider._mdb.get_transversal_vehicles = Mock(return_value=records)
    with pytest.raises(ToolError, match="was committed, but readback failed"):
        tool_fns(register_transversal_tools, fake_provider)["set_transversal_vehicle"](request=request_for("vehicle"))
    assert fake_provider._mdb.count("add_transversal_vehicle") == 1
    assert fake_provider._mdb.count("update_model") == 1


def test_authoritative_connectivity_rejection_is_not_hidden(fake_provider):
    writer = Mock(side_effect=ValueError("Adjacent nodes lack a direct beam connection"))
    fake_provider._mdb.add_transversal_lane = writer
    with pytest.raises(ToolError, match="direct beam"):
        tool_fns(register_transversal_tools, fake_provider)["set_transversal_lane"](request=request_for("lane"))
    writer.assert_called_once()
    assert fake_provider._mdb.calls == []


def test_read_uses_exact_selectors_and_local_pages(fake_provider):
    records = [DEFINITIONS["vehicle"], {"index": 99, "name": "v", "future": 7}]
    fake_provider._mdb.get_transversal_vehicles = Mock(return_value=records)
    result = tool_fns(register_transversal_tools, fake_provider)["get_transversal_data"](kind="vehicles", limit=1, offset=1)
    assert result == {"status": "success", "data": [records[1]], "total": 2, "limit": 1, "offset": 1, "has_more": False}
    fake_provider._mdb.get_transversal_vehicles.assert_called_once_with(name="", index=-1)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("operation, capability", [("read", "read_model"), ("write", "modify_model")])
@pytest.mark.parametrize("unknown", [False, True])
def test_permissions_prevent_native_calls(fake_provider, operation, capability, unknown):
    state = ready_model_state()
    state["model_state"]["capabilities"][capability] = False
    fake_provider.get_model_state = lambda: {"status": "state_unknown"} if unknown else state
    fns = tool_fns(register_transversal_tools, fake_provider)
    with pytest.raises(ToolError):
        if operation == "read":
            fns["get_transversal_data"](kind="vehicles")
        else:
            fns["set_transversal_vehicle"](request=request_for("vehicle"))
    assert fake_provider._mdb.calls == []


def test_lost_write_reply_is_not_repeated(fake_provider):
    error = type("CommandOutcomeUnknownError", (RuntimeError,), {})("reply lost")
    writer = Mock(side_effect=error)
    fake_provider._mdb.add_transversal_vehicle = writer
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN"):
        tool_fns(register_transversal_tools, fake_provider)["set_transversal_vehicle"](request=request_for("vehicle"))
    writer.assert_called_once()
    assert fake_provider._mdb.calls == []
