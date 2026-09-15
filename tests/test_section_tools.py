"""合并后 create_section 的行为测试：各类型分发与专用参数。"""

import pytest
import qtmodel
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolInputError


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


def test_polygon_payload_is_accepted_by_the_real_geometry_builder(fake_provider):
    loops = {"main": [[0, 0], [2, 0], [2, 1], [0, 1]]}
    functions = tool_fns(register_modeling_tools, fake_provider)
    functions["create_polygon_section"](name="Polygon", loop_segments=loops)
    kwargs = fake_provider._mdb.last("add_section")[2]
    assert kwargs["sec_type"] == "自定义线圈截面"
    assert isinstance(kwargs["loop_segments"], list)
    assert kwargs["loop_segments"][0]["main"][-1] == [0, 0]
    assert len(loops["main"]) == 4, "Normalization must not modify caller-owned coordinates"
    # This SDK builder is local Python geometry; it never contacts QiaoTong.
    shape = qtmodel.mdb.get_section_shape(
        sec_type=kwargs["sec_type"], loop_segments=kwargs["loop_segments"],
    )
    assert shape.parts[0].loop_segments


@pytest.mark.parametrize("loops", [
    {"sub1": [[0, 0], [1, 0], [1, 1]]},
    {"main": [[0, 0], [1, 0]]},
    {"main": [[0, 0], [1, 0], [2, 0]]},
    {"main": [[0, 0], [1, 0], [float("inf"), 1]]},
])
def test_invalid_polygon_is_rejected_before_writing(fake_provider, loops):
    functions = tool_fns(register_modeling_tools, fake_provider)
    with pytest.raises(ToolInputError):
        functions["create_polygon_section"](name="Invalid", loop_segments=loops)
    assert fake_provider._mdb.count("add_section") == 0
