"""0687ffe long-tail methods and changed concrete-check transport via the facade."""

import copy
import inspect
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolError

CALLS = json.loads((Path(__file__).parent / "fixtures/upstream_model_commands.json").read_text())["calls"]


def supported_or_rejected(p, calls, method, kwargs):
    """An absent/incompatible API must fail before any request, including on old wheels."""
    fn = getattr(p._mdb, method, None)
    reason = "has no method"
    if callable(fn):
        try:
            inspect.signature(fn).bind(**kwargs)
            return True
        except TypeError:
            reason = "Arguments do not match"
    with pytest.raises(ToolError, match=reason):
        tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert calls == []
    return False


@pytest.mark.parametrize("entry", CALLS, ids=lambda c: c["method"])
def test_exported_model_commands_commit_once_through_real_gateway(qtmodel_wire, entry):
    p, calls = qtmodel_wire
    method, kwargs = entry["method"], copy.deepcopy(entry["kwargs"])
    if not supported_or_rejected(p, calls, method, kwargs):
        return
    tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert [h for h, _ in calls] == [method.upper().replace("_", "-"), "UPDATE"]
    payload = calls[0][1]
    for key, value in kwargs.items():
        assert payload[key] == value


@pytest.mark.parametrize("method, kwargs, expected", [
    ("get_element_weight", {"ids": [1, 2]}, {"1": 50000.0, "2": 0.0}),
    ("get_element_weight_table", {"ids": [1]}, [{"element_id": 1, "geometry_size_unit": "m", "element_weight": 50000.0}]),
    ("get_load_statistics", {"case_names": ["恒载"]}, [{"case_id": 1, "case_name": "恒载", "fx": 0, "fy": 20, "fz": -100}]),
    ("get_material_statistics", {}, [{"material_id": 1, "material_name": "C55", "total_weight": 75000.0}]),
    ("get_mass_factor", {"indices": None}, [{"index": 3, "factor": 0, "group_names": ["主梁"], "effective_element_ids": [1, 2]}]),
    ("get_mass_factor", {"indices": []}, []),
    ("get_stiffness_factor", {"indices": [1]}, [{"index": 1, "factor": .8, "element_count": 3}]),
    ("get_flange_width", {"section_ids": None}, [{"section_id": 10, "end_j": {"b0": .4}, "future": True}]),
    ("get_flange_width_lines", {"section_id": 10, "position": 1}, [{"line_id": 4, "length": .5}]),
    ("get_effective_width_spans", {}, [{"span_id": 7, "future": {"retained": True}}]),
])
def test_new_queries_need_read_permission_only_and_retain_native_results(fake_provider, monkeypatch, method, kwargs, expected):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        return json.dumps(expected)

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._mdb = qtmodel.mdb
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: state
    if not supported_or_rejected(fake_provider, calls, method, kwargs):
        return
    result = tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert json.loads(result["message"].split("\n", 1)[1]) == expected
    assert [h for h, _ in calls] == [method.upper().replace("_", "-")]


@pytest.mark.parametrize("method, kwargs", [
    ("merge_node_groups", {"node_groups": [[1, 2], [3, 4]]}),
    ("merge_plate_elements", {"ids": [1, 2]}),
    ("merge_frame_elements", {"ids": [1, 2], "delete_free_nodes": False, "accept_warnings": True}),
    ("set_element_factor", {"kind": "mass", "index": 3, "name": "系数", "factor": 0, "element_ids": [2]}),
    ("remove_element_factor", {"kind": "stiffness", "indices": [1]}),
    ("update_mass_factor", {"index": 3, "factor": 0}),
    ("update_stiffness_factor", {"index": 1, "group_names": ["主梁"]}),
])
def test_other_new_mutators_preserve_zero_none_and_merge_flags(qtmodel_wire, method, kwargs):
    p, calls = qtmodel_wire
    if not supported_or_rejected(p, calls, method, kwargs):
        return
    tool_fns(register_api_gateway_tools, p)["call_qtmodel_api"](api_object="mdb", method=method, kwargs=kwargs)
    assert [h for h, _ in calls] == [method.upper().replace("_", "-"), "UPDATE"]
    for key, value in kwargs.items():
        assert calls[0][1][key] == value
    if method == "update_mass_factor":
        assert calls[0][1]["element_ids"] is calls[0][1]["group_names"] is None
    if method == "update_stiffness_factor":
        assert calls[0][1]["element_ids"] == []
        assert calls[0][1]["factor"] is None


