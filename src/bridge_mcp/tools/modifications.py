"""
MCP Modification Tools — update/modify existing model entities.
桥梁模型修改类工具 (基于 qtmodel 2.2.1 API)

Provides tools to modify existing nodes, elements, materials,
sections, boundaries, and structure groups.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_modification_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register all modify-type MCP tools."""

    # ── 1. Node modifications ─────────────────────────────────────────

    @mcp.tool()
    def update_node(
        node_id: int,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
        new_id: int = -1,
    ) -> str:
        """
        Modify an existing node's coordinates or ID (修改节点坐标或编号).

        Args:
            node_id: Existing node ID to modify (待修改的节点编号)
            x: New X coordinate, leave None to keep unchanged (新X坐标，不修改则留空)
            y: New Y coordinate, leave None to keep unchanged (新Y坐标，不修改则留空)
            z: New Z coordinate, leave None to keep unchanged (新Z坐标，不修改则留空)
            new_id: New node ID, -1 to keep unchanged (新节点编号，-1表示不修改编号)

        Example:
            update_node(1, z=-1.5)  # Move node 1 down to z=-1.5
        """
        try:
            kwargs = {"node_id": node_id, "new_id": new_id}
            if x is not None:
                kwargs["x"] = x
            if y is not None:
                kwargs["y"] = y
            if z is not None:
                kwargs["z"] = z
            provider.update_node(**kwargs)
            provider.update_model()
            parts = []
            if new_id != -1:
                parts.append(f"ID→{new_id}")
            if x is not None:
                parts.append(f"x={x}")
            if y is not None:
                parts.append(f"y={y}")
            if z is not None:
                parts.append(f"z={z}")
            return f"Node {node_id} updated ({', '.join(parts)}) (节点 {node_id} 修改成功)"
        except Exception as e:
            return f"Error updating node (修改节点失败): {e}"

    @mcp.tool()
    def move_nodes(
        ids: Any,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        offset_z: float = 0.0,
    ) -> str:
        """
        Move nodes by an offset (平移节点).

        Args:
            ids: Node ID(s) to move. Supports int, list, or range string '1to10'.
                 (节点编号，支持整数、列表或范围字符串)
            offset_x: X-direction offset in model units (X方向偏移量)
            offset_y: Y-direction offset in model units (Y方向偏移量)
            offset_z: Z-direction offset in model units (Z方向偏移量)

        Example:
            move_nodes("1to10", offset_z=-0.5)  # Move nodes 1-10 down by 0.5m
        """
        try:
            provider.move_nodes(
                ids=ids, offset_x=offset_x, offset_y=offset_y, offset_z=offset_z
            )
            provider.update_model()
            return (
                f"Nodes {ids} moved by ({offset_x}, {offset_y}, {offset_z}) "
                f"(节点 {ids} 平移成功)"
            )
        except Exception as e:
            return f"Error moving nodes (平移节点失败): {e}"

    # ── 2. Element modifications ──────────────────────────────────────

    @mcp.tool()
    def update_element(
        old_id: int,
        new_id: int = -1,
        ele_type: int | None = None,
        node_i: int | None = None,
        node_j: int | None = None,
        mat_id: int | None = None,
        sec_id: int | None = None,
        beta_angle: float | None = None,
    ) -> str:
        """
        Modify an existing element's properties (修改单元属性).

        Args:
            old_id: Existing element ID (待修改的单元编号)
            new_id: New element ID, -1 to keep unchanged  (新单元编号，-1不修改)
            ele_type: Element type (单元类型): 1=beam(梁), 2=truss(杆), 3=cable(索), 4=plate(板)
            node_i: New I-end node ID (新I端节点号)
            node_j: New J-end node ID (新J端节点号)
            mat_id: New material ID (新材料编号)
            sec_id: New section ID (新截面编号)
            beta_angle: New beta angle in degrees (新贝塔角，单位度)

        Example:
            update_element(5, mat_id=2, sec_id=3)  # Change element 5's material and section
        """
        try:
            kwargs: dict[str, Any] = {"old_id": old_id}
            if new_id != -1:
                kwargs["new_id"] = new_id
            if ele_type is not None:
                kwargs["ele_type"] = ele_type
            if node_i is not None and node_j is not None:
                kwargs["node_ids"] = [node_i, node_j]
            if mat_id is not None:
                kwargs["mat_id"] = mat_id
            if sec_id is not None:
                kwargs["sec_id"] = sec_id
            if beta_angle is not None:
                kwargs["beta_angle"] = beta_angle
            provider.update_element(**kwargs)
            provider.update_model()
            return f"Element {old_id} updated successfully (单元 {old_id} 修改成功)"
        except Exception as e:
            return f"Error updating element (修改单元失败): {e}"

    @mcp.tool()
    def update_element_material(
        ids: Any,
        mat_id: int,
    ) -> str:
        """
        Change the material of one or more elements (修改单元材料).

        Args:
            ids: Element ID(s). Supports int, list, or range string '1to50'.
                 (单元编号，支持整数、列表或范围字符串)
            mat_id: New material ID (新材料编号，使用 get_materials 查询有效编号)

        Example:
            update_element_material("1to20", mat_id=2)
        """
        try:
            provider.update_element_material(ids=ids, mat_id=mat_id)
            provider.update_model()
            return f"Material of element(s) {ids} changed to {mat_id} (单元材料修改成功)"
        except Exception as e:
            return f"Error updating element material (修改单元材料失败): {e}"

    @mcp.tool()
    def update_element_section(
        ids: Any,
        sec_id: int,
    ) -> str:
        """
        Change the section of one or more frame elements (修改杆系单元截面).

        Args:
            ids: Element ID(s). Supports int, list, or range string '1to50'.
                 (单元编号，支持整数、列表或范围字符串)
            sec_id: New section ID (新截面编号，使用 get_section_list 查询有效编号)

        Example:
            update_element_section("1to30", sec_id=2)
        """
        try:
            provider.update_frame_section(ids=ids, sec_id=sec_id)
            provider.update_model()
            return f"Section of element(s) {ids} changed to {sec_id} (单元截面修改成功)"
        except Exception as e:
            return f"Error updating element section (修改单元截面失败): {e}"

    @mcp.tool()
    def update_element_beta(
        ids: Any,
        beta: float,
    ) -> str:
        """
        Change the beta angle of one or more elements (修改单元贝塔角).

        The beta angle controls the local axis orientation of a beam/truss element.
        贝塔角控制单元局部坐标系方向。

        Args:
            ids: Element ID(s). Supports int, list, or range string.
                 (单元编号，支持整数、列表或范围字符串)
            beta: New beta angle in degrees (新贝塔角，单位：度)

        Example:
            update_element_beta("1to10", beta=90)
        """
        try:
            provider.update_element_beta(ids=ids, beta=beta)
            provider.update_model()
            return f"Beta angle of element(s) {ids} changed to {beta}° (贝塔角修改成功)"
        except Exception as e:
            return f"Error updating beta angle (修改贝塔角失败): {e}"

    @mcp.tool()
    def update_element_nodes(
        element_id: int,
        node_i: int,
        node_j: int,
    ) -> str:
        """
        Replace the end nodes of an element (修改单元端节点).

        Args:
            element_id: Element ID to modify (待修改的单元编号)
            node_i: New I-end node ID (新I端节点号)
            node_j: New J-end node ID (新J端节点号)
        """
        try:
            provider.update_element_node(element_id=element_id, node_ids=[node_i, node_j])
            provider.update_model()
            return (
                f"Element {element_id} nodes updated to [{node_i}, {node_j}] "
                f"(单元 {element_id} 端节点修改成功)"
            )
        except Exception as e:
            return f"Error updating element nodes (修改单元端节点失败): {e}"

    # ── 3. Structure group modifications ──────────────────────────────

    @mcp.tool()
    def add_to_structure_group(
        group_name: str,
        node_ids: Any = None,
        element_ids: Any = None,
    ) -> str:
        """
        Add nodes and/or elements to an existing structure group
        (向已有结构组中添加节点和/或单元).

        Args:
            group_name: Name of the structure group (结构组名称)
            node_ids: Node ID(s) to add. Supports int, list, or range string '1to10'.
                      (要添加的节点编号)
            element_ids: Element ID(s) to add. Supports int, list, or range string.
                         (要添加的单元编号)

        Example:
            add_to_structure_group("上部结构", element_ids="11to20")
        """
        try:
            kwargs: dict[str, Any] = {"name": group_name}
            if node_ids is not None:
                kwargs["node_ids"] = node_ids
            if element_ids is not None:
                kwargs["element_ids"] = element_ids
            provider.add_structure_to_group(**kwargs)
            return (
                f"Added to structure group '{group_name}' "
                f"(nodes: {node_ids}, elements: {element_ids}) "
                f"(已添加到结构组 '{group_name}')"
            )
        except Exception as e:
            return f"Error adding to structure group (向结构组添加成员失败): {e}"

    @mcp.tool()
    def remove_from_structure_group(
        group_name: str,
        node_ids: Any = None,
        element_ids: Any = None,
    ) -> str:
        """
        Remove nodes and/or elements from an existing structure group
        (从结构组中移除节点和/或单元).

        Args:
            group_name: Name of the structure group (结构组名称)
            node_ids: Node ID(s) to remove. Supports int, list, or range string.
                      (要移除的节点编号)
            element_ids: Element ID(s) to remove. Supports int, list, or range string.
                         (要移除的单元编号)
        """
        try:
            kwargs: dict[str, Any] = {"name": group_name}
            if node_ids is not None:
                kwargs["node_ids"] = node_ids
            if element_ids is not None:
                kwargs["element_ids"] = element_ids
            provider.remove_structure_from_group(**kwargs)
            return (
                f"Removed from structure group '{group_name}' "
                f"(nodes: {node_ids}, elements: {element_ids}) "
                f"(已从结构组 '{group_name}' 移除)"
            )
        except Exception as e:
            return f"Error removing from structure group (从结构组移除成员失败): {e}"

    # ── 4. Delete operations ──────────────────────────────────────────

    @mcp.tool()
    def remove_nodes(ids: Any = None) -> str:
        """
        Delete nodes from the model (删除节点).

        Args:
            ids: Node ID(s) to delete. Supports int, list, or range string '1to10'.
                 Leave empty to delete ALL nodes (危险！).
                 (节点编号，留空则删除全部节点，谨慎使用)

        Example:
            remove_nodes(ids=[5, 6, 7])  # Delete specific nodes
        """
        try:
            if ids is not None:
                provider.remove_nodes(ids=ids)
            else:
                provider.remove_nodes()
            provider.update_model()
            target = ids if ids is not None else "ALL NODES"
            return f"Deleted node(s) {target} (节点 {target} 已删除)"
        except Exception as e:
            return f"Error removing nodes (删除节点失败): {e}"

    @mcp.tool()
    def remove_elements(ids: Any = None, remove_free_nodes: bool = False) -> str:
        """
        Delete elements from the model (删除单元).

        Args:
            ids: Element ID(s) to delete. Supports int, list, or range string '1to10'.
                 Leave empty to delete ALL elements (危险！).
                 (单元编号，留空则删除全部单元，谨慎使用)
            remove_free_nodes: Also delete nodes that become free after element deletion
                               (是否同时删除孤立节点，默认不删除)

        Example:
            remove_elements(ids="11to20")
        """
        try:
            if ids is not None:
                provider.remove_elements(ids=ids, remove_free=remove_free_nodes)
            else:
                provider.remove_elements(remove_free=remove_free_nodes)
            provider.update_model()
            target = ids if ids is not None else "ALL ELEMENTS"
            return f"Deleted element(s) {target} (单元 {target} 已删除)"
        except Exception as e:
            return f"Error removing elements (删除单元失败): {e}"

    @mcp.tool()
    def merge_nodes(ids: Any = None, tolerance: float = 1e-4) -> str:
        """
        Merge nodes that are at (nearly) the same coordinates (合并重合节点).

        This is equivalent to the "Merge Nodes" operation in the GUI.
        Useful after building a model to remove accidental duplicate nodes.
        相当于界面上的"合并节点"功能，用于消除重叠节点。

        Args:
            ids: Node ID(s) to check. Supports int, list, or range string.
                 Leave empty to check ALL nodes.
                 (节点编号，留空则检查全部节点)
            tolerance: Merge distance tolerance in model units, default 0.0001m
                       (合并容许误差，默认 0.0001m)

        Example:
            merge_nodes()  # Merge all overlapping nodes in the model
        """
        try:
            if ids is not None:
                provider.merge_nodes(ids=ids, tolerance=tolerance)
            else:
                provider.merge_nodes(tolerance=tolerance)
            provider.update_model()
            return f"Merge nodes completed (tolerance={tolerance}) (节点合并完成)"
        except Exception as e:
            return f"Error merging nodes (合并节点失败): {e}"
