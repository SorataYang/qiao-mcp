"""
MCP Tools for prestress tendon operations.
预应力钢束操作工具

Provides tools for defining tendon properties, geometries,
and applying prestress forces.
"""

from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import (
    FiniteNumber,
    FourNumbers,
    NonnegativeNumber,
    SelectedIds,
    TendonNames,
    ThreeNumbers,
)


def register_tendon_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register tendon-related MCP tools."""

    @mcp.tool()
    def create_tendon_property(
        name: str,
        material_name: str,
        tendon_type: Literal[0, 1, 2] = 1,
        duct_type: Literal[1, 2, 3, 4, 5] = 1,
        steel_type: Literal[1, 2] = 1,
        area: float = 0.00139,
        duct_diameter: float = 0.10,
        friction: float = 0.25,
        deviation: float = 0.0015,
        anchorage_slip: float = 0.006,
        steel_detail: list[FiniteNumber] | None = None,
    ) -> str:
        """
        Create a tendon property definition (创建钢束特性).

        Args:
            name: Tendon property name (钢束特性名)
            material_name: Prestress steel material name, must exist
                           (钢材材料名，须已通过 create_material 创建)
            tendon_type: Tendon type (钢束类型): 0=pre-tension(先张),
                         1=post-tension(后张), 2=external(体外)
            duct_type: Duct type (孔道类型): 1=金属波纹管, 2=塑料波纹管,
                       3=铁皮管, 4=钢管, 5=抽芯成型
            steel_type: Steel type (钢材类型): 1=钢绞线(strand), 2=螺纹钢筋(threaded bar)
            area: Tendon area in m² (钢束面积), e.g. 0.00139 for 10Φ15.2 strands
            duct_diameter: Duct diameter in m (孔道直径)
            friction: Friction coefficient μ (摩阻系数), typically 0.20~0.30
            deviation: Wobble coefficient k (偏差系数), typically 0.0015
            anchorage_slip: Anchorage slip at each end in m (锚固滑移，两端相同), typ. 0.006
            steel_detail: Required for steel_type=2; otherwise an advanced override.
                          Raw qtmodel steel_detail list
                          (高级用法：直接给出原始 steel_detail 列表，覆盖上述四个参数；
                          钢绞线=[面积,孔道直径,摩阻,偏差]，
                          螺纹钢筋=[直径,面积,孔道直径,摩阻,偏差,张拉方式])
        """
        try:
            if steel_type == 2 and steel_detail is None:
                raise ToolInputError(
                    "steel_type=2 requires six steel_detail values "
                    "[diameter, area, duct diameter, friction, deviation, tension method] "
                    "(螺纹钢筋须提供六项 steel_detail，不能套用钢绞线四项默认值)"
                )
            detail = steel_detail if steel_detail is not None else [
                area, duct_diameter, friction, deviation
            ]
            expected = 4 if steel_type == 1 else 6
            if len(detail) != expected:
                raise ToolInputError(f"steel_type={steel_type} requires {expected} steel_detail values")
            if steel_type == 2 and detail[5] not in (1, 2):
                raise ToolInputError("Threaded-bar tension method must be 1 or 2 (张拉方式须为1或2)")
            provider.add_tendon_property(
                name=name,
                tendon_type=tendon_type,
                material_name=material_name,
                duct_type=duct_type,
                steel_type=steel_type,
                steel_detail=detail,
                slip_info=(anchorage_slip, anchorage_slip),
            )
            type_names = {0: "先张", 1: "后张", 2: "体外"}
            return (
                f"Tendon property '{name}' created (类型: {type_names.get(tendon_type, tendon_type)}) "
                f"(钢束特性 '{name}' 创建成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating tendon property (创建钢束特性失败): {e}") from e

    @mcp.tool()
    def create_tendon_2d(
        name: str,
        property_name: str,
        control_points: list[ThreeNumbers],
        point_insert: ThreeNumbers,
        num: int = 1,
        line_type: Literal[1, 2] = 1,
        position_type: Literal[1, 2] = 1,
        symmetry: Literal[0, 1, 2] = 2,
        group_name: str = "默认钢束组",
    ) -> str:
        """
        Create a 2D tendon defined by profile control points (创建2D钢束/平弯钢束).

        The tendon profile lies in the X-Z plane; each control point is
        [x, z, r] where r is the fillet radius (0 for sharp points).
        钢束线形位于XZ平面，控制点为 [x, z, r]，r为圆弧半径（0为折点）。

        Args:
            name: Tendon name (钢束名称)
            property_name: Tendon property name, must exist (钢束特性名，须已创建)
            control_points: Profile control points [[x, z, r], ...]
                            (控制点信息 [[x, z, 半径r], ...])
            point_insert: Exactly three values: [x,y,z] for straight positioning;
                for track positioning, [end, direction, element_id] where end is
                1=I or 2=J and direction is 1=I-to-J or 2=J-to-I
                (直线：[x,y,z]；轨迹：[插入端1/2,方向1/2,插入单元号])
            num: Number of tendons (根数)
            line_type: Point type (线型): 1=导线点(guide), 2=折线点(polyline)
            position_type: Positioning (定位方式): 1=straight(直线), 2=track line(轨迹线)
            symmetry: Symmetry point (对称点): 0=left end(左端), 1=right end(右端),
                      2=asymmetric(不对称)
            group_name: Tendon group name (钢束组名)

        Example:
            create_tendon_2d(name="T1", property_name="15-10",
                             control_points=[[0, -0.5, 0], [20, -1.2, 8], [40, -0.5, 0]],
                             point_insert=[0, 0, 0])
        """
        try:
            provider.add_tendon_2d(
                name=name,
                property_name=property_name,
                group_name=group_name,
                num=num,
                line_type=line_type,
                position_type=position_type,
                symmetry=symmetry,
                control_points=[tuple(pt) for pt in control_points],
                point_insert=tuple(point_insert),
            )
            return f"2D Tendon '{name}' created (2D钢束 '{name}' 创建成功)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating 2D tendon (创建2D钢束失败): {e}") from e

    @mcp.tool()
    def apply_prestress(
        case_name: str,
        tendon_name: TendonNames,
        force: NonnegativeNumber,
        tension_type: Literal[0, 1, 2] = 2,
        group_name: str = "",
    ) -> str:
        """
        Add prestress loading to named steel tendons (给钢束施加预应力荷载).

        Create tendon properties and geometry, the load case, and any named load group
        first. Use add_initial_tension_load for cable/truss initial axial force and
        add_cable_length_load for cable unstressed-length loading.
        This records a load; it does not solve or query prestress losses. The wrapper
        does not remove earlier prestress loads, and duplicate handling is determined
        by QiaoTong. Inspect get_model_data(kind="pre_stress_loads") before retrying
        instead of assuming the call is idempotent (先建钢束和工况；重试前查已有荷载).

        Args:
            case_name: Load case name for the prestress (预应力荷载工况名)
            tendon_name: Tendon name or list of tendon names (钢束名称或名称列表)
            force: Native prestress value, forwarded without conversion; the SDK
                does not declare a fixed unit here. Verify using QiaoTong's
                prestress definition/export (原生预应力值，不换算；单位须按桥通核验)
            tension_type: Tension end (张拉方式): 0=start(始端), 1=end(末端), 2=both(两端)
            group_name: Load group name (荷载组名)

        Returns:
            Summary of requested force, tendon count and case. Run analysis before
            get_tendon_loss_results; successful load creation alone supplies no losses.
        """
        try:
            names = [tendon_name] if isinstance(tendon_name, str) else tendon_name
            if not case_name.strip() or not names or any(not name.strip() for name in names):
                raise ToolInputError("Provide a load case and at least one nonempty tendon name")
            kwargs: dict[str, Any] = {"tension_type": tension_type}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_pre_stress(
                case_name=case_name, tendon_name=tendon_name, force=force, **kwargs
            )
            count = 1 if isinstance(tendon_name, str) else len(tendon_name)
            return (
                f"Prestress value {force} (native units) applied to {count} tendon(s) "
                f"in case '{case_name}' "
                f"(预应力原生值 {force} 已施加到 {count} 根钢束)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error applying prestress (施加预应力失败): {e}") from e

    @mcp.tool()
    def get_tendon_info(
        tendon_name: str = "",
    ) -> str:
        """
        Read saved tendon definitions, filtered by exact name or all names
        (按完整名称读取钢束定义，或读取全部钢束).

        Use get_tendon_loss_results for a stage's computed stress/loss distribution
        and get_tendon_position_result for discretized coordinates. This queries
        model data and never solves. Returns a message containing native records;
        a missing requested name returns a not-found message, not an MCP error.
        Any loss-related definition fields are not a substitute for stage results.
        (定义查询不求解；阶段损失和离散坐标分别用上述结果工具，未找到名称返回提示消息。)

        Args:
            tendon_name: Specific tendon name, or empty string for all tendons
                         (钢束名称，空字符串则返回所有钢束)
        """
        try:
            tendon_data = provider.get_tendon_data()
            if tendon_name:
                filtered = [t for t in tendon_data if t.get("name") == tendon_name]
                if not filtered:
                    return f"Tendon '{tendon_name}' not found (未找到钢束 '{tendon_name}')"
                return f"Tendon info (钢束信息): {filtered}"
            return (
                f"Total {len(tendon_data)} tendon(s) (共 {len(tendon_data)} 根钢束):\n"
                + "\n".join(str(t) for t in tendon_data)
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting tendon info (获取钢束信息失败): {e}") from e

    @mcp.tool()
    def add_tendon_3d(
        name: str,
        property_name: str,
        control_points: list[FourNumbers],
        point_insert: ThreeNumbers,
        num: int = 1,
        line_type: Literal[1, 2] = 1,
        position_type: Literal[1, 2] = 1,
        group_name: str = "默认钢束组",
    ) -> str:
        """
        Define a spatial tendon using ordered three-dimensional control points
        (用有序三维控制点定义空间钢束).

        Create the material and create_tendon_property first; property_name must
        name an existing tendon property. Use create_tendon_2d for a planar tendon
        profile. This tool defines geometry; apply_prestress adds the later load,
        and update_vertical_steel_tendon changes checking parameters instead.

        Every control point is [x, y, z, fillet_radius] and order is preserved.
        position_type changes the meaning of point_insert: straight positioning
        takes three coordinates, while track positioning takes end, direction
        and a real element ID. Use the bridge's coordinate and length convention;
        the wrapper performs no geometric or unit conversion.

        Writes the full definition and refreshes the model. A repeated name can
        replace an existing tendon, so read get_tendon_info before editing it.
        Returns a confirmation with the name, not discretized tendon positions or
        prestress results. (空间几何定义与施加预应力分开；重名可能覆盖，点序和单位原样提交。)

        Args:
            name: Tendon name (钢束名称)
            property_name: Tendon property name, must exist (钢束特性名，须已创建)
            control_points: 3D control points [[x, y, z, r], ...], r = fillet radius
                            (三维控制点 [[x, y, z, 半径r], ...])
            point_insert: Exactly three values: [x,y,z] for straight positioning;
                for track positioning, [end, direction, element_id] where end is
                1=I or 2=J and direction is 1=I-to-J or 2=J-to-I
                (直线：[x,y,z]；轨迹：[插入端1/2,方向1/2,插入单元号])
            num: Number of tendons (钢束根数)
            line_type: Point type (线型): 1=导线点(guide), 2=折线点(polyline)
            position_type: Positioning (定位方式): 1=straight(直线), 2=track line(轨迹线)
            group_name: Tendon group name (钢束组名)
        """
        try:
            provider.add_tendon_3d(
                name=name,
                property_name=property_name,
                group_name=group_name,
                num=num,
                line_type=line_type,
                position_type=position_type,
                control_points=[tuple(pt) for pt in control_points],
                point_insert=tuple(point_insert),
            )
            return f"Successfully added 3D tendon '{name}' (成功添加三维钢束)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding 3D tendon (添加三维钢束失败): {e}") from e

    @mcp.tool()
    def assign_tendon_elements(ids: SelectedIds) -> str:
        """
        Declare which elements contain tendons, i.e. are prestressed-concrete
        members (标记预应力单元：声明哪些单元内有钢束穿过).

        Despite the name, this does NOT bind elements to one particular tendon:
        the underlying qtmodel API takes element IDs only, no tendon name. It is
        a model-wide declaration so tendon area and prestress losses are
        accounted for in those elements.

        Ordering: create tendons (create_tendon_2d / add_tendon_3d) → call this
        ONCE with the union of every element any tendon passes through →
        apply_prestress. Writes to the model and refreshes it; not a query.

        (不把单元绑定到某根钢束——底层 API 只收单元号、不收钢束名，属全模型级声明，
        使这些单元计入钢束面积与预应力损失。顺序：先建钢束 → 一次性传入所有钢束
        经过的单元并集 → 再施加预应力。写模型并刷新，非查询。)

        Returns a confirmation. The SDK does not specify whether repeated
        declarations merge or replace membership; do not use repeated calls
        as a per-tendon incremental assignment. Verify the declaration in
        the bridge before repeating a call whose outcome is uncertain.

        Args:
            ids: IDs of the elements that tendons pass through — int, list, or
                 "XtoYbyN" range string, e.g. "1to10 15to62 236to293"
                 (有钢束穿过的单元编号；支持整数、列表或 "XtoYbyN" 范围字符串)
        """
        try:
            provider.add_tendon_elements(ids=ids)
            return (
                f"Elements {ids} marked as containing tendons "
                f"(已将单元 {ids} 标记为预应力单元)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error assigning tendon elements (分配单元失败): {e}") from e

    @mcp.tool()
    def get_tendon_loss_results(name: str, stage_id: int = 1) -> str:
        """
        Get prestress-loss distribution along one tendon at one construction
        stage (获取一根钢束在指定施工阶段的应力/损失分布).

        Read-only: it does not change the model. Returns a message containing
        the native list of points along
        the tendon / its host beam, each with tendon_name, beam_id, position,
        effective_s (effective stress), instance_s (instantaneous stress),
        except_s (target / control stress) and ratio (effective-stress ratio).
        Stress units follow the current project unit system. An empty list
        means the name did not match or that stage has no results.

        Preconditions: the tendon must exist, the named stage must have
        activated it, and a construction-stage analysis must already have been
        run (run_analysis after configure_analysis(do_construction_stage=True)).

        When to use vs. siblings: loss distribution at a stage here; geometry
        and saved definitions → get_tendon_info; coordinates along the
        tendon → get_tendon_position_result; unstressed length →
        get_tendon_length_result.

        (只读，不改模型。返回消息内包含沿钢束/所属梁单元分点的原生列表，每项含 tendon_name、
        beam_id、position、effective_s(有效应力)、instance_s(瞬时应力)、
        except_s(期望/控制应力)、ratio(有效应力比)。应力量纲跟随当前工程单位制。
        空列表表示未匹配到钢束或该阶段无结果。前置：钢束须存在、该阶段须已激活
        此钢束、且已跑过施工阶段分析。选型：某阶段的损失分布用本工具；保存的几何
        定义用 get_tendon_info；沿程坐标用 get_tendon_position_result；无应力长度
        用 get_tendon_length_result。)

        Args:
            name: Tendon name, must match the model exactly (钢束名，须与模型中完全一致)
            stage_id: Construction stage number, starting from 1 (施工阶段编号，从 1 开始)
        """
        try:
            data = provider.get_tendon_loss_results(name=name, stage_id=stage_id)
            return f"Tendon '{name}' loss results for stage {stage_id}:\n{data}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting tendon loss results (获取预应力损失结果失败): {e}") from e

    @mcp.tool()
    def get_tendon_position_result(name: str) -> str:
        """
        Read the bridge's discretized global coordinates for one tendon
        (读取一根钢束离散后的全局坐标).

        Use this to inspect the resulting tendon path; get_tendon_info reads
        saved tendon definitions, while get_tendon_loss_results reads stress
        and loss distributions. Requires an existing tendon and permission to
        read results. It never starts analysis or changes the model. Whether
        coordinates are available before a solve depends on the bridge.
        (核对离散钢束路径用本工具；定义用 get_tendon_info，应力/损失用
        get_tendon_loss_results。受结果读取权限约束，不自动求解。)

        Returns a message containing the native point list in tendon order.
        The SDK documents either [x,y,z] rows or {item1,item2,item3} objects,
        in global coordinates and the current model length unit. Empty data
        alone does not distinguish a missing name from unavailable geometry;
        check the definition and bridge state before retrying.

        Args:
            name: Exact, nonempty name of the existing tendon (已有钢束的完整非空名称)
        """
        try:
            data = provider.get_tendon_position_result(name=name)
            return f"Tendon '{name}' position results:\n{data}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting tendon position (获取钢束坐标结果失败): {e}") from e

    @mcp.tool()
    def get_tendon_length_result() -> str:
        """
        Get all tendon length results (获取所有钢束长度结果).
        """
        try:
            data = provider.get_tendon_length_result()
            return f"Tendon length results:\n{data}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error getting tendon lengths (获取钢束长度结果失败): {e}") from e
