"""International vehicle field/unit contracts and native-definition readback."""

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope
from qiao_mcp.tools.international_load import register_international_load_tools

FIXTURE = json.loads((Path(__file__).parent / "fixtures/international_definitions.json").read_text())
VEHICLE_CALLS = [c for c in FIXTURE["calls"] if c["method"] in {"add_international_vehicle", "update_international_vehicle"}]
# Active fields from the upstream field documentation, independent of our models.
FIELDS = {
    "AASHTO": {"dynamic_coefficient", "r", "dist", "d2", "d3", "w"},
    "BS": {"w1", "w2", "w3", "l_invert1", "l_invert2", "l1", "l2", "pa", "d1", "pb", "d", "d2", "d3", "d4", "d5", "d6", "number_of_units"},
    "EN1991": {"uniform_load1", "uniform_load2", "loaded_length1", "loaded_length2", "spacing1", "spacing2", "load_number", "train_length", "load_gap", "point_load", "fai1", "fai2", "alpha", "support_gap", "displacement_bias", "hslm_a_kind"},
}


def vehicle_request(standard="AASHTO", action="add"):
    call = next(c for c in VEHICLE_CALLS if c["kwargs"]["standard"] == standard and c["method"].startswith(action))
    kwargs = copy.deepcopy(call["kwargs"])
    kwargs["parameters"] = {k: v for k, v in kwargs["parameters"].items() if k in FIELDS[standard]}
    if standard != "EN1991":
        del kwargs["consider_point_load"], kwargs["consider_displacement_bias"]
    return {"action": action, **kwargs}


@pytest.mark.parametrize("call", VEHICLE_CALLS, ids=lambda c: f'{c["kwargs"]["standard"]}-{c["method"]}')
@pytest.mark.parametrize("gateway", [False, True])
def test_exported_vehicle_fields_reach_real_sdk_unchanged(fake_provider, monkeypatch, call, gateway):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    method, kwargs = call["method"], copy.deepcopy(call["kwargs"])
    if not callable(getattr(qtmodel.mdb, method, None)):
        pytest.skip("Installed qtmodel lacks international vehicle definitions")
    action = method.split("_", 1)[0]
    request = vehicle_request(kwargs["standard"], action)
    expected = kwargs if gateway else {k: v for k, v in request.items() if k != "action"}
    expected.setdefault("consider_point_load", False)
    expected.setdefault("consider_displacement_bias", False)
    record = {**kwargs, "name": kwargs.get("new_name", kwargs["name"]), "future_field": {"kept": True}}
    record.pop("new_name", None)
    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        return json.dumps([record]) if header == "GET-INTERNATIONAL-VEHICLES" else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    if gateway:
        tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    else:
        result = tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=request)
        assert result == {"status": "success", "committed": True, "data": record}
    assert [h for h, _ in calls] == [f"{action.upper()}-INTERNATIONAL-VEHICLE", "UPDATE"] + ([] if gateway else ["GET-INTERNATIONAL-VEHICLES"])
    calls[0][1].pop("version", None)
    assert calls[0][1] == expected


@pytest.mark.parametrize("standard, parameters, axles", [
    ("AASHTO", {"dynamic_coefficient": 1.33, "r": 90, "dist": 15.24, "d2": 4.27, "d3": 9.14, "w": 9340}, [[35000, 4.27], [145000, 0]]),
    ("BS", {"w1": 336, "w2": 36, "w3": 8.8, "pa": 120, "pb": 10, "number_of_units": 45, "l_invert1": .67, "l_invert2": .1}, [[140, 2.5], [150, 3]]),
    ("EN1991", {"uniform_load1": 80, "uniform_load2": 90, "loaded_length1": 12.5, "spacing1": .8, "loaded_length2": 22.5, "spacing2": 1.2, "load_number": 18, "hslm_a_kind": 4}, [[250, 1.6], [250, 0]]),
])
def test_each_standard_keeps_its_native_values_without_global_scaling(fake_provider, standard, parameters, axles):
    request = {**vehicle_request(standard), "parameters": parameters, "load_items": axles}
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[{"name": request["name"], "index": 71, "standard": standard}])
    tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=request)
    sent = fake_provider._mdb.last("add_international_vehicle")[2]
    assert sent["parameters"] == parameters and sent["load_items"] == axles
    assert fake_provider._mdb.count("update_model") == 1


