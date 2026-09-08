"""Plate thickness options remain explicit and compatible with older qtmodel builds."""

import inspect

import pytest
from conftest import tool_fns, tool_text

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError


def test_default_thickness_omits_optional_parameter(fake_provider):
    functions = tool_fns(register_modeling_tools, fake_provider)
    functions["add_thickness"](name="桥面板", t=0.2, index=3)

    assert fake_provider._mdb.last("add_thickness")[2] == {
        "name": "桥面板", "t": 0.2, "thick_type": 0, "index": 3,
    }
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("t_out", [0.0, 0.35])
def test_out_of_plane_thickness_is_forwarded_without_changing_plate_kind(fake_provider, t_out):
    functions = tool_fns(register_modeling_tools, fake_provider)
    result = functions["add_thickness"](name="桥面板", t=0.2, t_out=t_out)

    kwargs = fake_provider._mdb.last("add_thickness")[2]
    assert kwargs["t_out"] == t_out
    assert kwargs["t"] == 0.2
    assert kwargs["thick_type"] == 0
    assert fake_provider._mdb.count("update_model") == 1
    assert f"t_out={t_out}" in tool_text(result)


@pytest.mark.parametrize("t_out", [None, 0.0, 0.35])
def test_legacy_thickness_rejects_explicit_new_option_before_any_write(fake_provider, t_out):
    calls = []

    def legacy_add_thickness(name, t, thick_type, index):
        calls.append({"name": name, "t": t, "thick_type": thick_type, "index": index})

    fake_provider._mdb.add_thickness = legacy_add_thickness
    functions = tool_fns(register_modeling_tools, fake_provider)
    if t_out is None:
        functions["add_thickness"](name="桥面板", t=0.2, t_out=t_out)
        assert calls == [{"name": "桥面板", "t": 0.2, "thick_type": 0, "index": -1}]
        assert fake_provider._mdb.count("update_model") == 1
    else:
        with pytest.raises(ToolError, match="does not support.*t_out"):
            functions["add_thickness"](name="桥面板", t=0.2, t_out=t_out)
        assert calls == []
        assert fake_provider._mdb.calls == []


def test_thickness_tool_documents_correct_kind_and_optional_default(fake_provider):
    function = tool_fns(register_modeling_tools, fake_provider)["add_thickness"]
    assert inspect.signature(function).parameters["t_out"].default is None
    assert "0=普通板, 1=加劲肋板" in function.__doc__
