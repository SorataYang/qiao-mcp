"""Compare adapted payloads and rejection behavior with the real SDK builders."""

import copy

import pytest

from qiao_mcp.providers.international_commands import call_model_command


@pytest.mark.parametrize("reply", [None, "", "done", '{"ok": true}', "[]"])
@pytest.mark.parametrize("method, definition", [
    ("add_international_vehicle", {"name": "车辆"}),
    ("add_international_live_load_case", {"name": "工况", "influence_plane": "影响面",
                                          "sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"]}]}),
])
def test_native_response_decoding_is_preserved(monkeypatch, reply, method, definition):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(QtServer, "send_command", lambda **kwargs: reply)
    command = getattr(qtmodel.mdb, method)
    assert call_model_command(command, method, definition) == command(**definition)


@pytest.mark.parametrize("action", ["add", "update"])
@pytest.mark.parametrize("family, definition", [
    ("vehicle", {"name": "车辆"}),
    ("vehicle", {"name": "车辆", "parameters": {"r": 95, "alpha": 1.1}, "r": 0,
                 "load_items": ((-100, 0),), "consider_point_load": True}),
    ("live_load_case", {"name": "工况", "influence_plane": "影响面",
                        "sub_cases": [{"vehicle_name": "车辆", "lane_names": ("车道",)}]}),
    ("live_load_case", {"name": "工况", "influence_plane": "影响面", "span": 0,
                        "sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"],
                                       "factor": 1.2, "optimized": False, "lane_count": 0}],
                        "highway_factor": {}, "railway_factor": None}),
])
def test_native_defaults_and_normalization_are_preserved(qtmodel_wire, action, family, definition):
    provider, calls = qtmodel_wire
    method = f"{action}_international_{family}"
    command = getattr(provider._mdb, method)
    kwargs = copy.deepcopy(definition)
    if action == "update":
        kwargs["new_name"] = "改名'\\\n"
    original = copy.deepcopy(kwargs)
    command(**kwargs)
    native_header, native_payload = calls.pop()
    assert native_payload.pop("version")
    call_model_command(command, method, kwargs)
    assert calls == [(native_header, native_payload)]
    assert kwargs == original


@pytest.mark.parametrize("family, definition", [
    ("vehicle", {"name": ""}),
    ("vehicle", {"name": "车辆", "vehicle_type": True}),
    ("vehicle", {"name": "车辆", "index": 0}),
    ("vehicle", {"name": "车辆", "parameters": {"unknown": 1}}),
    ("vehicle", {"name": "车辆", "load_items": [[100, -1]]}),
    ("vehicle", {"name": "车辆", "r": float("nan")}),
    ("live_load_case", {"span": -1}),
    ("live_load_case", {"save_sub_case_result": 1}),
    ("live_load_case", {"index": True}),
    ("live_load_case", {"sub_cases": []}),
    ("live_load_case", {"sub_cases": [{"vehicle_name": "车辆", "lane_names": []}]}),
    ("live_load_case", {"sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"], "factor": 0}]}),
    ("live_load_case", {"sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"], "optimized": 1}]}),
    ("live_load_case", {"sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"], "lane_count": True}]}),
    ("live_load_case", {"sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"], "unknown": 1}]}),
    ("live_load_case", {"highway_factor": []}),
])
def test_invalid_native_inputs_still_fail_before_transport(qtmodel_wire, family, definition):
    provider, calls = qtmodel_wire
    method = f"add_international_{family}"
    command = getattr(provider._mdb, method)
    kwargs = {"name": "工况", "influence_plane": "影响面",
              "sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"]}]} if family == "live_load_case" else {}
    kwargs.update(definition)
    with pytest.raises(ValueError):
        command(**kwargs)
    with pytest.raises(ValueError):
        call_model_command(command, method, kwargs)
    assert calls == []


def test_unrelated_sdk_commands_keep_their_transport(qtmodel_wire):
    provider, calls = qtmodel_wire
    call_model_command(provider._mdb.remove_international_vehicle, "remove_international_vehicle", {"name": "车辆"})
    assert calls[0][0] == "REMOVE-INTERNATIONAL-VEHICLE"
    assert "version" in calls[0][1]


def test_sdk_api_not_open_still_blocks_the_request(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    calls = []
    monkeypatch.setattr(QtServer, "_ensure_connection", lambda: calls.append("connection"))
    fake_provider._mdb = qtmodel.mdb
    with pytest.raises(NotImplementedError, match="API_NOT_OPEN"):
        fake_provider.set_planned_lane("add", {
            "name": "规划车道", "influence_name": "影响面", "tandem_name": "纵列", "lane_width": 3.5,
        })
    assert calls == []


def test_case_nonfinite_factor_is_rejected_during_serialization(qtmodel_wire):
    provider, calls = qtmodel_wire
    with pytest.raises(ValueError):
        call_model_command(provider._mdb.add_international_live_load_case, "add_international_live_load_case", {
            "name": "工况", "influence_plane": "影响面",
            "sub_cases": [{"vehicle_name": "车辆", "lane_names": ["车道"]}],
            "highway_factor": {"coefficient": float("inf")},
        })
    assert calls == []
