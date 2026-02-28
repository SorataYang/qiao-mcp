"""
MCP Tools for visualization — screenshots and result plots.
可视化工具：模型截图与结果云图
"""

import os

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider

# Default output directory for images (图片默认保存目录)
DEFAULT_IMAGE_DIR = os.path.join(os.path.expanduser("~"), "bridge_mcp_images")


def _ensure_dir(path: str) -> str:
    """Ensure image directory exists and return it."""
    os.makedirs(path, exist_ok=True)
    return path


def register_visualization_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register visualization MCP tools."""

    @mcp.tool()
    def save_model_screenshot(
        file_path: str = "",
        view_angle: str = "iso",
    ) -> str:
        """
        Save a screenshot of the current bridge model view (保存桥梁模型截图).

        Args:
            file_path: Output file path (.png). If empty, saves to default directory.
                       输出路径（.png格式），为空则保存到默认目录
            view_angle: View angle preset (视角预设):
                'iso'(等轴测), 'front'(正视), 'side'(侧视), 'top'(俯视)
        """
        try:
            if not file_path:
                _ensure_dir(DEFAULT_IMAGE_DIR)
                file_path = os.path.join(DEFAULT_IMAGE_DIR, "model_view.png")

            # Set the view angle first
            angle_map = {
                "iso": (45, 35),
                "front": (0, 0),
                "side": (90, 0),
                "top": (0, 90),
            }
            if view_angle in angle_map:
                h, v = angle_map[view_angle]
                try:
                    provider.set_view_angle(horizontal=h, vertical=v)
                except Exception:
                    pass  # Non-critical; proceed with current view

            provider.save_model_image(file_path=file_path)
            return f"Screenshot saved to: {file_path} (截图已保存)"
        except Exception as e:
            return f"Error saving screenshot (保存截图失败): {e}"

    @mcp.tool()
    def plot_analysis_result(
        result_type: str,
        stage_id: int = -1,
        case_name: str = "",
        component: str = "",
        file_path: str = "",
    ) -> str:
        """
        Generate and save an analysis result plot (生成分析结果云图并保存).

        Args:
            result_type: Result type (结果类型):
                'displacement'(位移), 'reaction'(反力),
                'beam_force'(梁内力), 'beam_stress'(梁应力),
                'truss_force'(杆内力), 'truss_stress'(杆应力),
                'plate_force'(板内力), 'plate_stress'(板应力),
                'modal'(振型)
            stage_id: Construction stage ID (施工阶段ID):
                -1=operation(运营), 0=envelope(包络), n=stage n (第n阶段)
            case_name: Load case name for operation stage (运营阶段荷载工况名)
            component: Result component to display (显示分量), e.g.
                'uy'(竖向位移), 'mz'(弯矩), 'fx'(轴力), 'sz'(正应力)
                Leave empty to use default component.
            file_path: Output file path (.png). Empty = default directory.
                       输出路径，为空则保存到默认目录
        """
        try:
            if not file_path:
                _ensure_dir(DEFAULT_IMAGE_DIR)
                file_path = os.path.join(
                    DEFAULT_IMAGE_DIR, f"result_{result_type}_stage{stage_id}.png"
                )

            kwargs = {"stage_id": stage_id}
            if case_name:
                kwargs["case_name"] = case_name
            if component:
                kwargs["component"] = component

            provider.plot_result(
                result_type=result_type, file_path=file_path, **kwargs
            )
            return f"Result plot saved to: {file_path} (结果云图已保存)"
        except Exception as e:
            return f"Error plotting result (生成结果云图失败): {e}"

    @mcp.tool()
    def set_view_angle(
        angle_preset: str = "iso",
        horizontal: float | None = None,
        vertical: float | None = None,
    ) -> str:
        """
        Set the 3D view angle of the bridge model (设置三维视角).

        Args:
            angle_preset: View preset (视角预设):
                'iso'(等轴测), 'front'(正视图), 'side'(侧视图), 'top'(俯视图)
                Set to 'custom' to use horizontal/vertical values.
            horizontal: Horizontal rotation angle in degrees (水平旋转角，单位度)
            vertical: Vertical rotation angle in degrees (垂直旋转角，单位度)
        """
        try:
            if angle_preset != "custom":
                angle_map = {
                    "iso": (45, 35),
                    "front": (0, 0),
                    "side": (90, 0),
                    "top": (0, 90),
                }
                if angle_preset not in angle_map:
                    return (
                        f"Unknown preset '{angle_preset}'. "
                        "Use: iso, front, side, top, or custom"
                    )
                horizontal, vertical = angle_map[angle_preset]

            provider.set_view_angle(horizontal=horizontal, vertical=vertical)
            return (
                f"View angle set to {angle_preset} "
                f"(horizontal={horizontal}°, vertical={vertical}°) "
                f"(视角已设置)"
            )
        except Exception as e:
            return f"Error setting view angle (设置视角失败): {e}"
