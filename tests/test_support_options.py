"""Support options follow QiaoTong's eight-field and signed-axis export layouts."""

import inspect
from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from qiao_mcp.tools.envelope import ToolError, ToolInputError

SUPPORTS = [
    (register_modeling_tools, "set_support", "add_general_support", {}),
    (register_advanced_boundary_tools, "add_elastic_support", "add_elastic_support",
     {"spring_values": [2, 200], "support_type": 2}),
]
OPTIONS = [{}, {"coordinate": 0}, {"coordinate": 1}, {"extra_enabled": False},
           {"extra_enabled": True}, {"extra_parameters": [0] * 8},
           {"coordinate": 0, "extra_enabled": True, "extra_parameters": [0.1, 0.2, 1, 2, 3, 4, 5, 6]}]


@pytest.mark.parametrize("register, tool, method, arguments", SUPPORTS)
@pytest.mark.parametrize("options", OPTIONS)
def test_support_options_forwarded(fake_provider, register, tool, method, arguments, options):
    tool_fns(register, fake_provider)[tool](node_id=8, **arguments, **options)
    kwargs = fake_provider._mdb.last(method)[2]
    for key in ("coordinate", "extra_enabled", "extra_parameters"):
        if key == "extra_enabled" and "extra_parameters" in options and key not in options:
            assert kwargs[key] is True
        elif key in options:
            assert kwargs[key] == options[key]
        else:
            assert key not in kwargs
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("register, tool, method, arguments", SUPPORTS)
def test_legacy_support_rejects_options_before_writing(fake_provider, register, tool, method, arguments):
    calls = []

    def legacy(node_id, boundary_info, support_type=1):
        calls.append(node_id)

    setattr(fake_provider._mdb, method, legacy)
    function = tool_fns(register, fake_provider)[tool]
    function(node_id=8, **arguments)
    assert calls == [8]
    fake_provider._mdb.calls.clear()
    options_list = OPTIONS[1:]
    if method == "add_elastic_support":
        options_list = [*options_list, {"axis_direction": 3}]
    for options in options_list:
        with pytest.raises(ToolError, match="does not support"):
            function(node_id=8, **arguments, **options)
    assert calls == [8]
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("axis", range(6))
def test_signed_axis_including_zero_is_forwarded(fake_provider, axis):
    tool_fns(register_advanced_boundary_tools, fake_provider)["add_elastic_support"](
        node_id=9, support_type=3, spring_values=[axis // 2 + 1, 200], axis_direction=axis,
    )
    assert fake_provider._mdb.last("add_elastic_support")[2]["axis_direction"] == axis


@pytest.mark.parametrize("support_type, spring_values, axis", [(1, [0] * 6, 0), (2, [2, 200], 0)])
def test_signed_axis_must_match_unidirectional_support(fake_provider, support_type, spring_values, axis):
    with pytest.raises(ToolInputError, match="axis_direction"):
        tool_fns(register_advanced_boundary_tools, fake_provider)["add_elastic_support"](
            node_id=9, support_type=support_type, spring_values=spring_values, axis_direction=axis,
        )
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("register, tool, method, arguments", SUPPORTS)
@pytest.mark.parametrize("extra_enabled", [False, True])
def test_support_real_export_wire(qtmodel_wire, register, tool, method, arguments, extra_enabled):
    provider, requests = qtmodel_wire
    # structure_boundary_replay_logs.json / elastic_support_replay.json export layout.
    options = {"coordinate": 0, "extra_enabled": extra_enabled,
               "extra_parameters": [0.1, 0.2, 1, 2, 3, 4, 5, 6]}
    if method == "add_elastic_support":
        options["axis_direction"] = 3
    function = tool_fns(register, provider)[tool]
    parameters = inspect.signature(getattr(provider._mdb, method)).parameters
    if not options.keys() <= parameters.keys():
        with pytest.raises(ToolError, match="does not support"):
            function(node_id=8, **arguments, **options)
        assert requests == []
        return

    function(node_id=8, **arguments, **options)
    header = method.upper().replace("_", "-")
    payload = next(p for h, p in requests if h == header)
    for key, value in options.items():
        assert payload[key] == value
    expected_boundary = arguments.get("spring_values", [True, True, True, False, False, False])
    assert payload["boundary_info"] == expected_boundary
    assert len(requests) == 2


@pytest.mark.parametrize("register, tool, method, arguments", SUPPORTS)
def test_parameter_only_input_explicitly_enables_it_on_every_supporting_sdk(qtmodel_wire, register, tool, method, arguments):
    provider, requests = qtmodel_wire
    options = {"extra_parameters": [0.2, 0.1, 0, 0, 0, 0, 0, 0]}
    parameters = inspect.signature(getattr(provider._mdb, method)).parameters
    function = tool_fns(register, provider)[tool]
    if not {"extra_enabled", "extra_parameters"} <= parameters.keys():
        with pytest.raises(ToolError, match="does not support"):
            function(node_id=8, **arguments, **options)
        assert requests == []
        return
    function(node_id=8, **arguments, **options)
    assert requests[0][1]["extra_enabled"] is True
    assert requests[0][1]["extra_parameters"] == options["extra_parameters"]
    assert requests[1][0] == "UPDATE" and len(requests) == 2


@pytest.mark.parametrize("register, tool, method, arguments", SUPPORTS)
def test_support_commit_failure_does_not_claim_no_change(fake_provider, register, tool, method, arguments):
    commit = Mock(side_effect=RuntimeError("commit unavailable"))
    fake_provider._mdb.update_model = commit
    with pytest.raises(ToolError, match="model may have changed"):
        tool_fns(register, fake_provider)[tool](node_id=8, **arguments, extra_parameters=[0] * 8)
    assert fake_provider._mdb.count(method) == 1
    commit.assert_called_once()