def test_update_uses_original_name_and_returns_actual_id_despite_compatibility_index(fake_provider):
    request = {**vehicle_request(action="update"), "index": 999, "parameters": {"r": 0, "w": None}, "load_items": []}
    readback = {"name": request["new_name"], "index": 23, "standard": "AASHTO", "parameters": {"r": 0, "w": 9300}}
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[readback])
    result = tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=request)
    sent = fake_provider._mdb.last("update_international_vehicle")[2]
    assert sent["name"] == request["name"] and sent["index"] == 999
    assert sent["parameters"] == {"r": 0} and sent["load_items"] == []
    assert result["data"]["index"] == 23


def test_auto_id_is_read_back_from_the_exact_name(fake_provider):
    request = vehicle_request()
    del request["index"]
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[
        {"name": "other", "index": 999, "standard": "AASHTO"},
        {"name": request["name"], "index": 24, "standard": "AASHTO"},
    ])
    result = tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=request)
    assert result["data"]["index"] == 24
    assert fake_provider._mdb.last("add_international_vehicle")[2]["index"] == -1
    fake_provider._mdb.get_international_vehicles.assert_called_once_with()


@pytest.mark.parametrize("standard, patch", [
    ("AASHTO", {"parameters": {"point_load": 170}}),
    ("BS", {"parameters": {"w": 9000}}),
    ("EN1991", {"parameters": {"pa": 120}}),
    ("AASHTO", {"consider_point_load": True}),
    ("BS", {"vehicle_type": 4}), ("EN1991", {"vehicle_type": 0}),
    ("AASHTO", {"vehicle_type": True}), ("BS", {"definition_mode": True}),
    ("EN1991", {"parameters": {"load_number": 1.5}}),
    ("EN1991", {"parameters": {"load_number": 2147483648}}),
    ("EN1991", {"parameters": {"hslm_a_kind": 11}}),
    ("EN1991", {"parameters": {"hslm_a_kind": True}}),
    ("EN1991", {"consider_displacement_bias": 1}),
    ("AASHTO", {"parameters": {"w": float("inf")}}),
    ("BS", {"parameters": {"pa": "120"}}), ("BS", {"parameters": {"pb": False}}),
    ("AASHTO", {"load_items": [[3, -1]]}), ("EN1991", {"load_items": [[3, 1, 4]]}),
    ("AASHTO", {"load_items": [[True, 0]]}), ("EN1991", {"load_items": [[float("nan"), 0]]}),
    ("AASHTO", {"new_name": "new"}), ("AASHTO", {"index": 0}),
])
def test_invalid_vehicle_inputs_fail_in_mcp_before_guard(fake_provider, standard, patch):
    mcp = FastMCP("international")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_international_vehicle", {"request": {**vehicle_request(standard), **patch}}))
    fake_provider.ensure_operation_allowed.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("field", ["parameters", "load_items", "definition_mode"])
def test_full_replacement_requires_explicit_definition_parts(fake_provider, field):
    request = vehicle_request()
    del request[field]
    with pytest.raises(ToolError, match=field):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=request)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("method", ["add_international_vehicle", "get_international_vehicles"])
def test_missing_write_or_readback_api_never_mutates(fake_provider, method):
    writer, getter, commit = Mock(), Mock(), Mock()
    fake_provider._mdb = SimpleNamespace(add_international_vehicle=writer, get_international_vehicles=getter, update_model=commit)
    delattr(fake_provider._mdb, method)
    with pytest.raises(ToolError, match="does not support"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=vehicle_request())
    writer.assert_not_called()
    getter.assert_not_called()
    commit.assert_not_called()


def test_partial_sdk_signature_is_rejected_before_any_command(fake_provider):
    writer = Mock()
    fake_provider._mdb.add_international_vehicle = lambda name: writer(name)
    with pytest.raises(ToolError, match="arguments"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=vehicle_request())
    writer.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("records", [None, {}, [], [{"name": "wrong", "index": 71}], [{"name": vehicle_request()["name"], "index": True}]])
def test_bad_readback_reports_the_already_committed_write(fake_provider, records):
    fake_provider._mdb.get_international_vehicles = Mock(return_value=records)
    with pytest.raises(ToolError, match="was committed, but readback failed"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=vehicle_request())
    assert fake_provider._mdb.count("add_international_vehicle") == 1
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("lost_reply", [False, True])
def test_write_failure_is_never_replayed_or_committed(fake_provider, lost_reply):
    error = type("CommandOutcomeUnknownError", (RuntimeError,), {})("reply lost") if lost_reply else ValueError("wrong active live-load system")
    writer = Mock(side_effect=error)
    fake_provider._mdb.add_international_vehicle = writer
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN" if lost_reply else "active live-load system"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=vehicle_request())
    writer.assert_called_once()
    assert fake_provider._mdb.calls == []


