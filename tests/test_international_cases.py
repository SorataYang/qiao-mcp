"""International cases/planned lanes: exports, references and commit semantics."""

import asyncio
import copy
import inspect
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

CALLS = json.loads((Path(__file__).parent / "fixtures/international_definitions.json").read_text())["calls"]
CASE_CALLS = [c for c in CALLS if c["method"] in {"add_international_live_load_case", "update_international_live_load_case"}]
LANE_CALLS = [c for c in CALLS if c["method"].endswith("planned_lane_line")]


def case_request(standard="AASHTO", action="add"):
    call = next(c for c in CASE_CALLS if c["kwargs"]["sub_cases"][0]["vehicle_name"].startswith(standard) and c["method"].startswith(action))
    return {"action": action, "standard": standard, **copy.deepcopy(call["kwargs"])}


def lane_request(action="add"):
    call = next(c for c in LANE_CALLS if c["method"].startswith(action))
    return {"action": action, **copy.deepcopy(call["kwargs"])}


@pytest.mark.parametrize("standard", ["AASHTO", "BS", "EN1991"])
@pytest.mark.parametrize("action", ["add", "update"])
@pytest.mark.parametrize("gateway", [False, True])
def test_csharp_case_export_preserves_all_factor_fields(fake_provider, monkeypatch, standard, action, gateway):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    method = f"{action}_international_live_load_case"
    if not callable(getattr(qtmodel.mdb, method, None)):
        pytest.skip("Installed qtmodel lacks international live-load cases")
    request = case_request(standard, action)
    expected = {k: v for k, v in request.items() if k not in {"action", "standard"}}
    record = {**expected, "name": expected.get("new_name", expected["name"]), "future_case": False}
    record.pop("new_name", None)
    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        if header == "GET-INTERNATIONAL-VEHICLES":
            return json.dumps([{"name": request["sub_cases"][0]["vehicle_name"], "standard": standard, "index": 71}])
        return json.dumps([record]) if header == "GET-INTERNATIONAL-LIVE-LOAD-CASES" else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    if gateway:
        tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=expected)
    else:
        result = tool_fns(register_international_load_tools, fake_provider)["set_international_live_load_case"](request=request)
        assert result == {"status": "success", "committed": True, "data": record}
    headers = [f"{action.upper()}-INTERNATIONAL-LIVE-LOAD-CASE", "UPDATE"]
    if not gateway:
        headers = ["GET-INTERNATIONAL-VEHICLES", *headers, "GET-INTERNATIONAL-LIVE-LOAD-CASES"]
    assert [h for h, _ in calls] == headers
    payload = calls[0 if gateway else 1][1]
    payload.pop("version", None)
    assert payload == expected


@pytest.mark.parametrize("family", ["highway_factor", "railway_factor", "light_rail_factor"])
def test_complete_factor_objects_retain_zero_false_and_inactive_values(fake_provider, family):
    request = case_request("EN1991")
    factor = request.pop("highway_factor")
    factor["ImpactCoefficient"]["Span"] = 0
    factor["FatigueImpactCoefficient"]["ImpactValue"] = 1.7
    factor["IsCalculatedFatigue"] = False
    request.update(span=0, save_sub_case_result=False, **{family: factor})
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[{"name": request["sub_cases"][0]["vehicle_name"], "standard": "EN1991"}])
    fake_provider._mdb.get_international_live_load_cases = Mock(return_value=[{"name": request["name"], "index": 8}])
    tool_fns(register_international_load_tools, fake_provider)["set_international_live_load_case"](request=request)
    sent = fake_provider._mdb.last("add_international_live_load_case")[2]
    assert sent[family] == factor and sent["span"] == 0 and sent["save_sub_case_result"] is False
    assert "standard" not in sent
    assert fake_provider._mdb.count("update_model") == 1


def test_null_factor_uses_server_defaults_and_update_retains_actual_index(fake_provider):
    request = {**case_request(action="update"), "index": 700, "highway_factor": None}
    fake_provider._mdb.get_international_vehicles = Mock(return_value=[{"name": request["sub_cases"][0]["vehicle_name"], "standard": "AASHTO"}])
    fake_provider._mdb.get_international_live_load_cases = Mock(return_value=[{"name": request["new_name"], "index": 13}])
    result = tool_fns(register_international_load_tools, fake_provider)["set_international_live_load_case"](request=request)
    sent = fake_provider._mdb.last("update_international_live_load_case")[2]
    assert sent["index"] == 700 and result["data"]["index"] == 13
    assert not {"highway_factor", "railway_factor", "light_rail_factor"} & sent.keys()


