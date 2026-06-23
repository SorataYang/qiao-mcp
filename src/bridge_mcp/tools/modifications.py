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

    # ── 1. General model operations ───────────────────────────────────

    @mcp.tool()
    def initialize_model(confirm: bool = False) -> str:
        """
        Initialize a new empty model (初始化全新模型).
        
        WARNING: This will CLEAR the current model data in the active bridge software!
        (警告：此操作将清空桥通软件中的当前模型！)
        
        Use this ONLY when starting a brand new project, NOT when modifying an existing one.
        (仅在从零开始新建桥梁时使用，修改现有模型时绝对不要调用此工具)

        CRITICAL LLM INSTRUCTION: Do NOT call this tool autonomously to fix your own mistakes. 
        You MUST explicitly ask the USER for permission before calling this tool.
        (严重的指令：大模型绝对不可为了修复自己的建型错误而自行调用此工具清空模型！必须先向用户询问并获得许可！)
        
        Args:
            confirm: Must be set to true to execute (必须设为true以确认操作)
        """
        if not confirm:
            return "Initialization aborted. You must set confirm=True to clear the model. (初始化已取消，必须设置 confirm=True)"
            
        try:
            provider.initialize_model()
            provider.update_model()
            return "New model successfully initialized. The software is now ready for a new project. (新模型初始化成功，当前模型已清空)"
        except Exception as e:
            return f"Error initializing model (初始化模型失败): {e}"

    @mcp.tool()
    def save_model_file(file_path: str) -> str:
        """
        Save the current model to a file (保存模型文件).

        Args:
            file_path: Absolute or relative path to the .qtb file (保存的文件路径)
        """
        try:
            provider.save_model_file(file_path=file_path)
            return f"Successfully saved model to '{file_path}' (成功保存模型)"
        except Exception as e:
            return f"Error saving model file (保存模型文件失败): {e}"

    @mcp.tool()
    def open_model_file(file_path: str) -> str:
        """
        Open an existing model file (打开模型文件).

        Args:
            file_path: Absolute or relative path to the .qtb file (要打开的文件路径)
        """
        try:
            provider.open_model_file(file_path=file_path)
            provider.update_model()
            return f"Successfully opened model from '{file_path}' (成功打开模型)"
        except Exception as e:
            return f"Error opening model file (打开模型文件失败): {e}"

    @mcp.tool()
    def remove_unused_sections() -> str:
        """
        Clean up and remove all unused sections from the model (删除未使用的截面).
        """
        try:
            provider.remove_unused_sections()
            return "Successfully removed unused sections (成功清除未使用的截面)"
        except Exception as e:
            return f"Error removing unused sections (清除未使用的截面失败): {e}"

    # ── 2. Node modifications ─────────────────────────────────────────

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
    def update_node_id(node_id: int, new_id: int) -> str:
        """
        Change a node's ID (修改节点编号).

        Args:
            node_id: Existing node ID (原节点编号)
            new_id: New node ID (新节点编号)
        """
        try:
            provider.update_node_id(node_id=node_id, new_id=new_id)
            provider.update_model()
            return f"Successfully updated node ID from {node_id} to {new_id} (成功修改节点编号)"
        except Exception as e:
            return f"Error updating node ID (修改节点编号失败): {e}"

    @mcp.tool()
    def renumber_nodes(ids: Any = None, new_ids: Any = None) -> str:
        """
        Renumber nodes (节点重新编号).
        If no IDs are provided, renumbers all nodes starting from 1 continuously.

        Args:
            ids: List of node IDs or string format (可选，原节点号)
            new_ids: List of new node IDs (可选，新节点号)
        """
        try:
            provider.renumber_nodes(ids=ids, new_ids=new_ids)
            provider.update_model()
            return "Successfully renumbered nodes (成功重新编号节点)"
        except Exception as e:
            return f"Error renumbering nodes (重新编号失败): {e}"

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
    def update_element_id(old_id: int, new_id: int) -> str:
        """
        Change an element's ID (更改单元编号).

        Args:
            old_id: Existing element ID (原单元编号)
            new_id: New element ID (新单元编号)
        """
        try:
            provider.update_element_id(old_id=old_id, new_id=new_id)
            provider.update_model()
            return f"Successfully updated element ID from {old_id} to {new_id} (成功修改单元编号)"
        except Exception as e:
            return f"Error updating element ID (修改单元编号失败): {e}"

    @mcp.tool()
    def renumber_elements(element_ids: Any = None, new_ids: Any = None) -> str:
        """
        Renumber elements (单元编号重排序).
        If no IDs are provided, renumbers all elements starting from 1 continuously.

        Args:
            element_ids: List of element IDs or string format (可选，原单元号)
            new_ids: List of new element IDs (可选，新单元号)
        """
        try:
            provider.renumber_elements(element_ids=element_ids, new_ids=new_ids)
            provider.update_model()
            return "Successfully renumbered elements (成功重新编号单元)"
        except Exception as e:
            return f"Error renumbering elements (重新编号失败): {e}"

    @mcp.tool()
    def revert_local_orientation(ids: Any) -> str:
        """
        Revert local orientation of frame elements (反转杆系单元局部方向).

        Args:
            ids: Element ID(s) to revert (待反转方向的单元编号)
        """
        try:
            provider.revert_local_orientation(ids=ids)
            provider.update_model()
            return f"Successfully reverted local orientation for element(s) {ids} (成功反转单元方向)"
        except Exception as e:
            return f"Error reverting local orientation (反转单元方向失败): {e}"

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
    def remove_nodes(ids: Any = None, confirm_delete_all: bool = False) -> str:
        """
        Delete nodes from the model (删除节点).

        Args:
            ids: Node ID(s) to delete. Supports int, list, or range string '1to10'.
                 Leave empty to delete ALL nodes.
                 (节点编号，留空则删除全部节点)
            confirm_delete_all: MUST be set to true if ids is empty (deleting all nodes).
                                (如果要删除所有节点，必须设为 true)

        CRITICAL LLM INSTRUCTION: Do NOT delete all nodes autonomously to fix your own mistakes.
        You MUST explicitly ask the USER for permission before calling this tool with empty ids.
        (大模型绝对不可为了修复自己的错误而自行清空所有节点！必须先向用户询问并获得许可！)

        Example:
            remove_nodes(ids=[5, 6, 7])  # Delete specific nodes
        """
        try:
            if ids is None and not confirm_delete_all:
                return "Aborted: To delete ALL nodes, you must set confirm_delete_all=True. (中止：要删除所有节点必须确认)"
                
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
    def remove_elements(ids: Any = None, remove_free_nodes: bool = False, confirm_delete_all: bool = False) -> str:
        """
        Delete elements from the model (删除单元).

        Args:
            ids: Element ID(s) to delete. Supports int, list, or range string '1to10'.
                 Leave empty to delete ALL elements.
                 (单元编号，留空则删除全部单元)
            remove_free_nodes: Also delete nodes that become free after element deletion
                               (是否同时删除孤立节点，默认不删除)
            confirm_delete_all: MUST be set to true if ids is empty (deleting all elements).
                                (如果要删除所有单元，必须设为 true)

        CRITICAL LLM INSTRUCTION: Do NOT delete all elements autonomously to fix your own mistakes.
        You MUST explicitly ask the USER for permission before calling this tool with empty ids.
        (大模型绝对不可为了修复自己的错误而自行清空所有单元！必须先向用户询问并获得许可！)

        Example:
            remove_elements(ids="11to20")
        """
        try:
            if ids is None and not confirm_delete_all:
                return "Aborted: To delete ALL elements, you must set confirm_delete_all=True. (中止：要删除所有单元必须确认)"

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

    @mcp.tool()
    def update_plate_thick(
        ids,
        thick_id: int = 1,
    ) -> str:
        """
        Update Plate Thick
        """
        try:
            provider.update_plate_thick(ids=ids, thick_id=thick_id)
            return "update_plate_thick successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_plate_thick (执行失败): {e}"

    @mcp.tool()
    def remove_shrink_function(
        name: str = "",
    ) -> str:
        """
        Remove Shrink Function
        """
        try:
            provider.remove_shrink_function(name=name)
            return "remove_shrink_function successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_shrink_function (执行失败): {e}"

    @mcp.tool()
    def remove_creep_function(
        name: str = "",
    ) -> str:
        """
        Remove Creep Function
        """
        try:
            provider.remove_creep_function(name=name)
            return "remove_creep_function successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_creep_function (执行失败): {e}"

    @mcp.tool()
    def update_material_time_parameter(
        name: str = "",
        time_parameter_name: str = "",
        f_cuk: float = 0,
    ) -> str:
        """
        Update Material Time Parameter
        """
        try:
            provider.update_material_time_parameter(name=name, time_parameter_name=time_parameter_name, f_cuk=f_cuk)
            return "update_material_time_parameter successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_material_time_parameter (执行失败): {e}"

    @mcp.tool()
    def update_material_id(
        name: str,
        new_id: int,
    ) -> str:
        """
        Update Material Id
        """
        try:
            provider.update_material_id(name=name, new_id=new_id)
            return "update_material_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_material_id (执行失败): {e}"

    @mcp.tool()
    def update_time_parameter_id(
        name: str,
        new_id: int,
    ) -> str:
        """
        Update Time Parameter Id
        """
        try:
            provider.update_time_parameter_id(name=name, new_id=new_id)
            return "update_time_parameter_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_time_parameter_id (执行失败): {e}"

    @mcp.tool()
    def remove_material(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Material
        """
        try:
            provider.remove_material(index=index, name=name)
            return "remove_material successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_material (执行失败): {e}"

    @mcp.tool()
    def update_material_construction_factor(
        name: str,
        factor: float = 1,
    ) -> str:
        """
        Update Material Construction Factor
        """
        try:
            provider.update_material_construction_factor(name=name, factor=factor)
            return "update_material_construction_factor successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_material_construction_factor (执行失败): {e}"

    @mcp.tool()
    def remove_time_parameter(
        name: str = "",
    ) -> str:
        """
        Remove Time Parameter
        """
        try:
            provider.remove_time_parameter(name=name)
            return "remove_time_parameter successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_time_parameter (执行失败): {e}"

    @mcp.tool()
    def update_thickness_id(
        index: int,
        new_id: int,
    ) -> str:
        """
        Update Thickness Id
        """
        try:
            provider.update_thickness_id(index=index, new_id=new_id)
            return "update_thickness_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_thickness_id (执行失败): {e}"

    @mcp.tool()
    def remove_thickness(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Thickness
        """
        try:
            provider.remove_thickness(index=index, name=name)
            return "remove_thickness successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_thickness (执行失败): {e}"

    @mcp.tool()
    def update_section_id(
        index: int,
        new_id: int,
    ) -> str:
        """
        Update Section Id
        """
        try:
            provider.update_section_id(index=index, new_id=new_id)
            return "update_section_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_section_id (执行失败): {e}"

    @mcp.tool()
    def update_tapper_section_group(
        name: str,
        new_name = "",
        ids = None,
        factor_w: float = 1.0,
        factor_h: float = 1.0,
        ref_w: int = 0,
        ref_h: int = 0,
        dis_w: float = 0,
        dis_h: float = 0,
        parameter_info: str = None,
    ) -> str:
        """
        Update Tapper Section Group
        """
        try:
            provider.update_tapper_section_group(name=name, new_name=new_name, ids=ids, factor_w=factor_w, factor_h=factor_h, ref_w=ref_w, ref_h=ref_h, dis_w=dis_w, dis_h=dis_h, parameter_info=parameter_info)
            return "update_tapper_section_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_tapper_section_group (执行失败): {e}"

    @mcp.tool()
    def remove_tapper_section_group(
        name: str = "",
    ) -> str:
        """
        Remove Tapper Section Group
        """
        try:
            provider.remove_tapper_section_group(name=name)
            return "remove_tapper_section_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_tapper_section_group (执行失败): {e}"

    @mcp.tool()
    def update_boundary_group(
        name: str,
        new_name: str,
    ) -> str:
        """
        Update Boundary Group
        """
        try:
            provider.update_boundary_group(name=name, new_name=new_name)
            return "update_boundary_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_boundary_group (执行失败): {e}"

    @mcp.tool()
    def update_node_axis_id(
        node_id: int,
        new_id: int,
    ) -> str:
        """
        Update Node Axis Id
        """
        try:
            provider.update_node_axis_id(node_id=node_id, new_id=new_id)
            return "update_node_axis_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_node_axis_id (执行失败): {e}"

    @mcp.tool()
    def update_general_elastic_support_property_name(
        name: str,
        new_name: str,
    ) -> str:
        """
        Update General Elastic Support Property Name
        """
        try:
            provider.update_general_elastic_support_property_name(name=name, new_name=new_name)
            return "update_general_elastic_support_property_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_general_elastic_support_property_name (执行失败): {e}"

    @mcp.tool()
    def remove_effective_width(
        element_ids,
        group_name: str = "默认边界组",
    ) -> str:
        """
        Remove Effective Width
        """
        try:
            provider.remove_effective_width(element_ids=element_ids, group_name=group_name)
            return "remove_effective_width successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_effective_width (执行失败): {e}"

    @mcp.tool()
    def remove_boundary_group(
        name: str = "",
    ) -> str:
        """
        Remove Boundary Group
        """
        try:
            provider.remove_boundary_group(name=name)
            return "remove_boundary_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_boundary_group (执行失败): {e}"

    @mcp.tool()
    def remove_all_boundary(
    ) -> str:
        """
        Remove All Boundary
        """
        try:
            provider.remove_all_boundary()
            return "remove_all_boundary successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_all_boundary (执行失败): {e}"

    @mcp.tool()
    def remove_general_elastic_support_property(
        name: str = "",
    ) -> str:
        """
        Remove General Elastic Support Property
        """
        try:
            provider.remove_general_elastic_support_property(name=name)
            return "remove_general_elastic_support_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_general_elastic_support_property (执行失败): {e}"

    @mcp.tool()
    def remove_node_axis(
        node_id: int = -1,
    ) -> str:
        """
        Remove Node Axis
        """
        try:
            provider.remove_node_axis(node_id=node_id)
            return "remove_node_axis successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_node_axis (执行失败): {e}"

    @mcp.tool()
    def update_tendon_property_material(
        name: str,
        material_name: str,
    ) -> str:
        """
        Update Tendon Property Material
        """
        try:
            provider.update_tendon_property_material(name=name, material_name=material_name)
            return "update_tendon_property_material successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_tendon_property_material (执行失败): {e}"

    @mcp.tool()
    def update_tendon_property(
        name: str,
        new_name: str = "",
        tendon_type: int = 0,
        material_name: str = "",
        duct_type: int = 1,
        steel_type: int = 1,
        steel_detail: float = None,
        loos_detail: int = None,
        slip_info: float = None,
    ) -> str:
        """
        Update Tendon Property
        """
        try:
            provider.update_tendon_property(name=name, new_name=new_name, tendon_type=tendon_type, material_name=material_name, duct_type=duct_type, steel_type=steel_type, steel_detail=steel_detail, loos_detail=loos_detail, slip_info=slip_info)
            return "update_tendon_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_tendon_property (执行失败): {e}"

    @mcp.tool()
    def update_tendon_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Tendon Name
        """
        try:
            provider.update_tendon_name(name=name, new_name=new_name)
            return "update_tendon_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_tendon_name (执行失败): {e}"

    @mcp.tool()
    def update_element_component_type(
        ids = None,
        component_type: int = 2,
    ) -> str:
        """
        Update Element Component Type
        """
        try:
            provider.update_element_component_type(ids=ids, component_type=component_type)
            return "update_element_component_type successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_element_component_type (执行失败): {e}"

    @mcp.tool()
    def update_tendon_group(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Tendon Group
        """
        try:
            provider.update_tendon_group(name=name, new_name=new_name)
            return "update_tendon_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_tendon_group (执行失败): {e}"

    @mcp.tool()
    def remove_tendon(
        name: str = "",
        index: int = -1,
    ) -> str:
        """
        Remove Tendon
        """
        try:
            provider.remove_tendon(name=name, index=index)
            return "remove_tendon successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_tendon (执行失败): {e}"

    @mcp.tool()
    def remove_tendon_property(
        name: str = "",
        index: int = -1,
    ) -> str:
        """
        Remove Tendon Property
        """
        try:
            provider.remove_tendon_property(name=name, index=index)
            return "remove_tendon_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_tendon_property (执行失败): {e}"

    @mcp.tool()
    def remove_pre_stress(
        tendon_name: str = "",
    ) -> str:
        """
        Remove Pre Stress
        """
        try:
            provider.remove_pre_stress(tendon_name=tendon_name)
            return "remove_pre_stress successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_pre_stress (执行失败): {e}"

    @mcp.tool()
    def remove_tendon_group(
        name: str = "",
    ) -> str:
        """
        Remove Tendon Group
        """
        try:
            provider.remove_tendon_group(name=name)
            return "remove_tendon_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_tendon_group (执行失败): {e}"

    @mcp.tool()
    def update_distribute_plane_load_type(
        name: str = "",
        new_name: str = "",
        load_type: int = 1,
        point_list: float = None,
        load: float = 0,
        copy_x: str = None,
        copy_y: str = None,
        describe: str = "",
    ) -> str:
        """
        Update Distribute Plane Load Type
        """
        try:
            provider.update_distribute_plane_load_type(name=name, new_name=new_name, load_type=load_type, point_list=point_list, load=load, copy_x=copy_x, copy_y=copy_y, describe=describe)
            return "update_distribute_plane_load_type successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_distribute_plane_load_type (执行失败): {e}"

    @mcp.tool()
    def remove_nodal_force(
        node_id,
        case_name: str = "",
        group_name = "默认荷载组",
    ) -> str:
        """
        Remove Nodal Force
        """
        try:
            provider.remove_nodal_force(node_id=node_id, case_name=case_name, group_name=group_name)
            return "remove_nodal_force successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_nodal_force (执行失败): {e}"

    @mcp.tool()
    def remove_nodal_displacement(
        node_id,
        case_name: str = "",
        group_name = "默认荷载组",
    ) -> str:
        """
        Remove Nodal Displacement
        """
        try:
            provider.remove_nodal_displacement(node_id=node_id, case_name=case_name, group_name=group_name)
            return "remove_nodal_displacement successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_nodal_displacement (执行失败): {e}"

    @mcp.tool()
    def remove_initial_tension_load(
        element_id,
        case_name: str,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Remove Initial Tension Load
        """
        try:
            provider.remove_initial_tension_load(element_id=element_id, case_name=case_name, group_name=group_name)
            return "remove_initial_tension_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_initial_tension_load (执行失败): {e}"

    @mcp.tool()
    def remove_beam_element_load(
        element_id,
        case_name: str = "",
        load_type: int = 1,
        group_name = "默认荷载组",
    ) -> str:
        """
        Remove Beam Element Load
        """
        try:
            provider.remove_beam_element_load(element_id=element_id, case_name=case_name, load_type=load_type, group_name=group_name)
            return "remove_beam_element_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_beam_element_load (执行失败): {e}"

    @mcp.tool()
    def remove_plate_element_load(
        element_id,
        case_name: str,
        load_type: int,
        group_name = "默认荷载组",
    ) -> str:
        """
        Remove Plate Element Load
        """
        try:
            provider.remove_plate_element_load(element_id=element_id, case_name=case_name, load_type=load_type, group_name=group_name)
            return "remove_plate_element_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_plate_element_load (执行失败): {e}"

    @mcp.tool()
    def remove_cable_length_load(
        element_id,
        case_name: str,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Remove Cable Length Load
        """
        try:
            provider.remove_cable_length_load(element_id=element_id, case_name=case_name, group_name=group_name)
            return "remove_cable_length_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_cable_length_load (执行失败): {e}"

    @mcp.tool()
    def remove_distribute_plane_load(
        index: int = -1,
    ) -> str:
        """
        Remove Distribute Plane Load
        """
        try:
            provider.remove_distribute_plane_load(index=index)
            return "remove_distribute_plane_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_distribute_plane_load (执行失败): {e}"

    @mcp.tool()
    def remove_distribute_plane_load_type(
        name: str = -1,
    ) -> str:
        """
        Remove Distribute Plane Load Type
        """
        try:
            provider.remove_distribute_plane_load_type(name=name)
            return "remove_distribute_plane_load_type successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_distribute_plane_load_type (执行失败): {e}"

    @mcp.tool()
    def update_vehicle_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Vehicle Name
        """
        try:
            provider.update_vehicle_name(name=name, new_name=new_name)
            return "update_vehicle_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_vehicle_name (执行失败): {e}"

    @mcp.tool()
    def update_influence_plane_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Influence Plane Name
        """
        try:
            provider.update_influence_plane_name(name=name, new_name=new_name)
            return "update_influence_plane_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_influence_plane_name (执行失败): {e}"

    @mcp.tool()
    def update_lane_line_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Lane Line Name
        """
        try:
            provider.update_lane_line_name(name=name, new_name=new_name)
            return "update_lane_line_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_lane_line_name (执行失败): {e}"

    @mcp.tool()
    def update_node_tandem_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Node Tandem Name
        """
        try:
            provider.update_node_tandem_name(name=name, new_name=new_name)
            return "update_node_tandem_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_node_tandem_name (执行失败): {e}"

    @mcp.tool()
    def update_live_load_case_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Live Load Case Name
        """
        try:
            provider.update_live_load_case_name(name=name, new_name=new_name)
            return "update_live_load_case_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_live_load_case_name (执行失败): {e}"

    @mcp.tool()
    def remove_vehicle(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Vehicle
        """
        try:
            provider.remove_vehicle(index=index, name=name)
            return "remove_vehicle successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_vehicle (执行失败): {e}"

    @mcp.tool()
    def remove_node_tandem(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Node Tandem
        """
        try:
            provider.remove_node_tandem(index=index, name=name)
            return "remove_node_tandem successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_node_tandem (执行失败): {e}"

    @mcp.tool()
    def remove_influence_plane(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Influence Plane
        """
        try:
            provider.remove_influence_plane(index=index, name=name)
            return "remove_influence_plane successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_influence_plane (执行失败): {e}"

    @mcp.tool()
    def remove_lane_line(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Lane Line
        """
        try:
            provider.remove_lane_line(index=index, name=name)
            return "remove_lane_line successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_lane_line (执行失败): {e}"

    @mcp.tool()
    def remove_live_load_case(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Live Load Case
        """
        try:
            provider.remove_live_load_case(index=index, name=name)
            return "remove_live_load_case successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_live_load_case (执行失败): {e}"

    @mcp.tool()
    def update_load_to_mass(
        name: str = "",
        factor: float = 1,
    ) -> str:
        """
        Update Load To Mass
        """
        try:
            provider.update_load_to_mass(name=name, factor=factor)
            return "update_load_to_mass successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_load_to_mass (执行失败): {e}"

    @mcp.tool()
    def update_nodal_mass(
        node_id: int,
        new_node_id: int = -1,
        mass_info: float = None,
    ) -> str:
        """
        Update Nodal Mass
        """
        try:
            provider.update_nodal_mass(node_id=node_id, new_node_id=new_node_id, mass_info=mass_info)
            return "update_nodal_mass successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_nodal_mass (执行失败): {e}"

    @mcp.tool()
    def update_boundary_element_property_name(
        name: str = "",
        new_name: str = "",
    ) -> str:
        """
        Update Boundary Element Property Name
        """
        try:
            provider.update_boundary_element_property_name(name=name, new_name=new_name)
            return "update_boundary_element_property_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_boundary_element_property_name (执行失败): {e}"

    @mcp.tool()
    def update_boundary_element_link(
        index: int,
        property_name: str = "",
        node_i: int = 1,
        node_j: int = 2,
        beta: float = 0,
        node_system: int = 0,
        group_name: str = "默认边界组",
    ) -> str:
        """
        Update Boundary Element Link
        """
        try:
            provider.update_boundary_element_link(index=index, property_name=property_name, node_i=node_i, node_j=node_j, beta=beta, node_system=node_system, group_name=group_name)
            return "update_boundary_element_link successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_boundary_element_link (执行失败): {e}"

    @mcp.tool()
    def update_time_history_case_name(
        name: str = "",
        new_name: str = "",
    ) -> str:
        """
        Update Time History Case Name
        """
        try:
            provider.update_time_history_case_name(name=name, new_name=new_name)
            return "update_time_history_case_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_time_history_case_name (执行失败): {e}"

    @mcp.tool()
    def update_time_history_function_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Time History Function Name
        """
        try:
            provider.update_time_history_function_name(name=name, new_name=new_name)
            return "update_time_history_function_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_time_history_function_name (执行失败): {e}"

    @mcp.tool()
    def update_nodal_dynamic_load(
        index: int = -1,
        node_id: int = 1,
        case_name: str = "",
        function_name: str = "",
        direction: int = 1,
        factor: float = 1,
        time: float = 1,
    ) -> str:
        """
        Update Nodal Dynamic Load
        """
        try:
            provider.update_nodal_dynamic_load(index=index, node_id=node_id, case_name=case_name, function_name=function_name, direction=direction, factor=factor, time=time)
            return "update_nodal_dynamic_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_nodal_dynamic_load (执行失败): {e}"

    @mcp.tool()
    def update_ground_motion(
        index: int,
        case_name: str = "",
        info_x: float = None,
        info_y: float = None,
        info_z: float = None,
    ) -> str:
        """
        Update Ground Motion
        """
        try:
            provider.update_ground_motion(index=index, case_name=case_name, info_x=info_x, info_y=info_y, info_z=info_z)
            return "update_ground_motion successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_ground_motion (执行失败): {e}"

    @mcp.tool()
    def remove_time_history_load_case(
        name: str,
    ) -> str:
        """
        Remove Time History Load Case
        """
        try:
            provider.remove_time_history_load_case(name=name)
            return "remove_time_history_load_case successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_time_history_load_case (执行失败): {e}"

    @mcp.tool()
    def remove_time_history_function(
        ids = None,
        name: str = "",
    ) -> str:
        """
        Remove Time History Function
        """
        try:
            provider.remove_time_history_function(ids=ids, name=name)
            return "remove_time_history_function successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_time_history_function (执行失败): {e}"

    @mcp.tool()
    def remove_load_to_mass(
        name: str = "",
    ) -> str:
        """
        Remove Load To Mass
        """
        try:
            provider.remove_load_to_mass(name=name)
            return "remove_load_to_mass successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_load_to_mass (执行失败): {e}"

    @mcp.tool()
    def remove_nodal_mass(
        node_id = None,
    ) -> str:
        """
        Remove Nodal Mass
        """
        try:
            provider.remove_nodal_mass(node_id=node_id)
            return "remove_nodal_mass successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_nodal_mass (执行失败): {e}"

    @mcp.tool()
    def remove_boundary_element_property(
        name: str,
    ) -> str:
        """
        Remove Boundary Element Property
        """
        try:
            provider.remove_boundary_element_property(name=name)
            return "remove_boundary_element_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_boundary_element_property (执行失败): {e}"

    @mcp.tool()
    def remove_boundary_element_link(
        ids = None,
    ) -> str:
        """
        Remove Boundary Element Link
        """
        try:
            provider.remove_boundary_element_link(ids=ids)
            return "remove_boundary_element_link successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_boundary_element_link (执行失败): {e}"

    @mcp.tool()
    def remove_ground_motion(
        name: str,
    ) -> str:
        """
        Remove Ground Motion
        """
        try:
            provider.remove_ground_motion(name=name)
            return "remove_ground_motion successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_ground_motion (执行失败): {e}"

    @mcp.tool()
    def remove_nodal_dynamic_load(
        ids = None,
    ) -> str:
        """
        Remove Nodal Dynamic Load
        """
        try:
            provider.remove_nodal_dynamic_load(ids=ids)
            return "remove_nodal_dynamic_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_nodal_dynamic_load (执行失败): {e}"

    @mcp.tool()
    def update_spectrum_function_name(
        name: str = "",
        new_name: str = "",
    ) -> str:
        """
        Update Spectrum Function Name
        """
        try:
            provider.update_spectrum_function_name(name=name, new_name=new_name)
            return "update_spectrum_function_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_spectrum_function_name (执行失败): {e}"

    @mcp.tool()
    def update_spectrum_case_name(
        name: str,
        new_name: str = "",
    ) -> str:
        """
        Update Spectrum Case Name
        """
        try:
            provider.update_spectrum_case_name(name=name, new_name=new_name)
            return "update_spectrum_case_name successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_spectrum_case_name (执行失败): {e}"

    @mcp.tool()
    def remove_spectrum_case(
        name: str,
    ) -> str:
        """
        Remove Spectrum Case
        """
        try:
            provider.remove_spectrum_case(name=name)
            return "remove_spectrum_case successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_spectrum_case (执行失败): {e}"

    @mcp.tool()
    def remove_spectrum_function(
        ids = None,
        name: str = "",
    ) -> str:
        """
        Remove Spectrum Function
        """
        try:
            provider.remove_spectrum_function(ids=ids, name=name)
            return "remove_spectrum_function successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_spectrum_function (执行失败): {e}"

    @mcp.tool()
    def remove_element_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Element Temperature
        """
        try:
            provider.remove_element_temperature(element_id=element_id, case_name=case_name)
            return "remove_element_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_element_temperature (执行失败): {e}"

    @mcp.tool()
    def remove_top_plate_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Top Plate Temperature
        """
        try:
            provider.remove_top_plate_temperature(element_id=element_id, case_name=case_name)
            return "remove_top_plate_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_top_plate_temperature (执行失败): {e}"

    @mcp.tool()
    def remove_beam_section_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Beam Section Temperature
        """
        try:
            provider.remove_beam_section_temperature(element_id=element_id, case_name=case_name)
            return "remove_beam_section_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_beam_section_temperature (执行失败): {e}"

    @mcp.tool()
    def remove_gradient_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Gradient Temperature
        """
        try:
            provider.remove_gradient_temperature(element_id=element_id, case_name=case_name)
            return "remove_gradient_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_gradient_temperature (执行失败): {e}"

    @mcp.tool()
    def remove_custom_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Custom Temperature
        """
        try:
            provider.remove_custom_temperature(element_id=element_id, case_name=case_name)
            return "remove_custom_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_custom_temperature (执行失败): {e}"

    @mcp.tool()
    def remove_index_temperature(
        element_id,
        case_name: str,
    ) -> str:
        """
        Remove Index Temperature
        """
        try:
            provider.remove_index_temperature(element_id=element_id, case_name=case_name)
            return "remove_index_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_index_temperature (执行失败): {e}"

    @mcp.tool()
    def update_deviation_parameter(
        name: str = "",
        new_name: str = "",
        element_type: int = 1,
        parameters: float = None,
    ) -> str:
        """
        Update Deviation Parameter
        """
        try:
            provider.update_deviation_parameter(name=name, new_name=new_name, element_type=element_type, parameters=parameters)
            return "update_deviation_parameter successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_deviation_parameter (执行失败): {e}"

    @mcp.tool()
    def remove_deviation_parameter(
        name: str,
        para_type: int = 1,
    ) -> str:
        """
        Remove Deviation Parameter
        """
        try:
            provider.remove_deviation_parameter(name=name, para_type=para_type)
            return "remove_deviation_parameter successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_deviation_parameter (执行失败): {e}"

    @mcp.tool()
    def remove_deviation_load(
        element_id,
        case_name: str,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Remove Deviation Load
        """
        try:
            provider.remove_deviation_load(element_id=element_id, case_name=case_name, group_name=group_name)
            return "remove_deviation_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_deviation_load (执行失败): {e}"

    @mcp.tool()
    def update_weight_stage(
        name: str = "",
        structure_group_name: str = "",
        weight_stage_id: int = 1,
    ) -> str:
        """
        Update Weight Stage
        """
        try:
            provider.update_weight_stage(name=name, structure_group_name=structure_group_name, weight_stage_id=weight_stage_id)
            return "update_weight_stage successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_weight_stage (执行失败): {e}"

    @mcp.tool()
    def update_construction_stage_id(
        stage_id: int,
        target_id: int = 3,
    ) -> str:
        """
        Update Construction Stage Id
        """
        try:
            provider.update_construction_stage_id(stage_id=stage_id, target_id=target_id)
            return "update_construction_stage_id successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_construction_stage_id (执行失败): {e}"

    @mcp.tool()
    def update_all_stage_setting_type(
        setting_type: int = 1,
    ) -> str:
        """
        Update All Stage Setting Type
        """
        try:
            provider.update_all_stage_setting_type(setting_type=setting_type)
            return "update_all_stage_setting_type successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_all_stage_setting_type (执行失败): {e}"

    @mcp.tool()
    def update_section_connection_stage(
        name: str,
        new_name = "",
        sec_id: int = 1,
        element_id = None,
        stage_name = "",
        age: float = 0,
        weight_type: int = 0,
    ) -> str:
        """
        Update Section Connection Stage
        """
        try:
            provider.update_section_connection_stage(name=name, new_name=new_name, sec_id=sec_id, element_id=element_id, stage_name=stage_name, age=age, weight_type=weight_type)
            return "update_section_connection_stage successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_section_connection_stage (执行失败): {e}"

    @mcp.tool()
    def remove_section_connection_stage(
        name: str,
    ) -> str:
        """
        Remove Section Connection Stage
        """
        try:
            provider.remove_section_connection_stage(name=name)
            return "remove_section_connection_stage successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_section_connection_stage (执行失败): {e}"

    @mcp.tool()
    def update_global_setting(
        solver_type: int = 0,
        calculation_type: int = 2,
        thread_count: int = 12,
    ) -> str:
        """
        Update Global Setting
        """
        try:
            provider.update_global_setting(solver_type=solver_type, calculation_type=calculation_type, thread_count=thread_count)
            return "update_global_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_global_setting (执行失败): {e}"

    @mcp.tool()
    def update_live_load_setting(
        lateral_spacing: float = 0.1,
        vertical_spacing: float = 1,
        damper_calc_type: int = -1,
        displacement_calc_type: int = -1,
        force_calc_type: int = -1,
        reaction_calc_type: int = -1,
        link_calc_type: int = -1,
        constrain_calc_type: int = -1,
        eccentricity: float = 0.0,
        displacement_track: bool = False,
        force_track: bool = False,
        reaction_track: bool = False,
        link_track: bool = False,
        constrain_track: bool = False,
        damper_groups: str = None,
        displacement_groups: str = None,
        force_groups: str = None,
        reaction_groups: str = None,
        link_groups: str = None,
        constrain_groups: str = None,
    ) -> str:
        """
        Update Live Load Setting
        """
        try:
            provider.update_live_load_setting(lateral_spacing=lateral_spacing, vertical_spacing=vertical_spacing, damper_calc_type=damper_calc_type, displacement_calc_type=displacement_calc_type, force_calc_type=force_calc_type, reaction_calc_type=reaction_calc_type, link_calc_type=link_calc_type, constrain_calc_type=constrain_calc_type, eccentricity=eccentricity, displacement_track=displacement_track, force_track=force_track, reaction_track=reaction_track, link_track=link_track, constrain_track=constrain_track, damper_groups=damper_groups, displacement_groups=displacement_groups, force_groups=force_groups, reaction_groups=reaction_groups, link_groups=link_groups, constrain_groups=constrain_groups)
            return "update_live_load_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_live_load_setting (执行失败): {e}"

    @mcp.tool()
    def update_non_linear_setting(
        non_linear_type: int = 1,
        non_linear_method: int = 1,
        max_loading_steps: int = 1,
        max_iteration_times: int = 30,
        accuracy_of_displacement: float = 0.0001,
        accuracy_of_force: float = 0.0001,
    ) -> str:
        """
        Update Non Linear Setting
        """
        try:
            provider.update_non_linear_setting(non_linear_type=non_linear_type, non_linear_method=non_linear_method, max_loading_steps=max_loading_steps, max_iteration_times=max_iteration_times, accuracy_of_displacement=accuracy_of_displacement, accuracy_of_force=accuracy_of_force)
            return "update_non_linear_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_non_linear_setting (执行失败): {e}"

    @mcp.tool()
    def update_operation_stage_setting(
        do_analysis: bool = True,
        final_stage: str = "",
        static_load_cases: str = None,
        sink_load_cases: str = None,
        live_load_cases: str = None,
    ) -> str:
        """
        Update Operation Stage Setting
        """
        try:
            provider.update_operation_stage_setting(do_analysis=do_analysis, final_stage=final_stage, static_load_cases=static_load_cases, sink_load_cases=sink_load_cases, live_load_cases=live_load_cases)
            return "update_operation_stage_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_operation_stage_setting (执行失败): {e}"

    @mcp.tool()
    def update_response_spectrum_setting(
        do_analysis: bool = True,
        kind: int = 1,
        by_mode: bool = False,
        damping_ratio: float = 0.05,
    ) -> str:
        """
        Update Response Spectrum Setting
        """
        try:
            provider.update_response_spectrum_setting(do_analysis=do_analysis, kind=kind, by_mode=by_mode, damping_ratio=damping_ratio)
            return "update_response_spectrum_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_response_spectrum_setting (执行失败): {e}"

    @mcp.tool()
    def update_time_history_setting(
        do_analysis: bool = True,
        output_all: bool = True,
        groups: str = None,
    ) -> str:
        """
        Update Time History Setting
        """
        try:
            provider.update_time_history_setting(do_analysis=do_analysis, output_all=output_all, groups=groups)
            return "update_time_history_setting successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_time_history_setting (执行失败): {e}"

    @mcp.tool()
    def remove_check_load_combine(
        index: int = -1,
        name: str = "",
    ) -> str:
        """
        Remove Check Load Combine
        """
        try:
            provider.remove_check_load_combine(index=index, name=name)
            return "remove_check_load_combine successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_check_load_combine (执行失败): {e}"

    @mcp.tool()
    def remove_concrete_check_case(
        name: str = "",
    ) -> str:
        """
        Remove Concrete Check Case
        """
        try:
            provider.remove_concrete_check_case(name=name)
            return "remove_concrete_check_case successfully executed (执行成功)"
        except Exception as e:
            return f"Error in remove_concrete_check_case (执行失败): {e}"

    @mcp.tool()
    def update_element_steel_hoop(
        sec_id: int,
        bar_data: int,
    ) -> str:
        """
        Update Element Steel Hoop
        """
        try:
            provider.update_element_steel_hoop(sec_id=sec_id, bar_data=bar_data)
            return "update_element_steel_hoop successfully executed (执行成功)"
        except Exception as e:
            return f"Error in update_element_steel_hoop (执行失败): {e}"


    @mcp.tool()
    def add_single_section(
        index: int = -1,
        name: str = "",
        sec_type: str = "矩形",
        sec_data: dict = None,
    ) -> str:
        """
        Add Single Section
        """
        try:
            res = provider.add_single_section(index=index, name=name, sec_type=sec_type, sec_data=sec_data)
            if res is not None:
                return f"add_single_section successfully executed. Result:\n{res}"
            return "add_single_section successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_single_section (执行失败): {e}"

    @mcp.tool()
    def add_elements_to_tapper_section_group(
        name: str,
        ids = None,
    ) -> str:
        """
        Add Elements To Tapper Section Group
        """
        try:
            res = provider.add_elements_to_tapper_section_group(name=name, ids=ids)
            if res is not None:
                return f"add_elements_to_tapper_section_group successfully executed. Result:\n{res}"
            return "add_elements_to_tapper_section_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_elements_to_tapper_section_group (执行失败): {e}"

    @mcp.tool()
    def add_tapper_section_from_group(
        name: str = "",
    ) -> str:
        """
        Add Tapper Section From Group
        """
        try:
            res = provider.add_tapper_section_from_group(name=name)
            if res is not None:
                return f"add_tapper_section_from_group successfully executed. Result:\n{res}"
            return "add_tapper_section_from_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_tapper_section_from_group (执行失败): {e}"

    @mcp.tool()
    def add_general_elastic_support_property(
        name: str = "",
        data_matrix: float = None,
    ) -> str:
        """
        Add General Elastic Support Property
        """
        try:
            res = provider.add_general_elastic_support_property(name=name, data_matrix=data_matrix)
            if res is not None:
                return f"add_general_elastic_support_property successfully executed. Result:\n{res}"
            return "add_general_elastic_support_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_general_elastic_support_property (执行失败): {e}"

    @mcp.tool()
    def add_general_elastic_support(
        node_id = None,
        property_name: str = "",
        group_name: str = "默认边界组",
    ) -> str:
        """
        Add General Elastic Support
        """
        try:
            res = provider.add_general_elastic_support(node_id=node_id, property_name=property_name, group_name=group_name)
            if res is not None:
                return f"add_general_elastic_support successfully executed. Result:\n{res}"
            return "add_general_elastic_support successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_general_elastic_support (执行失败): {e}"

    @mcp.tool()
    def add_master_slave_links(
        node_ids: int = None,
        boundary_info: bool = None,
        group_name: str = "默认边界组",
    ) -> str:
        """
        Add Master Slave Links
        """
        try:
            res = provider.add_master_slave_links(node_ids=node_ids, boundary_info=boundary_info, group_name=group_name)
            if res is not None:
                return f"add_master_slave_links successfully executed. Result:\n{res}"
            return "add_master_slave_links successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_master_slave_links (执行失败): {e}"

    @mcp.tool()
    def add_node_axis(
        node_id: int,
        input_type: int = 1,
        coord_info: float = None,
        angle_info: float = None,
    ) -> str:
        """
        Add Node Axis
        """
        try:
            res = provider.add_node_axis(node_id=node_id, input_type=input_type, coord_info=coord_info, angle_info=angle_info)
            if res is not None:
                return f"add_node_axis successfully executed. Result:\n{res}"
            return "add_node_axis successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_node_axis (执行失败): {e}"

    @mcp.tool()
    def add_tendon_group(
        name: str = "",
    ) -> str:
        """
        Add Tendon Group
        """
        try:
            res = provider.add_tendon_group(name=name)
            if res is not None:
                return f"add_tendon_group successfully executed. Result:\n{res}"
            return "add_tendon_group successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_tendon_group (执行失败): {e}"

    @mcp.tool()
    def add_distribute_plane_load_type(
        name: str,
        load_type: int,
        point_list: float,
        load: float = 0,
        copy_x: str = None,
        copy_y: str = None,
        describe: str = "",
    ) -> str:
        """
        Add Distribute Plane Load Type
        """
        try:
            res = provider.add_distribute_plane_load_type(name=name, load_type=load_type, point_list=point_list, load=load, copy_x=copy_x, copy_y=copy_y, describe=describe)
            if res is not None:
                return f"add_distribute_plane_load_type successfully executed. Result:\n{res}"
            return "add_distribute_plane_load_type successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_distribute_plane_load_type (执行失败): {e}"

    @mcp.tool()
    def add_user_vehicle(
        name: str,
        load_type: str = "车辆荷载",
        p: float = 270000,
        q: float = 10500,
        dis: float = None,
        load_length: float = 500,
        n: int = 6,
        empty_load: float = 90000,
        width: float = 1.5,
        wheelbase: float = 1.8,
        min_dis: float = 1.5,
    ) -> str:
        """
        Add User Vehicle
        """
        try:
            res = provider.add_user_vehicle(name=name, load_type=load_type, p=p, q=q, dis=dis, load_length=load_length, n=n, empty_load=empty_load, width=width, wheelbase=wheelbase, min_dis=min_dis)
            if res is not None:
                return f"add_user_vehicle successfully executed. Result:\n{res}"
            return "add_user_vehicle successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_user_vehicle (执行失败): {e}"

    @mcp.tool()
    def add_node_tandem(
        name: str,
        node_ids: int,
        order_by_x: bool = True,
    ) -> str:
        """
        Add Node Tandem
        """
        try:
            res = provider.add_node_tandem(name=name, node_ids=node_ids, order_by_x=order_by_x)
            if res is not None:
                return f"add_node_tandem successfully executed. Result:\n{res}"
            return "add_node_tandem successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_node_tandem (执行失败): {e}"

    @mcp.tool()
    def add_influence_plane(
        name: str,
        tandem_names: str,
    ) -> str:
        """
        Add Influence Plane
        """
        try:
            res = provider.add_influence_plane(name=name, tandem_names=tandem_names)
            if res is not None:
                return f"add_influence_plane successfully executed. Result:\n{res}"
            return "add_influence_plane successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_influence_plane (执行失败): {e}"

    @mcp.tool()
    def add_car_relative_factor(
        name: str,
        code_index: int,
        cross_factors: float = None,
        longitude_factor: float = -1,
        impact_factor: float = -1,
        frequency: float = 14,
    ) -> str:
        """
        Add Car Relative Factor
        """
        try:
            res = provider.add_car_relative_factor(name=name, code_index=code_index, cross_factors=cross_factors, longitude_factor=longitude_factor, impact_factor=impact_factor, frequency=frequency)
            if res is not None:
                return f"add_car_relative_factor successfully executed. Result:\n{res}"
            return "add_car_relative_factor successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_car_relative_factor (执行失败): {e}"

    @mcp.tool()
    def add_train_relative_factor(
        name: str,
        code_index: int = 1,
        cross_factors: float = None,
        calc_fatigue: bool = False,
        line_count: int = 0,
        longitude_factor: float = -1,
        impact_factor: float = -1,
        fatigue_factor: float = -1,
        bridge_kind: int = 0,
        fill_thick: float = 0.5,
        rise: float = 1.5,
        calc_length: float = 50,
    ) -> str:
        """
        Add Train Relative Factor
        """
        try:
            res = provider.add_train_relative_factor(name=name, code_index=code_index, cross_factors=cross_factors, calc_fatigue=calc_fatigue, line_count=line_count, longitude_factor=longitude_factor, impact_factor=impact_factor, fatigue_factor=fatigue_factor, bridge_kind=bridge_kind, fill_thick=fill_thick, rise=rise, calc_length=calc_length)
            if res is not None:
                return f"add_train_relative_factor successfully executed. Result:\n{res}"
            return "add_train_relative_factor successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_train_relative_factor (执行失败): {e}"

    @mcp.tool()
    def add_metro_relative_factor(
        name: str,
        cross_factors: float = None,
        longitude_factor: float = -1,
        impact_factor: float = -1,
    ) -> str:
        """
        Add Metro Relative Factor
        """
        try:
            res = provider.add_metro_relative_factor(name=name, cross_factors=cross_factors, longitude_factor=longitude_factor, impact_factor=impact_factor)
            if res is not None:
                return f"add_metro_relative_factor successfully executed. Result:\n{res}"
            return "add_metro_relative_factor successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_metro_relative_factor (执行失败): {e}"

    @mcp.tool()
    def add_boundary_element_property(
        index: int = -1,
        name: str = "",
        kind: str = "钩",
        info_x: float = None,
        info_y: float = None,
        info_z: float = None,
        weight: float = 0,
        pin_stiffness: float = 0,
        pin_yield: float = 0,
        description: str = "",
    ) -> str:
        """
        Add Boundary Element Property
        """
        try:
            res = provider.add_boundary_element_property(index=index, name=name, kind=kind, info_x=info_x, info_y=info_y, info_z=info_z, weight=weight, pin_stiffness=pin_stiffness, pin_yield=pin_yield, description=description)
            if res is not None:
                return f"add_boundary_element_property successfully executed. Result:\n{res}"
            return "add_boundary_element_property successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_boundary_element_property (执行失败): {e}"

    @mcp.tool()
    def add_boundary_element_link(
        index: int = -1,
        property_name: str = "",
        node_i: int = 1,
        node_j: int = 2,
        beta: float = 0,
        node_system: int = 0,
        group_name: str = "默认边界组",
    ) -> str:
        """
        Add Boundary Element Link
        """
        try:
            res = provider.add_boundary_element_link(index=index, property_name=property_name, node_i=node_i, node_j=node_j, beta=beta, node_system=node_system, group_name=group_name)
            if res is not None:
                return f"add_boundary_element_link successfully executed. Result:\n{res}"
            return "add_boundary_element_link successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_boundary_element_link (执行失败): {e}"

    @mcp.tool()
    def add_nodal_dynamic_load(
        index: int = -1,
        node_id: int = 1,
        case_name: str = "",
        function_name: str = "",
        force_type: int = 1,
        factor: float = 1,
        time: float = 1,
    ) -> str:
        """
        Add Nodal Dynamic Load
        """
        try:
            res = provider.add_nodal_dynamic_load(index=index, node_id=node_id, case_name=case_name, function_name=function_name, force_type=force_type, factor=factor, time=time)
            if res is not None:
                return f"add_nodal_dynamic_load successfully executed. Result:\n{res}"
            return "add_nodal_dynamic_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_nodal_dynamic_load (执行失败): {e}"

    @mcp.tool()
    def add_ground_motion(
        case_name: str = "",
        info_x: float = None,
        info_y: float = None,
        info_z: float = None,
    ) -> str:
        """
        Add Ground Motion
        """
        try:
            res = provider.add_ground_motion(case_name=case_name, info_x=info_x, info_y=info_y, info_z=info_z)
            if res is not None:
                return f"add_ground_motion successfully executed. Result:\n{res}"
            return "add_ground_motion successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_ground_motion (执行失败): {e}"

    @mcp.tool()
    def add_vehicle_dynamic_load(
        node_ids = None,
        function_name: str = "",
        case_name: str = "",
        kind: int = 1,
        speed_kmh: float = 120,
        braking: bool = False,
        braking_a: float = 0.8,
        braking_d: float = 0,
        time: float = 0,
        direction: int = 6,
        gap: float = 14,
        factor: float = 1,
        vehicle_info_kn: float = None,
    ) -> str:
        """
        Add Vehicle Dynamic Load
        """
        try:
            res = provider.add_vehicle_dynamic_load(node_ids=node_ids, function_name=function_name, case_name=case_name, kind=kind, speed_kmh=speed_kmh, braking=braking, braking_a=braking_a, braking_d=braking_d, time=time, direction=direction, gap=gap, factor=factor, vehicle_info_kn=vehicle_info_kn)
            if res is not None:
                return f"add_vehicle_dynamic_load successfully executed. Result:\n{res}"
            return "add_vehicle_dynamic_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_vehicle_dynamic_load (执行失败): {e}"

    @mcp.tool()
    def add_index_temperature(
        element_id,
        case_name: str = "",
        temperature: float = 0,
        index: float = 1,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Add Index Temperature
        """
        try:
            res = provider.add_index_temperature(element_id=element_id, case_name=case_name, temperature=temperature, index=index, group_name=group_name)
            if res is not None:
                return f"add_index_temperature successfully executed. Result:\n{res}"
            return "add_index_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_index_temperature (执行失败): {e}"

    @mcp.tool()
    def add_top_plate_temperature(
        element_id,
        case_name: str = "",
        temperature: float = 0,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Add Top Plate Temperature
        """
        try:
            res = provider.add_top_plate_temperature(element_id=element_id, case_name=case_name, temperature=temperature, group_name=group_name)
            if res is not None:
                return f"add_top_plate_temperature successfully executed. Result:\n{res}"
            return "add_top_plate_temperature successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_top_plate_temperature (执行失败): {e}"

    @mcp.tool()
    def add_deviation_parameter(
        name: str = "",
        parameters: float = None,
    ) -> str:
        """
        Add Deviation Parameter
        """
        try:
            res = provider.add_deviation_parameter(name=name, parameters=parameters)
            if res is not None:
                return f"add_deviation_parameter successfully executed. Result:\n{res}"
            return "add_deviation_parameter successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_deviation_parameter (执行失败): {e}"

    @mcp.tool()
    def add_deviation_load(
        element_id,
        case_name: str = "",
        parameters: str = None,
        group_name: str = "默认荷载组",
    ) -> str:
        """
        Add Deviation Load
        """
        try:
            res = provider.add_deviation_load(element_id=element_id, case_name=case_name, parameters=parameters, group_name=group_name)
            if res is not None:
                return f"add_deviation_load successfully executed. Result:\n{res}"
            return "add_deviation_load successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_deviation_load (执行失败): {e}"

    @mcp.tool()
    def add_section_connection_stage(
        name: str,
        sec_id: int,
        element_id = None,
        stage_name = "",
        age: float = 0,
        weight_type: int = 0,
    ) -> str:
        """
        Add Section Connection Stage
        """
        try:
            res = provider.add_section_connection_stage(name=name, sec_id=sec_id, element_id=element_id, stage_name=stage_name, age=age, weight_type=weight_type)
            if res is not None:
                return f"add_section_connection_stage successfully executed. Result:\n{res}"
            return "add_section_connection_stage successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_section_connection_stage (执行失败): {e}"

    @mcp.tool()
    def add_element_to_connection_stage(
        element_id,
        name: str,
    ) -> str:
        """
        Add Element To Connection Stage
        """
        try:
            res = provider.add_element_to_connection_stage(element_id=element_id, name=name)
            if res is not None:
                return f"add_element_to_connection_stage successfully executed. Result:\n{res}"
            return "add_element_to_connection_stage successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_element_to_connection_stage (执行失败): {e}"

    @mcp.tool()
    def plot_composite_beam_force(
        file_path: str = "",
        stage_id: int = 1,
        case_name: str = "合计",
        show_increment: bool = False,
        envelop_type: int = 1,
        mat_type: int = 1,
        component: int = 1,
        show_line_chart: bool = True,
        line_scale: float = 1.0,
        flip_plot: bool = True,
        show_deformed: bool = True,
        deformed_actual: bool = False,
        deformed_scale: float = 1.0,
        show_number: bool = False,
        text_rotation: int = 0,
        max_min_kind: int = 1,
        show_legend: bool = True,
        digital_count: int = 3,
        text_exponential: bool = True,
        show_undeformed: bool = False,
        position: int = 1,
    ) -> str:
        """
        Plot Composite Beam Force
        """
        try:
            res = provider.plot_composite_beam_force(file_path=file_path, stage_id=stage_id, case_name=case_name, show_increment=show_increment, envelop_type=envelop_type, mat_type=mat_type, component=component, show_line_chart=show_line_chart, line_scale=line_scale, flip_plot=flip_plot, show_deformed=show_deformed, deformed_actual=deformed_actual, deformed_scale=deformed_scale, show_number=show_number, text_rotation=text_rotation, max_min_kind=max_min_kind, show_legend=show_legend, digital_count=digital_count, text_exponential=text_exponential, show_undeformed=show_undeformed, position=position)
            if res is not None:
                return f"plot_composite_beam_force successfully executed. Result:\n{res}"
            return "plot_composite_beam_force successfully executed (执行成功)"
        except Exception as e:
            return f"Error in plot_composite_beam_force (执行失败): {e}"

    @mcp.tool()
    def plot_composite_beam_stress(
        file_path: str = "",
        stage_id: int = 1,
        case_name: str = "合计",
        show_increment: bool = False,
        envelop_type: int = 1,
        mat_type: int = 0,
        component: int = 1,
        show_line_chart: bool = True,
        line_scale: float = 1.0,
        flip_plot: bool = True,
        show_deformed: bool = True,
        deformed_actual: bool = False,
        deformed_scale: float = 1.0,
        show_number: bool = False,
        text_rotation: int = 0,
        max_min_kind: int = 1,
        show_legend: bool = True,
        digital_count: int = 3,
        text_exponential: bool = True,
        show_undeformed: bool = False,
        position: int = 1,
    ) -> str:
        """
        Plot Composite Beam Stress
        """
        try:
            res = provider.plot_composite_beam_stress(file_path=file_path, stage_id=stage_id, case_name=case_name, show_increment=show_increment, envelop_type=envelop_type, mat_type=mat_type, component=component, show_line_chart=show_line_chart, line_scale=line_scale, flip_plot=flip_plot, show_deformed=show_deformed, deformed_actual=deformed_actual, deformed_scale=deformed_scale, show_number=show_number, text_rotation=text_rotation, max_min_kind=max_min_kind, show_legend=show_legend, digital_count=digital_count, text_exponential=text_exponential, show_undeformed=show_undeformed, position=position)
            if res is not None:
                return f"plot_composite_beam_stress successfully executed. Result:\n{res}"
            return "plot_composite_beam_stress successfully executed (执行成功)"
        except Exception as e:
            return f"Error in plot_composite_beam_stress (执行失败): {e}"

    @mcp.tool()
    def add_check_material(
        name: str = "",
        properties: float = None,
        model: int = 1,
        parameter_data: float = None,
        curve_data: float = None,
        user_material: int = 1,
        user_standard: int = 1,
    ) -> str:
        """
        Add Check Material
        """
        try:
            res = provider.add_check_material(name=name, properties=properties, model=model, parameter_data=parameter_data, curve_data=curve_data, user_material=user_material, user_standard=user_standard)
            if res is not None:
                return f"add_check_material successfully executed. Result:\n{res}"
            return "add_check_material successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_check_material (执行失败): {e}"

    @mcp.tool()
    def add_part_parameter_reinforcement(
        sec_id: int,
        position: int = 0,
        data_info: float = None,
    ) -> str:
        """
        Add Part Parameter Reinforcement
        """
        try:
            res = provider.add_part_parameter_reinforcement(sec_id=sec_id, position=position, data_info=data_info)
            if res is not None:
                return f"add_part_parameter_reinforcement successfully executed. Result:\n{res}"
            return "add_part_parameter_reinforcement successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_part_parameter_reinforcement (执行失败): {e}"

    @mcp.tool()
    def add_reinforcement_by_point(
        sec_id: int,
        position: int = 0,
        bar_data: int = None,
    ) -> str:
        """
        Add Reinforcement By Point
        """
        try:
            res = provider.add_reinforcement_by_point(sec_id=sec_id, position=position, bar_data=bar_data)
            if res is not None:
                return f"add_reinforcement_by_point successfully executed. Result:\n{res}"
            return "add_reinforcement_by_point successfully executed (执行成功)"
        except Exception as e:
            return f"Error in add_reinforcement_by_point (执行失败): {e}"

