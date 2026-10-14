"""
MCP Tools for bridge modeling operations.
桥梁建模操作工具

Provides tools for creating and managing model entities:
nodes, elements, materials, sections, structure groups, etc.
"""

import asyncio
import math
from typing import Any, Literal, get_args

from mcp.server.fastmcp import Context, FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import (
    CurvePoints,
    FiniteNumber,
    FiveNumbers,
    FourNumbers,
    FunctionReference,
    LoadCaseKind,
    LoadCombinationItem,
    NodeRows,
    NonnegativeNumber,
    PositiveInteger,
    PositiveNumber,
    SectionLoop,
    SectionProperties,
    SelectedIds,
    SupportExtraParameters,
    ThreeNumbers,
    TwoNumbers,
)

# qtmodel wait_solve 判为成功的状态集合（与其源码一致）
_SOLVE_SUCCESS_STATES = frozenset({"succeeded", "success", "completed", "complete"})


def _describe_ids(ids: list[int]) -> str:
    """Render an ID sequence compactly, preserving the order given.

    批量建模常创建上百个节点，逐一列出会淹没消息。但这里的顺序有语义——
    第 i 个编号对应第 i 个请求坐标，而后端的编号方向可能与坐标相反
    （实测 x=10/20/30 -> 102/101/100），因此**不能排序**，只能压缩
    单调连续段（升序或降序），断点必须忠实保留。
    """
    if not ids:
        return "none"
    runs: list[tuple[int, int]] = []
    start = prev = ids[0]
    step = 0
    for i in ids[1:]:
        delta = i - prev
        if delta in (1, -1) and (step == 0 or delta == step):
            step, prev = delta, i
            continue
        runs.append((start, prev))
        start = prev = i
        step = 0
    runs.append((start, prev))
    parts = [str(a) if a == b else f"{a}–{b}" for a, b in runs]
    if len(parts) <= 4:
        return ", ".join(parts)
    return ", ".join(parts[:3]) + f", … (+{len(parts) - 3} more ranges)"


def _closed_polygon_loops(loops: dict[str, list[list[float]]]) -> dict[str, list[list[float]]]:
    """Validate simple ring inputs and make closing edges explicit for the backend."""
    if "main" not in loops or any(key != "main" and not key.startswith("sub") for key in loops):
        raise ToolInputError("Provide a main outer loop and optional sub1/sub2/... holes")
    closed = {}
    for name, points in loops.items():
        if len(points) < 3 or any(len(point) != 2 for point in points):
            raise ToolInputError(f"Loop {name!r} needs at least three 2D points")
        if any(not math.isfinite(value) for point in points for value in point):
            raise ToolInputError(f"Loop {name!r} coordinates must be finite")
        ring = [list(point) for point in points]
        if len({tuple(point) for point in ring}) < 3:
            raise ToolInputError(f"Loop {name!r} needs at least three distinct vertices")
        if ring[-1] != ring[0]:
            ring.append(ring[0].copy())
        area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:], strict=False))
        if area2 == 0:
            raise ToolInputError(f"Loop {name!r} has zero signed area; check vertex order")
        closed[name] = ring
    return closed