def test_commit_failure_admits_possible_model_change(fake_provider):
    commit = Mock(side_effect=RuntimeError("commit unavailable"))
    fake_provider._mdb.update_model = commit
    with pytest.raises(ToolError, match="model may have changed"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_vehicle"](request=vehicle_request())
    assert fake_provider._mdb.count("add_international_vehicle") == 1
    commit.assert_called_once()


@pytest.mark.parametrize("kind, method", [("vehicles", "get_international_vehicles"), ("cases", "get_international_live_load_cases")])
def test_native_whole_list_query_filters_and_pages_locally(fake_provider, kind, method):
    records = [{"index": i, "name": "对象", "future": {"native": True}} for i in (4, 9, 20)]
    getter = Mock(return_value=records)
    setattr(fake_provider._mdb, method, getter)
    fn = tool_fns(register_international_load_tools, fake_provider)["get_international_live_load_data"]
    assert fn(kind=kind, name="对象", limit=1, offset=1) == {
        "status": "success", "data": [records[1]], "total": 3, "limit": 1, "offset": 1, "has_more": True,
    }
    assert fn(kind=kind, name="对象", index=20)["data"] == [records[-1]]
    assert fn(kind=kind, name="wrong", index=20)["data"] == []
    assert getter.call_args_list == [()] * 3
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("value", [None, {}, "unavailable", [1]])
def test_invalid_query_response_is_not_an_empty_success(fake_provider, value):
    fake_provider._mdb.get_international_vehicles = Mock(return_value=value)
    with pytest.raises(ToolError, match="valid definition list"):
        tool_fns(register_international_load_tools, fake_provider)["get_international_live_load_data"](kind="vehicles")


@pytest.mark.parametrize("write", [False, True])
@pytest.mark.parametrize("state_kind", ["unknown", "no_model", "solving", "postprocessing", "denied"])
def test_state_guards_prevent_international_model_access(fake_provider, write, state_kind):
    state = ready_model_state()
    model = state["model_state"]
    if state_kind == "unknown":
        state = {"status": "state_unknown"}
    elif state_kind == "no_model":
        model["model_opened"] = False
    elif state_kind == "solving":
        model["is_solving"] = True
    elif state_kind == "postprocessing":
        model.update(phase="postprocessing", is_base_stage=False)
        if not write:
            model["capabilities"]["read_model"] = False
    else:
        model["capabilities"]["modify_model" if write else "read_model"] = False
    if state_kind != "unknown":
        # The bridge's capability flags, not independently guessed phase rules,
        # are authoritative. Model a snapshot that denies this operation.
        model["capabilities"]["modify_model" if write else "read_model"] = False
    fake_provider.get_model_state = lambda: state
    fns = tool_fns(register_international_load_tools, fake_provider)
    with pytest.raises(ToolError):
        if write:
            fns["set_international_vehicle"](request=vehicle_request())
        else:
            fns["get_international_live_load_data"](kind="vehicles")
    assert fake_provider._mdb.calls == []


def test_read_in_postprocessing_uses_the_authoritative_read_capability(fake_provider):
    state = ready_model_state()
    state["model_state"].update(phase="postprocessing", is_base_stage=False)
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: state
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[])
    assert tool_fns(register_international_load_tools, fake_provider)["get_international_live_load_data"](kind="vehicles")["data"] == []
    fake_provider._mdb.get_international_vehicles.assert_called_once_with()


def test_vehicle_schema_discriminates_standards_and_marks_overwrites(fake_provider):
    mcp = FastMCP("international")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    write = tools["set_international_vehicle"]
    assert write.annotations.destructiveHint and not write.annotations.readOnlyHint
    assert tools["get_international_live_load_data"].annotations.readOnlyHint
    schema = write.inputSchema
    assert schema["properties"]["request"]["discriminator"]["propertyName"] == "standard"
    assert set(schema["$defs"]["AashtoParameters"]["properties"]) == FIELDS["AASHTO"]
    assert set(schema["$defs"]["BsParameters"]["properties"]) == FIELDS["BS"]
    assert set(schema["$defs"]["En1991Parameters"]["properties"]) == FIELDS["EN1991"]
    for model in ("AashtoVehicleWrite", "BsVehicleWrite", "En1991VehicleWrite"):
        assert {"parameters", "load_items", "vehicle_type", "definition_mode"} <= set(schema["$defs"][model]["required"])
        row = schema["$defs"][model]["properties"]["load_items"]["items"]
        assert row["minItems"] == row["maxItems"] == 2
    assert all(tool.outputSchema for tool in tools.values())
