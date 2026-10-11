"""Offline international workflow ordering, not a bridge/numerical acceptance test."""

import asyncio
import copy
from unittest.mock import AsyncMock

import pytest
from conftest import ready_model_state
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import ToolError


@pytest.mark.parametrize("standard, system, native_system", [
    ("AASHTO", "aashto", 1), ("BS", "bs", 3), ("EN1991", "en1991", 4),
])
def test_definition_commit_references_explicit_solve_and_full_result_name(fake_provider, standard, system, native_system):
    p = fake_provider
    records = {"vehicles": {}, "cases": {}, "planned": {}, "settings": {}}
    pending = []
    current_system = None
    # Ordinary and planned lanes can have the same name. The case must use the
    # planned namespace when optimized=True; this is distinct from optimize on
    # the older ordinary-lane definition.
    ordinary_lanes = {"车道": {"influence_name": "另一个影响面", "optimize": True}}
    state = ready_model_state()
    state["model_state"]["capabilities"]["query_results"] = False
    p.get_model_state = lambda: state

    def record_call(method, kwargs):
        p._mdb.calls.append((method, (), copy.deepcopy(kwargs)))

    def configure_system(**kwargs):
        nonlocal current_system
        assert kwargs == {"kind": native_system, "clear_existing": False}
        record_call("set_live_load_type", kwargs)
        current_system = kwargs["kind"]

    def commit():
        record_call("update_model", {})
        for family, name, definition in pending:
            records[family][name] = definition
        pending.clear()

    def make_vehicle_writer(factory=False):
        method = "add_international_user_vehicle" if factory else "add_international_vehicle"

        def write(**kwargs):
            assert current_system == native_system
            if not factory:
                assert kwargs["standard"] == standard
            record_call(method, kwargs)
            pending.append(("vehicles", kwargs["name"], {**kwargs, "index": 907, "standard": standard}))
        return write

    def write_lane(**kwargs):
        assert kwargs["influence_name"] == "影响面" and kwargs["tandem_name"] == "纵列"
        record_call("add_planned_lane_line", kwargs)
        pending.append(("planned", kwargs["name"], kwargs))

    def write_case(**kwargs):
        assert not pending
        assert kwargs["influence_plane"] == "影响面"
        for sub_case in kwargs["sub_cases"]:
            assert sub_case["vehicle_name"] in records["vehicles"]
            lanes = records["planned"] if sub_case["optimized"] else ordinary_lanes
            assert all(lanes[name]["influence_name"] == kwargs["influence_plane"] for name in sub_case["lane_names"])
        record_call("add_international_live_load_case", kwargs)
        pending.append(("cases", kwargs["name"], {**kwargs, "index": 38}))

    def write_settings(**kwargs):
        assert not pending and kwargs["live_load_cases"] == ["国际工况"]
        record_call("update_operation_stage_setting", kwargs)
        pending.append(("settings", "operation", kwargs))

    def solve(**kwargs):
        assert not pending and records["settings"]["operation"]["live_load_cases"] == ["国际工况"]
        assert kwargs["sync"] is False
        record_call("do_solve", kwargs)
        state["model_state"]["capabilities"]["query_results"] = True
        state["model_state"]["has_result_data"] = True
        return {"state": "completed"}

    p._mdb.set_live_load_type = configure_system
    p._mdb.update_model = commit
    p._mdb.add_international_vehicle = make_vehicle_writer()
    p._mdb.add_international_user_vehicle = make_vehicle_writer(factory=True)
    p._mdb.add_planned_lane_line = write_lane
    p._mdb.add_international_live_load_case = write_case
    p._mdb.get_international_vehicles = lambda: list(records["vehicles"].values())
    p._mdb.get_international_live_load_cases = lambda: list(records["cases"].values())
    p._mdb.update_operation_stage_setting = write_settings
    p._mdb.do_solve = solve
    mcp = FastMCP("international-flow")
    register_tool_catalog(mcp, p)
    fns = {t.name: t.fn for t in mcp._tool_manager.list_tools()}

    fns["configure_live_load_system"](system=system)
    if standard == "EN1991":
        vehicle = fns["create_en1991_vehicle"](request={
            "source": "user", "name": "车辆", "load_type": "LM71", "p": [250, 250], "dis": [1.6, 0],
        })
    else:
        vehicle = fns["set_international_vehicle"](request={
            "action": "add", "name": "车辆", "standard": standard, "vehicle_type": 0,
            "definition_mode": 1, "parameters": {"r": 90, "w": 9340} if standard == "AASHTO" else {"pa": 120, "w3": 9}, "load_items": [],
        })
    assert vehicle["data"]["index"] == 907
    lane = fns["set_planned_lane"](request={
        "action": "add", "name": "车道", "influence_name": "影响面", "tandem_name": "纵列",
        "lane_width": 3.5, "vehicle_number": 2, "offset": -1.5, "direction": 1,
    })
    assert lane["committed"] and "data" not in lane
    case = fns["set_international_live_load_case"](request={
        "action": "add", "name": "国际工况", "standard": standard, "influence_plane": "影响面", "span": 0,
        "sub_cases": [{"vehicle_name": vehicle["data"]["name"], "lane_names": ["车道"], "optimized": True}],
    })
    assert case["data"]["index"] == 38
    fns["configure_operation_stage"](
        final_stage="成桥", static_load_cases=["恒载"], sink_load_cases=[],
        live_load_cases=[case["data"]["name"]], transversal_load_cases=[],
    )
    assert p._mdb.count("update_model") == 5
    assert p._mdb.count("set_live_load_type") == 1
    assert p._mdb.count("do_solve") == 0
    with pytest.raises(ToolError):
        fns["get_analysis_results"](result_type="force", case_name="verified-result-id", case_name_mode="full")
    asyncio.run(fns["run_analysis"](ctx=AsyncMock(), read_timeout=60))
    assert p._mdb.count("do_solve") == 1
    for kind, method in [("force", "get_element_force"), ("deformation", "get_deformation"), ("reaction", "get_reaction")]:
        fns["get_analysis_results"](result_type=kind, ids=[7], case_name="verified-result-id", case_name_mode="full")
        assert p._odb.last(method)[2] == {"ids": [7], "stage_id": -1, "case_name": "verified-result-id"}
