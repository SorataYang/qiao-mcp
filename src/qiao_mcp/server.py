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
    "Live-load configuration: configure_live_load_system (clearing is opt-in), configure_operation_stage (all four case lists required; [] disables a family); defining loads never implicitly runs analysis\n"
    "Transversal: set_transversal_vehicle, set_transversal_lane, set_transversal_case, get_transversal_data, remove_transversal_data — complete definitions in fixed kN/m; read back actual IDs; lane distribution_widths are meters, node order is preserved; deleting requires an explicit target\n"
    "Result identifiers: get_analysis_results defaults to static ST: naming; use case_name_mode=full only with a complete identifier verified from QiaoTong results/UI, never guess prefixes from TV/MV combination codes. Prompt analyze_transversal guides the sequence.\n"
    "Model reinforcement snapshots: set_section_reinforcement, remove_section_reinforcement — use complete UI-exported model definitions and identifiers; model-write permission and one commit; current CSAN queries are not lossless model snapshots\n"
    "Model stirrups: set_check_stirrup_snapshot (original_id required to renumber), set_element_stirrups (None preserves a family, [] clears it; shear rows have 5 entries, torsion rows 3); legacy CSAN tools remain separate\n"
    "Model checking definitions: manage_check_material(set/reset), manage_check_case_definition(set/remove) for concrete/seismic/strengthening; full exported snapshots use native enums/units, run_concrete_check only imports and solves concrete cases\n"
    "SDK availability: listed methods still require desktop routes. qtmodel 2.9.3 rejects historical model-check snapshot and planned-lane add/update routes with API_NOT_OPEN; Qiao-MCP preserves that error without committing.\n"
    "International vehicles: set_international_vehicle(request discriminated by AASHTO/BS/EN1991), get_international_live_load_data(vehicles/cases). Select the matching system explicitly. Full replacements reset omitted scalars to new defaults; axle units are AASHTO N,m and EN1991 kN,m. BS axle units are unspecified by the SDK: preserve verified native exports without scaling. AASHTO r uses percent. Writes commit once and read back the exact name/actual ID.\n"
    "International workflow: create_en1991_vehicle(source standard/user) requires an explicit name; standard factory omits ineffective compatibility options, user factory retains axle/HSLM controls. set_planned_lane is distinct from add_traffic_lane(optimize=True), with model-unit lengths and export/UI verification (no getter); gateway removal requires lane_kind=planned. set_international_live_load_case checks vehicle names/standards, EN1991 duplicate lanes, and full native factors; QiaoTong checks lane/plane references. Explicitly configure operating live_load_cases, then run_analysis and use verified full result identifiers.\n"
    "Checking: setup_concrete_check, add_check_load_combination, add_parametric_reinforcement, run_concrete_check, get_check_data(kind=stress|materials|stirrups|reinforcement|*_setting|...), configure_check_analysis(kind=crack_width|limit_state|normal_stress|...), add_check_stirrup, manage_check_stirrup, assign_element_stirrup, update_vertical_steel_tendon, manage_check_case_file\n"
    "Modify:   update_node, update_node_id, renumber_nodes, move_nodes, merge_nodes, remove_nodes, update_element, update_element_id, renumber_elements, revert_local_orientation, remove_elements\n"
    "B1 queries: query_model_data(request={kind: nodes|elements|boundaries|loads|node_local_axes|section_summaries, ...}) — typed server-side filters/pages; get_model_data adds *_summaries, material_detail, load_case_detail, load_combination_detail, element_section and spans\n"
    "Edit readiness: get_model_edit_readiness — read-only diagnostics even when model operations are blocked; never automatically prepare edits, switch stages or delete results\n"
    "View:     set_view_angle, save_model_screenshot\n"
    "Gateway:  list_qtmodel_api, call_qtmodel_api — 长尾 API 先检索真实签名再调用\n"
    "State:    get_model_status — 在建模或修改前确认模型是否打开、当前处于前/后处理或求解阶段、是否为基本阶段以及当前允许的操作\n"
    "\n## Choosing Similar Tools\n"
    "Section properties: calc_section_property evaluates supplied geometry; get_model_data(kind=section_property, sec_id=...) reads a stored section; calculate_section_property rewrites properties for all existing sections.\n"
    "Group members: prefer add_to_structure_group for nodes/elements; add_elements_to_group is its element-only convenience tool. remove_from_structure_group removes memberships; remove_structure_group removes the group.\n"
    "Node edits: update_node sets absolute values and reads current coordinates when any component is omitted; update_node_id changes only one ID without that read; move_nodes adds relative offsets on each call. Renumbering requires both equal-length, unique ID lists for a local mapping; only omitting BOTH lists renumbers the entire model. A single omitted list or a blank selection is rejected.\n"
    "Stage views: switch_display_stage selects the modeling view by stage name; change_construct_stage selects the results view by integer stage index. Neither starts analysis.\n"
    "Element edits: update_element reads the unique target to fill omitted properties; missing applicable fields prevent writing. SDK query objects may themselves fill absent backend fields with defaults, so use targeted updates if the original record cannot be verified. Its node_i/node_j must be supplied together. update_element_id/material/section/beta/nodes target one property without rebuilding the record; material/section/beta accept batches. Reconnect plates through mdb.update_element_node with the complete node list.\n"
    "Tendons: get_tendon_info reads saved definitions; get_tendon_loss_results requires solved, activated construction-stage data; get_tendon_position_result reads discretized global coordinates with bridge-dependent pre-solve availability.\n"
    "Temperature: add_system_temperature calls the selected-element temperature API (SDK says final temperature, no automatic ΔT conversion); add_gradient_temperature uses a linear difference; add_beam_section_temperature uses code parameters; add_custom_temperature uses [top/bottom reference, height, temperature] rows with orientation 1=local Z and 2=local Y.\n"
    "Cable and tendon loads: add_initial_tension_load controls axial-force input; add_cable_length_load controls unstressed-length input; apply_prestress targets named tendons. These calls use native values; verify units in the relevant bridge definition, without inferring them from similarly named APIs.\n"
    "Plate loads: add_plate_element_load acts directly on selected plates; add_distribute_plane_load places a previously defined plane-load pattern. Omitting plate_ids from the latter uses all plates; it does not create the pattern.\n"
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
