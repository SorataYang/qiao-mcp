"""高级边界工具行为测试：参数映射与枚举语义。"""

from conftest import tool_fns

from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools


def test_elastic_link_maps_stiffness_to_boundary_info(fake_provider):
    fns = tool_fns(register_advanced_boundary_tools, fake_provider)
    fns["add_elastic_link"](
        start_node_id=1, end_node_id=2, link_type=1,
        stiffness_values=[1e6, 1e6, 1e6, 0, 0, 0],
    )
    _, _, kw = fake_provider._mdb.last("add_elastic_link")
    assert kw["boundary_info"] == [1e6, 1e6, 1e6, 0, 0, 0]
    assert kw["link_type"] == 1
    assert "stiffness" not in kw


def test_elastic_link_tension_only_uses_kx(fake_provider):
    fns = tool_fns(register_advanced_boundary_tools, fake_provider)
    fns["add_elastic_link"](start_node_id=1, end_node_id=2, link_type=3, kx=1e6)
    _, _, kw = fake_provider._mdb.last("add_elastic_link")
    assert kw["kx"] == 1e6
    assert "boundary_info" not in kw


def test_master_slave_link_uses_slave_id_and_boundary_info(fake_provider):
    fns = tool_fns(register_advanced_boundary_tools, fake_provider)
    fns["add_master_slave_link"](
        master_node_id=1,
        slave_node_ids=[2, 3],
        dof_constraints=[True, True, True, False, False, False],
    )
    _, _, kw = fake_provider._mdb.last("add_master_slave_link")
    assert kw["slave_id"] == [2, 3], "qtmodel 参数名为 slave_id（单数）"
    assert kw["boundary_info"] == [True, True, True, False, False, False]
    assert "slave_ids" not in kw and "dof_constraints" not in kw


def test_elastic_support_maps_spring_values_with_type(fake_provider):
    fns = tool_fns(register_advanced_boundary_tools, fake_provider)
    fns["add_elastic_support"](node_id=1, spring_values=[3, 1e6], support_type=3)
    _, _, kw = fake_provider._mdb.last("add_elastic_support")
    assert kw["boundary_info"] == [3, 1e6]
    assert kw["support_type"] == 3
    assert "spring_values" not in kw
