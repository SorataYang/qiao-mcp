"""Explicit live-load settings preserve selections and commit exactly once."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.envelope import (
    ToolError,
    _annotations_for,
    _operation_for,
    register_tools_with_envelope,
)
from qiao_mcp.tools.moving_load import register_moving_load_tools

SYSTEMS = {"china_longitudinal": 0, "aashto": 1, "china_transversal": 2, "bs": 3, "en1991": 4}
OPERATION = {
    "final_stage": "成桥", "static_load_cases": ["恒载"], "sink_load_cases": [],
    "live_load_cases": ["纵向"], "transversal_load_cases": ["横向"], "do_analysis": False,
}


@pytest.mark.parametrize("system, kind", SYSTEMS.items())
@pytest.mark.parametrize("clear", [False, True])
def test_system_mapping_and_one_commit(fake_provider, system, kind, clear):
    tool_fns(register_moving_load_tools, fake_provider)["configure_live_load_system"](
        system=system, clear_existing=clear,
    )
    assert fake_provider._mdb.calls == [
        ("set_live_load_type", (), {"kind": kind, "clear_existing": clear}),
        ("update_model", (), {}),
    ]


def test_operation_replaces_all_lists_and_preserves_false(fake_provider):
    tool_fns(register_moving_load_tools, fake_provider)["configure_operation_stage"](**OPERATION)
    assert fake_provider._mdb.calls == [
        ("update_operation_stage_setting", (), OPERATION), ("update_model", (), {}),
    ]


@pytest.mark.parametrize("tool, method, header, args, payload", [
    ("configure_live_load_system", "set_live_load_type", "SET-LIVE-LOAD-TYPE",
     {"system": "china_transversal"}, {"kind": 2, "clear_existing": False}),
    ("configure_operation_stage", "update_operation_stage_setting", "UPDATE-OPERATION-STAGE-SETTING",
     OPERATION, OPERATION),
])
def test_real_settings_payload(qtmodel_wire, tool, method, header, args, payload):
    p, requests = qtmodel_wire
    fn = getattr(p._mdb, method, None)
    if fn is None or not set(payload) <= set(inspect.signature(fn).parameters):
        pytest.skip("Installed qtmodel lacks explicit live-load settings")
    tool_fns(register_moving_load_tools, p)[tool](**args)
    assert [h for h, _ in requests] == [header, "UPDATE"]
    wire = dict(requests[0][1])
    wire.pop("version", None)
    assert wire == payload


@pytest.mark.parametrize("field", list(OPERATION)[:-1])
def test_omitted_operation_selection_fails_before_guard(fake_provider, field):
    mcp = FastMCP("configuration")
    register_tools_with_envelope(mcp, register_moving_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    args = {k: v for k, v in OPERATION.items() if k != field}
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("configure_operation_stage", args))
    fake_provider.ensure_operation_allowed.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("args", [
    {"system": "typo"}, {"system": "aashto", "clear_existing": "false"},
    {"system": "aashto", "clear_existing": 1},
])
def test_bad_system_options_fail_before_guard(fake_provider, args):
    mcp = FastMCP("configuration")
    register_tools_with_envelope(mcp, register_moving_load_tools, fake_provider)
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("configure_live_load_system", args))
    fake_provider.ensure_operation_allowed.assert_not_called()


def test_missing_or_old_method_fails_without_writes(fake_provider):
    commit = Mock()
    fake_provider._mdb = SimpleNamespace(update_model=commit)
    with pytest.raises(ValueError, match="does not support"):
        fake_provider.configure_live_load_system("china_transversal")

    def old_switch(kind):
        pytest.fail("Old switch must not run: it cannot promise no implicit clearing")

    fake_provider._mdb.set_live_load_type = old_switch
    with pytest.raises(ValueError, match="arguments"):
        fake_provider.configure_live_load_system("china_transversal")
    commit.assert_not_called()


@pytest.mark.parametrize("tool, args, capability", [
    ("configure_live_load_system", {"system": "china_transversal"}, "modify_model"),
    ("configure_operation_stage", OPERATION, "modify_stage_data"),
])
@pytest.mark.parametrize("unknown", [False, True])
def test_settings_respect_permissions(fake_provider, tool, args, capability, unknown):
    state = ready_model_state()
    state["model_state"]["capabilities"][capability] = False
    fake_provider.get_model_state = lambda: {"status": "state_unknown"} if unknown else state
    with pytest.raises(ToolError):
        tool_fns(register_moving_load_tools, fake_provider)[tool](**args)
    assert fake_provider._mdb.calls == []


def test_rejected_switch_never_retries_with_clearing(fake_provider):
    switch = Mock(side_effect=ValueError("Referenced cases prevent switching"))
    fake_provider._mdb.set_live_load_type = switch
    with pytest.raises(ToolError, match="Referenced"):
        tool_fns(register_moving_load_tools, fake_provider)["configure_live_load_system"](system="aashto")
    switch.assert_called_once_with(kind=1, clear_existing=False)
    assert fake_provider._mdb.calls == []


def test_commit_failure_reports_that_command_already_ran(fake_provider):
    fake_provider._mdb.update_model = Mock(side_effect=RuntimeError("commit failed"))
    with pytest.raises(ToolError, match="model may have changed"):
        tool_fns(register_moving_load_tools, fake_provider)["configure_live_load_system"](system="aashto")
    assert fake_provider._mdb.count("set_live_load_type") == 1
    fake_provider._mdb.update_model.assert_called_once_with()


def test_settings_annotations_and_operation_classes():
    assert _operation_for("configure_operation_stage") == "stage_write"
    assert _operation_for("configure_live_load_system") == "model_write"
    for name in ("configure_operation_stage", "configure_live_load_system"):
        assert _annotations_for(name).destructiveHint
        assert not _annotations_for(name).readOnlyHint
