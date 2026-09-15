"""MCP True=release is translated to the SDK's True=fixed constraint payload."""

import pytest
import qtmodel
from conftest import tool_fns
from qtmodel.core.qt_server import QtServer

from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools


@pytest.mark.parametrize("release_i, expected_i", [
    ([False, False, False, False, True, False], [True, True, True, True, False, True]),
    (None, [True, True, True, True, True, True]),
])
def test_release_flags_reach_the_native_constraint_api(
    fake_provider, monkeypatch, release_i, expected_i,
):
    sent = []

    def send_dict(header, payload=None, **kwargs):
        sent.append((header, payload))

    monkeypatch.setattr(fake_provider, "_require_available", lambda: None)
    monkeypatch.setattr(QtServer, "send_dict", send_dict)
    monkeypatch.setattr(qtmodel.mdb, "update_model", lambda: None)
    fake_provider._mdb = qtmodel.mdb
    functions = tool_fns(register_advanced_boundary_tools, fake_provider)
    functions["add_beam_constraint"](beam_id=7, release_i=release_i)

    header, payload = sent[0]
    assert header == "ADD-BEAM-CONSTRAINT"
    assert payload["beam_id"] == 7
    assert payload["info_i"] == expected_i
    assert payload["info_j"] == [True] * 6, "Omitting an end must not release all its DOFs"
