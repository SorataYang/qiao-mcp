"""Server-paged B1 queries: typed inputs, read guards, native payloads and pages.

Wire fixtures mirror qtmodel 8ae651e tests/test_mdb_model_*_query_contract.py.
They verify SDK request serialization, not real QiaoTong filtering semantics.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns
from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from qiao_mcp.tools.envelope import ToolError, _operation_for, register_tools_with_envelope
from qiao_mcp.tools.queries import register_query_tools
from qiao_mcp.tools.schemas import ModelQuery

QUERIES = [
    ({"kind": "nodes", "node_ids": [3, 7], "structure_group_names": ["主梁"],
      "near": [0, 1, 2], "tolerance": 0.01, "bbox": [-1, 0, 1, 1, 2, 3]},
     "query_node_data", "QUERY-NODES"),
    ({"kind": "elements", "element_ids": 5, "structure_group_names": ["主梁"],
      "element_type": "beam", "node_ids": [3, 7], "node_match": "all",
      "material_ids": [2], "section_ids": [4], "thickness_ids": [9]},
     "query_element_data", "QUERY-ELEMENTS"),
    ({"kind": "boundaries", "boundary_type": "general_support", "boundary_ids": [5],
      "group_names": ["边界"], "node_ids": [3], "element_ids": [7]},
     "query_boundary_data", "QUERY-BOUNDARIES"),
    ({"kind": "loads", "load_family": "beam_distributed_load", "load_ids": [3],
      "target_ids": [7], "case_names": ["恒载"], "group_names": ["荷载"]},
     "query_load_data", "QUERY-LOADS"),
    ({"kind": "node_local_axes", "node_ids": [7], "structure_group_names": ["主梁"]},
     "query_node_local_axis_data", "QUERY-NODE-LOCAL-AXES"),
    ({"kind": "section_summaries", "section_ids": [7, 3], "query": "梁",
      "section_type": "混凝土箱梁"}, "query_section_summaries", "QUERY-SECTION-SUMMARIES"),
]


@pytest.fixture
def query_catalog(fake_provider):
    mcp = FastMCP("model-queries")
    register_tools_with_envelope(mcp, register_query_tools, fake_provider)
    return mcp


@pytest.mark.parametrize("query, method, header", QUERIES)
def test_query_dispatch_keeps_native_page(query_catalog, fake_provider, query, method, header):
    page = {"items": [{"id": 7, "nested": {"extension": True}}], "offset": 40,
            "has_more": True, "missing_ids": [999], "future_field": "kept"}
    fn = Mock(return_value=page)
    setattr(fake_provider._mdb, method, fn)
    _, result = asyncio.run(query_catalog.call_tool("query_model_data", {
        "request": {**query, "limit": 2, "offset": 40},
    }))
    assert result == {"status": "success", "data": page}
    assert "total" not in result["data"]
    kwargs = fn.call_args.kwargs
    assert kwargs["offset"] == 40 and kwargs["limit"] == 2
    assert "kind" not in kwargs
    assert fake_provider._mdb.calls == fake_provider._odb.calls == fake_provider._cdb.calls == []


@pytest.mark.parametrize("query, method, header", QUERIES)
def test_real_client_query_serialization(fake_provider, monkeypatch, query, method, header):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, method, None)):
        pytest.skip(f"Installed qtmodel lacks {method}")
    page = {"items": [{"unknown_field": "保留"}], "has_more": False}
    send = Mock(return_value=json.dumps(page))
    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    result = tool_fns(register_query_tools, fake_provider)["query_model_data"](
        request={**query, "offset": 40, "limit": 2},
    )
    assert result["data"] == page
    send.assert_called_once()
    assert send.call_args.kwargs["header"] == header
    payload = json.loads(send.call_args.kwargs["command"])
    assert payload["offset"] == 40 and payload["limit"] == 2
    for key, value in query.items():
        if key == "kind":
            continue
        assert payload[key] == ([value] if key.endswith("_ids") and isinstance(value, int) else value)
    if "tolerance" not in query:
        assert "tolerance" not in payload


@pytest.mark.parametrize("query", [
    {"kind": "unknown"}, {"kind": "nodes"}, {"kind": "nodes", "node_ids": []},
    {"kind": "nodes", "node_ids": True}, {"kind": "nodes", "node_ids": 1.5},
    {"kind": "nodes", "node_ids": [0]}, {"kind": "nodes", "node_ids": [True]},
    {"kind": "nodes", "node_ids": "1to10"},
    {"kind": "nodes", "structure_group_names": "主梁"},
    {"kind": "nodes", "structure_group_names": ["  "]},
    {"kind": "nodes", "near": [0, 0, 0]},
    {"kind": "nodes", "tolerance": 1},
    {"kind": "nodes", "near": [0, 0], "tolerance": 1},
    {"kind": "nodes", "near": [0, 0, 0], "tolerance": -1},
    {"kind": "nodes", "near": [0, 0, float("nan")], "tolerance": 1},
    {"kind": "node_local_axes", "bbox": [0, 0, 2, 1, 1, 1]},
    {"kind": "nodes", "bbox": [0] * 5},
    {"kind": "elements", "node_match": "none"},
    {"kind": "elements", "element_type": "bogus"},
    {"kind": "elements", "limit": 501}, {"kind": "elements", "offset": -1},
    {"kind": "elements", "limit": True}, {"kind": "elements", "offset": 1.2},
    {"kind": "loads", "load_family": "nodal_force", "case_names": "恒载"},
    {"kind": "loads", "load_family": "live_load"},
    {"kind": "loads"}, {"kind": "boundaries", "boundary_type": "support"},
    {"kind": "section_summaries", "limit": 101},
    {"kind": "section_summaries", "section_ids": list(range(1, 102))},
    {"kind": "section_summaries", "section_ids": 3},
    {"kind": "elements", "node_ids": list(range(1, 502))},
    {"kind": "nodes", "node_ids": [1], "ignored_typo": True},
])
def test_query_validation_precedes_guard(query_catalog, fake_provider, monkeypatch, query):
    guard = Mock()
    monkeypatch.setattr(fake_provider, "ensure_operation_allowed", guard)
    with pytest.raises(ToolError):
        asyncio.run(query_catalog.call_tool("query_model_data", {"request": query}))
    guard.assert_not_called()
    assert fake_provider._mdb.calls == fake_provider._odb.calls == []


@pytest.mark.parametrize("state", [
    {"status": "state_unknown"},
    {"status": "model_state", "model_state": {"model_opened": False, "capabilities": {}}},
    {"status": "model_state", "model_state": {"phase": "solving", "capabilities": {"read_model": False}}},
])
def test_query_respects_read_permission(query_catalog, fake_provider, state):
    fake_provider.get_model_state = lambda: state
    with pytest.raises(ToolError):
        asyncio.run(query_catalog.call_tool("query_model_data", {"request": {"kind": "elements"}}))
    assert fake_provider._mdb.calls == []


def test_query_allowed_without_write_permission(query_catalog, fake_provider):
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: state
    fake_provider._mdb.query_element_data = Mock(return_value={"items": [], "has_more": False})
    _, result = asyncio.run(query_catalog.call_tool("query_model_data", {"request": {"kind": "elements"}}))
    assert result["data"]["items"] == []
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("query, method, header", QUERIES)
def test_missing_api_never_downloads_all_records(fake_provider, query, method, header):
    fake_provider._mdb = SimpleNamespace()
    fake_provider._odb = SimpleNamespace()
    with pytest.raises(ToolError, match="no model query"):
        tool_fns(register_query_tools, fake_provider)["query_model_data"](request=query)


@pytest.mark.parametrize("response", [None, "", {}, [], "not supported"])
def test_invalid_response_does_not_masquerade_as_empty_page(fake_provider, response):
    fake_provider._mdb.query_element_data = Mock(return_value=response)
    with pytest.raises(ToolError, match="no valid query page"):
        tool_fns(register_query_tools, fake_provider)["query_model_data"](request={"kind": "elements"})


def test_query_exception_is_not_swallowed(fake_provider):
    fake_provider._mdb.query_element_data = Mock(side_effect=TimeoutError("query timed out"))
    with pytest.raises(ToolError, match="query timed out"):
        tool_fns(register_query_tools, fake_provider)["query_model_data"](request={"kind": "elements"})


def test_section_page_keeps_truncation_missing_ids_and_input_order(fake_provider):
    page = {"items": [{"section_id": 7}], "total": 2, "truncated": True,
            "missing_section_ids": [999], "offset": 0, "limit": 1}
    fn = Mock(return_value=page)
    fake_provider._mdb.query_section_summaries = fn
    result = tool_fns(register_query_tools, fake_provider)["query_model_data"](request={
        "kind": "section_summaries", "section_ids": [7, 3, 999], "limit": 1,
    })
    assert result["data"] == page
    assert fn.call_args.kwargs["section_ids"] == [7, 3, 999]


def test_query_schema_is_discriminated_closed_and_readonly(query_catalog):
    tool = next(t for t in asyncio.run(query_catalog.list_tools()) if t.name == "query_model_data")
    request = tool.inputSchema["properties"]["request"]
    assert request["discriminator"]["propertyName"] == "kind"
    assert len(request["oneOf"]) == 6
    for schema in tool.inputSchema["$defs"].values():
        assert schema["additionalProperties"] is False
        assert all(field.get("description") for field in schema["properties"].values())
    assert tool.annotations.readOnlyHint and tool.annotations.idempotentHint
    assert not tool.annotations.destructiveHint
    assert _operation_for(tool.name) == "model_read"
    assert "data" in tool.outputSchema["properties"]
    # The cap differs only for the section endpoint.
    assert TypeAdapter(ModelQuery).validate_python({"kind": "elements", "limit": 500}).limit == 500
