"""
MCP Tools for bridge modeling operations.
桥梁建模操作工具

Provides tools for creating and managing model entities:
nodes, elements, materials, sections, structure groups, etc.
"""

import asyncio
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError


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


def register_modeling_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register all modeling-related MCP tools."""

    @mcp.tool()
    def create_nodes(
        node_data: list[list[float]],
        intersected: bool = False,
        is_merged: bool = True,
        merge_error: float = 1e-3,
        numbering_type: int = 1,
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
            merge_error: Merge tolerance in model units, default 1e-3 (合并容差，默认1mm)
            numbering_type: Node numbering strategy: 1=sequential (编号方式: 1=顺序编号)
            start_id: Starting node ID when auto-numbering (起始节点编号)
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
            return f"Successfully created {len(node_data)} nodes (成功创建 {len(node_data)} 个节点)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating nodes (创建节点失败): {e}") from e

    @mcp.tool()
    def create_nodes_linear(
        count: int,
        start_x: float = 0.0,
        start_y: float = 0.0,
        start_z: float = 0.0,
        spacing_x: float = 0.0,
        spacing_y: float = 0.0,
        spacing_z: float = 0.0,
        start_id: int = 1,
        is_merged: bool = True,
        merge_error: float = 1e-3,
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
            return "Error: count must be a positive integer > 0 (节点数量必须大于0)"

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
                    f"Created {count} nodes {span}, but the assigned IDs could not "
                    f"be read back — query them with get_model_data(kind='nodes') "
                    f"before creating elements "
                    f"(成功创建 {count} 个节点，但未能读回编号，建单元前请先查询)"
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
                f"Created/resolved {len(created_ids)} nodes at IDs {id_desc}, {span}"
                f"{order} (成功创建 {len(created_ids)} 个等间距节点){note}"
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
        ele_type: int = 1,
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
            mat_id: Material ID — use get_materials to find valid IDs (材料编号)
            sec_id: Section ID — use get_section_list to find valid IDs (截面编号)
            element_id: Element ID, -1 = auto-assign next available ID (单元编号，-1表示自动分配)
            beta_angle: Beta angle in degrees, controls local axis orientation (贝塔角，度)
            ele_type: Element type (单元类型): 1=Beam(梁), 2=Truss(杆), 3=Cable(索)
            initial_type: Initial strain/force type (初始应变类型): 0=None, 1=Strain, 2=Force
            initial_value: Initial strain or force value (初始应变或内力值)

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
        ele_type: int = 1,
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
        In QiaoTong, creating a load case named "自重" is sufficient for self-weight —
        the software applies it automatically (see server instructions for details).

        Args:
            name: Load case name (工况名称, e.g. "自重", "SW", "恒荷")
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
        combine_type: int = 1,
        combine_info: list[list] | None = None,
        describe: str = "",
        index: int = -1,
    ) -> str:
        """
        Add a load combination (添加荷载组合).

        Combines multiple load cases into a single combination for analysis/checking.
        (将多个荷载工况组合成一个荷载组合)

        Args:
            name: Load combination name (荷载组合名称)
            combine_type: Combination type (组合类型): 1=Add(线性加), 2=Envelope(包络), etc.
            combine_info: List of components [[case_name, case_type, factor], ...]
                          (组合项信息 [[工况名, 类型(如'ST'), 系数], ...])
            describe: Description (描述说明)
            index: ID index, -1 for auto (编号，-1自动生成)
        """
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "combine_type": combine_type,
                "describe": describe,
                "index": index,
            }
            if combine_info is not None:
                kwargs["combine_info"] = [tuple(item) for item in combine_info]
            provider.add_load_combine(**kwargs)
            return f"Successfully added load combination '{name}' (成功添加荷载组合 '{name}')"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding load combination (添加荷载组合失败): {e}") from e



    @mcp.tool()
    def create_material(
        name: str,
        mat_type: int,
        standard: int = 1,
        database: str = "",
        data_info: list[float] | None = None,
    ) -> str:
        """
        Create a material in the bridge model (创建材料).

        Args:
            name: Material name (材料名称)
            mat_type: Material type (材料类型): 1=Concrete(混凝土), 2=Steel(钢材),
                      3=Prestress(预应力), 4=Rebar(钢筋), 5=Custom(自定义), 6=Composite(组合)
            standard: Code standard index, starts from 1 (规范序号，从1开始)
            database: Material database name, e.g. 'C50', 'Q345' (数据库名称)
            data_info: Custom material properties [E, γ, ν, α] for mat_type=5
                       自定义材料参数 [弹性模量, 容重, 泊松比, 热膨胀系数]
        """
        try:
            kwargs: dict[str, Any] = {}
            if data_info:
                kwargs["data_info"] = data_info
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
        code_index: int = 1,
        time_parameter: list[float] | None = None,
        creep_data: list[list] | None = None,
        shrink_data: str = "",
        index: int = -1,
    ) -> str:
        """
        Add time-dependent material parameters (添加时间依存材料参数).

        Args:
            name: Parameter name (参数名称)
            code_index: Code index (规范号)
            time_parameter: Code specific parameters (规范关联的材料参数)
            creep_data: Custom creep data [[time, value], ...] (自定义徐变数据)
            shrink_data: Custom shrinkage data string (自定义收缩数据)
            index: ID index, -1 for auto (编号，-1自动生成)
        """
        try:
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
        creep_data: list[list[float]],
        scale_factor: float = 1.0,
    ) -> str:
        """
        Add user-defined creep function (添加自定义徐变函数).

        Args:
            name: Function name (函数名称)
            creep_data: Creep coefficient over time [[time(days), coefficient], ...]
                        (徐变系数表 [[天数, 徐变系数], ...])
            scale_factor: Scale factor (比例系数)
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
        shrink_data: list[list[float]] | None = None,
        scale_factor: float = 1.0,
    ) -> str:
        """
        Add user-defined shrinkage function (添加自定义收缩函数).

        Args:
            name: Function name (函数名称)
            shrink_data: Shrinkage strain over time [[time(days), strain], ...]
                         (收缩应变表 [[天数, 应变], ...])
            scale_factor: Scale factor (比例系数)
        """
        try:
            kwargs: dict[str, Any] = {"name": name, "scale_factor": scale_factor}
            if shrink_data is not None:
                kwargs["shrink_data"] = [tuple(item) for item in shrink_data]
            provider.add_shrink_function(**kwargs)
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
        loop_segments: dict[str, list[list[float]]]
    ) -> str:
        """
        Create a custom polygon cross-section (创建任意多边形截面).

        Args:
            name: Section name (截面名称)
            loop_segments: Dictionary of loops. Keys should be 'main' for outer loop and 'sub1'... for inner hollow loops. Example: `{"main": [[y1,z1], [y2,z2], ...]}`
        """
        try:
            provider.add_section(
                name=name,
                sec_type="任意",
                sec_info=[],
                loop_segments=loop_segments
            )
            return f"Successfully created polygon section '{name}'"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating polygon section: {e}") from e

    @mcp.tool()
    def create_line_width_section(
        name: str,
        sec_lines: list[list[float]]
    ) -> str:
        """
        Create a line-width cross-section (创建线宽截面).

        Args:
            name: Section name (截面名称)
            sec_lines: List of line segments with thickness. Format: [[y1, z1, y2, z2, thickness], ...]
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

        Args:
            name: Section name (截面名称)
            area: Cross-sectional area (横截面面积 Area)
            ix: Torsional constant (扭转惯性矩 Ixx)
            iy: Moment of inertia about y-axis (抗弯惯性矩 Iyy)
            iz: Moment of inertia about z-axis (抗弯惯性矩 Izz)
            sec_property: Full list of properties (up to 29). If not provided, a basic list is auto-generated with Area, Ix, Iy, Iz.
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
        Create a tapered section from two existing sections (根据两个已存截面创建渐变截面).

        Args:
            name: Tapered section name (渐变截面名称)
            begin_id: Start section ID (起始截面编号)
            end_id: End section ID (终止截面编号)
            shear_consider: Consider shear deformation (是否考虑剪切变形), default True
            sec_normalize: Normalize section (截面归一化), default False
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
        ref_w: int = 0,
        ref_h: int = 0,
        dis_w: float = 0,
        dis_h: float = 0,
    ) -> str:
        """
        Add a tapered section group (添加变截面组).

        Args:
            name: Group name (变截面组名称)
            ids: Element IDs in the group (变截面组内的单元编号)
            factor_w: Width variation factor (宽度变化系数)
            factor_h: Height variation factor (高度变化系数)
            ref_w: Width reference point (宽度参考点: 0=i, 1=j)
            ref_h: Height reference point (高度参考点: 0=i, 1=j)
            dis_w: Width variation distance (宽度变化距离)
            dis_h: Height variation distance (高度变化距离)
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
        thick_type: int = 0,
        index: int = -1,
    ) -> str:
        """
        Add a plate thickness property (添加板厚度).

        Args:
            name: Thickness name (厚度名称)
            t: Thickness in meters (板厚 m)
            thick_type: Thickness type (厚度类型): 0=平面内及平面外等厚, 1=平面内及平面外不等厚
            index: ID index, -1 for auto (编号，-1自动生成)
        """
        try:
            provider.add_thickness(name=name, t=t, thick_type=thick_type, index=index)
            return f"Successfully added thickness '{name}' (成功添加板厚度)"
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
        Add effective width to beam elements (添加截面有效宽度).

        Args:
            element_ids: Element ID(s) (单元编号)
            factor_i: I-end factor (I端系数)
            factor_j: J-end factor (J端系数)
            dz_i: I-end Dz offset (I端 Dz 偏移)
            dz_j: J-end Dz offset (J端 Dz 偏移)
            group_name: Boundary group name (边界组名)
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
        bias_point: list[float] | None = None,
        side_i: bool = True
    ) -> str:
        """
        Update section bias/eccentricity (更新截面偏心/对齐方式).

        Args:
            index: Section ID (截面编号)
            bias_type: Bias type (偏心类型): e.g. "中心", "中上", "中下", "左上", "右上", "左下", "右下"
            center_type: Center type (中心类型): "质心" (Centroid) or "剪心" (Shear center), default "质心"
            shear_consider: Consider shear deformation (是否考虑剪切变形), default True
            bias_point: Custom bias offset [y, z] (自定义偏心距离)
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
    def remove_section(ids: int | list[int] | str) -> str:
        """
        Delete one or more sections from the model (删除截面).

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
        sec_property: list[float],
        side_i: bool = True
    ) -> str:
        """
        Directly modify the calculated properties of a section (直接修改截面特性值).

        Use this to manually override Area, Ix, Iy, Iz etc. after creation.
        Typically used for fine-tuning or correcting auto-calculated values.
        (用于手动覆盖截面面积、惯性矩等自动计算值)

        Args:
            index: Section ID (截面编号)
            sec_property: List of up to 29 section properties in order:
                          [Area, Asy, Asz, Ixx, Iyy, Izz, ...]
                          (截面特性列表，按顺序: 面积, 剪切面积y, 剪切面积z, 扭转惯性矩, 抗弯惯性矩y, 抗弯惯性矩z, ...)
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
        Recalculate properties for all sections in the model (重新计算所有截面特性).

        Call this after creating or modifying section geometry to ensure
        Area, Iy, Iz, J etc. are up-to-date.
        (在创建或修改截面几何后调用，确保面积、惯性矩等特性值为最新)
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
    ) -> str:
        """
        Set support boundary conditions on nodes (设置节点支承).

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
        """
        try:
            boundary_info = [dx, dy, dz, rx, ry, rz]
            kwargs: dict[str, Any] = {}
            if group_name:
                kwargs["group_name"] = group_name
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
        Apply forces/moments at nodes (施加节点荷载).

        Args:
            node_id: Node ID(s) (节点编号)
            case_name: Load case name (荷载工况名)
            fx: Force in X direction (X方向力)
            fy: Force in Y direction (Y方向力)
            fz: Force in Z direction (Z方向力)
            mx: Moment about X axis (绕X轴弯矩)
            my: Moment about Y axis (绕Y轴弯矩)
            mz: Moment about Z axis (绕Z轴弯矩)
            group_name: Load group name (荷载组名)
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
        direction: int = 3,
        load_values: list[float] | None = None,
        load_positions: list[float] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply distributed load on beam elements (施加梁单元分布荷载).

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
        Apply system temperature load (体系温度/整体升降温荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            temperature: Temperature value (温度变化值，如升温+20，降温-20)
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
        section_oriental: int = 0,
        element_type: int = 1,
        group_name: str = "",
    ) -> str:
        """
        Apply gradient temperature load (梯度温度荷载).

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
        orientation: int = 1,
        temperature_data: list[list[float]] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply custom temperature load (自定义温度荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            orientation: Direction of temperature change (温度方向, 1=Y向, 2=Z向)
            temperature_data: Custom temperature points [[distance, temp_diff], ...] (温度数据点)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs: dict[str, Any] = {"orientation": orientation}
            if group_name:
                kwargs["group_name"] = group_name
            if temperature_data is not None:
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
        sec_type: int = 1,
        t1: float = 0,
        t2: float = 0,
        t3: float = 0,
        t4: float = 0,
        thick: float = 0,
        group_name: str = "",
    ) -> str:
        """
        Apply beam section temperature load (梁截面温度荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            code_index: Code index (规范号)
            sec_type: Section type (截面类型, 如1为箱梁等)
            t1: Temperature difference param 1 (各部位温差参数1)
            t2: Temperature difference param 2 (各部位温差参数2)
            t3: Temperature difference param 3 (各部位温差参数3)
            t4: Temperature difference param 4 (各部位温差参数4)
            thick: Thickness parameter (厚度参数)
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
        tension_type: int = 1,
        application_type: int = 1,
        stiffness: float = 0.0,
        group_name: str = "",
    ) -> str:
        """
        Apply initial tension load (初拉力荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            tension: Tension force (拉力值)
            tension_type: Type of tension (初拉力类型)
            application_type: Application type (施加方式)
            stiffness: Stiffness reduction (刚度参数)
            group_name: Load group name (荷载组名)
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
        tension_type: int = 1,
        group_name: str = "",
    ) -> str:
        """
        Apply cable length adjustment load (索长误差荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            length: Length difference (长度误差量)
            tension_type: Tension type (拉力类型)
            group_name: Load group name (荷载组名)
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
        load_type: int = 1,
        load_place: int = 1,
        coord_system: int = 3,
        list_load: list[float] | float | None = None,
        list_xy: list[float] | None = None,
        group_name: str = "",
    ) -> str:
        """
        Apply plate element load (板单元面上荷载).

        Args:
            element_id: Element ID(s) (单元编号)
            case_name: Load case name (荷载工况名)
            load_type: Load type (荷载类型)
            load_place: Application place (施加位置)
            coord_system: Coordinate system (坐标系: 3为整体)
            list_load: Load values (荷载值)
            list_xy: Location coords (位置坐标)
            group_name: Load group name (荷载组名)
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
        point1: list[float] | None = None,
        point2: list[float] | None = None,
        point3: list[float] | None = None,
        plate_ids: list[int] | None = None,
        coord_system: int = 3,
        group_name: str = "",
    ) -> str:
        """
        Apply arbitrary distributed plane load (任意分布面荷载).

        Args:
            index: Load ID (编号)
            case_name: Load case name (荷载工况名)
            type_name: Load type name (分布面荷载类型名)
            point1: 1st point defining the plane [x,y,z] (定义面的点1)
            point2: 2nd point defining the plane [x,y,z] (定义面的点2)
            point3: 3rd point defining the plane [x,y,z] (定义面的点3)
            plate_ids: Optional plate elements to load (指定板单元)
            coord_system: Coordinate system (坐标系)
            group_name: Load group name (荷载组名)
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

        Args:
            node_id: Node ID(s) (节点编号)
            case_name: Load case name (荷载工况名)
            dz: Settlement in Z direction (Z向沉降量/下沉为负值)
            dx: Displacement in X direction (X向强制位移)
            dy: Displacement in Y direction (Y向强制位移)
            rx: Rotation around X axis (绕X轴强制转角)
            ry: Rotation around Y axis (绕Y轴强制转角)
            rz: Rotation around Z axis (绕Z轴强制转角)
            group_name: Load group name (荷载组名)
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
        mass_x: float = 0.0,
        mass_y: float = 0.0,
        mass_z: float = 0.0,
        mass_rm: float = 0.0,
    ) -> str:
        """
        Add nodal mass for dynamic analysis (添加节点质量).

        Args:
            node_id: Node ID(s) (节点编号)
            mass_x: Mass in X direction (X向质量)
            mass_y: Mass in Y direction (Y向质量)
            mass_z: Mass in Z direction (Z向质量)
            mass_rm: Rotational mass (转动质量)
        """
        try:
            mass_info = (mass_x, mass_y, mass_z, mass_rm)
            provider.add_nodal_mass(node_id=node_id, mass_info=mass_info)
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
        Convert a load case to mass for dynamic analysis (将荷载转换为质量).

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
        kind: int = 0,
        function_info: list[list[float]] | None = None,
    ) -> str:
        """
        Add response spectrum function (添加反应谱函数).

        Args:
            name: Function name (函数名称)
            factor: Scale factor (比例系数)
            kind: Type of spectrum (反应谱类型, 例如中国规范等)
            function_info: User defined spectrum points [[period, value], ...] (自定义谱数据)
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
        kind: int = 1,
        info_x: list | None = None,
        info_y: list | None = None,
        info_z: list | None = None,
    ) -> str:
        """
        Add response spectrum load case (添加反应谱工况).

        Args:
            name: Case name (工况名称)
            description: Description (描述)
            kind: Combination method (组合方法, SRSS/CQC等)
            info_x: X direction info [function_name, factor] (X向配置 [谱函数名, 系数])
            info_y: Y direction info [function_name, factor] (Y向配置)
            info_z: Z direction info [function_name, factor] (Z向配置)
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
        kind: int = 0,
        function_info: list[list[float]] | None = None,
    ) -> str:
        """
        Add time history function (添加时程函数).

        Args:
            name: Function name (函数名称)
            factor: Scale factor (比例系数)
            kind: Type (类型)
            function_info: Time history points [[time, value], ...] (时程数据点)
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
        Add time history analysis case (添加时程分析工况).

        Args:
            name: Case name (工况名称)
            duration: Total duration in seconds (总时长)
            time_step: Output time step in seconds (输出步长)
            description: Description (描述)
            index: ID index (编号)
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
        Configure buckling analysis settings (屈曲分析设定).

        Args:
            do_analysis: Enable buckling analysis (是否进行屈曲分析)
            mode_count: Number of modes to calculate (计算模态数)
            stage_id: Construction stage ID for base state, -1 for base model (施工阶段号)
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
        duration: float,
        active_structures: list[list] | None = None,
        active_boundaries: list[list] | None = None,
        active_loads: list[list] | None = None,
    ) -> str:
        """
        Add a construction stage (添加施工阶段).

        Args:
            name: Stage name (施工阶段名称)
            duration: Stage duration in days (时长，单位：天)
            active_structures: Activated structure groups (激活结构组):
                               [[group_name, age, install_method, weight_stage_id], ...]
                               install_method: 1=deformation, 2=unstressed, 3=tangent, 4=tangent
                               (安装方法: 1=变形法, 2=无应力法, 3=接线法, 4=切线法)
            active_boundaries: Activated boundary groups (激活边界组):
                               [[group_name, position], ...], position: 0=before, 1=after deformation
            active_loads: Activated load groups (激活荷载组):
                          [[group_name, time], ...], time: 0=start, 1=end
        """
        try:
            kwargs: dict[str, Any] = {}
            if active_structures:
                kwargs["active_structures"] = [tuple(s) for s in active_structures]
            if active_boundaries:
                kwargs["active_boundaries"] = [tuple(b) for b in active_boundaries]
            if active_loads:
                kwargs["active_loads"] = [tuple(l) for l in active_loads]
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
        solver_type: int = 0,
    ) -> str:
        """
        Configure analysis settings (配置分析设置).

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
            if do_vibration:
                provider.update_self_vibration_setting(
                    do_analysis=True, mode_num=vibration_modes
                )
            return (
                f"Analysis configured: construction_stage={do_construction_stage}, "
                f"creep={do_creep}, vibration={do_vibration} "
                f"(分析配置完成)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error configuring analysis (配置分析失败): {e}") from e

    @mcp.tool()
    async def run_analysis(ctx: Context, read_timeout: int = 3600) -> str:
        """
        Run the structural analysis calculation (执行结构分析计算).

        Use this after all loads, boundaries, and analysis settings are configured.
        Solving can take a long time; it runs in a worker thread so the connection
        stays responsive, with periodic progress heartbeats.
        求解可能耗时较长，在工作线程中执行以保持连接不阻塞，并周期性上报进度。

        Args:
            read_timeout: Max total solve time in seconds, default 3600
                          (求解总时限秒数；超时抛错，求解本身在后台继续)
        """
        try:
            loop = asyncio.get_running_loop()
            solve = loop.run_in_executor(
                None, lambda: provider.run_analysis(read_timeout=read_timeout)
            )
            elapsed = 0
            # 每 5 秒发一次进度心跳，直到求解线程返回
            while True:
                done, _ = await asyncio.wait({solve}, timeout=5)
                if done:
                    await solve  # 传播求解线程中的异常
                    break
                elapsed += 5
                try:
                    await ctx.report_progress(
                        progress=elapsed, total=read_timeout,
                        message=f"Solving… {elapsed}s elapsed (求解中，已用 {elapsed}s)",
                    )
                except Exception:
                    pass  # 进度上报失败不应影响求解
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
                       For stage_id=-1, the tool automatically adds "ST:" prefix if missing.
                       (运营阶段查询时工具会自动添加 "ST:" 前缀)
            limit: Max items per page, default 100 (单页条数上限)
            offset: Pagination offset (翻页偏移)

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
            if case_name:
                # 运营阶段查询：qtmodel 要求工况名加 "ST:" 前缀
                # Operation stage queries require "ST:" prefix in qtmodel
                if stage_id == -1 and not case_name.startswith("ST:"):
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
