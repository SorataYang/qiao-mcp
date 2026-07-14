"""
MCP Tools for prestress tendon operations.
预应力钢束操作工具

Provides tools for defining tendon properties, geometries,
and applying prestress forces.
"""

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError


def register_tendon_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register tendon-related MCP tools."""

    @mcp.tool()
    def create_tendon_property(
        name: str,
        material_name: str,
        tendon_type: int = 1,
        duct_type: int = 1,
        steel_type: int = 1,
        area: float = 0.00139,
        duct_diameter: float = 0.10,
        friction: float = 0.25,
        deviation: float = 0.0015,
        anchorage_slip: float = 0.006,
        steel_detail: list[float] | None = None,
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
            steel_detail: Advanced override, raw qtmodel steel_detail list
                          (高级用法：直接给出原始 steel_detail 列表，覆盖上述四个参数；
                          钢绞线=[面积,孔道直径,摩阻,偏差]，
                          螺纹钢筋=[直径,面积,孔道直径,摩阻,偏差,张拉方式])
        """
        try:
            detail = steel_detail if steel_detail is not None else [
                area, duct_diameter, friction, deviation
            ]
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
        control_points: list[list[float]],
        point_insert: list[float],
        num: int = 1,
        line_type: int = 1,
        position_type: int = 1,
        symmetry: int = 2,
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
            point_insert: Insertion point [x, y, z] for straight positioning
                          (直线定位时的插入点坐标 [x, y, z])
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
        tendon_name: str | list[str],
        force: float,
        tension_type: int = 2,
        group_name: str = "",
    ) -> str:
        """
        Apply prestress force to tendon(s) (施加预应力).

        Args:
            case_name: Load case name for the prestress (预应力荷载工况名)
            tendon_name: Tendon name or list of tendon names (钢束名称或名称列表)
            force: Prestress force in N (预应力张拉力，单位N), e.g. 3000000 = 3000kN
            tension_type: Tension end (张拉方式): 0=start(始端), 1=end(末端), 2=both(两端)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs = {"tension_type": tension_type}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_pre_stress(
                case_name=case_name, tendon_name=tendon_name, force=force, **kwargs
            )
            count = 1 if isinstance(tendon_name, str) else len(tendon_name)
            return (
                f"Prestress {force/1000:.0f}kN applied to {count} tendon(s) "
                f"in case '{case_name}' "
                f"(预应力 {force/1000:.0f}kN 已施加到 {count} 根钢束)"
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
        Get tendon geometry and prestress loss results (获取钢束信息与损失结果).

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
        control_points: list[list[float]],
        point_insert: list[float],
        num: int = 1,
        line_type: int = 1,
        position_type: int = 1,
        group_name: str = "默认钢束组",
    ) -> str:
        """
        Add a 3D tendon (添加三维钢束/空间钢束).

        Args:
            name: Tendon name (钢束名称)
            property_name: Tendon property name, must exist (钢束特性名，须已创建)
            control_points: 3D control points [[x, y, z, r], ...], r = fillet radius
                            (三维控制点 [[x, y, z, 半径r], ...])
            point_insert: Insertion point [x, y, z] for straight positioning
                          (直线定位时的插入点坐标)
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
    def assign_tendon_elements(ids: int | list[int] | str) -> str:
        """
        Assign elements to a tendon (为钢束分配单元).

        Args:
            ids: Element IDs (单元编号)
        """
        try:
            provider.add_tendon_elements(ids=ids)
            return f"Successfully assigned elements {ids} to tendon (成功为钢束分配单元)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error assigning tendon elements (分配单元失败): {e}") from e

    @mcp.tool()
    def get_tendon_loss_results(name: str, stage_id: int = 1) -> str:
        """
        Get tendon prestress loss results (获取预应力损失结果).

        Args:
            name: Tendon name (钢束名)
            stage_id: Construction stage ID (施工阶段编号)
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
        Get tendon position/coordinate results (获取钢束坐标结果).

        Args:
            name: Tendon name (钢束名)
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
