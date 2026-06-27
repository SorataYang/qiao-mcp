"""
MCP Tools for visualization — screenshots and result plots.
可视化工具：模型截图与结果云图
"""

import os

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider

# Default output directory for images (图片默认保存目录)
DEFAULT_IMAGE_DIR = os.path.join(os.path.expanduser("~"), "qiao_mcp_images")


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

            provider.set_view_direction(horizontal_degree=horizontal, vertical_degree=vertical)
            return (
                f"View angle set to {angle_preset} "
                f"(horizontal={horizontal}°, vertical={vertical}°) "
                f"(视角已设置)"
            )
        except Exception as e:
            return f"Error setting view angle (设置视角失败): {e}"

    @mcp.tool()
    def display_ids(
        node_id: bool = False,
        element_id: bool = False,
    ) -> str:
        """
        Toggle the display of node and element IDs (开关节点和单元编号显示).

        Args:
            node_id: True to show node IDs, False to hide (显示节点号)
            element_id: True to show element IDs, False to hide (显示单元号)
        """
        try:
            provider.display_node_id(show_id=node_id)
            provider.display_element_id(show_id=element_id)
            return "Successfully updated ID display settings (成功更新编号显示设置)"
        except Exception as e:
            return f"Error updating ID display (更新编号显示失败): {e}"

    @mcp.tool()
    def activate_structure(
        node_ids: list[int] | None = None,
        element_ids: list[int] | None = None,
    ) -> str:
        """
        Activate only specific nodes/elements for display (仅激活显示指定节点/单元).

        Args:
            node_ids: Node IDs to activate (要激活的节点号)
            element_ids: Element IDs to activate (要激活的单元号)
        """
        try:
            kwargs = {}
            if node_ids is not None: kwargs["node_ids"] = node_ids
            if element_ids is not None: kwargs["element_ids"] = element_ids
            provider.activate_structure(**kwargs)
            return "Successfully activated selected structure (成功激活选中结构)"
        except Exception as e:
            return f"Error activating structure (激活结构失败): {e}"

    @mcp.tool()
    def set_render(flag: bool = True) -> str:
        """
        Toggle solid rendering mode (开关实体渲染模式).

        Args:
            flag: True for rendered view, False for wireframe (是否渲染)
        """
        try:
            provider.set_render(flag=flag)
            return f"Successfully set render mode to {flag} (成功设置渲染模式)"
        except Exception as e:
            return f"Error setting render mode (设置渲染模式失败): {e}"

    @mcp.tool()
    def reset_display() -> str:
        """
        Reset display view (恢复默认显示/全显).
        """
        try:
            provider.reset_display()
            return "Successfully reset display (成功恢复默认显示)"
        except Exception as e:
            return f"Error resetting display (恢复默认显示失败): {e}"

    @mcp.tool()
    def set_unit(unit_force: str = "KN", unit_length: str = "MM") -> str:
        """
        Set display units (设置显示单位).

        Args:
            unit_force: Force unit (力单位, 例如: KN, N, TONF)
            unit_length: Length unit (长度单位, 例如: M, MM, CM)
        """
        try:
            provider.set_unit(unit_force=unit_force, unit_length=unit_length)
            return f"Successfully set unit to {unit_force}-{unit_length} (成功设置单位)"
        except Exception as e:
            return f"Error setting unit (设置单位失败): {e}"

    @mcp.tool()
    def change_construct_stage(stage: int = 0) -> str:
        """
        Change current construction stage in view (切换当前显示的施工阶段).

        Args:
            stage: Stage ID, 0 for Base stage (施工阶段号，0为成桥阶段)
        """
        try:
            provider.change_construct_stage(stage=stage)
            return f"Successfully changed to stage {stage} (成功切换施工阶段)"
        except Exception as e:
            return f"Error changing construct stage (切换施工阶段失败): {e}"
