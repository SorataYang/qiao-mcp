"""A transient discovery timeout must not become a stale permission decision."""

from unittest.mock import Mock

import pytest
from conftest import ready_model_state

from qiao_mcp.providers.qtmodel_provider import QtModelProvider

DISCONNECTED = {
    "status": "software_not_running", "connected": False, "compatible": None,
    "message": "未发现桥通 HTTP 服务。",
}
CONNECTED = {"status": "connected", "connected": True, "compatible": True}


@pytest.fixture
def provider_and_sleep(monkeypatch):
    provider = QtModelProvider.__new__(QtModelProvider)
    provider._available = True
    sleep = Mock()
    monkeypatch.setattr("qiao_mcp.providers.qtmodel_provider.time.sleep", sleep)
    return provider, sleep


def test_connection_recovers_after_one_missing_probe(provider_and_sleep, monkeypatch):
    from qtmodel.core.qt_server import QtServer

    provider, sleep = provider_and_sleep
    probe = Mock(side_effect=[DISCONNECTED, CONNECTED])
    monkeypatch.setattr(QtServer, "get_connection_status", probe)

    assert provider.get_connection_status() == CONNECTED
    assert probe.call_count == 2
    sleep.assert_called_once_with(0.1)


def test_recovered_state_still_blocks_postprocessing_writes(provider_and_sleep, monkeypatch):
    from qtmodel.core.qt_server import QtServer

    provider, sleep = provider_and_sleep
    state = ready_model_state()
    state["model_state"].update(phase="postprocessing", has_result_data=True)
    state["model_state"]["capabilities"]["modify_model"] = False
    probe = Mock(side_effect=[DISCONNECTED, state])
    monkeypatch.setattr(QtServer, "get_model_state", probe, raising=False)
    provider._probe_cache = CONNECTED

    with pytest.raises(RuntimeError, match="capability=modify_model"):
        provider.ensure_operation_allowed("model_write")
    assert probe.call_count == 2
    sleep.assert_called_once_with(0.1)


@pytest.mark.parametrize("method", ["get_connection_status", "get_model_state"])
def test_persistent_disconnect_is_bounded_and_remains_unavailable(provider_and_sleep, monkeypatch, method):
    from qtmodel.core.qt_server import QtServer

    provider, sleep = provider_and_sleep
    probe = Mock(return_value=DISCONNECTED)
    monkeypatch.setattr(QtServer, method, probe, raising=False)

    assert getattr(provider, method)() == DISCONNECTED
    assert probe.call_count == 2
    sleep.assert_called_once_with(0.1)


@pytest.mark.parametrize("status", [
    CONNECTED,
    {"status": "version_mismatch", "connected": True, "compatible": False},
    {"status": "state_unknown", "connected": True},
    {"status": "probe_failed", "connected": False},
])
def test_other_probe_results_are_not_retried(provider_and_sleep, monkeypatch, status):
    from qtmodel.core.qt_server import QtServer

    provider, sleep = provider_and_sleep
    probe = Mock(return_value=status)
    monkeypatch.setattr(QtServer, "get_model_state", probe, raising=False)

    assert provider.get_model_state() == status
    assert probe.call_count == 1
    sleep.assert_not_called()
