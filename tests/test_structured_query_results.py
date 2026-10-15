"""Numeric results, provenance and pagination are machine-readable, without invented units."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.moving_load import register_moving_load_tools
from qiao_mcp.tools.queries import register_query_tools

COUNTS = dict(nodes=100000, elements=80000, materials=3, sections=4,
              construction_stages=5, load_cases=6, structure_groups=7, boundary_groups=8)


def test_summary_uses_one_native_query_and_keeps_source_fields(fake_provider):
    native = {"has_project": True, "counts": COUNTS, "phase": "preprocessing"}
    fake_provider._mdb = SimpleNamespace(get_model_summary=Mock(return_value=native))
    fake_provider.get_node_data = Mock(side_effect=AssertionError("must not fetch nodes"))
    result = fake_provider.get_model_summary()
    assert result["node_count"] == 100000 and result["stage_count"] == 5
    assert result["counts"] == COUNTS and result["summary_source"] == "native"
    fake_provider._mdb.get_model_summary.assert_called_once_with()
    fake_provider.get_node_data.assert_not_called()


@pytest.mark.parametrize("reply", [None, {}, {"counts": {"nodes": 0}}, {"counts": {**COUNTS, "nodes": True}}])
def test_invalid_native_summary_does_not_silently_fallback(fake_provider, reply):
    fake_provider._mdb.get_model_summary = Mock(return_value=reply)
    fake_provider.get_node_data = Mock(side_effect=AssertionError("no fallback on failure"))
    with pytest.raises(RuntimeError):
        fake_provider.get_model_summary()
    fake_provider.get_node_data.assert_not_called()


def test_absent_sdk_summary_retains_explicit_legacy_fallback(fake_provider):
    methods = ["get_node_data", "get_element_data", "get_material_data", "get_section_names",
               "get_stage_names", "get_load_case_names", "get_structure_group_names", "get_boundary_group_names"]
    fake_provider._mdb = SimpleNamespace(**{name: Mock(return_value=[]) for name in methods})
    fake_provider._odb = SimpleNamespace()
    assert fake_provider.get_model_summary()["summary_source"] == "legacy_collections"
    fake_provider._mdb.get_node_data.assert_called_once()


def test_analysis_result_preserves_numbers_case_and_page(fake_provider):
    fake_provider.get_element_force = Mock(return_value=[
        {"element_id": 1, "force_i": {"Fx": 1.25}}, {"element_id": 2, "force_i": {"Fx": -2.5}},
    ])
    snapshot = fake_provider.get_model_state()
    snapshot["model_state"].update(model_instance_id="model-a", model_revision="rev-a")
    fake_provider.get_model_state = Mock(return_value=snapshot)
    fn = tool_fns(register_modeling_tools, fake_provider)["get_analysis_results"]
    result = fn(result_type="force", case_name="Dead", limit=1, offset=1)
    assert result["data"] == [{"element_id": 2, "force_i": {"Fx": -2.5}}]
    assert result["pagination"] == {"scope": "local", "offset": 1, "limit": 1, "returned": 1, "total": 2, "next_offset": None}
    assert result["source"]["selectors"]["case_name"] == "ST:Dead"
    assert result["source"]["observed_model_instance_id"] == "model-a"
    assert result["units"] is None and result["coordinate_system"] is None
    assert "-2.5" in result["message"] and result["warnings"]
    # No extra probe to fabricate result provenance.
    fake_provider.get_model_state.assert_called_once()
    assert fake_provider.get_result_observation()["observed_model_instance_id"] is None


@pytest.mark.parametrize("registrar,operation,provider_method,arguments", [
    (register_query_tools, "get_model_data", "get_material_data", {"kind": "materials"}),
    (register_query_tools, "get_special_results", "get_vibration_modal_results", {"kind": "vibration_modal"}),
    (register_checking_tools, "get_check_data", "get_check_data", {"kind": "stress"}),
    (register_moving_load_tools, "get_live_load_results", "get_live_load_results", {"case_name": "MV:Truck"}),
])
def test_query_families_keep_structured_payload_and_known_metadata(fake_provider, registrar, operation, provider_method, arguments):
    data = {"items": [{"value": 2.5}], "units": {"value": "kN"}, "coordinate_system": "local"}
    setattr(fake_provider, provider_method, Mock(return_value=data))
    result = tool_fns(registrar, fake_provider)[operation](**arguments)
    assert result["data"] == data
    assert result["units"] == {"value": "kN"}
    assert result["source"]["operation"] == operation


def test_backend_page_is_not_sliced_twice(fake_provider):
    native = {"items": [{"id": 99}], "offset": 20, "limit": 1, "total": 30, "has_more": True}
    fake_provider.get_model_catalog_data = Mock(return_value=native)
    result = tool_fns(register_query_tools, fake_provider)["get_model_data"](
        kind="load_case_detail", ids=1, offset=20, limit=1,
    )
    assert result["data"] == native
    assert result["pagination"]["scope"] == "backend"
    assert result["pagination"]["next_offset"] == 21


def test_empty_results_remain_empty_not_zero(fake_provider):
    fake_provider.get_check_data = Mock(return_value=[])
    result = tool_fns(register_checking_tools, fake_provider)["get_check_data"](kind="stress")
    assert result["data"] == [] and result["pagination"]["total"] == 0
    assert any("does not prove a zero" in warning for warning in result["warnings"])
