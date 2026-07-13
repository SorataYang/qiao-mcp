"""合并查询工具行为测试：kind 分发、分页限流、必填参数校验。"""

import pytest

from qiao_mcp.tools.envelope import ToolInputError
from qiao_mcp.tools.queries import MAX_LIMIT, register_query_tools

from conftest import tool_fns, tool_text


def _fns(fake_provider):
    return tool_fns(register_query_tools, fake_provider)


def test_only_four_query_tools_registered(fake_provider):
    fns = _fns(fake_provider)
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
    fns = _fns(fake_provider)
    text = tool_text(fns["get_model_data"](kind="nodes", ids="1to10"))
    assert "node_id" in text


def test_pagination_truncates_and_reports(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_node_data", lambda ids: [{"node_id": i} for i in range(250)]
    )
    fns = _fns(fake_provider)
    text = tool_text(fns["get_model_data"](kind="nodes", limit=100))
    assert "[1–100 of 250]" in text
    assert "TRUNCATED" in text and "offset=100" in text
    text2 = tool_text(fns["get_model_data"](kind="nodes", limit=100, offset=100))
    assert "[101–200 of 250]" in text2
    text3 = tool_text(fns["get_model_data"](kind="nodes", limit=100, offset=200))
    assert "[201–250 of 250]" in text3
    assert "TRUNCATED" not in text3


def test_limit_is_capped(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_node_data", lambda ids: [{"node_id": i} for i in range(1000)]
    )
    fns = _fns(fake_provider)
    text = tool_text(fns["get_model_data"](kind="nodes", limit=99999))
    assert f"[1–{MAX_LIMIT} of 1000]" in text, "limit 必须被钳制到 MAX_LIMIT"


def test_required_param_guards(fake_provider):
    fns = _fns(fake_provider)
    for kind in ("section_detail", "group_elements", "stage_elements"):
        with pytest.raises(ToolInputError):
            fns["get_model_data"](kind=kind)
    assert fake_provider._odb.calls == [], "缺必填参数时不得发起查询"


def test_unknown_kind_rejected(fake_provider):
    fns = _fns(fake_provider)
    with pytest.raises(ToolInputError):
        fns["get_model_data"](kind="bogus")
    with pytest.raises(ToolInputError):
        fns["find_entities"](by="bogus")
    with pytest.raises(ToolInputError):
        fns["get_special_results"](kind="bogus")


def test_find_entities_point_search(fake_provider, monkeypatch):
    monkeypatch.setattr(fake_provider, "get_node_id", lambda x, y, z, tol: 42)
    fns = _fns(fake_provider)
    text = tool_text(fns["find_entities"](by="node_at_point", x=1.0, y=2.0, z=3.0))
    assert "42" in text


def test_calc_section_property_requires_exactly_one_input(fake_provider):
    fns = _fns(fake_provider)
    with pytest.raises(ToolInputError):
        fns["calc_section_property"]()
    with pytest.raises(ToolInputError):
        fns["calc_section_property"](
            loop_segments=[{"main": [[0, 0], [1, 0], [1, 1]]}],
            sec_lines=[[0, 0, 1, 0, 0.1]],
        )


def test_special_results_modal_dispatch(fake_provider, monkeypatch):
    monkeypatch.setattr(
        fake_provider, "get_vibration_modal_results",
        lambda mode: [{"mode": mode, "freq": 1.23}],
    )
    fns = _fns(fake_provider)
    text = tool_text(fns["get_special_results"](kind="vibration_modal", mode=2))
    assert "1.23" in text
