"""B1 catalog queries preserve legacy text results and server-side detail pages."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.envelope import ToolError, register_tools_with_envelope
from qiao_mcp.tools.queries import register_query_tools

CATALOGS = [
    ("material_summaries", "get_material_summaries", {}, [{"material_id": 7, "name": "C50", "material_type": "混凝土"}]),
    ("material_detail", "get_material_detail", {"material_id": 7}, {"material_id": 7}),
    ("load_case_summaries", "get_load_case_summaries", {}, [{"load_case_id": 7, "name": "恒载"}]),
    ("load_case_detail", "get_load_case_detail", {"load_case_id": 7, "offset": 10, "limit": 1},
     {"load_case_id": 7, "items": [{"id": 99}], "has_more": True}),
    ("load_combination_summaries", "get_load_combination_summaries", {}, [{"combination_id": 7, "name": "组合"}]),
    ("load_combination_detail", "get_load_combination_detail", {"combination_id": 7, "offset": 10, "limit": 1},
     {"combination_id": 7, "items": [{"id": 99}], "has_more": True}),
    ("construction_stage_summaries", "get_construction_stage_summaries", {}, [{"stage_id": 7, "name": "成桥", "duration": 0.5,
      "cumulative_duration": 7.5, "result_available": False, "is_final": True}]),
    ("element_section", "get_element_section", {"ele_id": 7, "position": 1}, {"index": 8, "name": "实际截面"}),
    ("spans", "get_span_data", {}, [{"id": 7, "name": "跨径", "element_ids": [2], "support_ids": [3]}]),
]


def query_args(kind, options):
    args = {"kind": kind}
    if kind.endswith("_detail") or kind == "element_section":
        args["ids"] = [7]
    if kind == "element_section":
        args["position"] = 1
    if "offset" in options:
        args.update(offset=10, limit=1)
    return args


@pytest.mark.parametrize("kind, method, options, response", CATALOGS)
def test_catalog_dispatch_and_data(fake_provider, kind, method, options, response):
    fn = Mock(return_value=response)
    setattr(fake_provider._mdb, method, fn)
    result = tool_fns(register_query_tools, fake_provider)["get_model_data"](**query_args(kind, options))
    fn.assert_called_once_with(**options)
    text = result["message"]
    # Decode after the textual header; summaries have a legacy pagination line.
    lines = text.splitlines()
    raw = "\n".join(lines[2:] if isinstance(response, list) else lines[1:])
    assert json.loads(raw) == response
    assert fake_provider._mdb.calls == fake_provider._odb.calls == fake_provider._cdb.calls == []


@pytest.mark.parametrize("kind, method, options, response", CATALOGS)
def test_real_catalog_constructor_keeps_http_fields(fake_provider, monkeypatch, kind, method, options, response):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, method, None)):
        pytest.skip(f"Installed qtmodel lacks {method}")
    # Unknown fields must survive typed summary conversion too.
    if isinstance(response, list):
        response = [{**item, "future_field": {"value": 1}} for item in response]
    send = Mock(return_value=json.dumps(response))
    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    result = tool_fns(register_query_tools, fake_provider)["get_model_data"](**query_args(kind, options))
    send.assert_called_once()
    kwargs = send.call_args.kwargs
    assert kwargs["header"] == method.replace("_", "-").upper()
    payload = json.loads(kwargs["command"]) if kwargs["command"] else {}
    payload.pop("version", None)
    assert payload == options
    lines = result["message"].splitlines()
    assert json.loads("\n".join(lines[2:] if isinstance(response, list) else lines[1:])) == response


@pytest.mark.parametrize("kind", ["material_detail", "load_case_detail", "load_combination_detail", "element_section"])
@pytest.mark.parametrize("ids", [None, [], [1, 2], True, 1.5, 0, -1, "1to2", "7", [True]])
def test_details_reject_ambiguous_ids_before_query(fake_provider, kind, ids):
    mcp = FastMCP("catalog-details")
    register_tools_with_envelope(mcp, register_query_tools, fake_provider)
    with pytest.raises(ToolError):
        asyncio.run(mcp.call_tool("get_model_data", {"kind": kind, "ids": ids}))
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("kind, method, options, response", CATALOGS)
def test_missing_catalog_method_errors(fake_provider, kind, method, options, response):
    fake_provider._mdb = SimpleNamespace()
    fake_provider._odb = SimpleNamespace()
    with pytest.raises(ToolError, match="no model query"):
        tool_fns(register_query_tools, fake_provider)["get_model_data"](**query_args(kind, options))


def test_catalog_failure_is_not_empty_success(fake_provider):
    fake_provider._mdb.get_material_summaries = Mock(side_effect=TimeoutError("timeout"))
    with pytest.raises(ToolError, match="timeout"):
        tool_fns(register_query_tools, fake_provider)["get_model_data"](kind="material_summaries")


def test_legacy_list_output_stays_paginated_text(fake_provider):
    fake_provider._mdb.get_node_data = Mock(return_value=[{"id": 1}, {"id": 2}])
    result = tool_fns(register_query_tools, fake_provider)["get_model_data"](kind="nodes", limit=1, offset=1)
    assert result == {"status": "success", "message": 'nodes:\n[2–2 of 2]\n[\n  {\n    "id": 2\n  }\n]'}
