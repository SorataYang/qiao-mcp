"""On-demand discovery reduces initial payload while keeping every operation usable."""

import asyncio
import json
from unittest.mock import Mock

import pytest
from conftest import PNG_BYTES
from mcp.types import ImageContent

from qiao_mcp.domain_server import DomainFastMCP
from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import ToolError


@pytest.fixture
def server(fake_provider):
    server = DomainFastMCP("discovery")
    register_tool_catalog(server, fake_provider)
    return server


def call(server, tool_name, **arguments):
    return asyncio.run(server.call_tool(tool_name, arguments))


def test_initial_catalog_is_small_and_complete_catalog_is_reachable(server, fake_provider):
    fake_provider.ensure_operation_allowed = Mock(side_effect=AssertionError("discovery contacted desktop"))
    compact = asyncio.run(server.list_tools())
    size = len(json.dumps([t.model_dump(mode="json") for t in compact]).encode())
    server.catalog_layout = "flat"
    flat = asyncio.run(server.list_tools())
    original_size = len(json.dumps([t.model_dump(mode="json") for t in flat]).encode())
    assert size < original_size * 0.1
    names = []
    offset = 0
    while True:
        page = call(server, "search_operations", offset=offset, limit=50)[1]
        names.extend(item["operation"] for item in page["items"])
        offset = page["next_offset"]
        if offset is None:
            break
    assert set(names) == {tool.name for tool in flat}
    assert len(names) == len(set(names))
    for tool in flat:
        details = call(server, "get_operation_schema", operation=tool.name)[1]
        assert details["inputSchema"] == tool.inputSchema
        assert details["outputSchema"] == tool.outputSchema
    fake_provider.ensure_operation_allowed.assert_not_called()


@pytest.mark.parametrize("query,expected", [
    ("run_concrete_check", "run_concrete_check"), ("节点", "create_nodes"),
    ("截面", "create_section"), ("self weight", "set_self_weight_stage"),
])
def test_english_and_chinese_search(server, query, expected):
    matches = call(server, "search_operations", query=query, limit=50)[1]["items"]
    assert expected in [item["operation"] for item in matches]


def test_execution_preserves_handler_and_guard(server, fake_provider):
    fake_provider.add_load_case = Mock()
    arguments = {"name": "L", "case_type": "恒载"}
    direct = call(server, "create_load_case", **arguments)
    fake_provider.add_load_case.reset_mock()
    result = call(server, "execute_operation", operation="create_load_case", arguments=arguments)
    assert result == direct
    fake_provider.add_load_case.assert_called_once()
    fake_provider.ensure_operation_allowed = Mock(side_effect=ToolError("blocked"))
    with pytest.raises(ToolError, match="blocked"):
        call(server, "execute_operation", operation="create_load_case", arguments=arguments)


@pytest.mark.parametrize("arguments", [{"bogus": 1}, {"node_data": [["invalid", 0, 0]]}])
def test_invalid_execution_never_reaches_provider(server, fake_provider, arguments):
    fake_provider.ensure_operation_allowed = Mock()
    with pytest.raises(ToolError):
        call(server, "execute_operation", operation="create_nodes", arguments=arguments)
    fake_provider.ensure_operation_allowed.assert_not_called()


def test_unknown_operation_and_domain_are_explicit(server):
    for name, arguments in [
        ("get_operation_schema", {"operation": "absent"}),
        ("search_operations", {"domain": "absent"}),
        ("execute_operation", {"operation": "execute_operation", "arguments": {}}),
    ]:
        with pytest.raises(ToolError):
            call(server, name, **arguments)


def test_discovered_image_retains_content_type(server, fake_provider, tmp_path):
    target = tmp_path / "model.png"
    fake_provider.save_model_image = lambda file_path: target.write_bytes(PNG_BYTES)
    result = call(server, "execute_operation", operation="save_model_screenshot", arguments={
        "file_path": str(target), "view_angle": "current", "return_image": True,
    })
    assert any(isinstance(item, ImageContent) for item in result)
