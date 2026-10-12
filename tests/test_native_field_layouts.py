"""工具参数到 qtmodel 原生字段布局的映射测试。

这些布局由上游测试中的桥通 C# 导出日志确定，不以 docstring 的"示例"为准：

- 节点质量 mass_info = (平动质量, 绕X, 绕Y, 绕Z 转动惯量)；2.9 起另有
  mass_xyz=(mX, mY, mZ) 表达各向不同的平动质量，此时 mass_info 首项取 mZ
  （tests/fixtures/mass_plane_replay_logs.json）。
- 收缩徐变 code_index=1000 为用户自定义函数，1–9 各规范参数个数固定
  （tests/fixtures/time_parameter_replay.json 与 test_section_time_parameter_contract.py）。
"""

from __future__ import annotations

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError


@pytest.fixture
def modeling(fake_provider):
    return tool_fns(register_modeling_tools, fake_provider)


# ── 节点质量 ──────────────────────────────────────────────────────────


def test_isotropic_mass_uses_legacy_layout_for_every_build(modeling, fake_provider):
    modeling["add_nodal_mass"](node_id=1, mass=12.5, rot_x=1.0, rot_y=2.0, rot_z=3.0)
    _, _, kwargs = fake_provider._mdb.last("add_nodal_mass")
    assert kwargs == {"node_id": 1, "mass_info": [12.5, 1.0, 2.0, 3.0]}
    assert fake_provider._mdb.count("update_model") == 1


def test_direction_override_sends_mass_xyz_in_exporter_layout(modeling, fake_provider):
    modeling["add_nodal_mass"](node_id=[1], mass=20.0, mass_x=10.0, mass_z=30.0,
                               rot_x=4.0, rot_y=5.0, rot_z=6.0)
    _, _, kwargs = fake_provider._mdb.last("add_nodal_mass")
    # 与 C# 导出日志一致：mass_info 首项为 mZ，三向平动质量放在 mass_xyz
    assert kwargs == {
        "node_id": [1], "mass_info": [30.0, 4.0, 5.0, 6.0], "mass_xyz": [10.0, 20.0, 30.0],
    }


def test_direction_override_is_rejected_by_legacy_builds(modeling, fake_provider):
    calls = []

    def legacy_add_nodal_mass(node_id, mass_info=None):
        calls.append((node_id, mass_info))

    fake_provider._mdb.add_nodal_mass = legacy_add_nodal_mass
    with pytest.raises(ToolError, match="mass_xyz"):
        modeling["add_nodal_mass"](node_id=1, mass_z=100.0)
    assert calls == [], "旧版 qtmodel 不能表达各向不同质量时必须拒绝，不得静默合并"

    modeling["add_nodal_mass"](node_id=1, mass=100.0)
    assert calls == [(1, [100.0, 0.0, 0.0, 0.0])]


def test_all_zero_mass_is_rejected_before_writing(modeling, fake_provider):
    with pytest.raises(ToolError, match="nonzero"):
        modeling["add_nodal_mass"](node_id=1)
    assert fake_provider._mdb.calls == []


# ── 收缩徐变材料 ──────────────────────────────────────────────────────


def test_user_defined_functions_use_code_1000(modeling, fake_provider):
    modeling["add_time_parameter"](
        name="自定义", code_index=1000, creep_data=[["徐变函数", 18.5]], shrink_data="收缩函数",
    )
    _, _, kwargs = fake_provider._mdb.last("add_time_parameter")
    assert kwargs["code_index"] == 1000
    assert kwargs["creep_data"] == [("徐变函数", 18.5)]
    assert kwargs["shrink_data"] == "收缩函数"


def test_code_parameters_keep_native_count(modeling, fake_provider):
    modeling["add_time_parameter"](name="JTJ", code_index=3, time_parameter=[2, 1.75, 0.006, 0.001])
    assert fake_provider._mdb.last("add_time_parameter")[2]["time_parameter"] == [2, 1.75, 0.006, 0.001]


@pytest.mark.parametrize("arguments", [
    {"code_index": 1000},
    {"code_index": 1000, "creep_data": [["C", 7]], "time_parameter": [1, 2, 3, 4]},
    {"code_index": 1, "creep_data": [["C", 7]]},
    {"code_index": 1, "time_parameter": [1, 2, 3]},
    {"code_index": 8, "time_parameter": [1, 2, 3]},
])
def test_inconsistent_time_parameters_are_rejected(modeling, fake_provider, arguments):
    with pytest.raises(ToolError):
        modeling["add_time_parameter"](name="T", **arguments)
    assert fake_provider._mdb.calls == []


# ── 材料与截面特性 ────────────────────────────────────────────────────


def test_custom_material_requires_properties(modeling, fake_provider):
    with pytest.raises(ToolError, match="data_info"):
        modeling["create_material"](name="M", mat_type=5)
    assert fake_provider._mdb.calls == []
    modeling["create_material"](name="M", mat_type=5, data_info=[3.5e10, 2.5e4, 0.2, 1.2e-5])
    assert fake_provider._mdb.last("add_material")[2]["data_info"] == [3.5e10, 2.5e4, 0.2, 1.2e-5]


@pytest.mark.parametrize("count", [26, 29])
def test_section_property_accepts_both_native_layouts(modeling, fake_provider, count):
    values = [float(i) for i in range(count)]
    modeling["update_section_property"](index=1, sec_property=values)
    assert fake_provider._mdb.last("update_section_property")[2]["sec_property"] == values
