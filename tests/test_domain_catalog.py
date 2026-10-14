"""Domain discovery and dispatch must preserve the complete operation contract."""

import asyncio
import base64
import threading
import time
from unittest.mock import AsyncMock, Mock

import jsonschema
import pytest
from conftest import PNG_BYTES
from mcp.types import ImageContent

from qiao_mcp.domain_server import DomainFastMCP
from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.domains import TOOL_DOMAINS
from qiao_mcp.tools.envelope import ToolError


@pytest.fixture
def domain_server(fake_provider):
    server = DomainFastMCP("domain-test")
    register_tool_catalog(server, fake_provider)
    return server


def _call(server, domain, operation, **fields):
    return asyncio.run(server.call_tool(domain, {"request": {"operation": operation, **fields}}))


def test_default_catalog_covers_every_registered_operation_once(domain_server):
    domains = asyncio.run(domain_server.list_tools())
    operations = {tool.name: tool for tool in domain_server._tool_manager.list_tools()}
    assert len(domains) == 15 and len(operations) == 153
    seen = []
    for domain in domains:
        schema = domain.inputSchema
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False
        request = schema["properties"]["request"]
        assert request["description"]
        for name, ref in request["discriminator"]["mapping"].items():
            seen.append(name)
            variant = schema["$defs"][ref.rsplit("/", 1)[1]]
            original = operations[name].parameters
            assert set(variant["properties"]) == set(original["properties"]) | {"operation"}
            assert set(variant["required"]) == set(original.get("required", [])) | {"operation"}
            assert variant["additionalProperties"] is False
            assert "ctx" not in variant["properties"]
            for field, info in original["properties"].items():
                advertised = variant["properties"][field]
                assert advertised.get("description") == info.get("description")
                assert ("default" in advertised) == ("default" in info)
                assert advertised.get("default") == info.get("default")
        if domain.name == "view_model":
            assert domain.outputSchema is None  # Supports MCP image content.
        else:
            assert domain.outputSchema["type"] == "object"
            jsonschema.Draft202012Validator.check_schema(domain.outputSchema)
    assert len(seen) == len(set(seen)) and set(seen) == set(operations)


def test_flat_layout_exposes_all_legacy_tools(fake_provider):
    server = DomainFastMCP("flat-test", catalog_layout="flat")
    register_tool_catalog(server, fake_provider)
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {tool.name for tool in server._tool_manager.list_tools()}
    assert len(tools) == 153


def test_unknown_layout_fails_explicitly():
    with pytest.raises(ValueError, match="QIAO_MCP_CATALOG_LAYOUT"):
        DomainFastMCP("invalid", catalog_layout="partial")


def test_adding_unassigned_operation_cannot_silently_hide_it(domain_server):
    asyncio.run(domain_server.list_tools())  # Populate the cache first.

    @domain_server.tool()
    def unrelated_operation() -> str:
        return "unused"

    with pytest.raises(ValueError, match="unassigned=.*unrelated_operation"):
        asyncio.run(domain_server.list_tools())


@pytest.mark.parametrize("domain,operation,fields", [
    ("edit_loads", "create_load_case", {"name": "L", "case_type": "恒载"}),
    ("edit_geometry", "create_nodes", {"node_data": [[0, 0, 0], [3, 0, 0]], "is_merged": False}),
    ("edit_geometry", "move_nodes", {"ids": "1to3", "offset_x": 2}),
    ("view_model", "set_render", {"flag": False}),
    ("manage_checks", "manage_check_stirrup", {"action": "remove", "stirrup_id": 7}),
])
def test_domain_and_legacy_calls_have_identical_effects_and_responses(
    domain_server, fake_provider, domain, operation, fields,
):
    legacy = asyncio.run(domain_server.call_tool(operation, fields))
    databases = (fake_provider._mdb, fake_provider._odb, fake_provider._cdb)
    expected = [list(db.calls) for db in databases]
    for db in databases:
        db.calls.clear()
    grouped = _call(domain_server, domain, operation, **fields)
    assert grouped == legacy
    assert [db.calls for db in databases] == expected


@pytest.mark.parametrize("arguments", [
    {},
    {"request": {"operation": "remove_nodes", "ids": [1]}},
    {"request": {"operation": "get_model_info", "node_ids": [1]}},
    {"request": {"operation": "query_model_data", "request": {"kind": "nodes", "near": [0, 0, 0]}}},
    {"request": {"operation": "get_model_info"}, "extra": True},
])
def test_invalid_or_cross_domain_requests_fail_before_provider(domain_server, fake_provider, arguments):
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError, match="Invalid request for query_model"):
        asyncio.run(domain_server.call_tool("query_model", arguments))
    fake_provider.ensure_operation_allowed.assert_not_called()
    assert not fake_provider._mdb.calls


