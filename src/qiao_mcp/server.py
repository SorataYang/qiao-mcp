"""
Qiao-MCP Server — MCP server for intelligent bridge structural design.
桥梁智能设计 MCP 服务器

This server exposes bridge analysis software capabilities through the
Model Context Protocol (MCP), enabling LLMs to interact with bridge
structural analysis tools.
"""

import logging
import sys

# Ensure stdout/stderr use UTF-8 to prevent Mojibake in Node.js (MCP Inspector) under Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from mcp.server.fastmcp import FastMCP

from qiao_mcp.prompts import register_prompts
from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.resources import register_resources

# Phase 1 modules
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools

# Phase 5 — long-tail API gateway (逃生舱)
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.checking import register_checking_tools

# Structured-return envelope for all tool registrations
from qiao_mcp.tools.envelope import register_tools_with_envelope

# Phase 2 modules
from qiao_mcp.tools.group_management import register_group_tools

# Phase 4 — modify tools
from qiao_mcp.tools.modifications import register_modification_tools
from qiao_mcp.tools.moving_load import register_moving_load_tools

# Phase 3 — read-only query tools
from qiao_mcp.tools.queries import register_query_tools
from qiao_mcp.tools.tendon import register_tendon_tools
from qiao_mcp.tools.visualization import register_visualization_tools
from qiao_mcp.tools.workflows import register_workflow_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qiao-mcp")

# ── Initialize Provider first (needed to build dynamic instructions) ──

provider = QtModelProvider()

if provider.is_available():
    logger.info(f"✅ {provider.get_software_name()} provider loaded successfully")
else:
    logger.warning(
        f"⚠️  {provider.get_software_name()} provider not available — {provider._unavailable_reason}"
    )

# ── Build MCP instructions dynamically from the active provider ───────

_SERVER_INSTRUCTIONS = (
    f"You are an AI assistant for bridge structural design "
    f"connected to {provider.get_software_name()} via Qiao-MCP.\n\n"
    "## Software-Specific Rules — Read Before Using Any Tool\n"
    + provider.get_llm_instructions()
    + "\n## Available Tool Groups\n"
    "Core:     create_nodes_linear, create_nodes, create_elements, create_material, create_section (全部参数化截面类型), create_polygon_section, create_line_width_section, create_section_from_properties\n"
    "Loads:    create_load_group, create_load_case, set_self_weight_stage, set_gravity, apply_nodal_force, apply_beam_distributed_load, add_system_temperature, add_gradient_temperature, add_support_settlement\n"
    "Boundary: set_support, add_elastic_link, add_master_slave_link, add_elastic_support\n"
    "Groups:   create_structure_group, update_structure_group_name, remove_structure_group, create_boundary_group, add_to_structure_group, remove_from_structure_group, list_group_members\n"
    "Stages:   add_construction_stage, merge_operation_stage, configure_analysis, run_analysis, get_analysis_results, plot_analysis_result\n"
    "Workflow: create_simple_beam_bridge, create_continuous_beam_bridge\n"
    "Queries:  get_model_info, get_model_data(kind=nodes|elements|materials|sections|load_cases|stages|structure_groups|...), find_entities, calc_section_property, get_special_results\n"
    "Tendons:  create_tendon_property, create_tendon_2d, apply_prestress, get_tendon_info\n"
    "Traffic:  add_node_tandem, add_influence_plane, add_traffic_lane, add_standard_vehicle, create_live_load_case, get_live_load_results\n"
    "Checking: setup_concrete_check, add_check_load_combination, add_parametric_reinforcement, run_concrete_check\n"
    "Modify:   update_node, update_node_id, renumber_nodes, move_nodes, merge_nodes, remove_nodes, update_element, update_element_id, renumber_elements, revert_local_orientation, remove_elements\n"
    "View:     set_view_angle, save_model_screenshot\n"
    "Gateway:  list_qtmodel_api, call_qtmodel_api — 长尾 API 先检索真实签名再调用\n"
)

# ── Initialize MCP Server ─────────────────────────────────────────────

mcp = FastMCP("qiao-mcp", instructions=_SERVER_INSTRUCTIONS)

# ── Register Tools (wrapped with the structured-return envelope) ──────
# 所有工具注册统一经 envelope 包装：成功返回结构化 dict，失败抛 ToolError。

_TOOL_REGISTRARS = [
    register_modeling_tools,       # Phase 1
    register_group_tools,          # Phase 2
    register_tendon_tools,
    register_advanced_boundary_tools,
    register_visualization_tools,
    register_moving_load_tools,
    register_checking_tools,
    register_workflow_tools,
    register_query_tools,          # Phase 3
    register_modification_tools,   # Phase 4
    register_api_gateway_tools,    # Phase 5 (逃生舱)
]

for _registrar in _TOOL_REGISTRARS:
    register_tools_with_envelope(mcp, _registrar, provider)

# Resources 与 Prompts 不经工具包装
register_resources(mcp, provider)
register_prompts(mcp)

logger.info(f"🌉 Qiao-MCP server initialized with {provider.get_software_name()} backend")


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    """Run the Qiao-MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
