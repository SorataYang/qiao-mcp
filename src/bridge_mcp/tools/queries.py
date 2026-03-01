"""
MCP Query Tools — read-only information retrieval from the bridge model.
桥梁模型只读信息查询工具

Provides tools to inspect current model state:
    nodes, elements, materials,  sections, boundaries,
    load cases / groups, structure groups, construction stages,
    tendon properties, taper section groups.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def _fmt(obj: Any) -> str:
    """Pretty-print any object as compact JSON for MCP responses."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def register_query_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register all read-only query tools."""

    # ── 1. Nodes ──────────────────────────────────────────────────────

    @mcp.tool()
    def get_nodes(ids: Any = None) -> str:
        """
        Get node coordinate data from the model (获取节点坐标数据).

        Args:
            ids: Node ID(s) to query. Supports int, list, or range string like '1to10 15 20'.
                 Leave empty to get ALL nodes (节点编号，留空返回全部节点).

        Returns:
            JSON list of node dicts with keys: id, x, y, z
            (JSON节点列表，每项包含 id, x, y, z 坐标)

        The typical format from qtmodel is:
            [{"id": 1, "x": 0.0, "y": 0.0, "z": 0.0}, ...]
        """
        try:
            data = provider.get_node_data(ids=ids)
            if not data:
                return "No nodes found (未找到节点). Model may be empty."
            return f"Nodes ({len(data)} total):\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting nodes (获取节点失败): {e}"

    # ── 2. Elements ───────────────────────────────────────────────────

    @mcp.tool()
    def get_elements(ids: Any = None) -> str:
        """
        Get element data from the model (获取单元数据).

        Args:
            ids: Element ID(s) to query. Supports int, list, or range string like '1to50'.
                 Leave empty to get ALL elements (单元编号，留空返回全部单元).

        Returns:
            JSON list of element dicts.
            Typical keys: id, type (1=beam,2=truss,3=cable,4=plate),
                          material_id, section_id, node_i, node_j
            (JSON单元列表，包含单元类型、材料、截面、节点等信息)
        """
        try:
            data = provider.get_element_data(ids=ids)
            if not data:
                return "No elements found (未找到单元). Model may be empty."
            return f"Elements ({len(data)} total):\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting elements (获取单元失败): {e}"

    # ── 3. Materials ──────────────────────────────────────────────────

    @mcp.tool()
    def get_materials() -> str:
        """
        Get all materials defined in the model (获取所有材料定义).

        Returns:
            JSON list of material dicts with keys: id, name, mat_type, E, gamma (unit weight),
            nu (Poisson's ratio), alpha (thermal expansion), standard, database
            (JSON材料列表，包含材料类型、弹性模量、容重、泊松比等参数)

        Use this before create_element to get valid material IDs.
        (创建单元前调用此工具以获取有效的材料编号)
        """
        try:
            data = provider.get_material_data()
            if not data:
                return "No materials defined (尚未定义材料). Use create_material tool first."
            return f"Materials ({len(data)} total):\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting materials (获取材料失败): {e}"

    # ── 4. Sections ───────────────────────────────────────────────────

    @mcp.tool()
    def get_section_list() -> str:
        """
        Get all section names/IDs defined in the model (获取所有截面列表).

        Returns:
            List of section IDs or names.
            (截面编号或名称列表)

        Use this before create_elements to get valid section IDs.
        (创建单元前调用此工具以获取有效的截面编号)
        """
        try:
            data = provider.get_section_names()
            if not data:
                return "No sections defined (尚未定义截面). Use create_section tool first."
            return f"Sections ({len(data)} total):\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting sections (获取截面列表失败): {e}"

    @mcp.tool()
    def get_section_detail(sec_id: int, position: int = 0) -> str:
        """
        Get detailed properties of a specific section (获取截面详细属性).

        Args:
            sec_id: Section ID (截面编号)
            position: Position along tapered section (变截面位置): 0=start(起端), 1=end(末端)

        Returns:
            JSON dict of section properties including:
            area (面积), Iy (y轴惯性矩), Iz (z轴惯性矩), J (扭转惯性矩),
            Sy (抗弯截面系数y), Sz (抗弯截面系数z), height (梁高), width (梁宽)
        """
        try:
            data = provider.get_section_data(sec_id=sec_id, position=position)
            if not data:
                return f"Section {sec_id} not found (截面 {sec_id} 不存在)."
            return f"Section {sec_id} properties:\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting section detail (获取截面详情失败): {e}"

    # ── 5. Boundaries ─────────────────────────────────────────────────

    @mcp.tool()
    def get_boundaries() -> str:
        """
        Get all boundary conditions defined in the model (获取所有边界条件).

        Returns:
            JSON dict with keys:
              - general_supports: nodal supports (一般支承)
              - elastic_links: elastic connection links (弹性连接)
              - elastic_supports: elastic supports (弹性支承)
              - master_slave_links: rigid body constraints (主从约束)
              - beam_constraints: beam end releases (梁端约束)
            (以JSON形式返回所有类型的边界条件)
        """
        try:
            data = provider.get_boundary_data()
            totals = {k: len(v) for k, v in data.items()}
            grand_total = sum(totals.values())
            if grand_total == 0:
                return "No boundary conditions defined (尚未定义边界条件)."
            return f"Boundary conditions (total {grand_total}):\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting boundaries (获取边界条件失败): {e}"

    # ── 6. Load cases & groups ────────────────────────────────────────

    @mcp.tool()
    def get_load_cases() -> str:
        """
        Get all load case names defined in the model (获取所有荷载工况名称).

        Returns:
            List of load case names.
            (荷载工况名称列表)

        Use this to know which load cases are available before querying results.
        (查询分析结果前，先调用此工具确认已有哪些荷载工况)
        """
        try:
            data = provider.get_load_case_names()
            if not data:
                return "No load cases defined (尚未定义荷载工况)."
            return f"Load cases ({len(data)} total):\n" + "\n".join(f"  - {n}" for n in data)
        except Exception as e:
            return f"Error getting load cases (获取荷载工况失败): {e}"

    # ── 7. Construction stages ────────────────────────────────────────

    @mcp.tool()
    def get_construction_stages() -> str:
        """
        Get all construction stage names defined in the model (获取所有施工阶段名称).

        Returns:
            List of construction stage names in execution order.
            (施工阶段名称列表，按施工顺序排列)
        """
        try:
            data = provider.get_stage_names()
            if not data:
                return "No construction stages defined (尚未定义施工阶段)."
            return (
                f"Construction stages ({len(data)} total):\n"
                + "\n".join(f"  {i+1}. {n}" for i, n in enumerate(data))
            )
        except Exception as e:
            return f"Error getting construction stages (获取施工阶段失败): {e}"

    # ── 8. Structure groups ───────────────────────────────────────────

    @mcp.tool()
    def get_structure_groups() -> str:
        """
        Get all structure group names defined in the model (获取所有结构组名称).

        Returns:
            List of structure group names.
            (结构组名称列表)

        Structure groups are used in construction stages to activate/deactivate elements.
        (结构组在施工阶段中用于激活/钝化单元)
        """
        try:
            data = provider.get_structure_group_names()
            if not data:
                return "No structure groups defined (尚未定义结构组)."
            return (
                f"Structure groups ({len(data)} total):\n"
                + "\n".join(f"  - {n}" for n in data)
            )
        except Exception as e:
            return f"Error getting structure groups (获取结构组失败): {e}"

    @mcp.tool()
    def get_structure_group_members(group_name: str) -> str:
        """
        Get the element/node members of a specific structure group
        (获取指定结构组所包含的单元/节点).

        Args:
            group_name: Name of the structure group (结构组名称)

        Returns:
            JSON dict with element and node IDs in the group.
            (JSON格式的结构组成员列表，含单元和节点编号)
        """
        try:
            data = provider.get_structure_group_elements(name=group_name)
            if not data:
                return f"Structure group '{group_name}' is empty or not found."
            return f"Structure group '{group_name}':\n{_fmt(data)}"
        except Exception as e:
            return f"Error getting structure group members (获取结构组成员失败): {e}"

    # Note: get_tendon_info is registered in tools/tendon.py
