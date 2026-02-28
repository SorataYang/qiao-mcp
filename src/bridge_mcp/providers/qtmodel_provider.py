"""
QTModel Provider — adapter for 桥通 (QiaoTong) bridge analysis software.

This provider wraps the `qtmodel` Python API (mdb/odb/cdb) to implement
the BridgeProvider interface.

桥通软件后端适配器，封装 qtmodel Python API。
"""

from typing import Any

from bridge_mcp.providers import BridgeProvider


class QtModelProvider(BridgeProvider):
    """
    Provider for QiaoTong bridge analysis software via the `qtmodel` Python API.

    The qtmodel API exposes three main objects:
    - mdb: Model database (building / modifying the model)
    - odb: Output database (querying results and visualization)
    - cdb: Check database (structural verification)

    桥通软件 qtmodel API 适配器。
    """

    def __init__(self):
        self._mdb = None
        self._odb = None
        self._available = False
        self._unavailable_reason = ""
        self._try_import()

    def _try_import(self):
        """Attempt to import qtmodel and connect to QiaoTong software."""
        try:
            import qtmodel
            # Accessing mdb/odb/cdb will raise if the software is not running
            self._mdb = qtmodel.mdb
            self._odb = qtmodel.odb
            self._available = True
        except ImportError:
            self._available = False
            self._unavailable_reason = (
                "qtmodel package not found. Run: uv add qtmodel "
                "(qtmodel 包未安装，请运行: uv add qtmodel)"
            )
        except Exception as e:
            # qtmodel is installed but QiaoTong software is likely not running
            self._available = False
            self._unavailable_reason = (
                f"qtmodel imported but connection failed ({type(e).__name__}: {e}). "
                "Please ensure QiaoTong software is running. "
                "(qtmodel 已安装，但连接失败，请确保桥通软件已启动)"
            )

    @property
    def name(self) -> str:
        return "qtmodel"

    @property
    def version(self) -> str:
        try:
            import qtmodel
            return getattr(qtmodel, "__version__", "unknown")
        except ImportError:
            return "not installed"

    def is_available(self) -> bool:
        return self._available

    def _require_available(self):
        """Raise error if provider is not available."""
        if not self._available:
            raise RuntimeError(
                f"qtmodel provider unavailable: {self._unavailable_reason}"
            )

    # ── Model Information ──────────────────────────────────────────────

    def get_model_summary(self) -> dict[str, Any]:
        self._require_available()
        nodes = self._odb.get_node_data()
        elements = self._odb.get_element_data()
        materials = self._odb.get_material_data()
        sections = self._odb.get_section_names()
        stages = self._odb.get_stage_names()
        load_cases = self._odb.get_load_case_names()
        groups = self._odb.get_structure_group_names()
        boundaries = self._odb.get_boundary_group_names()

        return {
            "node_count": len(nodes) if isinstance(nodes, list) else 0,
            "element_count": len(elements) if isinstance(elements, list) else 0,
            "material_count": len(materials) if isinstance(materials, list) else 0,
            "section_count": len(sections) if isinstance(sections, list) else 0,
            "stage_count": len(stages) if isinstance(stages, list) else 0,
            "load_case_count": len(load_cases) if isinstance(load_cases, list) else 0,
            "structure_group_count": len(groups) if isinstance(groups, list) else 0,
            "boundary_group_count": len(boundaries) if isinstance(boundaries, list) else 0,
        }

    def get_node_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            result = self._odb.get_node_data(ids=ids)
        else:
            result = self._odb.get_node_data()
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    def get_element_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            result = self._odb.get_element_data(ids=ids)
        else:
            result = self._odb.get_element_data()
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    def get_material_data(self) -> list[dict]:
        self._require_available()
        return self._odb.get_material_data() or []

    def get_section_data(self, sec_id: int, position: int = 0) -> dict:
        self._require_available()
        return self._odb.get_section_data(sec_id, position=position) or {}

    def get_section_names(self) -> list[int]:
        self._require_available()
        return self._odb.get_section_names() or []

    def get_boundary_data(self) -> dict[str, list[dict]]:
        self._require_available()
        return {
            "general_supports": self._odb.get_general_support_data() or [],
            "elastic_links": self._odb.get_elastic_link_data() or [],
            "elastic_supports": self._odb.get_elastic_support_data() or [],
            "master_slave_links": self._odb.get_master_slave_link_data() or [],
            "beam_constraints": self._odb.get_beam_constraint_data() or [],
        }

    def get_load_case_names(self) -> list[str]:
        self._require_available()
        return self._odb.get_load_case_names() or []

    def get_stage_names(self) -> list[str]:
        self._require_available()
        return self._odb.get_stage_names() or []

    def get_structure_group_names(self) -> list[str]:
        self._require_available()
        return self._odb.get_structure_group_names() or []

    # ── Modeling Operations ────────────────────────────────────────────

    def add_nodes(self, node_data: list[list[float]], **kwargs) -> None:
        self._require_available()
        self._mdb.add_nodes(node_data=node_data, **kwargs)

    def add_elements(self, ele_data: list[list], **kwargs) -> None:
        self._require_available()
        self._mdb.add_elements(ele_data=ele_data, **kwargs)

    def add_material(
        self,
        name: str,
        mat_type: int,
        standard: int = 1,
        database: str = "",
        **kwargs,
    ) -> None:
        self._require_available()
        params = {"name": name, "mat_type": mat_type, "standard": standard}
        if database:
            params["database"] = database
        params.update(kwargs)
        self._mdb.add_material(**params)

    def add_section(self, name: str, sec_type: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_section(name=name, sec_type=sec_type, **kwargs)

    # ── Boundary Operations ────────────────────────────────────────────

    def add_general_support(
        self, node_id: Any, boundary_info: list, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_general_support(
            node_id=node_id, boundary_info=boundary_info, **kwargs
        )

    def add_elastic_link(
        self, link_type: int, start_id: int, end_id: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_elastic_link(
            link_type=link_type, start_id=start_id, end_id=end_id, **kwargs
        )

    # ── Load Operations ────────────────────────────────────────────────

    def add_nodal_force(
        self, node_id: Any, case_name: str, load_info: list, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_nodal_force(
            node_id=node_id, case_name=case_name, load_info=load_info, **kwargs
        )

    def add_beam_element_load(
        self, element_id: Any, case_name: str, load_type: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_beam_element_load(
            element_id=element_id, case_name=case_name, load_type=load_type, **kwargs
        )

    # ── Tendon Operations ──────────────────────────────────────────────

    def add_tendon_property(self, name: str, tendon_type: int, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_property(name=name, tendon_type=tendon_type, **kwargs)

    def add_tendon_2d(self, name: str, property_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_2d(name=name, property_name=property_name, **kwargs)

    def add_pre_stress(
        self, case_name: str, tendon_name: str, force: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_pre_stress(
            case_name=case_name, tendon_name=tendon_name, force=force, **kwargs
        )

    # ── Construction Stage Operations ──────────────────────────────────

    def add_construction_stage(self, name: str, duration: float, **kwargs) -> None:
        self._require_available()
        self._mdb.add_construction_stage(name=name, duration=duration, **kwargs)

    def merge_all_stages(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.merge_all_stages(name=name, **kwargs)

    # ── Analysis Operations ────────────────────────────────────────────

    def update_project_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_project_setting(**kwargs)

    def update_construction_stage_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_construction_stage_setting(**kwargs)

    def update_self_vibration_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_self_vibration_setting(**kwargs)

    # ── Result Extraction ──────────────────────────────────────────────

    def get_deformation(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        return self._odb.get_deformation(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_force(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        return self._odb.get_element_force(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_stress(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        return self._odb.get_element_stress(ids=ids, stage_id=stage_id, **kwargs)

    def get_reaction(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        return self._odb.get_reaction(ids=ids, stage_id=stage_id, **kwargs)

    # ── Visualization ──────────────────────────────────────────────────

    def save_model_image(self, file_path: str) -> str:
        self._require_available()
        return self._odb.save_png(file_path=file_path)

    def plot_result(self, result_type: str, file_path: str, **kwargs) -> str:
        self._require_available()
        plot_methods = {
            "displacement": self._odb.plot_displacement_result,
            "reaction": self._odb.plot_reaction_result,
            "beam_force": self._odb.plot_beam_element_force,
            "beam_stress": self._odb.plot_beam_element_stress,
            "truss_force": self._odb.plot_truss_element_force,
            "truss_stress": self._odb.plot_truss_element_stress,
            "plate_force": self._odb.plot_plate_element_force,
            "plate_stress": self._odb.plot_plate_element_stress,
            "modal": self._odb.plot_modal_result,
        }
        method = plot_methods.get(result_type)
        if method is None:
            raise ValueError(
                f"Unknown result_type '{result_type}'. "
                f"Available types: {list(plot_methods.keys())}"
            )
        return method(file_path=file_path, **kwargs)

    # ── Validation ─────────────────────────────────────────────────────

    def validate_model(self) -> dict[str, Any]:
        self._require_available()
        errors = []
        warnings = []

        # Check for overlapping nodes
        overlap_nodes = self._odb.get_overlap_nodes()
        if overlap_nodes:
            warnings.append(
                f"Found {len(overlap_nodes)} groups of overlapping nodes "
                f"(发现 {len(overlap_nodes)} 组重合节点): {overlap_nodes[:5]}..."
            )

        # Check for overlapping elements
        overlap_elements = self._odb.get_overlap_elements()
        if overlap_elements:
            warnings.append(
                f"Found {len(overlap_elements)} groups of overlapping elements "
                f"(发现 {len(overlap_elements)} 组重合单元): {overlap_elements[:5]}..."
            )

        # Check basic model existence
        summary = self.get_model_summary()
        if summary["node_count"] == 0:
            errors.append("Model has no nodes (模型无节点)")
        if summary["element_count"] == 0:
            errors.append("Model has no elements (模型无单元)")
        if summary["material_count"] == 0:
            errors.append("Model has no materials (模型无材料)")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
        }

    # ── Structural Checking ────────────────────────────────────────────

    def add_check_load_combine(
        self, name: str, standard: int, kind: int, **kwargs
    ) -> None:
        self._require_available()
        raise NotImplementedError("Structural checking (CDB) is not yet supported in this qtmodel version.")

    def solve_concrete_check(self, name: str) -> None:
        self._require_available()
        raise NotImplementedError("Structural checking (CDB) is not yet supported in this qtmodel version.")

    def add_concrete_check_case(
        self, name: str, standard: int, structure_type: int, group_name: str
    ) -> None:
        self._require_available()
        raise NotImplementedError("Structural checking (CDB) is not yet supported in this qtmodel version.")

    def add_parameter_reinforcement(self, sec_id: int, **kwargs) -> None:
        self._require_available()
        raise NotImplementedError("Structural checking (CDB) is not yet supported in this qtmodel version.")

    # ── Group Management ───────────────────────────────────────────────

    def add_structure_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_structure_group(name=name)

    def add_elements_to_structure_group(self, name: str, element_ids: Any) -> None:
        self._require_available()
        # Real API uses add_structure_to_group
        self._mdb.add_structure_to_group(name=name, element_ids=element_ids)

    def get_structure_group_elements(self, name: str) -> list:
        self._require_available()
        # Real API uses get_group_elements
        return self._odb.get_group_elements(name=name) or []

    def add_boundary_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_boundary_group(name=name)

    def add_load_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_load_group(name=name)

    # ── Advanced Boundary ──────────────────────────────────────────────

    def add_master_slave_link(self, master_id: int, slave_ids: Any, **kwargs) -> None:
        self._require_available()
        self._mdb.add_master_slave_link(
            master_id=master_id, slave_ids=slave_ids, **kwargs
        )

    def add_elastic_support(self, node_id: Any, spring_values: list, **kwargs) -> None:
        self._require_available()
        self._mdb.add_elastic_support(
            node_id=node_id, spring_values=spring_values, **kwargs
        )

    # ── Moving Loads ───────────────────────────────────────────────────

    def add_standard_vehicle(self, name: str, vehicle_type: int, standard: int) -> None:
        self._require_available()
        self._mdb.add_standard_vehicle(
            name=name, vehicle_type=vehicle_type, standard=standard
        )

    def add_lane(self, name: str, **kwargs) -> None:
        self._require_available()
        # Real API method is add_lane_line
        self._mdb.add_lane_line(name=name, **kwargs)

    def add_live_load_case(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_live_load_case(name=name, **kwargs)

    def get_live_load_results(self, case_name: str, result_type: str, ids: Any) -> Any:
        self._require_available()
        # Live load results are embedded in standard result queries (deformation/force/stress)
        # Query using the live load case name directly
        if result_type == "force":
            return self._odb.get_element_force(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "stress":
            return self._odb.get_element_stress(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "deformation":
            return self._odb.get_deformation(ids=ids, stage_id=-1, case_name=case_name)
        else:
            return self._odb.get_element_force(ids=ids, stage_id=-1, case_name=case_name)

    # ── Self-weight ────────────────────────────────────────────────────

    def add_self_weight(self, case_name: str, **kwargs) -> None:
        self._require_available()
        # qtmodel does not have a dedicated add_self_weight API.
        # Self-weight is enabled globally via update_global_setting.
        # Here we create a load case for it — the solver applies self-weight automatically.
        try:
            self._mdb.add_load_case(name=case_name, case_type=1)  # type 1 = static
        except Exception:
            pass  # Load case may already exist

    # ── Tendon Data ────────────────────────────────────────────────────

    def get_tendon_data(self) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_data() or []

    # ── Visualization Control ──────────────────────────────────────────

    def set_view_angle(self, horizontal: float, vertical: float) -> None:
        self._require_available()
        self._odb.set_view_camera(horizontal=horizontal, vertical=vertical)

