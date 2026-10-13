"""Use actual CDB request constructors for the checking audit regressions."""

import json
from typing import get_args

import pytest
from conftest import tool_fns

from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.schemas import CheckDataKind


@pytest.mark.parametrize("kind", get_args(CheckDataKind))
def test_every_check_query_binds_to_real_sdk(fake_provider, monkeypatch, kind):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def reply(command="", header="", **kwargs):
        requests.append((header, json.loads(command) if command else {}))
        return "[]"

    monkeypatch.setattr(QtServer, "send_command", staticmethod(reply))
    fake_provider._cdb = qtmodel.cdb
    functions = tool_fns(register_checking_tools, fake_provider)
    functions["get_check_data"](kind=kind)
    assert len(requests) == 1
    assert requests[0][0].startswith("GET-")
    assert fake_provider._mdb.calls == []
    if kind not in {"stress", "load_table", "case", "shear_stirrup", "torsion_stirrup"}:
        assert not ({"name", "element_id", "stress_type", "combine_type"} & requests[0][1].keys())


def test_case_query_passes_only_its_supported_name(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def reply(header="", payload=None, **kwargs):
        requests.append((header, payload))
        return [{"name": "Chosen"}]

    monkeypatch.setattr(QtServer, "send_dict", staticmethod(reply))
    fake_provider._cdb = qtmodel.cdb
    functions = tool_fns(register_checking_tools, fake_provider)
    functions["get_check_data"](kind="case", name="Chosen")
    assert requests == [("GET-CONCRETE-CHECK-CASE", {"name": "Chosen"})]


def test_typed_check_records_remain_objects_after_pagination(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    rows = [{"ele_id": n, "stirrup_i_y": 2, "stirrup_i_x": 3, "stirrup_j_y": 4, "stirrup_j_x": 5}
            for n in (7, 8)]
    monkeypatch.setattr(QtServer, "send_command", staticmethod(lambda **kwargs: json.dumps(rows)))
    fake_provider._cdb = qtmodel.cdb
    result = tool_fns(register_checking_tools, fake_provider)["get_check_data"](
        kind="shear_stirrup", limit=1, offset=1,
    )
    page = json.loads(result["message"].split("\n", 2)[2])
    assert page == [rows[1]]


@pytest.mark.parametrize("status", [
    None, {}, "", "success", {"is_running": False},
    {"state": "succeeded", "ok": False},
    {"state": "succeeded", "is_running": True},
])
def test_check_completion_requires_unambiguous_success(fake_provider, status):
    calls = []

    def stopped(**kwargs):
        calls.append(kwargs)
        return status

    fake_provider._cdb.solve_concrete_check = stopped
    functions = tool_fns(register_checking_tools, fake_provider)
    with pytest.raises(ToolError, match="did not complete"):
        functions["run_concrete_check"](name="C1")
    assert len(calls) == 1


def test_check_setting_sends_defaults_and_reports_replacement(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def reply(header="", payload=None, **kwargs):
        requests.append((header, payload))

    monkeypatch.setattr(QtServer, "send_dict", staticmethod(reply))
    fake_provider._cdb = qtmodel.cdb
    functions = tool_fns(register_checking_tools, fake_provider)
    result = functions["configure_check_analysis"](kind="limit_state", settings={"cal_fatigue": True})
    assert requests[0] == ("UPDATE-LIMIT-STATE-METHOD-ANALYSIS-SETTING", {
        "cal_fatigue": True, "fatigue_limit_steel_bar": 145.0,
        "fatigue_limit_prestress": 150.0, "is_consider_as_simple_support": False,
        "is_consider_construction_load": False,
    })
    assert requests[1][0] == "SAVE-CHECK-CASE"
    assert "omitted fields use SDK defaults" in result["message"]


@pytest.mark.parametrize("rows", [[["C1", 1, 1, 9]], [["C1", 1]]])
def test_check_combinations_do_not_drop_extra_columns(fake_provider, rows):
    with pytest.raises(ToolError, match="load_case_factors"):
        tool_fns(register_checking_tools, fake_provider)["add_check_load_combination"](
            name="Combination", load_case_factors=rows,
        )
    assert fake_provider._cdb.calls == []
