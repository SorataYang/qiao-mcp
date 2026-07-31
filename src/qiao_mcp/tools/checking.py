"""
MCP Tools for structural concrete checking and reinforcement design.
结构混凝土检算与配筋设计工具
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError


def register_checking_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register structural checking MCP tools."""

    @mcp.tool()
    def setup_concrete_check(
        name: str,
        standard: int = 1,
        structure_type: int = 3,
        group_name: str = "默认结构组",
    ) -> str:
        """
        Create a concrete structural check case (创建混凝土检算工况).

        Args:
            name: Check case name (检算工况名称)
            standard: Design code (检算规范):
                1=JTG 3362-2018 (公路规范), 2=TB 10092-2017 (铁路规范)
            structure_type: Structural category (结构类型):
                1=钢筋混凝土 (RC), 2=B类预应力构件, 3=A类预应力构件, 4=全预应力构件
            group_name: Structure group name to check (检算的结构组名)
        """
        try:
            provider.add_concrete_check_case(
                name=name,
                standard=standard,
                structure_type=structure_type,
                group_name=group_name,
            )
            std_names = {1: "JTG 3362-2018(公路)", 2: "TB 10092-2017(铁路)"}
            struct_names = {1: "钢筋混凝土", 2: "B类预应力", 3: "A类预应力", 4: "全预应力"}
            return (
                f"Concrete check case '{name}' created: "
                f"{std_names.get(standard, standard)}, "
                f"{struct_names.get(structure_type, structure_type)}, "
                f"group='{group_name}' "
                f"(混凝土检算工况 '{name}' 创建成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting up concrete check (创建混凝土检算工况失败): {e}") from e

    @mcp.tool()
    def add_check_load_combination(
        name: str,
        standard: int = 1,
        kind: int = 3,
        load_case_factors: list[list] | None = None,
        combine_method: int = 1,
    ) -> str:
        """
        Add a load combination for structural checking (添加检算荷载组合).

        Args:
            name: Combination name (组合名称)
            standard: Code standard (规范): 1=JTG D60-2015, 2=TB 2017
            kind: Combination type (组合类型):
                Highway JTG D60: 1=基本组合, 2=偶然组合, 3=标准值组合,
                                 4=频遇组合, 5=准永久组合, 6=疲劳组合, 7=临时组合
                Railway TB 2017: 1=主力组合, 2=主加附组合, 3=主加特殊组合, 4=临时组合
            load_case_factors: Load case factors list, format:
                               [[case_name, unfavorable_factor, favorable_factor], ...]
                               荷载工况系数 [[工况名, 不利系数, 有利系数], ...]
            combine_method: Combination method (组合方式): 1=相加并判别, 2=包络
        """
        try:
            factors = load_case_factors or []
            factors_tuple = [(row[0], row[1], row[2]) for row in factors]
            provider.add_check_load_combine(
                name=name,
                standard=standard,
                combine_type=kind,
                combine_method=combine_method,
                combine_info=factors_tuple,
            )
            return (
                f"Load combination '{name}' added with {len(factors)} cases "
                f"(荷载组合 '{name}' 添加成功，包含 {len(factors)} 个工况)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding load combination (添加荷载组合失败): {e}") from e

    @mcp.tool()
    def run_concrete_check(
        name: str,
        max_wait_seconds: float | None = 1800.0,
    ) -> str:
        """
        Execute concrete structural checking analysis (运行混凝土检算).

        Syncs the named check case into the current check data, then runs the
        code-based verification and waits for the background task to finish.
        先将指定检算工况同步为当前检算数据，再运行规范验算并等待后台任务完成。

        Args:
            name: Check case name to run (要运行的检算工况名)
            max_wait_seconds: Max seconds to wait for completion; None = no limit
                              (最长等待秒数，None 表示不限时)
        """
        try:
            provider.solve_concrete_check(name=name, wait=True, max_wait=max_wait_seconds)
            return (
                f"Concrete check '{name}' completed. "
                f"Use get_check_results to retrieve results. "
                f"(混凝土检算 '{name}' 完成，使用 get_check_results 获取结果)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error running concrete check (运行混凝土检算失败): {e}") from e

    @mcp.tool()
    def add_parametric_reinforcement(
        section_id: int,
        position: int = 0,
        has_outer: bool = True,
        has_inner: bool = True,
        outer_rebar_info: list[list] | None = None,
        inner_rebar_info: list[list] | None = None,
    ) -> str:
        """
        Add parametric reinforcement to a concrete section (添加参数化配筋).

        Args:
            section_id: Section ID (截面ID)
            position: Section end (截面位置): 0=I端 (start), 1=J端 (end)
            has_outer: Has outer reinforcement (是否有外部钢筋)
            has_inner: Has inner reinforcement (是否有内部钢筋)
            outer_rebar_info: Outer rebar list (外部钢筋信息):
                              [[diameter, material_id, cover, spacing_or_count, bars_per_bundle], ...]
                              [[直径mm, 材料号, 层边距m, 间距m/数量, 每束根数], ...]
            inner_rebar_info: Inner rebar list (内部钢筋信息), same format as outer
        """
        try:
            kwargs: dict[str, Any] = {
                "sec_id": section_id,
                "position": position,
                "has_outer": has_outer,
                "has_inner": has_inner,
            }
            if outer_rebar_info:
                kwargs["outer_info"] = [tuple(r) for r in outer_rebar_info]
            if inner_rebar_info:
                kwargs["inner_info"] = [tuple(r) for r in inner_rebar_info]
            provider.add_parameter_reinforcement(**kwargs)
            return (
                f"Parametric reinforcement added to section {section_id} "
                f"({'I端' if position == 0 else 'J端'}) "
                f"(参数化配筋添加成功)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding reinforcement (添加配筋失败): {e}") from e

    @mcp.tool()
    def add_check_stirrup(
        stirrup_id: int,
        name: str,
        stirrup_type: int = 1,
        material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter: float = 0.020,
        spacing: float = 0.2,
        core_diameter: float = 0.0,
    ) -> str:
        """
        Add a stirrup definition for checking (添加检算箍筋定义).

        Args:
            stirrup_id: Stirrup definition ID (箍筋定义编号)
            name: Stirrup definition name (箍筋定义名称)
            stirrup_type: Stirrup type (箍筋类型): 1=普通箍筋 (normal), 2=螺旋式箍筋 (spiral)
            material_id: Rebar material ID (钢筋材料号)
            limbs_number: Number of limbs, for normal stirrups (普通箍筋肢数)
            loops_number: Number of loops, for spiral stirrups (螺旋式箍筋环数)
            diameter: Stirrup diameter in meters (箍筋直径, 单位 m, 如 0.020 = 20mm)
            spacing: Stirrup spacing in meters (箍筋间距, 单位 m)
            core_diameter: Core diameter for spiral stirrups in meters
                           (螺旋式箍筋核心直径, 单位 m, 仅螺旋箍筋使用)
        """
        try:
            provider.add_check_stirrup(
                stirrup_id=stirrup_id,
                name=name,
                stirrup_type=stirrup_type,
                rebar_material_id=material_id,
                limbs_number=limbs_number,
                loops_number=loops_number,
                diameter_m=diameter,
                spacing_m=spacing,
                core_diameter_m=core_diameter,
            )
            return f"Successfully added check stirrup '{name}' (成功添加检算箍筋)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding check stirrup (添加检算箍筋失败): {e}") from e

    @mcp.tool()
    def update_vertical_steel_tendon(
        limbs_number: int = 0,
        area: float = 0.000804,
        spacing: float = 0.2,
        effective_prestress: float = 800000000.0,
        fpd: float = 900000000.0,
    ) -> str:
        """
        Update vertical prestress tendon parameters for checking (修改竖向预应力钢束参数).

        Args:
            limbs_number: Number of vertical limbs/strands (竖向预应力肢数)
            area: Area of a single limb in m^2 (单肢面积, 单位 m², 如 0.000804 = 804mm²)
            spacing: Longitudinal spacing in meters (钢束间距, 单位 m)
            effective_prestress: Effective prestress in Pa (有效预应力, 单位 Pa, 8e8 = 800MPa)
            fpd: Design tensile strength in Pa (强度设计值 fpd, 单位 Pa, 9e8 = 900MPa)
        """
        try:
            provider.update_vertical_steel_tendon(
                limbs_number=limbs_number,
                area_m2=area,
                spacing_m=spacing,
                effective_prestress_pa=effective_prestress,
                fpd_pa=fpd,
            )
            return "Successfully updated vertical prestress tendon (成功修改竖向预应力钢束参数)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(
                f"Error updating vertical steel tendon (修改竖向预应力钢束参数失败): {e}"
            ) from e
