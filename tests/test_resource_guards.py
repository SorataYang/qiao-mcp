"""All resource paths apply the same read guard and propagate protocol errors."""

import asyncio
import json
import threading

import pytest
from mcp.server.mcpserver.exceptions import ResourceError

from qiao_mcp.registration import OperationServer as MCPServer
from qiao_mcp.resources import register_resources

RESOURCES = {
    "summary": "get_model_summary", "materials": "get_material_data",
    "sections": "get_section_names", "load-cases": "get_load_case_names",
    "stages": "get_stage_names", "structure-groups": "get_structure_group_names",
    "boundaries": "get_boundary_data",
}


@pytest.mark.parametrize("path,method", RESOURCES.items())
@pytest.mark.parametrize("outcome", ["blocked", "failed", "empty"])
def test_resources_are_guarded_and_errors_are_not_data(fake_provider, path, method, outcome):
    calls = []

    def guard(operation):
        calls.append(operation)
        if outcome == "blocked":
            raise RuntimeError("read permission denied")

    def query():
        calls.append("query")
        if outcome == "failed":
            raise ConnectionError("desktop disconnected")
        return []

    fake_provider.ensure_operation_allowed = guard
    setattr(fake_provider, method, query)
    server = MCPServer("resources")
    register_resources(server, fake_provider)
    if outcome == "empty":
        results = list(asyncio.run(server.read_resource(f"bridge://model/{path}")))
        assert json.loads(results[0].content) == []
    else:
        with pytest.raises(ResourceError, match="permission denied|desktop disconnected"):
            asyncio.run(server.read_resource(f"bridge://model/{path}"))
    assert calls == (["model_read"] if outcome == "blocked" else ["model_read", "query"])


def test_resource_guard_and_query_do_not_block_event_loop(fake_provider):
    entered = threading.Event()
    release = threading.Event()

    def query():
        entered.set()
        assert release.wait(2)
        return []

    fake_provider.get_material_data = query
    server = MCPServer("resources")
    register_resources(server, fake_provider)

    async def scenario():
        read = asyncio.create_task(server.read_resource("bridge://model/materials"))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.005)
            assert entered.is_set()
        finally:
            release.set()
        await read

    asyncio.run(scenario())
