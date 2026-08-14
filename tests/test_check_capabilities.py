"""qtmodel 2.5.0 新增检算能力的聚合工具测试。

覆盖三件事：
1. kind/action 分派正确（聚合工具的核心风险是派发到错误的 qtmodel 方法）；
2. 单位约定——箍筋类沿用本库 SI（m）并在 provider 换算；
   分析设置类按 qtmodel 原生 mm/MPa 透传，**不得**被误换算；
3. 非法 kind/action 与缺失必填参数报 ToolInputError 而非静默成功。
"""

from __future__ import annotations

import pytest
from conftest import tool_fns

from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolInputError


@pytest.fixture
def tools(fake_provider):
    return tool_fns(register_checking_tools, fake_provider)


# ── 查询分派 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("stress", "get_concrete_check_stress_info"),
        ("solve_status", "get_concrete_check_solve_status"),
        ("basic_info", "get_check_case_basic_info"),
        ("materials", "get_check_case_material_infos"),
        ("stirrups", "get_check_case_stirrup_infos"),
        ("reinforcement", "get_check_case_reinforcement_data"),
        ("element_table", "get_element_table_info"),
        ("crack_width_setting", "get_crack_width_analysis_setting"),
        ("limit_state_setting", "get_limit_state_method_analysis_setting"),
        ("bearing_curve_setting", "get_bearing_curve_analysis_setting"),
    ],
)
def test_query_kind_dispatches_to_right_method(tools, fake_provider, kind, expected):
    tools["get_check_data"](kind=kind)
    assert fake_provider._cdb.count(expected) == 1, f"kind='{kind}' 应调用 {expected}"


def test_query_stress_forwards_type_and_name(tools, fake_provider):
    tools["get_check_data"](kind="stress", stress_type=4, name="主力组合")
    _, _, kw = fake_provider._cdb.last("get_concrete_check_stress_info")
    assert kw["stress_type"] == 4
    assert kw["specific_load_type_name"] == "主力组合"


def test_query_element_stirrup_forwards_element_id(tools, fake_provider):
    tools["get_check_data"](kind="shear_stirrup", element_id=7)
    _, _, kw = fake_provider._cdb.last("get_element_shear_stirrup_data")
    assert kw["ele_id"] == 7


def test_query_element_stirrup_defaults_to_all(tools, fake_provider):
    """省略 element_id 时应传 -1（qtmodel 约定：<=0 表示全部）。"""
    tools["get_check_data"](kind="torsion_stirrup")
    _, _, kw = fake_provider._cdb.last("get_element_torsion_stirrup_data")
    assert kw["ele_id"] == -1


def test_unknown_query_kind_raises_input_error(tools):
    with pytest.raises(ToolInputError):
        tools["get_check_data"](kind="no_such_kind")


# ── 分析设置：原生单位透传，禁止换算 ─────────────────────────────────


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("crack_width", "update_crack_width_analysis_setting"),
        ("normal_stress", "update_normal_stress_analysis_setting"),
        ("limit_state", "update_limit_state_method_analysis_setting"),
        ("normal_section_bearing", "update_normal_section_bearing_analysis_setting"),
        ("oblique_shear_bearing", "update_oblique_section_shear_bearing_analysis_setting"),
        ("moment_curvature", "update_moment_curvature_curve_analysis_setting"),
        ("bearing_curve", "update_bearing_curve_analysis_setting"),
    ],
)
def test_setting_kind_dispatches_to_right_method(tools, fake_provider, kind, expected):
    tools["configure_check_analysis"](kind=kind, settings={})
    assert fake_provider._cdb.count(expected) == 1


def test_setting_values_passed_through_unconverted(tools, fake_provider):
    """分析设置为 qtmodel 原生 mm/MPa，必须原样透传——换算即为错误。"""
    tools["configure_check_analysis"](
        kind="crack_width", settings={"protective_thickness": 30.0}
    )
    _, _, kw = fake_provider._cdb.last("update_crack_width_analysis_setting")
    assert kw["protective_thickness"] == pytest.approx(30.0), (
        "保护层厚度按 qtmodel 原生 mm 透传；若被当作 m 换算成 30000 则严重错误"
    )


