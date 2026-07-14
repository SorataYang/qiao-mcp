"""可视化视角工具行为测试：预设映射与失败可见性。"""

import pytest
from conftest import tool_fns, tool_text

from qiao_mcp.tools.envelope import ToolInputError
from qiao_mcp.tools.visualization import register_visualization_tools


def test_screenshot_uses_builtin_view_preset(fake_provider, tmp_path):
    fns = tool_fns(register_visualization_tools, fake_provider)
    out = str(tmp_path / "m.png")
    result = fns["save_model_screenshot"](file_path=out, view_angle="top")
    _, _, kw = fake_provider._odb.last("set_view_direction")
    assert kw == {"direction": 5}, "top 应映射为软件内置顶视图编号 5"
    _, _, kw = fake_provider._odb.last("save_png")
    assert kw["file_path"] == out
    assert result["status"] == "success"


def test_screenshot_current_view_skips_direction(fake_provider, tmp_path):
    fns = tool_fns(register_visualization_tools, fake_provider)
    fns["save_model_screenshot"](file_path=str(tmp_path / "m.png"), view_angle="current")
    assert fake_provider._odb.count("set_view_direction") == 0


def test_screenshot_view_failure_is_reported_not_swallowed(fake_provider, tmp_path):
    saved = []

    class Odb:
        def set_view_direction(self, **kw):
            raise RuntimeError("连接失败")

        def save_png(self, file_path):
            saved.append(file_path)

    fake_provider._odb = Odb()
    fns = tool_fns(register_visualization_tools, fake_provider)
    result = fns["save_model_screenshot"](file_path=str(tmp_path / "m.png"))
    assert "WARNING" in tool_text(result), "视角设置失败必须在返回中可见，不得静默吞掉"
    assert saved, "视角失败时仍应完成截图"


def test_set_view_angle_preset_and_custom(fake_provider):
    fns = tool_fns(register_visualization_tools, fake_provider)
    fns["set_view_angle"](angle_preset="front")
    _, _, kw = fake_provider._odb.last("set_view_direction")
    assert kw == {"direction": 2}

    fns["set_view_angle"](angle_preset="custom", horizontal=30, vertical=15)
    _, _, kw = fake_provider._odb.last("set_view_direction")
    assert kw == {"horizontal_degree": 30, "vertical_degree": 15}


def test_set_view_angle_rejects_unknown_preset(fake_provider):
    fns = tool_fns(register_visualization_tools, fake_provider)
    with pytest.raises(ToolInputError):
        fns["set_view_angle"](angle_preset="bogus")
    assert fake_provider._odb.count("set_view_direction") == 0
