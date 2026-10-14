"""
MCP Tools for moving load analysis.
移动荷载工具

Provides tools for the complete qtmodel live-load workflow:
node tandems (节点纵列) → influence planes (影响面) → lane lines (车道线)
→ standard vehicles (标准车辆) → live load cases (活载工况).
"""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import StrictBool, TypeAdapter

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.live_load_schemas import LiveLoadCaseNames, LiveLoadSubCases, LiveLoadSystem
from qiao_mcp.tools.schemas import MessageResult

_SUB_CASE_ADAPTER = TypeAdapter(LiveLoadSubCases)


def register_moving_load_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register moving load MCP tools."""

    @mcp.tool()
    def configure_live_load_system(
        system: LiveLoadSystem, clear_existing: StrictBool = False,
    ) -> MessageResult:
        """Explicitly select the bridge live-load system (选择活载体系).

        Existing incompatible definitions can block a switch. Set clear_existing
        only when the user chose to delete those definitions; references in
        combinations/operation settings may still block deletion. Never retry a
        rejected switch with clearing enabled automatically. Does not run analysis.

        Args:
            system: china_longitudinal=中国纵向, aashto=AASHTO,
                china_transversal=中国横向, bs=BS, en1991=EN1991.
            clear_existing: Explicitly allow clearing old live-load definitions
                during the switch (允许清理旧活载；默认 False).
        """
        try:
            provider.configure_live_load_system(system, clear_existing=clear_existing)
            return MessageResult(status="success", message=f"Live-load system set to {system} (活载体系已设置)")
        except Exception as exc:
            raise ToolError(f"Error configuring live-load system (设置活载体系失败): {exc}") from exc

    @mcp.tool()
    def configure_operation_stage(
        final_stage: str,
        static_load_cases: LiveLoadCaseNames,
        sink_load_cases: LiveLoadCaseNames,
        live_load_cases: LiveLoadCaseNames,
        transversal_load_cases: LiveLoadCaseNames,
        do_analysis: StrictBool = True,
    ) -> MessageResult:
        """Replace all operation-stage analysis selections (完整设置运营阶段).

        Each case list is required: [] disables that family. Read the current
        analysis_context first and include every family that should remain
        enabled. Names must match existing definitions. This only commits settings;
        use run_analysis separately to solve. It does not switch the displayed stage.

        Args:
            final_stage: Exact final construction-stage name to inherit; an empty
                string delegates stage selection to QiaoTong (最终施工阶段名).
            static_load_cases: Complete ordinary static case names; [] disables (静力工况).
            sink_load_cases: Complete settlement case names; [] disables (沉降工况).
            live_load_cases: Complete longitudinal/influence-plane live-load case
                names; [] disables (纵向活载工况).
            transversal_load_cases: Complete transversal case names; [] disables (横向工况).
            do_analysis: Whether operation-stage analysis is enabled (是否计算运营阶段).
        """
        try:
            provider.configure_operation_stage(
                final_stage=final_stage, static_load_cases=static_load_cases,
                sink_load_cases=sink_load_cases, live_load_cases=live_load_cases,
                transversal_load_cases=transversal_load_cases, do_analysis=do_analysis,
            )
            return MessageResult(status="success", message="Operation-stage selections replaced (运营阶段设置已完整替换)")
        except Exception as exc:
            raise ToolError(f"Error configuring operation stage (设置运营阶段失败): {exc}") from exc

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding node tandem (添加节点纵列失败): {e}") from e

    @mcp.tool()
    def add_influence_plane(
        name: str,
        tandem_names: list[str],
        always_divided_by_beam_shape: bool | None = None,
    ) -> str:
        """
        Define an influence plane from node tandems (添加影响面).

        STEP 2 of the moving load workflow. The influence plane is built
        from one or more node tandems and is required by lanes and load cases.

        Create the referenced tandems with add_node_tandem first. This defines
        the supporting influence-plane geometry; add_traffic_lane places a lane
        on it, and create_live_load_case selects vehicles and lanes for analysis.
        It does not calculate influence ordinates or create vehicles.

        tandem_names contains existing tandem names in the intended plane order.
        The optional beam-shape division setting is omitted when None; explicitly
        setting it requires SDK support. Writes and refreshes the model and
        returns the requested plane name. Reference validation and repeated-name
        handling belong to the bridge; verify the plane before building lanes.
        (先建节点纵列，再建影响面与车道；这里只写定义，不计算影响值。)

        Args:
            name: Influence plane name (影响面名称, e.g. "影响面1")
            tandem_names: Node tandem names (节点纵列名称列表)
            always_divided_by_beam_shape: Always divide by beam shape. None keeps the
                                         upstream default (False); explicit values
                                         require a supporting qtmodel build
                                         (是否始终按梁形划分；省略保持默认，需新版)
        """
        try:
            kwargs: dict[str, Any] = {}
            if always_divided_by_beam_shape is not None:
                kwargs["always_divided_by_beam_shape"] = always_divided_by_beam_shape
            provider.add_influence_plane(name=name, tandem_names=tandem_names, **kwargs)
            return f"Influence plane '{name}' created (影响面 '{name}' 创建成功)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding influence plane (添加影响面失败): {e}") from e

    @mcp.tool()
    def add_traffic_lane(
        name: str,
        influence_name: str,
        tandem_name: str,
        offset: float = 0.0,
        lane_width: float = 3.1,
        optimize: bool = False,
        direction: Literal[0, 1] = 0,
    ) -> str:
        """
        Define a traffic lane line for moving load analysis (添加车道线).

        STEP 3 of the moving load workflow. Requires an influence plane
        and a node tandem created beforehand.

        Use for an ordinary moving-load lane tied to an influence plane. A
        transversal lane uses set_transversal_lane; an international planned lane
        uses set_planned_lane and a separate namespace. This tool does not create
        a vehicle, a live-load case or a structural beam element.

        influence_name and tandem_name must reference existing definitions.
        offset locates the lane laterally from its tandem, while lane_width is
        its width; both use meters. optimize enables lateral vehicle wandering,
        and direction reverses travel along the same lane definition.

        Writes and refreshes the model and returns the lane/plane summary.
        Use the lane in create_live_load_case afterwards, then configure and run
        analysis separately. Duplicate-name and reference handling are backend-owned.
        (普通移动荷载车道与横向/国际拟定车道分开；偏移和宽度用米，定义后另建活载工况。)

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error defining traffic lane (添加车道线失败): {e}") from e

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

        Use for a vehicle or lane-load template provided by the bridge's listed
        Chinese design-code database. set_international_vehicle and
        create_en1991_vehicle define international families; set_transversal_vehicle
        defines transversal vehicles. These use different schemas and namespaces.

        standard_code selects the database and load_type must match an actual
        entry in that code's desktop UI. load_length and factor are specialized
        railway options, not universal vehicle geometry or axle-scale controls.
        The wrapper forwards the selection; it does not synthesize missing templates.

        Writes and refreshes the model, returning a definition summary. The vehicle
        is not placed on a lane or solved here: reference it in create_live_load_case
        with the previously created plane/lanes. Inspect definitions before reusing
        a name because duplicate and unsupported-template handling belongs to the bridge.
        (规范与荷载类型须匹配界面数据库；车辆定义、车道组合和求解分别执行。)

        Args:
            name: Vehicle name (车辆荷载名称)
            standard_code: Design code (荷载规范):
                1=铁路桥涵规范 TB10002-2017, 2=城市桥梁 CJJ11-2019,
                3=公路工程技术标准 JTJ 001-97, 4=公路桥涵通规 JTG D60-2004,
                5=公路桥涵通规 JTG D60-2015, 6=城市轨道交通 GB/T51234-2017,
                7=市域铁路 T/CRS C0101-2017
            load_type: Load type name exactly as shown in the QiaoTong UI
                       (荷载类型，与软件界面名称一致), e.g. "公路I级车道" (公路通规),
                       "ZK高速铁路" (铁路规范 TB10002-2017)
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding standard vehicle (添加标准车辆失败): {e}") from e

    @mcp.tool()
    def create_live_load_case(
        name: str,
        influence_plane: str,
        span: float,
        sub_cases: LiveLoadSubCases,
        sub_case_optimized: list[StrictBool] | None = None,
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
            sub_case_optimized: Optimization flag for each sub-case, in the same order
                                and with exactly the same length as sub_cases. None
                                keeps legacy behavior; explicit lists require a
                                supporting qtmodel build (各子工况优化标志，等长布尔列表，需新版)

        Example:
            create_live_load_case(name="活载工况1", influence_plane="影响面1", span=100,
                                  sub_cases=[["公路I级", 1.0, ["车道1", "车道2"]]])
        """
        try:
            kwargs: dict[str, Any] = {}
            if sub_case_optimized is not None:
                if len(sub_case_optimized) != len(sub_cases):
                    raise ToolInputError(
                        "sub_case_optimized must have the same length as sub_cases "
                        "(子工况优化标志数量必须与子工况一致)"
                    )
                kwargs["sub_case_optimized"] = sub_case_optimized
            try:
                formatted = _SUB_CASE_ADAPTER.validate_python(sub_cases)
            except ValueError as exc:
                raise ToolInputError(
                    "sub_cases requires [vehicle_name, factor, [lane names...]] rows "
                    "(子工况必须为三列，车道必须为名称列表)"
                ) from exc
            provider.add_live_load_case(
                name=name,
                influence_plane=influence_plane,
                span=span,
                sub_case=formatted,
                **kwargs,
            )
            return (
                f"Live load case '{name}' created on plane '{influence_plane}' "
                f"with {len(formatted)} sub-case(s) (活载工况 '{name}' 创建成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating live load case (创建活载工况失败): {e}") from e

    @mcp.tool()
    def get_live_load_results(
        case_name: str,
        result_type: Literal["force", "stress", "deformation"] = "force",
        element_ids: list[int] | str = "",
        envelope_type: Literal[1, 2] = 1,
    ) -> str:
        """
        Get moving load analysis results (获取移动荷载分析结果).

        Queries operating-stage results for one extreme at a time. The default
        is maximum; request envelope_type=2 separately for minimum. The case name
        is passed verbatim: obtain its complete result name from verified model
        data. This tool neither prefixes a case name nor runs analysis.
        查询运营阶段已求解结果；默认最大值，最小值须单独指定2；工况全名原样传入。

        Use after a moving-load case has been included in operating-stage
        configuration and successfully solved. get_analysis_results serves the
        general result interface; get_transversal_data and
        get_international_live_load_data read definitions rather than results.

        result_type determines the selection namespace: element_ids selects
        elements for force/stress but nodes for deformation. The empty string
        requests all IDs. There is no pagination, and each call returns only the
        selected maximum or minimum extreme, not both envelope sides together.

        Read-only: returns the native result as text without changing the view,
        refreshing the model, converting units or filling missing values. An
        unavailable/empty result needs a check of the solved case and identifiers,
        not an automatic rerun or guessed case prefix.
        (变形查询使用节点号；单次只有一侧极值，空选择查全部，返回原生数据且不补造缺失值。)

        Args:
            case_name: Complete live-load result case name (活载结果工况全名)
            result_type: Result type (结果类型): 'force'(内力), 'stress'(应力), 'deformation'(变形)
            element_ids: Element IDs for force/stress, node IDs for deformation;
                empty string queries all IDs (内力/应力用单元号，变形用节点号；空串查询全部)
            envelope_type: Extreme to request: 1=maximum, 2=minimum
                (单次查询的极值：1最大、2最小)
        """
        try:
            result = provider.get_live_load_results(
                case_name=case_name,
                result_type=result_type,
                ids=element_ids,
                envelope_type=envelope_type,
            )
            return str(result)
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting live load results (获取移动荷载结果失败): {e}") from e