def test_grouped_write_preserves_original_operation_guard(domain_server, fake_provider):
    fake_provider.ensure_operation_allowed = Mock(side_effect=ToolError("model not editable"))
    with pytest.raises(ToolError, match="model not editable"):
        _call(domain_server, "edit_geometry", "move_nodes", ids=[1], offset_x=1)
    fake_provider.ensure_operation_allowed.assert_called_once_with("model_write")
    assert not fake_provider._mdb.calls


def test_nested_query_keeps_native_filters_and_structured_page(domain_server, fake_provider):
    page = {"items": [{"id": 1}], "has_more": True, "offset": 0, "limit": 2}
    fake_provider.query_model_data = Mock(return_value=page)
    result = _call(
        domain_server, "query_model", "query_model_data",
        request={"kind": "nodes", "node_ids": [1, 2], "limit": 2},
    )
    fake_provider.query_model_data.assert_called_once_with("nodes", node_ids=[1, 2], offset=0, limit=2)
    assert result[1] == {"status": "success", "data": page}


@pytest.mark.parametrize("fields,expected", [
    ({}, {}),
    ({"sub_steps": None}, {}),
    ({"sub_steps": []}, {"sub_steps": []}),
    ({"sub_steps": [0.5]}, {"sub_steps": [0.5]}),
])
def test_omitted_null_and_empty_values_keep_operation_semantics(domain_server, fake_provider, fields, expected):
    fake_provider.update_construction_stage = Mock()
    _call(domain_server, "edit_construction", "update_construction_stage", name="S", **fields)
    fake_provider.update_construction_stage.assert_called_once_with(
        name="S", new_name="", duration=0, **expected,
    )


def test_lost_reply_is_still_an_unknown_outcome(domain_server, fake_provider):
    class CommandOutcomeUnknownError(RuntimeError):
        pass

    fake_provider.add_load_case = Mock(side_effect=CommandOutcomeUnknownError("reply lost"))
    with pytest.raises(ToolError, match="OUTCOME UNKNOWN.*Do NOT retry"):
        _call(domain_server, "edit_loads", "create_load_case", name="L")
    fake_provider.add_load_case.assert_called_once()


def test_image_content_survives_domain_dispatch(domain_server, fake_provider, tmp_path):
    target = tmp_path / "model.png"
    fake_provider.save_model_image = lambda file_path: target.write_bytes(PNG_BYTES)
    result = _call(
        domain_server, "view_model", "save_model_screenshot",
        file_path=str(target), view_angle="current", return_image=True,
    )
    image = next(item for item in result if isinstance(item, ImageContent))
    assert base64.b64decode(image.data) == PNG_BYTES
    assert target.read_bytes() == PNG_BYTES


def test_domain_solve_keeps_context_progress_and_background_execution(domain_server, fake_provider, monkeypatch):
    context = Mock(report_progress=AsyncMock())
    monkeypatch.setattr(domain_server, "get_context", lambda: context)
    solve_threads = []

    def solve(**kwargs):
        solve_threads.append(threading.current_thread().ident)
        time.sleep(0.06)
        return {"state": "succeeded", "is_running": False}

    fake_provider.run_analysis = solve
    real_wait = asyncio.wait

    async def short_heartbeat(futures, timeout):
        return await real_wait(futures, timeout=0.01)

    monkeypatch.setattr(asyncio, "wait", short_heartbeat)
    result = _call(domain_server, "analyze_model", "run_analysis", read_timeout=60)
    assert result[1]["status"] == "success"
    assert len(solve_threads) == 1
    assert solve_threads[0] != threading.current_thread().ident
    assert context.report_progress.await_count > 0


def test_domain_annotations_distinguish_diagnostics_from_writes(domain_server):
    domains = {tool.name: tool for tool in asyncio.run(domain_server.list_tools())}
    for name in ("inspect_bridge", "query_model", "query_results"):
        assert domains[name].annotations.readOnlyHint is True
        assert domains[name].annotations.destructiveHint is False
    assert domains["edit_geometry"].annotations.destructiveHint is True
    assert domains["access_backend"].annotations.openWorldHint is True
    assert {domain.name for domain in TOOL_DOMAINS} == set(domains)