def register_modeling_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register all modeling-related MCP tools."""

    @mcp.tool()
    def create_nodes(
        node_data: NodeRows,
        intersected: bool = False,
        is_merged: bool = True,
        merge_error: NonnegativeNumber = 1e-3,
        numbering_type: Literal[0, 1, 2] = 1,
        start_id: int = 1,
    ) -> str:
        """
        Create nodes in the bridge model from an explicit coordinate list (创建节点).

        Prefer `create_nodes_linear` when nodes are evenly spaced along a line
        — it is far more concise for typical bridge models.

        Args:
            node_data: List of node coordinates. Format: [[x,y,z], ...] or [[id,x,y,z], ...]
                       节点坐标列表，格式: [[x,y,z],...] 或 [[id,x,y,z],...]
            intersected: Whether to split elements at intersection points (是否交叉分割, 默认关)
            is_merged: Whether to merge duplicate nodes at the same position (是否合并重合节点)
            merge_error: Merge tolerance in model units, default 1e-3
                         (合并容差，默认0.001模型长度单位)
            numbering_type: Numbering strategy: 0=smallest unused ID, 1=existing maximum+1,
                2=request start_id (编号方式：0最小空号、1最大号加一、2用户指定)
            start_id: Requested first ID, used only with numbering_type=2. QiaoTong may
                reassign conflicting IDs; query get_model_data(kind="nodes") afterwards
                (仅编号方式2使用；冲突时请查询实际编号)
        """
        try:
            provider.add_nodes(
                node_data=node_data,
                intersected=intersected,
                is_merged=is_merged,
                merge_error=merge_error,
                numbering_type=numbering_type,
                start_id=start_id,
            )
            return (
                f"Submitted {len(node_data)} node coordinates; merging may reuse existing nodes. "
                "Read get_model_data(kind='nodes') for actual IDs and counts. "
                f"(已提交 {len(node_data)} 组坐标；合并可能复用旧节点，请回读实际编号和数量)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating nodes (创建节点失败): {e}") from e

    @mcp.tool()
    def create_nodes_linear(
        count: PositiveInteger,
        start_x: float = 0.0,
        start_y: float = 0.0,
        start_z: float = 0.0,
        spacing_x: float = 0.0,
        spacing_y: float = 0.0,
        spacing_z: float = 0.0,
        start_id: int = 1,
        is_merged: bool = True,
        merge_error: NonnegativeNumber = 1e-3,
    ) -> str:
        """
        Create evenly-spaced nodes along a straight line — the preferred way to model
        a bridge girder (等间距直线批量创建节点).

        Instead of listing 101 coordinates for a 100m span at 1m intervals, just specify
        the count, starting point, and spacing in each direction.

        Args:
            count: Number of nodes to create (节点数量)
            start_x: X coordinate of the first node (起点X坐标)
            start_y: Y coordinate of the first node (起点Y坐标)
            start_z: Z coordinate of the first node (起点Z坐标)
            spacing_x: X increment between nodes, m (相邻节点X方向间距)
            spacing_y: Y increment between nodes (相邻节点Y方向间距)
            spacing_z: Z increment between nodes (相邻节点Z方向间距)
            start_id: Requested ID of the first node (期望的起始节点编号).
                      HONORED ONLY when the model has no conflicting IDs — the
                      backend assigns its own numbering when start_id is taken.
                      The returned message reports the IDs actually assigned;
                      always trust those, not start_id.
                      （编号可能被后端改派，请以返回消息中的实际编号为准）
            is_merged: Whether to merge duplicate nodes (是否合并重合节点).
                       When merging occurs, fewer nodes are created than requested.
            merge_error: Merge tolerance, default 1e-3 (合并容差)

        Examples:
            # 100m simply-supported beam, 101 nodes at 1m pitch along X axis:
            create_nodes_linear(count=101, start_x=0, spacing_x=1.0)

            # Two-span 50m+50m continuous beam, start x from 0:
            create_nodes_linear(count=101, start_x=0, spacing_x=1.0)
        """
        if count <= 0:
            raise ToolInputError("count must be a positive integer > 0 (节点数量必须大于0)")

        try:
            node_data = [
                [start_x + i * spacing_x, start_y + i * spacing_y, start_z + i * spacing_z]
                for i in range(count)
            ]
            # numbering_type: 0=未使用的最小号码 1=最大号码加1 2=用户定义号码。
            # 只有 2 会读 start_id；此前硬编码 1，导致 start_id 被静默忽略。
            created_ids = provider.add_nodes_returning_ids(
                node_data=node_data,
                intersected=False,
                is_merged=is_merged,
                merge_error=merge_error,
                numbering_type=2,
                start_id=start_id,
            )
            end_x = start_x + (count - 1) * spacing_x
            end_y = start_y + (count - 1) * spacing_y
            end_z = start_z + (count - 1) * spacing_z
            span = (
                f"from ({start_x},{start_y},{start_z}) "
                f"to ({end_x:.3f},{end_y:.3f},{end_z:.3f})"
            )
            # 实际编号由后端裁定，必须回报真实值——LLM 会用它建单元
            if not created_ids:
                return (
                    f"Submitted {count} node coordinates {span}, but the assigned IDs could not "
                    f"be resolved unambiguously — query them with get_model_data(kind='nodes') "
                    f"before creating elements "
                    f"(已提交 {count} 组坐标，但未能确定编号，建单元前请先查询)"
                )
            # created_ids 按请求坐标顺序给出该点真实可用的编号（可能是新建的，
            # 也可能是 is_merged 命中的既有节点），故按序展示而非排序后压缩
            id_desc = _describe_ids(created_ids)
            note = ""
            if len(created_ids) != count:
                note = (
                    f" NOTE: {count} coordinates requested but only "
                    f"{len(created_ids)} node IDs resolved — verify with "
                    f"get_model_data(kind='nodes') "
                    f"（有坐标未能解析到编号，请查询核实）"
                )
            first, last = created_ids[0], created_ids[-1]
            order = "" if first <= last else " (note: IDs run opposite to coordinates)"
            return (
                f"Resolved {count} coordinates to {len(set(created_ids))} distinct nodes "
                f"at IDs {id_desc}, {span}{order} "
                f"(已解析 {len(set(created_ids))} 个节点，包含合并复用的节点){note}"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating linear nodes (批量创建节点失败): {e}") from e



    @mcp.tool()
    def create_beam_element(
        node_i: int,
        node_j: int,
        mat_id: int,
        sec_id: int,
        element_id: int = -1,
        beta_angle: float = 0.0,
        ele_type: Literal[1, 2, 3] = 1,
        initial_type: int = 0,
        initial_value: float = 0.0,
    ) -> str:
        """
        Create a single frame element (beam/truss/cable) with named parameters
        (创建单个梁/杆/索单元，参数具名).

        This is the preferred way to create individual elements — all parameters
        have explicit names and inline documentation.

        Args:
            node_i: Start node ID (I端节点编号)
            node_j: End node ID (J端节点编号)
            mat_id: Material ID — query get_model_data(kind="materials") for IDs (材料编号)
            sec_id: Section ID — query get_model_data(kind="sections") for IDs (截面编号)
            element_id: Element ID, -1 = auto-assign next available ID (单元编号，-1表示自动分配)
            beta_angle: Beta angle in degrees, controls local axis orientation (贝塔角，度)
            ele_type: Element type (单元类型): 1=Beam(梁), 2=Truss(杆), 3=Cable(索)
            initial_type: Cable initialization only: 1=initial tension, 2=initial
                horizontal force, 3=unstressed length. Set explicitly for cables;
                beam/truss elements ignore it (索：1初拉力、2初始水平力、3无应力长度)
            initial_value: Cable initial force (N) or unstressed length (m), according
                to initial_type (索单元初始力或无应力长度，取决于初始化类型)

        Example:
            create_beam_element(node_i=1, node_j=2, mat_id=1, sec_id=1)
        """
        try:
            # Build element data row: [id, type, mat, sec, beta, nodeI, nodeJ, init_type, init_val]
            eid = element_id if element_id != -1 else 0  # 0 = let API auto-assign
            ele_data = [[eid, ele_type, mat_id, sec_id, beta_angle, node_i, node_j,
                         initial_type, initial_value]]
            provider.add_elements(ele_data=ele_data)
            return (
                f"Created {'beam' if ele_type==1 else 'truss' if ele_type==2 else 'cable'} element "
                f"(nodes {node_i}→{node_j}, mat={mat_id}, sec={sec_id}) "
                f"(成功创建单元 {node_i}→{node_j})"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating beam element (创建单元失败): {e}") from e

    @mcp.tool()
    def create_beam_elements_linear(
        mat_id: int,
        sec_id: int,
        node_ids: list[int] | None = None,
        node_id_start: int = 0,
        count: int = 0,
        element_id_start: int = 1,
        beta_angle: float = 0.0,
        ele_type: Literal[1, 2, 3] = 1,
    ) -> str:
        """
        Batch-create frame elements chaining nodes along a girder
        (批量创建沿主梁方向连接相邻节点的梁单元).

        PREFERRED: pass node_ids — the exact ID sequence reported by
        create_nodes_linear. Elements chain them in the order given:
        node_ids[0]→[1], [1]→[2], …
        （首选：直接传 create_nodes_linear 回报的编号序列，按给定顺序连接）

        Do NOT assume node IDs are consecutive. The backend assigns numbering in
        an order that is NOT predictable from the request — measured on qtmodel
        2.6.3, one batch came back [1104,1103,1102,1101,1100] (reversed) and
        another [1201,1200,1204,1203,1202] (neither ascending nor reversed).
        Chaining by ID arithmetic on such a batch silently produces folded-back
        geometry: elements of wrong length and direction that the solver accepts
        without error, yielding a model that computes the wrong bridge.
        （后端编号顺序不可预测，按编号递推会静默建出折返几何，求解器不会报错）

        Node coordinates are checked before writing: if the chain is not
        geometrically monotonic, the call fails instead of building a bad model.

        Args:
            mat_id: Material ID for all elements (所有梁单元的材料编号)
            sec_id: Section ID for all elements (所有梁单元的截面编号)
            node_ids: Node IDs in girder order, as reported by create_nodes_linear
                      (节点编号序列，按主梁走向排列). Creates len(node_ids)-1 elements.
            node_id_start: LEGACY fallback, only when node_ids is omitted — assumes
                           IDs run consecutively from here (旧式用法，假设编号连续)
            count: Number of elements, only with node_id_start (单元数量)
            element_id_start: ID assigned to the first element, then auto-incremented
                              (第一个单元的编号，后续自动递增)
            beta_angle: Beta angle in degrees, same for all elements (贝塔角，度)
            ele_type: 1=Beam(梁), 2=Truss(杆), 3=Cable(索)

        Examples:
            # Preferred — chain the IDs create_nodes_linear actually returned:
            create_beam_elements_linear(mat_id=1, sec_id=1,
                                        node_ids=[5, 501, 500, 502])

            # Legacy — only safe when the nodes are known to be consecutive:
            create_beam_elements_linear(mat_id=1, sec_id=1,
                                        node_id_start=1, count=100)
        """
        # ── 解析节点链：显式序列优先，否则回落到编号递推 ──
        if node_ids:
            chain = [int(n) for n in node_ids]
            if len(chain) < 2:
                raise ToolInputError(
                    "node_ids needs at least 2 node IDs to form one element "
                    "(至少需要 2 个节点编号才能形成 1 个单元)"
                )
            if len(set(chain)) != len(chain):
                raise ToolInputError(
                    f"node_ids contains duplicates: {chain} "
                    "(节点编号序列中存在重复)"
                )
        elif node_id_start > 0 and count > 0:
            chain = [node_id_start + i for i in range(count + 1)]
        else:
            raise ToolInputError(
                "Provide node_ids (preferred), or both node_id_start and count "
                "(请提供 node_ids，或同时提供 node_id_start 与 count)"
            )

        # ── 写入前几何校验：拦截折返几何 ──
        # 后端接受任何有效节点编号的连线，长度忽正忽负也不报错，最终算出错的桥。
        # 这里在写入前按真实坐标核对单调性，宁可拒绝也不建出坏模型。
        try:
            geom = provider.check_node_chain_geometry(chain)
        except Exception:
            geom = None  # 校验本身失败（如查询不可用）不应阻塞建模

        if geom and not geom.get("ok"):
            raise ToolInputError(
                f"Refusing to create elements — node chain is not geometrically "
                f"monotonic: {geom.get('reason', 'unknown')}. Chaining these IDs "
                f"would build folded-back elements that the solver accepts but "
                f"which model the wrong structure. Query get_model_data(kind='nodes') "
                f"and pass node_ids in true girder order. "
                f"（节点链几何非单调，拒绝建单元以免产生折返几何，"
                f"请按主梁真实走向传入 node_ids）"
            )

        try:
            ele_data = [
                [element_id_start + i, ele_type, mat_id, sec_id, beta_angle,
                 chain[i], chain[i + 1], 0, 0.0]
                for i in range(len(chain) - 1)
            ]
            provider.add_elements(ele_data=ele_data)
            n_ele = len(ele_data)
            last_ele = element_id_start + n_ele - 1
            kind = {1: "beam", 2: "truss", 3: "cable"}.get(ele_type, "frame")
            detail = ""
            if geom and geom.get("total_length"):
                detail = f", total length {geom['total_length']:.3f}"
            return (
                f"Created {n_ele} {kind} elements (IDs {element_id_start}–{last_ele}) "
                f"chaining nodes {_describe_ids(chain)} "
                f"(mat={mat_id}, sec={sec_id}{detail}) "
                f"(成功批量创建 {n_ele} 个单元)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating beam elements (批量创建梁单元失败): {e}") from e

    @mcp.tool()
    def create_elements(
        element_data: list[list],
    ) -> str:
        """
        Create elements from a raw data array (通过原始数组创建单元).

        For beam elements, prefer `create_beam_element` or `create_beam_elements_linear`
        which have named parameters and are easier to use correctly.

        Args:
            element_data: Element data list. Each item format:
                - Beam/Truss: [id, type(1=beam,2=truss), matId, secId, beta, nodeI, nodeJ, initType, initVal]
                - Cable:      [id, 3, matId, secId, beta, nodeI, nodeJ, tensionType, tensionVal]
                - Plate:      [id, 4, matId, thicknessId, beta, nodeI, nodeJ, nodeK, nodeL, plateType]
                单元数据列表。梁=1, 杆=2, 索=3, 板=4
        """
        try:
            provider.add_elements(ele_data=element_data)
            return f"Successfully created {len(element_data)} elements (成功创建 {len(element_data)} 个单元)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating elements (创建单元失败): {e}") from e

    @mcp.tool()
    def create_load_group(name: str = "默认荷载组") -> str:
        """
        Create a load group (创建荷载组).

        Every load in QiaoTong must belong to a load group.
        Create this before creating a load case or applying loads.
        每个荷载必须属于某个荷载组，迅建荷载工况之前先建荷载组。

        Args:
            name: Load group name (荷载组名称, e.g. "默认荷载组")
        """
        try:
            provider.add_load_group(name=name)
            return f"Successfully created load group '{name}' (成功创建荷载组 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating load group (创建荷载组失败): {e}") from e

    @mcp.tool()
    def create_load_case(
        name: str,
        case_type: str = "施工阶段荷载",
    ) -> str:
        """
        Create a load case (创建荷载工况).

        A load case must exist before loads can be applied to it.
        This creates a named case, without applying any load. For automatic
        structural self-weight, configure set_self_weight_stage and include the
        stage with merge_operation_stage; a case named "自重" does not enable it.
        (本工具只建工况，不施加荷载；自动自重由自重阶段及运营阶段合并配置。)

        Args:
            name: Load case name (工况名称, e.g. "二期恒载", "风荷载")
            case_type: Load case type (荷载工况类型):
                "施工阶段荷载" (default) | "恒载" | "活载" | "制动力" | "风荷载"
                "体系温度荷载" | "梯度温度荷载"
                "长轨伸缩挠曲力荷载" | "脱轨荷载" | "长轨断轨力荷载"
                "船舶撞击荷载" | "汽车撞击荷载" | "用户定义荷载"
        """
        try:
            provider.add_load_case(name=name, case_type=case_type)
            return (
                f"Successfully created load case '{name}' (type='{case_type}'). "
                f"(成功创建荷载工况 '{name}')"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating load case '{name}' (创建工况失败): {e}") from e

    @mcp.tool()
    def add_load_combine(
        name: str,
        combine_type: Literal[1, 2, 3, 4, 5, 6] = 1,
        combine_info: list[LoadCombinationItem] | None = None,
        describe: str = "",
        index: int = -1,
    ) -> str:
        """
        Create or replace a model load combination (创建或替换模型荷载组合).

        Use this for MDB model/result combinations. For a concrete-check CDB case,
        use add_check_load_combination. Referenced cases/combinations must exist;
        create_load_case creates an individual case rather than a combination.
        QiaoTong supports automatic overwrite, so use a distinct name/index when
        creating a new combination. This writes the definition but does not solve.
        (引用工况须已存在；组合可被覆盖，调用后不会自动求解。)

        Args:
            name: Load combination name (荷载组合名称)
            combine_type: Native rule: 1=add, 2=discriminant, 3=envelope, 4=SRSS,
                5=absolute sum, 6=permanent actions added and other actions discriminated
                (1叠加、2判别、3包络、4平方和开根、5绝对值和、6混合)
            combine_info: Components [[case_type, case_name, factor], ...], in that order.
                Types: ST=static, CS=construction stage, CB=combination, MV=moving load,
                SM=settlement, RS=response spectrum, TH=time history, TV=transverse
                moving-load case from transversal analysis (qtmodel 2.9+, uses the case
                name directly). None/[] creates an empty definition
                (先类型、再工况名、最后系数；TV 为横向移动荷载工况；省略时组合为空)
            describe: Description (描述说明)
            index: ID index, -1 for auto (编号，-1自动生成)

        Example:
            add_load_combine(name="ULS", combine_type=1,
                combine_info=[["ST", "Dead", 1.2], ["ST", "Live", 1.4]])

        Returns:
            Success message identifying the saved combination; backend failures are
            MCP errors. Configure/run analysis before requesting combination results.
        """
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "combine_type": combine_type,
                "describe": describe,
                "index": index,
            }
            if combine_info is not None:
                if any(len(item) != 3 or item[0] not in get_args(LoadCaseKind) for item in combine_info):
                    raise ToolInputError("combine_info items must be [case_type, case_name, factor]")
                kwargs["combine_info"] = [tuple(item) for item in combine_info]
            provider.add_load_combine(**kwargs)
            return f"Saved load combination '{name}' (已创建或更新荷载组合 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding load combination (添加荷载组合失败): {e}") from e



    @mcp.tool()
    def create_material(
        name: str,
        mat_type: Literal[1, 2, 3, 4, 5, 6],
        standard: int = 1,
        database: str = "",
        data_info: FourNumbers | None = None,
        is_orthotropic: bool | None = None,
        ey: PositiveNumber | None = None,
    ) -> str:
        """
        Create a material in the bridge model (创建材料).

        Use a database grade for code materials; mat_type=5 requires the four
        custom properties. This defines a material, without assigning elements
        or solving. Read get_model_data(kind="materials") for its actual ID,
        then create elements or use update_element_material to assign it.
        The SDK documents overwrite by name: inspect an existing material before
        reusing its name. Returns a confirmation, not the new material ID.
        (数据库材料指定牌号，自定义材料填四项参数；同名可覆盖，创建后回读编号再赋给单元。)
        Composite constituents and creep-material bindings require additional
        SDK options: discover mdb.add_material with list_qtmodel_api and use
        call_qtmodel_api with verified parameters. The dedicated tool exposes
        neither composite_info nor creep_id (组合主辅材及徐变绑定经网关设置).

        Args:
            name: Material name (材料名称)
            mat_type: Material type (材料类型): 1=Concrete(混凝土), 2=Steel(钢材),
                      3=Prestress(预应力), 4=Rebar(钢筋), 5=Custom(自定义), 6=Composite(组合)
            standard: Code standard index, starts from 1 (规范序号，从1开始)
            database: Material database name, e.g. 'C50', 'Q345' (数据库名称)
            data_info: Custom material properties [E, γ, ν, α]; required for mat_type=5
                       自定义材料参数 [弹性模量, 容重, 泊松比, 热膨胀系数]，mat_type=5 时必填
            is_orthotropic: Enable orthotropic material behavior. None keeps the
                            upstream default (False); explicit values require a
                            supporting qtmodel build (是否正交异性；省略保持默认，需新版)
            ey: Elastic modulus along the element local Y axis, in Pa. None keeps
                the upstream default (3.45e10); use with is_orthotropic=True
                (单元局部Y向弹性模量，Pa；用于正交异性材料，需新版 qtmodel)
        """
        try:
            if mat_type == 5 and data_info is None:
                raise ToolInputError(
                    "mat_type=5 (custom) requires data_info [E, γ, ν, α] "
                    "(自定义材料必须提供 data_info)"
                )
            kwargs: dict[str, Any] = {}
            if data_info:
                kwargs["data_info"] = data_info
            if is_orthotropic is not None:
                kwargs["is_orthotropic"] = is_orthotropic
            if ey is not None:
                kwargs["ey"] = ey
            provider.add_material(
                name=name,
                mat_type=mat_type,
                standard=standard,
                database=database,
                **kwargs,
            )
            return f"Successfully created material '{name}' (成功创建材料 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating material (创建材料失败): {e}") from e

    @mcp.tool()
    def add_time_parameter(
        name: str,
        code_index: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 1000] = 1,
        time_parameter: list[FiniteNumber] | None = None,
        creep_data: list[FunctionReference] | None = None,
        shrink_data: str = "",
        index: int = -1,
    ) -> str:
        """
        Define a named creep-and-shrinkage material, either by a design code
        or by custom functions (添加收缩徐变材料).

        Writes to the model and refreshes it. This is a named DEFINITION that
        other materials then reference; it applies no load by itself. Creep
        analysis must also be turned on with configure_analysis(do_creep=True).

        Custom functions use code_index=1000: create them first with
        add_creep_function and add_shrink_function, then pass their NAMES here.
        creep_data is NOT a time-value table — that format belongs to
        add_creep_function.

        (写模型并刷新。这是一个命名定义，由其它材料引用，自身不施加荷载。徐变分析
        还需用 configure_analysis(do_creep=True) 打开。自定义函数须配 code_index=1000：
        先用 add_creep_function / add_shrink_function 建好，再把"函数名"传进来。
        creep_data 不是时间-数值表——那种格式属于 add_creep_function。)

        Material binding via creep_id is available through mdb.add_material
        in the gateway, not through create_material's exposed parameters.
        Returns a confirmation; the SDK does not specify same-name replacement
        rules here, so inspect the bridge before redefining a name.
        (材料的 creep_id 绑定经网关；重名处理由桥通决定，先核对再重定义。)

        Args:
            name: Creep-and-shrinkage material name (收缩徐变材料名)
            code_index: Design code, or 1000 for user-defined functions
                        (规范编号；1000 为用户自定义函数):
                        1=JTG 3362-2018(公规，默认) | 2=JTG D62-2004(公规)
                        3=JTJ 023-85(公规) | 4=TB 10092-2017(铁规)
                        5=GB 50157-2013(地铁) | 6=ageing theory(老化理论)
                        7=BS 5400-4-1990 | 8=AASHTO LRFD 2017
                        9=BS EN 1992-2:2005 | 1000=user-defined(用户自定义)
            time_parameter: Code-specific parameters for codes 1–9; omit to keep
                            the code's defaults. When given, the count is fixed per
                            code: 1→4, 2→3, 3→4, 4→5, 5→3, 6→4, 7→4, 8→2, 9→5
                            (规范 1–9 的参数表，省略则用规范默认值；给出时个数按规范固定)
            creep_data: Required with code_index=1000 and only allowed there:
                        [[function_name, age], ...], where function_name is from
                        add_creep_function and age is the loading age in days.
                        NOT [[time, value]].
                        (仅 code_index=1000 使用且必填：[[函数名, 加载龄期(天)], ...]；
                        函数名来自 add_creep_function。不是 [[时间, 数值]]。)
            shrink_data: Name of a shrinkage function from add_shrink_function,
                         used with code_index=1000; empty string means none
                         (收缩函数名，来自 add_shrink_function，配合 1000 使用；空字符串表示不用)
            index: Material ID, -1 to auto-assign (材料编号，-1 自动生成)
        """
        try:
            # 各规范参数个数与 qtmodel 2.9 客户端校验一致（上游以桥通 C# 日志核对）
            parameter_counts = (4, 3, 4, 5, 3, 4, 4, 2, 5)
            if code_index == 1000:
                if not creep_data:
                    raise ToolInputError(
                        "code_index=1000 (user-defined) requires creep_data "
                        "[[function_name, age], ...] (用户自定义须提供 creep_data)"
                    )
                if time_parameter is not None:
                    raise ToolInputError(
                        "time_parameter applies to design codes 1–9, not code_index=1000 "
                        "(time_parameter 只用于规范 1–9)"
                    )
            else:
                if creep_data is not None:
                    raise ToolInputError(
                        "Custom creep functions require code_index=1000; design code "
                        f"{code_index} ignores creep_data (自定义徐变函数须配 code_index=1000)"
                    )
                expected = parameter_counts[code_index - 1]
                if time_parameter is not None and len(time_parameter) != expected:
                    raise ToolInputError(
                        f"code_index={code_index} takes {expected} time_parameter values, "
                        f"got {len(time_parameter)} (该规范参数个数应为 {expected})"
                    )
            kwargs: dict[str, Any] = {
                "name": name,
                "code_index": code_index,
                "index": index,
            }
            if time_parameter is not None:
                kwargs["time_parameter"] = time_parameter
            if creep_data is not None:
                kwargs["creep_data"] = [tuple(item) for item in creep_data]
            if shrink_data:
                kwargs["shrink_data"] = shrink_data

            provider.add_time_parameter(**kwargs)
            return f"Successfully added time parameter '{name}' (成功添加时间依存参数 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding time parameter (添加时间依存参数失败): {e}") from e

    @mcp.tool()
    def add_creep_function(
        name: str,
        creep_data: CurvePoints,
        scale_factor: float = 1.0,
    ) -> str:
        """
        Store a named creep-coefficient curve (定义命名徐变系数曲线).

        Use measured/custom creep data here; use add_time_parameter for a
        code-based creep-and-shrinkage material, or add_shrink_function for
        shrinkage strain. To use this curve, reference its name in
        add_time_parameter(code_index=1000, creep_data=[[name, loading_age]]).
        Creating the curve alone neither assigns it to elements nor solves.
        (自定义徐变曲线用本工具；规范收缩徐变材料用 add_time_parameter。
        曲线须被 code_index=1000 的材料引用，自身不分配给单元或启动分析。)

        Writes the definition, refreshes the model and returns a confirmation.
        Points are sent in their supplied order, including duplicates; the
        bridge owns interpolation and same-name handling. For intentional
        edits, discover mdb.update_creep_function with list_qtmodel_api first.

        Args:
            name: Curve name later referenced by the time-dependent material
                  (后续收缩徐变材料引用的函数名)
            creep_data: Creep coefficient over time [[time(days), coefficient], ...]
                        with at least one finite pair; order is preserved
                        (徐变系数表 [[天数, 无量纲系数], ...]，至少一个有限数值对，保留顺序)
            scale_factor: Curve scale factor forwarded unchanged to QiaoTong;
                points are not pre-scaled locally. Scaling interpretation is
                owned by the bridge (缩放因子单独传递，本地不乘点值，具体缩放含义由桥通确定)
        """
        try:
            creep_tuples = [tuple(item) for item in creep_data]
            provider.add_creep_function(
                name=name, creep_data=creep_tuples, scale_factor=scale_factor
            )
            return f"Successfully added creep function '{name}' (成功添加徐变函数)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding creep function (添加徐变函数失败): {e}") from e

    @mcp.tool()
    def add_shrink_function(
        name: str,
        shrink_data: CurvePoints,
        scale_factor: float = 1.0,
    ) -> str:
        """
        Add user-defined shrinkage function (添加自定义收缩函数).

        Use shrinkage strain here and add_creep_function for creep coefficients.
        Reference this name in add_time_parameter's shrink_data with code_index=1000
        and the required creep-function references. The curve alone assigns no
        material and does not solve. Order and duplicate points pass through;
        interpolation and same-name handling belong to the bridge. Returns a
        confirmation after refresh (收缩应变曲线须由自定义收缩徐变材料引用；保留点序，
        不自动赋材或求解，插值/重名规则由桥通决定).

        Args:
            name: Function name (函数名称)
            shrink_data: Shrinkage strain over time [[time(days), strain], ...];
                         at least one point
                         (收缩应变表 [[天数, 应变], ...]，至少一个点)
            scale_factor: Factor sent separately from the original points;
                no local scaling. Verify its interpretation in QiaoTong
                (比例系数单独传递，点值不在本地缩放，具体含义须核验)
        """
        try:
            provider.add_shrink_function(
                name=name,
                shrink_data=[tuple(item) for item in shrink_data],
                scale_factor=scale_factor,
            )
            return f"Successfully added shrink function '{name}' (成功添加收缩函数)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding shrink function (添加收缩函数失败): {e}") from e

    @mcp.tool()
    def create_section(
        name: str,
        sec_type: str,
        sec_info: list[float] | None = None,
        mat_combine: list[float] | None = None,
        box_num: int | None = None,
        box_height: float | None = None,
        symmetry: bool = True,
        chamfer_info: list[str] | None = None,
    ) -> str:
        """
        Create a cross-section (创建截面) — one tool for all parametric section types.

        This writes a section with automatic numbering (index=-1).
        Read sections before and after calling, then use
        the actual ID for elements. Initial property calculation belongs to the
        bridge; the response only confirms the requested name (请求自动分配截面号，
        创建前后回读；初始特性由桥通计算，返回名称确认).

        Args:
            name: Section name (截面名称)
            sec_type: Section type, Chinese enum (截面类型，中文枚举)。
                sec_info layout per type (各类型 sec_info 参数顺序):
                ─ 基本形状 ─
                "矩形":       [宽, 高]
                "圆形":       [直径]
                "圆管":       [直径, 壁厚]
                "箱型":       [宽, 高, 底宽, 腹板厚, 顶板厚, 底板厚]
                "T形":        [宽, 高, 腹板厚, 顶板厚]
                "倒T形":      [宽, 高, 腹板厚, 底板厚]
                "I字形":      [顶宽, 底宽, 高, 腹板厚, 顶板厚, 底板厚]
                "马蹄T形":    [宽, 高, 腹板厚, 翼缘厚, 腹板底渐变高, 顶倒角宽, 顶倒角高, 底倒角宽, 底倒角高]
                "实腹八边形": [宽, 高, 倒角高, 倒角宽]
                "空腹八边形": [宽, 高, 腹板厚, 顶板厚, 底板厚, 倒角宽, 倒角高]
                "内八角形":   [宽, 高, 腹板厚, 顶板厚, 底板厚, 倒角宽, 倒角高]
                "实腹圆端形": [宽, 高]
                "空腹圆端形": [宽, 高, 壁厚]
                ─ 混凝土/组合 ─
                "I字型混凝土": [顶宽, 底宽, 高, 腹板厚, 顶板厚, 底板厚, 顶倒角宽, 顶倒角高, 底倒角宽, 底倒角高]
                "钢管砼":     [直径, 壁厚]
                "钢箱砼":     [宽, 高, 底宽, 腹板厚, 顶板厚, 底板厚]
                "混凝土箱梁": 顶板/腹板/底板参数列表，配合 box_num/box_height/symmetry/chamfer_info
                "工字组合梁" | "箱形组合梁" | "自定义组合梁": sec_info + mat_combine(材料组合比)
                ─ 钢结构带肋 ─
                "带肋H截面":   [高, 宽, 左右腹板厚, 横腹板厚, 腹板肋高, 腹板肋厚]
                "钢工字型带肋": [顶宽, 底宽, 腹板高, 顶板厚, 底板厚, 腹板厚, 顶缘肋距, 肋数, 肋距, 肋高, 肋厚]
                "带肋钢箱":   [宽, 高, 腹板厚, 顶板厚, 底板厚, 顶底板肋高, 顶底板肋厚, 腹板肋高, 腹板肋厚,
                              顶底板肋距, 腹板肋距, 腹板肋数, 顶底板肋数]
                "钢桁箱梁3":  [高, 宽, 顶悬臂肋高, 底悬臂肋高, 腹板厚, 顶板厚, 底板厚, 顶板肋高, 顶板肋厚,
                              底板肋高, 底板肋厚, 腹板肋高, 腹板肋厚]
                "钢桁箱梁1":  [高, 宽, 左悬臂宽, 右悬臂宽, 底悬臂高, 腹板厚, 顶板厚, 底板厚, 顶板肋高, 顶板肋厚,
                              底板肋高, 底板肋厚, 顶缘腹板肋距, 腹板肋数, 腹板肋距, 腹板肋高, 腹板肋厚,
                              左腹板肋位置, 右腹板肋位置, 左悬臂肋距, 左悬臂肋高, 左悬臂肋厚, 左悬臂肋顶距,
                              左悬臂肋底距, 左悬臂肋倒角, 右悬臂肋距, 右悬臂肋高, 右悬臂肋厚, 右悬臂肋顶距,
                              右悬臂肋底距, 右悬臂肋倒角]  (32项)
                "钢桁箱梁2":  [高, 宽, 左上悬臂宽, 右上悬臂宽, 左下悬臂宽, 右下悬臂宽, 腹板厚, 顶板厚, 底板厚,
                              顶板肋高, 顶板肋厚, 底板肋高, 底板肋厚, 顶缘腹板肋距, 腹板肋数, 腹板肋距,
                              腹板肋高, 腹板肋厚, 左腹板肋位置, 右腹板肋位置, 左上悬臂肋距, 左上悬臂肋高,
                              左上悬臂肋厚, 左上悬臂肋顶距, 左上悬臂肋底距, 左上悬臂肋倒角, 右上悬臂肋距,
                              右上悬臂肋高, 右上悬臂肋厚, 右上悬臂肋顶距, 右上悬臂肋底距, 右上悬臂肋倒角,
                              左下悬臂肋距, 左下悬臂肋高, 左下悬臂肋厚, 右下悬臂肋距, 右下悬臂肋高,
                              右下悬臂肋厚]  (38项)
            sec_info: Section dimensions in the order shown above (按上表顺序的截面尺寸参数)
            mat_combine: Material combination ratios for composite sections (组合梁材料组合比)
            box_num: Number of box cells, concrete box girder only (箱室数，混凝土箱梁)
            box_height: Box girder height, concrete box girder only (箱梁梁高)
            symmetry: Symmetric section, concrete box girder (是否对称截面)
            chamfer_info: Chamfer info strings, concrete box girder (倒角信息)

        For non-parametric sections use: create_polygon_section (任意多边形),
        create_line_width_section (线宽), create_section_from_properties (按特性值).

        Example:
            create_section(name="主梁", sec_type="矩形", sec_info=[1.0, 1.5])
            create_section(name="钢管", sec_type="圆管", sec_info=[0.6, 0.016])
        """
        try:
            kwargs: dict[str, Any] = {}
            if sec_info:
                kwargs["sec_info"] = sec_info
            if mat_combine is not None:
                kwargs["mat_combine"] = mat_combine
            if box_num is not None:
                kwargs["box_num"] = box_num
            if box_height is not None:
                kwargs["box_height"] = box_height
            if chamfer_info is not None:
                kwargs["chamfer_info"] = chamfer_info
            if sec_type == "混凝土箱梁":
                kwargs["symmetry"] = symmetry
            provider.add_section(name=name, sec_type=sec_type, **kwargs)
            return f"Successfully created section '{name}' (type: {sec_type}) (成功创建截面 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating section (创建截面失败): {e}") from e

    @mcp.tool()
    def create_polygon_section(
        name: str,
        loop_segments: dict[str, SectionLoop]
    ) -> str:
        """
        Create a custom section from polygon outlines and holes (创建多边形截面).

        Use create_section for a standard parametric shape, create_line_width_section
        for thin-wall centreline segments, or calc_section_property to calculate
        properties without adding a section. This writes a section definition;
        use get_model_data(kind="sections") to obtain its ID before assigning it.
        Supply points in perimeter order with no self-intersections; holes must lie
        inside the main outline. Missing closing points are appended automatically.
        Basic point count/area is checked; verify hole containment and intersection
        topology before calling. Requests automatic numbering (index=-1);
        verify backend handling before reusing a section name.
        (按边界顺序输入截面平面坐标，孔洞应在外圈内部；自动补闭合点。)

        Args:
            name: Section name (截面名称)
            loop_segments: One main outline and optional sub1/sub2/... holes, each with
                at least three distinct finite [y,z] points in the section plane,
                using model length units. These are 2D section coordinates, not global
                XYZ node coordinates (main外圈，sub前缀为内孔；截面平面二维坐标)

        Example:
            create_polygon_section(name="Rectangle",
                loop_segments={"main": [[0,0], [2,0], [2,1], [0,1]]})

        Returns:
            Success message with the section name; malformed rings or backend failures
            produce MCP errors. No elements are created or reassigned.
        """
        try:
            provider.add_section(
                name=name,
                sec_type="自定义线圈截面",
                sec_info=[],
                loop_segments=[_closed_polygon_loops(loop_segments)]
            )
            return f"Successfully created polygon section '{name}'"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating polygon section: {e}") from e

    @mcp.tool()
    def create_line_width_section(
        name: str,
        sec_lines: list[FiveNumbers]
    ) -> str:
        """
        Create a section from thin-walled centreline segments (创建线宽截面).

        Writes to the model. The shape is described as a skeleton: each segment
        is a centreline with a wall thickness, which suits thin-walled steel
        box and I-shapes. Describe the actual wall junctions; the wrapper does
        not join or reorder segments. These are section-plane lines, not plate
        elements in the global model.

        The wrapper calls add_section without supplied properties, leaving
        initial property calculation to the bridge. Read the resulting section
        with get_model_data(kind="section_property", sec_id=...). Use
        calculate_section_property when all existing sections need recomputing.
        The wrapper requests automatic numbering (index=-1).
        Read back sections before and after creation.
        Returns the requested name in a confirmation, not computed properties.

        When to use vs. siblings: thin-walled centreline shapes here; a solid
        outline given as polygon loops → create_polygon_section; properties you
        already know → create_section_from_properties; only inspecting the
        properties of a shape without adding a section → calc_section_property.

        (写模型。用"骨架"描述截面：每段是一条中心线加壁厚，适合薄壁钢箱、工字形等。
        按实际壁交点输入，本包装不连接或重排线段；初始特性计算交给桥通，创建后回读。
        本工具请求自动分配截面号；需全模型重算时调
        calculate_section_property。返回确认消息，不含特性值。选型：薄壁中心线
        形状用本工具；实体轮廓按多边形环给出用 create_polygon_section；已知特性值直接
        建用 create_section_from_properties；只想算某形状的特性而不建截面用
        calc_section_property。)

        Args:
            name: Section name (截面名称)
            sec_lines: Centreline segments with wall thickness, as
                       [[y1, z1, y2, z2, thickness], ...] — the two endpoints of
                       each segment in section coordinates, then its thickness
                       (中心线段与壁厚，[[y1, z1, y2, z2, 壁厚], ...]，前四个为该段
                       在截面坐标系中的两个端点，最后为壁厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="线宽",
                sec_info=[],
                sec_lines=sec_lines
            )
            return f"Successfully created line-width section '{name}'"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating line-width section: {e}") from e

    @mcp.tool()
    def create_section_from_properties(
        name: str,
        area: float,
        ix: float,
        iy: float,
        iz: float,
        sec_property: list[float] | None = None
    ) -> str:
        """
        Create a section directly from its pre-calculated properties (通过截面特性直接创建截面).

        Use create_section/create_polygon_section/create_line_width_section when
        geometry should determine properties; calc_section_property only evaluates
        candidate geometry. Here supplied properties skip bridge calculation.
        Requests automatic numbering with index=-1; read back the actual ID.
        Returns a confirmation without assigning elements.
        (已有特性直接建截面，不自动由几何补算；回读编号后再赋给单元。)

        Args:
            name: Section name (截面名称)
            area: Cross-sectional area (横截面面积 Area)
            ix: Torsional constant (扭转惯性矩 Ixx)
            iy: Moment of inertia about y-axis (抗弯惯性矩 Iyy)
            iz: Moment of inertia about z-axis (抗弯惯性矩 Izz)
            sec_property: Complete native property vector; current SDK accepts
                26 or 29 values in its UI/export order. When None, this wrapper
                builds [area,0,0,ix,iy,iz] + 23 zeros; verify omitted properties
                before analysis. A supplied list takes precedence over scalars.
                (原生26/29项；省略时仅填面积/惯性矩，其余补零，不代表完整工程截面特性)
        """
        try:
            if sec_property is None:
                sec_property = [area, 0, 0, ix, iy, iz] + [0] * 23

            provider.add_section(
                name=name,
                sec_type="任意",
                sec_info=[],
                sec_property=sec_property
            )
            return f"Successfully created property-based section '{name}'"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating property-based section: {e}") from e

    @mcp.tool()
    def create_tapered_section(
        name: str,
        begin_id: int,
        end_id: int,
        shear_consider: bool = True,
        sec_normalize: bool = False
    ) -> str:
        """
        Create a tapered section definition joining two existing end sections
        (由两个已有端截面定义渐变截面).

        First create the constant end sections with create_section (or a custom
        section tool), then use their saved section IDs as begin_id and end_id.
        These are section IDs, not node or element IDs. Use create_section for
        a constant section; use this tool when the start and end shapes differ.

        The call writes one section definition and refreshes the model. Assign
        the resulting section to elements with create_beam_element or
        update_element_section. For a taper extending across several elements,
        add_tapper_section_group defines the interpolation law after assignment.
        Creating the definition alone does not create those elements or groups.

        Returns a confirmation with the name. To obtain the automatically
        allocated ID, read get_model_data(kind="sections") before assignment.
        The bridge validates end-section compatibility and duplicate names;
        this wrapper does not preflight either condition.
        (先建立两端截面并取得真实编号；创建后回读新编号再赋给单元。
        多单元连续变化规律由 add_tapper_section_group 设置。)

        Args:
            name: Tapered section name (渐变截面名称)
            begin_id: Start section ID (起始截面编号)
            end_id: End section ID (终止截面编号)
            shear_consider: Consider shear deformation (是否考虑剪切变形), default True
            sec_normalize: Adaptively order the end sections' loops/line-width
                contours when their drawing order differs; default False
                (自动匹配两端线圈/线宽绘制顺序，避免渲染和计算失效；默认关闭)
        """
        try:
            provider.add_tapper_section_by_id(
                name=name,
                begin_id=begin_id,
                end_id=end_id,
                shear_consider=shear_consider,
                sec_normalize=sec_normalize
            )
            return f"Successfully created tapered section '{name}' (成功创建渐变截面)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating tapered section (创建渐变截面失败): {e}") from e

    @mcp.tool()
    def add_tapper_section_group(
        name: str,
        ids: list[int] | str | None = None,
        factor_w: float = 1.0,
        factor_h: float = 1.0,
        ref_w: Literal[0, 1] = 0,
        ref_h: Literal[0, 1] = 0,
        dis_w: float = 0,
        dis_h: float = 0,
    ) -> str:
        """
        Group elements so their sections vary continuously along the group
        (添加变截面组，使组内单元截面沿纵向连续变化).

        Writes to the model and refreshes it. The elements must already exist
        and carry tapered sections (create_tapered_section); this tool defines
        the LAW by which the section interpolates across them, not the sections
        themselves.

        factor_w / factor_h are variation ORDERS (exponents), not scale factors:
        1.0 gives a linear taper, any other value gives a power-law taper. They
        never multiply the section dimensions.

        Only the simple power-law form is exposed here. Parametric groups —
        per-parameter laws keyed by the UI parameter name, supporting nonlinear
        / piecewise-custom / circular-arc variation — need the escape hatch:
        call_qtmodel_api(api_object="mdb", method="add_tapper_section_group",
                         kwargs={..., "parameter_info": {"梁高(H)": "1,2,I,0"}}).

        (写模型并刷新。单元须已存在且已赋变截面(create_tapered_section)；本工具定义的是
        截面沿组内插值的"变化规律"，不是截面本身。factor_w / factor_h 是变化阶数(指数)
        而非缩放系数：1.0 为线性变化，其它值为幂次非线性变化，它们不会去乘截面尺寸。
        本工具只暴露简单的幂次形式；参数化变截面组（按 UI 参数名分别指定规律，支持
        非线性/自定义分段/圆弧三种）需经逃生舱传 parameter_info。)

        create_structure_group/add_to_structure_group manage membership only;
        they do not define taper laws. The legacy spelling tapper is retained.
        Returns a confirmation; same-name replacement rules are not specified
        by the SDK (普通结构组不定义变化规律；重名行为须核验，保留历史拼写 tapper).

        Args:
            name: Group name (变截面组名称)
            ids: Element IDs in the group — list or "XtoYbyN" range string
                 (变截面组内的单元编号，支持列表或 "XtoYbyN" 范围字符串)
            factor_w: Variation ORDER in the width direction; 1.0=linear,
                      other=nonlinear power law
                      (宽度方向变化阶数；1.0 为线性，其它为幂次非线性)
            factor_h: Variation ORDER in the height direction; 1.0=linear,
                      other=nonlinear power law
                      (高度方向变化阶数；1.0 为线性，其它为幂次非线性)
            ref_w: Which end the width variation is measured from
                   (宽度方向参考点): 0=I-end(i端) | 1=J-end(j端)
            ref_h: Which end the height variation is measured from
                   (高度方向参考点): 0=I-end(i端) | 1=J-end(j端)
            dis_w: Distance along the width direction (宽度方向距离)
            dis_h: Distance along the height direction (高度方向距离)
        """
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "factor_w": factor_w,
                "factor_h": factor_h,
                "ref_w": ref_w,
                "ref_h": ref_h,
                "dis_w": dis_w,
                "dis_h": dis_h,
            }
            if ids is not None:
                kwargs["ids"] = ids
            provider.add_tapper_section_group(**kwargs)
            return f"Successfully added tapered section group '{name}' (成功添加变截面组)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding tapered section group (添加变截面组失败): {e}") from e

    @mcp.tool()
    def add_thickness(
        name: str,
        t: float = 0.1,
        thick_type: Literal[0, 1] = 0,
        index: int = -1,
        t_out: float | None = None,
    ) -> str:
        """
        Add a plate thickness property (添加板厚度).

        Args:
            name: Thickness name (厚度名称)
            t: In-plane/base thickness in meters (面内/基板厚度 m)
            thick_type: Thickness type (厚度类型): 0=普通板, 1=加劲肋板
            index: ID index, -1 for auto (编号，-1自动生成)
            t_out: Out-of-plane thickness in meters; omitted means the same as t.
                   Requires a qtmodel build exposing t_out; older builds reject
                   an explicit value before creating anything.
                   (面外厚度 m；省略时与 t 相同，旧版不支持时明确报错)

        For rib geometry and other advanced properties, discover add_thickness
        with list_qtmodel_api and use call_qtmodel_api.
        （加劲肋尺寸等完整参数请先检索签名，再通过 API 网关调用。）
        """
        try:
            kwargs: dict[str, Any] = {"name": name, "t": t, "thick_type": thick_type, "index": index}
            if t_out is not None:
                kwargs["t_out"] = t_out
            provider.add_thickness(**kwargs)
            detail = f" (t={t} m, t_out={t_out} m)" if t_out is not None else ""
            return f"Successfully added thickness '{name}' (成功添加板厚度){detail}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding thickness (添加板厚度失败): {e}") from e

    @mcp.tool()
    def add_effective_width(
        element_ids: int | list[int] | str,
        factor_i: float,
        factor_j: float,
        dz_i: float = 0,
        dz_j: float = 0,
        group_name: str = "",
    ) -> str:
        """
        Reduce beam bending stiffness to model effective flange width
        (添加有效宽度系数，用折减刚度体现翼缘有效宽度).

        Writes to the model and refreshes it. Despite the name it applies no
        width: it scales the section's Iy at each element end and can shift the
        centroid, which is how a reduced effective flange width is represented.

        This is a BOUNDARY-GROUP entry, not a section property. It therefore
        follows the boundary group's activation in construction-stage analysis —
        the group must exist (create_boundary_group) and be activated by a stage
        (add_construction_stage's active_boundaries) to take effect.

        Only the Iy/centroid-z pair is exposed. Current qtmodel also documents
        Iz factors, local-y centroid shifts and axial-area factors. Discover
        mdb.add_effective_width with list_qtmodel_api before using those options
        through call_qtmodel_api; older SDK builds may document them differently.
        The bridge controls repeated boundary definitions. Returns a confirmation;
        no analysis runs here. Verify centroid-shift units in the bridge.

        (写模型并刷新。名字虽叫有效宽度，实际不施加任何宽度：它按单元两端折减截面 Iy、
        并可平移形心，以此体现翼缘有效宽度的折减。本项属于边界组、不是截面属性，因此在
        施工阶段分析中随边界组激活生效——边界组须已建立，且被某阶段的 active_boundaries
        激活。本工具只暴露 Iy 与形心 z 这一对；上游另有 z 向系数、y 向形心平移与轴向系数，
        当前 SDK 已说明这些参数；旧版说明可能不同，先检索真实签名再经网关调用。
        形心偏移单位和重复定义策略须核对桥通；本调用只返回确认、不求解。)

        Args:
            element_ids: Element ID(s) — int, list, or "XtoYbyN" range string
                         (单元编号，支持整数、列表或 "XtoYbyN" 范围字符串)
            factor_i: Reduction factor applied to Iy at the I-end; a value below
                      1.0 softens the element in bending
                      (I端截面 Iy 折减系数；小于 1.0 即削弱抗弯刚度)
            factor_j: Reduction factor applied to Iy at the J-end
                      (J端截面 Iy 折减系数)
            dz_i: Centroid shift in z at the I-end (I端截面形心 z 向变换量)
            dz_j: Centroid shift in z at the J-end (J端截面形心 z 向变换量)
            group_name: Boundary group name, empty for the default boundary
                        group (边界组名，空则用默认边界组)
        """
        try:
            kwargs: dict[str, Any] = {
                "element_ids": element_ids,
                "factor_i": factor_i,
                "factor_j": factor_j,
                "dz_i": dz_i,
                "dz_j": dz_j,
            }
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_effective_width(**kwargs)
            return f"Successfully added effective width to elements {element_ids} (成功添加有效宽度)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding effective width (添加有效宽度失败): {e}") from e

    @mcp.tool()
    def update_section_bias(
        index: int,
        bias_type: str,
        center_type: str = "质心",
        shear_consider: bool = True,
        bias_point: TwoNumbers | None = None,
        side_i: bool = True
    ) -> str:
        """
        Change the alignment and eccentricity of an existing section definition
        (修改已有截面定义的对齐和偏心设置).

        Select a saved section ID, not an element ID. Use this to position the
        section relative to its reference axis; update_element_section changes
        which section an element uses, and update_element_beta rotates an element.
        Read get_model_data(kind="sections") to identify the intended definition.

        bias_type selects a named alignment. Supply bias_point only for the
        custom alignment; its two components use the section-plane coordinates
        and length convention shown in the bridge. For a tapered section,
        side_i selects I or J, so changing both ends requires two calls.

        Each call sends center_type and shear_consider, including their defaults;
        they are not partial-update sentinels. The command changes a shared
        section definition and can affect every element using it. Returns a
        confirmation without recalculating analysis or returning section data.
        (按截面编号修改，可能影响全部引用单元；两端分别设置，中心类型与剪切选项均会提交。)

        Args:
            index: Section ID (截面编号)
            bias_type: Bias type (偏心类型): e.g. "中心", "中上", "中下", "左上", "右上", "左下", "右下"
            center_type: Center type (中心类型): "质心" (Centroid) or "剪心" (Shear center), default "质心"
            shear_consider: Consider shear deformation (是否考虑剪切变形), default True
            bias_point: Two custom offsets in the bridge's section-plane coordinates;
                        used only with custom alignment (自定义偏心的两个截面平面分量)
            side_i: Apply to I-end (应用于I端) - for tapered sections True means I-end, False means J-end, default True
        """
        try:
            provider.update_section_bias(
                index=index,
                bias_type=bias_type,
                center_type=center_type,
                shear_consider=shear_consider,
                bias_point=bias_point,
                side_i=side_i
            )
            return f"Successfully updated section {index} bias to '{bias_type}' (成功更新截面偏心)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating section bias (更新截面偏心失败): {e}") from e

    @mcp.tool()
    def remove_section(ids: SelectedIds) -> str:
        """
        Delete explicitly selected section definitions from the active model
        (按编号删除指定截面定义).

        Use this for known section IDs. Use remove_unused_sections for automatic
        cleanup of unused definitions, or remove_elements to delete elements.
        Inspect get_model_data(kind="sections") and element assignments first;
        update_element_section changes an assignment without deleting a section.

        Requires a nonempty ID selection. The tool validates that selection,
        submits one delete command, refreshes the model and returns a confirmation.
        It does not create a backup or reassign elements. Referenced-section
        rejection, cascading effects and ID handling belong to the bridge, so
        inspect affected elements before continuing with cached section IDs.
        Save a model checkpoint if the definitions may need to be restored.
        (空选择会被拒绝；删除后刷新并返回确认，不自动备份或改配单元截面。
        引用关系由桥通处理，应先核对使用情况并保存需要保留的模型。)

        Args:
            ids: Section ID(s) to delete. Supports int, list, or range string '3to5'.
                 (截面编号，支持整数、列表或范围字符串)
        """
        try:
            provider.remove_section(ids=ids)
            return f"Successfully removed section(s) {ids} (成功删除截面)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing section (删除截面失败): {e}") from e

    @mcp.tool()
    def update_section_property(
        index: int,
        sec_property: SectionProperties,
        side_i: bool = True
    ) -> str:
        """
        Directly modify the calculated properties of a section (直接修改截面特性值).

        Use this to manually override Area, Ix, Iy, Iz etc. after creation.
        Typically used for fine-tuning or correcting auto-calculated values.
        (用于手动覆盖截面面积、惯性矩等自动计算值)

        Args:
            index: Section ID (截面编号)
            sec_property: The complete property table, in QiaoTong UI order:
                          exactly 26 values (legacy layout) or 29 values (full layout)
                          [Area, Asy, Asz, Ixx, Iyy, Izz, ...]
                          (完整截面特性表，按桥通界面顺序：26 项旧格式或 29 项完整格式，
                          依次为面积、剪切面积y、剪切面积z、扭转惯性矩、抗弯惯性矩y、抗弯惯性矩z …)
            side_i: For tapered sections, True=I-end, False=J-end (变截面时 True=I端, False=J端)
        """
        try:
            provider.update_section_property(
                index=index, sec_property=sec_property, side_i=side_i
            )
            return f"Successfully updated section {index} properties (成功修改截面 {index} 特性)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating section property (修改截面特性失败): {e}") from e

    @mcp.tool()
    def calculate_section_property() -> str:
        """
        Recalculate and store properties for all existing model sections
        (重新计算并保存模型中所有截面的特性).

        Use after changing stored section geometry. This model-write operation
        requires an editable model and updates section properties such as area
        and inertias. It returns a completion message, not the property values.
        Read values with get_model_data(kind="section_property", sec_id=...).

        For a trial polygon or line-width geometry, use calc_section_property:
        it returns calculated values without creating or updating model sections.
        (修改已有截面几何后使用，须允许模型写入；返回完成消息，数值经
        get_model_data 回读。试算几何用 calc_section_property，不修改已有截面。)
        """
        try:
            provider.calculate_section_property()
            return "Successfully recalculated all section properties (成功重新计算所有截面特性)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error calculating section properties (计算截面特性失败): {e}") from e

    @mcp.tool()
    def set_support(
        node_id: int | list[int] | str,
        dx: bool = True,
        dy: bool = True,
        dz: bool = True,
        rx: bool = False,
        ry: bool = False,
        rz: bool = False,
        group_name: str = "",
        coordinate: Literal[0, 1] | None = None,
        extra_enabled: bool | None = None,
        extra_parameters: SupportExtraParameters | None = None,
    ) -> str:
        """
        Set fixed/free translational and rotational restraints on existing nodes
        (为已有节点设置六自由度固定或自由支承).

        Use for idealized restraints. add_elastic_support defines finite spring
        stiffness, add_support_settlement applies prescribed displacement as a
        load, and remove_boundary(kind="support") deletes a support definition.
        Nodes must exist; group_name identifies a boundary group, not a load case.

        True fixes a degree of freedom and False leaves it free. The complete
        six-flag vector is sent on every call, replacing existing restraint
        settings for the selected nodes. Defaults fix all translations and leave
        rotations free; supply all desired flags when changing an existing support.
        Every node in a multi-node selection receives the same vector.

        Omitted coordinate/additional settings preserve existing values. Supplying
        extra_parameters enables them unless extra_enabled=False explicitly clears
        them. Writes and refreshes the model, then returns a confirmation; analysis
        must be run separately after the boundary configuration is complete.
        (六项每次整体提交；省略坐标系和附加设置则保留原值。相同约束用于所选全部节点。)

        Args:
            node_id: Node ID(s). Supports int, list, or range string like '1to10'
                     (节点编号，支持整数、列表或范围字符串如 '1to10')
            dx: Fix X translation (固定X平动), default True
            dy: Fix Y translation (固定Y平动), default True
            dz: Fix Z translation (固定Z平动), default True
            rx: Fix X rotation (固定X转动), default False
            ry: Fix Y rotation (固定Y转动), default False
            rz: Fix Z rotation (固定Z转动), default False
            group_name: Boundary group name (边界组名)
            coordinate: 0=global, 1=node coordinate system; None preserves the
                        existing setting on overwrite or uses the creation default
                        (0=整体，1=节点坐标系；省略时覆盖保留原值、新增用默认值)
            extra_enabled: Enable additional support parameters. None enables them
                           when extra_parameters is supplied, otherwise preserves the
                           existing setting. False clears them (提供附加参数时默认启用；
                           两者均省略保留原设置，False 清空；需新版 qtmodel)
            extra_parameters: Exactly [static friction, dynamic friction, Dx, Dy, Dz,
                              Rx, Ry, Rz]; supplying this enables it unless explicitly
                              disabled. None preserves it. Requires a supporting
                              qtmodel build (静摩擦、动摩擦、Dx/Dy/Dz/Rx/Ry/Rz，共8项)
        """
        try:
            boundary_info = [dx, dy, dz, rx, ry, rz]
            kwargs: dict[str, Any] = {}
            if group_name:
                kwargs["group_name"] = group_name
            for key, value in {
                "coordinate": coordinate, "extra_enabled": extra_enabled,
                "extra_parameters": extra_parameters,
            }.items():
                if value is not None:
                    kwargs[key] = value
            provider.add_general_support(
                node_id=node_id, boundary_info=boundary_info, **kwargs
            )
            return f"Successfully set support on node(s) {node_id} (成功设置支承)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting support (设置支承失败): {e}") from e

    @mcp.tool()
    def set_self_weight_stage(
        stage_name: str,
        structure_group_name: str = "默认结构组",
        weight_stage_id: int = 1,
    ) -> str:
        """
        Configure self-weight for a construction stage (设置施工阶段自重).

        IMPORTANT — In QiaoTong, self-weight is NOT a load case. It is controlled
        by each construction stage's "self-weight stage number" per structure group.
        The solver computes gravity load automatically from section area × material
        unit weight × g. You only choose WHICH stage carries a group's self-weight.
        （桥通中自重不是荷载工况，由施工阶段对各结构组的"计自重阶段号"控制，
        求解器按 截面面积 × 材料容重 × 重力加速度 自动计算。）

        For a single-stage / one-shot (一次成桥) model, self-weight is handled when
        you merge stages via merge_operation_stage — you usually do NOT need this tool.
        Use it only to override which stage accounts for a group's self-weight.

        Args:
            stage_name: Construction stage name (施工阶段名)
            structure_group_name: Structure group name (结构组名)
            weight_stage_id: Self-weight stage number (计自重阶段号):
                0=not counted(不计自重), 1=this stage(本阶段), n=stage n(第n阶段)
        """
        try:
            provider.set_weight_stage(
                stage_name=stage_name,
                structure_group_name=structure_group_name,
                weight_stage_id=weight_stage_id,
            )
            return (
                f"Self-weight of group '{structure_group_name}' set to stage "
                f"id {weight_stage_id} for '{stage_name}' (施工阶段自重设置成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting self-weight stage (设置施工阶段自重失败): {e}") from e

    @mcp.tool()
    def set_gravity(gravity: float = 9.8) -> str:
        """
        Set the gravitational acceleration used for self-weight (设置重力加速度).

        Changes the project setting and refreshes the model; it does not run
        analysis or create a self-weight load case. Use set_self_weight_stage
        to choose when a structure group's automatic self-weight participates,
        then run_analysis when new results are required.
        (本工具改总体重力参数；计自重阶段用 set_self_weight_stage，更新结果需另行分析。)

        This is a call to mdb.update_project_setting, whose SDK also sends
        empty project/personnel/date/description fields and reference
        temperature 0. Existing settings are not read and merged here;
        preservation of those fields is not guaranteed. If they matter, read
        get_model_data(kind="project_metadata") or the UI and use the gateway
        with a verified complete update_project_setting payload instead.
        (SDK 同时下发工程信息空值和基准温度 0，本工具不回读合并；需保留自定义总体
        设置时，先核对工程信息/UI，再经网关提交完整设置。) Returns a confirmation.

        Args:
            gravity: Gravitational acceleration in m/s² (重力加速度，单位 m/s²), default 9.8
        """
        try:
            provider.update_project_setting(gravity=gravity)
            return f"Gravity set to {gravity} m/s² (重力加速度已设为 {gravity})"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting gravity (设置重力加速度失败): {e}") from e

    @mcp.tool()
    def apply_nodal_force(
        node_id: int | list[int] | str,
        case_name: str,
        fx: float = 0,
        fy: float = 0,
        fz: float = 0,
        mx: float = 0,
        my: float = 0,
        mz: float = 0,
        group_name: str = "",
    ) -> str:
        """
        Apply a concentrated force and/or moment at nodes (施加节点集中荷载).

        Adds one nodal load to load case case_name for every listed node and
        refreshes the model; create the load case first with create_load_case.
        Components use global axes; with Z upward, downward force has negative
        fz. Values are forwarded without unit conversion. The SDK does not
        specify fixed force/moment units here: verify the bridge's native
        convention using a known load before submitting engineering values.

        The SDK requests an automatic load index (-1), not an in-place update.
        Read existing loads with query_model_data(request={"kind":"loads",
        "load_family":"nodal_force"}) before repeating. To edit a known index,
        discover mdb.update_nodal_force with list_qtmodel_api and call it through
        call_qtmodel_api. Returns a confirmation, not reactions or a load ID.

        When to use vs. siblings: point loads on nodes here; loads spread along
        a beam → apply_beam_distributed_load; a prescribed settlement instead of
        a force → add_support_settlement; automatic structural self-weight →
        set_self_weight_stage and merge_operation_stage.

        (向工况 case_name 的每个指定节点添加集中荷载并刷新模型；需先用
        create_load_case 建好工况。整体 Z 向上时，向下的 fz 取负；不换算单位，
        固定力/力矩单位须从桥通核验。SDK 每次自动分配荷载编号，不是原位修改；
        重复前回读，修改已知编号可经网关调 update_nodal_force。返回确认消息，
        不含反力或荷载编号。节点集中力、沿梁分布力、强制沉降分别选本工具、
        apply_beam_distributed_load、add_support_settlement；自动自重通过
        set_self_weight_stage 和 merge_operation_stage 配置。)

        Args:
            node_id: Node ID(s) — int, list, or "XtoYbyN" range string
                     (节点编号，支持整数、列表或 "XtoYbyN" 范围字符串)
            case_name: Load case name, must already exist (荷载工况名，须已存在)
            fx: Global X force, in verified native force units (整体X向力，桥通原生力单位)
            fy: Global Y force, in verified native force units (整体Y向力，桥通原生力单位)
            fz: Global Z force; negative when Z is upward and load is downward
                (整体Z向力，桥通原生力单位；Z轴向上时向下为负)
            mx: Moment about global X, in native moment units (绕整体X轴力矩，原生力矩单位)
            my: Moment about global Y, in native moment units (绕整体Y轴力矩，原生力矩单位)
            mz: Moment about global Z, in native moment units (绕整体Z轴力矩，原生力矩单位)
            group_name: Load group name, empty for the default group
                        (荷载组名，空则用默认荷载组)
        """
        try:
            load_info = [fx, fy, fz, mx, my, mz]
            kwargs: dict[str, Any] = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_nodal_force(
                node_id=node_id, case_name=case_name, load_info=load_info, **kwargs
            )
            return f"Successfully applied force to node(s) {node_id} in case '{case_name}' (成功施加荷载)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying force (施加荷载失败): {e}") from e

    @mcp.tool()
    def apply_beam_distributed_load(
        element_id: int | list[int] | str,
        case_name: str,
        direction: Literal[1, 2, 3, 4, 5, 6] = 3,
        load_values: list[float] | None = None,
        load_positions: list[float] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply a distributed force along selected beam elements in an existing
        static load case (在已有工况中向梁单元施加分布力).

        Create the elements and case first. Use apply_nodal_force for forces at
        nodes, add_plate_element_load for plate loading, or add_distribute_plane_load
        to place a separately defined plane-load pattern. This tool's positions
        are measured along each selected beam from its I end.

        Pair load_positions with load_values: [0, 1] spans the full element;
        equal endpoint values give a uniform load and differing values describe
        a linear variation. Positions are relative fractions, not physical
        distances. The same profile applies to every selected element. Signs and
        load units follow the chosen global/local axis and the bridge convention;
        the wrapper performs no unit conversion.

        Nonempty lists are passed through without sorting; omitted/empty lists
        use SDK defaults, not a generated load profile. Writes and refreshes the
        model and returns a confirmation without solving. Repeated-load handling
        belongs to the bridge; inspect existing loads before repeating a request.
        (位置和值一一对应，从各单元 I 端量取；单位原样传入，空列表不自动生成荷载。)

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            direction: Load direction (荷载方向): 1=Global X, 2=Global Y, 3=Global Z,
                       4=Local X, 5=Local Y, 6=Local Z
            load_values: Load values at positions (荷载值列表), e.g. [q1, q2] for linear varying
            load_positions: Relative positions 0-1 (荷载位置), e.g. [0, 1] for full span
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {"coord_system": direction}
            if load_values:
                kwargs["list_load"] = load_values
            if load_positions:
                kwargs["list_x"] = load_positions
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_beam_element_load(
                element_id=element_id,
                case_name=case_name,
                load_type=3,  # Distributed force
                **kwargs,
            )
            return f"Successfully applied distributed load on element(s) {element_id} (成功施加分布荷载)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying distributed load (施加分布荷载失败): {e}") from e

    @mcp.tool()
    def add_system_temperature(
        element_id: int | list[int] | str,
        case_name: str,
        temperature: float,
        group_name: str = "",
    ) -> str:
        """
        Apply a uniform temperature to selected elements (均匀单元温度荷载).

        Submits an element-temperature definition to an existing load case,
        refreshes the model and returns a confirmation. Despite the MCP name,
        it calls mdb.add_element_temperature, not the SDK's model-wide
        add_system_temperature. The whole section has one value, no gradient.
        (向已有工况提交指定单元的均匀温度并刷新；底层为 add_element_temperature，
        不是 SDK 中不带单元选择的 add_system_temperature。)

        When to use vs. siblings: uniform element temperature here; linear gradient →
        add_gradient_temperature; code-based section temperature →
        add_beam_section_temperature; arbitrary profile → add_custom_temperature.
        The SDK labels the value "final temperature"; this wrapper does not
        subtract a reference temperature or convert an intended ΔT. Confirm
        that convention in the target bridge. Repeated-call replacement or
        accumulation is not specified by this SDK; inspect existing loads
        before repeating. (SDK 称参数为最终温度，本工具不做温差换算；重复调用行为
        未由 SDK 定义，须核对桥通中的基准温度与既有荷载。)

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            temperature: Native uniform element-temperature value, forwarded
                         unchanged; the SDK describes a final temperature,
                         not an automatically converted ΔT
                         (原样传递的均匀单元温度；SDK 称最终温度，不自动把温差换算为终温)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_system_temperature(
                element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
            )
            return f"Successfully applied system temperature load '{temperature}' to element(s) {element_id} (成功施加体系温度)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying system temperature load (施加体系温度失败): {e}") from e

    @mcp.tool()
    def add_gradient_temperature(
        element_id: int | list[int] | str,
        case_name: str,
        temperature: float,
        section_oriental: Literal[0, 1] = 0,
        element_type: Literal[1, 2] = 1,
        group_name: str = "",
    ) -> str:
        """
        Apply a linear temperature gradient through the section (梯度温度荷载).

        Adds a gradient temperature load to load case case_name for the given
        element(s) and refreshes the model; create the load case first.
        Temperature varies linearly through the section depth.
        (向工况 case_name 的指定单元添加梯度温度并刷新模型；需先建好工况。温度沿截面高度线性变化。)

        When to use vs. siblings: linear gradient here; uniform element temperature →
        add_system_temperature; code-based section temperature →
        add_beam_section_temperature; arbitrary profile → add_custom_temperature.
        (选型：线性梯度用本工具；均匀单元温度用 add_system_temperature；规范梁截面温度用 add_beam_section_temperature；任意分布用 add_custom_temperature。)
        Returns a confirmation without solving. Values and signs pass through;
        verify temperature units and gradient sign in the target bridge. The SDK
        does not specify how repeated definitions combine or replace each other.
        (返回确认，不求解；单位、梯度正负和重复定义处理须按桥通核验。)

        Args:
            element_id: Element ID(s) (单元编号，支持范围字符串)
            case_name: Load case name (荷载工况名)
            temperature: Temperature difference (温差)
            section_oriental: Section direction, beams only (截面方向，仅梁单元):
                0=section Y (截面Y向, default), 1=section Z (截面Z向)
            element_type: Element type (单元类型): 1=beam(梁), 2=plate(板)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {
                "section_oriental": section_oriental,
                "element_type": element_type,
            }
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_gradient_temperature(
                element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
            )
            return f"Successfully applied gradient temperature '{temperature}' to element(s) {element_id} (成功施加梯度温度)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying gradient temperature load (施加梯度温度失败): {e}") from e

    @mcp.tool()
    def add_custom_temperature(
        element_id: int | list[int] | str,
        case_name: str,
        orientation: Literal[1, 2] = 1,
        temperature_data: list[tuple[Literal[1, 2], FiniteNumber, FiniteNumber]] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply an arbitrary temperature profile over the section (自定义温度荷载).

        Adds a custom temperature load to load case case_name for the given
        element(s) and refreshes the model; create the load case first. The
        SDK profile rows are [reference, height, temperature], where reference
        is 1=top or 2=bottom. For example [[1,0.25,12.5],[2,0.10,5.0]]. Rows are
        forwarded in order without interpolation, sorting or unit conversion.
        (需已有工况和梁单元；每行是 [参考位置1顶/2底, 高度, 温度]，按输入顺序原样提交。)

        When to use vs. siblings: arbitrary/measured profile here; uniform element temperature →
        add_system_temperature; linear gradient → add_gradient_temperature;
        code-based section temperature → add_beam_section_temperature.
        (选型：任意/实测分布用本工具；均匀用 add_system_temperature；线性梯度用 add_gradient_temperature；规范梁截面温度用 add_beam_section_temperature。)

        Every row must contain all three values; two-number rows lack a
        top/bottom reference and are rejected before writing. None
        omits the profile argument; [] sends an empty profile. The SDK does not
        define their bridge behavior, fixed units, interpolation or repeated
        load handling. Verify those in the target bridge. Returns a confirmation
        without solving. (每行必须三列，缺少顶底基准的两列会被拒绝；None 省略参数、
        [] 传空表，具体空值行为、单位、插值及重复定义策略须核验，返回确认不求解。)

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            orientation: Direction in local element coordinates: 1=Z, 2=Y
                         (单元局部坐标方向：1=Z向，2=Y向)
            temperature_data: Rows [[reference, height, temperature], ...],
                reference 1=top or 2=bottom; use bridge-verified native units.
                None omits, [] sends empty; no reference is inferred.
                (三列：顶底基准、高度、温度；不推断顶底基准或空值)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {"orientation": orientation}
            if group_name:
                kwargs["group_name"] = group_name
            if temperature_data is not None:
                if any(len(item) != 3 or item[0] not in (1, 2) for item in temperature_data):
                    raise ToolInputError(
                        "temperature_data rows must be [reference (1=top, 2=bottom), height, "
                        "temperature]; two-value rows have no reference (自定义温度须提供三列)"
                    )
                kwargs["temperature_data"] = [tuple(item) for item in temperature_data]
            provider.add_custom_temperature(element_id=element_id, case_name=case_name, **kwargs)
            return f"Successfully applied custom temperature to element(s) {element_id} (成功施加自定义温度)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying custom temperature (施加自定义温度失败): {e}") from e

    @mcp.tool()
    def add_beam_section_temperature(
        element_id: int | list[int] | str,
        case_name: str,
        code_index: int = 1,
        sec_type: Literal[1, 2] = 1,
        t1: float = 0,
        t2: float = 0,
        t3: float = 0,
        t4: float = 0,
        thick: float = 0,
        group_name: str = "",
    ) -> str:
        """
        Apply code-based beam section temperatures (梁截面温度荷载，按规范).

        Submits a code-defined section temperature load to load case case_name
        for the given element(s) and refreshes the model; create the load case
        first. Uses standard design-code parameters (t1–t4 at code depths).
        (向工况 case_name 的指定单元添加规范梁截面温度并刷新模型；需先建好工况。按规范用 t1–t4 等标准参数。)

        When to use vs. siblings: design-code section temperatures here;
        uniform element temperature → add_system_temperature; linear gradient →
        add_gradient_temperature; arbitrary profile → add_custom_temperature.
        (选型：规范梁截面温度用本工具；均匀用 add_system_temperature；线性梯度用 add_gradient_temperature；任意分布用 add_custom_temperature。)

        Returns a confirmation. The SDK exposes t1–t4 and thick but does not
        document the full code-specific profile layout, fixed units, or
        repeated-call policy. Use values verified in the selected code's
        bridge dialog/export; do not infer depths or overwrite semantics.

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            code_index: Code index; the SDK documents 1=JTG D60-2015,
                2=AASHTO 2017 (规范号：1公路规范2015、2美规2017)
            sec_type: Material category: 1=concrete, 2=composite beam
                (截面材料类别：1混凝土、2组合梁；不是截面形状编号)
            t1: First native temperature-profile parameter from the selected
                code's dialog/export (所选规范界面/导出中的第 1 个温度参数)
            t2: Second native temperature-profile parameter (同一规范的第 2 个温度参数)
            t3: Third native temperature-profile parameter (同一规范的第 3 个温度参数)
            t4: Fourth native temperature-profile parameter (同一规范的第 4 个温度参数)
            thick: Native thickness parameter for the selected profile;
                   verify its unit in the bridge (所选温度图式的厚度参数，单位须在桥通确认)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {
                "code_index": code_index, "sec_type": sec_type,
                "t1": t1, "t2": t2, "t3": t3, "t4": t4, "thick": thick
            }
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_beam_section_temperature(element_id=element_id, case_name=case_name, **kwargs)
            return f"Successfully applied beam section temperature to element(s) {element_id} (成功施加梁截面温度)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying beam section temperature (施加梁截面温度失败): {e}") from e

    @mcp.tool()
    def add_initial_tension_load(
        element_id: int | list[int] | str,
        case_name: str,
        tension: float = 0.0,
        tension_type: Literal[0, 1] = 1,
        application_type: Literal[1, 2, 3] = 1,
        stiffness: float = 0.0,
        group_name: str = "",
    ) -> str:
        """
        Apply an initial tension to cable/truss elements (初始拉力).

        Adds one initial-tension load to load case case_name for the given
        element(s) and refreshes the model; create the load case first with
        create_load_case. Typically used to set cable forces in cable-stayed
        and suspension models.

        When to use vs. siblings: prescribe a FORCE here; prescribe an
        unstressed cable LENGTH instead → add_cable_length_load (equivalently,
        set application_type=3 to convert this force into a length tensioning).

        (向工况 case_name 的指定单元添加初始拉力并刷新模型；需先用 create_load_case
        建好工况。常用于斜拉桥/悬索桥索力。选型：给定"力"用本工具，给定"无应力索长"
        用 add_cable_length_load，或将 application_type 设为 3 由本工具转为索长张拉。)

        Returns a confirmation; it does not solve or return the resulting
        cable force. The SDK does not specify fixed force units or whether
        repeated definitions replace earlier ones. Use bridge-verified values
        and inspect the existing load before repeating; no unit conversion
        is performed here.

        Args:
            element_id: Element ID(s) — int, list, or "XtoYbyN" range string
                        (单元编号，支持整数、列表或 "XtoYbyN" 范围字符串)
            case_name: Load case name, must already exist (荷载工况名，须已存在)
            tension: Initial tension force in the bridge API's native unit;
                     the SDK declares no fixed N/kN unit (初始拉力，使用经桥通核验的原生单位)
            tension_type: How `tension` is interpreted (张拉类型):
                          0=increment(增量，叠加到现有索力)
                          1=total(全量，直接指定最终索力，默认)
            application_type: How the tension is applied (计算方式):
                              1=external force(体外力，默认)
                              2=internal force(体内力)
                              3=convert to cable-length tensioning(转为索长张拉)
            stiffness: Cable stiffness participation factor (索刚度参与系数)
            group_name: Load group name, empty for the default group
                        (荷载组名，空则用默认荷载组)
        """
        try:
            kwargs: dict[str, Any] = {
                "tension": tension, "tension_type": tension_type,
                "application_type": application_type, "stiffness": stiffness
            }
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_initial_tension_load(element_id=element_id, case_name=case_name, **kwargs)
            return f"Successfully applied initial tension {tension} to element(s) {element_id} (成功施加初拉力)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying initial tension (施加初拉力失败): {e}") from e

    @mcp.tool()
    def add_cable_length_load(
        element_id: int | list[int] | str,
        case_name: str,
        length: float = 0.0,
        tension_type: Literal[0, 1] = 1,
        group_name: str = "",
    ) -> str:
        """
        Tension a cable by prescribing its length (索长张拉).

        Adds one cable-length tensioning load to load case case_name for the
        given element(s) and refreshes the model; create the load case first
        with create_load_case. The resulting cable force is whatever the
        prescribed length produces — you control length, not force.

        When to use vs. siblings: prescribe a LENGTH here; prescribe a FORCE
        instead → add_initial_tension_load.

        (向工况 case_name 的指定单元添加索长张拉并刷新模型；需先用 create_load_case
        建好工况。索力由给定长度反算得出——本工具控制长度而非力。选型：给定"长度"用
        本工具，给定"力"用 add_initial_tension_load。)

        Returns a confirmation, not the resulting cable force. Length is
        forwarded without conversion; the SDK does not declare a fixed unit
        or repeated-definition policy. Use a value verified against the
        bridge's cable-length input and inspect existing loads before reuse.

        Args:
            element_id: Element ID(s) — int, list, or "XtoYbyN" range string
                        (单元编号，支持整数、列表或 "XtoYbyN" 范围字符串)
            case_name: Load case name, must already exist (荷载工况名，须已存在)
            length: Cable length input in the bridge API's native unit;
                    verify it in the bridge, as the SDK gives no fixed unit
                    (索长输入，SDK 未声明固定单位，须先核对桥通接口使用的单位)
            tension_type: How `length` is interpreted (张拉类型):
                          0=increment(增量，相对现有索长的变化量)
                          1=total(全量，直接指定目标索长，默认)
            group_name: Load group name, empty for the default group
                        (荷载组名，空则用默认荷载组)
        """
        try:
            kwargs: dict[str, Any] = {"length": length, "tension_type": tension_type}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_cable_length_load(element_id=element_id, case_name=case_name, **kwargs)
            return f"Successfully applied cable length load {length} to element(s) {element_id} (成功施加索长荷载)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying cable length load (施加索长荷载失败): {e}") from e

    @mcp.tool()
    def add_plate_element_load(
        element_id: int | list[int] | str,
        case_name: str,
        load_type: Literal[1, 2, 3, 4] = 1,
        load_place: Literal[0, 1, 2, 3, 4] = 1,
        coord_system: Literal[1, 2, 3, 4, 5, 6] = 3,
        list_load: list[float] | float | None = None,
        list_xy: TwoNumbers | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply a force or moment to plate elements, on a face or an edge
        (板单元荷载：集中/分布力或弯矩，可加在面上或边上).

        Adds one plate load to load case case_name for the given element(s)
        and refreshes the model; create the load case first with
        create_load_case. Which optional arguments are needed depends on
        load_type: concentrated loads (1, 2) need list_xy; distributed loads
        (3, 4) need load_place.

        When to use vs. siblings: per-element plate loads here; a load
        pattern spread over a plane and distributed onto many plates →
        add_distribute_plane_load. Beam elements → apply_beam_distributed_load.

        (向工况 case_name 的指定板单元添加荷载并刷新模型；需先用 create_load_case
        建好工况。可选参数取决于 load_type：集中荷载(1、2)需 list_xy；分布荷载(3、4)
        需 load_place。选型：逐单元加板荷载用本工具；按平面荷载图式分配到多个板单元
        用 add_distribute_plane_load；梁单元用 apply_beam_distributed_load。)

        Requests automatic load IDs and returns a confirmation. Repeating
        this add call is not an update by ID. Magnitudes and distances are
        passed without conversion; the SDK does not define fixed units for
        each load family. Verify the bridge convention for force vs. moment
        and point vs. distributed loading before importing values.

        Args:
            element_id: Plate element ID(s) — int or list (板单元编号，整数或列表)
            case_name: Load case name, must already exist (荷载工况名，须已存在)
            load_type: What is applied (荷载类型):
                       1=concentrated force(集中力，默认)
                       2=concentrated moment(集中弯矩)
                       3=distributed force(分布力)
                       4=distributed moment(分布弯矩)
            load_place: Where a DISTRIBUTED load acts; only needed for
                        load_type 3 and 4 (分布荷载的作用位置，仅分布荷载需要):
                        0=face IJKL(面IJKL) | 1=edge IJ(边IJ) | 2=edge JK(边JK)
                        3=edge KL(边KL) | 4=edge LI(边LI)
            coord_system: Direction of the load (荷载方向坐标系):
                          1=global X(整体X) | 2=global Y(整体Y)
                          3=global Z(整体Z，默认) | 4=local X(局部X)
                          5=local Y(局部Y) | 6=local Z(局部Z)
            list_load: Load magnitude(s) — a single value or a list, e.g.
                       [1000] for one concentrated force
                       (荷载值，单值或列表，如集中力 [1000])
            list_xy: Position of a CONCENTRATED load as absolute distances
                     [x along IJ, y along IL]; only needed for load_type 1 and 2
                     (集中荷载的位置，[IJ方向绝对距离x, IL方向绝对距离y]，
                     仅集中荷载需要)
            group_name: Load group name, empty for the default group
                        (荷载组名，空则用默认荷载组)
        """
        try:
            kwargs: dict[str, Any] = {"load_type": load_type, "load_place": load_place, "coord_system": coord_system}
            if group_name:
                kwargs["group_name"] = group_name
            if list_load is not None:
                kwargs["list_load"] = list_load
            if list_xy is not None:
                kwargs["list_xy"] = tuple(list_xy)
            provider.add_plate_element_load(element_id=element_id, case_name=case_name, **kwargs)
            return f"Successfully applied plate load to element(s) {element_id} (成功施加板单元荷载)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying plate load (施加板单元荷载失败): {e}") from e

    @mcp.tool()
    def add_distribute_plane_load(
        index: int,
        case_name: str,
        type_name: str,
        point1: ThreeNumbers | None = None,
        point2: ThreeNumbers | None = None,
        point3: ThreeNumbers | None = None,
        plate_ids: list[int] | None = None,
        coord_system: int = 3,
        group_name: str = "",
    ) -> str:
        """
        Place a predefined plane load pattern and distribute it onto plate
        elements (放置分配面荷载图式，并分配到板单元).

        Adds one distributed plane load to load case case_name and refreshes
        the model. Two things must exist first: the load case
        (create_load_case) and the load PATTERN named by type_name.

        Creating the pattern has no dedicated tool — use the escape hatch:
        call_qtmodel_api(api_object="mdb",
                         method="add_distribute_plane_load_type", kwargs={...}).

        point1/point2/point3 are not three arbitrary coplanar points: they
        define the pattern's local axes — origin, a point on the local x-axis,
        and a point on the local y-axis. Swapping them rotates the pattern.

        When to use vs. siblings: a reusable pattern spread over an area here;
        loads applied element by element → add_plate_element_load.

        (向工况 case_name 添加分配面荷载并刷新模型。需先有两样东西：荷载工况
        (create_load_case) 和 type_name 指向的荷载图式。图式没有专用工具，需经逃生舱
        call_qtmodel_api(api_object="mdb", method="add_distribute_plane_load_type") 创建。
        point1/2/3 不是任意三个共面点，而是图式的局部坐标系：原点、局部x轴上一点、
        局部y轴上一点，顺序颠倒会导致图式旋转。选型：可复用的面荷载图式用本工具；
        逐个单元施加用 add_plate_element_load。)

        Returns a confirmation. Omitting frame points delegates their
        defaults to the bridge; Qiao-MCP does not construct a missing frame.
        Existing-ID and repeated-definition behavior are not specified by
        the SDK, so inspect the bridge before reusing an index or retrying.

        Args:
            index: Load ID; pass -1 to auto-assign
                   (荷载编号，传 -1 由程序自动编号)
            case_name: Load case name, must already exist (荷载工况名，须已存在)
            type_name: Name of an existing plane-load pattern, created via
                       add_distribute_plane_load_type
                       (已存在的分配面荷载类型名，经 add_distribute_plane_load_type 创建)
            point1: Local origin [x,y,z] (局部坐标系原点)
            point2: A point on the local x-axis [x,y,z] (局部x轴上一点)
            point3: A point on the local y-axis [x,y,z] (局部y轴上一点)
            plate_ids: Plate elements to receive the load; omit to load ALL
                       plate elements in the model
                       (承受该荷载的板单元；不传则作用于模型中全部板单元)
            coord_system: Native load-direction code, default 3. The SDK does
                          not document this API's enum; use a bridge-verified
                          value rather than borrowing another tool's mapping
                          (原生方向代码，默认 3；本接口未给枚举表，使用桥通已核验取值)
            group_name: Load group name, empty for the default group
                        (荷载组名，空则用默认荷载组)
        """
        try:
            kwargs: dict[str, Any] = {"coord_system": coord_system}
            if group_name:
                kwargs["group_name"] = group_name
            if point1:
                kwargs["point1"] = tuple(point1)
            if point2:
                kwargs["point2"] = tuple(point2)
            if point3:
                kwargs["point3"] = tuple(point3)
            if plate_ids:
                kwargs["plate_ids"] = plate_ids
            provider.add_distribute_plane_load(index=index, case_name=case_name, type_name=type_name, **kwargs)
            return f"Successfully applied distributed plane load '{type_name}' (成功施加分布面荷载)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying distributed plane load (施加分布面荷载失败): {e}") from e

    @mcp.tool()
    def add_support_settlement(
        node_id: int | list[int] | str,
        case_name: str,
        dz: float,
        dx: float = 0.0,
        dy: float = 0.0,
        rx: float = 0.0,
        ry: float = 0.0,
        rz: float = 0.0,
        group_name: str = "",
    ) -> str:
        """
        Apply support settlement / nodal displacement load (支座沉降/节点强制位移).

        Apply a prescribed displacement to existing nodes in an existing load
        case. Use set_support to define restraints, or apply_nodal_force for
        forces; this tool does not create either a restraint or a node.
        (已有节点的强制位移荷载用本工具；约束用 set_support，节点力用 apply_nodal_force。)

        Sends [dx,dy,dz,rx,ry,rz] without unit conversion, adds a displacement
        record using the SDK's automatic ID, refreshes the model and returns
        a confirmation. Repeating the call is not an update of a known record;
        use query_model_data(request={"kind":"loads","load_family":"nodal_displacement"})
        to inspect records first. Verify native displacement/rotation units
        in the bridge before converting imported values; the SDK does not
        specify fixed units for this command.
        (原样发送六个位移/转角分量，自动编号并刷新；重复调用不能当作原位修改。
        输入采用桥通原生单位，SDK 未声明本命令的固定单位，导入前须在桥通确认。)

        Args:
            node_id: Existing node IDs: int, list, or "XtoYbyN" range string
                     (已有节点编号，整数、列表或范围字符串)
            case_name: Existing load case name (已存在的荷载工况名)
            dz: Settlement in Z direction (Z向沉降量/下沉为负值)
            dx: Displacement in X direction (X向强制位移)
            dy: Displacement in Y direction (Y向强制位移)
            rx: Rotation around X axis (绕X轴强制转角)
            ry: Rotation around Y axis (绕Y轴强制转角)
            rz: Rotation around Z axis (绕Z轴强制转角)
            group_name: Load group name; empty uses the SDK default group
                        (荷载组名，空字符串使用 SDK 默认荷载组)
        """
        try:
            displacement_info = [dx, dy, dz, rx, ry, rz]
            kwargs: dict[str, Any] = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_support_settlement(
                node_id=node_id, case_name=case_name, displacement_info=displacement_info, **kwargs
            )
            return f"Successfully applied support settlement '{dz}' to node(s) {node_id} (成功施加支座沉降)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying support settlement (施加支座沉降失败): {e}") from e

    @mcp.tool()
    def add_nodal_mass(
        node_id: int | list[int] | str,
        mass: NonnegativeNumber = 0.0,
        mass_x: NonnegativeNumber | None = None,
        mass_y: NonnegativeNumber | None = None,
        mass_z: NonnegativeNumber | None = None,
        rot_x: NonnegativeNumber = 0.0,
        rot_y: NonnegativeNumber = 0.0,
        rot_z: NonnegativeNumber = 0.0,
    ) -> str:
        """
        Attach a lumped mass to nodes for dynamic analysis (添加节点集中质量).

        Writes to the model and refreshes it. This is a MASS property, not a
        load: it belongs to no load case and contributes inertia only, never
        static force.

        A physical point mass (equipment, ballast block) has the same
        translational mass in every direction — pass it as `mass`. Use
        mass_x / mass_y / mass_z only to override a direction on purpose, e.g. a
        mass that should act vertically only. Direction-specific values need
        qtmodel 2.9+ and are rejected on older builds rather than merged.
        rot_x / rot_y / rot_z are rotational mass moments of inertia.

        Create mass before the relevant vibration/dynamic analysis; to include
        eigenvalue analysis use configure_analysis(do_vibration=True). This
        tool returns a confirmation and does not start a solve. Mass from dead load is usually
        supplied separately by add_load_to_mass; use this tool for discrete
        items the model does not carry as load (equipment, ballast blocks).

        When to use vs. siblings: a discrete mass at a node here; converting an
        existing load case into mass → add_load_to_mass; a static downward
        force → apply_nodal_force.

        (写模型并刷新。这是质量属性、不是荷载：不属于任何荷载工况，只贡献惯性、
        不产生静力。实体点质量在各方向相同，用 mass 给出；只有刻意让某方向不同时
        （如仅竖向参与）才用 mass_x/mass_y/mass_z 覆盖，需 qtmodel 2.9+，旧版直接拒绝
        而不静默合并。rot_x/rot_y/rot_z 为转动惯量。应在自振/动力分析前定义；自振分析用
        configure_analysis(do_vibration=True) 开启，本调用仅返回确认、不求解。恒载的质量通常由 add_load_to_mass
        单独提供；本工具用于模型未按荷载计入的离散物件。选型：节点离散质量用本工具；
        把已有工况折算为质量用 add_load_to_mass；静力向下的力用 apply_nodal_force。)

        Mass/inertia values use verified native bridge units without scaling.
        The SDK does not define repeated assignment behavior here; read the
        existing nodal mass in QiaoTong before adding the same item again.
        (质量与惯量均不换算单位，重复赋值策略须核对桥通，避免重复计入同一物件。)

        Args:
            node_id: Node ID(s) — int, list, or "XtoYbyN" range string
                     (节点编号，支持整数、列表或 "XtoYbyN" 范围字符串)
            mass: Translational mass applied along global X, Y and Z
                  (三向平动质量，整体坐标系)
            mass_x: Optional X translational mass; defaults to mass
                    (可选，单独指定整体X向平动质量，默认取 mass)
            mass_y: Optional Y translational mass; defaults to mass
                    (可选，单独指定整体Y向平动质量，默认取 mass)
            mass_z: Optional Z translational mass — vertical in a normal model;
                    defaults to mass (可选，单独指定整体Z向即竖向平动质量，默认取 mass)
            rot_x: Rotational mass moment of inertia about global X (绕整体X轴转动惯量)
            rot_y: Rotational mass moment of inertia about global Y (绕整体Y轴转动惯量)
            rot_z: Rotational mass moment of inertia about global Z (绕整体Z轴转动惯量)
        """
        try:
            translational = tuple(
                mass if value is None else value for value in (mass_x, mass_y, mass_z)
            )
            rotation = (rot_x, rot_y, rot_z)
            if not any(translational) and not any(rotation):
                raise ToolInputError(
                    "Give a nonzero mass or rotational inertia (质量与转动惯量不能全为零)"
                )
            provider.add_nodal_mass(
                node_id=node_id, mass_xyz=translational, rotation=rotation
            )
            return f"Successfully added nodal mass to node(s) {node_id} (成功添加节点质量)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding nodal mass (添加节点质量失败): {e}") from e

    @mcp.tool()
    def add_load_to_mass(
        name: str,
        factor: float = 1.0,
    ) -> str:
        """
        Add a mass-conversion rule for an existing load case used in dynamic
        analysis (为已有荷载工况设置动力分析的荷载转质量规则).

        Use when an existing load should contribute to the mass model. For
        explicit nodal masses use add_nodal_mass; for the subsequent vibration
        analysis enable it with configure_analysis and then call run_analysis.
        name is the existing load-case name, not a new mass or combination name.

        factor is passed as the conversion coefficient. The bridge performs the
        actual conversion; this wrapper neither computes masses nor deletes the
        source loads. It writes the rule, refreshes the model and returns a
        confirmation, not a mass total. Verify repeated rules in the bridge to
        avoid unintended mass contributions; replacement behavior is backend-owned.
        (传入已有工况名和转换系数；本工具仅配置规则，不返回质量数值，也不启动求解。)

        Args:
            name: Load case name to convert (要转换为质量的荷载工况名称)
            factor: Conversion factor (转换系数，通常取1.0)
        """
        try:
            provider.add_load_to_mass(name=name, factor=factor)
            return f"Successfully set load '{name}' to convert to mass (成功设置荷载转换为质量)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error converting load to mass (荷载转质量失败): {e}") from e

    @mcp.tool()
    def add_spectrum_function(
        name: str,
        factor: float = 1.0,
        kind: Literal[0, 1, 2] = 0,
        function_info: list[TwoNumbers] | None = None,
    ) -> str:
        """
        Define a response spectrum curve for later use (定义反应谱函数曲线).

        Stores a named period-vs-value curve and refreshes the model. This is a
        DEFINITION only — it applies no load until a spectrum case references it
        by name (add_spectrum_case).

        Common practice: give function_info a normalized curve and put the
        seismic coefficient in factor, e.g. factor=0.075 for a rare earthquake.

        (保存一条以名字标识的"周期-数值"曲线并刷新模型。本工具只是定义，
        在 add_spectrum_case 按名引用前不产生任何荷载。常见做法：function_info 给
        归一化曲线，地震系数放在 factor 里，如罕遇取 factor=0.075。)

        Args:
            name: Function name, referenced later by add_spectrum_case
                  (反应谱函数名，后续由 add_spectrum_case 按名引用)
            factor: Scale factor applied to the whole curve; commonly the
                    seismic coefficient (反应谱调整系数，作用于整条曲线，
                    常用于放地震系数)
            kind: What the curve's values mean (曲线数值的量纲):
                  0=dimensionless(无量纲，默认) | 1=acceleration(加速度)
                  2=displacement(位移)
            function_info: Curve points [[period, value], ...]
                           (反应谱曲线数据点 [[周期, 数值], ...])
        """
        try:
            kwargs: dict[str, Any] = {"name": name, "factor": factor, "kind": kind}
            if function_info is not None:
                kwargs["function_info"] = [tuple(item) for item in function_info]
            provider.add_spectrum_function(**kwargs)
            return f"Successfully added spectrum function '{name}' (成功添加反应谱函数)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding spectrum function (添加反应谱函数失败): {e}") from e

    @mcp.tool()
    def add_spectrum_case(
        name: str,
        description: str = "",
        kind: Literal[1, 2] = 1,
        info_x: FunctionReference | None = None,
        info_y: FunctionReference | None = None,
        info_z: FunctionReference | None = None,
    ) -> str:
        """
        Create a response spectrum case that excites the model in one or more
        directions (创建反应谱工况，按方向施加地震作用).

        Adds the case and refreshes the model. The spectrum FUNCTION named in
        info_x/y/z must already exist (add_spectrum_function), and the model
        needs a mass source (add_load_to_mass / add_nodal_mass) plus
        self-vibration analysis enabled (configure_analysis with
        do_vibration=True) for results to be meaningful.

        Supply only the directions required by the intended loading definition;
        omitted directions use the SDK's empty defaults. Multi-direction input
        is supported; choose its combination kind explicitly.

        Response-spectrum modal combination (SRSS/CQC) is NOT set here; it lives
        in the global spectrum setting, reachable via
        call_qtmodel_api(api_object="mdb",
                         method="update_response_spectrum_setting",
                         kwargs={"kind": 1}).

        (添加工况并刷新模型。info_x/y/z 引用的反应谱函数须已由 add_spectrum_function
        建好；模型还需有质量来源(add_load_to_mass / add_nodal_mass)并开启自振分析
        (configure_analysis 的 do_vibration=True)，结果才有意义。按目标加载定义给出
        方向，省略方向取 SDK 空默认；多方向输入须明确组合方式。振型组合方式(SRSS/CQC)不在本工具设置，
        属全局反应谱设置，需经逃生舱 call_qtmodel_api 调
        update_response_spectrum_setting。)

        For an explicit time-domain input choose add_time_history_case; ordinary
        static cases use create_load_case. Returns a confirmation without solving;
        inspect existing names before repeating, as duplicate handling belongs
        to QiaoTong (时域与普通静力工况分别用上述工具，返回确认不求解，重名前先核对).

        Args:
            name: Case name (工况名称)
            description: Description (说明)
            kind: How the directional components are combined (方向分量的组合方式):
                  1=vector modulus(求模，默认) | 2=algebraic sum(求和).
                  NOT the modal combination method — SRSS/CQC is set in the
                  global spectrum setting
                  (不是振型组合方式；SRSS/CQC 在全局反应谱设置里)
            info_x: X-direction excitation [function_name, factor]; omit for no
                    X component (X向输入 [谱函数名, 系数]，不传则该方向无输入)
            info_y: Y-direction excitation [function_name, factor] (Y向输入)
            info_z: Z-direction excitation [function_name, factor] (Z向输入)
        """
        try:
            kwargs: dict[str, Any] = {"name": name, "description": description, "kind": kind}
            if info_x:
                kwargs["info_x"] = tuple(info_x)
            if info_y:
                kwargs["info_y"] = tuple(info_y)
            if info_z:
                kwargs["info_z"] = tuple(info_z)
            provider.add_spectrum_case(**kwargs)
            return f"Successfully added spectrum case '{name}' (成功添加反应谱工况)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding spectrum case (添加反应谱工况失败): {e}") from e

    @mcp.tool()
    def add_time_history_function(
        name: str,
        factor: float = 1.0,
        kind: Literal[0, 1, 2, 3] = 0,
        function_info: list[TwoNumbers] | None = None,
    ) -> str:
        """
        Define a time-varying function for time-history analysis, e.g. a
        ground-motion record (定义时程函数，如地震波时程曲线).

        Creates a reusable named function and refreshes the model. This only
        stores the curve — it applies nothing on its own. To use it as seismic
        input, create a time-history case (add_time_history_case) and then bind
        this function to a direction via the escape hatch:
        call_qtmodel_api(api_object="mdb", method="add_ground_motion",
                         kwargs={"case_name": ..., "info_x": [name, factor, arrival_time]}).

        When to use vs. siblings: a time-domain curve here; a response spectrum
        curve → add_spectrum_function.

        (创建可复用的命名函数并刷新模型。本工具只存曲线、自身不施加任何作用。
        要作为地震输入使用，需先建时程工况 add_time_history_case，再经逃生舱调
        add_ground_motion 把函数绑定到某个方向。选型：时域曲线用本工具；
        反应谱曲线用 add_spectrum_function。)

        Returns a confirmation. Point order and values are passed through;
        there is no sorting, time shift or unit conversion. The SDK names
        the physical quantity but does not specify its fixed unit or
        same-name replacement policy. Preserve verified bridge input units
        and inspect a named function before attempting a replacement.

        Args:
            name: Function name, referenced later by add_ground_motion
                  (函数名称，后续由 add_ground_motion 引用)
            factor: Scale factor applied to every value (整体放大系数)
            kind: What the values represent (数值的物理量):
                  0=dimensionless(无量纲，默认) | 1=acceleration(加速度)
                  2=force(力) | 3=moment(力矩).
                  Seismic ground-motion records use 1
                  (地震波时程用 1)
            function_info: Curve points [[time, value], ...], e.g.
                           [[0, 0], [0.02, 0.1], [0.04, 0.3]]
                           (曲线数据点 [[时间, 数值], ...])
        """
        try:
            kwargs: dict[str, Any] = {"name": name, "factor": factor, "kind": kind}
            if function_info is not None:
                kwargs["function_info"] = function_info
            provider.add_time_history_function(**kwargs)
            return f"Successfully added time history function '{name}' (成功添加时程函数)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding time history function (添加时程函数失败): {e}") from e

    @mcp.tool()
    def add_time_history_case(
        name: str,
        duration: float = 1.0,
        time_step: float = 0.01,
        description: str = "",
        index: int = -1,
    ) -> str:
        """
        Create a time-history analysis case: the time-integration settings for
        one dynamic run (创建时程分析工况，即一次动力分析的时间积分设置).

        Adds the case and refreshes the model. The case is a container for
        analysis settings — it applies no load by itself. Seismic input is bound
        separately, per direction, via the mdb method add_ground_motion (escape
        hatch; it has no dedicated tool).

        Typical order: define a mass source (add_load_to_mass / add_nodal_mass)
        → define the wave (add_time_history_function) → this case → bind input
        (mdb.add_ground_motion via call_qtmodel_api) → enable self-vibration
        analysis (configure_analysis with do_vibration=True).

        LIMITATION — this tool exposes only the basic settings. Cases are
        therefore created LINEAR and UNDAMPED (upstream treats an empty damping
        name as no damping). Damping, boundary-nonlinear analysis, convergence
        limits and the integration scheme are reachable only via the escape
        hatch: define damping with
        call_qtmodel_api(api_object="mdb", method="add_dynamic_damping", ...),
        then create the case with method="add_time_history_case" passing
        damping=<that name> plus analysis_kind / nonlinear_groups / min_step /
        tolerance / mode_superposition_kind as needed.

        When to use vs. siblings: a time-domain run here; a response-spectrum
        run → add_spectrum_case.

        (添加工况并刷新模型。工况只是分析设置的容器，自身不施加荷载；地震输入需另经
        add_ground_motion 按方向绑定。典型顺序：质量来源 → 时程函数 → 本工况 →
        绑定地震动 → 开启自振分析。局限：本工具只暴露基本设置，因此建出的工况是
        线性、无阻尼的(上游以空阻尼名表示无阻尼)；阻尼、边界非线性、收敛控制与积分
        方法需经逃生舱先 add_dynamic_damping 定义阻尼，再调 add_time_history_case
        并传 damping 等参数。选型：时域分析用本工具；反应谱分析用 add_spectrum_case。)

        Returns a confirmation, not time-response data. The SDK does not specify
        duplicate-name handling; inspect the bridge before redefining this case.
        (返回工况创建确认，不含时程结果；重名策略需核对桥通。)

        Args:
            name: Case name, referenced by add_ground_motion
                  (工况名称，由 add_ground_motion 引用)
            duration: Total analysis duration in seconds (分析总时长，秒)
            time_step: Integration time step in seconds (分析时间步长，秒)
            description: Free-text description (描述)
            index: Case ID; pass -1 to auto-assign
                   (工况编号，传 -1 由程序自动编号)
        """
        try:
            provider.add_time_history_case(
                name=name, duration=duration, time_step=time_step,
                description=description, index=index
            )
            return f"Successfully added time history case '{name}' (成功添加时程工况)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding time history case (添加时程工况失败): {e}") from e

    @mcp.tool()
    def update_bulking_setting(
        do_analysis: bool = True,
        mode_count: int = 3,
        stage_id: int = -1,
    ) -> str:
        """
        Configure linear buckling analysis (屈曲分析设定；方法名 bulking 为历史拼写).

        Writes to the model. Enabling analysis does not run it — call
        run_analysis afterwards. The misspelling "bulking" is the upstream
        method name; renaming it would break existing callers.

        LIMITATION — this tool exposes only the three basic switches. The
        load-case assignment (constant_cases / variable_cases), whether
        self-weight is treated as constant or variable, and whether the
        prestressed or unstressed geometry is used, are reachable only via
        the escape hatch:
        call_qtmodel_api(api_object="mdb", method="update_bulking_setting",
                         kwargs={"variable_cases": ["工况1"], "calculate_kind": 1,
                                 "stressed": True, ...}).
        Without at least one variable_cases name, a buckling run typically has
        nothing to vary.

        (写模型。打开分析开关并不求解——之后还要调 run_analysis。"bulking" 是上游
        方法名的历史拼写，改名会破坏已有调用。局限：本工具只暴露三个基本开关；
        荷载工况分配(constant_cases / variable_cases)、恒载归为不变还是可变、
        以及采用预应力还是无应力几何，都需经逃生舱设置。不指定 variable_cases
        时屈曲分析通常没有可变荷载。)

        Use configure_analysis for the other global solve switches, or
        update_construction_stage to change a stage's contents. This sends SDK
        defaults for unexposed buckling fields without reading/merging previous
        settings; do not assume an earlier gateway configuration is preserved.
        Returns a confirmation (区别于全局分析开关和阶段内容修改；未暴露字段沿用 SDK
        默认值，不回读合并，不能保证保留此前网关设置，返回确认消息).

        Args:
            do_analysis: Enable linear buckling analysis (是否进行线性屈曲分析)
            mode_count: Number of buckling modes to compute, must be positive
                        (屈曲模态数，须为正整数)
            stage_id: Construction-stage number used as the base state
                      (作为基准状态的施工阶段号):
                      -1 or non-positive = the LAST construction stage
                      (最后施工阶段，不是基本模型);
                      a positive integer must already exist
                      (正整数必须对应已有阶段)
        """
        try:
            provider.update_bulking_setting(
                do_analysis=do_analysis, mode_count=mode_count, stage_id=stage_id
            )
            return "Successfully updated buckling analysis settings (成功设定屈曲分析)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating buckling settings (屈曲分析设定失败): {e}") from e

    @mcp.tool()
    def add_construction_stage(
        name: str,
        duration: NonnegativeNumber,
        active_structures: list[list] | None = None,
        active_boundaries: list[list] | None = None,
        active_loads: list[list] | None = None,
        sub_steps: list[NonnegativeNumber] | None = None,
    ) -> str:
        """
        Add a construction stage and say what becomes active in it
        (添加施工阶段并指定其激活内容).

        Appends a stage after the existing ones and refreshes the model. Every
        group named here must already exist (create_structure_group /
        create_boundary_group / create_load_group). Stages are cumulative: what a
        stage activates stays active in later stages unless deactivated.

        LIMITATION — this tool can only ACTIVATE. Deactivation (钝化) of
        structure, boundary and load groups, temporary loads, and the two
        release-behaviour settings are not exposed, so falsework removal or
        temporary-support release cannot be modelled through it. Use the escape
        hatch for those: call_qtmodel_api(api_object="mdb",
        method="add_construction_stage", kwargs={..., "delete_structures": [...],
        "delete_boundaries": [...], "delete_loads": [...], "temp_loads": [...]}).

        When to use vs. siblings: creating a stage here; editing one that exists
        → update_construction_stage; deleting → remove_construction_stage;
        collapsing all stages into a final operation stage →
        merge_operation_stage. Construction-stage analysis must also be turned
        on with configure_analysis(do_construction_stage=True).

        (在已有阶段之后追加一个阶段并刷新模型。此处引用的每个组都须已存在。阶段是累积的：
        某阶段激活的内容在后续阶段保持激活，除非被钝化。局限：本工具只能"激活"。结构组/
        边界组/荷载组的钝化、临时荷载、以及两个释放行为设置都未暴露，因此支架拆除、
        临时支座释放无法经本工具表达，需经逃生舱调 add_construction_stage 并传
        delete_structures / delete_boundaries / delete_loads / temp_loads。
        选型：建阶段用本工具；改已有阶段用 update_construction_stage；删用
        remove_construction_stage；合并为运营阶段用 merge_operation_stage。
        还须用 configure_analysis(do_construction_stage=True) 打开施工阶段分析。)

        Empty/None activation lists are omitted by this wrapper. Duplicate-name
        handling belongs to the bridge; inspect existing stages before repeating.
        Returns the requested stage name in a confirmation, not a queried ID.
        (空激活列表等同省略；重名策略由桥通决定，返回请求阶段名而非回读编号。)

        Args:
            name: Stage name (施工阶段名称)
            duration: Stage duration in days, including fractional days. Fractional
                      durations require a qtmodel build exposing sub_steps; older
                      builds are rejected rather than silently truncating the value
                      (时长，单位天，支持小数；旧版不支持时明确报错，不截断)
            sub_steps: Sub-step durations in days, e.g. [0.25, 1.5]. None omits the
                       option; [] explicitly supplies no sub-steps. Requires a
                       supporting qtmodel build (子步时长列表；省略保持旧行为，需新版)
            active_structures: Structure groups to activate (激活结构组):
                [[group_name, age, install_method, weight_stage_id], ...]
                age: concrete age in days at activation (激活时龄期，天)
                install_method: 1=deformation(变形法) | 2=unstressed(无应力法)
                                3=connection(接线法) | 4=tangent(切线法)
                weight_stage_id: which stage carries the self-weight
                                 (计自重的施工阶段): 0=no self-weight(不计自重)
                                 | 1=this stage(本阶段) | n=stage n(第n阶段).
                                 Referencing a stage that does not exist yet
                                 requires adding that stage first
                                 (若引用尚未建立的阶段，需先建该阶段)
            active_boundaries: Boundary groups to activate (激活边界组):
                [[group_name, position], ...]
                position: 0=before deformation(变形前) | 1=after deformation(变形后)
            active_loads: Load groups to activate (激活荷载组):
                [[group_name, time], ...]
                time: 0=at stage start(阶段开始) | 1=at stage end(阶段结束)
        """
        try:
            kwargs: dict[str, Any] = {}
            if active_structures:
                kwargs["active_structures"] = [tuple(s) for s in active_structures]
            if active_boundaries:
                kwargs["active_boundaries"] = [tuple(b) for b in active_boundaries]
            if active_loads:
                kwargs["active_loads"] = [tuple(l) for l in active_loads]
            if sub_steps is not None:
                kwargs["sub_steps"] = sub_steps
            provider.add_construction_stage(name=name, duration=duration, **kwargs)
            return f"Successfully added construction stage '{name}' (成功添加施工阶段 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding construction stage (添加施工阶段失败): {e}") from e

    @mcp.tool()
    def configure_analysis(
        do_construction_stage: bool = True,
        do_creep: bool = False,
        do_vibration: bool = False,
        vibration_modes: int = 10,
        solver_type: Literal[0, 1] = 0,
    ) -> str:
        """
        Configure structural solver, construction-stage and vibration options
        before running analysis (配置结构求解、施工阶段和自振分析选项).

        Use after defining the model, supports, loads and stages; run_analysis
        performs the subsequent solve. configure_check_analysis controls concrete
        checking instead, and configure_live_load_system selects traffic systems.
        do_creep affects the construction-stage analysis; vibration_modes is
        meaningful when do_vibration enables the modal calculation.

        Three setting groups are written in sequence. True and False are both
        applied, so do_vibration=False explicitly disables vibration. Every call
        replaces these groups, and unexposed fields such as thread settings use
        SDK defaults. Supply the complete intended options instead of treating
        omitted arguments as unchanged values. A later failure can leave an
        earlier group updated; inspect settings before retrying.

        Returns the configured option summary. It does not run a solver or produce
        results; use run_analysis once configuration is complete.
        (三组设置依次整体写入，未暴露项用 SDK 默认值；中途失败可能已写入前面的设置。)

        Args:
            do_construction_stage: Enable construction stage analysis (是否进行施工阶段分析)
            do_creep: Enable creep analysis (是否进行徐变分析)
            do_vibration: Enable self-vibration analysis (是否进行自振分析)
            vibration_modes: Number of vibration modes (振型数量)
            solver_type: Solver type (求解器): 0=sparse matrix, 1=variable bandwidth
                         0=稀疏矩阵, 1=变带宽
        """
        try:
            provider.update_construction_stage_setting(
                do_analysis=do_construction_stage,
                do_creep_analysis=do_creep,
            )
            provider.update_self_vibration_setting(
                do_analysis=do_vibration, mode_num=vibration_modes
            )
            provider.update_global_setting(solver_type=solver_type)
            return (
                f"Analysis configured: construction_stage={do_construction_stage}, "
                f"creep={do_creep}, vibration={do_vibration}, solver_type={solver_type} "
                f"(分析配置完成)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error configuring analysis (配置分析失败): {e}") from e

    @mcp.tool()
    async def run_analysis(
        ctx: Context, read_timeout: PositiveInteger = 3600, show_view: bool = False
    ) -> str:
        """
        Run the structural analysis calculation (执行结构分析计算).

        Use this after all loads, boundaries, and analysis settings are configured.
        Solving can take a long time; it runs in a worker thread so the connection
        stays responsive, with periodic progress heartbeats. Success is reported only
        when QiaoTong's final solve state is a success; a solve the user terminated in
        QiaoTong, or any other unfinished state, is an error.
        求解可能耗时较长，在工作线程中执行以保持连接不阻塞，并周期性上报进度。
        只有桥通报告的最终状态为成功时才报完成；用户在桥通中终止求解等未完成状态均报错。

        Args:
            read_timeout: Max total solve time in seconds, default 3600
                          (求解总时限秒数；超时抛错，求解本身在后台继续)
            show_view: Request the QiaoTong analysis progress window, default False.
                       Does not change background solving, polling or MCP progress.
                       True requires a qtmodel build exposing this option; older
                       builds reject it before starting the solve.
                       (是否显示桥通分析进度窗口；不影响异步求解，旧版不支持开启时明确报错)
        """
        try:
            kwargs: dict[str, Any] = {"read_timeout": read_timeout}
            if show_view:
                kwargs["show_view"] = True
            loop = asyncio.get_running_loop()
            solve = loop.run_in_executor(
                None, lambda: provider.run_analysis(**kwargs)
            )
            elapsed = 0
            # 每 5 秒发一次进度心跳，直到求解线程返回
            while True:
                done, _ = await asyncio.wait({solve}, timeout=5)
                if done:
                    status = await solve  # 传播求解线程中的异常
                    break
                elapsed += 5
                try:
                    await ctx.report_progress(
                        progress=elapsed, total=read_timeout,
                        message=f"Solving… {elapsed}s elapsed (求解中，已用 {elapsed}s)",
                    )
                except Exception:
                    pass  # 进度上报失败不应影响求解
            # 用户终止等结局不抛错而是返回状态，必须核对后才能宣告完成
            state = str(status.get("state", "")).lower() if isinstance(status, dict) else ""
            if (
                state not in _SOLVE_SUCCESS_STATES
                or status.get("ok") is False
                or str(status.get("is_running", "")).lower() == "true"
            ):
                message = (status.get("message") or "") if isinstance(status, dict) else ""
                raise ToolError(
                    f"Analysis success was not confirmed: state={state or 'unknown'}"
                    + (f", message={message}" if message else "")
                    + ". Inspect the model and solve status before starting another run. "
                    f"(无法确认结构分析成功：状态 {state or 'unknown'}；再次求解前请先检查模型和求解状态)"
                )
            return "Analysis successfully completed (结构分析计算完成)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error running analysis (结构分析失败): {e}") from e

    @mcp.tool()
    def validate_model() -> str:
        """
        Validate the current model for common issues before running analysis
        (验证模型，在运行分析前检查常见问题).

        Checks for:
        - Missing nodes/elements/materials (缺失的节点/单元/材料)
        - Overlapping nodes (重合节点)
        - Overlapping elements (重合单元)
        """
        try:
            result = provider.validate_model()
            lines = []
            if result["is_valid"]:
                lines.append("✅ Model validation PASSED (模型验证通过)")
            else:
                lines.append("❌ Model validation FAILED (模型验证失败)")

            summary = result["summary"]
            lines.append(
                f"\n📊 Model Summary (模型概要):\n"
                f"  Nodes (节点): {summary['node_count']}\n"
                f"  Elements (单元): {summary['element_count']}\n"
                f"  Materials (材料): {summary['material_count']}\n"
                f"  Sections (截面): {summary['section_count']}\n"
                f"  Stages (施工阶段): {summary['stage_count']}\n"
                f"  Load Cases (荷载工况): {summary['load_case_count']}"
            )

            if result["errors"]:
                lines.append("\n🚫 Errors (错误):")
                for err in result["errors"]:
                    lines.append(f"  - {err}")

            if result["warnings"]:
                lines.append("\n⚠️ Warnings (警告):")
                for warn in result["warnings"]:
                    lines.append(f"  - {warn}")

            return "\n".join(lines)
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error validating model (模型验证失败): {e}") from e

    @mcp.tool()
    def get_model_info() -> str:
        """
        Get a summary of the current bridge model (获取当前桥梁模型概要信息).

        Returns counts of all model entities: nodes, elements, materials,
        sections, construction stages, load cases, etc.
        返回所有模型实体的数量统计。
        """
        try:
            summary = provider.get_model_summary()
            return (
                f"📊 Bridge Model Summary (桥梁模型概要):\n"
                f"  Nodes (节点): {summary['node_count']}\n"
                f"  Elements (单元): {summary['element_count']}\n"
                f"  Materials (材料): {summary['material_count']}\n"
                f"  Sections (截面): {summary['section_count']}\n"
                f"  Construction Stages (施工阶段): {summary['stage_count']}\n"
                f"  Load Cases (荷载工况): {summary['load_case_count']}\n"
                f"  Structure Groups (结构组): {summary['structure_group_count']}\n"
                f"  Boundary Groups (边界组): {summary['boundary_group_count']}"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting model info (获取模型信息失败): {e}") from e

    @mcp.tool()
    def get_analysis_results(
        result_type: str,
        ids: int | list[int] | str = 1,
        stage_id: int = -1,
        case_name: str = "",
        limit: int = 100,
        offset: int = 0,
        case_name_mode: Literal["static", "full"] = "static",
    ) -> str:
        """
        Get analysis results from the bridge model (获取分析结果).

        Args:
            result_type: Type of result to retrieve (结果类型):
                'deformation' (变形), 'force' (内力), 'stress' (应力), 'reaction' (反力)
            ids: Node/Element IDs to query (查询的节点/单元编号)
            stage_id: Construction stage (施工阶段): -1=operation(运营), 0=envelope(包络),
                      n=stage n (第n阶段)
            case_name: Load case name for operation stage (运营阶段荷载工况名).
                       static mode adds "ST:" when missing for stage_id=-1.
                       full mode passes a verified complete result identifier unchanged.
            limit: Max items per page, default 100 (单页条数上限)
            offset: Pagination offset (翻页偏移)
            case_name_mode: static preserves the legacy ordinary static-case prefix;
                full requires a nonempty complete identifier confirmed by QiaoTong
                results/UI and passes it unchanged. Do not infer TV:/MV: result
                prefixes from combination type codes (完整工况名模式不猜测前缀).

        Returns:
            Deformation results (变形): List of dicts with keys
                {node_id, dx, dy, dz, rx, ry, rz} (lowercase, in meters/radians)
            Force results (内力): List of dicts with keys
                {element_id, force_i: {Fx, Fy, Fz, Mx, My, Mz}, force_j: {...}}
                (nested structure, forces in kN, moments in kN·m)
            Stress/Reaction: Similar nested dict structures
        """
        try:
            from qiao_mcp.tools.queries import _paginate

            kwargs: dict[str, Any] = {}
            if case_name_mode not in {"static", "full"}:
                raise ToolInputError("case_name_mode must be static or full")
            if case_name_mode == "full" and not case_name.strip():
                raise ToolInputError("full mode requires a verified complete case_name (完整模式须提供已核实的工况标识)")
            if case_name:
                # Preserve the original static-case convention only in static mode.
                if case_name_mode == "static" and stage_id == -1 and not case_name.startswith("ST:"):
                    kwargs["case_name"] = f"ST:{case_name}"
                else:
                    kwargs["case_name"] = case_name

            if result_type == "deformation":
                result = provider.get_deformation(ids=ids, stage_id=stage_id, **kwargs)
            elif result_type == "force":
                result = provider.get_element_force(ids=ids, stage_id=stage_id, **kwargs)
            elif result_type == "stress":
                result = provider.get_element_stress(ids=ids, stage_id=stage_id, **kwargs)
            elif result_type == "reaction":
                result = provider.get_reaction(ids=ids, stage_id=stage_id, **kwargs)
            else:
                raise ToolInputError(f"Unknown result_type '{result_type}'. "
                    "Available: deformation, force, stress, reaction")
            return f"{result_type} results:\n{_paginate(result, limit, offset)}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting results (获取结果失败): {e}") from e