@pytest.mark.parametrize("records", [[], [{"name": "wrong", "standard": "EN1991"}],
    [{"name": case_request("EN1991")["sub_cases"][0]["vehicle_name"], "standard": "BS"}],
    [{"name": case_request("EN1991")["sub_cases"][0]["vehicle_name"], "standard": "EN1991"}] * 2,
])
def test_missing_ambiguous_or_wrong_standard_vehicle_is_rejected_before_write(fake_provider, records):
    fake_provider._mdb.get_international_vehicles = Mock(return_value=records)
    with pytest.raises(ToolError, match="No unique EN1991 vehicle"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_live_load_case"](request=case_request("EN1991"))
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("duplicated", ["within_subcase", "across_subcases", "across_lane_kinds", "hb_reference"])
def test_en1991_duplicate_lanes_fail_before_guard(fake_provider, duplicated):
    request = case_request("EN1991")
    first = request["sub_cases"][0]
    if duplicated == "within_subcase":
        first["lane_names"] *= 2
    elif duplicated == "hb_reference":
        first["hb_lane_names"] = first["lane_names"][:]
    else:
        second = copy.deepcopy(first)
        second["optimized"] = duplicated == "across_lane_kinds"
        request["sub_cases"].append(second)
    mcp = FastMCP("case")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError, match="assigned twice"):
        asyncio.run(mcp.call_tool("set_international_live_load_case", {"request": request}))
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("patch", [
    {"sub_cases": []}, {"span": -1}, {"save_sub_case_result": 1},
    {"sub_cases": [{"vehicle_name": "v", "lane_names": []}]},
    {"sub_cases": [{"vehicle_name": "v", "lane_names": ["L"], "factor": 0}]},
    {"sub_cases": [{"vehicle_name": "v", "lane_names": ["L"], "optimized": 1}]},
    {"sub_cases": [{"vehicle_name": "v", "lane_names": ["L"], "lane_count": True}]},
    {"sub_cases": [{"vehicle_name": "v", "lane_names": ["L"], "future": 1}]},
    {"standard": "china"}, {"highway_factor": {}},
])
def test_invalid_case_shapes_do_not_reach_guard(fake_provider, patch):
    mcp = FastMCP("case")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_international_live_load_case", {"request": {**case_request(), **patch}}))
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("path, value", [
    (("unknown",), 1), (("ReduceCode",), None),
    (("ImpactCoefficient", "IsDefinedByUser"), 1),
    (("ImpactCoefficient", "unknown"), 1), (("ImpactCoefficient", "ImpactValue"), float("nan")),
    (("LongitudeReduceCoefficient", "Value"), None),
    (("FatigueImpactCoefficient", "BaseFrequency"), float("inf")),
    (("CrossReduceCoefficient", "CrossReduceSet", "1"), False),
    (("CrossReduceCoefficient", "CrossReduceSet", "not_a_count"), 1),
])
def test_nested_factors_reject_unknown_null_and_nonfinite_fields_before_guard(fake_provider, path, value):
    request = case_request()
    target = request["highway_factor"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    mcp = FastMCP("factor")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_international_live_load_case", {"request": request}))
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("action", ["add", "update"])
def test_planned_lane_export_uses_dedicated_endpoint_and_one_commit(qtmodel_wire, action):
    p, calls = qtmodel_wire
    if not callable(getattr(p._mdb, f"{action}_planned_lane_line", None)):
        pytest.skip("Installed qtmodel lacks planned-lane operations")
    request = lane_request(action)
    result = tool_fns(register_international_load_tools, p)["set_planned_lane"](request=request)
    assert result["committed"] is True and "data" not in result
    assert "export/UI" in result["message"]
    assert [h for h, _ in calls] == [f"{action.upper()}-PLANNED-LANE-LINE", "UPDATE"]
    calls[0][1].pop("version", None)
    assert calls[0][1] == {k: v for k, v in request.items() if k != "action"}


def test_planned_lane_update_keeps_name_and_zero_values(qtmodel_wire):
    p, calls = qtmodel_wire
    if not callable(getattr(p._mdb, "update_planned_lane_line", None)):
        pytest.skip("Installed qtmodel lacks planned-lane operations")
    request = {**lane_request("update"), "vehicle_number": 0, "offset": 0, "direction": 0}
    del request["new_name"]
    tool_fns(register_international_load_tools, p)["set_planned_lane"](request=request)
    assert calls[0][1]["new_name"] == ""
    assert calls[0][1]["vehicle_number"] == calls[0][1]["offset"] == calls[0][1]["direction"] == 0


@pytest.mark.parametrize("patch", [
    {"lane_width": 0}, {"vehicle_number": -1}, {"vehicle_number": True},
    {"offset": float("inf")}, {"direction": 2}, {"direction": True},
    {"name": " "}, {"influence_name": ""}, {"tandem_name": ""},
    {"new_name": "invalid_on_add"}, {"index": 1},
])
def test_invalid_planned_lane_is_rejected_before_guard(fake_provider, patch):
    mcp = FastMCP("planned")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_planned_lane", {"request": {**lane_request(), **patch}}))
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("tool, method, spec", [
    ("set_planned_lane", "add_planned_lane_line", lane_request()),
    ("set_international_live_load_case", "add_international_live_load_case", case_request()),
])
@pytest.mark.parametrize("message", ["influence plane does not exist", "lane belongs to another plane", "tandem does not exist"])
def test_authoritative_reference_rejection_is_propagated_without_commit(fake_provider, tool, method, spec, message):
    writer = Mock(side_effect=ValueError(message))
    setattr(fake_provider._mdb, method, writer)
    if tool == "set_international_live_load_case":
        fake_provider._mdb.get_international_vehicles = Mock(return_value=[{"name": spec["sub_cases"][0]["vehicle_name"], "standard": "AASHTO"}])
    with pytest.raises(ToolError, match=message):
        tool_fns(register_international_load_tools, fake_provider)[tool](request=spec)
    writer.assert_called_once()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("missing", ["add_international_live_load_case", "get_international_live_load_cases", "get_international_vehicles"])
def test_missing_case_capabilities_are_rejected_before_mutation(fake_provider, missing):
    writer, vehicles, cases, commit = Mock(), Mock(), Mock(), Mock()
    db = SimpleNamespace(add_international_live_load_case=writer, get_international_vehicles=vehicles,
                         get_international_live_load_cases=cases, update_model=commit)
    delattr(db, missing)
    fake_provider._mdb = db
    with pytest.raises(ToolError, match="does not support"):
        tool_fns(register_international_load_tools, fake_provider)["set_international_live_load_case"](request=case_request())
    writer.assert_not_called()
    commit.assert_not_called()


@pytest.mark.parametrize("tool, method, spec", [
    ("set_planned_lane", "add_planned_lane_line", lane_request()),
    ("set_international_live_load_case", "add_international_live_load_case", case_request()),
])
def test_incompatible_writer_signature_fails_before_queries_and_writes(fake_provider, tool, method, spec):
    writer = Mock()
    setattr(fake_provider._mdb, method, lambda name: writer(name))
    with pytest.raises(ToolError, match="arguments"):
        tool_fns(register_international_load_tools, fake_provider)[tool](request=spec)
    writer.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("tool, method, spec", [
    ("set_planned_lane", "add_planned_lane_line", lane_request()),
    ("set_international_live_load_case", "add_international_live_load_case", case_request()),
])
@pytest.mark.parametrize("commit_failure", [False, True])
def test_lost_outcomes_are_not_replayed(fake_provider, tool, method, spec, commit_failure):
    error = type("CommandOutcomeUnknownError", (RuntimeError,), {})("reply lost")
    writer = Mock(side_effect=None if commit_failure else error)
    commit = Mock(side_effect=error if commit_failure else None)
    setattr(fake_provider._mdb, method, writer)
    fake_provider._mdb.update_model = commit
    if tool == "set_international_live_load_case":
        fake_provider._mdb.get_international_vehicles = Mock(return_value=[{"name": spec["sub_cases"][0]["vehicle_name"], "standard": "AASHTO"}])
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN"):
        tool_fns(register_international_load_tools, fake_provider)[tool](request=spec)
    writer.assert_called_once()
    assert commit.call_count == int(commit_failure)


@pytest.mark.parametrize("tool, spec", [
    ("set_planned_lane", lane_request()),
    ("set_international_live_load_case", case_request()),
    ("create_en1991_vehicle", {"source": "user", "name": "v"}),
])
@pytest.mark.parametrize("unknown", [False, True])
def test_all_new_writes_require_model_permission(fake_provider, tool, spec, unknown):
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: {"status": "state_unknown"} if unknown else state
    with pytest.raises(ToolError):
        tool_fns(register_international_load_tools, fake_provider)[tool](request=spec)
    assert fake_provider._mdb.calls == []


def test_planned_deletion_uses_explicit_lane_namespace(qtmodel_wire):
    p, calls = qtmodel_wire
    if "lane_kind" not in inspect.signature(p._mdb.remove_lane_line).parameters:
        pytest.skip("Installed qtmodel lacks explicit lane namespaces")
    tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](
        api_object="mdb", method="remove_lane_line", kwargs={"name": "同名车道", "lane_kind": "planned"},
    )
    assert [h for h, _ in calls] == ["REMOVE-LANE-LINE", "UPDATE"]
    assert calls[0][1]["lane_kind"] == "planned" and calls[0][1]["name"] == "同名车道"


def test_case_and_lane_schemas_keep_native_objects_and_destructive_annotations(fake_provider):
    mcp = FastMCP("international")
    register_tools_with_envelope(mcp, register_international_load_tools, fake_provider)
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert len(tools) == 5
    for name in ("set_planned_lane", "set_international_live_load_case", "create_en1991_vehicle"):
        assert tools[name].annotations.destructiveHint and not tools[name].annotations.readOnlyHint
        assert tools[name].outputSchema
    definitions = tools["set_international_live_load_case"].inputSchema["$defs"]
    factor = definitions["InternationalRelativeFactors"]
    assert factor["additionalProperties"] is False
    assert set(factor["required"]) == set(case_request()["highway_factor"])
    assert definitions["InternationalSubCase"]["properties"]["lane_names"]["minItems"] == 1
    planned = tools["set_planned_lane"].inputSchema["$defs"]["PlannedLaneWrite"]
    assert {"vehicle_number", "offset", "direction", "lane_width"} <= set(planned["required"])
    assert planned["properties"]["direction"]["enum"] == [0, 1]
