"""
MCP Tools for structural concrete checking and reinforcement design.
结构混凝土检算与配筋设计工具
"""

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


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
        except Exception as e:
            return f"Error setting up concrete check (创建混凝土检算工况失败): {e}"

    @mcp.tool()
    def add_check_load_combination(
        name: str,
        standard: int = 1,
        kind: int = 3,
        load_case_factors: list[list] | None = None,
        combine_type: int = 1,
    ) -> str:
        """
        Add a load combination for structural checking (添加检算荷载组合).

        Args:
            name: Combination name (组合名称)
            standard: Code standard (规范): 1=JTG D60-2015, 2=TB 10002-2017
            kind: Combination type (组合类型):
                Highway JTG D60: 1=基本组合, 2=偶然组合, 3=标准值组合,
                                 4=频遇组合, 5=准永久组合
                Railway TB 10002: 1=主力组合, 2=主加附组合, 3=主加特殊组合
            load_case_factors: Load case factors list, format:
                               [[case_name, unfavorable_factor, favorable_factor], ...]
                               荷载工况系数 [[工况名, 不利系数, 有利系数], ...]
            combine_type: Combination method (组合方式): 1=叠加判别, 2=包络
        """
        try:
            factors = load_case_factors or []
            factors_tuple = [(row[0], row[1], row[2]) for row in factors]
            provider.add_check_load_combine(
                name=name,
                standard=standard,
                kind=kind,
                combine_type=combine_type,
                combine_info=factors_tuple,
            )
            return (
                f"Load combination '{name}' added with {len(factors)} cases "
                f"(荷载组合 '{name}' 添加成功，包含 {len(factors)} 个工况)"
            )
        except Exception as e:
            return f"Error adding load combination (添加荷载组合失败): {e}"

    @mcp.tool()
    def run_concrete_check(
        name: str,
    ) -> str:
        """
        Execute concrete structural checking analysis (运行混凝土检算).

        Runs the code-based verification for the specified check case.
        对指定的检算工况运行规范验算。

        Args:
            name: Check case name to run (要运行的检算工况名)
        """
        try:
            provider.solve_concrete_check(name=name)
            return (
                f"Concrete check '{name}' completed. "
                f"Use get_check_results to retrieve results. "
                f"(混凝土检算 '{name}' 完成，使用 get_check_results 获取结果)"
            )
        except Exception as e:
            return f"Error running concrete check (运行混凝土检算失败): {e}"

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
            kwargs = {
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
        except Exception as e:
            return f"Error adding reinforcement (添加配筋失败): {e}"

    @mcp.tool()
    def add_steel_hoop(
        index: int,
        name: str,
        hoop_type: int = 1,
        material_id: int = 1,
        nums: int = 2,
        diameter: float = 0.012,
        gap: float = 0.1,
        core_diameter: float = 0.0,
    ) -> str:
        """
        Add shear reinforcement / hoops (添加抗剪钢筋/箍筋).

        Args:
            index: Hoop ID (箍筋编号)
            name: Hoop name (箍筋名称)
            hoop_type: Hoop type (箍筋类型): 1=闭合式箍筋 (closed), 2=开口式箍筋 (open)
            material_id: Material ID (材料编号)
            nums: Number of branches (箍筋肢数)
            diameter: Rebar diameter in meters (钢筋直径m)
            gap: Spacing in meters (间距m)
            core_diameter: Core diameter for spiral hoops (芯截面直径, 仅螺旋箍筋使用)
        """
        try:
            provider.add_steel_hoop(
                index=index,
                name=name,
                hoop_type=hoop_type,
                material_id=material_id,
                nums=nums,
                diameter=diameter,
                gap=gap,
                core_diameter=core_diameter,
            )
            return f"Successfully added steel hoop '{name}' (成功添加抗剪钢筋)"
        except Exception as e:
            return f"Error adding steel hoop (添加抗剪钢筋失败): {e}"

    @mcp.tool()
    def update_vertical_steel_hoop(
        nums: int = 0,
        area: float = 0.001,
        gap: float = 0.2,
        effective_prestress: float = 800000000.0,
        fpd: float = 900000000.0,
    ) -> str:
        """
        Update vertical prestress reinforcement parameters for checking (修改竖向预应力抗剪参数).

        Args:
            nums: Number of vertical rebars/strands (竖向预应力根数)
            area: Area of a single rebar in m^2 (单根面积)
            gap: Longitudinal spacing in meters (纵向间距)
            effective_prestress: Effective prestress in Pa (有效预应力)
            fpd: Design tensile strength of vertical prestress in Pa (竖向预应力抗拉强度设计值)
        """
        try:
            provider.update_vertical_steel_hoop(
                nums=nums,
                area=area,
                gap=gap,
                effective_prestress=effective_prestress,
                fpd=fpd,
            )
            return "Successfully updated vertical prestress reinforcement (成功修改竖向预应力参数)"
        except Exception as e:
            return f"Error updating vertical steel hoop (修改竖向预应力参数失败): {e}"
