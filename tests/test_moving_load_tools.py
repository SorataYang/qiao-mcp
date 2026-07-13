"""移动荷载工具行为测试：完整工作流的参数下发与格式转换。"""

from qiao_mcp.tools.moving_load import register_moving_load_tools

from conftest import tool_fns


def test_full_moving_load_workflow_dispatch(fake_provider):
    fns = tool_fns(register_moving_load_tools, fake_provider)
    mdb = fake_provider._mdb

    fns["add_node_tandem"](name="节点纵列1", node_ids="1to101")
    _, _, kw = mdb.last("add_node_tandem")
    assert kw == {"name": "节点纵列1", "node_ids": "1to101", "order_by_x": True}

    fns["add_influence_plane"](name="影响面1", tandem_names=["节点纵列1"])
    _, _, kw = mdb.last("add_influence_plane")
    assert kw == {"name": "影响面1", "tandem_names": ["节点纵列1"]}

    fns["add_traffic_lane"](name="车道1", influence_name="影响面1", tandem_name="节点纵列1")
    _, _, kw = mdb.last("add_lane_line")
    assert kw["influence_name"] == "影响面1"
    assert kw["tandem_name"] == "节点纵列1"
    assert kw["lane_width"] == 3.1

    fns["add_standard_vehicle"](name="公路I级")
    _, _, kw = mdb.last("add_standard_vehicle")
    assert kw["standard_code"] == 5
    assert kw["load_type"] == "公路I级车道"

    result = fns["create_live_load_case"](
        name="活载工况1",
        influence_plane="影响面1",
        span=100.0,
        sub_cases=[["公路I级", 1.0, ["车道1", "车道2"]]],
    )
    _, _, kw = mdb.last("add_live_load_case")
    assert kw["influence_plane"] == "影响面1"
    assert kw["span"] == 100.0
    assert kw["sub_case"] == [("公路I级", 1.0, ["车道1", "车道2"])]
    assert "Error" not in result


def test_get_live_load_results_rejects_unknown_type(fake_provider):
    fns = tool_fns(register_moving_load_tools, fake_provider)
    result = fns["get_live_load_results"](case_name="活载工况1", result_type="bogus")
    assert "Unknown result_type" in result
    assert fake_provider._odb.calls == [], "未知结果类型不得静默回退到内力查询"
