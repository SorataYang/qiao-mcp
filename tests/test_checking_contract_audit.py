"""Use actual CDB request constructors for the checking audit regressions."""

import json
from typing import get_args

import pytest
from conftest import run_async_tool, tool_fns

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


@pytest.mark.parametrize("kind", ["shear_stirrup", "torsion_stirrup"])
@pytest.mark.parametrize("element_id,expected_ids", [(4, [4]), (5, []), (None, [4, 6])])
def test_stirrup_query_filters_native_rows_before_pagination(fake_provider, monkeypatch, kind, element_id, expected_ids):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    rows = [{"ele_id": 4}, {"ele_id": 6}]
    monkeypatch.setattr(QtServer, "send_command", staticmethod(lambda **kwargs: json.dumps(rows)))
    fake_provider._cdb = qtmodel.cdb
    result = tool_fns(register_checking_tools, fake_provider)["get_check_data"](
        kind=kind, element_id=element_id, limit=1,
    )
    assert [row["ele_id"] for row in result["data"]] == expected_ids[:1]
    assert result["pagination"]["total"] == len(expected_ids)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("kind", ["shear_stirrup", "torsion_stirrup"])
def test_stirrup_query_offset_applies_after_selection(fake_provider, kind):
    method = f"get_element_{kind}_data"
    setattr(fake_provider._cdb, method, lambda **kwargs: [{"ele_id": 4}, {"ele_id": 6}])
    result = tool_fns(register_checking_tools, fake_provider)["get_check_data"](
        kind=kind, element_id=6, offset=1,
    )
    assert result["data"] == []
    assert result["pagination"]["total"] == 1


@pytest.mark.parametrize("kind", ["shear_stirrup", "torsion_stirrup"])
@pytest.mark.parametrize("rows", [[{}], [{"ele_id": True}], {"ele_id": 4}])
def test_selected_stirrup_query_rejects_unverifiable_identity(fake_provider, kind, rows):
    setattr(fake_provider._cdb, f"get_element_{kind}_data", lambda **kwargs: rows)
    with pytest.raises(ToolError, match="verify.*element"):
        tool_fns(register_checking_tools, fake_provider)["get_check_data"](kind=kind, element_id=4)


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
        run_async_tool(functions["run_concrete_check"], name="C1")
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


@pytest.mark.parametrize("label", ["P1 (ST)", "ST:P1", "工况(左幅) (ST)"])
def test_check_combination_labels_and_query_selectors_are_not_rewritten(fake_provider, monkeypatch, label):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def reply(command="", header="", **kwargs):
        requests.append((header, json.loads(command) if command else {}))
        return "[]"

    monkeypatch.setattr(QtServer, "send_command", staticmethod(reply))
    fake_provider._cdb = qtmodel.cdb
    functions = tool_fns(register_checking_tools, fake_provider)
    functions["add_check_load_combination"](
        name="验算组合", kind=3, load_case_factors=[[label, 1.2, 0.9]],
    )
    functions["get_check_data"](kind="load_table", combine_type=1)
    assert requests[0][0] == "ADD-CHECK-LOAD-COMBINE"
    assert requests[0][1]["combine_type"] == 3
    assert requests[0][1]["combine_info"] == [[label, 1.2, 0.9]]
    assert requests[1][0] == "GET-CHECK-CASE-LOAD-TABLE-INFO"
    assert requests[1][1]["combine_type"] == 1
    assert "P1 (ST)" in functions["add_check_load_combination"].__doc__
    assert "definition kind" in functions["get_check_data"].__doc__


@pytest.mark.parametrize("name", [
    "add_parametric_reinforcement", "add_check_stirrup", "manage_check_stirrup",
    "assign_element_stirrup", "update_vertical_steel_tendon",
])
def test_definition_tools_distinguish_model_writes_from_csan_snapshots(fake_provider, name):
    doc = tool_fns(register_checking_tools, fake_provider)[name].__doc__
    assert "model checking definitions" in doc
    assert "CSAN snapshot" in doc


def test_check_setup_and_run_document_verified_lifecycle_limits(fake_provider):
    functions = tool_fns(register_checking_tools, fake_provider)
    assert "solved construction stage" in functions["setup_concrete_check"].__doc__
    assert "component_force_type" in functions["setup_concrete_check"].__doc__
    assert "case definition behind" in functions["setup_concrete_check"].__doc__
    assert "reuse an existing check file" in functions["run_concrete_check"].__doc__
    assert "do not regenerate" in functions["get_check_data"].__doc__
