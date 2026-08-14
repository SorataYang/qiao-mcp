"""qtmodel 2.5.0 检算接口迁移测试。

重点守护**契约测试看不见的两类回归**：

1. **单位换算**：2.5.0 的替代函数静默改了单位（直径 m→mm、面积 m²→mm²、
   应力 Pa→MPa）。签名能绑定、CI 全绿，但数值差 1000 倍，产出错误的检算结果。
2. **枚举取值**：stirrup_type / combine_method 的取值含义随改名而变。

这些断言直接检查落到 cdb 的**最终数值**，而非仅参数名。
"""

from __future__ import annotations

import pytest
from conftest import tool_fns

from qiao_mcp.tools.checking import register_checking_tools


@pytest.fixture
def tools(fake_provider):
    return tool_fns(register_checking_tools, fake_provider)


# ── 单位换算 ────────────────────────────────────────────────────────────


def test_stirrup_diameter_converted_meters_to_mm(tools, fake_provider):
    """箍筋直径：工具收 m，落到 qtmodel 必须是 mm（×1000）。"""
    tools["add_check_stirrup"](stirrup_id=1, name="S1", diameter=0.020)
    _, _, kw = fake_provider._cdb.last("add_check_stirrup")
    assert kw["stirrup_diameter"] == pytest.approx(20.0), (
        "0.020 m 必须换算为 20 mm；若原样传 0.020 则后端按 0.02mm 计算，" "抗剪承载力将严重偏小"
    )
    # 间距与核心直径在 2.5.0 仍是 m，不得误换算
    assert kw["stirrup_spacing"] == pytest.approx(0.2)


def test_stirrup_spacing_and_core_diameter_stay_meters(tools, fake_provider):
    tools["add_check_stirrup"](stirrup_id=1, name="S1", spacing=0.15, core_diameter=1.2)
    _, _, kw = fake_provider._cdb.last("add_check_stirrup")
    assert kw["stirrup_spacing"] == pytest.approx(0.15)
    assert kw["core_diameter"] == pytest.approx(1.2)


def test_vertical_tendon_area_converted_m2_to_mm2(tools, fake_provider):
    """单肢面积：工具收 m²，落到 qtmodel 必须是 mm²（×1e6）。"""
    tools["update_vertical_steel_tendon"](area=0.000804)
    _, _, kw = fake_provider._cdb.last("update_vertical_steel_tendon")
    assert kw["single_limb_area"] == pytest.approx(804.0)


def test_vertical_tendon_stresses_converted_pa_to_mpa(tools, fake_provider):
    """有效预应力与 fpd：工具收 Pa，落到 qtmodel 必须是 MPa（÷1e6）。"""
    tools["update_vertical_steel_tendon"](effective_prestress=8.0e8, fpd=9.0e8)
    _, _, kw = fake_provider._cdb.last("update_vertical_steel_tendon")
    assert kw["effective_prestress"] == pytest.approx(800.0)
    assert kw["strength_design_value"] == pytest.approx(900.0)
    # 间距仍为 m
    assert kw["spacing"] == pytest.approx(0.2)


def test_vertical_tendon_defaults_match_qtmodel_defaults(tools, fake_provider):
    """工具默认值换算后应与 qtmodel 2.5.0 的界面默认值一致。"""
    tools["update_vertical_steel_tendon"]()
    _, _, kw = fake_provider._cdb.last("update_vertical_steel_tendon")
    assert kw["single_limb_area"] == pytest.approx(804.0)
    assert kw["effective_prestress"] == pytest.approx(800.0)
    assert kw["strength_design_value"] == pytest.approx(900.0)


# ── 参数改名与枚举 ──────────────────────────────────────────────────────


def test_load_combine_maps_kind_to_combine_type(tools, fake_provider):
    """2.5.0：旧 kind（组合类型）→ combine_type；旧 combine_type（组合方式）→ combine_method。"""
    tools["add_check_load_combination"](
        name="标准组合", standard=1, kind=3, combine_method=2, load_case_factors=[["P1 (ST)", 1.0, 1.0]]
    )
    _, _, kw = fake_provider._cdb.last("add_check_load_combine")
    assert kw["combine_type"] == 3, "kind=3(标准值组合) 必须落到 combine_type"
    assert kw["combine_method"] == 2, "combine_method=2(包络) 必须原样落到 combine_method"
    assert kw["standard"] == 1
    assert kw["combine_info"] == [("P1 (ST)", 1.0, 1.0)]
    # 2.5.0 已移除的参数不得再出现
    assert "kind" not in kw
    assert "index" not in kw


def test_load_combine_default_method_is_additive(tools, fake_provider):
    """默认组合方式应为 1=相加并判别（此前默认值实为包络，与文档不符）。"""
    tools["add_check_load_combination"](name="C1")
    _, _, kw = fake_provider._cdb.last("add_check_load_combine")
    assert kw["combine_method"] == 1


# ── 求解流程 ────────────────────────────────────────────────────────────


def test_run_concrete_check_imports_case_then_solves(tools, fake_provider):
    """2.5.0 solve 不再接受 name，须先 import_concrete_check_case 同步工况。"""
    tools["run_concrete_check"](name="混凝土检算")
    calls = [c[0] for c in fake_provider._cdb.calls]
    assert calls.index("import_concrete_check_case") < calls.index("solve_concrete_check"), (
        "必须先同步工况再求解，否则会对上一次的检算数据求解"
    )
    _, _, imp_kw = fake_provider._cdb.last("import_concrete_check_case")
    assert imp_kw["case_name"] == "混凝土检算"
    _, _, solve_kw = fake_provider._cdb.last("solve_concrete_check")
    assert "name" not in solve_kw, "2.5.0 的 solve_concrete_check 已无 name 参数"
    assert solve_kw["wait"] is True, "工具语义是同步等待完成，必须 wait=True"


def test_run_concrete_check_passes_max_wait(tools, fake_provider):
    tools["run_concrete_check"](name="C1", max_wait_seconds=600.0)
    _, _, kw = fake_provider._cdb.last("solve_concrete_check")
    assert kw["max_wait"] == pytest.approx(600.0)


def test_run_concrete_check_accepts_unlimited_wait(tools, fake_provider):
    tools["run_concrete_check"](name="C1", max_wait_seconds=None)
    _, _, kw = fake_provider._cdb.last("solve_concrete_check")
    assert kw["max_wait"] is None
