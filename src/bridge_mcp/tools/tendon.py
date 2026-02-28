"""
MCP Tools for prestress tendon operations.
预应力钢束操作工具

Provides tools for defining tendon properties, geometries,
and applying prestress forces.
"""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_tendon_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register tendon-related MCP tools."""

    @mcp.tool()
    def create_tendon_property(
        name: str,
        tendon_type: int = 1,
        elastic_modulus: float = 1.95e11,
        area: float = 0.0,
        friction: float = 0.25,
        deviation: float = 0.003,
        anchorage_loss: float = 0.006,
    ) -> str:
        """
        Create a tendon property definition (创建钢束特性).

        Args:
            name: Tendon property name (钢束特性名)
            tendon_type: Tendon type (钢束类型): 1=post-tension(后张法), 2=pre-tension(先张法)
            elastic_modulus: Elastic modulus in Pa (弹性模量，单位Pa), e.g. 1.95e11
            area: Cross-section area in m² (截面面积，单位m²), e.g. 0.00139 for 15Φ5钢绞线
            friction: Friction coefficient μ (摩擦系数μ), typically 0.20~0.30
            deviation: Wobble friction coefficient k (偏差系数k), typically 0.001~0.005
            anchorage_loss: Anchorage set loss in m (锚固损失，单位m), typically 0.006
        """
        try:
            provider.add_tendon_property(
                name=name,
                tendon_type=tendon_type,
                elastic_modulus=elastic_modulus,
                area=area,
                friction=friction,
                deviation=deviation,
                anchorage_loss=anchorage_loss,
            )
            return (
                f"Tendon property '{name}' created (类型: {'后张法' if tendon_type == 1 else '先张法'}) "
                f"(钢束特性 '{name}' 创建成功)"
            )
        except Exception as e:
            return f"Error creating tendon property (创建钢束特性失败): {e}"

    @mcp.tool()
    def create_tendon_2d(
        name: str,
        property_name: str,
        element_ids: list[int] | str,
        control_points: list[list[float]],
        tension_type: int = 3,
        group_name: str = "",
    ) -> str:
        """
        Create a 2D tendon by specifying control points along elements (创建2D钢束).

        A 2D tendon lies in the X-Y plane of members and is defined by relative
        control points (x, y) measured from element-local coordinates.
        2D钢束在构件XY平面内，通过相对bei控制点定义钢束走线。

        Args:
            name: Tendon name (钢束名称)
            property_name: Tendon property name (钢束特性名)
            element_ids: List of element IDs the tendon passes through (钢束所经过的单元编号)
            control_points: Control point list, format [[x, y], ...] in local element
                            coordinates (控制点列表，格式[[截面位置x, 偏心y],...])
                            x is relative position 0-1 along element (x为沿单元长度的相对位置0-1)
                            y is eccentricity in meters (y为偏心距，单位m)
            tension_type: Tension method (张拉方式): 1=jack-start(始端张拉), 2=jack-end(终端张拉),
                          3=both-ends(两端张拉)
            group_name: Load group name (荷载组名)
        """
        try:
            kwargs = {}
            if group_name:
                kwargs["group_name"] = group_name
            provider.add_tendon_2d(
                name=name,
                property_name=property_name,
                element_ids=element_ids,
                control_points=control_points,
                tension_type=tension_type,
                **kwargs,
            )
            return f"2D Tendon '{name}' created (2D钢束 '{name}' 创建成功)"
        except Exception as e:
            return f"Error creating 2D tendon (创建2D钢束失败): {e}"

    @mcp.tool()
    def apply_prestress(
        case_name: str,
        tendon_name: str | list[str],
        force: float,
        group_name: str = "",
    ) -> str:
        """
        Apply prestress force to tendon(s) (施加预应力).

        Args:
            case_name: Load case name for the prestress (预应力荷载工况名)
            tendon_name: Tendon name or list of tendon names (钢束名称或名称列表)
            force: Prestress force in N (预应力张拉力，单位N), e.g. 3000000 = 3000kN
            group_name: Load group name (荷载组名)
        """
        try:
            names = [tendon_name] if isinstance(tendon_name, str) else tendon_name
            kwargs = {}
            if group_name:
                kwargs["group_name"] = group_name
            for tn in names:
                provider.add_pre_stress(
                    case_name=case_name, tendon_name=tn, force=force, **kwargs
                )
            return (
                f"Prestress {force/1000:.0f}kN applied to {len(names)} tendon(s) "
                f"in case '{case_name}' "
                f"(预应力 {force/1000:.0f}kN 已施加到 {len(names)} 根钢束)"
            )
        except Exception as e:
            return f"Error applying prestress (施加预应力失败): {e}"

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
        except Exception as e:
            return f"Error getting tendon info (获取钢束信息失败): {e}"
