"""Gateway-only operation-stage and cascade parameters need no extra tools."""

import inspect

import pytest
from conftest import tool_fns, tool_text

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError

GATEWAY_OPTIONS = [
    ("update_operation_stage_setting", "UPDATE-OPERATION-STAGE-SETTING",
     {"do_analysis": True, "final_stage": "成桥", "static_load_cases": ["恒载"],
      "sink_load_cases": [], "live_load_cases": ["纵向活载"]}, "transversal_load_cases", ["横向活载"]),
    ("update_operation_stage_setting", "UPDATE-OPERATION-STAGE-SETTING",
     {"do_analysis": True, "final_stage": "成桥"}, "transversal_load_cases", []),
    ("remove_material", "REMOVE-MATERIAL", {"name": "材料"}, "cascade", False),
    ("remove_material", "REMOVE-MATERIAL", {"name": "材料"}, "cascade", True),
    ("remove_tendon_property", "REMOVE-TENDON-PROPERTY", {"name": "钢束特性"}, "cascade", False),
    ("remove_tendon_property", "REMOVE-TENDON-PROPERTY", {"name": "钢束特性"}, "cascade", True),
]


@pytest.mark.parametrize("method, header, base, key, value", GATEWAY_OPTIONS)
def test_gateway_options_are_discoverable_and_reach_real_wire(qtmodel_wire, method, header, base, key, value):
    provider, requests = qtmodel_wire
    functions = tool_fns(register_api_gateway_tools, provider)
    supported = key in inspect.signature(getattr(provider._mdb, method)).parameters
    listing = tool_text(functions["list_qtmodel_api"](api_object="mdb", pattern=method))
    assert method in listing
    assert (key in listing) == supported
    assert requests == []  # signature discovery is offline
    if not supported:
        with pytest.raises(ToolError, match="Real signature"):
            functions["call_qtmodel_api"](api_object="mdb", method=method, kwargs={**base, key: value})
        assert requests == []
        return

    functions["call_qtmodel_api"](api_object="mdb", method=method, kwargs={**base, key: value})
    payload = next(p for h, p in requests if h == header)
    assert payload[key] == value
    for name, expected in base.items():
        assert payload[name] == expected
    assert len(requests) == 2


@pytest.mark.parametrize("method, default", [("remove_material", True), ("remove_tendon_property", False)])
def test_cascade_upstream_defaults_are_not_overridden(qtmodel_wire, method, default):
    provider, requests = qtmodel_wire
    tool_fns(register_api_gateway_tools, provider)["call_qtmodel_api"](
        api_object="mdb", method=method, kwargs={"name": "指定对象"},
    )
    payload = next(p for h, p in requests if h == method.upper().replace("_", "-"))
    if "cascade" in inspect.signature(getattr(provider._mdb, method)).parameters:
        assert payload["cascade"] is default
    else:
        assert "cascade" not in payload
    assert len(requests) == 2


def test_gateway_documents_replacement_and_cascade_scope(fake_provider):
    functions = tool_fns(register_api_gateway_tools, fake_provider)
    doc = functions["call_qtmodel_api"].__doc__
    assert "transversal_load_cases" in doc
    assert "省略/空列表会关闭对应分析" in doc
    assert "cascade=True" in doc and "cascade=False" in doc
    assert "without a dialog" in doc
    assert "delete ALL" in doc
    assert "confirm the target and cascade scope" in doc
