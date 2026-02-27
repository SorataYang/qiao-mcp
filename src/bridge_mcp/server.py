"""
Bridge-MCP Server — MCP server for intelligent bridge structural design.
桥梁智能设计 MCP 服务器

This server exposes bridge analysis software capabilities through the
Model Context Protocol (MCP), enabling LLMs to interact with bridge
structural analysis tools.
"""

import logging

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers.qtmodel_provider import QtModelProvider
from bridge_mcp.tools import register_modeling_tools
from bridge_mcp.resources import register_resources
from bridge_mcp.prompts import register_prompts

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
        "Available tool categories:\n"
        "• Modeling (建模): create_nodes, create_elements, create_material, create_section\n"
        "• Boundary (边界): set_support\n"
        "• Loading (荷载): apply_nodal_force, apply_beam_distributed_load\n"
        "• Construction (施工): add_construction_stage\n"
        "• Analysis (分析): configure_analysis, validate_model\n"
        "• Results (结果): get_model_info, get_analysis_results\n\n"
        "Use workflow prompts to get guided design assistance."
    ),
)

# ── Initialize Provider ───────────────────────────────────────────────

provider = QtModelProvider()

if provider.is_available():
    logger.info("✅ QTModel provider loaded successfully (桥通后端加载成功)")
else:
    logger.warning(
        "⚠️  QTModel provider not available — qtmodel not installed or "
        "QiaoTong software not running. Tools will return error messages. "
        "(qtmodel 不可用，工具调用将返回错误信息)"
    )

# ── Register Tools, Resources, Prompts ────────────────────────────────

register_modeling_tools(mcp, provider)
register_resources(mcp, provider)
register_prompts(mcp)

logger.info("🌉 Bridge-MCP server initialized (桥梁MCP服务器已初始化)")


# ── Entry Point ───────────────────────────────────────────────────────

def main():
    """Run the Bridge-MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
