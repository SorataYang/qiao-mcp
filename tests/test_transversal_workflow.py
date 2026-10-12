"""Offline definition→readback→settings→solve→result flow, not a numerical proof."""

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import ready_model_state, tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.prompts import register_prompts
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope


@pytest.mark.parametrize("mode, stage, name, expected", [
    ("static", -1, "恒载", "ST:恒载"), ("static", -1, "ST:恒载", "ST:恒载"),
    ("static", 1, "施工", "施工"), ("full", -1, "bridge-confirmed:横向", "bridge-confirmed:横向"),
    ("full", -1, "原样名称", "原样名称"), ("full", 2, "stage:工况", "stage:工况"),
])
@pytest.mark.parametrize("result_type, method", [
    ("deformation", "get_deformation"), ("force", "get_element_force"),
    ("stress", "get_element_stress"), ("reaction", "get_reaction"),
])
def test_result_name_modes(fake_provider, mode, stage, name, expected, result_type, method):
    tool_fns(register_modeling_tools, fake_provider)["get_analysis_results"](
        result_type=result_type, ids=[3], stage_id=stage, case_name=name, case_name_mode=mode,
    )
    assert fake_provider._odb.last(method)[2] == {"ids": [3], "stage_id": stage, "case_name": expected}
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("name", ["", "  "])
def test_full_name_mode_requires_an_identifier(fake_provider, name):
    with pytest.raises(ToolError, match="complete case_name"):
        tool_fns(register_modeling_tools, fake_provider)["get_analysis_results"](
            result_type="force", case_name=name, case_name_mode="full",
        )
    assert fake_provider._odb.calls == []


@pytest.mark.parametrize("kind, header", [("force", "GET-ELEMENT-FORCE"), ("deformation", "GET-DEFORMATION"), ("reaction", "GET-REACTION")])
def test_real_result_constructor_preserves_full_name(fake_provider, monkeypatch, kind, header):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    send = Mock(return_value="[]")
    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._odb = qtmodel.odb
    tool_fns(register_modeling_tools, fake_provider)["get_analysis_results"](
        result_type=kind, ids=[3], stage_id=-1,
        case_name="bridge-confirmed:横向", case_name_mode="full",
    )
    send.assert_called_once()
    assert send.call_args.kwargs["header"] == header
    payload = json.loads(send.call_args.kwargs["command"])
    assert payload["case_name"] == "bridge-confirmed:横向"
    assert payload["stage_id"] == -1 and payload["ids"] == [3]


def test_mode_schema_rejects_unknown_before_guard(fake_provider):
    mcp = FastMCP("result-modes")
    register_tools_with_envelope(mcp, register_modeling_tools, fake_provider)
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "get_analysis_results")
    assert tool.inputSchema["properties"]["case_name_mode"]["enum"] == ["static", "full"]
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("get_analysis_results", {"result_type": "force", "case_name_mode": "guess"}))
    fake_provider.ensure_operation_allowed.assert_not_called()


def test_transversal_prompt_references_registered_tools(fake_provider):
    mcp = FastMCP("prompts")
    register_tool_catalog(mcp, fake_provider)
    register_prompts(mcp)
    prompts = asyncio.run(mcp.list_prompts())
    assert len(prompts) == 5
    prompt = asyncio.run(mcp.get_prompt("analyze_transversal", {"case_name": "横向试验"}))
    content = "\n".join(message.content.text for message in prompt.messages)
    references = set(re.findall(r"`([A-Za-z_][A-Za-z_0-9]*)`", content))
    assert references <= {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"configure_operation_stage", "set_transversal_case", "run_analysis", "get_analysis_results"} <= references
    assert 'case_name_mode="full"' in content and "clear_existing=False" in content
    assert "横向试验" in content


def test_definitions_flow_through_actual_ids_and_explicit_analysis(fake_provider):
    p = fake_provider
    fixture = json.loads((Path(__file__).parent / "fixtures/transversal_definitions.json").read_text())
    definitions = {}
    actual_ids = {"vehicle": 93, "lane": 187, "case": 52}
    state = ready_model_state()
    state["model_state"]["capabilities"]["query_results"] = False
    p.get_model_state = lambda: state

    def make_writer(kind):
        def write(**kwargs):
            p._mdb.calls.append((f"add_transversal_{kind}", (), kwargs))
            definitions[kind] = {**kwargs, "index": actual_ids[kind]}
        return write

    def make_reader(kind):
        def read(name="", index=-1):
            item = definitions.get(kind)
            return [item] if item and (not name or item["name"] == name) and (index == -1 or item["index"] == index) else []
        return read

    for kind in actual_ids:
        setattr(p._mdb, f"add_transversal_{kind}", make_writer(kind))
        setattr(p._mdb, f"get_transversal_{kind}s", make_reader(kind))

    def solve(**kwargs):
        p._mdb.calls.append(("do_solve", (), kwargs))
        assert definitions["case"]["vehicle_id"] == 93
        assert definitions["case"]["lane_id"] == 187
        assert p._mdb.last("update_operation_stage_setting")[2]["transversal_load_cases"] == [definitions["case"]["name"]]
        state["model_state"]["capabilities"]["query_results"] = True
        state["model_state"]["has_result_data"] = True
        return {"state": "completed"}

    p._mdb.do_solve = solve
    mcp = FastMCP("transversal-flow")
    register_tool_catalog(mcp, p)
    fns = {tool.name: tool.fn for tool in mcp._tool_manager.list_tools()}
    fns["configure_live_load_system"](system="china_transversal")
    ids = {}
    for kind in ("vehicle", "lane", "case"):
        definition = dict(fixture["definitions"][kind])
        definition.pop("index")
        if kind == "lane":
            definition["distribution_widths"] = definition.pop("load_factors")
        if kind == "case":
            definition.update(vehicle_id=ids["vehicle"], lane_id=ids["lane"])
            factors = [float(v) for v in definition["reduction_factors"].split("|")[1].split(",")]
            definition.update(reduction_factors=factors[:-1], greater_lane_factor=factors[-1])
        result = fns[f"set_transversal_{kind}"](request={"action": "add", **definition})
        ids[kind] = result["data"]["index"]
    assert ids == actual_ids
    assert p._mdb.count("set_live_load_type") == 1 and p._mdb.count("do_solve") == 0
    fns["configure_operation_stage"](
        final_stage="成桥", static_load_cases=["恒载"], sink_load_cases=[], live_load_cases=[],
        transversal_load_cases=[definitions["case"]["name"]],
    )
    assert p._mdb.count("update_model") == 5
    with pytest.raises(ToolError):
        fns["get_analysis_results"](result_type="force", case_name="bridge-confirmed:横向", case_name_mode="full")
    asyncio.run(fns["run_analysis"](ctx=AsyncMock(), read_timeout=60))
    assert p._mdb.last("do_solve")[2]["sync"] is False
    assert p._mdb.count("do_solve") == 1
    for result_type, method in [("force", "get_element_force"), ("deformation", "get_deformation"), ("reaction", "get_reaction")]:
        fns["get_analysis_results"](result_type=result_type, ids=[3], case_name="bridge-confirmed:横向", case_name_mode="full")
        assert p._odb.last(method)[2]["case_name"] == "bridge-confirmed:横向"
