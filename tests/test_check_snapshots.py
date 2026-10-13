"""Base-model snapshot transport and input validation using exported C# fixtures."""

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
from qiao_mcp.tools.check_snapshots import register_check_snapshot_tools
from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope

CALLS = json.loads((Path(__file__).parent / "fixtures/check_snapshots.json").read_text())["calls"]
SNAPSHOT_CALLS = [item for item in CALLS if item["method"] in {
    "set_section_reinforcement", "remove_section_reinforcement_by_name", "set_check_stirrup", "set_element_stirrups",
    "set_check_material", "remove_check_material", "set_check_case", "remove_check_case_snapshot",
}]
SECTION = next(item["kwargs"]["definition"] for item in CALLS if item["method"] == "set_section_reinforcement")


@pytest.fixture
def check_wire(qtmodel_wire):
    import qtmodel

    p, calls = qtmodel_wire
    p._cdb = qtmodel.cdb
    return p, calls


@pytest.mark.parametrize("call", SNAPSHOT_CALLS)
@pytest.mark.parametrize("gateway", [False, True])
def test_exported_snapshot_wire(check_wire, call, gateway):
    p, wire = check_wire
    method = call["method"]
    if not callable(getattr(p._cdb, method, None)):
        pytest.skip("Installed qtmodel lacks model snapshots")
    kwargs = copy.deepcopy(call["kwargs"])
    if gateway:
        result = tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](api_object="cdb", method=method, kwargs=kwargs)
    else:
        tool = {"remove_section_reinforcement_by_name": "remove_section_reinforcement",
                "set_check_stirrup": "set_check_stirrup_snapshot",
                "set_check_material": "manage_check_material", "remove_check_material": "manage_check_material",
                "set_check_case": "manage_check_case_definition", "remove_check_case_snapshot": "manage_check_case_definition"}.get(method, method)
        arguments = {"request": kwargs} if method == "set_element_stirrups" else kwargs
        if method in {"set_check_material", "set_check_case"}:
            arguments = {"request": {"action": "set", **kwargs}}
        elif method in {"remove_check_material", "remove_check_case_snapshot"}:
            arguments = {"request": {"action": "reset" if method == "remove_check_material" else "remove", **kwargs}}
        result = tool_fns(register_check_snapshot_tools, p)[tool](**arguments)
        assert result["committed"] is True
    assert result["status"] == "success"
    assert [h for h, _ in wire] == [method.replace("_", "-").upper(), "UPDATE"]
    wire[0][1].pop("version", None)
    assert wire[0][1] == call["kwargs"]


