"""
MCP Tools for bridge modeling operations.
桥梁建模操作工具

Provides tools for creating and managing model entities:
nodes, elements, materials, sections, structure groups, etc.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


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
        except Exception as e:
            return f"Error creating nodes (创建节点失败): {e}"

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
            start_id: ID of the first node (起始节点编号)
            is_merged: Whether to merge duplicate nodes (是否合并重合节点)
            merge_error: Merge tolerance, default 1e-3 (合并容差)

        Examples:
            # 100m simply-supported beam, 101 nodes at 1m pitch along X axis:
            create_nodes_linear(count=101, start_x=0, spacing_x=1.0)

            # Two-span 50m+50m continuous beam, start x from 0:
            create_nodes_linear(count=101, start_x=0, spacing_x=1.0)
        """
        try:
            node_data = [
                [start_x + i * spacing_x, start_y + i * spacing_y, start_z + i * spacing_z]
                for i in range(count)
            ]
            provider.add_nodes(
                node_data=node_data,
                intersected=False,
                is_merged=is_merged,
                merge_error=merge_error,
                numbering_type=1,
                start_id=start_id,
            )
            end_x = start_x + (count - 1) * spacing_x
            end_y = start_y + (count - 1) * spacing_y
            end_z = start_z + (count - 1) * spacing_z
            return (
                f"Created {count} nodes (IDs {start_id}–{start_id + count - 1}), "
                f"from ({start_x},{start_y},{start_z}) to ({end_x:.3f},{end_y:.3f},{end_z:.3f}) "
                f"(成功批量创建 {count} 个等间距节点)"
            )
        except Exception as e:
            return f"Error creating linear nodes (批量创建节点失败): {e}"



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
        except Exception as e:
            return f"Error creating beam element (创建单元失败): {e}"

    @mcp.tool()
    def create_beam_elements_linear(
        node_id_start: int,
        count: int,
        mat_id: int,
        sec_id: int,
        element_id_start: int = 1,
        beta_angle: float = 0.0,
        ele_type: int = 1,
    ) -> str:
        """
        Batch-create frame elements connecting consecutive nodes along a girder
        (批量创建沿主梁方向连接相邻节点的梁单元).

        This is the most efficient way to model a bridge girder — instead of
        specifying every element individually, you only need the starting node,
        the count, and the material/section.

        Elements are created connecting nodes: node_id_start→+1, node_id_start+1→+2, etc.

        Args:
            node_id_start: ID of the first node (I end of first element) (起始节点编号)
            count: Number of elements to create (单元数量)
            mat_id: Material ID for all elements (所有梁单元的材料编号)
            sec_id: Section ID for all elements (所有梁单元的截面编号)
            element_id_start: ID assigned to the first element, then auto-incremented
                              (第一个单元的编号，后续自动递增)
            beta_angle: Beta angle in degrees, same for all elements (贝塔角，度)
            ele_type: 1=Beam(梁), 2=Truss(杆), 3=Cable(索)

        Examples:
            # 100m beam with 100 elements (101 nodes already created at IDs 1–101):
            create_beam_elements_linear(node_id_start=1, count=100, mat_id=1, sec_id=1)

            # Second span of a two-span continuous beam (nodes 101-201):
            create_beam_elements_linear(node_id_start=101, count=100, mat_id=1, sec_id=1,
                                        element_id_start=101)
        """
        try:
            ele_data = [
                [element_id_start + i, ele_type, mat_id, sec_id, beta_angle,
                 node_id_start + i, node_id_start + i + 1, 0, 0.0]
                for i in range(count)
            ]
            provider.add_elements(ele_data=ele_data)
            last_ele = element_id_start + count - 1
            last_node = node_id_start + count
            return (
                f"Created {count} beam elements (IDs {element_id_start}–{last_ele}), "
                f"connecting nodes {node_id_start}–{last_node} "
                f"(mat={mat_id}, sec={sec_id}) "
                f"(成功批量创建 {count} 个梁单元)"
            )
        except Exception as e:
            return f"Error creating beam elements (批量创建梁单元失败): {e}"

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
        except Exception as e:
            return f"Error creating elements (创建单元失败): {e}"

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
        except Exception as e:
            return f"Error creating load group (创建荷载组失败): {e}"

    @mcp.tool()
    def create_load_case(
        name: str,
        case_type: str = "施工阶段荷载",
    ) -> str:
        """
        Create a static load case (创建静力荷载工况).

        Before applying self-weight or other static loads, a load case MUST be created first.
        必须先创建荷载工况，然后才能在该工况下施加荷载。

        Args:
            name: Name of the load case (工况名称, e.g. "自重", "恒荷", "SW")
            case_type: Type of load case (荷载工况类型), valid options:
                "施工阶段荷载" (default, for stage-based 阶段工况),
                "恒荷" (permanent/dead load),
                "活荷" (live load),
                "预应力" (prestress),
                "车辆荷载" (vehicle load)
        """
        try:
            provider.add_load_case(name=name, case_type=case_type)
            return f"Successfully created load case '{name}' (type='{case_type}') (成功创建荷载工况 '{name}')"
        except Exception as e:
            return f"Error creating load case '{name}' (创建工况失败): {e}"



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
            kwargs = {}
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
        except Exception as e:
            return f"Error creating material (创建材料失败): {e}"

    @mcp.tool()
    def create_section(
        name: str,
        sec_type: str,
        sec_info: list[float] | None = None,
        box_height: float | None = None,
        box_num: int | None = None,
    ) -> str:
        """
        Create a cross-section in the bridge model (创建截面).

        Args:
            name: Section name (截面名称)
            sec_type: Section type name (截面类型), e.g.: '矩形'(Rectangle), '圆形'(Circle),
                      '工字形'(I-shape), '混凝土箱梁'(Concrete box girder), '工字钢梁'(Steel I-girder),
                      '箱型钢梁'(Steel box girder)
            sec_info: Section dimension parameters (截面参数列表), varies by sec_type
            box_height: Box girder height, required for concrete box girder (箱梁梁高)
            box_num: Number of cells, required for concrete box girder (箱室数)
        """
        try:
            kwargs = {}
            if sec_info:
                kwargs["sec_info"] = sec_info
            if box_height is not None:
                kwargs["box_height"] = box_height
            if box_num is not None:
                kwargs["box_num"] = box_num
            provider.add_section(name=name, sec_type=sec_type, **kwargs)
            return f"Successfully created section '{name}' (type: {sec_type}) (成功创建截面 '{name}')"
        except Exception as e:
            return f"Error creating section (创建截面失败): {e}"

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
            kwargs = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_general_support(
                node_id=node_id, boundary_info=boundary_info, **kwargs
            )
            return f"Successfully set support on node(s) {node_id} (成功设置支承)"
        except Exception as e:
            return f"Error setting support (设置支承失败): {e}"

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
            kwargs = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_nodal_force(
                node_id=node_id, case_name=case_name, load_info=load_info, **kwargs
            )
            return f"Successfully applied force to node(s) {node_id} in case '{case_name}' (成功施加荷载)"
        except Exception as e:
            return f"Error applying force (施加荷载失败): {e}"

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
            kwargs = {"coord_system": direction}
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
        except Exception as e:
            return f"Error applying distributed load (施加分布荷载失败): {e}"

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
            kwargs = {}
            if active_structures:
                kwargs["active_structures"] = [tuple(s) for s in active_structures]
            if active_boundaries:
                kwargs["active_boundaries"] = [tuple(b) for b in active_boundaries]
            if active_loads:
                kwargs["active_loads"] = [tuple(l) for l in active_loads]
            provider.add_construction_stage(name=name, duration=duration, **kwargs)
            return f"Successfully added construction stage '{name}' (成功添加施工阶段 '{name}')"
        except Exception as e:
            return f"Error adding construction stage (添加施工阶段失败): {e}"

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
        except Exception as e:
            return f"Error configuring analysis (配置分析失败): {e}"

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
        except Exception as e:
            return f"Error validating model (模型验证失败): {e}"

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
        except Exception as e:
            return f"Error getting model info (获取模型信息失败): {e}"

    @mcp.tool()
    def get_analysis_results(
        result_type: str,
        ids: int | list[int] | str = 1,
        stage_id: int = -1,
        case_name: str = "",
    ) -> str:
        """
        Get analysis results from the bridge model (获取分析结果).

        Args:
            result_type: Type of result to retrieve (结果类型):
                'deformation' (变形), 'force' (内力), 'stress' (应力), 'reaction' (反力)
            ids: Node/Element IDs to query (查询的节点/单元编号)
            stage_id: Construction stage (施工阶段): -1=operation(运营), 0=envelope(包络),
                      n=stage n (第n阶段)
            case_name: Load case name for operation stage (运营阶段荷载工况名)
        """
        try:
            kwargs = {}
            if case_name:
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
                return (
                    f"Unknown result_type '{result_type}'. "
                    "Available: deformation, force, stress, reaction"
                )
            return str(result)
        except Exception as e:
            return f"Error getting results (获取结果失败): {e}"
