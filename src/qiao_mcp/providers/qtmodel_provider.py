"""
QTModel Provider — adapter for 桥通 (QiaoTong) bridge analysis software.

This provider wraps the `qtmodel` Python API (mdb/odb/cdb) to implement
the BridgeProvider interface.

桥通软件后端适配器，封装 qtmodel Python API。
"""

import ast
import json
from typing import Any

from qiao_mcp.providers import BridgeProvider


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
        """Initialize the qtmodel provider and check availability."""
        self._mdb = None
        self._odb = None
        self._cdb = None
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
            self._cdb = qtmodel.cdb
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

    def get_software_name(self) -> str:
        return "QiaoTong (桥通)"

    def get_llm_instructions(self) -> str:
        return """
        ### Self-Weight (自重) — QiaoTong (桥通) computes it automatically from geometry
        Self-weight in QiaoTong is NOT a load case and NOT an element load. The solver
        computes it from section area × material unit weight × gravity. What you control
        is WHICH construction stage accounts for each structure group's self-weight.

        CORRECT approach:
        • One-shot bridge (一次成桥): create the model, then call merge_operation_stage
          — self-weight is included automatically. No self-weight load case is needed.
        • Staged construction: use set_self_weight_stage(stage_name, structure_group_name,
          weight_stage_id) to choose the stage that carries each group's self-weight
          (weight_stage_id: 0=none, 1=this stage, n=stage n).
        • Gravity defaults to 9.8 m/s²; change it with set_gravity if needed.

        DO NOT do this (MIDAS/SAP2000 approach — WRONG for QiaoTong):
        ✗ Create a load case named "自重" and expect it to hold self-weight
        ✗ Calculate area × density × g manually
        ✗ Call apply_beam_distributed_load with self-weight kN/m values

        ### Node & Element creation — use batch tools to keep AI calls concise
        ✓ create_nodes_linear(count=101, start_x=0, spacing_x=1.0)   # 101 nodes in 1 call
        ✓ create_beam_elements_linear(node_id_start=1, count=100, mat_id=1, sec_id=1)
        ✗ Do not pass a raw list of 101 coordinate pairs to create_nodes

        ### Initialization — 危险操作
        • Only call initialize_model(confirm=True) when the user explicitly says "新建模型"
        • Never call it to fix your own mistakes — ask the user
        • remove_nodes / remove_elements require confirm_delete_all=True when deleting all

        ### Load case types (case_type must be a Chinese string):
        "施工阶段荷载" | "恒载" | "活载" | "制动力" | "风荷载"
        "体系温度荷载" | "梯度温度荷载"
        "长轨伸缩挠曲力荷载" | "脱轨荷载" | "长轨断轨力荷载"
        "船舶撞击荷载" | "汽车撞击荷载" | "用户定义荷载"
        """


    def _require_available(self):
        """Raise error if provider is not available."""
        if not self._available:
            raise RuntimeError(
                f"qtmodel provider unavailable: {self._unavailable_reason}"
            )

    # ── Generic API gateway (逃生舱) ───────────────────────────────────

    # 危险/长耗时操作必须走各自带防护的专用工具，禁止经逃生舱直呼
    _API_BLOCKLIST = {"initial", "do_solve"}

    def _resolve_api_object(self, api_object: str):
        obj = {"mdb": self._mdb, "odb": self._odb, "cdb": self._cdb}.get(api_object)
        if obj is None:
            raise ValueError(f"Unknown api_object '{api_object}'. Use: mdb, odb, cdb")
        return obj

    def list_api_methods(self, api_object: str, pattern: str = "") -> list[dict]:
        """List callable qtmodel API methods with signatures, filtered by substring."""
        import inspect

        self._require_available()
        obj = self._resolve_api_object(api_object)
        out = []
        for name in dir(obj):
            if name.startswith("_") or name in self._API_BLOCKLIST:
                continue
            if pattern and pattern.lower() not in name.lower():
                continue
            fn = getattr(obj, name)
            if not callable(fn):
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                sig = "(...)"
            out.append({"method": name, "signature": sig})
        return out

    def call_api(self, api_object: str, method: str, kwargs: dict | None = None) -> Any:
        """Call a whitelisted qtmodel API method after validating the signature."""
        import inspect

        self._require_available()
        obj = self._resolve_api_object(api_object)
        if method.startswith("_") or method in self._API_BLOCKLIST:
            raise ValueError(
                f"Method '{method}' is not callable via the gateway "
                f"(该方法不允许经逃生舱调用，请使用对应的专用工具)"
            )
        fn = getattr(obj, method, None)
        if fn is None or not callable(fn):
            raise ValueError(
                f"{api_object} has no method '{method}' "
                f"(方法不存在，可用 list 模式按关键字检索)"
            )
        kwargs = kwargs or {}
        sig = inspect.signature(fn)
        try:
            sig.bind(**kwargs)
        except TypeError as e:
            raise ValueError(
                f"Arguments do not match (参数不匹配): {e}. Real signature (真实签名): {method}{sig}"
            ) from e
        result = self._parse(fn(**kwargs))
        if api_object == "mdb" and method.startswith(("add_", "update_", "remove_")):
            self._mdb.update_model()
        return result

    # ── Model Information ──────────────────────────────────────────────

    @staticmethod
    def _parse(result: Any) -> Any:
        """Parse string result from qtmodel API into Python object."""
        if isinstance(result, str):
            cleaned = result.strip()
            if not cleaned:
                return cleaned
                
            # Fallback to standard JSON parsing first (handles true/false/null)
            try:
                return json.loads(cleaned)
            except Exception:
                pass

            # QtModel sometimes returns Python string representations (e.g., single quotes for strings)
            # which json.loads fails to parse. ast.literal_eval handles these robustly.
            try:
                parsed = ast.literal_eval(cleaned)
                return parsed
            except Exception:
                pass
                
        return result


    @staticmethod
    def _validate_ids(ids, required: bool = False):
        """Validate and normalize ids input for robust error handling."""
        if ids is None:
            if required:
                raise ValueError("ids parameter is required but was empty or None.")
            return None
            
        if isinstance(ids, str):
            cleaned = ids.strip()
            if not cleaned:
                if required:
                    raise ValueError("ids string cannot be empty.")
                return None
            return cleaned
            
        if isinstance(ids, (int, float)):
            if ids <= 0:
                raise ValueError(f"Invalid ID: {ids}. IDs must be positive integers.")
            return int(ids)
            
        if isinstance(ids, (list, tuple)):
            if not ids and required:
                raise ValueError("ids list cannot be empty.")
            valid_ids = []
            for i in ids:
                try:
                    val = int(i)
                    if val <= 0:
                        raise ValueError(f"Invalid ID in list: {i}. IDs must be positive.")
                    valid_ids.append(val)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid ID format in list: {i}") from e
            return valid_ids
            
        raise ValueError(f"Unsupported ids type: {type(ids)}. Expected int, list, or string.")

    def _safe_get(self, fn_name: str, *args, **kwargs) -> Any:
        """Call an odb method by name, auto-parse JSON, return None on error."""
        fn = getattr(self._odb, fn_name, None)
        if fn is None:
            # Fallback: if this python version of qtmodel wrapper is missing the method, 
            # attempt to send it directly as a REST command header to the running QT Server.
            try:
                from qtmodel.core.qt_server import QtServer
                header = fn_name.replace("_", "-").upper()
                raw_result = QtServer.send_dict(header=header)
                return self._parse(raw_result)
            except Exception:
                return None
                
        try:
            return self._parse(fn(*args, **kwargs))
        except Exception:
            return None

    @staticmethod
    def _count(result) -> int:
        if isinstance(result, (list, dict)):
            return len(result)
        return 0

    def get_model_summary(self) -> dict[str, Any]:
        self._require_available()
        return {
            "node_count":            self._count(self._safe_get("get_node_data")),
            "element_count":         self._count(self._safe_get("get_element_data")),
            "material_count":        self._count(self._safe_get("get_material_data")),
            "section_count":         self._count(self.get_section_names()),
            "stage_count":           self._count(self.get_stage_names()),
            "load_case_count":       self._count(self.get_load_case_names()),
            "structure_group_count": self._count(self._safe_get("get_structure_group_names")),
            "boundary_group_count":  self._count(self._safe_get("get_boundary_group_names")),
        }

    @staticmethod
    def _to_dicts(result: Any) -> list[dict]:
        """Normalize a query result to a list of plain dicts.

        qtmodel 的 get_node_data/get_element_data 返回 Node/Element 对象，
        其 __repr__/__str__ 返回 dict（非字符串），直接 JSON 序列化会崩溃；
        此处统一用对象的 to_dict() 拍平为普通 dict。
        """
        if result is None:
            return []
        if isinstance(result, dict):
            result = [result]
        if not isinstance(result, list):
            return []
        out = []
        for item in result:
            if isinstance(item, dict):
                out.append(item)
            elif hasattr(item, "to_dict"):
                out.append(item.to_dict())
            else:
                out.append(item)
        return out

    def get_node_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        result = self._parse(
            self._odb.get_node_data(ids=ids) if ids is not None else self._odb.get_node_data()
        )
        return self._to_dicts(result)

    def get_element_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        result = self._parse(
            self._odb.get_element_data(ids=ids) if ids is not None else self._odb.get_element_data()
        )
        return self._to_dicts(result)

    def get_material_data(self) -> list[dict]:
        self._require_available()
        result = self._parse(self._odb.get_material_data())
        return result if isinstance(result, list) else []

    def get_section_data(self, sec_id: int, position: int = 0) -> dict:
        self._require_available()
        result = self._parse(self._odb.get_section_data(sec_id, position=position))
        return result if isinstance(result, dict) else {}

    def get_section_names(self) -> dict[str, str] | list:
        """Return section info (dict of id->name, or list of IDs/dicts depending on API version)."""
        self._require_available()
        
        # New API returns JSON dict {"3": "上横梁", "4": "下横梁", ...}
        for method in ("get_section_names", "get_section_ids", "get_all_section_data"):
            result = self._safe_get(method)
            # dict output: {"3": "SectionName"}
            if isinstance(result, dict):
                return {str(k): str(v) for k, v in result.items()}
            # list output: [{"id": 3, "name": "SectionName"}] or [3, 4]
            if isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    return {str(d.get("id", i + 1)): d.get("name", f"Section {i + 1}") for i, d in enumerate(result)}
                return result
        return {}

    def get_boundary_data(self) -> dict[str, list[dict]]:
        self._require_available()
        return {
            "general_supports": self._safe_get("get_general_support_data") or [],
            "elastic_links":    self._safe_get("get_elastic_link_data") or [],
            "elastic_supports": self._safe_get("get_elastic_support_data") or [],
            "master_slave_links": self._safe_get("get_master_slave_link_data") or [],
            "beam_constraints": self._safe_get("get_beam_constraint_data") or [],
        }

    def get_load_case_names(self) -> list[str]:
        """Return load case names."""
        self._require_available()
        # Older version uses get_load_case_names, newer uses get_case_names
        for method in ("get_load_case_names", "get_case_names"):
            result = self._safe_get(method)
            if isinstance(result, list):
                return result
        return []

    def get_stage_names(self) -> list[str]:
        """Return construction stage names."""
        self._require_available()
        for method in ("get_stage_names", "get_stage_name"):
            result = self._safe_get(method)
            if isinstance(result, list):
                return result
        return []

    def get_structure_group_names(self) -> list[str]:
        self._require_available()
        result = self._safe_get("get_structure_group_names")
        return result if isinstance(result, list) else []

    # ── Modeling Operations ────────────────────────────────────────────

    def initialize_model(self) -> None:
        self._require_available()
        self._mdb.initial()

    def update_model(self) -> None:
        """Refresh the model display in QiaoTong software."""
        self._require_available()
        self._mdb.update_model()

    def save_model_file(self, file_path: str) -> None:
        self._require_available()
        self._mdb.save_file(file_path=file_path)

    def open_model_file(self, file_path: str) -> None:
        self._require_available()
        self._mdb.open_file(file_path=file_path)

    def remove_unused_sections(self) -> None:
        self._require_available()
        self._mdb.remove_unused_sections()
        self._mdb.update_model()

    def add_nodes(self, node_data: list[list[float]], **kwargs) -> None:
        self._require_available()
        if not node_data:
            raise ValueError("node_data cannot be empty")
        self._mdb.add_nodes(node_data=node_data, **kwargs)
        self._mdb.update_model()

    def add_elements(self, ele_data: list[list], **kwargs) -> None:
        self._require_available()
        if not ele_data:
            raise ValueError("ele_data cannot be empty")
        self._mdb.add_elements(ele_data=ele_data, **kwargs)
        self._mdb.update_model()

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
        self._mdb.update_model()

    def add_time_parameter(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_parameter(**kwargs)
        self._mdb.update_model()

    def add_creep_function(self, name: str, creep_data: list, scale_factor: float = 1) -> None:
        self._require_available()
        self._mdb.add_creep_function(name=name, creep_data=creep_data, scale_factor=scale_factor)
        self._mdb.update_model()

    def add_shrink_function(self, name: str, shrink_data: list | None = None, scale_factor: float = 1) -> None:
        self._require_available()
        self._mdb.add_shrink_function(name=name, shrink_data=shrink_data, scale_factor=scale_factor)
        self._mdb.update_model()

    def add_thickness(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_thickness(**kwargs)
        self._mdb.update_model()

    def add_effective_width(self, element_ids, **kwargs) -> None:
        self._require_available()
        self._mdb.add_effective_width(element_ids=element_ids, **kwargs)
        self._mdb.update_model()

    def add_tapper_section_group(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tapper_section_group(**kwargs)
        self._mdb.update_model()

    def add_section(self, name: str, sec_type: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_section(name=name, sec_type=sec_type, **kwargs)
        self._mdb.update_model()

    def add_tapper_section_by_id(self, name: str, begin_id: int, end_id: int, shear_consider: bool = True, sec_normalize: bool = False) -> None:
        self._require_available()
        self._mdb.add_tapper_section_by_id(name=name, begin_id=begin_id, end_id=end_id, shear_consider=shear_consider, sec_normalize=sec_normalize)
        self._mdb.update_model()

    def remove_section(self, ids: Any) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.remove_section(ids=ids)
        self._mdb.update_model()

    def update_section_bias(self, index: int, bias_type: str, center_type: str = "质心", shear_consider: bool = True, bias_point: list[float] | None = None, side_i: bool = True) -> None:
        self._require_available()
        kwargs = {}
        if bias_point is not None:
            kwargs["bias_point"] = bias_point
        self._mdb.update_section_bias(index=index, bias_type=bias_type, center_type=center_type, shear_consider=shear_consider, side_i=side_i, **kwargs)

    def update_section_property(self, index: int, sec_property: list[float], side_i: bool = True) -> None:
        self._require_available()
        self._mdb.update_section_property(index=index, sec_property=sec_property, side_i=side_i)

    def calculate_section_property(self) -> None:
        self._require_available()
        self._mdb.calculate_section_property()

    # ── Modify Operations ──────────────────────────────────────────────

    # qtmodel 的 Element 查询模型用字符串表示单元类型，update_element 则要求整数
    _ELE_TYPE_TO_INT = {"BEAM": 1, "LINK": 2, "CABLE": 3, "PLATE": 4}

    @staticmethod
    def _field(entity: Any, name: str) -> Any:
        """Read a field from a query-model object (attr) or parsed dict."""
        if isinstance(entity, dict):
            return entity.get(name)
        return getattr(entity, name, None)

    def update_node(self, node_id: int, **kwargs) -> None:
        self._require_available()
        # qtmodel 的 update_node 会把未传入的坐标按默认值 1 整体下发，
        # 部分更新会静默改写其余坐标；此处先读回当前坐标补齐缺省分量。
        if not {"x", "y", "z"} <= kwargs.keys():
            nodes = self.get_node_data(ids=node_id)
            if not nodes:
                raise ValueError(
                    f"Node {node_id} not found; cannot fill unchanged coordinates "
                    f"(节点 {node_id} 不存在，无法回填未指定坐标)"
                )
            for axis in ("x", "y", "z"):
                kwargs.setdefault(axis, self._field(nodes[0], axis))
        self._mdb.update_node(node_id=node_id, **kwargs)

    def update_node_id(self, node_id: int, new_id: int) -> None:
        self._require_available()
        self._mdb.update_node_id(node_id=node_id, new_id=new_id)

    def renumber_nodes(self, ids: Any = None, new_ids: Any = None) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is None:
            self._mdb.renumber_nodes()
        else:
            self._mdb.renumber_nodes(ids, new_ids)

    def move_nodes(self, ids: Any, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.move_nodes(ids=ids, offset_x=offset_x, offset_y=offset_y, offset_z=offset_z)

    def update_element(self, old_id: int, **kwargs) -> None:
        self._require_available()
        # 同 update_node：qtmodel 的 update_element 整体下发全部字段，
        # 未指定字段会被默认值覆盖（如 ele_type→1、beta_angle→0），
        # 先读回当前单元数据补齐（plate_type 查询模型不含，无法回填）。
        fields = ("ele_type", "node_ids", "beta_angle", "mat_id", "sec_id",
                  "initial_type", "initial_value")
        missing = [f for f in fields if f not in kwargs]
        if missing:
            elements = self.get_element_data(ids=old_id)
            if not elements:
                raise ValueError(
                    f"Element {old_id} not found; cannot fill unchanged fields "
                    f"(单元 {old_id} 不存在，无法回填未指定字段)"
                )
            current = elements[0]
            for f in missing:
                value = self._field(current, f)
                if f == "ele_type" and isinstance(value, str):
                    value = self._ELE_TYPE_TO_INT.get(value.upper(), value)
                if value is not None:
                    kwargs.setdefault(f, value)
        self._mdb.update_element(old_id=old_id, **kwargs)

    def update_element_id(self, old_id: int, new_id: int) -> None:
        self._require_available()
        self._mdb.update_element_id(old_id=old_id, new_id=new_id)

    def renumber_elements(self, element_ids: Any = None, new_ids: Any = None) -> None:
        self._require_available()
        if element_ids is None:
            self._mdb.renumber_elements()
        else:
            self._mdb.renumber_elements(element_ids, new_ids)

    def revert_local_orientation(self, ids: Any) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.revert_local_orientation(ids=ids)

    def update_element_material(self, ids: Any, mat_id: int) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.update_element_material(ids=ids, mat_id=mat_id)

    def update_frame_section(self, ids: Any, sec_id: int) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.update_frame_section(ids=ids, sec_id=sec_id)

    def update_element_beta(self, ids: Any, beta: float) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.update_element_beta(ids=ids, beta=beta)

    def update_element_node(self, element_id: int, node_ids: list) -> None:
        self._require_available()
        self._mdb.update_element_node(element_id, node_ids)

    def remove_structure_from_group(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.remove_structure_from_group(name=name, **kwargs)

    def remove_nodes(self, ids: Any = None) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is not None:
            self._mdb.remove_nodes(ids=ids)
        else:
            self._mdb.remove_nodes()

    def remove_elements(self, ids: Any = None, remove_free: bool = False) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is not None:
            self._mdb.remove_elements(ids=ids, remove_free=remove_free)
        else:
            self._mdb.remove_elements(remove_free=remove_free)

    def merge_nodes(self, ids: Any = None, tolerance: float = 1e-4) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is not None:
            self._mdb.merge_nodes(ids=ids, tolerance=tolerance)
        else:
            self._mdb.merge_nodes(tolerance=tolerance)


    def add_general_support(
        self, node_id: Any, boundary_info: list, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_general_support(
            node_id=node_id, boundary_info=boundary_info, **kwargs
        )
        self._mdb.update_model()

    def add_elastic_link(
        self, link_type: int, start_id: int, end_id: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_elastic_link(
            link_type=link_type, start_id=start_id, end_id=end_id, **kwargs
        )
        self._mdb.update_model()

    def add_beam_constraint(
        self, beam_id: int, info_i: list[bool] | None = None, info_j: list[bool] | None = None, group_name: str = ""
    ) -> None:
        self._require_available()
        kwargs: dict[str, Any] = {"beam_id": beam_id}
        if info_i is not None:
            kwargs["info_i"] = info_i
        if info_j is not None:
            kwargs["info_j"] = info_j
        if group_name:
            kwargs["group_name"] = group_name
        self._mdb.add_beam_constraint(**kwargs)
        self._mdb.update_model()

    def add_constraint_equation(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_constraint_equation(**kwargs)
        self._mdb.update_model()

    def remove_boundary(self, **kwargs) -> None:
        self._require_available()
        self._mdb.remove_boundary(**kwargs)
        self._mdb.update_model()

    # ── Load Operations ────────────────────────────────────────────────

    def add_load_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_load_group(name=name)
        self._mdb.update_model()

    def add_load_case(self, name: str, case_type: str = "施工阶段荷载", desc: str = "") -> None:
        self._require_available()
        self._mdb.add_load_case(name=name, case_type=case_type)
        self._mdb.update_model()

    def add_load_combine(self, index: int = -1, name: str = "", combine_type: int = 1, describe: str = "", combine_info: list[tuple] | None = None) -> None:
        self._require_available()
        kwargs = {"index": index, "name": name, "combine_type": combine_type, "describe": describe}
        if combine_info is not None:
            kwargs["combine_info"] = combine_info
        self._mdb.add_load_combine(**kwargs)
        self._mdb.update_model()

    def add_nodal_force(
        self, node_id: Any, case_name: str, load_info: list, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_nodal_force(
            node_id=node_id, case_name=case_name, load_info=load_info, **kwargs
        )
        self._mdb.update_model()

    def add_beam_element_load(
        self, element_id: Any, case_name: str, load_type: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_beam_element_load(
            element_id=element_id, case_name=case_name, load_type=load_type, **kwargs
        )
        self._mdb.update_model()

    def add_system_temperature(
        self, element_id: Any, case_name: str, temperature: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_element_temperature(
            element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
        )
        self._mdb.update_model()

    def add_gradient_temperature(
        self, element_id: Any, case_name: str, temperature: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_gradient_temperature(
            element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
        )
        self._mdb.update_model()


    def add_custom_temperature(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_custom_temperature(element_id=element_id, case_name=case_name, **kwargs)
        self._mdb.update_model()

    def add_beam_section_temperature(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_beam_section_temperature(element_id=element_id, case_name=case_name, **kwargs)
        self._mdb.update_model()

    def add_initial_tension_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_initial_tension_load(element_id=element_id, case_name=case_name, **kwargs)
        self._mdb.update_model()

    def add_cable_length_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_cable_length_load(element_id=element_id, case_name=case_name, **kwargs)
        self._mdb.update_model()

    def add_plate_element_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_plate_element_load(element_id=element_id, case_name=case_name, **kwargs)
        self._mdb.update_model()

    def add_distribute_plane_load(self, index: int, case_name: str, type_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_distribute_plane_load(index=index, case_name=case_name, type_name=type_name, **kwargs)
        self._mdb.update_model()

    def add_support_settlement(
        self, node_id: Any, case_name: str, displacement_info: list, **kwargs
    ) -> None:
        self._require_available()
        # qtmodel 的参数名为 load_info
        self._mdb.add_node_displacement(
            node_id=node_id, case_name=case_name, load_info=displacement_info, **kwargs
        )
        self._mdb.update_model()

    # ── Tendon Operations ──────────────────────────────────────────────

    def add_tendon_property(self, name: str, tendon_type: int, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_property(name=name, tendon_type=tendon_type, **kwargs)
        self._mdb.update_model()

    def add_tendon_2d(self, name: str, property_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_2d(name=name, property_name=property_name, **kwargs)
        self._mdb.update_model()

    def add_tendon_3d(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_3d(name=name, **kwargs)
        self._mdb.update_model()

    def add_tendon_elements(self, ids: Any) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        self._mdb.add_tendon_elements(ids=ids)
        self._mdb.update_model()

    def add_pre_stress(
        self, case_name: str, tendon_name: str, force: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_pre_stress(
            case_name=case_name, tendon_name=tendon_name, force=force, **kwargs
        )
        self._mdb.update_model()

    # ── Construction Stage Operations ──────────────────────────────────

    def add_construction_stage(self, name: str, duration: float, **kwargs) -> None:
        self._require_available()
        self._mdb.add_construction_stage(name=name, duration=duration, **kwargs)
        self._mdb.update_model()

    def merge_all_stages(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.merge_all_stages(name=name, **kwargs)
        self._mdb.update_model()

    def remove_construction_stage(self, name: str = "") -> None:
        self._require_available()
        self._mdb.remove_construction_stage(name=name)
        self._mdb.update_model()

    def update_construction_stage(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.update_construction_stage(name=name, **kwargs)
        self._mdb.update_model()

    def switch_display_stage(self, stage_name: str) -> None:
        self._require_available()
        self._mdb.update_view_stage(stage_name=stage_name)
        self._mdb.update_model()

    # ── Analysis Operations ────────────────────────────────────────────

    def update_project_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_project_setting(**kwargs)
        self._mdb.update_model()

    def update_construction_stage_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_construction_stage_setting(**kwargs)
        self._mdb.update_model()

    def update_self_vibration_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_self_vibration_setting(**kwargs)
        self._mdb.update_model()

    def update_bulking_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_bulking_setting(**kwargs)
        self._mdb.update_model()

    def add_nodal_mass(self, node_id, **kwargs) -> None:
        self._require_available()
        self._mdb.add_nodal_mass(node_id=node_id, **kwargs)
        self._mdb.update_model()

    def add_load_to_mass(self, name: str, factor: float = 1.0) -> None:
        self._require_available()
        self._mdb.add_load_to_mass(name=name, factor=factor)
        self._mdb.update_model()

    def add_spectrum_function(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_spectrum_function(**kwargs)
        self._mdb.update_model()

    def add_spectrum_case(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_spectrum_case(**kwargs)
        self._mdb.update_model()

    def add_time_history_function(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_history_function(**kwargs)
        self._mdb.update_model()

    def add_time_history_case(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_history_case(**kwargs)
        self._mdb.update_model()

    def run_analysis(self, read_timeout: int = 3600) -> None:
        """启动求解并阻塞至后台任务真正结束。

        2.5.0 起 do_solve 默认 wait=False——只启动后台求解便立即返回（内部
        sleep(3)）。若不显式等待，调用方会在求解仍在进行时就去取结果。
        这里用 wait=True 让 qtmodel 轮询 GET-PROJECT-SOLVE-STATUS 直到收敛，
        并把 read_timeout 作为求解总时限（而非单次 HTTP 超时）。

        求解失败/取消时 qtmodel 抛 RuntimeError，超时抛 TimeoutError，
        均由上层转为 ToolError。
        """
        self._require_available()
        self._mdb.do_solve(
            wait=True,
            poll_interval=2.0,
            max_wait=read_timeout,
            status_read_timeout=30,
        )

    def add_node_tandem(self, *args, **kwargs):
        self._require_available()
        return self._mdb.add_node_tandem(*args, **kwargs)

    def add_influence_plane(self, *args, **kwargs):
        self._require_available()
        return self._mdb.add_influence_plane(*args, **kwargs)

    # ── Result Extraction ──────────────────────────────────────────────

    def get_deformation(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        return self._odb.get_deformation(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_force(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        return self._odb.get_element_force(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_stress(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        return self._odb.get_element_stress(ids=ids, stage_id=stage_id, **kwargs)

    def get_reaction(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        return self._odb.get_reaction(ids=ids, stage_id=stage_id, **kwargs)

    def get_vibration_modal_results(self, mode: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_vibration_modal_results(mode=mode)

    def get_buckling_modal_results(self, mode: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_buckling_modal_results(mode=mode)


    def get_thickness_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_thickness_data(*args, **kwargs)

    def get_node_id(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_node_id(*args, **kwargs)

    def get_group_nodes(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_group_nodes(*args, **kwargs)

    def get_elements_by_point(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elements_by_point(*args, **kwargs)

    def get_elements_by_material(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elements_by_material(*args, **kwargs)

    def get_elements_by_section(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elements_by_section(*args, **kwargs)

    def get_element_type(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_element_type(*args, **kwargs)

    def get_element_weight(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_element_weight(*args, **kwargs)

    def get_span_supports(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_span_supports(*args, **kwargs)

    def get_span_elements(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_span_elements(*args, **kwargs)

    def get_section_shape(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_section_shape(*args, **kwargs)

    def get_section_property(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_section_property(*args, **kwargs)

    def get_section_property_by_loops(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_section_property_by_loops(*args, **kwargs)

    def get_section_property_by_lines(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_section_property_by_lines(*args, **kwargs)

    def get_node_local_axis_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_node_local_axis_data(*args, **kwargs)

    def get_constraint_equation_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_constraint_equation_data(*args, **kwargs)

    def get_effective_width_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_effective_width_data(*args, **kwargs)

    def get_tendon_property_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_tendon_property_data(*args, **kwargs)

    def get_pre_stress_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_pre_stress_load_data(*args, **kwargs)

    def get_node_mass_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_node_mass_data(*args, **kwargs)

    def get_nodal_force_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_nodal_force_load_data(*args, **kwargs)

    def get_nodal_displacement_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_nodal_displacement_load_data(*args, **kwargs)

    def get_beam_element_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_beam_element_load_data(*args, **kwargs)

    def get_plate_element_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_plate_element_load_data(*args, **kwargs)

    def get_initial_tension_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_initial_tension_load_data(*args, **kwargs)

    def get_cable_length_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_cable_length_load_data(*args, **kwargs)

    def get_deviation_parameters(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_deviation_parameters(*args, **kwargs)

    def get_deviation_load_data(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_deviation_load_data(*args, **kwargs)

    def get_elements_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elements_of_stage(*args, **kwargs)

    def get_nodes_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_nodes_of_stage(*args, **kwargs)

    def get_groups_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_groups_of_stage(*args, **kwargs)

    def get_self_concurrent_reaction(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_self_concurrent_reaction(*args, **kwargs)

    def get_all_concurrent_reaction(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_all_concurrent_reaction(*args, **kwargs)

    def get_concurrent_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_concurrent_force(*args, **kwargs)

    def get_elastic_link_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elastic_link_force(*args, **kwargs)

    def get_constrain_equation_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_constrain_equation_force(*args, **kwargs)

    def get_cable_element_length(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_cable_element_length(*args, **kwargs)

    def get_period_and_vibration_results(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_period_and_vibration_results(*args, **kwargs)

    def get_buckling_eigenvalue(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_buckling_eigenvalue(*args, **kwargs)
    def get_tendon_loss_results(self, name: str, stage_id: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_loss_results(name=name, stage_id=stage_id)

    def get_tendon_position_result(self, name: str) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_position_result(name=name)

    def get_tendon_length_result(self) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_length_result()

    # ── Visualization ──────────────────────────────────────────────────

    def display_node_id(self, show_id: bool = True) -> None:
        self._require_available()
        self._odb.display_node_id(show_id=show_id)

    def display_element_id(self, show_id: bool = True) -> None:
        self._require_available()
        self._odb.display_element_id(show_id=show_id)

    def set_view_direction(self, **kwargs) -> None:
        self._require_available()
        self._odb.set_view_direction(**kwargs)

    def activate_structure(self, **kwargs) -> None:
        self._require_available()
        self._odb.activate_structure(**kwargs)

    def set_render(self, flag: bool = True) -> None:
        self._require_available()
        self._odb.set_render(flag=flag)

    def reset_display(self) -> None:
        self._require_available()
        self._odb.reset_display()

    def set_unit(self, unit_force: str = 'KN', unit_length: str = 'MM') -> None:
        self._require_available()
        self._odb.set_unit(unit_force=unit_force, unit_length=unit_length)

    def change_construct_stage(self, stage: int = 0) -> None:
        self._require_available()
        self._odb.change_construct_stage(stage=stage)

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
        self, name: str, standard: int, combine_type: int, combine_method: int, **kwargs
    ) -> None:
        self._require_available()
        # 2.5.0 起：旧 kind → combine_type（组合类型：基本/偶然/标准…），
        # 旧 combine_type → combine_method（组合方式：1-相加并判别 2-包络），index 已移除
        self._cdb.add_check_load_combine(
            name=name,
            standard=standard,
            combine_type=combine_type,
            combine_method=combine_method,
            **kwargs,
        )

    def solve_concrete_check(
        self,
        name: str,
        wait: bool = True,
        max_wait: float | None = None,
        poll_interval: float = 5.0,
    ) -> None:
        """同步指定检算工况后启动检算；wait=True 时轮询至后台任务结束。

        2.5.0 起 solve_concrete_check 不再接受 name，改为对"当前检算数据"求解，
        故先用 import_concrete_check_case 把目标工况同步为当前 CSAN 检算数据。
        """
        self._require_available()
        self._cdb.import_concrete_check_case(case_name=name)
        self._cdb.solve_concrete_check(
            wait=wait,
            poll_interval=poll_interval,
            max_wait=max_wait,
        )

    def add_concrete_check_case(
        self, name: str, standard: int, structure_type: int, group_name: str
    ) -> None:
        self._require_available()
        self._cdb.add_concrete_check_case(name=name, standard=standard, structure_type=structure_type, group_name=group_name)

    def add_parameter_reinforcement(self, sec_id: int, **kwargs) -> None:
        self._require_available()
        self._cdb.add_parameter_reinforcement(sec_id=sec_id, **kwargs)

    def add_check_stirrup(
        self,
        stirrup_id: int,
        name: str,
        stirrup_type: int = 1,
        rebar_material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter_m: float = 0.020,
        spacing_m: float = 0.2,
        core_diameter_m: float = 0.0,
    ) -> None:
        """添加检算箍筋定义（2.5.0 起取代 add_steel_hoop）。

        入参统一用 SI（米），此处换算为 qtmodel 2.5.0 要求的单位：
        箍筋直径 m → mm；间距与核心直径仍为 m。
        """
        self._require_available()
        self._cdb.add_check_stirrup(
            stirrup_id=stirrup_id,
            name=name,
            stirrup_type=stirrup_type,
            rebar_material_id=rebar_material_id,
            limbs_number=limbs_number,
            loops_number=loops_number,
            stirrup_diameter=diameter_m * 1000.0,  # m → mm
            stirrup_spacing=spacing_m,
            core_diameter=core_diameter_m,
        )

    def update_vertical_steel_tendon(
        self,
        limbs_number: int = 0,
        area_m2: float = 0.000804,
        spacing_m: float = 0.2,
        effective_prestress_pa: float = 8.0e8,
        fpd_pa: float = 9.0e8,
    ) -> None:
        """修改竖向钢束设置（2.5.0 起取代 update_vertical_steel_hoop）。

        入参统一用 SI（m²/Pa），此处换算为 qtmodel 2.5.0 要求的单位：
        面积 m² → mm²（×1e6）；应力 Pa → MPa（÷1e6）。
        """
        self._require_available()
        self._cdb.update_vertical_steel_tendon(
            limbs_number=limbs_number,
            single_limb_area=area_m2 * 1.0e6,  # m² → mm²
            spacing=spacing_m,
            effective_prestress=effective_prestress_pa / 1.0e6,  # Pa → MPa
            strength_design_value=fpd_pa / 1.0e6,  # Pa → MPa
        )

    def get_reinforcement_data(self) -> dict[str, Any]:
        self._require_available()
        return self._cdb.get_reinforcement_data()

    # ── Concrete Check: 2.5.0 新增能力 ─────────────────────────────────
    #
    # 说明：cdb 的检算设置类接口（*_analysis_setting）在 qtmodel 源码与官方
    # 文档中均未标注量纲，但从默认值可判定为 mm/MPa（如保护层 30.0=30mm、
    # 钢筋疲劳限值 145.0=145MPa）。因未见权威单位说明，此处**不做换算**，
    # 按原生单位透传，由工具层 docstring 明确告知调用方。

    # 查询：全部为读操作，直接透传 qtmodel 返回值
    _CHECK_QUERY_METHODS = {
        "case": "get_concrete_check_case",
        "basic_info": "get_check_case_basic_info",
        "materials": "get_check_case_material_infos",
        "vertical_prestress": "get_check_case_vertical_prestress_info",
        "stirrups": "get_check_case_stirrup_infos",
        "reinforcement": "get_check_case_reinforcement_data",
        "tendon_section": "get_check_case_prestress_tendon_sec_info",
        "section_property": "get_check_case_section_property",
        "element_table": "get_element_table_info",
        "solve_status": "get_concrete_check_solve_status",
        "normal_section_bearing_setting": "get_normal_section_bearing_analysis_setting",
        "oblique_shear_bearing_setting": "get_oblique_section_shear_bearing_analysis_setting",
        "limit_state_setting": "get_limit_state_method_analysis_setting",
        "normal_stress_setting": "get_normal_stress_analysis_setting",
        "crack_width_setting": "get_crack_width_analysis_setting",
        "moment_curvature_setting": "get_moment_curvature_curve_analysis_setting",
        "bearing_curve_setting": "get_bearing_curve_analysis_setting",
    }

    def get_check_data(self, kind: str, **kwargs) -> Any:
        """按 kind 读取检算数据；kind 到 qtmodel 方法的映射见 _CHECK_QUERY_METHODS。"""
        self._require_available()
        if kind in self._CHECK_QUERY_METHODS:
            method = getattr(self._cdb, self._CHECK_QUERY_METHODS[kind])
            return method(**{k: v for k, v in kwargs.items() if v is not None})
        # 需要参数的查询单独分派
        if kind == "stress":
            return self._cdb.get_concrete_check_stress_info(
                stress_type=kwargs.get("stress_type", 1),
                specific_load_type_name=kwargs.get("name", ""),
            )
        if kind == "load_table":
            return self._cdb.get_check_case_load_table_info(
                combine_type=kwargs.get("combine_type", 1),
                specific_load_type_name=kwargs.get("name", ""),
            )
        if kind == "shear_stirrup":
            ele_id = kwargs.get("element_id")
            return self._cdb.get_element_shear_stirrup_data(
                ele_id=-1 if ele_id is None else ele_id
            )
        if kind == "torsion_stirrup":
            ele_id = kwargs.get("element_id")
            return self._cdb.get_element_torsion_stirrup_data(
                ele_id=-1 if ele_id is None else ele_id
            )
        raise ValueError(f"unknown check data kind: {kind}")

    # 分析设置：kind → qtmodel update 方法；参数原样透传（原生 mm/MPa）
    _CHECK_SETTING_METHODS = {
        "normal_section_bearing": "update_normal_section_bearing_analysis_setting",
        "oblique_shear_bearing": "update_oblique_section_shear_bearing_analysis_setting",
        "limit_state": "update_limit_state_method_analysis_setting",
        "normal_stress": "update_normal_stress_analysis_setting",
        "crack_width": "update_crack_width_analysis_setting",
        "moment_curvature": "update_moment_curvature_curve_analysis_setting",
        "bearing_curve": "update_bearing_curve_analysis_setting",
    }

    def configure_check_analysis(self, kind: str, settings: dict[str, Any]) -> None:
        """更新某一类检算分析设置；settings 按 qtmodel 原生参数名与单位传入。"""
        self._require_available()
        if kind not in self._CHECK_SETTING_METHODS:
            raise ValueError(f"unknown analysis setting kind: {kind}")
        getattr(self._cdb, self._CHECK_SETTING_METHODS[kind])(**settings)

    def update_check_stirrup(
        self,
        stirrup_id: int,
        name: str,
        stirrup_type: int = 1,
        rebar_material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter_m: float = 0.020,
        spacing_m: float = 0.2,
        core_diameter_m: float = 0.0,
    ) -> None:
        """修改检算箍筋定义；直径由 m 换算为 qtmodel 要求的 mm。"""
        self._require_available()
        self._cdb.update_check_stirrup(
            stirrup_id=stirrup_id,
            name=name,
            stirrup_type=stirrup_type,
            rebar_material_id=rebar_material_id,
            limbs_number=limbs_number,
            loops_number=loops_number,
            stirrup_diameter=diameter_m * 1000.0,  # m → mm
            stirrup_spacing=spacing_m,
            core_diameter=core_diameter_m,
        )

    def remove_check_stirrup(self, stirrup_id: int = -1, name: str = "") -> None:
        self._require_available()
        self._cdb.remove_check_stirrup(stirrup_id=stirrup_id, name=name)

    def set_element_shear_stirrup(
        self,
        element_id: int,
        stirrup_i_y: int = 1,
        stirrup_i_x: int = 1,
        stirrup_j_y: int = 1,
        stirrup_j_x: int = 1,
    ) -> None:
        self._require_available()
        self._cdb.add_element_shear_stirrup(
            ele_id=element_id,
            stirrup_i_y=stirrup_i_y,
            stirrup_i_x=stirrup_i_x,
            stirrup_j_y=stirrup_j_y,
            stirrup_j_x=stirrup_j_x,
        )

    def set_element_torsion_stirrup(
        self, element_id: int, stirrup_i: int = 1, stirrup_j: int = 1
    ) -> None:
        self._require_available()
        self._cdb.add_element_torsion_stirrup(
            ele_id=element_id, stirrup_i=stirrup_i, stirrup_j=stirrup_j
        )

    def remove_element_stirrup(
        self, element_id: int = -1, remove_shear: bool = True, remove_torsion: bool = True
    ) -> None:
        """删除单元箍筋设置；element_id<=0 表示删除全部。"""
        self._require_available()
        self._cdb.remove_element_stirrup(
            ele_id=element_id, remove_shear=remove_shear, remove_torsion=remove_torsion
        )

    def open_check_case(self, name: str = "", file_path: str = "") -> Any:
        self._require_available()
        return self._cdb.open_concrete_check_case(name=name, file_path=file_path)

    def save_check_case(self, file_path: str = "") -> Any:
        """保存当前检算工况；给出 file_path 时另存为该路径。"""
        self._require_available()
        if file_path:
            return self._cdb.save_as_check_case(file_path=file_path)
        return self._cdb.save_check_case()

    # ── Group Management ───────────────────────────────────────────────

    def add_structure_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_structure_group(name=name)
        self._mdb.update_model()

    def update_structure_group_name(self, name: str, new_name: str) -> None:
        self._require_available()
        self._mdb.update_structure_group_name(name=name, new_name=new_name)
        self._mdb.update_model()

    def remove_structure_group(self, name: str = "") -> None:
        self._require_available()
        if name:
            self._mdb.remove_structure_group(name=name)
        else:
            self._mdb.remove_structure_group()
        self._mdb.update_model()

    def add_structure_to_group(
        self, name: str, node_ids: Any = None, element_ids: Any = None
    ) -> None:
        """Add nodes and/or elements to a structure group. 向结构组添加节点/单元"""
        self._require_available()
        self._mdb.add_structure_to_group(
            name=name, node_ids=node_ids, element_ids=element_ids
        )
        self._mdb.update_model()

    def add_elements_to_structure_group(self, name: str, element_ids: Any) -> None:
        self.add_structure_to_group(name=name, element_ids=element_ids)

    def get_structure_group_elements(self, name: str) -> list:
        self._require_available()
        # qtmodel 的参数名为 group_name
        return self._odb.get_group_elements(group_name=name) or []

    def add_boundary_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_boundary_group(name=name)
        self._mdb.update_model()

    # ── Advanced Boundary ──────────────────────────────────────────────

    def add_master_slave_link(self, master_id: int, slave_id: Any, **kwargs) -> None:
        self._require_available()
        self._mdb.add_master_slave_link(
            master_id=master_id, slave_id=slave_id, **kwargs
        )
        self._mdb.update_model()

    def add_elastic_support(
        self, node_id: Any, support_type: int = 1, boundary_info: list | None = None, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_elastic_support(
            node_id=node_id, support_type=support_type, boundary_info=boundary_info, **kwargs
        )
        self._mdb.update_model()

    # ── Moving Loads ───────────────────────────────────────────────────

    def add_standard_vehicle(
        self, name: str, standard_code: int = 1, load_type: str = "公路I级车道", **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_standard_vehicle(
            name=name, standard_code=standard_code, load_type=load_type, **kwargs
        )
        self._mdb.update_model()

    def add_lane(self, name: str, **kwargs) -> None:
        self._require_available()
        # Real API method is add_lane_line
        self._mdb.add_lane_line(name=name, **kwargs)
        self._mdb.update_model()

    def add_live_load_case(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_live_load_case(name=name, **kwargs)
        self._mdb.update_model()

    def get_live_load_results(self, case_name: str, result_type: str, ids: Any) -> Any:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        # Live load results are embedded in standard result queries (deformation/force/stress)
        # Query using the live load case name directly
        if result_type == "force":
            return self._odb.get_element_force(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "stress":
            return self._odb.get_element_stress(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "deformation":
            return self._odb.get_deformation(ids=ids, stage_id=-1, case_name=case_name)
        else:
            raise ValueError(
                f"Unknown result_type '{result_type}'. "
                "Available: force, stress, deformation"
            )

    # ── Self-weight ────────────────────────────────────────────────────

    def set_weight_stage(
        self, stage_name: str, structure_group_name: str = "默认结构组", weight_stage_id: int = 1
    ) -> None:
        """Set which construction stage accounts for a structure group's self-weight.

        QiaoTong 中自重不是一个"荷载工况"，而是由施工阶段的"计自重阶段号"控制：
        weight_stage_id: 0=不计自重, 1=本阶段, n=第 n 阶段。
        重力加速度由 update_project_setting(gravity=...) 决定。
        """
        self._require_available()
        self._mdb.update_weight_stage(
            name=stage_name,
            structure_group_name=structure_group_name,
            weight_stage_id=weight_stage_id,
        )
        self._mdb.update_model()

    # ── Tendon Data ────────────────────────────────────────────────────

    def get_tendon_data(self) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_data() or []

    # ── Visualization Control ──────────────────────────────────────────

    def set_view_angle(self, horizontal: float, vertical: float) -> None:
        self._require_available()
        self._odb.set_view_direction(
            horizontal_degree=horizontal, vertical_degree=vertical
        )

