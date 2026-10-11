"""Edit diagnostics remain usable without model permissions and never prepare edits."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from conftest import tool_fns
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import _annotations_for, _operation_for, register_tools_with_envelope


@pytest.fixture
def diagnostic_provider(fake_provider, monkeypatch):
    monkeypatch.setattr(fake_provider, "get_connection_status", lambda: {
        "status": "connected", "connected": True, "compatible": True,
    })
    return fake_provider


@pytest.mark.parametrize("state", [
    {"status": "state_unknown"},
    {"status": "model_state", "model_state": {"model_opened": False, "capabilities": {}}},
    {"status": "model_state", "model_state": {"phase": "solving", "capabilities": {}}},
    {"status": "model_state", "model_state": {"phase": "postprocessing", "capabilities": {}}},
])
def test_readiness_ignores_model_guard_and_preserves_response(diagnostic_provider, state):
    p = diagnostic_provider
    p.get_model_state = Mock(return_value=state)
    # The response is intentionally opaque: do not invent a server field layout.
    raw = {"status": "blocked", "preparation_token": "opaque-token", "future_field": {"value": 3}}
    p._mdb.get_model_edit_readiness = Mock(return_value=raw)
    result = tool_fns(register_api_gateway_tools, p)["get_model_edit_readiness"]()
    assert result == {"status": "success", "readiness": raw}
    p.get_model_state.assert_not_called()
    assert p._mdb.calls == p._odb.calls == p._cdb.calls == []
    assert not any("token" in key for key in vars(p))


def test_missing_client_api_does_not_probe_or_send(diagnostic_provider):
    p = diagnostic_provider
    p._mdb = SimpleNamespace()
    p.get_connection_status = Mock(side_effect=AssertionError("Do not probe"))
    assert p.get_model_edit_readiness()["status"] == "api_unavailable"
    p.get_connection_status.assert_not_called()


@pytest.mark.parametrize("connection, expected", [
    ({"status": "software_not_running", "connected": False}, "not_connected"),
    ({"status": "version_mismatch", "connected": True, "compatible": False}, "not_connected"),
    ({"status": "probe_failed", "connected": False}, "probe_failed"),
    ({"status": "unknown"}, "not_connected"),
])
def test_connection_failure_never_sends_readiness(diagnostic_provider, connection, expected):
    p = diagnostic_provider
    p.get_connection_status = lambda: connection
    result = p.get_model_edit_readiness()
    assert result["status"] == expected
    assert result["connection"] == connection
    assert "readiness" not in result
    assert p._mdb.calls == []


@pytest.mark.parametrize("response", [None, "", {}, [], "unsupported command"])
def test_invalid_server_data_is_unknown_not_editable(diagnostic_provider, response):
    diagnostic_provider._mdb.get_model_edit_readiness = Mock(return_value=response)
    result = diagnostic_provider.get_model_edit_readiness()
    assert result["status"] == "state_unknown"
    assert "readiness" not in result


@pytest.mark.parametrize("error, status", [
    (NotImplementedError("unsupported"), "server_unsupported"),
    (TimeoutError("timeout"), "probe_failed"),
])
def test_probe_errors_do_not_become_ready(diagnostic_provider, error, status):
    diagnostic_provider._mdb.get_model_edit_readiness = Mock(side_effect=error)
    assert diagnostic_provider.get_model_edit_readiness()["status"] == status


def test_real_client_uses_readonly_header_and_preserves_unknown_fields(diagnostic_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    if not callable(getattr(qtmodel.mdb, "get_model_edit_readiness", None)):
        pytest.skip("Installed qtmodel has no edit readiness API")
    send = Mock(return_value='{"preparation_token":"一次性", "server_extension":[1,2]}')
    monkeypatch.setattr(QtServer, "send_command", send)
    diagnostic_provider._mdb = qtmodel.mdb
    result = diagnostic_provider.get_model_edit_readiness()
    assert result["readiness"] == {"preparation_token": "一次性", "server_extension": [1, 2]}
    send.assert_called_once_with(header="GET-MODEL-EDIT-READINESS", command="", read_timeout=600)


def test_readiness_schema_and_annotations(diagnostic_provider):
    mcp = FastMCP("readiness")
    register_tools_with_envelope(mcp, register_api_gateway_tools, diagnostic_provider)
    diagnostic_provider._mdb.get_model_edit_readiness = Mock(return_value={"opaque": 1})
    _, structured = asyncio.run(mcp.call_tool("get_model_edit_readiness", {}))
    assert structured["status"] == "success"
    assert structured["readiness"] == {"opaque": 1}
    tool = next(t for t in asyncio.run(mcp.list_tools()) if t.name == "get_model_edit_readiness")
    assert "readiness" in tool.outputSchema["properties"]
    assert _operation_for(tool.name) == "connection"
    assert _annotations_for(tool.name).readOnlyHint is True
    assert _annotations_for(tool.name).destructiveHint is False
