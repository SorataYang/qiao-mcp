"""
Bridge-MCP Server — MCP server for intelligent bridge structural design.
桥梁智能设计 MCP 服务器

This server exposes bridge analysis software capabilities through the
Model Context Protocol (MCP), enabling LLMs to interact with bridge
structural analysis tools.
"""

import sys
import logging

# Ensure stdout/stderr use UTF-8 to prevent Mojibake in Node.js (MCP Inspector) under Windows
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers.qtmodel_provider import QtModelProvider

# Phase 1 modules
from bridge_mcp.tools import register_modeling_tools
from bridge_mcp.resources import register_resources
from bridge_mcp.prompts import register_prompts

# Phase 2 modules
from bridge_mcp.tools.group_management import register_group_tools
from bridge_mcp.tools.tendon import register_tendon_tools
from bridge_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from bridge_mcp.tools.visualization import register_visualization_tools
from bridge_mcp.tools.moving_load import register_moving_load_tools
from bridge_mcp.tools.checking import register_checking_tools
from bridge_mcp.tools.workflows import register_workflow_tools

# Phase 3 — read-only query tools
from bridge_mcp.tools.queries import register_query_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bridge-mcp")

# ── Initialize MCP Server ─────────────────────────────────────────────

mcp = FastMCP(
    "bridge-mcp",
    instructions=(
        "Bridge-MCP is an MCP server for intelligent bridge structural design "
        "and analysis. It provides tools to create bridge models, apply loads, "
        "run structural analysis, and review results through the QiaoTong (桥通) "
        "bridge analysis software.\n\n"
        "桥梁智能设计 MCP 服务器，通过桥通软件进行桥梁结构建模、分析和检算。\n\n"
        "Phase 1 tools — Core modeling (核心建模):\n"
        "  create_nodes, create_elements, create_material, create_section,\n"
        "  set_support, apply_nodal_force, apply_beam_distributed_load,\n"
        "  add_construction_stage, configure_analysis, validate_model,\n"
        "  get_model_info, get_analysis_results\n\n"
        "Phase 2 tools — Advanced features (高级功能):\n"
        "  Groups: create_structure_group, create_boundary_group, create_load_group,\n"
        "          list_group_members, add_elements_to_group, merge_operation_stage\n"
        "  Tendon: create_tendon_property, create_tendon_2d, apply_prestress, get_tendon_info\n"
        "  Boundary: add_elastic_link, add_master_slave_link, add_elastic_support\n"
        "  Viz: save_model_screenshot, plot_analysis_result, set_view_angle\n"
        "  Loads: add_standard_vehicle, add_traffic_lane, create_live_load_case,\n"
        "         get_live_load_results\n"
        "  Check: setup_concrete_check, add_check_load_combination,\n"
        "         run_concrete_check, add_parametric_reinforcement\n"
        "  Workflow: create_simple_beam_bridge, create_continuous_beam_bridge\n\n"
        "Use workflow prompts to get guided design assistance."
    ),
)

# ── Initialize Provider ───────────────────────────────────────────────

provider = QtModelProvider()

if provider.is_available():
    logger.info("✅ QTModel provider loaded successfully (桥通后端加载成功)")
else:
    logger.warning(
        f"⚠️  QTModel provider not available — {provider._unavailable_reason}"
    )

# ── Register Phase 1 Tools, Resources, Prompts ────────────────────────

register_modeling_tools(mcp, provider)
register_resources(mcp, provider)
register_prompts(mcp)

# ── Register Phase 2 Tools ────────────────────────────────────────────

register_group_tools(mcp, provider)
register_tendon_tools(mcp, provider)
register_advanced_boundary_tools(mcp, provider)
register_visualization_tools(mcp, provider)
register_moving_load_tools(mcp, provider)
register_checking_tools(mcp, provider)
register_workflow_tools(mcp, provider)

# ── Register Phase 3 Query Tools ──────────────────────────────────────

register_query_tools(mcp, provider)

logger.info("🌉 Bridge-MCP server initialized (桥梁MCP服务器已初始化)")


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    """Run the Bridge-MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
