"""CDB base-model commands share model permissions and one commit with the gateway."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError, _operation_for

METHODS = [
    "set_steel_bar_material_convention", "set_section_reinforcement",
    "remove_section_reinforcement_by_name", "set_check_stirrup", "set_element_stirrups",
    "set_check_material", "remove_check_material", "set_check_case", "remove_check_case_snapshot",
]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("gateway", [False, True])
def test_snapshot_requires_model_write_not_csan_permission(fake_provider, method, gateway):
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: state
    with pytest.raises(RuntimeError, match="modify_model"):
        if gateway:
            fake_provider.call_api("cdb", method, {})
        else:
            fake_provider.write_check_snapshot(method)
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("gateway", [False, True])
def test_snapshot_commits_once_without_current_csan(fake_provider, method, gateway):
    state = ready_model_state()
    state["model_state"]["capabilities"]["check_model"] = False
    fake_provider.get_model_state = lambda: state
    if gateway:
        fake_provider.call_api("cdb", method, {"value": False})
    else:
        fake_provider.write_check_snapshot(method, value=False)
    assert fake_provider._cdb.calls == [(method, (), {"value": False})]
    assert fake_provider._mdb.calls == [("update_model", (), {})]


@pytest.mark.parametrize("method", ["get_reinforcement_data", "save_concrete_check_file", "solve_concrete_check", "update_check_stirrup"])
def test_legacy_cdb_operations_do_not_commit_model(fake_provider, method):
    fake_provider.call_api("cdb", method, {})
    assert fake_provider._cdb.calls == [(method, (), {})]
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("gateway", [False, True])
def test_failed_snapshot_does_not_commit_or_retry(fake_provider, gateway):
    write = Mock(side_effect=RuntimeError("rejected snapshot"))
    fake_provider._cdb.set_check_material = write
    with pytest.raises(RuntimeError, match="rejected snapshot"):
        if gateway:
            fake_provider.call_api("cdb", "set_check_material", {"definition": {"index": 1}})
        else:
            fake_provider.write_check_snapshot("set_check_material", definition={"index": 1})
    write.assert_called_once()
    assert fake_provider._mdb.calls == []


def test_unknown_state_blocks_snapshot(fake_provider):
    fake_provider.get_model_state = lambda: {"status": "state_unknown"}
    with pytest.raises(RuntimeError):
        fake_provider.write_check_snapshot("set_element_stirrups", shear=[], torsion=None)
    assert fake_provider._cdb.calls == fake_provider._mdb.calls == []


def test_explicit_method_list_and_old_signatures_fail_before_write(fake_provider):
    assert fake_provider._API_CDB_MODEL_WRITES == frozenset(METHODS)
    fake_provider._cdb = SimpleNamespace(set_check_stirrup=lambda definition: pytest.fail("must bind before writing"))
    with pytest.raises(ValueError, match="arguments"):
        fake_provider.write_check_snapshot("set_check_stirrup", definition={"StirrupTypeId": 3}, original_id=1)
    with pytest.raises(ValueError, match="Not a model snapshot"):
        fake_provider.write_check_snapshot("solve_concrete_check")
    assert fake_provider._mdb.calls == []


def test_gateway_reports_commit_failure_without_replaying(fake_provider):
    fake_provider._mdb.update_model = Mock(side_effect=RuntimeError("commit unavailable"))
    with pytest.raises(ToolError, match="model may have changed"):
        tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](
            api_object="cdb", method="set_element_stirrups", kwargs={"shear": [], "torsion": None},
        )
    assert fake_provider._cdb.count("set_element_stirrups") == 1
    fake_provider._mdb.update_model.assert_called_once()


def test_gateway_preserves_outcome_unknown_for_cdb(fake_provider):
    error = type("CommandOutcomeUnknownError", (RuntimeError,), {})("reply lost")
    fake_provider._cdb.set_element_stirrups = Mock(side_effect=error)
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN"):
        tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](
            api_object="cdb", method="set_element_stirrups", kwargs={"shear": []},
        )
    fake_provider._cdb.set_element_stirrups.assert_called_once()
    assert fake_provider._mdb.calls == []


def test_snapshot_tool_classes_do_not_change_legacy_check_tools():
    for name in ["set_section_reinforcement", "remove_section_reinforcement", "set_check_stirrup_snapshot", "set_element_stirrups", "manage_check_material", "manage_check_case_definition"]:
        assert _operation_for(name) == "model_write"
    for name in ["add_parametric_reinforcement", "manage_check_stirrup", "assign_element_stirrup"]:
        assert _operation_for(name) == "check_write"
