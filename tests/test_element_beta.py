"""Use the beta field accepted by the live UPDATE-ELEMENT-BETA route."""

import pytest
from conftest import tool_fns

from qiao_mcp.tools.modifications import register_modification_tools


@pytest.mark.parametrize("ids, expected", [(7, [7]), ([9, 7], [9, 7]), ("7to9", [7, 8, 9])])
def test_beta_payload_targets_the_requested_elements(qtmodel_wire, ids, expected):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)["update_element_beta"](ids=ids, beta=30)
    assert [header for header, _ in requests] == ["UPDATE-ELEMENT-BETA", "UPDATE"]
    payload = requests[0][1]
    assert payload["ids"] == expected
    assert payload["beta"] == 30
    assert "beta_angle" not in payload


@pytest.mark.parametrize("beta", [float("nan"), float("inf"), True])
def test_invalid_beta_is_rejected_before_writing(qtmodel_wire, beta):
    provider, requests = qtmodel_wire
    with pytest.raises(ValueError, match="finite"):
        provider.update_element_beta([7], beta)
    assert requests == []


def test_failed_beta_write_is_not_replayed_or_committed(qtmodel_wire, monkeypatch):
    from qtmodel.core.qt_server import QtServer

    provider, requests = qtmodel_wire
    calls = []

    def fail(header, payload):
        calls.append((header, payload))
        raise TimeoutError("reply lost")

    monkeypatch.setattr(QtServer, "send_dict", fail)
    with pytest.raises(Exception, match="reply lost"):
        tool_fns(register_modification_tools, provider)["update_element_beta"](ids=7, beta=30)
    assert len(calls) == 1
    assert requests == []
