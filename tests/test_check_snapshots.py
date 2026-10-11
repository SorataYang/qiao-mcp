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
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope

CALLS = json.loads((Path(__file__).parent / "fixtures/check_snapshots.json").read_text())["calls"]
SNAPSHOT_CALLS = [item for item in CALLS if item["method"] in {
    "set_section_reinforcement", "remove_section_reinforcement_by_name", "set_check_stirrup", "set_element_stirrups",
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
                "set_check_stirrup": "set_check_stirrup_snapshot"}.get(method, method)
        arguments = {"request": kwargs} if method == "set_element_stirrups" else kwargs
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