def test_setting_stress_limits_passed_through_unconverted(tools, fake_provider):
    tools["configure_check_analysis"](
        kind="limit_state", settings={"fatigue_limit_steel_bar": 145.0}
    )
    _, _, kw = fake_provider._cdb.last("update_limit_state_method_analysis_setting")
    assert kw["fatigue_limit_steel_bar"] == pytest.approx(145.0), "疲劳限值按 MPa 原样透传"


def test_unknown_setting_kind_raises_input_error(tools):
    with pytest.raises(ToolInputError):
        tools["configure_check_analysis"](kind="nope", settings={})


# ── 箍筋定义：SI 入参，provider 换算 ──────────────────────────────────


def test_update_stirrup_converts_diameter_to_mm(tools, fake_provider):
    """与 add_check_stirrup 一致：工具收 m，落到 qtmodel 是 mm。"""
    tools["manage_check_stirrup"](action="update", stirrup_id=1, name="S1", diameter=0.016)
    _, _, kw = fake_provider._cdb.last("update_check_stirrup")
    assert kw["stirrup_diameter"] == pytest.approx(16.0)
    assert kw["stirrup_spacing"] == pytest.approx(0.2)


def test_update_stirrup_requires_name(tools):
    with pytest.raises(ToolInputError):
        tools["manage_check_stirrup"](action="update", stirrup_id=1)


def test_remove_stirrup_requires_id_or_name(tools):
    with pytest.raises(ToolInputError):
        tools["manage_check_stirrup"](action="remove")


def test_remove_stirrup_by_id(tools, fake_provider):
    tools["manage_check_stirrup"](action="remove", stirrup_id=3)
    _, _, kw = fake_provider._cdb.last("remove_check_stirrup")
    assert kw["stirrup_id"] == 3


def test_unknown_stirrup_action_raises_input_error(tools):
    with pytest.raises(ToolInputError):
        tools["manage_check_stirrup"](action="delete", stirrup_id=1, name="S1")


# ── 单元箍筋指定 ────────────────────────────────────────────────────────


def test_assign_shear_stirrup(tools, fake_provider):
    tools["assign_element_stirrup"](
        action="shear", element_id=5, stirrup_i_y=2, stirrup_j_x=3
    )
    _, _, kw = fake_provider._cdb.last("add_element_shear_stirrup")
    assert kw["ele_id"] == 5
    assert kw["stirrup_i_y"] == 2
    assert kw["stirrup_j_x"] == 3


def test_assign_torsion_stirrup(tools, fake_provider):
    tools["assign_element_stirrup"](action="torsion", element_id=5, stirrup_i=4)
    _, _, kw = fake_provider._cdb.last("add_element_torsion_stirrup")
    assert kw["ele_id"] == 5
    assert kw["stirrup_i"] == 4


def test_assign_requires_element_id(tools):
    with pytest.raises(ToolInputError):
        tools["assign_element_stirrup"](action="shear")


def test_remove_element_stirrup_all(tools, fake_provider):
    """element_id 省略时删除全部（qtmodel 约定 <=0）。"""
    tools["assign_element_stirrup"](action="remove")
    _, _, kw = fake_provider._cdb.last("remove_element_stirrup")
    assert kw["ele_id"] == -1


# ── 工况文件 ────────────────────────────────────────────────────────────


def test_open_case_by_name(tools, fake_provider):
    tools["manage_check_case_file"](action="open", name="C1")
    _, _, kw = fake_provider._cdb.last("open_concrete_check_case")
    assert kw["name"] == "C1"


def test_save_case_without_path_uses_save(tools, fake_provider):
    tools["manage_check_case_file"](action="save")
    assert fake_provider._cdb.count("save_check_case") == 1
    assert fake_provider._cdb.count("save_as_check_case") == 0


def test_save_case_with_path_uses_save_as(tools, fake_provider):
    tools["manage_check_case_file"](action="save", file_path="D:/t/case.cck")
    _, _, kw = fake_provider._cdb.last("save_as_check_case")
    assert kw["file_path"] == "D:/t/case.cck"
    assert fake_provider._cdb.count("save_check_case") == 0


def test_open_requires_name_or_path(tools):
    with pytest.raises(ToolInputError):
        tools["manage_check_case_file"](action="open")


def test_unknown_case_action_raises_input_error(tools):
    with pytest.raises(ToolInputError):
        tools["manage_check_case_file"](action="delete", name="C1")
