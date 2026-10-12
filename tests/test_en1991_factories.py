"""Real EN1991 factory transport, effective controls and validation boundaries."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope
from qiao_mcp.tools.international_load import register_international_load_tools

UNIFORM_FIELDS = {"uniform_load1", "uniform_load2", "loaded_length1", "loaded_length2", "spacing1", "spacing2"}


@pytest.mark.parametrize("source", ["standard", "user"])
@pytest.mark.parametrize("load_type", ["LoadModel71", "LM71", "SW0", "SW2", "UnloadedTrain", "HSLMA", "HSLMB"])
def test_real_factories_keep_effective_fields_and_read_back_actual_id(fake_provider, monkeypatch, source, load_type):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, f"add_international_{source}_vehicle", None)):
        pytest.skip("Installed qtmodel lacks EN1991 factories")
    request = {
        "source": source, "load_type": load_type, "name": '欧规"车辆\\一', "load_gap": 3.75,
        "fai1": 0, "fai2": .2, "alpha": 1.1, "consider_point_load": True, "support_gap": .85,
        "consider_displacement_bias": True, "displacement_bias": -.25,
    }
    if source == "standard":
        request.update(load_number=11, hslm_a_kind=4)
    else:
        request.update(uniform_load1=80.5, uniform_load2=90.5, loaded_length1=12.5, loaded_length2=23.5,
                       spacing1=.8, spacing2=.9, p=[250, 260], dis=[1.6, 0], load_length=19.5, num=16, point_load=180)
    record = {"index": 96, "name": request["name"], "standard": "EN1991", "parameters": {"factory_extension": 7}}
    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        return json.dumps([record]) if header == "GET-INTERNATIONAL-VEHICLES" else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    result = tool_fns(register_international_load_tools, fake_provider)["create_en1991_vehicle"](request=request)
    assert result == {"status": "success", "committed": True, "data": record}
    assert [h for h, _ in calls] == [f"ADD-INTERNATIONAL-{source.upper()}-VEHICLE", "UPDATE", "GET-INTERNATIONAL-VEHICLES"]
    for key, value in request.items():
        if key != "source":
            assert calls[0][1][key] == value
    if source == "standard":
        # The SDK still sends compatibility defaults; callers cannot override
        # these six ineffective fields through the standard factory schema.
        assert calls[0][1]["loaded_length1"] == 1.7976931348623157e308
        assert calls[0][1]["uniform_load1"] == 80


def test_user_lm71_leaves_null_axles_for_the_native_four_axle_default(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, "add_international_user_vehicle", None)):
        pytest.skip("Installed qtmodel lacks EN1991 factories")
    payloads = []

    def send(command="", header="", read_timeout=600):
        if header == "ADD-INTERNATIONAL-USER-VEHICLE":
            payloads.append(json.loads(command))
        return json.dumps([{"name": "默认LM71", "index": 34, "standard": "EN1991"}]) if header.startswith("GET-") else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    tool_fns(register_international_load_tools, fake_provider)["create_en1991_vehicle"](
        request={"source": "user", "name": "默认LM71", "p": None, "dis": None},
    )
    assert payloads[0]["p"] is None and payloads[0]["dis"] is None
    assert payloads[0]["load_type"] == "LoadModel71"
    assert payloads[0]["consider_point_load"] is False
    assert payloads[0]["consider_displacement_bias"] is False
    assert payloads[0]["fai1"] == 0


@pytest.mark.parametrize("source, patch", [
    ("standard", {field: 1} ) for field in sorted(UNIFORM_FIELDS)
] + [
    ("standard", {"p": [250], "dis": [0]}), ("user", {"load_number": 10}),
    ("standard", {"name": None}), ("user", {"name": " "}),
    ("standard", {"load_type": "unknown"}), ("user", {"alpha": 0}),
    ("user", {"fai1": -1}), ("standard", {"fai2": float("nan")}),
    ("standard", {"hslm_a_kind": 0}), ("standard", {"hslm_a_kind": 11}),
    ("standard", {"load_number": True}), ("user", {"num": 1.5}),
    ("user", {"p": [250]}), ("user", {"dis": [0]}),
    ("user", {"p": [250, 250], "dis": [0]}), ("user", {"p": [], "dis": []}),
    ("user", {"p": [0], "dis": [0]}), ("user", {"p": [250], "dis": [-1]}),
    ("user", {"uniform_load1": -1}), ("user", {"loaded_length1": float("inf")}),
    ("user", {"spacing2": -1}), ("user", {"load_length": 0}),
    ("standard", {"consider_point_load": 1}), ("user", {"consider_point_load": True, "support_gap": 0}),
    ("standard", {"load_type": "HSLMB", "load_gap": 0}),
    ("user", {"load_type": "HSLMA", "point_load": 0}),
])
def test_factory_invalid_or_ineffective_options_fail_before_guard(fake_provider, source, patch):
    mcp = FastMCP("factory")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("create_en1991_vehicle", {"request": {"source": source, "name": "v", **patch}}))
    fake_provider.ensure_operation_allowed.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("source", ["standard", "user"])
@pytest.mark.parametrize("failure", ["missing_factory", "partial_factory", "missing_getter", "lost_reply", "readback_failed"])
def test_factory_failures_do_not_replay_writes(fake_provider, source, failure):
    writer, commit = Mock(), Mock()
    method = f"add_international_{source}_vehicle"
    db = SimpleNamespace(update_model=commit, get_international_vehicles=Mock(return_value=[]))
    setattr(db, method, writer)
    if failure == "missing_factory":
        delattr(db, method)
    elif failure == "partial_factory":
        setattr(db, method, lambda name: writer(name))
    elif failure == "missing_getter":
        delattr(db, "get_international_vehicles")
    elif failure == "lost_reply":
        writer.side_effect = type("CommandOutcomeUnknownError", (RuntimeError,), {})("reply lost")
    fake_provider._mdb = db
    with pytest.raises(ToolError, match="committed" if failure == "readback_failed" else "OUTCOME UNKNOWN" if failure == "lost_reply" else "does not support"):
        tool_fns(register_international_load_tools, fake_provider)["create_en1991_vehicle"](request={"source": source, "name": "v"})
    assert writer.call_count == int(failure in {"lost_reply", "readback_failed"})
    assert commit.call_count == int(failure == "readback_failed")


def test_factory_schema_separates_effective_standard_and_user_controls(fake_provider):
    mcp = FastMCP("factory")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "create_en1991_vehicle")
    schema = tool.inputSchema
    assert schema["properties"]["request"]["discriminator"]["propertyName"] == "source"
    standard = schema["$defs"]["En1991StandardFactory"]
    user = schema["$defs"]["En1991UserFactory"]
    assert not UNIFORM_FIELDS & standard["properties"].keys()
    assert UNIFORM_FIELDS <= user["properties"].keys()
    assert {"p", "dis", "load_length", "num", "point_load"} <= user["properties"].keys()
    assert standard["additionalProperties"] is user["additionalProperties"] is False
    assert "name" in standard["required"] and "name" in user["required"]
    assert tool.annotations.destructiveHint and not tool.annotations.readOnlyHint
    assert tool.outputSchema
