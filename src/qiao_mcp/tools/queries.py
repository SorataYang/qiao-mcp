"""
MCP Query Tools — read-only information retrieval from the bridge model.
桥梁模型只读信息查询工具（合并版）

Four consolidated tools replace the former 52 single-purpose wrappers:
    get_model_data      — entity/load/stage data by kind (按类型查询模型数据)
    find_entities       — locate nodes/elements by coordinates or attributes (按条件定位)
    calc_section_property — compute properties from raw geometry (按几何计算截面特性)
    get_special_results — post-analysis special results (专项分析结果)

All list outputs are paginated (limit/offset) to protect the LLM context window.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider

# 输出保护：单次返回的最大条数上限
MAX_LIMIT = 500


def _fmt(obj: Any) -> str:
    """Pretty-print any object as compact JSON for MCP responses."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _paginate(data: Any, limit: int, offset: int) -> str:
    """Slice list data and annotate with pagination info (分页并标注截断信息)."""
    if not isinstance(data, list):
        return _fmt(data)
    total = len(data)
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    window = data[offset : offset + limit]
    header = f"[{offset + 1}–{offset + len(window)} of {total}]"
    if offset + len(window) < total:
        header += (
            f" TRUNCATED — use offset={offset + len(window)} for the next page "
            f"(结果已截断，用 offset 翻页)"
        )
    return f"{header}\n{_fmt(window)}"


