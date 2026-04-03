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
    def create_rectangle_section(name: str, width: float, height: float) -> str:
        """
        Create a rectangular cross-section (创建矩形截面).

        Args:
            name: Section name (截面名称)
            width: Rectangle width (长)
            height: Rectangle height (高)
        """
        try:
            provider.add_section(name=name, sec_type="矩形", sec_info=[width, height])
            return f"Successfully created rectangular section '{name}' ({width}x{height})"
        except Exception as e:
            return f"Error creating rectangular section: {e}"

    @mcp.tool()
    def create_circle_section(name: str, diameter: float) -> str:
        """
        Create a circular cross-section (创建圆形截面).

        Args:
            name: Section name (截面名称)
            diameter: Circle diameter (直径)
        """
        try:
            provider.add_section(name=name, sec_type="圆形", sec_info=[diameter])
            return f"Successfully created circular section '{name}' (D={diameter})"
        except Exception as e:
            return f"Error creating circular section: {e}"

    @mcp.tool()
    def create_circular_tube_section(name: str, diameter: float, thickness: float) -> str:
        """
        Create a circular tube cross-section (创建圆管截面).

        Args:
            name: Section name (截面名称)
            diameter: Tube outer diameter (直径)
            thickness: Wall thickness (壁厚)
        """
        try:
            provider.add_section(name=name, sec_type="圆管", sec_info=[diameter, thickness])
            return f"Successfully created circular tube section '{name}'"
        except Exception as e:
            return f"Error creating circular tube section: {e}"

    @mcp.tool()
    def create_t_section(name: str, width: float, height: float, web_thickness: float, top_thickness: float) -> str:
        """
        Create a T-shape cross-section (创建T形截面).

        Args:
            name: Section name (截面名称)
            width: Top flange width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
        """
        try:
            provider.add_section(name=name, sec_type="T形", sec_info=[width, height, web_thickness, top_thickness])
            return f"Successfully created T-shape section '{name}'"
        except Exception as e:
            return f"Error creating T-shape section: {e}"

    @mcp.tool()
    def create_i_section(
        name: str,
        top_width: float,
        bottom_width: float,
        height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
    ) -> str:
        """
        Create an I-shape cross-section (创建I字形截面).

        Args:
            name: Section name (截面名称)
            top_width: Top flange width (顶板宽)
            bottom_width: Bottom flange width (底板宽)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="I字形",
                sec_info=[top_width, bottom_width, height, web_thickness, top_thickness, bottom_thickness],
            )
            return f"Successfully created I-shape section '{name}'"
        except Exception as e:
            return f"Error creating I-shape section: {e}"

    @mcp.tool()
    def create_box_section(
        name: str,
        width: float,
        height: float,
        bottom_width: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
    ) -> str:
        """
        Create a box cross-section (创建箱型截面).

        Args:
            name: Section name (截面名称)
            width: Top width (长)
            height: Total height (高)
            bottom_width: Bottom width (底板宽)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="箱型",
                sec_info=[width, height, bottom_width, web_thickness, top_thickness, bottom_thickness],
            )
            return f"Successfully created box section '{name}'"
        except Exception as e:
            return f"Error creating box section: {e}"

    @mcp.tool()
    def create_solid_octagon_section(name: str, width: float, height: float, chamfer_height: float, chamfer_width: float) -> str:
        """
        Create a solid octagon cross-section (创建实腹八边形截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
            chamfer_height: Chamfer height (倒角高)
            chamfer_width: Chamfer width (倒角宽)
        """
        try:
            provider.add_section(name=name, sec_type="实腹八边形", sec_info=[width, height, chamfer_height, chamfer_width])
            return f"Successfully created solid octagon section '{name}'"
        except Exception as e:
            return f"Error creating solid octagon section: {e}"

    @mcp.tool()
    def create_solid_round_ended_section(name: str, width: float, height: float) -> str:
        """
        Create a solid round-ended cross-section (创建实腹圆端形截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
        """
        try:
            provider.add_section(name=name, sec_type="实腹圆端形", sec_info=[width, height])
            return f"Successfully created solid round-ended section '{name}'"
        except Exception as e:
            return f"Error creating solid round-ended section: {e}"

    @mcp.tool()
    def create_hollow_round_ended_section(name: str, width: float, height: float, thickness: float) -> str:
        """
        Create a hollow round-ended cross-section (创建空腹圆端形截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
            thickness: Wall thickness (壁厚)
        """
        try:
            provider.add_section(name=name, sec_type="空腹圆端形", sec_info=[width, height, thickness])
            return f"Successfully created hollow round-ended section '{name}'"
        except Exception as e:
            return f"Error creating hollow round-ended section: {e}"

    @mcp.tool()
    def create_hollow_octagon_section(
        name: str,
        width: float,
        height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        chamfer_width: float,
        chamfer_height: float,
    ) -> str:
        """
        Create a hollow octagon cross-section (创建空腹八边形截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            chamfer_width: Chamfer width (倒角宽)
            chamfer_height: Chamfer height (倒角高)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="空腹八边形",
                sec_info=[width, height, web_thickness, top_thickness, bottom_thickness, chamfer_width, chamfer_height]
            )
            return f"Successfully created hollow octagon section '{name}'"
        except Exception as e:
            return f"Error creating hollow octagon section: {e}"

    @mcp.tool()
    def create_inner_octagon_section(
        name: str,
        width: float,
        height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        chamfer_width: float,
        chamfer_height: float,
    ) -> str:
        """
        Create an inner octagon cross-section (创建内八角形截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            chamfer_width: Chamfer width (倒角宽)
            chamfer_height: Chamfer height (倒角高)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="内八角形",
                sec_info=[width, height, web_thickness, top_thickness, bottom_thickness, chamfer_width, chamfer_height]
            )
            return f"Successfully created inner octagon section '{name}'"
        except Exception as e:
            return f"Error creating inner octagon section: {e}"

    @mcp.tool()
    def create_inverted_t_section(name: str, width: float, height: float, web_thickness: float, bottom_thickness: float) -> str:
        """
        Create an inverted T-shape cross-section (创建倒T形截面).

        Args:
            name: Section name (截面名称)
            width: Bottom flange width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
        """
        try:
            provider.add_section(name=name, sec_type="倒T形", sec_info=[width, height, web_thickness, bottom_thickness])
            return f"Successfully created inverted T-shape section '{name}'"
        except Exception as e:
            return f"Error creating inverted T-shape section: {e}"

    @mcp.tool()
    def create_horseshoe_t_section(
        name: str,
        width: float,
        height: float,
        web_thickness: float,
        flange_thickness: float,
        web_bottom_taper_height: float,
        top_chamfer_width: float,
        top_chamfer_height: float,
        bottom_chamfer_width: float,
        bottom_chamfer_height: float,
    ) -> str:
        """
        Create a horseshoe T-shape cross-section (创建马蹄T形截面).

        Args:
            name: Section name (截面名称)
            width: Flange width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            flange_thickness: Flange thickness (底板厚)
            web_bottom_taper_height: Web bottom taper height (腹板底变高)
            top_chamfer_width: Top chamfer width (顶板倒角宽)
            top_chamfer_height: Top chamfer height (顶板倒角高)
            bottom_chamfer_width: Bottom chamfer width (腹板倒角宽)
            bottom_chamfer_height: Bottom chamfer height (腹板倒角高)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="马蹄T形",
                sec_info=[width, height, web_thickness, flange_thickness, web_bottom_taper_height, top_chamfer_width, top_chamfer_height, bottom_chamfer_width, bottom_chamfer_height]
            )
            return f"Successfully created horseshoe T-shape section '{name}'"
        except Exception as e:
            return f"Error creating horseshoe T-shape section: {e}"

    @mcp.tool()
    def create_concrete_i_section(
        name: str,
        top_width: float,
        bottom_width: float,
        height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        top_chamfer_width: float,
        top_chamfer_height: float,
        bottom_chamfer_width: float,
        bottom_chamfer_height: float,
    ) -> str:
        """
        Create a concrete I-shape cross-section (创建I字型混凝土截面).

        Args:
            name: Section name (截面名称)
            top_width: Top flange width (顶板宽)
            bottom_width: Bottom flange width (底板宽)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            top_chamfer_width: Top chamfer width (顶板倒角宽)
            top_chamfer_height: Top chamfer height (顶板倒角高)
            bottom_chamfer_width: Bottom chamfer width (底板倒角宽)
            bottom_chamfer_height: Bottom chamfer height (底板倒角高)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="I字型混凝土",
                sec_info=[top_width, bottom_width, height, web_thickness, top_thickness, bottom_thickness, top_chamfer_width, top_chamfer_height, bottom_chamfer_width, bottom_chamfer_height]
            )
            return f"Successfully created concrete I-shape section '{name}'"
        except Exception as e:
            return f"Error creating concrete I-shape section: {e}"

    @mcp.tool()
    def create_cfst_section(name: str, diameter: float, thickness: float) -> str:
        """
        Create a Concrete Filled Steel Tube (CFST) cross-section (创建钢管砼组合截面).

        Args:
            name: Section name (截面名称)
            diameter: Outer diameter of the steel tube (钢管直径)
            thickness: Wall thickness of the steel tube (钢管壁厚)
        """
        try:
            provider.add_section(name=name, sec_type="钢管砼", sec_info=[diameter, thickness])
            return f"Successfully created CFST section '{name}'"
        except Exception as e:
            return f"Error creating CFST section: {e}"

    @mcp.tool()
    def create_cfsb_section(
        name: str,
        width: float,
        height: float,
        bottom_width: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
    ) -> str:
        """
        Create a Concrete Filled Steel Box (CFSB) cross-section (创建钢箱砼组合截面).

        Args:
            name: Section name (截面名称)
            width: Top width (长)
            height: Total height (高)
            bottom_width: Steel box bottom width (钢箱底板宽)
            web_thickness: Steel box web thickness (钢箱腹板厚)
            top_thickness: Steel box top flange thickness (钢箱顶板厚)
            bottom_thickness: Steel box bottom flange thickness (钢箱底板厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="钢箱砼",
                sec_info=[width, height, bottom_width, web_thickness, top_thickness, bottom_thickness]
            )
            return f"Successfully created CFSB section '{name}'"
        except Exception as e:
            return f"Error creating CFSB section: {e}"

    @mcp.tool()
    def create_ribbed_h_section(
        name: str,
        height: float,
        width: float,
        left_right_web_thickness: float,
        cross_web_thickness: float,
        web_rib_height: float,
        web_rib_thickness: float,
    ) -> str:
        """
        Create a ribbed H-section (创建带肋H截面).

        Args:
            name: Section name (截面名称)
            height: Total height (高)
            width: Total width (长)
            left_right_web_thickness: Left and right web thickness (左右腹板厚)
            cross_web_thickness: Cross web thickness (横向腹板厚)
            web_rib_height: Web rib height (腹板肋高)
            web_rib_thickness: Web rib thickness (腹板肋厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="带肋H截面",
                sec_info=[height, width, left_right_web_thickness, cross_web_thickness, web_rib_height, web_rib_thickness]
            )
            return f"Successfully created ribbed H-section '{name}'"
        except Exception as e:
            return f"Error creating ribbed H-section: {e}"

    @mcp.tool()
    def create_ribbed_i_section(
        name: str,
        top_width: float,
        bottom_width: float,
        web_height: float,
        top_thickness: float,
        bottom_thickness: float,
        web_thickness: float,
        top_flange_rib_distance: float,
        rib_count: int,
        rib_spacing: float,
        rib_height: float,
        rib_thickness: float,
    ) -> str:
        """
        Create a ribbed steel I-shape section (创建钢工字型带肋截面).

        Args:
            name: Section name (截面名称)
            top_width: Top flange width (顶板长)
            bottom_width: Bottom flange width (底板长)
            web_height: Web height (中腹高)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            web_thickness: Web thickness (腹板厚)
            top_flange_rib_distance: Distance from top flange to web rib (顶板与腹板肋的距离)
            rib_count: Number of ribs (肋数)
            rib_spacing: Rib spacing (肋距)
            rib_height: Rib height (肋高)
            rib_thickness: Rib thickness (肋厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="钢工字型带肋",
                sec_info=[top_width, bottom_width, web_height, top_thickness, bottom_thickness, web_thickness, top_flange_rib_distance, rib_count, rib_spacing, rib_height, rib_thickness]
            )
            return f"Successfully created ribbed steel I-shape section '{name}'"
        except Exception as e:
            return f"Error creating ribbed steel I-shape section: {e}"

    @mcp.tool()
    def create_ribbed_steel_box_section(
        name: str,
        width: float,
        height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        top_bottom_rib_height: float,
        top_bottom_rib_thickness: float,
        web_rib_height: float,
        web_rib_thickness: float,
        top_bottom_rib_spacing: float,
        web_rib_spacing: float,
        web_rib_count: int,
        top_bottom_rib_count: int,
    ) -> str:
        """
        Create a ribbed steel box cross-section (创建带肋钢箱截面).

        Args:
            name: Section name (截面名称)
            width: Total width (长)
            height: Total height (高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            top_bottom_rib_height: Top and bottom rib height (顶底板肋高)
            top_bottom_rib_thickness: Top and bottom rib thickness (顶底板肋厚)
            web_rib_height: Web rib height (腹板肋高)
            web_rib_thickness: Web rib thickness (腹板肋厚)
            top_bottom_rib_spacing: Top and bottom rib spacing (顶底板肋距)
            web_rib_spacing: Web rib spacing (腹板肋距)
            web_rib_count: Number of web ribs (腹板肋数)
            top_bottom_rib_count: Number of top/bottom ribs (顶底板肋数)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="带肋钢箱",
                sec_info=[width, height, web_thickness, top_thickness, bottom_thickness, top_bottom_rib_height, top_bottom_rib_thickness, web_rib_height, web_rib_thickness, top_bottom_rib_spacing, web_rib_spacing, web_rib_count, top_bottom_rib_count]
            )
            return f"Successfully created ribbed steel box section '{name}'"
        except Exception as e:
            return f"Error creating ribbed steel box section: {e}"

    @mcp.tool()
    def create_steel_truss_box_3_section(
        name: str,
        height: float,
        width: float,
        top_cantilever_rib_height: float,
        bottom_cantilever_rib_height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        top_rib_height: float,
        top_rib_thickness: float,
        bottom_rib_height: float,
        bottom_rib_thickness: float,
        web_rib_height: float,
        web_rib_thickness: float,
    ) -> str:
        """
        Create a Steel Truss Box 3 cross-section (创建钢桁箱梁3截面).

        Args:
            name: Section name (截面名称)
            height: Total height (高)
            width: Total width (长)
            top_cantilever_rib_height: Top cantilever rib height (上悬臂肋高)
            bottom_cantilever_rib_height: Bottom cantilever rib height (下悬臂肋高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            top_rib_height: Top rib height (顶板肋高)
            top_rib_thickness: Top rib thickness (顶板肋厚)
            bottom_rib_height: Bottom rib height (底板肋高)
            bottom_rib_thickness: Bottom rib thickness (底板肋厚)
            web_rib_height: Web rib height (腹板肋高)
            web_rib_thickness: Web rib thickness (腹板肋厚)
        """
        try:
            provider.add_section(
                name=name,
                sec_type="钢桁箱梁3",
                sec_info=[
                    height, width, top_cantilever_rib_height, bottom_cantilever_rib_height,
                    web_thickness, top_thickness, bottom_thickness,
                    top_rib_height, top_rib_thickness,
                    bottom_rib_height, bottom_rib_thickness,
                    web_rib_height, web_rib_thickness
                ]
            )
            return f"Successfully created Steel Truss Box 3 section '{name}'"
        except Exception as e:
            return f"Error creating Steel Truss Box 3 section: {e}"

    @mcp.tool()
    def create_steel_truss_box_1_section(
        name: str,
        height: float,
        width: float,
        left_cantilever_width: float,
        right_cantilever_width: float,
        bottom_cantilever_height: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        top_rib_height: float,
        top_rib_thickness: float,
        bottom_rib_height: float,
        bottom_rib_thickness: float,
        top_web_rib_distance: float,
        web_rib_count: int,
        web_rib_spacing: float,
        web_rib_height: float,
        web_rib_thickness: float,
        left_web_rib_pos: int,      # 0 for Inner, 1 for Outer
        right_web_rib_pos: int,     # 0 for Inner, 1 for Outer
        left_cantilever_rib_spacing: float,
        left_cantilever_rib_height: float,
        left_cantilever_rib_thickness: float,
        left_cantilever_rib_top_dist: float,
        left_cantilever_rib_bottom_dist: float,
        left_cantilever_rib_chamfer: float,
        right_cantilever_rib_spacing: float,
        right_cantilever_rib_height: float,
        right_cantilever_rib_thickness: float,
        right_cantilever_rib_top_dist: float,
        right_cantilever_rib_bottom_dist: float,
        right_cantilever_rib_chamfer: float,
    ) -> str:
        """
        Create a Steel Truss Box 1 cross-section (创建钢桁箱梁1截面).

        Args:
            name: Section name (截面名称)
            height: Total height without cantilevers (高)
            width: Total width (长)
            left_cantilever_width: Left cantilever width (左悬臂长)
            right_cantilever_width: Right cantilever width (右悬臂长)
            bottom_cantilever_height: Bottom cantilever height (下悬臂高)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            top_rib_height: Top rib height (顶板肋高)
            top_rib_thickness: Top rib thickness (顶板肋厚)
            bottom_rib_height: Bottom rib height (底板肋高)
            bottom_rib_thickness: Bottom rib thickness (底板肋厚)
            top_web_rib_distance: Distance from top flange to web ribs (顶板与腹板肋距)
            web_rib_count: Number of web ribs (腹板肋数)
            web_rib_spacing: Web rib spacing (腹板肋距)
            web_rib_height: Web rib height (腹板肋高)
            web_rib_thickness: Web rib thickness (腹板肋厚)
            left_web_rib_pos: Left web rib position (0:内Inner, 1:外Outer)
            right_web_rib_pos: Right web rib position (0:内Inner, 1:外Outer)
            left_cantilever_rib_spacing: Left cantilever rib spacing (左悬臂肋距)
            left_cantilever_rib_height: Left cantilever rib height (左悬臂肋高)
            left_cantilever_rib_thickness: Left cantilever rib thickness (左悬臂肋厚)
            left_cantilever_rib_top_dist: Left cantilever rib top dist (左悬臂肋顶距离)
            left_cantilever_rib_bottom_dist: Left cantilever rib bottom dist (左悬臂肋底距离)
            left_cantilever_rib_chamfer: Left cantilever rib chamfer (左悬臂肋倒角)
            right_cantilever_rib_spacing: Right cantilever rib spacing (右悬臂肋距)
            right_cantilever_rib_height: Right cantilever rib height (右悬臂肋高)
            right_cantilever_rib_thickness: Right cantilever rib thickness (右悬臂肋厚)
            right_cantilever_rib_top_dist: Right cantilever rib top dist (右悬臂肋顶距离)
            right_cantilever_rib_bottom_dist: Right cantilever rib bottom dist (右悬臂肋底距离)
            right_cantilever_rib_chamfer: Right cantilever rib chamfer (右悬臂肋倒角)
        """
        try:
            sec_info = [
                height, width, left_cantilever_width, right_cantilever_width, bottom_cantilever_height,
                web_thickness, top_thickness, bottom_thickness,
                top_rib_height, top_rib_thickness, bottom_rib_height, bottom_rib_thickness,
                top_web_rib_distance, web_rib_count, web_rib_spacing, web_rib_height, web_rib_thickness,
                left_web_rib_pos, right_web_rib_pos,
                left_cantilever_rib_spacing, left_cantilever_rib_height, left_cantilever_rib_thickness,
                left_cantilever_rib_top_dist, left_cantilever_rib_bottom_dist, left_cantilever_rib_chamfer,
                right_cantilever_rib_spacing, right_cantilever_rib_height, right_cantilever_rib_thickness,
                right_cantilever_rib_top_dist, right_cantilever_rib_bottom_dist, right_cantilever_rib_chamfer
            ]
            provider.add_section(
                name=name,
                sec_type="钢桁箱梁1",
                sec_info=sec_info,
            )
            return f"Successfully created Steel Truss Box 1 section '{name}'"
        except Exception as e:
            return f"Error creating Steel Truss Box 1 section: {e}"

    @mcp.tool()
    def create_steel_truss_box_2_section(
        name: str,
        height: float,
        width: float,
        left_top_cantilever_width: float,
        right_top_cantilever_width: float,
        left_bottom_cantilever_width: float,
        right_bottom_cantilever_width: float,
        web_thickness: float,
        top_thickness: float,
        bottom_thickness: float,
        top_rib_height: float,
        top_rib_thickness: float,
        bottom_rib_height: float,
        bottom_rib_thickness: float,
        top_web_rib_distance: float,
        web_rib_count: int,
        web_rib_spacing: float,
        web_rib_height: float,
        web_rib_thickness: float,
        left_web_rib_pos: int,
        right_web_rib_pos: int,
        left_top_cantilever_rib_spacing: float,
        left_top_cantilever_rib_height: float,
        left_top_cantilever_rib_thickness: float,
        left_top_cantilever_rib_top_dist: float,
        left_top_cantilever_rib_bottom_dist: float,
        left_top_cantilever_rib_chamfer: float,
        right_top_cantilever_rib_spacing: float,
        right_top_cantilever_rib_height: float,
        right_top_cantilever_rib_thickness: float,
        right_top_cantilever_rib_top_dist: float,
        right_top_cantilever_rib_bottom_dist: float,
        right_top_cantilever_rib_chamfer: float,
        left_bottom_cantilever_rib_spacing: float,
        left_bottom_cantilever_rib_height: float,
        left_bottom_cantilever_rib_thickness: float,
        right_bottom_cantilever_rib_spacing: float,
        right_bottom_cantilever_rib_height: float,
        right_bottom_cantilever_rib_thickness: float,
    ) -> str:
        """
        Create a Steel Truss Box 2 cross-section (创建钢桁箱梁2截面).

        Args:
            name: Section name (截面名称)
            height: Total height (高)
            width: Total width (长)
            left_top_cantilever_width: Left top cantilever width (左上悬臂长)
            right_top_cantilever_width: Right top cantilever width (右上悬臂长)
            left_bottom_cantilever_width: Left bottom cantilever width (左下悬臂长)
            right_bottom_cantilever_width: Right bottom cantilever width (右下悬臂长)
            web_thickness: Web thickness (腹板厚)
            top_thickness: Top flange thickness (顶板厚)
            bottom_thickness: Bottom flange thickness (底板厚)
            ... (and rib parameters for flanges, webs, and all 4 cantilevers as per QtModel UI)
        """
        try:
            sec_info = [
                height, width,
                left_top_cantilever_width, right_top_cantilever_width,
                left_bottom_cantilever_width, right_bottom_cantilever_width,
                web_thickness, top_thickness, bottom_thickness,
                top_rib_height, top_rib_thickness,
                bottom_rib_height, bottom_rib_thickness,
                top_web_rib_distance, web_rib_count, web_rib_spacing, web_rib_height, web_rib_thickness,
                left_web_rib_pos, right_web_rib_pos,
                left_top_cantilever_rib_spacing, left_top_cantilever_rib_height, left_top_cantilever_rib_thickness,
                left_top_cantilever_rib_top_dist, left_top_cantilever_rib_bottom_dist, left_top_cantilever_rib_chamfer,
                right_top_cantilever_rib_spacing, right_top_cantilever_rib_height, right_top_cantilever_rib_thickness,
                right_top_cantilever_rib_top_dist, right_top_cantilever_rib_bottom_dist, right_top_cantilever_rib_chamfer,
                left_bottom_cantilever_rib_spacing, left_bottom_cantilever_rib_height, left_bottom_cantilever_rib_thickness,
                right_bottom_cantilever_rib_spacing, right_bottom_cantilever_rib_height, right_bottom_cantilever_rib_thickness
            ]
            provider.add_section(
                name=name,
                sec_type="钢桁箱梁2",
                sec_info=sec_info,
            )
            return f"Successfully created Steel Truss Box 2 section '{name}'"
        except Exception as e:
            return f"Error creating Steel Truss Box 2 section: {e}"

    @mcp.tool()
    def create_composite_i_section(
        name: str,
        sec_info: list[float],
        materials_ratio: list[float]
    ) -> str:
        """
        Create a Composite I-Girder cross-section (创建工字组合梁截面).

        Args:
            name: Section name (截面名称)
            sec_info: Geometric parameters (几何信息数据如顶板宽、底板宽、厚度等)
            materials_ratio: Combine material parameters (组合材料参数 [Es/Ec, Ds/Dc, ps(钢泊松比), pc(砼泊松比), Ts/Tc])
        """
        try:
            provider.add_section(
                name=name,
                sec_type="工字组合梁",
                sec_info=sec_info,
                mat_combine=materials_ratio
            )
            return f"Successfully created Composite I-Girder section '{name}'"
        except Exception as e:
            return f"Error creating Composite I-Girder section: {e}"

    @mcp.tool()
    def create_composite_box_section(
        name: str,
        sec_info: list[float],
        materials_ratio: list[float]
    ) -> str:
        """
        Create a Composite Box Girder cross-section (创建箱形组合梁截面).

        Args:
            name: Section name (截面名称)
            sec_info: Geometric parameters (几何信息数据如顶板宽、底板宽、厚度等)
            materials_ratio: Combine material parameters (组合材料参数 [Es/Ec, Ds/Dc, ps(钢泊松比), pc(砼泊松比), Ts/Tc])
        """
        try:
            provider.add_section(
                name=name,
                sec_type="箱形组合梁",
                sec_info=sec_info,
                mat_combine=materials_ratio
            )
            return f"Successfully created Composite Box Girder section '{name}'"
        except Exception as e:
            return f"Error creating Composite Box Girder section: {e}"

    @mcp.tool()
    def create_custom_composite_section(
        name: str,
        sec_info: list[float],
        materials_ratio: list[float]
    ) -> str:
        """
        Create a Custom Composite cross-section (创建自定义组合梁截面).

        Args:
            name: Section name (截面名称)
            sec_info: Geometric parameters (几何信息数据)
            materials_ratio: Combine material parameters (组合材料参数 [Es/Ec, Ds/Dc, ps, pc, Ts/Tc])
        """
        try:
            provider.add_section(
                name=name,
                sec_type="自定义组合梁",
                sec_info=sec_info,
                mat_combine=materials_ratio
            )
            return f"Successfully created Custom Composite section '{name}'"
        except Exception as e:
            return f"Error creating Custom Composite section: {e}"

    @mcp.tool()
    def create_concrete_box_girder_section(
        name: str,
        box_num: int,
        box_height: float,
        sec_info: list[float],
        symmetry: bool = True,
        chamfer_info: list[float] | None = None,
        box_other_info: dict | None = None,
    ) -> str:
        """
        Create a Concrete Box Girder cross-section (创建混凝土箱梁截面).

        Args:
            name: Section name (截面名称)
            box_num: Number of box cells (箱室个数)
            box_height: Box girder height (梁高)
            sec_info: Complex geometric list (截面几何基础数据列表如 B1,B2...)
            symmetry: Whether the section is symmetric (是否对称)
            chamfer_info: Chamfer parameter list (倒角数据列表)
            box_other_info: Additional parameters config like i1, B0, B4, T4
        """
        try:
            kwargs = {
                "box_num": box_num,
                "box_height": box_height,
                "symmetry": symmetry,
            }
            if chamfer_info is not None:
                kwargs["chamfer_info"] = chamfer_info
            if box_other_info is not None:
                kwargs["box_other_info"] = box_other_info

            provider.add_section(
                name=name,
                sec_type="混凝土箱梁",
                sec_info=sec_info,
                **kwargs
            )
            return f"Successfully created Concrete Box Girder section '{name}'"
        except Exception as e:
            return f"Error creating Concrete Box Girder section: {e}"

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
        except Exception as e:
            return f"Error creating polygon section: {e}"

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
        except Exception as e:
            return f"Error creating line-width section: {e}"

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
        except Exception as e:
            return f"Error creating property-based section: {e}"

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
        except Exception as e:
            return f"Error creating tapered section (创建渐变截面失败): {e}"

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
        except Exception as e:
            return f"Error updating section bias (更新截面偏心失败): {e}"

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
