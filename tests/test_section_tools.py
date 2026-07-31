"""合并后 create_section 的行为测试：各类型分发与专用参数。"""

from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools


def test_specific_section_tools_removed(fake_provider):
    fns = tool_fns(register_modeling_tools, fake_provider)
    assert "create_rectangle_section" not in fns
    assert "create_steel_truss_box_1_section" not in fns
    # 输入结构不同的三个保留
    assert "create_polygon_section" in fns
    assert "create_line_width_section" in fns
    assert "create_section_from_properties" in fns


def test_rectangle_via_merged_tool(fake_provider):
    fns = tool_fns(register_modeling_tools, fake_provider)
    fns["create_section"](name="主梁", sec_type="矩形", sec_info=[1.0, 1.5])
    _, _, kw = fake_provider._mdb.last("add_section")
    assert kw == {"name": "主梁", "sec_type": "矩形", "sec_info": [1.0, 1.5]}


def test_composite_section_passes_mat_combine(fake_provider):
    fns = tool_fns(register_modeling_tools, fake_provider)
    fns["create_section"](
        name="组合梁", sec_type="工字组合梁",
        sec_info=[2.0, 0.2, 1.5, 0.016, 0.4, 0.024],
        mat_combine=[1.0, 0.15],
    )
    _, _, kw = fake_provider._mdb.last("add_section")
    assert kw["mat_combine"] == [1.0, 0.15]
    assert kw["sec_type"] == "工字组合梁"


def test_concrete_box_girder_specific_params(fake_provider):
    fns = tool_fns(register_modeling_tools, fake_provider)
    fns["create_section"](
        name="箱梁", sec_type="混凝土箱梁",
        sec_info=[1.0, 2.0, 3.0], box_num=3, box_height=2.5, symmetry=True,
    )
    _, _, kw = fake_provider._mdb.last("add_section")
    assert kw["box_num"] == 3
    assert kw["box_height"] == 2.5
    assert kw["symmetry"] is True


def test_symmetry_not_sent_for_plain_shapes(fake_provider):
    fns = tool_fns(register_modeling_tools, fake_provider)
    fns["create_section"](name="圆", sec_type="圆形", sec_info=[0.6])
    _, _, kw = fake_provider._mdb.last("add_section")
    assert "symmetry" not in kw, "非箱梁类型不应下发 symmetry，避免覆盖 qtmodel 默认"
