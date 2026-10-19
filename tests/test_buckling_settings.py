"""Regression for the native route requiring nonempty variable load cases."""

import asyncio

import pytest
from conftest import tool_fns

from qiao_mcp.registration import OperationServer
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope


@pytest.mark.parametrize("enabled", [False, True])
def test_buckling_full_definition_reaches_native_wire(qtmodel_wire, enabled):
    provider, requests = qtmodel_wire
    tool_fns(register_modeling_tools, provider)["update_bulking_setting"](
        variable_cases=["轴压", "制动力"], constant_cases=["恒载"],
        do_analysis=enabled, mode_count=2, stage_id=3,
        calculate_kind=2, stressed=False,
    )
    payload = next(p for h, p in requests if h == "UPDATE-BULKING-SETTING")
    expected = {
        "do_analysis": enabled, "mode_count": 2, "stage_id": 3,
        "calculate_kind": 2, "stressed": False,
        "constant_cases": ["恒载"], "variable_cases": ["轴压", "制动力"],
    }
    assert {key: payload[key] for key in expected} == expected
    assert len(requests) == 2  # Full definition, then refresh.


def test_disabled_buckling_still_supplies_required_case(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_modeling_tools, provider)["update_bulking_setting"](
        variable_cases=["轴压"], do_analysis=False,
    )
    payload = next(p for h, p in requests if h == "UPDATE-BULKING-SETTING")
    assert payload["variable_cases"] == ["轴压"]
    assert payload["constant_cases"] == []
    assert payload["do_analysis"] is False


@pytest.mark.parametrize("arguments", [
    {}, {"variable_cases": []}, {"variable_cases": [""]},
    {"variable_cases": [" "]}, {"variable_cases": ["轴压"], "mode_count": 0},
    {"variable_cases": ["轴压"], "constant_cases": [" "]},
    {"variable_cases": ["轴压"], "calculate_kind": 3},
])
def test_incomplete_buckling_definition_fails_before_native_write(fake_provider, arguments):
    server = OperationServer("buckling-test")
    register_tools_with_envelope(server, register_modeling_tools, fake_provider)
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("update_bulking_setting", arguments))
    assert fake_provider._mdb.calls == []


def test_catalog_requires_variable_cases(fake_provider):
    server = OperationServer("buckling-schema")
    register_modeling_tools(server, fake_provider)
    tool = next(t for t in asyncio.run(server.list_tools()) if t.name == "update_bulking_setting")
    assert tool.input_schema["required"] == ["variable_cases"]
    assert tool.input_schema["properties"]["variable_cases"]["minItems"] == 1
