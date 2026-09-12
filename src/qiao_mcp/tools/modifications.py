"""
MCP Modification Tools — update/modify existing model entities.
桥梁模型修改类工具 (基于 qtmodel 2.5.0 API)

Provides tools to modify existing nodes, elements, materials,
sections, boundaries, and structure groups.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError


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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error initializing model (初始化模型失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error saving model file (保存模型文件失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error opening model file (打开模型文件失败): {e}") from e

    @mcp.tool()
    def remove_unused_sections() -> str:
        """
        Clean up and remove all unused sections from the model (删除未使用的截面).
        """
        try:
            provider.remove_unused_sections()
            return "Successfully removed unused sections (成功清除未使用的截面)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing unused sections (清除未使用的截面失败): {e}") from e

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
        Modify an existing node's coordinates and/or ID (修改节点坐标或编号).

        Writes to the model and refreshes it. Partial updates are safe: the
        underlying qtmodel API overwrites all three coordinates on every call,
        so this tool first re-reads the node's current position and fills in
        whichever of x/y/z you left out. That costs one extra model query, and
        it fails if the node does not exist.

        When to use vs. siblings: coordinates (with or without a new ID) here;
        renumbering only → update_node_id (no read-back, cheaper); shifting
        nodes by a relative offset rather than to absolute coordinates →
        move_nodes; renumbering many nodes → renumber_nodes.

        (写模型并刷新。部分更新是安全的：底层 qtmodel API 每次调用都会整体覆盖三个
        坐标，因此本工具会先读回节点当前位置、补齐你没传的 x/y/z——代价是多一次模型
        查询，且节点不存在时会失败。选型：改坐标（可同时改编号）用本工具；只改编号用
        update_node_id（无需读回、更省）；按相对偏移平移用 move_nodes；批量改号用
        renumber_nodes。)

        Args:
            node_id: Existing node ID to modify (待修改的节点编号)
            x: New absolute X coordinate, leave None to keep unchanged
               (新X坐标，绝对值；不修改则留空)
            y: New absolute Y coordinate, leave None to keep unchanged
               (新Y坐标，绝对值；不修改则留空)
            z: New absolute Z coordinate, leave None to keep unchanged
               (新Z坐标，绝对值；不修改则留空)
            new_id: New node ID, -1 to keep unchanged (新节点编号，-1表示不修改编号)

        Example:
            update_node(1, z=-1.5)  # Move node 1 down to z=-1.5
        """
        try:
            kwargs: dict[str, Any] = {"node_id": node_id, "new_id": new_id}
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating node (修改节点失败): {e}") from e

    @mcp.tool()
    def update_node_id(node_id: int, new_id: int) -> str:
        """
        Renumber one node, leaving its coordinates untouched (仅修改节点编号).

        Writes to the model and refreshes it. Only the ID changes — this is the
        narrow, single-purpose tool.

        When to use vs. siblings: renumbering ONE node here; moving a node or
        changing coordinates and ID together → update_node (it re-reads the
        node's current coordinates first, so it costs an extra model query);
        renumbering MANY nodes, or compacting all node numbers from 1 →
        renumber_nodes.

        (写模型并刷新。只改编号、不动坐标，是单一用途的窄工具。选型：改一个节点的编号
        用本工具；要改坐标、或同时改坐标和编号用 update_node（它会先读回当前坐标补齐，
        多一次模型查询）；批量改号或把全部节点号从 1 起重排用 renumber_nodes。)

        Args:
            node_id: Existing node ID (原节点编号)
            new_id: New node ID; must not collide with an existing node
                    (新节点编号，不能与已有节点冲突)
        """
        try:
            provider.update_node_id(node_id=node_id, new_id=new_id)
            provider.update_model()
            return f"Successfully updated node ID from {node_id} to {new_id} (成功修改节点编号)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating node ID (修改节点编号失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error renumbering nodes (重新编号失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error moving nodes (平移节点失败): {e}") from e

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
        Modify several properties of ONE element in a single call (修改单元属性).

        Writes to the model and refreshes it. Partial updates are safe: the
        underlying qtmodel API overwrites every field on each call, so this tool
        first re-reads the element's current data and fills in whatever you left
        out. That costs one extra model query, and it fails if the element does
        not exist.

        One caveat: it handles ONE element — old_id is a single ID, not a range.

        When to use vs. siblings: several properties of one element at once
        here; ONE property across MANY elements → update_element_material /
        update_element_section / update_element_beta (they accept lists and
        "1to50" range strings); connectivity only → update_element_nodes;
        renumbering only → update_element_id (no read-back, cheaper).

        (写模型并刷新。部分更新是安全的：底层 qtmodel API 每次都整体覆盖全部字段，
        因此本工具会先读回单元当前数据补齐——代价是多一次模型查询，单元不存在时失败。
        一点注意：一次只处理一个单元(old_id 是单个编号、不支持区间)。
        选型：一次改一个单元的多个属性用
        本工具；对大批单元改同一个属性用 update_element_material /
        update_element_section / update_element_beta（支持列表与 "1to50" 区间串）；
        只改连接用 update_element_nodes；只改编号用 update_element_id。)

        Args:
            old_id: Existing element ID, a single ID (待修改的单元编号，单个)
            new_id: New element ID, -1 to keep unchanged  (新单元编号，-1不修改)
            ele_type: Element type (单元类型): 1=beam(梁), 2=truss(杆), 3=cable(索), 4=plate(板)
            node_i: New I-end node ID (新I端节点号)
            node_j: New J-end node ID (新J端节点号)
            mat_id: New material ID (新材料编号)
            sec_id: New section ID, or thickness ID for a plate
                    (新截面编号；板单元时为板厚编号)
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating element (修改单元失败): {e}") from e

    @mcp.tool()
    def update_element_id(old_id: int, new_id: int) -> str:
        """
        Renumber one element, leaving all its properties untouched
        (仅修改单元编号).

        Writes to the model and refreshes it. Only the ID changes — this is the
        narrow, single-purpose tool.

        When to use vs. siblings: renumbering ONE element here; changing
        properties and ID together → update_element (it re-reads the element's
        current data first, so it costs an extra model query); renumbering MANY
        elements, or compacting all element numbers from 1 → renumber_elements.

        (写模型并刷新。只改编号、不动任何属性，是单一用途的窄工具。选型：改一个单元的
        编号用本工具；要连带改属性用 update_element（它会先读回当前单元数据补齐，
        多一次模型查询）；批量改号或把全部单元号从 1 起重排用 renumber_elements。)

        Args:
            old_id: Existing element ID (原单元编号)
            new_id: New element ID; must not collide with an existing element
                    (新单元编号，不能与已有单元冲突)
        """
        try:
            provider.update_element_id(old_id=old_id, new_id=new_id)
            provider.update_model()
            return f"Successfully updated element ID from {old_id} to {new_id} (成功修改单元编号)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating element ID (修改单元编号失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error renumbering elements (重新编号失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error reverting local orientation (反转单元方向失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating element material (修改单元材料失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating element section (修改单元截面失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating beta angle (修改贝塔角失败): {e}") from e

    @mcp.tool()
    def update_element_nodes(
        element_id: int,
        node_i: int,
        node_j: int,
    ) -> str:
        """
        Reconnect a frame element to different end nodes (改接杆系单元的端节点).

        Writes to the model and refreshes it. Changes only the connectivity —
        material, section and beta angle are left alone. Both nodes must already
        exist. Reconnecting changes the element's geometry, so anything derived
        from its length (self-weight, cable unstressed length) changes with it.

        FRAME ELEMENTS ONLY (beam/truss/cable, 2 nodes). Plate elements need 4
        nodes, which this tool cannot express; use the escape hatch instead:
        call_qtmodel_api(api_object="mdb", method="update_element_node",
                         kwargs={"element_id": 7, "node_ids": [1, 2, 3, 4]}).

        When to use vs. siblings: connectivity here; the element's material,
        section or beta angle → update_element_material /
        update_element_section / update_element_beta; several of those at once
        on one element → update_element.

        (写模型并刷新。只改连接关系，材料/截面/贝塔角不动；两个节点须已存在。改接会改变
        单元几何，凡由长度导出的量（自重、索无应力长度）都随之变化。仅适用于杆系单元
        (梁/杆/索，2 节点)；板单元需 4 节点，本工具无法表达，需经逃生舱调
        update_element_node。选型：改连接用本工具；改材料/截面/贝塔角用对应的
        update_element_* 窄工具；一次改多项用 update_element。)

        Args:
            element_id: Element ID to modify (待修改的单元编号)
            node_i: New I-end node ID, must exist (新I端节点号，须已存在)
            node_j: New J-end node ID, must exist (新J端节点号，须已存在)
        """
        try:
            provider.update_element_node(element_id=element_id, node_ids=[node_i, node_j])
            provider.update_model()
            return (
                f"Element {element_id} nodes updated to [{node_i}, {node_j}] "
                f"(单元 {element_id} 端节点修改成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating element nodes (修改单元端节点失败): {e}") from e

    # ── 3. Structure group modifications ──────────────────────────────

    @mcp.tool()
    def add_to_structure_group(
        group_name: str,
        node_ids: Any = None,
        element_ids: Any = None,
    ) -> str:
        """
        Add nodes and/or elements to an existing structure group — the general
        one (向已有结构组中添加节点和/或单元，通用).

        Writes to the model and refreshes it. Adds to the group's existing
        members rather than replacing them; the group must already exist
        (create_structure_group). Pass either or both of node_ids/element_ids.

        When to use vs. siblings: prefer this tool — it is the general form.
        add_elements_to_group is a convenience wrapper that reaches the same
        underlying call with only element_ids, so it can do nothing this cannot.

        This tool cannot take members out. remove_structure_group deletes the
        whole group; to drop individual members use the escape hatch:
        call_qtmodel_api(api_object="mdb",
                         method="remove_structure_from_group", kwargs={...}).

        (写模型并刷新。是向组内现有成员追加、而非替换；结构组须已存在。node_ids 与
        element_ids 可只传一个或都传。选型：优先用本工具，它是通用形式；
        add_elements_to_group 只是仅传 element_ids 的便捷封装，能做的事本工具都能做。
        本工具不能移除成员；remove_structure_group 是删掉整个组，移除单个成员需经逃生舱调
        remove_structure_from_group。)

        Args:
            group_name: Name of the structure group, must already exist
                        (结构组名称，须已存在)
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding to structure group (向结构组添加成员失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing from structure group (从结构组移除成员失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing nodes (删除节点失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing elements (删除单元失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error merging nodes (合并节点失败): {e}") from e

