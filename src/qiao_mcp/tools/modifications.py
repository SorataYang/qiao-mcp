"""
MCP Modification Tools — update/modify existing model entities.
桥梁模型修改类工具 (基于 qtmodel 2.5.0 API)

Provides tools to modify existing nodes, elements, materials,
sections, boundaries, and structure groups.
"""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import StrictBool

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import FiniteNumber, NonnegativeNumber, QueryId, SelectedIds


def register_modification_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register all modify-type MCP tools."""

    # ── 1. General model operations ───────────────────────────────────

    @mcp.tool()
    def initialize_model(confirm: StrictBool = False) -> str:
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
        if confirm is not True:
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
        Save the active QiaoTong model to its native file (保存当前桥通模型).

        Use before model changes or to create a checkpoint. For an image use
        save_model_screenshot; this saves the editable model. Requires an open model
        and a writable path on the machine running QiaoTong. Existing files may be
        overwritten; the wrapper creates no backup and returns no downloaded file.
        (路径属于桥通所在机器，已有文件可能被覆盖；不会自动备份或下载。)

        Args:
            file_path: Prefer an absolute path on the QiaoTong host. The qtmodel SDK
                documents .bfmd native files; use the format supported by your QiaoTong
                version. Relative paths resolve in QiaoTong's environment; an empty
                string saves to its current path (桥通主机路径；空串用当前路径)

        Returns:
            Success message after the backend save call, or an MCP error on failure.
            The MCP process does not independently verify a file on the remote host.
        """
        try:
            provider.save_model_file(file_path=file_path)
            destination = repr(file_path) if file_path else "the current QiaoTong path"
            return f"Successfully saved model to {destination} (成功保存模型)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error saving model file (保存模型文件失败): {e}") from e

    @mcp.tool()
    def open_model_file(file_path: str) -> str:
        """
        Open an existing model file (打开模型文件).

        Replaces the active model. Save unsaved work with save_model_file first.
        The path is read by QiaoTong on its host, not uploaded from the MCP machine.

        Args:
            file_path: Native model path on the QiaoTong host (.bfmd in the qtmodel SDK;
                use the format your desktop version supports). Prefer an absolute path.
                (桥通主机上的模型文件路径，建议使用绝对路径)
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
        node_id: QueryId,
        x: FiniteNumber | None = None,
        y: FiniteNumber | None = None,
        z: FiniteNumber | None = None,
        new_id: QueryId | Literal[-1] = -1,
    ) -> str:
        """
        Modify an existing node's coordinates and/or ID (修改节点坐标或编号).

        Writes to the model and refreshes it. The underlying qtmodel API
        overwrites all three coordinates, so when any of x/y/z is omitted this
        tool reads the current position once and fills the omitted components.
        That read fails if the node is missing. Supplying all three coordinates
        skips the extra read; the bridge then validates the target node.

        When to use vs. siblings: coordinates (with or without a new ID) here;
        renumbering only → update_node_id (no read-back, cheaper); shifting
        nodes by a relative offset rather than to absolute coordinates →
        move_nodes; renumbering many nodes → renumber_nodes.

        (写模型并刷新。底层每次整体覆盖三坐标，省略任一坐标时先回读补齐，节点不存在
        时回读失败；三坐标齐全时不额外查询，由桥通校验目标。选型：改坐标（可同时改编号）用本工具；只改编号用
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
    def update_node_id(node_id: QueryId, new_id: QueryId) -> str:
        """
        Renumber one node, leaving its coordinates untouched (仅修改节点编号).

        Writes to the model and refreshes it. Only the ID changes — this is the
        narrow, single-purpose tool.

        When to use vs. siblings: renumbering ONE node here; moving a node or
        changing coordinates and ID together → update_node (it reads current
        coordinates only when some coordinate components are omitted);
        renumbering MANY nodes, or compacting all node numbers from 1 →
        renumber_nodes.

        (写模型并刷新。只改编号、不动坐标，是单一用途的窄工具。选型：改一个节点的编号
        用本工具；要改坐标、或同时改坐标和编号用 update_node（省略部分坐标时多一次
        模型查询补齐）；批量改号或把全部节点号从 1 起重排用 renumber_nodes。)

        Returns a confirmation, not an updated node record. The bridge owns
        collision checks and reference updates; read nodes/elements back
        before using cached identifiers after the change.

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
    def renumber_nodes(ids: SelectedIds | None = None, new_ids: SelectedIds | None = None) -> str:
        """
        Renumber selected nodes with an explicit mapping, or compact all node
        numbers from 1 (按映射批量改号，或从 1 开始重排全模型节点).

        For selected nodes, supply BOTH ids and new_ids with equal lengths;
        each old ID maps to the new ID at the same position. Omit BOTH arguments
        to intentionally renumber all nodes. Supplying only one is rejected;
        blank selections, mismatched counts and duplicate IDs are also rejected.
        (局部改号须同时传入等长、无重复的旧新编号；仅一列或空选择会报错。
        两者均省略表示有意全模型重排。)

        Use update_node_id for one ID, update_node for coordinates plus an ID,
        or move_nodes for relative offsets. This call writes and refreshes the
        model, then returns a confirmation, not an old-to-new mapping. Read
        nodes/elements back before reusing cached IDs; collision and reference
        handling are owned by the bridge and are not preflighted here.

        Args:
            ids: Old IDs, as an int/list/range string; pair with new_ids to
                 limit the operation to these nodes (原节点号，局部改号须与 new_ids 成对)
            new_ids: New IDs matching ids in order and count; omit together
                     with ids for full-model renumbering (对应的新编号；与 ids 同时省略才全模型重排)
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
        ids: SelectedIds,
        offset_x: FiniteNumber = 0.0,
        offset_y: FiniteNumber = 0.0,
        offset_z: FiniteNumber = 0.0,
    ) -> str:
        """
        Move nodes by an offset (平移节点).

        Use update_node for absolute coordinates on one node; use update_node_id
        or renumber_nodes for numbering without moving geometry. Each call adds
        the offset again, so it is not idempotent. Returns a confirmation after
        refreshing the model; re-read affected geometry before a new analysis.
        (本工具按相对位移移动，重复会再次累加；绝对坐标用 update_node，改号用改号工具。)

        Args:
            ids: Node ID(s) to move. Supports int, list, or range string '1to10'.
                 (节点编号，支持整数、列表或范围字符串)
            offset_x: X-direction offset in model units (X方向偏移量)
            offset_y: Y-direction offset in model units (Y方向偏移量)
            offset_z: Z-direction offset in model units (Z方向偏移量)

        Example:
            move_nodes("1to10", offset_z=-0.5)  # Shift Z by -0.5 in model length units
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
        old_id: QueryId,
        new_id: QueryId | Literal[-1] = -1,
        ele_type: Literal[1, 2, 3, 4] | None = None,
        node_i: QueryId | None = None,
        node_j: QueryId | None = None,
        mat_id: QueryId | None = None,
        sec_id: QueryId | None = None,
        beta_angle: FiniteNumber | None = None,
    ) -> str:
        """
        Modify several properties of ONE element in a single call (修改单元属性).

        Writes to the model and refreshes it. The underlying qtmodel API
        overwrites the record, so this tool reads the current element once and
        fills omitted fields present in that record. A missing/ambiguous element
        or missing applicable field fails before writing. SDK query objects may
        themselves fill absent backend fields with defaults; use targeted update
        tools when the original record cannot be verified.

        One caveat: it handles ONE element — old_id is a single ID, not a range.
        Both node_i and node_j are needed to replace connectivity; supplying
        only one is rejected. This two-node input cannot reconnect a
        plate; use the gateway's mdb.update_element_node with all four nodes.
        Other plate properties can be updated while retaining its connectivity.
        (改接须同时给 node_i/node_j，单给一个会报错；板的四节点改接经网关完成。)

        When to use vs. siblings: several properties of one element at once
        here; ONE property across MANY elements → update_element_material /
        update_element_section / update_element_beta (they accept lists and
        "1to50" range strings); connectivity only → update_element_nodes;
        renumbering only → update_element_id (no read-back, cheaper).

        (写模型并刷新。底层整体覆盖，本工具多一次查询补齐回读记录中已有的字段，
        单元不唯一或缺少适用字段时失败。SDK 也可能为后端缺失字段补默认值，
        原始记录不可核实时应使用单字段修改工具。
        一点注意：一次只处理一个单元(old_id 是单个编号、不支持区间)。
        选型：一次改一个单元的多个属性用
        本工具；对大批单元改同一个属性用 update_element_material /
        update_element_section / update_element_beta（支持列表与 "1to50" 区间串）；
        只改连接用 update_element_nodes；只改编号用 update_element_id。)

        Args:
            old_id: Existing element ID, a single ID (待修改的单元编号，单个)
            new_id: New element ID, -1 to keep unchanged  (新单元编号，-1不修改)
            ele_type: Element type (单元类型): 1=beam(梁), 2=truss(杆), 3=cable(索), 4=plate(板)
            node_i: New frame I-end node ID; only used together with node_j
                    (新I端节点号，仅与 node_j 同时提供时生效)
            node_j: New frame J-end node ID; only used together with node_i
                    (新J端节点号，仅与 node_i 同时提供时生效)
            mat_id: New material ID (新材料编号)
            sec_id: New section ID, or thickness ID for a plate
                    (新截面编号；板单元时为板厚编号)
            beta_angle: New beta angle in degrees (新贝塔角，单位度)

        Example:
            update_element(5, mat_id=2, sec_id=3)  # Change element 5's material and section
        """
        try:
            if (node_i is None) != (node_j is None):
                raise ToolInputError("node_i and node_j must be supplied together (改接必须同时给出 I/J 节点)")
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
    def update_element_id(old_id: QueryId, new_id: QueryId) -> str:
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
    def renumber_elements(element_ids: SelectedIds | None = None, new_ids: SelectedIds | None = None) -> str:
        """
        Renumber elements (单元编号重排序).
        Supply both lists with equal lengths and unique IDs for a local mapping;
        omit both to renumber all elements from 1. Supplying only one is rejected.
        For one ID use
        update_element_id, or update_element to change properties as well.
        Returns a confirmation, not a mapping; read elements and references back
        before reusing old IDs (局部须两列成对，仅同时省略才全模型重排；完成后回读).

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
    def revert_local_orientation(ids: SelectedIds) -> str:
        """
        Reverse the local x-axis of frame elements, swapping their I and J ends
        (反转杆系单元局部方向，即对调 I/J 端).

        Writes to the model and refreshes it. FRAME ELEMENTS ONLY
        (beam/truss/cable). After the swap, "I-end" and "J-end" in every other
        tool refer to the opposite physical ends of the member. Re-read its
        connectivity and local-axis-dependent loads, then rerun analysis before
        interpreting new end forces. The SDK does not promise a sign flip for
        every result component or automatic transformation of attached loads.
        Returns a confirmation, not transformed results.

        When to use vs. siblings: reversing I/J here; rotating the local
        y/z-axes around the member axis without swapping ends →
        update_element_beta.

        (写模型并刷新。仅适用于杆系单元(梁/杆/索)。对调后，其它工具中的"I端""J端"
        指向该构件相反的物理端。回读连接和局部荷载并重新求解后再解释端力；SDK
        未承诺全部结果符号翻转或附属荷载自动转换。返回确认消息。
        选型：对调 I/J 用本工具；绕杆轴旋转局部 y/z 轴、不对调端点用
        update_element_beta。)

        Args:
            ids: Frame element ID(s) — int, list, or "XtoYbyN" range string
                 (杆系单元编号，支持整数、列表或 "XtoYbyN" 范围字符串)
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
        ids: SelectedIds,
        mat_id: QueryId,
    ) -> str:
        """
        Change the material of one or more elements (修改单元材料).

        Requires an existing material and elements. For several properties on
        one element use update_element; this targeted batch operation does not
        read and rebuild the whole element record. Returns a confirmation after
        refresh, with no solve (单字段批量赋值；单个单元多字段修改用 update_element).

        Args:
            ids: Element ID(s). Supports int, list, or range string '1to50'.
                 (单元编号，支持整数、列表或范围字符串)
            mat_id: New material ID; query get_model_data(kind="materials") for valid IDs
                (新材料编号，先查询已有材料)

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
        ids: SelectedIds,
        sec_id: QueryId,
    ) -> str:
        """
        Change the section of one or more frame elements (修改杆系单元截面).

        Requires an existing section and frame elements. For a plate thickness
        or several properties on one element use update_element. This calls the
        frame-section endpoint directly; returns a confirmation after refresh,
        without solving (杆系截面批量赋值；板厚或多字段修改用 update_element).

        Args:
            ids: Element ID(s). Supports int, list, or range string '1to50'.
                 (单元编号，支持整数、列表或范围字符串)
            sec_id: New section ID; query get_model_data(kind="sections") for valid IDs
                (新截面编号，先查询已有截面)

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
        ids: SelectedIds,
        beta: FiniteNumber,
    ) -> str:
        """
        Change the beta angle of one or more elements (修改单元贝塔角).

        The beta angle controls the local axis orientation of a beam/truss element.
        贝塔角控制单元局部坐标系方向。
        Use revert_local_orientation to reverse I/J instead; use update_element
        for several properties on one element. This sets an absolute angle,
        not an angular increment, and returns a confirmation without solving.
        (绝对角赋值；对调端点用 revert_local_orientation，多字段修改用 update_element。)

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
        element_id: QueryId,
        node_i: QueryId,
        node_j: QueryId,
    ) -> str:
        """
        Reconnect a frame element to different end nodes (改接杆系单元的端节点).

        Writes to the model and refreshes it. Changes only the connectivity —
        material, section and beta angle are left alone. Both nodes must already
        exist. Reconnecting changes the element's geometry. Verify length-based
        settings and local-axis loads, then solve again; this call does not
        itself recompute results or explicitly update a cable's unstressed length.
        Returns the requested connectivity in a confirmation, not a read-back.

        FRAME ELEMENTS ONLY (beam/truss/cable, 2 nodes). Plate elements need 4
        nodes, which this tool cannot express; use the escape hatch instead:
        call_qtmodel_api(api_object="mdb", method="update_element_node",
                         kwargs={"element_id": 7, "node_ids": [1, 2, 3, 4]}).

        When to use vs. siblings: connectivity here; the element's material,
        section or beta angle → update_element_material /
        update_element_section / update_element_beta; several of those at once
        on one element → update_element.

        (写模型并刷新。只改连接关系，材料/截面/贝塔角不动；两个节点须已存在。改接会改变
        单元几何，应核对长度相关设置和局部荷载后重新求解；本调用不显式改索无应力长度，
        也不重算结果，返回的是请求连接信息。仅适用于杆系单元
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
        node_ids: SelectedIds | None = None,
        element_ids: SelectedIds | None = None,
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

        Use remove_from_structure_group to remove selected members while keeping
        the group and model entities. remove_structure_group deletes the group.

        (写模型并刷新。是向组内现有成员追加、而非替换；结构组须已存在。node_ids 与
        element_ids 可只传一个或都传。选型：优先用本工具，它是通用形式；
        add_elements_to_group 只是仅传 element_ids 的便捷封装，能做的事本工具都能做。
        移除指定成员用 remove_from_structure_group，保留组和模型实体；
        删除整个组用 remove_structure_group。)

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
        node_ids: SelectedIds | None = None,
        element_ids: SelectedIds | None = None,
    ) -> str:
        """
        Remove nodes and/or elements from an existing structure group
        (从结构组中移除节点和/或单元).

        Use to change group membership after add_to_structure_group. Supply
        explicit node_ids and/or element_ids; the group and the model's nodes
        and elements remain. This writes group membership and refreshes the
        model. Use remove_structure_group to delete the group itself.
        (显式指定要移出的节点/单元，仅修改成员关系并刷新模型，保留组和模型实体；
        删除整个组用 remove_structure_group。)

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
    def remove_nodes(ids: SelectedIds | None = None, confirm_delete_all: StrictBool = False) -> str:
        """
        Delete nodes from the model (删除节点).

        Args:
            ids: Node ID(s) to delete. Supports int, list, or range string '1to10'.
                 Omit/use None plus confirm_delete_all=True to delete ALL nodes;
                 empty strings/lists are invalid (省略或 None 配合确认删除全部；空串/空表无效)
            confirm_delete_all: MUST be set to true if ids is empty (deleting all nodes).
                                (如果要删除所有节点，必须设为 true)

        CRITICAL LLM INSTRUCTION: Do NOT delete all nodes autonomously to fix your own mistakes.
        You MUST explicitly ask the USER for permission before calling this tool with empty ids.
        (大模型绝对不可为了修复自己的错误而自行清空所有节点！必须先向用户询问并获得许可！)

        Example:
            remove_nodes(ids=[5, 6, 7])  # Delete specific nodes
        """
        try:
            if ids is None and confirm_delete_all is not True:
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
    def remove_elements(ids: SelectedIds | None = None, remove_free_nodes: StrictBool = False, confirm_delete_all: StrictBool = False) -> str:
        """
        Delete elements from the model (删除单元).

        Args:
            ids: Element ID(s) to delete. Supports int, list, or range string '1to10'.
                 Omit/use None plus confirm_delete_all=True to delete ALL elements;
                 empty strings/lists are invalid (省略或 None 配合确认删除全部；空串/空表无效)
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
            if ids is None and confirm_delete_all is not True:
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
    def merge_nodes(ids: SelectedIds | None = None, tolerance: NonnegativeNumber = 1e-4) -> str:
        """
        Merge nodes that are at (nearly) the same coordinates (合并重合节点).

        This is equivalent to the "Merge Nodes" operation in the GUI.
        Useful after building a model to remove accidental duplicate nodes.
        相当于界面上的"合并节点"功能，用于消除重叠节点。

        Args:
            ids: Node ID(s) to check. Supports int, list, or range string.
                 Omit/use None to check ALL nodes; empty strings/lists are invalid
                 (省略或 None 检查全部节点；空串/空表无效)
            tolerance: Merge distance tolerance in model length units, default 0.0001
                       (合并容许误差，按模型长度单位，默认 0.0001)

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
