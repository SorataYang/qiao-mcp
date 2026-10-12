"""Construction stage precision, sub-step forwarding and legacy compatibility."""

import inspect

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.group_management import register_group_tools

STAGES = [
    (register_modeling_tools, "add_construction_stage", "ADD-CONSTRUCTION-STAGE"),
    (register_group_tools, "update_construction_stage", "UPDATE-CONSTRUCTION-STAGE"),
]


@pytest.mark.parametrize("register, method, header", STAGES)
@pytest.mark.parametrize("sub_steps", [None, [], [0.25, 1.5]])
def test_stage_options_forwarded(fake_provider, register, method, header, sub_steps):
    tool_fns(register, fake_provider)[method](
        name="阶段", duration=2.75, sub_steps=sub_steps,
        active_structures=[["结构组", 2.25, 1, 1]],
    )
    kwargs = fake_provider._mdb.last(method)[2]
    assert kwargs["duration"] == 2.75
    assert kwargs["active_structures"] == [("结构组", 2.25, 1, 1)]
    if sub_steps is None:
        assert "sub_steps" not in kwargs
    else:
        assert kwargs["sub_steps"] == sub_steps
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("register, method, header", STAGES)
def test_legacy_stage_omits_options_and_rejects_sub_steps(fake_provider, register, method, header):
    calls = []

    def legacy(name, duration=0, new_name=""):
        calls.append(duration)

    setattr(fake_provider._mdb, method, legacy)
    function = tool_fns(register, fake_provider)[method]
    function(name="阶段", duration=2)
    assert calls == [2]
    fake_provider._mdb.calls.clear()
    for steps in ([], [0.25, 1.5]):
        with pytest.raises(ToolError, match="does not support.*sub_steps"):
            function(name="阶段", duration=2, sub_steps=steps)
    assert calls == [2]
    assert fake_provider._mdb.calls == []


def test_legacy_add_never_truncates_fractional_duration(fake_provider):
    calls = []

    def legacy(name, duration):
        calls.append(int(duration))

    fake_provider._mdb.add_construction_stage = legacy
    with pytest.raises(ToolError, match="fractional duration"):
        tool_fns(register_modeling_tools, fake_provider)["add_construction_stage"](
            name="阶段", duration=2.75,
        )
    assert calls == []
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("register, method, header", STAGES)
@pytest.mark.parametrize("duration, sub_steps", [(2, None), (2.75, None), (2.75, []), (2.75, [0.25, 1.5])])
def test_stage_real_wire(qtmodel_wire, register, method, header, duration, sub_steps):
    provider, requests = qtmodel_wire
    function = tool_fns(register, provider)[method]
    supports_steps = "sub_steps" in inspect.signature(getattr(provider._mdb, method)).parameters
    if not supports_steps and (sub_steps is not None or (method == "add_construction_stage" and duration == 2.75)):
        with pytest.raises(ToolError, match="does not support"):
            function(name="阶段", duration=duration, sub_steps=sub_steps)
        assert requests == []
        return

    function(name="阶段", duration=duration, sub_steps=sub_steps)
    payload = next(p for h, p in requests if h == header)
    assert payload["duration"] == duration
    if sub_steps is None:
        assert "sub_steps" not in payload
    else:
        # QiaoTong export: load_stage_replay_logs.json (not required at test runtime).
        assert payload["sub_steps"] == sub_steps
    assert len(requests) == 2  # write + update_model
