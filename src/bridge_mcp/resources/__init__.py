"""
MCP Resources for bridge model data.
桥梁模型数据资源

Exposes model information as MCP Resources that LLMs can read for context.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_resources(mcp: FastMCP, provider: BridgeProvider):
    """Register all MCP resources."""

    @mcp.resource("bridge://model/summary")
    def model_summary() -> str:
        """
        Current bridge model summary (当前桥梁模型概要).
        Provides node/element/material/section counts and other statistics.
        """
        try:
            summary = provider.get_model_summary()
            return json.dumps(summary, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/materials")
    def model_materials() -> str:
        """
        List of all materials in the current model (当前模型所有材料列表).
        """
        try:
            materials = provider.get_material_data()
            return json.dumps(materials, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/sections")
    def model_sections() -> str:
        """
        List of all section IDs in the current model (当前模型所有截面编号列表).
        """
        try:
            sections = provider.get_section_names()
            return json.dumps(sections, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/load-cases")
    def model_load_cases() -> str:
        """
        List of all load case names in the current model (当前模型所有荷载工况名).
        """
        try:
            cases = provider.get_load_case_names()
            return json.dumps(cases, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/stages")
    def model_stages() -> str:
        """
        List of all construction stage names (所有施工阶段名称).
        """
        try:
            stages = provider.get_stage_names()
            return json.dumps(stages, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/structure-groups")
    def model_structure_groups() -> str:
        """
        List of all structure group names (所有结构组名称).
        """
        try:
            groups = provider.get_structure_group_names()
            return json.dumps(groups, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.resource("bridge://model/boundaries")
    def model_boundaries() -> str:
        """
        Boundary condition data in the current model (当前模型边界条件信息).
        Includes general supports, elastic links, elastic supports,
        master-slave links, and beam constraints.
        """
        try:
            boundary_data = provider.get_boundary_data()
            return json.dumps(boundary_data, indent=2, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
