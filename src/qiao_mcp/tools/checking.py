"""
MCP Tools for structural concrete checking and reinforcement design.
结构混凝土检算与配筋设计工具
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError

MAX_LIMIT = 500


def _fmt(obj: Any) -> str:
    """把 qtmodel 返回值（含 CheckStressItem 等自定义对象）序列化为文本。"""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


def _paginate(data: Any, limit: int, offset: int) -> str:
    """Slice list data and annotate with pagination info (分页并标注截断信息)."""
    if not isinstance(data, list):
        return _fmt(data)
    total = len(data)
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    window = data[offset : offset + limit]
    header = f"[{offset + 1}–{offset + len(window)} of {total}]"
    if offset + len(window) < total:
        header += (
            f" TRUNCATED — use offset={offset + len(window)} for the next page "
            f"(结果已截断，用 offset 翻页)"
        )
    return f"{header}\n{_fmt(window)}"


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

    # ── qtmodel 2.5.0 新增检算能力 ─────────────────────────────────────

    @mcp.tool()
    def get_check_data(
        kind: str,
        element_id: int | None = None,
        stress_type: int = 1,
        combine_type: int = 1,
        name: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """
        Query concrete-check data by kind (按类型查询混凝土检算数据).

        Read-only. Requires a check case to be open/imported first.
        只读工具；需先创建或打开检算工况。列表结果分页返回。

        Args:
            kind: What to query (查询类型):
                ── 结果 Results ──
                "stress" (应力信息, 可选 stress_type/name),
                "solve_status" (检算求解状态)
                ── 工况 Case ──
                "case" (检算工况, 可选 name), "basic_info" (检算基本信息),
                "materials" (材料信息), "load_table" (荷载表, 可选 combine_type/name),
                "section_property" (截面特性), "element_table" (单元表)
                ── 配筋 Reinforcement ──
                "reinforcement" (配筋数据), "stirrups" (箍筋定义),
                "shear_stirrup" (单元抗剪箍筋, 可选 element_id),
                "torsion_stirrup" (单元抗扭箍筋, 可选 element_id),
                "vertical_prestress" (竖向预应力), "tendon_section" (钢束截面)
                ── 分析设置 Analysis settings ──
                "normal_section_bearing_setting" (正截面承载力),
                "oblique_shear_bearing_setting" (斜截面抗剪承载力),
                "limit_state_setting" (极限状态法), "normal_stress_setting" (正应力),
                "crack_width_setting" (裂缝宽度), "moment_curvature_setting" (弯矩曲率),
                "bearing_curve_setting" (承载力曲线)
            element_id: Element ID for stirrup queries; omit for all (单元号，省略则查全部)
            stress_type: Stress combination type for kind="stress" (应力组合类型):
                非 AASHTO: 1=标准值组合, 2=频遇组合, 3=准永久值组合, 4=主力组合,
                          5=主加附组合, 6=施工组合, 7=主加特殊组合, 8=恒载作用,
                          9=预应力作用, 10~13=使用组合Ⅰ~Ⅳ, 14=永久作用组合
                AASHTO 2020: 1~4=使用组合Ⅰ~Ⅳ, 5=永久作用组合, 6=施工组合
            combine_type: Combination type for kind="load_table" (荷载表组合类型)
            name: Explicit display name; overrides stress_type/combine_type when set
                  (指定组合显示名，非空时优先于类型序号)
            limit: Max items per page, default 100, max 500 (单页条数上限)
            offset: Pagination offset (分页偏移)
        """
        try:
            data = provider.get_check_data(
                kind,
                element_id=element_id,
                stress_type=stress_type,
                combine_type=combine_type,
                name=name,
            )
            if data is None or data == [] or data == {}:
                return (
                    f"No data for kind='{kind}' (无数据). "
                    f"Check case may not be open or analysis not run."
                )
            return f"{kind}:\n{_paginate(data, limit, offset)}"
        except ValueError as e:
            raise ToolInputError(
                f"{e}. See tool description for valid kinds (未知查询类型，请查阅工具说明)"
            ) from e
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error querying check data '{kind}' (查询检算数据失败): {e}") from e

    @mcp.tool()
    def configure_check_analysis(kind: str, settings: dict[str, Any]) -> str:
        """
        Configure a concrete-check analysis setting group (配置混凝土检算分析设置).

        ⚠️ UNITS (单位): parameters in this tool use qtmodel's NATIVE units —
        **mm for lengths and MPa for stresses**, NOT the SI (m/Pa) used elsewhere
        in this server. qtmodel does not document these units; they are inferred
        from its defaults (e.g. protective_thickness=30.0 means 30 mm,
        fatigue_limit_steel_bar=145.0 means 145 MPa). Pass values accordingly.
        本工具参数沿用 qtmodel 原生单位（长度 mm、应力 MPa），与本服务器其余
        工具的 SI 约定不同；qtmodel 未标注单位，此结论由其默认值推断。

        Use get_check_data("<kind>_setting") to read current values first.
        建议先用 get_check_data 读取当前值，再按需覆盖。

        Args:
            kind: Setting group (设置类别):
                "normal_section_bearing" (正截面承载力):
                    normal_section_bearing_calculation_type: 1=同比例变化 2=轴力不变
                        3=My不变 4=Mz不变 5=轴力与My不变 6=轴力与Mz不变 7=My与Mz不变
                "oblique_shear_bearing" (斜截面抗剪承载力):
                    reinforcement_height_multiple, is_consider_as_simple_support,
                    shear_strength_material_factor,
                    oblique_section_shear_direction_type: 1=竖向(z) 2=横向(y) 3=双向
                "limit_state" (极限状态法):
                    cal_fatigue, fatigue_limit_steel_bar (MPa),
                    fatigue_limit_prestress (MPa), is_consider_as_simple_support,
                    is_consider_construction_load
                "normal_stress" (正应力):
                    aashto2020_normal_stress_rebar_type: 1=直钢筋/无交叉焊缝焊接钢丝网
                        2=高应力区带交叉焊缝的直焊接钢丝网,
                    tendon_allowable_stress_amplitude (MPa),
                    flange_web_slenderness_ratio,
                    construction_stage_concrete_tensile_limit (MPa),
                    service_combination3_concrete_tension_limit (MPa)
                "crack_width" (裂缝宽度):
                    highway_environment_category_type (1~7 公路环境类别),
                    railway_environment_category_type (1~6 铁路环境类别),
                    railway_limit_environment_category_type (1~11 铁路限值环境类别),
                    crack_setting_type: 1=0 2=0.10 3=0.15 4=0.20 5=0.25 6=禁止使用,
                    clear_protective_thickness (mm), protective_thickness (mm),
                    steel_bar_type: 1=带肋钢筋 2=光圆钢筋,
                    effect_coefficient_type: 1=软件自动计算 2=用户指定,
                    user_specified_effect_coefficient, is_epoxy_resin_rebar,
                    is_welded_rebar_skeleton, mq_mg (活载/恒载弯矩比), exposure_coefficient
                "moment_curvature" (弯矩曲率):
                    moment_curvature_type: 1=轴力P变化 2=弯矩M变化,
                    moment_curvature_model_type: 1=双线性模型 2=理想弹塑性模型
                "bearing_curve" (承载力曲线):
                    bearing_curve_count (计算点数),
                    angle_between_m_and_y_axis (弯矩方向与y轴夹角), force_p (轴力P)
            settings: Parameter dict for the chosen kind; only pass what you change
                      (该类别的参数字典，只需传要修改的项)
        """
        try:
            if not isinstance(settings, dict):
                raise ToolInputError("settings must be a dict (settings 必须为字典)")
            provider.configure_check_analysis(kind, settings)
            changed = ", ".join(f"{k}={v}" for k, v in settings.items()) or "(no change)"
            return f"Analysis setting '{kind}' updated: {changed} (检算分析设置已更新)"
        except ValueError as e:
            raise ToolInputError(
                f"{e}. See tool description for valid kinds (未知设置类别，请查阅工具说明)"
            ) from e
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error configuring '{kind}' (配置检算分析设置失败): {e}") from e

    @mcp.tool()
    def manage_check_stirrup(
        action: str,
        stirrup_id: int = -1,
        name: str = "",
        stirrup_type: int = 1,
        material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter: float = 0.020,
        spacing: float = 0.2,
        core_diameter: float = 0.0,
    ) -> str:
        """
        Update or remove a stirrup definition (修改或删除检算箍筋定义).

        Use add_check_stirrup to create one. Lengths are in METERS (SI), converted
        internally. 新增请用 add_check_stirrup；长度入参为米，内部换算。

        Args:
            action: "update" (修改) or "remove" (删除)
            stirrup_id: Stirrup definition ID (箍筋定义编号); <=0 means match by name
            name: Stirrup definition name (箍筋定义名称)
            stirrup_type: 1=普通箍筋 (normal), 2=螺旋式箍筋 (spiral)
            material_id: Rebar material ID (钢筋材料号)
            limbs_number: Limbs, for normal stirrups (普通箍筋肢数)
            loops_number: Loops, for spiral stirrups (螺旋式箍筋环数)
            diameter: Stirrup diameter in meters (箍筋直径, 单位 m)
            spacing: Stirrup spacing in meters (箍筋间距, 单位 m)
            core_diameter: Spiral core diameter in meters (螺旋箍筋核心直径, 单位 m)
        """
        try:
            if action == "update":
                if not name:
                    raise ToolInputError("update requires name (修改需提供箍筋名称)")
                provider.update_check_stirrup(
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
                return f"Stirrup '{name}' updated (箍筋定义已修改)"
            if action == "remove":
                if stirrup_id <= 0 and not name:
                    raise ToolInputError(
                        "remove requires stirrup_id or name (删除需提供编号或名称)"
                    )
                provider.remove_check_stirrup(stirrup_id=stirrup_id, name=name)
                target = name or f"#{stirrup_id}"
                return f"Stirrup '{target}' removed (箍筋定义已删除)"
            raise ToolInputError(f"Unknown action '{action}'; use update/remove (未知操作)")
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error managing stirrup (管理箍筋定义失败): {e}") from e

    @mcp.tool()
    def assign_element_stirrup(
        action: str,
        element_id: int = -1,
        stirrup_i_y: int = 1,
        stirrup_i_x: int = 1,
        stirrup_j_y: int = 1,
        stirrup_j_x: int = 1,
        stirrup_i: int = 1,
        stirrup_j: int = 1,
    ) -> str:
        """
        Assign or remove element stirrups (指定或删除单元箍筋).

        Stirrup numbers refer to definitions created by add_check_stirrup.
        箍筋号引用 add_check_stirrup 创建的箍筋定义。

        Args:
            action: "shear" (抗剪箍筋), "torsion" (抗扭箍筋), or "remove" (删除)
            element_id: Element ID (单元号); for "remove", <=0 removes all elements
            stirrup_i_y: I-end vertical stirrup ID, shear only (I端竖向箍筋号)
            stirrup_i_x: I-end transverse stirrup ID, shear only (I端横向箍筋号)
            stirrup_j_y: J-end vertical stirrup ID, shear only (J端竖向箍筋号)
            stirrup_j_x: J-end transverse stirrup ID, shear only (J端横向箍筋号)
            stirrup_i: I-end stirrup ID, torsion only (I端抗扭箍筋号)
            stirrup_j: J-end stirrup ID, torsion only (J端抗扭箍筋号)
        """
        try:
            if action == "shear":
                if element_id <= 0:
                    raise ToolInputError("shear requires element_id (需提供单元号)")
                provider.set_element_shear_stirrup(
                    element_id=element_id,
                    stirrup_i_y=stirrup_i_y,
                    stirrup_i_x=stirrup_i_x,
                    stirrup_j_y=stirrup_j_y,
                    stirrup_j_x=stirrup_j_x,
                )
                return f"Shear stirrup assigned to element {element_id} (单元抗剪箍筋已指定)"
            if action == "torsion":
                if element_id <= 0:
                    raise ToolInputError("torsion requires element_id (需提供单元号)")
                provider.set_element_torsion_stirrup(
                    element_id=element_id, stirrup_i=stirrup_i, stirrup_j=stirrup_j
                )
                return f"Torsion stirrup assigned to element {element_id} (单元抗扭箍筋已指定)"
            if action == "remove":
                provider.remove_element_stirrup(element_id=element_id)
                scope = f"element {element_id}" if element_id > 0 else "all elements"
                return f"Stirrups removed from {scope} (单元箍筋已删除)"
            raise ToolInputError(
                f"Unknown action '{action}'; use shear/torsion/remove (未知操作)"
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error assigning element stirrup (指定单元箍筋失败): {e}") from e

    @mcp.tool()
    def manage_check_case_file(action: str, name: str = "", file_path: str = "") -> str:
        """
        Open or save a concrete check case file (打开或保存混凝土检算工况文件).

        Args:
            action: "open" (打开) or "save" (保存)
            name: Check case name; for "open", resolves to the default check data
                  directory when file_path is empty (工况名称)
            file_path: Full path to the case file. For "open" it takes priority over
                       name; for "save" a non-empty value means save-as
                       (工况文件完整路径；保存时非空表示另存为)
        """
        try:
            if action == "open":
                if not name and not file_path:
                    raise ToolInputError("open requires name or file_path (需提供名称或路径)")
                provider.open_check_case(name=name, file_path=file_path)
                return f"Check case '{name or file_path}' opened (检算工况已打开)"
            if action == "save":
                provider.save_check_case(file_path=file_path)
                where = f" to {file_path}" if file_path else ""
                return f"Check case saved{where} (检算工况已保存)"
            raise ToolInputError(f"Unknown action '{action}'; use open/save (未知操作)")
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error managing check case file (管理检算工况文件失败): {e}") from e
