"""钢束工具行为测试：参数组装与格式转换。"""

from qiao_mcp.tools.tendon import register_tendon_tools

from conftest import tool_fns


def test_tendon_property_builds_steel_detail_and_slip_info(fake_provider):
    fns = tool_fns(register_tendon_tools, fake_provider)
    fns["create_tendon_property"](
        name="15-10",
        material_name="预应力钢绞线",
        area=0.00139,
        duct_diameter=0.09,
        friction=0.22,
        deviation=0.0015,
        anchorage_slip=0.006,
    )
    _, _, kw = fake_provider._mdb.last("add_tendon_property")
    assert kw["material_name"] == "预应力钢绞线"
    assert kw["steel_detail"] == [0.00139, 0.09, 0.22, 0.0015]
    assert kw["slip_info"] == (0.006, 0.006)
    assert kw["tendon_type"] == 1, "默认后张法应为 qtmodel 枚举 1"


def test_tendon_property_raw_steel_detail_override(fake_provider):
    fns = tool_fns(register_tendon_tools, fake_provider)
    raw = [0.032, 0.000804, 0.05, 0.3, 0.0015, 1]
    fns["create_tendon_property"](
        name="精轧螺纹", material_name="螺纹钢筋", steel_type=2, steel_detail=raw
    )
    _, _, kw = fake_provider._mdb.last("add_tendon_property")
    assert kw["steel_detail"] == raw


def test_tendon_2d_converts_points_to_tuples(fake_provider):
    fns = tool_fns(register_tendon_tools, fake_provider)
    fns["create_tendon_2d"](
        name="T1",
        property_name="15-10",
        control_points=[[0, -0.5, 0], [20, -1.2, 8]],
        point_insert=[0, 0, 0],
    )
    _, _, kw = fake_provider._mdb.last("add_tendon_2d")
    assert kw["control_points"] == [(0, -0.5, 0), (20, -1.2, 8)]
    assert kw["point_insert"] == (0, 0, 0)
    assert kw["group_name"] == "默认钢束组"


def test_apply_prestress_passes_list_and_tension_type(fake_provider):
    fns = tool_fns(register_tendon_tools, fake_provider)
    fns["apply_prestress"](
        case_name="预应力", tendon_name=["T1", "T2"], force=1395000.0, tension_type=0
    )
    _, _, kw = fake_provider._mdb.last("add_pre_stress")
    assert kw["tendon_name"] == ["T1", "T2"], "qtmodel 原生支持列表，应一次下发"
    assert kw["tension_type"] == 0
