"""
Bridge-MCP Provider abstraction layer.
Defines the interface that backend software adapters must implement.
桥梁分析软件后端抽象层
"""

from abc import ABC, abstractmethod
from typing import Any


class BridgeProvider(ABC):
    """
    Abstract base class for bridge analysis software providers.
    Each provider adapts a specific bridge analysis software (e.g., qtmodel/桥通)
    to the bridge-mcp interface.

    桥梁分析软件后端抽象基类。
    每个 Provider 对接一个具体的桥梁分析软件。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'qtmodel')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider version string."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend software is available and properly configured."""
        ...

    # ── Model Information ──────────────────────────────────────────────

    @abstractmethod
    def get_model_summary(self) -> dict[str, Any]:
        """
        Get a summary of the current model.
        Returns dict with keys like: node_count, element_count, material_count, etc.
        获取当前模型概要信息
        """
        ...

    @abstractmethod
    def get_node_data(self, ids: Any = None) -> list[dict]:
        """Get node information. 获取节点信息"""
        ...

    @abstractmethod
    def get_element_data(self, ids: Any = None) -> list[dict]:
        """Get element information. 获取单元信息"""
        ...

    @abstractmethod
    def get_material_data(self) -> list[dict]:
        """Get material information. 获取材料信息"""
        ...

    @abstractmethod
    def get_section_data(self, sec_id: int, position: int = 0) -> dict:
        """Get section information. 获取截面信息"""
        ...

    @abstractmethod
    def get_section_names(self) -> list[int]:
        """Get all section IDs. 获取所有截面编号"""
        ...

    @abstractmethod
    def get_boundary_data(self) -> dict[str, list[dict]]:
        """Get boundary condition data. 获取边界条件信息"""
        ...

    @abstractmethod
    def get_load_case_names(self) -> list[str]:
        """Get load case names. 获取荷载工况名"""
        ...

    @abstractmethod
    def get_stage_names(self) -> list[str]:
        """Get construction stage names. 获取施工阶段名称"""
        ...

    @abstractmethod
    def get_structure_group_names(self) -> list[str]:
        """Get structure group names. 获取结构组名称"""
        ...

    # ── Modeling Operations ────────────────────────────────────────────

    @abstractmethod
    def add_nodes(self, node_data: list[list[float]], **kwargs) -> None:
        """Add nodes to the model. 添加节点"""
        ...

    @abstractmethod
    def add_elements(self, ele_data: list[list], **kwargs) -> None:
        """Add elements to the model. 添加单元"""
        ...

    @abstractmethod
    def add_material(
        self,
        name: str,
        mat_type: int,
        standard: int = 1,
        database: str = "",
        **kwargs,
    ) -> None:
        """Add material. 添加材料"""
        ...

    @abstractmethod
    def add_section(self, name: str, sec_type: str, **kwargs) -> None:
        """Add section. 添加截面"""
        ...

    # ── Boundary Operations ────────────────────────────────────────────

    @abstractmethod
    def add_general_support(
        self, node_id: Any, boundary_info: list, **kwargs
    ) -> None:
        """Add general support. 添加一般支承"""
        ...

    @abstractmethod
    def add_elastic_link(self, link_type: int, start_id: int, end_id: int, **kwargs) -> None:
        """Add elastic link. 添加弹性连接"""
        ...

    # ── Load Operations ────────────────────────────────────────────────

    @abstractmethod
    def add_nodal_force(
        self, node_id: Any, case_name: str, load_info: list, **kwargs
    ) -> None:
        """Add nodal force. 添加节点荷载"""
        ...

    @abstractmethod
    def add_beam_element_load(
        self, element_id: Any, case_name: str, load_type: int, **kwargs
    ) -> None:
        """Add beam element load. 添加梁单元荷载"""
        ...

    # ── Tendon Operations ──────────────────────────────────────────────

    @abstractmethod
    def add_tendon_property(self, name: str, tendon_type: int, **kwargs) -> None:
        """Add tendon property. 添加钢束特性"""
        ...

    @abstractmethod
    def add_tendon_2d(self, name: str, property_name: str, **kwargs) -> None:
        """Add 2D tendon. 添加2D钢束"""
        ...

    @abstractmethod
    def add_pre_stress(
        self, case_name: str, tendon_name: str, force: float, **kwargs
    ) -> None:
        """Add prestress load. 添加预应力"""
        ...

    # ── Construction Stage Operations ──────────────────────────────────

    @abstractmethod
    def add_construction_stage(self, name: str, duration: float, **kwargs) -> None:
        """Add a construction stage. 添加施工阶段"""
        ...

    @abstractmethod
    def merge_all_stages(self, name: str, **kwargs) -> None:
        """Merge all construction stages. 合并所有施工阶段"""
        ...

    # ── Analysis Operations ────────────────────────────────────────────

    @abstractmethod
    def update_project_setting(self, **kwargs) -> None:
        """Update project settings. 更新项目配置"""
        ...

    @abstractmethod
    def update_construction_stage_setting(self, **kwargs) -> None:
        """Update construction stage analysis settings. 更新施工阶段分析设置"""
        ...

    @abstractmethod
    def update_self_vibration_setting(self, **kwargs) -> None:
        """Update self-vibration analysis settings. 更新自振分析设置"""
        ...

    # ── Result Extraction ──────────────────────────────────────────────

    @abstractmethod
    def get_deformation(self, ids: Any, stage_id: int, **kwargs) -> str:
        """Get nodal deformation results. 获取节点变形结果"""
        ...

    @abstractmethod
    def get_element_force(self, ids: Any, stage_id: int, **kwargs) -> str:
        """Get element internal force results. 获取单元内力结果"""
        ...

    @abstractmethod
    def get_element_stress(self, ids: Any, stage_id: int, **kwargs) -> str:
        """Get element stress results. 获取单元应力结果"""
        ...

    @abstractmethod
    def get_reaction(self, ids: Any, stage_id: int, **kwargs) -> str:
        """Get support reaction results. 获取反力结果"""
        ...

    # ── Visualization ──────────────────────────────────────────────────

    @abstractmethod
    def save_model_image(self, file_path: str) -> str:
        """Save current model view as image. 保存模型图片"""
        ...

    @abstractmethod
    def plot_result(self, result_type: str, file_path: str, **kwargs) -> str:
        """Plot analysis results. 绘制分析结果图"""
        ...

    # ── Validation ─────────────────────────────────────────────────────

    @abstractmethod
    def validate_model(self) -> dict[str, Any]:
        """
        Validate the current model for common issues.
        Returns a dict with keys: is_valid, errors, warnings.
        验证当前模型，检查常见问题（悬空节点、缺失材料等）
        """
        ...

    @abstractmethod
    def add_check_load_combine(self, name: str, standard: int, kind: int, **kwargs) -> None:
        """Add check load combination. 添加检算荷载组合"""
        ...

    @abstractmethod
    def solve_concrete_check(self, name: str) -> None:
        """Run concrete structural check. 运行混凝土检算"""
        ...

    @abstractmethod
    def add_concrete_check_case(self, name: str, standard: int, structure_type: int, group_name: str) -> None:
        """Create concrete check case. 创建混凝土检算工况"""
        ...

    @abstractmethod
    def add_parameter_reinforcement(self, sec_id: int, **kwargs) -> None:
        """Add parametric reinforcement. 添加参数化配筋"""
        ...

    # ── Group Management ───────────────────────────────────────────────

    @abstractmethod
    def add_structure_group(self, name: str) -> None:
        """Create a structure group. 创建结构组"""
        ...

    @abstractmethod
    def add_elements_to_structure_group(self, name: str, element_ids: Any) -> None:
        """Add elements to a structure group. 向结构组添加单元"""
        ...

    @abstractmethod
    def get_structure_group_elements(self, name: str) -> list:
        """Get element IDs in a structure group. 获取结构组中的单元"""
        ...

    @abstractmethod
    def add_boundary_group(self, name: str) -> None:
        """Create a boundary group. 创建边界组"""
        ...

    @abstractmethod
    def add_load_group(self, name: str) -> None:
        """Create a load group. 创建荷载组"""
        ...

    # ── Advanced Boundary ──────────────────────────────────────────────

    @abstractmethod
    def add_master_slave_link(self, master_id: int, slave_ids: Any, **kwargs) -> None:
        """Add master-slave constraint. 添加主从约束"""
        ...

    @abstractmethod
    def add_elastic_support(self, node_id: Any, spring_values: list, **kwargs) -> None:
        """Add elastic spring support. 添加弹性支承"""
        ...

    # ── Moving Loads ───────────────────────────────────────────────────

    @abstractmethod
    def add_standard_vehicle(self, name: str, vehicle_type: int, standard: int) -> None:
        """Add standard vehicle load. 添加标准车辆"""
        ...

    @abstractmethod
    def add_lane(self, name: str, **kwargs) -> None:
        """Define a traffic lane. 定义行车道"""
        ...

    @abstractmethod
    def add_live_load_case(self, name: str, **kwargs) -> None:
        """Create a live load case. 创建移动荷载工况"""
        ...

    @abstractmethod
    def get_live_load_results(self, case_name: str, result_type: str, ids: Any) -> Any:
        """Get live load analysis results. 获取移动荷载结果"""
        ...

    # ── Self-weight ────────────────────────────────────────────────────

    @abstractmethod
    def add_self_weight(self, case_name: str, **kwargs) -> None:
        """Add self-weight load. 添加自重荷载"""
        ...

    # ── Tendon Data ────────────────────────────────────────────────────

    @abstractmethod
    def get_tendon_data(self) -> list[dict]:
        """Get all tendon information. 获取所有钢束信息"""
        ...

    # ── Visualization Control ──────────────────────────────────────────

    @abstractmethod
    def set_view_angle(self, horizontal: float, vertical: float) -> None:
        """Set 3D view camera angle. 设置三维视角"""
        ...
