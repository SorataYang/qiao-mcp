"""
MCP Tools for visualization — screenshots and result plots.
可视化工具：模型截图与结果云图
"""

import os
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import PlotResultKind, ViewAngle, ViewSelection

# Default output directory for images (图片默认保存目录)
DEFAULT_IMAGE_DIR = os.path.join(os.path.expanduser("~"), "qiao_mcp_images")


def _ensure_dir(path: str) -> str:
    """Ensure image directory exists and return it."""
    os.makedirs(path, exist_ok=True)
    return path


# QiaoTong 软件内置视图预设编号（odb.set_view_direction 的 direction 参数）
_VIEW_PRESETS = {
    "iso": 1,      # 空间视图1
    "front": 2,    # 前视图
    "side": 4,     # 左视图
    "top": 5,      # 顶视图
    "right": 6,    # 右视图
    "back": 8,     # 后视图
    "bottom": 10,  # 底视图
}


def register_visualization_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register visualization MCP tools."""

    @mcp.tool(structured_output=False)
    def save_model_screenshot(
        file_path: str = "",
        view_angle: ViewAngle = "iso",
        return_image: bool = True,
    ) -> str | Image:
        """
        Capture a screenshot of the current bridge model view (截取桥梁模型视图).

        By default returns the image itself so it can be viewed directly.
        默认直接返回图像内容，可在客户端预览。

        Args:
            file_path: Output file path (.png). If empty, saves to default directory.
                       输出路径（.png格式），为空则保存到默认目录
            view_angle: View preset (视角预设): 'iso'(空间视图), 'front'(前视),
                'side'(左视), 'top'(俯视), 'right'(右视), 'back'(后视), 'bottom'(仰视),
                or 'current' to keep the current view (保持当前视角)
            return_image: Return the PNG as viewable image content; if False, return
                          only the saved path (是否直接返回图像内容，否则仅返回路径)
        """
        try:
            if not file_path:
                _ensure_dir(DEFAULT_IMAGE_DIR)
                file_path = os.path.join(DEFAULT_IMAGE_DIR, "model_view.png")

            warning = ""
            if view_angle != "current":
                if view_angle not in _VIEW_PRESETS:
                    valid = ", ".join(_VIEW_PRESETS)
                    raise ToolInputError(f"Unknown view_angle '{view_angle}'. Valid: {valid}, current")
                try:
                    provider.set_view_direction(direction=_VIEW_PRESETS[view_angle])
                except Exception as e:
                    warning = f" (WARNING: view preset failed, used current view — 视角设置失败: {e})"

            provider.save_model_image(file_path=file_path)

            if return_image and not warning and os.path.exists(file_path):
                # 直接返回图像内容，便于模型/客户端查看
                return Image(path=file_path)
            return f"Screenshot saved to: {file_path} (截图已保存){warning}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error saving screenshot (保存截图失败): {e}") from e

    @mcp.tool(structured_output=False)
    def plot_analysis_result(
        result_type: PlotResultKind,
        stage_id: int = -1,
        case_name: str = "",
        component: str = "",
        file_path: str = "",
        return_image: bool = True,
    ) -> str | Image:
        """
        Generate an analysis result contour plot (生成分析结果云图).

        By default returns the plot image itself for direct viewing.
        默认直接返回云图图像内容，可在客户端预览。

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
                'uy'(Y向位移), 'mz'(弯矩), 'fx'(轴力), 'sz'(正应力)
                Leave empty to use default component.
            file_path: Output file path (.png). Empty = default directory.
                       输出路径，为空则保存到默认目录
            return_image: Return the PNG as viewable image content; if False, return
                          only the saved path (是否直接返回图像内容，否则仅返回路径)
        """
        try:
            if not file_path:
                _ensure_dir(DEFAULT_IMAGE_DIR)
                file_path = os.path.join(
                    DEFAULT_IMAGE_DIR, f"result_{result_type}_stage{stage_id}.png"
                )

            kwargs: dict[str, Any] = {"stage_id": stage_id}
            if case_name:
                kwargs["case_name"] = case_name
            if component:
                kwargs["component"] = component

            provider.plot_result(
                result_type=result_type, file_path=file_path, **kwargs
            )
            if return_image and os.path.exists(file_path):
                return Image(path=file_path)
            return f"Result plot saved to: {file_path} (结果云图已保存)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error plotting result (生成结果云图失败): {e}") from e

    @mcp.tool()
    def set_view_angle(
        angle_preset: ViewSelection = "iso",
        horizontal: float | None = None,
        vertical: float | None = None,
    ) -> str:
        """
        Set the 3D view angle of the bridge model (设置三维视角).

        Args:
            angle_preset: View preset (视角预设): 'iso'(空间视图), 'front'(前视图),
                'side'(左视图), 'top'(俯视图), 'right'(右视图), 'back'(后视图),
                'bottom'(仰视图). Set to 'custom' to use horizontal/vertical rotation.
            horizontal: Horizontal rotation in degrees, for 'custom' (水平旋转角，度)
            vertical: Vertical rotation in degrees, for 'custom' (垂直旋转角，度)
        """
        try:
            if angle_preset == "custom":
                if horizontal is None and vertical is None:
                    raise ToolInputError("custom preset requires horizontal/vertical degrees (custom 需给出旋转角度)")
                provider.set_view_direction(
                    horizontal_degree=horizontal or 0, vertical_degree=vertical or 0
                )
                return (
                    f"View rotated to horizontal={horizontal or 0}°, vertical={vertical or 0}° "
                    f"(视角已设置)"
                )
            if angle_preset not in _VIEW_PRESETS:
                valid = ", ".join(_VIEW_PRESETS)
                raise ToolInputError(f"Unknown preset '{angle_preset}'. Use: {valid}, or custom")
            provider.set_view_direction(direction=_VIEW_PRESETS[angle_preset])
            return f"View angle set to {angle_preset} (视角已设置)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting view angle (设置视角失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating ID display (更新编号显示失败): {e}") from e

    @mcp.tool()
    def activate_structure(
        node_ids: list[int] | None = None,
        element_ids: list[int] | None = None,
    ) -> str:
        """
        Show only the given nodes/elements in the view, hiding all others
        (仅在视图中激活显示指定节点/单元，其余隐藏).

        Display-only: changes what is drawn, not model data or results.
        Call reset_display to bring the full model back afterwards.
        (纯显示操作，不改模型或计算结果；用完调 reset_display 恢复全图。)

        When to use: isolate a subregion before a screenshot; prefer this
        over re-reading the model when you only need a visual check.
        (截图前隔离局部时用；只需目视检查时用它，而非重新读模型。)

        Args:
            node_ids: Node IDs to activate (要激活的节点号)
            element_ids: Element IDs to activate (要激活的单元号)
        """
        try:
            kwargs: dict[str, Any] = {}
            if node_ids is not None:
                kwargs["node_ids"] = node_ids
            if element_ids is not None:
                kwargs["element_ids"] = element_ids
            provider.activate_structure(**kwargs)
            return "Successfully activated selected structure (成功激活选中结构)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error activating structure (激活结构失败): {e}") from e

    @mcp.tool()
    def set_render(flag: bool = True) -> str:
        """
        Toggle solid (rendered) vs wireframe display (开关实体渲染/线框显示).

        Display-only: affects how the model is drawn, not model data or
        results. Pair with save_model_screenshot for solid-shaded captures.
        (纯显示操作，不改模型或结果；配合 save_model_screenshot 出实体图。)

        Args:
            flag: True for rendered view, False for wireframe (是否渲染)
        """
        try:
            provider.set_render(flag=flag)
            return f"Successfully set render mode to {flag} (成功设置渲染模式)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting render mode (设置渲染模式失败): {e}") from e

    @mcp.tool()
    def reset_display() -> str:
        """
        Restore the default full-model view (恢复默认显示/全显).

        Display-only: undoes view filters such as activate_structure and
        brings every node/element back into view. Does not change model
        data or results.
        (纯显示操作：撤销 activate_structure 等视图过滤、恢复显示所有节点/单元；不改模型或结果。)
        """
        try:
            provider.reset_display()
            return "Successfully reset display (成功恢复默认显示)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error resetting display (恢复默认显示失败): {e}") from e

    @mcp.tool()
    def set_unit(unit_force: str = "KN", unit_length: str = "MM") -> str:
        """
        Set the force/length units used for display and reporting
        (设置显示与报告所用的力/长度单位).

        Display setting only: it changes the units values are shown in and
        does NOT rescale model geometry, section properties, or stored data.
        Set it before taking screenshots or reading displayed quantities.
        (仅显示设置：只改数值显示单位，不缩放模型几何/截面特性/已存数据；读数或截图前先设好。)

        Args:
            unit_force: Force unit (力单位, 例如: KN, N, TONF)
            unit_length: Length unit (长度单位, 例如: M, MM, CM)
        """
        try:
            provider.set_unit(unit_force=unit_force, unit_length=unit_length)
            return f"Successfully set unit to {unit_force}-{unit_length} (成功设置单位)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error setting unit (设置单位失败): {e}") from e

    @mcp.tool()
    def change_construct_stage(stage: int = 0) -> str:
        """
        Change the construction stage of the results view, BY INDEX
        (按阶段号切换结果视图的施工阶段).

        Display-only: it changes which stage the current window shows and does
        NOT re-run the analysis. Use it to step through stages when reading
        results or taking screenshots.

        When to use vs. switch_display_stage: this one takes an integer stage
        INDEX and drives the results/post-processing view (odb).
        switch_display_stage takes the stage NAME and drives the modelling view
        (mdb). The index here is not a name — passing a string fails.

        (纯显示操作：切换当前窗口显示的阶段，不重新求解；逐阶段读结果或截图时用它。
        选型：本工具收阶段"号"、作用于结果/后处理视图(odb)；switch_display_stage 收阶段
        "名"、作用于建模视图(mdb)。此处只接受整数，传字符串阶段名会失败。)

        Args:
            stage: Stage number — 0 = the base model (not the completed-bridge
                   stage), a positive integer = that construction stage
                   (施工阶段号：0 为基本模型（不是成桥阶段），正整数为对应施工阶段)
        """
        try:
            provider.change_construct_stage(stage=stage)
            return f"Successfully changed to stage {stage} (成功切换施工阶段)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error changing construct stage (切换施工阶段失败): {e}") from e
