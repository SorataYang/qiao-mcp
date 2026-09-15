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

from qiao_mcp import __version__
from qiao_mcp.prompts import register_prompts
from qiao_mcp.providers import PROVIDER_ENV, create_provider
from qiao_mcp.resources import register_resources
from qiao_mcp.tools.catalog import register_tool_catalog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qiao-mcp")

# ── Initialize Provider first (needed to build dynamic instructions) ──

# 后端由 BRIDGE_PROVIDER 选择（默认 qtmodel）。构造失败直接向上抛：
# 选错后端时启动失败远好于连上另一套软件、事后才在建模结果里暴露。
provider = create_provider()

# Catalog inspection must not wait for HTTP discovery or a desktop application.
# Connection probes happen in the diagnostic tools and guarded operations.
logger.info(
    "Initialized %s adapter (%s=%s); use check_qiaotong_connection to check connectivity",
    provider.get_software_name(), PROVIDER_ENV, provider.name,
)
if reason := provider.unavailable_reason():
    logger.warning("Backend adapter diagnostic: %s", reason)

# ── Build MCP instructions dynamically from the active provider ───────

_SERVER_INSTRUCTIONS = (
    f"You are an AI assistant for bridge structural design "
    f"using {provider.get_software_name()} via Qiao-MCP.\n"
    "Start with check_qiaotong_connection; use get_model_status to confirm the "
    "model and allowed operations before making changes.\n\n"
    "## Software-Specific Rules — Read Before Using Any Tool\n"
    + provider.get_llm_instructions()
    + "\n## Available Tool Groups\n"
    "Core:     create_nodes_linear, create_nodes, create_elements, create_material, create_section (全部参数化截面类型), create_polygon_section, create_line_width_section, create_section_from_properties\n"
    "Loads:    create_load_group, create_load_case, set_self_weight_stage, set_gravity, apply_nodal_force, apply_beam_distributed_load, add_system_temperature, add_gradient_temperature, add_support_settlement\n"
    "Boundary: set_support, add_elastic_link, add_master_slave_link, add_elastic_support\n"
    "Groups:   create_structure_group, update_structure_group_name, remove_structure_group, create_boundary_group, add_to_structure_group, remove_from_structure_group, list_group_members\n"
    "Stages:   add_construction_stage, merge_operation_stage, configure_analysis, run_analysis, get_analysis_results, plot_analysis_result\n"
    "Workflow: create_simple_beam_bridge, create_continuous_beam_bridge\n"
    "Queries:  get_model_info, get_model_data(kind=nodes|elements|materials|sections|load_cases|stages|structure_groups|summary|analysis_context|project_metadata|check_context|structure_group_summaries|...), find_entities, calc_section_property, get_special_results\n"
    "Tendons:  create_tendon_property, create_tendon_2d, apply_prestress, get_tendon_info\n"
    "Traffic:  add_node_tandem, add_influence_plane, add_traffic_lane, add_standard_vehicle, create_live_load_case, get_live_load_results\n"
    "Checking: setup_concrete_check, add_check_load_combination, add_parametric_reinforcement, run_concrete_check, get_check_data(kind=stress|materials|stirrups|reinforcement|*_setting|...), configure_check_analysis(kind=crack_width|limit_state|normal_stress|...), add_check_stirrup, manage_check_stirrup, assign_element_stirrup, update_vertical_steel_tendon, manage_check_case_file\n"
    "Modify:   update_node, update_node_id, renumber_nodes, move_nodes, merge_nodes, remove_nodes, update_element, update_element_id, renumber_elements, revert_local_orientation, remove_elements\n"
    "View:     set_view_angle, save_model_screenshot\n"
    "Gateway:  list_qtmodel_api, call_qtmodel_api — 长尾 API 先检索真实签名再调用\n"
    "State:    get_model_status — 在建模或修改前确认模型是否打开、当前处于前/后处理或求解阶段、是否为基本阶段以及当前允许的操作\n"
)

# ── Initialize MCP Server ─────────────────────────────────────────────

mcp = FastMCP("qiao-mcp", instructions=_SERVER_INSTRUCTIONS)
# FastMCP 1.x otherwise reports the MCP SDK version in initialize.serverInfo.
# Catalogs need the installed server version to identify a fresh inspection.
mcp._mcp_server.version = __version__

# ── Register Tools (wrapped with the structured-return envelope) ──────
# 所有工具注册统一经 envelope 包装：成功返回结构化 dict，失败抛 ToolError。

register_tool_catalog(mcp, provider)

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
