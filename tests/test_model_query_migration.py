"""Model-query ownership and read-only gateway compatibility across qtmodel builds."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError


@pytest.mark.parametrize("modern", [True, False], ids=["mdb", "legacy-odb"])
@pytest.mark.parametrize(("method", "args", "kwargs", "qt_method", "payload"), [
    ("get_node_data", (), {"ids": "1to3"}, "get_node_data", [{"node_id": 1}]),
    ("get_element_data", (), {"ids": [2]}, "get_element_data", [{"index": 2}]),
    ("get_material_data", (), {}, "get_material_data", [{"index": 3}]),
    ("get_section_data", (3,), {"position": 1}, "get_section_data", {"name": "主梁"}),
    ("get_section_shape", (3,), {}, "get_model_section_shape", {"parts": []}),
    ("get_section_property", (3,), {}, "get_section_property", {"Ax": 2.0}),
    ("get_thickness_data", (), {}, "get_thickness_data", [{"thick_id": 1}]),
    ("get_nodal_force_load_data", (), {}, "get_nodal_force_load_data", [{"node_id": 1}]),
    ("get_tendon_data", (), {}, "get_tendon_data", [{"name": "T1"}]),
    ("get_elements_of_stage", (2,), {}, "get_elements_of_stage", [1, 2]),
    ("get_elements_by_material", (3,), {}, "get_elements_by_material", [1, 2]),
])
def test_model_queries_prefer_mdb_and_fall_back_only_when_absent(
    fake_provider, modern, method, args, kwargs, qt_method, payload,
):
    query = Mock(return_value=json.dumps(payload))
    legacy = Mock(side_effect=AssertionError("legacy query must not run")) if modern else query
    local_shape = Mock(side_effect=AssertionError("local shape builder must not run"))
    fake_provider._mdb = SimpleNamespace(get_section_shape=local_shape)
    fake_provider._odb = SimpleNamespace(**{method: legacy})
    if modern:
        setattr(fake_provider._mdb, qt_method, query)

    assert getattr(fake_provider, method)(*args, **kwargs) == payload
    query.assert_called_once_with(*args, **kwargs)
    local_shape.assert_not_called()
    if modern:
        legacy.assert_not_called()


def test_query_failure_does_not_retry_the_legacy_namespace(fake_provider):
    query = Mock(side_effect=RuntimeError("query rejected"))
    legacy = Mock()
    fake_provider._mdb = SimpleNamespace(get_material_data=query, get_model_summary=query)
    fake_provider._odb = SimpleNamespace(get_material_data=legacy, get_model_summary=legacy)

    with pytest.raises(RuntimeError, match="query rejected"):
        fake_provider.get_material_data()
    assert fake_provider.get_model_overview("summary") is None
    legacy.assert_not_called()


def test_optional_queries_keep_legacy_odb_support(fake_provider):
    query = Mock(return_value='[{"name": "主梁", "node_count": 3}]')
    fake_provider._mdb = SimpleNamespace()
    fake_provider._odb = SimpleNamespace(get_structure_group_summaries=query)
    assert fake_provider.get_model_overview("structure_group_summaries") == [
        {"name": "主梁", "node_count": 3},
    ]
    query.assert_called_once_with()


def test_group_validation_and_boundary_queries_use_mdb(fake_provider):
    fake_provider.get_structure_group_elements("主梁")
    fake_provider.get_boundary_data()
    fake_provider.validate_model()

    assert fake_provider._odb.calls == []
    for method in (
        "get_group_elements", "get_general_support_data", "get_elastic_link_data",
        "get_elastic_support_data", "get_master_slave_link_data", "get_beam_constraint_data",
        "get_overlap_nodes", "get_overlap_elements", "get_node_data", "get_element_data",
    ):
        assert fake_provider._mdb.count(method) >= 1
    assert fake_provider._mdb.last("get_group_elements")[2] == {"group_name": "主梁"}


@pytest.mark.parametrize("method", [
    "get_node_data", "query_node_data", "get_nodal_force_load_data",
    "get_model_section_shape", "calc_section_property",
])
@pytest.mark.parametrize("read_allowed", [True, False])
def test_mdb_gateway_queries_require_read_permission_and_never_refresh(
    fake_provider, method, read_allowed,
):
    query = Mock(return_value=[SimpleNamespace(node_id=1)])
    refresh = Mock()
    fake_provider._mdb = SimpleNamespace(**{method: query, "update_model": refresh})
    state = ready_model_state()
    state["model_state"]["capabilities"].update(
        read_model=read_allowed, modify_model=False, query_results=False,
    )
    fake_provider.get_model_state = lambda: state
    functions = tool_fns(register_api_gateway_tools, fake_provider)

    if read_allowed:
        result = functions["call_qtmodel_api"](api_object="mdb", method=method)
        assert json.loads(result["message"].split("\n", 1)[1]) == [{"node_id": 1}]
        query.assert_called_once_with()
    else:
        with pytest.raises(ToolError, match="read_model"):
            functions["call_qtmodel_api"](api_object="mdb", method=method)
        query.assert_not_called()
    refresh.assert_not_called()


def test_mdb_gateway_section_recalculation_requires_write_permission(fake_provider):
    recalculate = Mock()
    refresh = Mock()
    fake_provider._mdb = SimpleNamespace(
        calculate_section_property=recalculate,
        update_model=refresh,
    )
    state = ready_model_state()
    state["model_state"]["capabilities"].update(
        read_model=True, modify_model=False, query_results=False,
    )
    fake_provider.get_model_state = lambda: state
    functions = tool_fns(register_api_gateway_tools, fake_provider)

    with pytest.raises(ToolError, match="modify_model"):
        functions["call_qtmodel_api"](
            api_object="mdb", method="calculate_section_property"
        )

    recalculate.assert_not_called()
    refresh.assert_not_called()


def test_analysis_results_still_use_odb(fake_provider):
    fake_provider.get_element_force(ids=[1], stage_id=-1, case_name="恒载")
    assert fake_provider._mdb.calls == []
    assert fake_provider._odb.last("get_element_force")[2] == {
        "ids": [1], "stage_id": -1, "case_name": "恒载",
    }