@pytest.mark.parametrize("method", ["calculate_effective_width", "set_flange_width", "merge_frame_elements", "update_mass_factor"])
def test_new_mutators_are_never_mistaken_for_readonly_calculations(fake_provider, method):
    state = ready_model_state()
    state["model_state"]["capabilities"]["modify_model"] = False
    fake_provider.get_model_state = lambda: state
    writer = Mock()
    setattr(fake_provider._mdb, method, writer)
    with pytest.raises(ToolError, match="modify_model"):
        tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"](api_object="mdb", method=method)
    writer.assert_not_called()
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "canceled"])
def test_named_concrete_check_uses_supported_background_signature(fake_provider, monkeypatch, outcome):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    calls = []

    def send(command="", header="", read_timeout=600):
        calls.append((header, json.loads(command) if command else None))
        if header == "GET-CONCRETE-CHECK-SOLVE-STATUS":
            return json.dumps({"state": outcome, "is_running": False, "message": "native outcome"})
        return json.dumps({"state": "running"}) if header == "SOLVE-CONCRETE-CHECK" else ""

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._cdb = qtmodel.cdb
    run = tool_fns(register_checking_tools, fake_provider)["run_concrete_check"]
    if outcome == "succeeded":
        assert run(name="具名检算", max_wait_seconds=12)["status"] == "success"
    else:
        with pytest.raises(ToolError, match=outcome):
            run(name="具名检算", max_wait_seconds=12)
    assert [h for h, _ in calls] == ["IMPORT-CONCRETE-CHECK-CASE", "SOLVE-CONCRETE-CHECK", "GET-CONCRETE-CHECK-SOLVE-STATUS"]
    assert calls[0][1]["case_name"] == "具名检算"
    assert not {"sync", "show_view", "modal", "auto_close"} & (calls[1][1] or {}).keys()
    assert fake_provider._mdb.calls == []


def test_removed_cdb_window_options_follow_actual_signature(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    send = Mock(return_value="")
    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._cdb = qtmodel.cdb
    call = tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"]
    if "show_view" in inspect.signature(qtmodel.cdb.solve_concrete_check).parameters:
        call(api_object="cdb", method="solve_concrete_check", kwargs={"show_view": True})
        assert send.call_args.kwargs["header"] == "SHOW-CONCRETE-CHECK-ANALYSIS-VIEW"
    else:
        with pytest.raises(ToolError, match="Arguments do not match"):
            call(api_object="cdb", method="solve_concrete_check", kwargs={"show_view": True})
        send.assert_not_called()
    assert fake_provider._mdb.calls == []


def test_new_csan_reinforcement_removal_is_distinct_from_model_snapshot(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    send = Mock(return_value="")
    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._cdb = qtmodel.cdb
    call = tool_fns(register_api_gateway_tools, fake_provider)["call_qtmodel_api"]
    if not callable(getattr(qtmodel.cdb, "remove_section_reinforcement", None)):
        with pytest.raises(ToolError, match="has no method"):
            call(api_object="cdb", method="remove_section_reinforcement", kwargs={"sec_id": 7, "position": 1})
        send.assert_not_called()
    else:
        call(api_object="cdb", method="remove_section_reinforcement", kwargs={"sec_id": 7, "position": 1})
        assert send.call_args.kwargs["header"] == "REMOVE-SECTION-REINFORCEMENT"
        payload = json.loads(send.call_args.kwargs["command"])
        assert payload["sec_id"] == 7 and payload["position"] == 1
    assert fake_provider._mdb.calls == []
