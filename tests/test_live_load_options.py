"""Live-load opt-ins preserve omitted/False/empty values and older signatures."""

import inspect

import pytest
from conftest import tool_fns

from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.moving_load import register_moving_load_tools

CASES = [
    ("add_influence_plane", "add_influence_plane", {"name": "面", "tandem_names": ["纵列"]},
     {"always_divided_by_beam_shape": False}),
    ("add_influence_plane", "add_influence_plane", {"name": "面", "tandem_names": ["纵列"]},
     {"always_divided_by_beam_shape": True}),
    ("create_live_load_case", "add_live_load_case",
     {"name": "活载", "influence_plane": "面", "span": 50,
      "sub_cases": [["车1", 1.25, ["车道1"]], ["车2", 0.5, ["车道2"]]]},
     {"sub_case_optimized": [False, True]}),
    ("create_live_load_case", "add_live_load_case",
     {"name": "活载", "influence_plane": "面", "span": 50, "sub_cases": []},
     {"sub_case_optimized": []}),
]


@pytest.mark.parametrize("tool, method, arguments, options", CASES)
def test_live_load_options_forwarded(fake_provider, tool, method, arguments, options):
    tool_fns(register_moving_load_tools, fake_provider)[tool](**arguments, **options)
    kwargs = fake_provider._mdb.last(method)[2]
    for key, value in options.items():
        assert kwargs[key] == value
    if "sub_cases" in arguments:
        assert kwargs["sub_case"] == [tuple(case) for case in arguments["sub_cases"]]


@pytest.mark.parametrize("tool, method, arguments, options", CASES)
def test_legacy_live_load_rejects_options_without_writing(fake_provider, tool, method, arguments, options):
    calls = []

    def legacy_plane(name, tandem_names):
        calls.append(name)

    def legacy_case(name, influence_plane, span, sub_case):
        calls.append(name)

    setattr(fake_provider._mdb, method, legacy_plane if method == "add_influence_plane" else legacy_case)
    function = tool_fns(register_moving_load_tools, fake_provider)[tool]
    function(**arguments)
    assert calls == [arguments["name"]]
    fake_provider._mdb.calls.clear()
    with pytest.raises(ToolError, match="does not support"):
        function(**arguments, **options)
    assert calls == [arguments["name"]]
    assert fake_provider._mdb.calls == []


def test_sub_case_flags_must_match_case_count(fake_provider):
    with pytest.raises(ToolInputError, match="same length"):
        tool_fns(register_moving_load_tools, fake_provider)["create_live_load_case"](
            name="活载", influence_plane="面", span=50,
            sub_cases=[["车", 1.25, ["车道"]]], sub_case_optimized=[],
        )
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("tool, method, arguments, options", CASES)
def test_live_load_real_wire(qtmodel_wire, tool, method, arguments, options):
    provider, requests = qtmodel_wire
    function = tool_fns(register_moving_load_tools, provider)[tool]
    parameters = inspect.signature(getattr(provider._mdb, method)).parameters
    if not options.keys() <= parameters.keys():
        with pytest.raises(ToolError, match="does not support"):
            function(**arguments, **options)
        assert requests == []
        return

    function(**arguments, **options)
    payload = next(p for h, p in requests if h == method.upper().replace("_", "-"))
    for key, value in options.items():
        assert payload[key] == value
    if "sub_cases" in arguments:
        # live_load_loop_logs.json uses a parallel bool list, not a fourth tuple field.
        assert payload["sub_case"] == arguments["sub_cases"]
