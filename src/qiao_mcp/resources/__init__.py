"""
MCP Resources for bridge model data.
桥梁模型数据资源

Exposes model information as MCP Resources that LLMs can read for context.
"""

import asyncio
import json
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError

from qiao_mcp.providers import BridgeProvider


def _read_model_resource(provider: BridgeProvider, query: Callable[[], Any]) -> str:
    """Guard and read in one worker scope; failures are resource errors."""
    try:
        with ExitStack() as stack:
            context = getattr(provider, "operation_context", None)
            if callable(context):
                stack.enter_context(context("model_read"))
            else:
                guard = getattr(provider, "ensure_operation_allowed", None)
                if callable(guard):
                    guard("model_read")
            return json.dumps(query(), indent=2, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        raise ResourceError(f"Unable to read model resource: {exc}") from exc


def register_resources(mcp: MCPServer, provider: BridgeProvider):
    """Register all MCP resources."""

    @mcp.resource("bridge://model/summary")
    async def model_summary() -> str:
        """
        Current bridge model summary (当前桥梁模型概要).
        Provides node/element/material/section counts and other statistics.
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_model_summary)

    @mcp.resource("bridge://model/materials")
    async def model_materials() -> str:
        """
        List of all materials in the current model (当前模型所有材料列表).
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_material_data)

    @mcp.resource("bridge://model/sections")
    async def model_sections() -> str:
        """
        List of all section IDs in the current model (当前模型所有截面编号列表).
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_section_names)

    @mcp.resource("bridge://model/load-cases")
    async def model_load_cases() -> str:
        """
        List of all load case names in the current model (当前模型所有荷载工况名).
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_load_case_names)

    @mcp.resource("bridge://model/stages")
    async def model_stages() -> str:
        """
        List of all construction stage names (所有施工阶段名称).
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_stage_names)

    @mcp.resource("bridge://model/structure-groups")
    async def model_structure_groups() -> str:
        """
        List of all structure group names (所有结构组名称).
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_structure_group_names)

    @mcp.resource("bridge://model/boundaries")
    async def model_boundaries() -> str:
        """
        Boundary condition data in the current model (当前模型边界条件信息).
        Includes general supports, elastic links, elastic supports,
        master-slave links, and beam constraints.
        """
        return await asyncio.to_thread(_read_model_resource, provider, provider.get_boundary_data)