def test_inactive_parameters_and_bar_points_are_preserved(fake_provider):
    result = tool_fns(register_check_snapshot_tools, fake_provider)["set_section_reinforcement"](definition=SECTION)
    native = fake_provider._cdb.last("set_section_reinforcement")[2]["definition"]
    assert native == SECTION
    assert native["has_outer"] is False and native["outer"]
    assert native["points"] and len(native["outer"][0]) == 6
    assert result["committed"] is True
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("patch", [
    {"outer": [[.03, 1, .1, 5, .04]]}, {"parts": [[1, 0, 0]]},
    {"points": [[1, 2, .03]]}, {"outer": [[.03, True, .1, 5, .04, 1]]},
    {"outer": [[.03, 1.2, .1, 5, .04, 1]]}, {"points": [[float("nan"), 2, .02, 1]]},
    {"has_outer": 1}, {"generation_method": -1}, {"ignored_typo": []},
    {"section_id_name": " "},
])
def test_bad_snapshot_is_rejected_before_guard(fake_provider, patch):
    mcp = FastMCP("snapshots")
    register_tools_with_envelope(mcp, register_check_snapshot_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_section_reinforcement", {"definition": {**SECTION, **patch}}))
    fake_provider.ensure_operation_allowed.assert_not_called()
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


@pytest.mark.parametrize("field", list(SECTION))
def test_complete_snapshot_rejects_missing_fields(fake_provider, field):
    definition = {k: v for k, v in SECTION.items() if k != field}
    with pytest.raises(ToolError, match=field):
        tool_fns(register_check_snapshot_tools, fake_provider)["set_section_reinforcement"](definition=definition)
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


@pytest.mark.parametrize("identifier", ["1", "1-I", "1-J", "G7-2"])
def test_complete_identifiers_use_by_name_endpoint(fake_provider, identifier):
    tool_fns(register_check_snapshot_tools, fake_provider)["remove_section_reinforcement"](section_id_name=identifier)
    assert fake_provider._cdb.calls == [("remove_section_reinforcement_by_name", (), {"section_id_name": identifier})]
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("state", [
    {"status": "state_unknown"},
    {"status": "model_state", "model_state": {"model_opened": False, "capabilities": {}}},
    {"status": "model_state", "model_state": {"phase": "solving", "capabilities": {"check_model": True}}},
    {"status": "model_state", "model_state": {"phase": "postprocessing", "capabilities": {"check_model": True}}},
])
def test_snapshot_tools_require_model_permission(fake_provider, state):
    fake_provider.get_model_state = lambda: state
    with pytest.raises(ToolError):
        tool_fns(register_check_snapshot_tools, fake_provider)["set_section_reinforcement"](definition=SECTION)
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


def test_snapshot_does_not_require_a_current_csan_case(fake_provider):
    state = ready_model_state()
    state["model_state"]["capabilities"]["check_model"] = False
    fake_provider.get_model_state = lambda: state
    tool_fns(register_check_snapshot_tools, fake_provider)["set_section_reinforcement"](definition=SECTION)
    assert fake_provider._mdb.count("update_model") == 1


def test_missing_snapshot_api_fails_explicitly(fake_provider):
    fake_provider._cdb = SimpleNamespace()
    with pytest.raises(ToolError, match="does not support"):
        tool_fns(register_check_snapshot_tools, fake_provider)["set_section_reinforcement"](definition=SECTION)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("shear, torsion", [
    (None, []), ([], None), ([], []), (None, None),
    ([[1, 3, 0, 3, 0]], [[1, 3, 0]]),
])
def test_assignment_none_empty_and_zero_are_distinct(fake_provider, shear, torsion):
    tool_fns(register_check_snapshot_tools, fake_provider)["set_element_stirrups"](request={"shear": shear, "torsion": torsion})
    assert fake_provider._cdb.calls == [("set_element_stirrups", (), {"shear": shear, "torsion": torsion})]
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("assignment", [
    {"shear": [[1, 1, 0, 0]]}, {"torsion": [[1, 0, 0, 0]]},
    {"shear": [[1, 3, 0, 3, 0], [1, 3, 0, 0, 0]]},
    {"torsion": [[1, 3, 0], [1, 0, 3]]}, {"torsion": [[0, 1, 0]]},
    {"torsion": [[1, -1, 0]]}, {"torsion": [[1, True, 0]]},
    {"torsion": [[1, 1.5, 0]]},
])
def test_invalid_assignments_fail_before_guard(fake_provider, assignment):
    mcp = FastMCP("assignments")
    register_tools_with_envelope(mcp, register_check_snapshot_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("set_element_stirrups", {"request": assignment}))
    fake_provider.ensure_operation_allowed.assert_not_called()


def test_stirrup_rename_passes_explicit_original_id_without_unit_conversion(fake_provider):
    definition = copy.deepcopy(next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_stirrup"))
    definition["StirrupTypeId"] = 8
    tool_fns(register_check_snapshot_tools, fake_provider)["set_check_stirrup_snapshot"](definition=definition, original_id=1)
    assert fake_provider._cdb.last("set_check_stirrup")[2] == {"definition": definition, "original_id": 1}
    assert definition["StirrupType"] == 0
    assert definition["StirrupDiameter"] == 12 and definition["StirrupSpacing"] == .1


def test_stirrup_snapshot_rejects_partial_legacy_definition(fake_provider):
    with pytest.raises(ToolError, match="StirrupTypeName"):
        tool_fns(register_check_snapshot_tools, fake_provider)["set_check_stirrup_snapshot"](definition={"StirrupTypeId": 8})
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


def test_material_snapshot_preserves_zero_false_and_extended_properties(fake_provider):
    definition = copy.deepcopy(next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_material"))
    definition["parameters"]["future_property"] = {"enabled": False, "points": [[0, 0], [1.5, 2]]}
    tool_fns(register_check_snapshot_tools, fake_provider)["manage_check_material"](request={"action": "set", "definition": definition})
    assert fake_provider._cdb.last("set_check_material")[2]["definition"] == definition
    assert definition["elastic_modulus"] == 30000000000.0
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("tool, value", [
    ("manage_check_material", {"action": "reset"}),
    ("manage_check_material", {"action": "reset", "index": 0}),
    ("manage_check_material", {"action": "set", "definition": {"index": 1}}),
    ("manage_check_material", {"action": "reset", "index": 1, "definition": {}}),
    ("manage_check_case_definition", {"action": "remove", "family": "other", "index": 1}),
    ("manage_check_case_definition", {"action": "remove", "family": "concrete", "index": True}),
    ("manage_check_case_definition", {"action": "remove", "family": "seismic"}),
    ("manage_check_case_definition", {"action": "set", "definition": {"family": "concrete", "index": 1}}),
])
def test_invalid_management_requests_fail_before_guard(fake_provider, tool, value):
    mcp = FastMCP("snapshots")
    register_tools_with_envelope(mcp, register_check_snapshot_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool(tool, {"request": value}))
    fake_provider.ensure_operation_allowed.assert_not_called()


def test_material_nonfinite_nested_property_fails_before_guard(fake_provider):
    definition = copy.deepcopy(next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_material"))
    definition["parameters"]["future_curve"] = [[1, float("nan")]]
    mcp = FastMCP("snapshots")
    register_tools_with_envelope(mcp, register_check_snapshot_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("manage_check_material", {"request": {"action": "set", "definition": definition}}))
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("flags", [[True] * 5, [True] * 7, [1] * 6])
def test_case_force_flags_require_six_actual_booleans(fake_provider, flags):
    definition = copy.deepcopy(next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_case"))
    definition["force_components"] = flags
    with pytest.raises(ToolError):
        tool_fns(register_check_snapshot_tools, fake_provider)["manage_check_case_definition"](request={"action": "set", "definition": definition})
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


@pytest.mark.parametrize("flag", [False, True])
def test_material_number_convention_remains_a_committed_gateway_command(check_wire, flag):
    p, wire = check_wire
    if not callable(getattr(p._cdb, "set_steel_bar_material_convention", None)):
        pytest.skip("Installed qtmodel lacks model snapshot operations")
    tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](
        api_object="cdb", method="set_steel_bar_material_convention", kwargs={"new_format": flag},
    )
    assert [h for h, _ in wire] == ["SET-STEEL-BAR-MATERIAL-CONVENTION", "UPDATE"]
    assert wire[0][1]["new_format"] is flag


def test_model_snapshots_commit_before_named_concrete_import_and_solve(fake_provider):
    p = fake_provider
    events, pending, committed = [], {}, {}

    def writer(method):
        def write(**kwargs):
            events.append(method)
            pending[method] = copy.deepcopy(kwargs)
        return write

    methods = ["set_section_reinforcement", "set_check_material", "set_check_case"]
    for method in methods:
        setattr(p._cdb, method, writer(method))

    def commit():
        committed.update(pending)
        pending.clear()
        events.append("commit")

    def import_case(case_name):
        assert not pending and set(committed) == set(methods)
        assert committed["set_section_reinforcement"]["definition"] == SECTION
        assert committed["set_check_case"]["definition"]["name"] == case_name
        events.append("import")

    def solve(**kwargs):
        assert events[-1] == "import"
        assert kwargs["wait"] is True and kwargs["max_wait"] == 12
        events.append("solve")
        return {"state": "succeeded", "is_running": False, "ok": True}

    p._mdb.update_model = commit
    p._cdb.import_concrete_check_case = import_case
    p._cdb.solve_concrete_check = solve
    fns = tool_fns(register_check_snapshot_tools, p)
    fns["set_section_reinforcement"](definition=SECTION)
    material = next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_material")
    case = next(c["kwargs"]["definition"] for c in CALLS if c["method"] == "set_check_case")
    fns["manage_check_material"](request={"action": "set", "definition": material})
    fns["manage_check_case_definition"](request={"action": "set", "definition": case})
    assert events == ["set_section_reinforcement", "commit", "set_check_material", "commit", "set_check_case", "commit"]
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    p.get_model_state = lambda: state
    result = tool_fns(register_checking_tools, p)["run_concrete_check"](name=case["name"], max_wait_seconds=12)
    assert events[-2:] == ["import", "solve"]
    assert "get_check_data" in result["message"]