def register_query_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register consolidated read-only query tools."""

    @mcp.tool()
    def get_model_data(
        kind: str,
        ids: int | list[int] | str | None = None,
        name: str = "",
        sec_id: int | None = None,
        position: int = 0,
        stage_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Query model data by kind (按类型查询模型数据) — the single read tool for
        entities, loads, groups and stages. List results are paginated.

        Args:
            kind: What to query (查询类型):
                ── 实体 Entities ──
                "nodes" (节点, 可选 ids), "elements" (单元, 可选 ids),
                "materials" (材料), "sections" (截面列表),
                "section_detail" (截面详情, 需 sec_id, 可选 position 0=起端 1=末端),
                "section_shape" (截面形状, 需 sec_id),
                "section_property" (截面特性, 需 sec_id),
                "thickness" (板厚), "boundaries" (全部边界条件),
                "node_local_axis" (节点局部坐标), "constraint_equations" (约束方程),
                "effective_widths" (有效宽度), "reinforcement" (配筋数据)
                ── 组 Groups ──
                "structure_groups" (结构组名列表),
                "group_elements" (结构组内单元, 需 name),
                "group_nodes" (结构组内节点, 需 name)
                ── 荷载 Loads ──
                "load_cases" (荷载工况名), "nodal_force_loads" (节点力),
                "nodal_displacement_loads" (节点位移/沉降), "beam_element_loads" (梁单元荷载),
                "plate_element_loads" (板单元荷载), "initial_tension_loads" (初拉力),
                "cable_length_loads" (索长荷载), "pre_stress_loads" (预应力荷载),
                "node_masses" (节点质量), "tendon_properties" (钢束特性),
                "deviation_parameters" (制造偏差参数), "deviation_loads" (制造偏差荷载)
                ── 施工阶段 Stages ──
                "stages" (施工阶段名), "stage_elements" (阶段内单元, 需 stage_id),
                "stage_nodes" (阶段内节点, 需 stage_id), "stage_groups" (阶段内组, 需 stage_id)
            ids: Entity IDs for nodes/elements, int/list/range string "1to10" (编号)
            name: Group name, for group_elements/group_nodes (结构组名)
            sec_id: Section ID, for section_detail/section_shape/section_property (截面号)
            position: Tapered section end, for section_detail (变截面位置 0起/1末)
            stage_id: Stage ID, for stage_* kinds (施工阶段号)
            limit: Max items per page, default 100, max 500 (单页条数上限)
            offset: Skip count for pagination (翻页偏移)
        """
        try:
            if kind == "nodes":
                data = provider.get_node_data(ids=ids)
            elif kind == "elements":
                data = provider.get_element_data(ids=ids)
            elif kind == "materials":
                data = provider.get_material_data()
            elif kind == "sections":
                data = provider.get_section_names()
            elif kind == "section_detail":
                if sec_id is None:
                    return "section_detail requires sec_id (需要提供 sec_id)"
                data = provider.get_section_data(sec_id=sec_id, position=position)
            elif kind == "section_shape":
                if sec_id is None:
                    return "section_shape requires sec_id (需要提供 sec_id)"
                data = provider.get_section_shape(sec_id)
            elif kind == "section_property":
                if sec_id is None:
                    return "section_property requires sec_id (需要提供 sec_id)"
                data = provider.get_section_property(sec_id)
            elif kind == "thickness":
                data = provider.get_thickness_data()
            elif kind == "boundaries":
                data = provider.get_boundary_data()
            elif kind == "node_local_axis":
                data = provider.get_node_local_axis_data()
            elif kind == "constraint_equations":
                data = provider.get_constraint_equation_data()
            elif kind == "effective_widths":
                data = provider.get_effective_width_data()
            elif kind == "reinforcement":
                data = provider.get_reinforcement_data()
            elif kind == "structure_groups":
                data = provider.get_structure_group_names()
            elif kind == "group_elements":
                if not name:
                    return "group_elements requires name (需要提供结构组名 name)"
                data = provider.get_structure_group_elements(name=name)
            elif kind == "group_nodes":
                if not name:
                    return "group_nodes requires name (需要提供结构组名 name)"
                data = provider.get_group_nodes(name)
            elif kind == "load_cases":
                data = provider.get_load_case_names()
            elif kind == "nodal_force_loads":
                data = provider.get_nodal_force_load_data()
            elif kind == "nodal_displacement_loads":
                data = provider.get_nodal_displacement_load_data()
            elif kind == "beam_element_loads":
                data = provider.get_beam_element_load_data()
            elif kind == "plate_element_loads":
                data = provider.get_plate_element_load_data()
            elif kind == "initial_tension_loads":
                data = provider.get_initial_tension_load_data()
            elif kind == "cable_length_loads":
                data = provider.get_cable_length_load_data()
            elif kind == "pre_stress_loads":
                data = provider.get_pre_stress_load_data()
            elif kind == "node_masses":
                data = provider.get_node_mass_data()
            elif kind == "tendon_properties":
                data = provider.get_tendon_property_data()
            elif kind == "deviation_parameters":
                data = provider.get_deviation_parameters()
            elif kind == "deviation_loads":
                data = provider.get_deviation_load_data()
            elif kind == "stages":
                data = provider.get_stage_names()
            elif kind == "stage_elements":
                if stage_id is None:
                    return "stage_elements requires stage_id (需要提供 stage_id)"
                data = provider.get_elements_of_stage(stage_id)
            elif kind == "stage_nodes":
                if stage_id is None:
                    return "stage_nodes requires stage_id (需要提供 stage_id)"
                data = provider.get_nodes_of_stage(stage_id)
            elif kind == "stage_groups":
                if stage_id is None:
                    return "stage_groups requires stage_id (需要提供 stage_id)"
                data = provider.get_groups_of_stage(stage_id)
            else:
                return (
                    f"Unknown kind '{kind}'. See tool description for the full list "
                    f"(未知查询类型，请查阅工具说明)"
                )

            if data is None or data == [] or data == {}:
                return f"No data for kind='{kind}' (无数据). Model may be empty or analysis not run."
            return f"{kind}:\n{_paginate(data, limit, offset)}"
        except Exception as e:
            return f"Error querying {kind} (查询失败): {e}"

    @mcp.tool()
    def find_entities(
        by: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        tolerance: float = 1e-3,
        name: str = "",
        index: int | None = None,
        ids: int | list[int] | str | None = None,
        span_info_name: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Locate nodes/elements by coordinates or attributes (按坐标或属性定位节点/单元).

        Args:
            by: Search mode (查找方式):
                "node_at_point" (按坐标找节点, 需 x/y/z, 可选 tolerance),
                "elements_at_point" (按坐标找单元, 需 x/y/z, 可选 tolerance),
                "elements_by_material" (按材料名找单元, 需 name),
                "elements_by_section" (按截面号找单元, 需 index),
                "element_type" (查单元类型, 需 ids),
                "element_weight" (查单元重量, 需 ids),
                "span_supports" (跨径支承信息, 需 span_info_name),
                "span_elements" (跨径单元信息, 需 span_info_name)
            x, y, z: Coordinates for point search (坐标)
            tolerance: Search tolerance (容差)
            name: Material name (材料名)
            index: Section ID (截面号)
            ids: Element IDs (单元编号)
            span_info_name: Span info name (跨径信息名)
            limit: Max items per page (单页条数上限)
            offset: Pagination offset (翻页偏移)
        """
        try:
            if by == "node_at_point":
                data = provider.get_node_id(x, y, z, tolerance)
            elif by == "elements_at_point":
                data = provider.get_elements_by_point(x, y, z, tolerance)
            elif by == "elements_by_material":
                if not name:
                    return "elements_by_material requires name (需要材料名)"
                data = provider.get_elements_by_material(name)
            elif by == "elements_by_section":
                if index is None:
                    return "elements_by_section requires index (需要截面号)"
                data = provider.get_elements_by_section(index)
            elif by == "element_type":
                if ids is None:
                    return "element_type requires ids (需要单元编号)"
                data = provider.get_element_type(ids)
            elif by == "element_weight":
                if ids is None:
                    return "element_weight requires ids (需要单元编号)"
                data = provider.get_element_weight(ids)
            elif by == "span_supports":
                if not span_info_name:
                    return "span_supports requires span_info_name (需要跨径信息名)"
                data = provider.get_span_supports(span_info_name)
            elif by == "span_elements":
                if not span_info_name:
                    return "span_elements requires span_info_name (需要跨径信息名)"
                data = provider.get_span_elements(span_info_name)
            else:
                return f"Unknown search mode '{by}' (未知查找方式，请查阅工具说明)"

            if data is None or data == []:
                return f"Nothing found for by='{by}' (未找到匹配项)"
            return f"{by}:\n{_paginate(data, limit, offset)}"
        except Exception as e:
            return f"Error finding entities (查找失败): {e}"

    @mcp.tool()
    def calc_section_property(
        loop_segments: list[dict] | None = None,
        sec_lines: list[list[float]] | None = None,
    ) -> str:
        """
        Compute section properties from raw geometry, without creating a section
        (按几何直接计算截面特性，不创建截面).

        Provide EXACTLY ONE of:
            loop_segments: Polygon loops [{"main": [[x,y],...], "sub": ...}, ...]
                           (多边形环定义)
            sec_lines: Line-width segments [[x1,y1,x2,y2,width], ...] (线宽定义)
        """
        try:
            if (loop_segments is None) == (sec_lines is None):
                return "Provide exactly one of loop_segments / sec_lines (两者恰选其一)"
            if loop_segments is not None:
                data = provider.get_section_property_by_loops(loop_segments)
            else:
                data = provider.get_section_property_by_lines(sec_lines)
            return f"Section properties:\n{_fmt(data)}"
        except Exception as e:
            return f"Error calculating section property (计算截面特性失败): {e}"

    @mcp.tool()
    def get_special_results(
        kind: str,
        ids: int | list[int] | str | None = None,
        case_name: str = "",
        node_id: int | None = None,
        mode: int = 1,
        stage_id: int = 1,
        result_kind: int = 1,
        envelop_type: int = 1,
        increment_type: int = 1,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Get special post-analysis results (专项分析结果查询) — beyond the basic
        deformation/force/stress/reaction of get_analysis_results.

        Args:
            kind: Result kind (结果类型):
                "vibration_modal" (自振振型, 需 mode), "buckling_modal" (屈曲振型, 需 mode),
                "period_vibration" (周期与振型汇总), "buckling_eigenvalue" (屈曲特征值),
                "self_concurrent_reaction" (自并发反力, 需 node_id + case_name),
                "all_concurrent_reaction" (全并发反力, 需 node_id + case_name),
                "concurrent_force" (并发内力, 需 ids + case_name),
                "elastic_link_force" (弹性连接内力, 需 ids),
                "constraint_equation_force" (约束方程内力, 需 ids),
                "cable_element_length" (索单元无应力长度, 需 ids)
            ids: Element/link IDs (单元/连接编号)
            case_name: Load case name (荷载工况名)
            node_id: Node ID for concurrent reactions (并发反力节点号)
            mode: Mode number for modal results (振型阶数)
            stage_id: Construction stage (施工阶段号, -1=运营)
            result_kind: Result kind flag (结果种类)
            envelop_type: Envelope type (包络类型)
            increment_type: Increment type (增量类型)
            limit: Max items per page (单页条数上限)
            offset: Pagination offset (翻页偏移)
        """
        try:
            if kind == "vibration_modal":
                data = provider.get_vibration_modal_results(mode=mode)
            elif kind == "buckling_modal":
                data = provider.get_buckling_modal_results(mode=mode)
            elif kind == "period_vibration":
                data = provider.get_period_and_vibration_results()
            elif kind == "buckling_eigenvalue":
                data = provider.get_buckling_eigenvalue()
            elif kind == "self_concurrent_reaction":
                if node_id is None or not case_name:
                    return "self_concurrent_reaction requires node_id and case_name"
                data = provider.get_self_concurrent_reaction(node_id, case_name)
            elif kind == "all_concurrent_reaction":
                if node_id is None or not case_name:
                    return "all_concurrent_reaction requires node_id and case_name"
                data = provider.get_all_concurrent_reaction(node_id, case_name)
            elif kind == "concurrent_force":
                if ids is None or not case_name:
                    return "concurrent_force requires ids and case_name"
                data = provider.get_concurrent_force(ids, case_name)
            elif kind == "elastic_link_force":
                if ids is None:
                    return "elastic_link_force requires ids"
                data = provider.get_elastic_link_force(
                    ids, result_kind, stage_id, envelop_type, increment_type, case_name
                )
            elif kind == "constraint_equation_force":
                if ids is None:
                    return "constraint_equation_force requires ids"
                data = provider.get_constrain_equation_force(
                    ids, result_kind, stage_id, envelop_type, increment_type, case_name
                )
            elif kind == "cable_element_length":
                if ids is None:
                    return "cable_element_length requires ids"
                data = provider.get_cable_element_length(ids, stage_id, increment_type)
            else:
                return f"Unknown result kind '{kind}' (未知结果类型，请查阅工具说明)"

            if data is None or data == []:
                return f"No results for kind='{kind}' (无结果). Has the analysis been run?"
            return f"{kind}:\n{_paginate(data, limit, offset)}"
        except Exception as e:
            return f"Error getting special results (查询专项结果失败): {e}"
