"""Check a built wheel over stdio without calling bridge operations.

Run with the project's installed dependencies:
    uv run python scripts/check_mcp_package.py dist/qiao_mcp-0.3.3-py3-none-any.whl
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


async def inspect_package(wheel: Path, expected_tools: int, output: Path | None) -> None:
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
            invalid = await session.call_tool("create_nodes_linear", {"count": 0})

    assert initialized.serverInfo.name == "qiao-mcp"
    assert initialized.serverInfo.version == expected_version, initialized.serverInfo
    assert initialized.instructions and "get_model_status" in initialized.instructions
    assert len(tools) == expected_tools, f"Expected {expected_tools} tools, got {len(tools)}"
    assert len(resources) == 7 and len(prompts) == 4
    parameters = [
        (tool.name, name, schema)
        for tool in tools for name, schema in tool.inputSchema.get("properties", {}).items()
    ]
    missing = [f"{tool}.{name}" for tool, name, schema in parameters if not schema.get("description")]
    assert not missing, f"Missing parameter descriptions: {missing}"
    assert all(name != "ctx" for _, name, _ in parameters), "Injected Context leaked into the schema"
    assert all(tool.annotations is not None for tool in tools), "Missing tool annotations"
    image_tools = {"save_model_screenshot", "plot_analysis_result"}
    for tool in tools:
        assert (tool.outputSchema is None) == (tool.name in image_tools), tool.name
    assert not connection.isError and connection.structuredContent
    assert connection.structuredContent["connection_status"] == "software_not_running"
    assert connection.structuredContent["connected"] is False
    assert invalid.isError, "Invalid arguments must use the MCP error channel"
    if output:
        output.write_text(json.dumps({
            "initialize": initialized.model_dump(mode="json", exclude_none=True),
            "tools": [tool.model_dump(mode="json", exclude_none=True) for tool in tools],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "version": expected_version,
        "tools": len(tools),
        "described_parameters": len(parameters),
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
    parser.add_argument("--expected-tools", type=int, default=133)
    parser.add_argument("--output", type=Path, help="Write the inspected protocol catalog as JSON")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(
        inspect_package(args.wheel.resolve(), args.expected_tools, args.output), timeout=30,
    ))
