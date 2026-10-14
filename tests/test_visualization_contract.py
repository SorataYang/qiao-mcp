"""Actual SDK plot signatures, integer components and cross-host image transfer."""

import json

import pytest
from conftest import PNG_BASE64, PNG_BYTES, tool_fns
from mcp.server.fastmcp import Image

from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.visualization import register_visualization_tools


@pytest.fixture
def image_wire(fake_provider, monkeypatch):
    import qtmodel
    from qtmodel.core.qt_server import QtServer

    requests = []

    def send(command="", header="", read_timeout=600):
        requests.append((header, json.loads(command) if command else None))
        return PNG_BASE64

    monkeypatch.setattr(QtServer, "send_command", send)
    fake_provider._odb = qtmodel.odb
    return tool_fns(register_visualization_tools, fake_provider), requests


def test_remote_screenshot_is_decoded_and_saved_on_mcp_host(image_wire, tmp_path):
    functions, requests = image_wire
    path = tmp_path / "local" / "模型.png"
    image = functions["save_model_screenshot"](file_path=str(path), view_angle="current")
    assert isinstance(image, Image)
    assert path.read_bytes() == PNG_BYTES
    assert len(requests) == 1
    assert requests[0][0] == "SAVE-PNG"
    assert requests[0][1]["file_path"] == ""


@pytest.mark.parametrize("kind, component, header, expected", [
    ("displacement", "uy", "PLOT-DISPLACEMENT-RESULT", 2),
    ("reaction", "mz", "PLOT-REACTION-RESULT", 7),
    ("beam_force", "mz", "PLOT-BEAM-ELEMENT-FORCE", 6),
    ("beam_stress", "lower_left", "PLOT-BEAM-ELEMENT-STRESS", 8),
    ("truss_force", "n", "PLOT-TRUSS-ELEMENT-FORCE", 0),
    ("truss_force", 0, "PLOT-TRUSS-ELEMENT-FORCE", 0),
    ("truss_stress", "", "PLOT-TRUSS-ELEMENT-STRESS", None),
    ("plate_force", "mxy", "PLOT-PLATE-ELEMENT-FORCE", 6),
    ("plate_stress", "fxy", "PLOT-PLATE-ELEMENT-STRESS", 3),
    ("beam_force", "6", "PLOT-BEAM-ELEMENT-FORCE", 6),
])
def test_plot_components_reach_actual_sdk_as_native_integers(
    image_wire, tmp_path, kind, component, header, expected,
):
    functions, requests = image_wire
    path = tmp_path / "plot.png"
    image = functions["plot_analysis_result"](
        result_type=kind, component=component, file_path=str(path), stage_id=2,
    )
    assert isinstance(image, Image)
    assert path.read_bytes() == PNG_BYTES
    assert len(requests) == 1
    command, payload = requests[0]
    assert command == header
    assert payload["file_path"] == ""
    assert payload["stage_id"] == 2
    if expected is None:
        assert "component" not in payload
    else:
        assert type(payload["component"]) is int
        assert payload["component"] == expected


def test_modal_plot_uses_mode_fields_instead_of_unsupported_stage_fields(image_wire, tmp_path):
    functions, requests = image_wire
    functions["plot_analysis_result"](
        result_type="modal", mode=3, mode_kind=2, file_path=str(tmp_path / "modal.png"),
    )
    command, payload = requests[0]
    assert command == "PLOT-MODAL-RESULT"
    assert (payload["mode"], payload["mode_kind"]) == (3, 2)
    assert not {"stage_id", "case_name", "component"}.intersection(payload)


@pytest.mark.parametrize("arguments", [
    {"result_type": "modal", "stage_id": 2},
    {"result_type": "modal", "component": "mz"},
    {"result_type": "truss_stress", "component": "sz"},
    {"result_type": "beam_force", "component": 7},
    {"result_type": "displacement", "mode": 2},
])
def test_invalid_plot_selection_fails_before_request(image_wire, tmp_path, arguments):
    functions, requests = image_wire
    with pytest.raises(ToolError):
        functions["plot_analysis_result"](file_path=str(tmp_path / "plot.png"), **arguments)
    assert requests == []


@pytest.mark.parametrize("reply", [None, "", "Saved file on Windows", "aGVsbG8="])
def test_failed_capture_never_returns_an_old_local_image(fake_provider, tmp_path, reply):
    path = tmp_path / "old.png"
    path.write_bytes(PNG_BYTES)
    fake_provider._odb.save_png = lambda file_path: reply
    functions = tool_fns(register_visualization_tools, fake_provider)
    with pytest.raises(ToolError):
        functions["save_model_screenshot"](file_path=str(path), view_angle="current")
    assert path.read_bytes() == PNG_BYTES
