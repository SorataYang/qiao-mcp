"""Opt-in orthotropic material properties retain older MDB call signatures."""

import inspect

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolError

OPTIONS = [{}, {"is_orthotropic": False}, {"is_orthotropic": True}, {"ey": 2.8e10},
           {"is_orthotropic": True, "ey": 2.8e10}]


@pytest.mark.parametrize("options", OPTIONS)
def test_material_options_forwarded(fake_provider, options):
    tool_fns(register_modeling_tools, fake_provider)["create_material"](
        name="材料", mat_type=1, database="C50", **options,
    )
    kwargs = fake_provider._mdb.last("add_material")[2]
    assert kwargs == {"name": "材料", "mat_type": 1, "standard": 1, "database": "C50", **options}
    assert fake_provider._mdb.count("update_model") == 1


def test_legacy_material_keeps_default_and_rejects_each_new_option(fake_provider):
    calls = []

    def legacy(name, mat_type, standard, database):
        calls.append(name)

    fake_provider._mdb.add_material = legacy
    function = tool_fns(register_modeling_tools, fake_provider)["create_material"]
    function(name="材料", mat_type=1, database="C50")
    assert calls == ["材料"]
    fake_provider._mdb.calls.clear()
    for options in OPTIONS[1:]:
        with pytest.raises(ToolError, match="does not support"):
            function(name="材料", mat_type=1, database="C50", **options)
    assert calls == ["材料"]
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("options", OPTIONS)
def test_material_real_wire(qtmodel_wire, options):
    provider, requests = qtmodel_wire
    function = tool_fns(register_modeling_tools, provider)["create_material"]
    parameters = inspect.signature(provider._mdb.add_material).parameters
    arguments = {"name": "正交材料", "mat_type": 5, "data_info": [3.5e10, 2.5e4, 0.2, 1.5e-5]}
    if not options.keys() <= parameters.keys():
        with pytest.raises(ToolError, match="does not support"):
            function(**arguments, **options)
        assert requests == []
        return

    function(**arguments, **options)
    payload = next(p for h, p in requests if h == "ADD-MATERIAL")
    assert payload["data_info"] == arguments["data_info"]
    for key, value in options.items():
        assert payload[key] == value
    assert len(requests) == 2
