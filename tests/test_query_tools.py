"""合并查询工具行为测试：kind 分发、分页限流、必填参数校验。"""

from qiao_mcp.tools.queries import MAX_LIMIT, register_query_tools

from conftest import tool_fns


def test_only_four_query_tools_registered(fake_provider):
    fns = tool_fns(register_query_tools, fake_provider)
    assert set(fns) == {
        "get_model_data",
        "find_entities",
        "calc_section_property",
        "get_special_results",
    }


def test_kind_dispatch_nodes_with_ids(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_node_data",
        lambda ids: [{"node_id": 1, "x": 0, "y": 0, "z": 0}],
    )
    fns = tool_fns(register_query_tools, fake_provider)
    result = fns["get_model_data"](kind="nodes", ids="1to10")
    assert "node_id" in result and "Error" not in result


def test_pagination_truncates_and_reports(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_node_data", lambda ids: [{"node_id": i} for i in range(250)]
    )
    fns = tool_fns(register_query_tools, fake_provider)
    result = fns["get_model_data"](kind="nodes", limit=100)
    assert "[1–100 of 250]" in result
    assert "TRUNCATED" in result and "offset=100" in result
    # 第二页
    result2 = fns["get_model_data"](kind="nodes", limit=100, offset=100)
    assert "[101–200 of 250]" in result2
    # 末页无截断标记
    result3 = fns["get_model_data"](kind="nodes", limit=100, offset=200)
    assert "[201–250 of 250]" in result3
    assert "TRUNCATED" not in result3


def test_limit_is_capped(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_node_data", lambda ids: [{"node_id": i} for i in range(1000)]
    )
    fns = tool_fns(register_query_tools, fake_provider)
    result = fns["get_model_data"](kind="nodes", limit=99999)
    assert f"[1–{MAX_LIMIT} of 1000]" in result, "limit 必须被钳制到 MAX_LIMIT"


def test_required_param_guards(fake_provider):
    fns = tool_fns(register_query_tools, fake_provider)
    assert "sec_id" in fns["get_model_data"](kind="section_detail")
    assert "name" in fns["get_model_data"](kind="group_elements")
    assert "stage_id" in fns["get_model_data"](kind="stage_elements")
    assert fake_provider._odb.calls == [], "缺必填参数时不得发起查询"


def test_unknown_kind_rejected(fake_provider):
    fns = tool_fns(register_query_tools, fake_provider)
    assert "Unknown kind" in fns["get_model_data"](kind="bogus")
    assert "Unknown search mode" in fns["find_entities"](by="bogus")
    assert "Unknown result kind" in fns["get_special_results"](kind="bogus")


def test_find_entities_point_search(fake_provider, monkeypatch):
    monkeypatch.setattr(fake_provider, "get_node_id", lambda x, y, z, tol: 42)
    fns = tool_fns(register_query_tools, fake_provider)
    result = fns["find_entities"](by="node_at_point", x=1.0, y=2.0, z=3.0)
    assert "42" in result


def test_calc_section_property_requires_exactly_one_input(fake_provider):
    fns = tool_fns(register_query_tools, fake_provider)
    assert "恰选其一" in fns["calc_section_property"]()
    assert "恰选其一" in fns["calc_section_property"](
        loop_segments=[{"main": [[0, 0], [1, 0], [1, 1]]}], sec_lines=[[0, 0, 1, 0, 0.1]]
    )


def test_special_results_modal_dispatch(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_vibration_modal_results",
        lambda mode: [{"mode": mode, "freq": 1.23}],
    )
    fns = tool_fns(register_query_tools, fake_provider)
    result = fns["get_special_results"](kind="vibration_modal", mode=2)
    assert "1.23" in result
