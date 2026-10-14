"""Check a built wheel over stdio without calling bridge operations.

Run with the project's installed dependencies:
    uv run python scripts/check_mcp_package.py dist/qiao_mcp-0.5.0-py3-none-any.whl
"""

import argparse
import asyncio
import json
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def inspect_package(
    wheel: Path, expected_tools: int, output: Path | None, catalog_layout: str = "domains",
) -> None:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
    assert metadata["Name"] == "qiao-mcp", "Expected a Qiao-MCP wheel"
    expected_version = metadata["Version"]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "qiao_mcp.server"],
        env={
            "PYTHONPATH": str(wheel),
            "BRIDGE_PROVIDER": "qtmodel",
            "QIAO_MCP_CATALOG_LAYOUT": catalog_layout,
            # An explicit unused endpoint avoids discovering a real bridge session.
            "QIAOTONG_HTTP_URL": "http://localhost:1/pythonForQt/",
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = (await session.list_tools()).tools
            resources = (await session.list_resources()).resources
            prompts = (await session.list_prompts()).prompts
            connection = await session.call_tool("check_qiaotong_connection", {})
            readiness = await session.call_tool("get_model_edit_readiness", {})
            invalid_query = await session.call_tool("query_model_data", {
                "request": {"kind": "nodes", "near": [0, 0, 0]},
            })
            invalid = await session.call_tool("create_nodes_linear", {"count": 0})
            if catalog_layout == "domains":
                domain_connection = await session.call_tool("inspect_bridge", {
                    "request": {"operation": "check_qiaotong_connection"},
                })
                domain_query_error = await session.call_tool("query_model", {
                    "request": {"operation": "query_model_data", "request": {
                        "kind": "nodes", "near": [0, 0, 0],
                    }},
                })
                cross_domain_error = await session.call_tool("inspect_bridge", {
                    "request": {"operation": "initialize_model", "confirm": True},
                })
                assert not domain_connection.isError and domain_connection.structuredContent
                assert domain_connection.structuredContent["connection_status"] == "software_not_running"
                assert domain_query_error.isError and cross_domain_error.isError

    assert initialized.serverInfo.name == "qiao-mcp"
    assert initialized.serverInfo.version == expected_version, initialized.serverInfo
    assert initialized.instructions and "get_model_status" in initialized.instructions
    assert len(tools) == expected_tools, f"Expected {expected_tools} tools, got {len(tools)}"
    assert len(resources) == 7 and len(prompts) == 5
    assert "analyze_transversal" in {prompt.name for prompt in prompts}
    parameters = [
        (tool.name, name, schema)
        for tool in tools for name, schema in tool.inputSchema.get("properties", {}).items()
    ]
    missing = [f"{tool}.{name}" for tool, name, schema in parameters if not schema.get("description")]
    assert not missing, f"Missing parameter descriptions: {missing}"
    assert all(name != "ctx" for _, name, _ in parameters), "Injected Context leaked into the schema"
    assert all(tool.annotations is not None for tool in tools), "Missing tool annotations"
    image_tools = {"view_model"} if catalog_layout == "domains" else {"save_model_screenshot", "plot_analysis_result"}
    for tool in tools:
        assert (tool.outputSchema is None) == (tool.name in image_tools), tool.name
    assert not connection.isError and connection.structuredContent
    assert connection.structuredContent["connection_status"] == "software_not_running"
    assert connection.structuredContent["connected"] is False
    assert not readiness.isError and readiness.structuredContent
    assert readiness.structuredContent["status"] in {"not_connected", "api_unavailable"}
    assert invalid_query.isError, "Invalid nested query inputs must use the MCP error channel"
    assert invalid.isError, "Invalid arguments must use the MCP error channel"
    operations = [tool.name for tool in tools]
    operation_parameters = len(parameters)
    if catalog_layout == "domains":
        operations = []
        operation_parameters = 0
        for tool in tools:
            schema = tool.inputSchema
            branches = schema["properties"]["request"]["discriminator"]["mapping"]
            operations.extend(branches)
            for ref in branches.values():
                properties = schema["$defs"][ref.rsplit("/", 1)[1]]["properties"]
                assert "ctx" not in properties
                assert all(prop.get("description") for prop in properties.values())
                operation_parameters += len(properties) - 1
    assert len(operations) == len(set(operations)) == 153, "The complete operation catalog must be preserved"
    if output:
        output.write_text(json.dumps({
            "catalog_layout": catalog_layout,
            "operations": operations,
            "initialize": initialized.model_dump(mode="json", exclude_none=True),
            "tools": [tool.model_dump(mode="json", exclude_none=True) for tool in tools],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": expected_version,
        "catalog_layout": catalog_layout,
        "tools": len(tools),
        "operations": len(operations),
        "described_parameters": len(parameters),
        "operation_parameters": operation_parameters,
        "resources": len(resources),
        "prompts": len(prompts),
        "instructions": True,
        "output_schemas": sum(tool.outputSchema is not None for tool in tools),
        "structured_response": True,
        "invalid_input_is_error": True,
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--expected-tools", type=int)
    parser.add_argument("--catalog-layout", choices=("domains", "flat"), default="domains")
    parser.add_argument("--output", type=Path, help="Write the inspected protocol catalog as JSON")
    args = parser.parse_args()
    expected_tools = args.expected_tools if args.expected_tools is not None else (15 if args.catalog_layout == "domains" else 153)
    asyncio.run(asyncio.wait_for(
        inspect_package(args.wheel.resolve(), expected_tools, args.output, args.catalog_layout), timeout=30,
    ))
