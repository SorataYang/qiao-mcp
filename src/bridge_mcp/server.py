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

# Phase 4 — modify tools
from bridge_mcp.tools.modifications import register_modification_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bridge-mcp")

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
    f"connected to {provider.get_software_name()} via Bridge-MCP.\n\n"
    "## Software-Specific Rules — Read Before Using Any Tool\n"
    + provider.get_llm_instructions()
    + "\n## Available Tool Groups\n"
    "Core:     create_nodes_linear, create_beam_elements_linear, create_material, create_section\n"
    "Loads:    create_load_group, create_load_case, apply_beam_distributed_load, apply_nodal_force\n"
    "Boundary: set_support, add_elastic_link, add_master_slave_link, add_elastic_support\n"
    "Groups:   create_structure_group, create_boundary_group, add_to_group\n"
    "Stages:   add_construction_stage, configure_analysis, get_analysis_results\n"
    "Workflow: create_simple_beam_bridge, create_continuous_beam_bridge\n"
    "Queries:  get_model_summary, get_node_data, get_element_data, get_materials, get_section_list\n"
)

# ── Initialize MCP Server ─────────────────────────────────────────────

mcp = FastMCP("bridge-mcp", instructions=_SERVER_INSTRUCTIONS)

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

# ── Register Phase 4 Modification Tools ───────────────────────────────

register_modification_tools(mcp, provider)

logger.info(f"🌉 Bridge-MCP server initialized with {provider.get_software_name()} backend")


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    """Run the Bridge-MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
