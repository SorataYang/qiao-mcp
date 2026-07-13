"""
MCP Tools for moving load analysis.
移动荷载工具

Provides tools for the complete qtmodel live-load workflow:
node tandems (节点纵列) → influence planes (影响面) → lane lines (车道线)
→ standard vehicles (标准车辆) → live load cases (活载工况).
"""

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider


def register_moving_load_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register moving load MCP tools."""

    @mcp.tool()
    def add_node_tandem(
        name: str,
        node_ids: list[int] | str,
        order_by_x: bool = True,
    ) -> str:
        """
        Define a node tandem — the node path a moving load travels along
        (添加节点纵列，移动荷载行进经过的节点序列).

        This is STEP 1 of the moving load workflow:
        add_node_tandem → add_influence_plane → add_traffic_lane
        → add_standard_vehicle → create_live_load_case

        Args:
            name: Tandem name (节点纵列名, e.g. "节点纵列1")
            node_ids: Node IDs along the girder, list or range string like "1to101"
                      (节点列表，支持 XtoY 范围字符串)
            order_by_x: Auto-sort nodes by X coordinate ascending (按X坐标自动排序)
        """
        try:
            provider.add_node_tandem(name=name, node_ids=node_ids, order_by_x=order_by_x)
            return f"Node tandem '{name}' created (节点纵列 '{name}' 创建成功)"
        except Exception as e:
            return f"Error adding node tandem (添加节点纵列失败): {e}"

    @mcp.tool()
    def add_influence_plane(
        name: str,
        tandem_names: list[str],
    ) -> str:
        """
        Define an influence plane from node tandems (添加影响面).

        STEP 2 of the moving load workflow. The influence plane is built
        from one or more node tandems and is required by lanes and load cases.

        Args:
            name: Influence plane name (影响面名称, e.g. "影响面1")
            tandem_names: Node tandem names (节点纵列名称列表)
        """
        try:
            provider.add_influence_plane(name=name, tandem_names=tandem_names)
            return f"Influence plane '{name}' created (影响面 '{name}' 创建成功)"
        except Exception as e:
            return f"Error adding influence plane (添加影响面失败): {e}"

    @mcp.tool()
    def add_traffic_lane(
        name: str,
        influence_name: str,
        tandem_name: str,
        offset: float = 0.0,
        lane_width: float = 3.1,
        optimize: bool = False,
        direction: int = 0,
    ) -> str:
        """
        Define a traffic lane line for moving load analysis (添加车道线).

        STEP 3 of the moving load workflow. Requires an influence plane
        and a node tandem created beforehand.

        Args:
            name: Lane name (车道线名称, e.g. "车道1")
            influence_name: Influence plane name (影响面名称)
            tandem_name: Node tandem name (节点纵列名)
            offset: Lateral offset from the tandem in meters (横向偏移，单位m)
            lane_width: Lane width in meters (车道宽度，单位m), typical 3.1~3.75
            optimize: Allow vehicle lateral wandering (是否允许车辆摆动)
            direction: Travel direction (行车方向): 0=forward(向前), 1=backward(向后)
        """
        try:
            provider.add_lane(
                name=name,
                influence_name=influence_name,
                tandem_name=tandem_name,
                offset=offset,
                lane_width=lane_width,
                optimize=optimize,
                direction=direction,
            )
            return (
                f"Traffic lane '{name}' defined on plane '{influence_name}' "
                f"(width={lane_width}m) (车道线 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error defining traffic lane (添加车道线失败): {e}"

    @mcp.tool()
    def add_standard_vehicle(
        name: str,
        standard_code: int = 5,
        load_type: str = "公路I级车道",
        load_length: float = 0.0,
        factor: float = 1.0,
    ) -> str:
        """
        Add a standard vehicle load from a design code database (添加标准车辆荷载).

        STEP 4 of the moving load workflow.

        Args:
            name: Vehicle name (车辆荷载名称)
            standard_code: Design code (荷载规范):
                1=铁路桥涵规范 TB10002-2017, 2=城市桥梁 CJJ11-2019,
                3=公路工程技术标准 JTJ 001-97, 4=公路桥涵通规 JTG D60-2004,
                5=公路桥涵通规 JTG D60-2015, 6=城市轨道交通 GB/T51234-2017,
                7=市域铁路 T/CRS C0101-2017
            load_type: Load type name exactly as shown in the QiaoTong UI
                       (荷载类型，与软件界面名称一致), e.g. "公路I级车道" (公路通规),
                       "高速铁路" (铁路规范)
            load_length: Load length limit, 0 = unlimited (荷载长度限制，铁路规范参数)
            factor: Load factor (荷载系数，铁路 ZH 荷载参数)
        """
        try:
            provider.add_standard_vehicle(
                name=name,
                standard_code=standard_code,
                load_type=load_type,
                load_length=load_length,
                factor=factor,
            )
            return (
                f"Standard vehicle '{name}' added (code {standard_code}, type '{load_type}') "
                f"(标准车辆 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error adding standard vehicle (添加标准车辆失败): {e}"

    @mcp.tool()
    def create_live_load_case(
        name: str,
        influence_plane: str,
        span: float,
        sub_cases: list[list],
    ) -> str:
        """
        Create a moving live load case (创建活载工况).

        FINAL STEP of the moving load workflow. The analysis engine finds the
        worst-case vehicle positions for envelope results
        (分析引擎自动计算最不利车辆位置得到包络效应).

        Args:
            name: Load case name (活载工况名)
            influence_plane: Influence plane name (影响面名称)
            span: Bridge span in meters (跨度，单位m)
            sub_cases: Sub-case list, each item [vehicle_name, factor, [lane names...]]
                       (子工况信息 [[车辆名, 系数, [车道名...]], ...])

        Example:
            create_live_load_case(name="活载工况1", influence_plane="影响面1", span=100,
                                  sub_cases=[["公路I级", 1.0, ["车道1", "车道2"]]])
        """
        try:
            formatted = [(str(v), float(f), list(lanes)) for v, f, lanes in sub_cases]
            provider.add_live_load_case(
                name=name,
                influence_plane=influence_plane,
                span=span,
                sub_case=formatted,
            )
            return (
                f"Live load case '{name}' created on plane '{influence_plane}' "
                f"with {len(formatted)} sub-case(s) (活载工况 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error creating live load case (创建活载工况失败): {e}"

    @mcp.tool()
    def get_live_load_results(
        case_name: str,
        result_type: str = "force",
        element_ids: list[int] | str = "",
    ) -> str:
        """
        Get moving load analysis results (获取移动荷载分析结果).

        Returns envelope (maximum and minimum) results for specified elements.
        返回指定单元的移动荷载包络结果（最大值和最小值）。

        Args:
            case_name: Live load case name (活载工况名)
            result_type: Result type (结果类型): 'force'(内力), 'stress'(应力), 'deformation'(变形)
            element_ids: Element or node IDs to query (查询的单元或节点编号)
        """
        try:
            result = provider.get_live_load_results(
                case_name=case_name,
                result_type=result_type,
                ids=element_ids,
            )
            return str(result)
        except Exception as e:
            return f"Error getting live load results (获取移动荷载结果失败): {e}"
