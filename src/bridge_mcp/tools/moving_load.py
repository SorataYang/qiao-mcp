"""
MCP Tools for moving load analysis.
移动荷载工具

Provides tools for defining standard vehicles, traffic lanes,
and live load cases for highway and railway bridges.
"""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_moving_load_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register moving load MCP tools."""

    @mcp.tool()
    def add_standard_vehicle(
        name: str,
        vehicle_type: int = 1,
        standard: int = 1,
    ) -> str:
        """
        Add a standard vehicle load from design code database (添加标准车辆荷载).

        Uses vehicle data from Chinese highway and railway design codes.
        使用中国公路和铁路设计规范中的标准车辆模型。

        Args:
            name: Vehicle name (车辆名称)
            vehicle_type: Vehicle type index (车辆类型序号，从1开始按规范排序)
                Highway (公路, standard=1): 1=汽车荷载车队, 2=平板挂车, etc.
                Railway (铁路, standard=2): 1=ZK活载, 2=ZC活载, etc.
            standard: Code standard (规范): 1=JTG D60公路规范, 2=TB 10002铁路规范
        """
        try:
            provider.add_standard_vehicle(
                name=name, vehicle_type=vehicle_type, standard=standard
            )
            std_name = "公路规范JTG D60" if standard == 1 else "铁路规范TB 10002"
            return (
                f"Standard vehicle '{name}' added from {std_name} type {vehicle_type} "
                f"(标准车辆 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error adding standard vehicle (添加标准车辆失败): {e}"

    @mcp.tool()
    def add_traffic_lane(
        name: str,
        lane_width: float = 3.75,
        lateral_offset: float = 0.0,
        element_ids: list[int] | str = "",
    ) -> str:
        """
        Define a traffic lane for moving load analysis (定义行车道).

        Args:
            name: Lane name (行车道名称)
            lane_width: Lane width in meters (车道宽度，单位m), typical 3.5~4.0m
            lateral_offset: Lateral offset from reference line in meters
                            (相对参考轴的横向偏移，单位m)
            element_ids: Element IDs that form the lane (行车道所经过的单元编号)
        """
        try:
            provider.add_lane(
                name=name,
                lane_width=lane_width,
                lateral_offset=lateral_offset,
                element_ids=element_ids,
            )
            return (
                f"Traffic lane '{name}' defined (width={lane_width}m) "
                f"(行车道 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error defining traffic lane (定义行车道失败): {e}"

    @mcp.tool()
    def create_live_load_case(
        name: str,
        vehicle_names: list[str],
        lane_names: list[str],
        load_factor: float = 1.0,
        impact_factor: float = 1.0,
    ) -> str:
        """
        Create a moving live load case combining vehicles and lanes (创建移动荷载工况).

        The analysis engine will automatically find the worst-case vehicle positions
        for maximum/minimum effects (分析引擎自动计算最不利车辆位置，得到最大/最小效应包络).

        Args:
            name: Load case name (荷载工况名)
            vehicle_names: List of vehicle names to apply (车辆名称列表)
            lane_names: List of lane names to load (车道名称列表)
            load_factor: Vehicle load factor (车辆荷载系数), default 1.0
            impact_factor: Dynamic impact factor (冲击系数/动力放大系数), default 1.0
        """
        try:
            provider.add_live_load_case(
                name=name,
                vehicle_names=vehicle_names,
                lane_names=lane_names,
                load_factor=load_factor,
                impact_factor=impact_factor,
            )
            return (
                f"Live load case '{name}' created: {len(vehicle_names)} vehicle(s) "
                f"on {len(lane_names)} lane(s) "
                f"(移动荷载工况 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error creating live load case (创建移动荷载工况失败): {e}"

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
            case_name: Live load case name (移动荷载工况名)
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
