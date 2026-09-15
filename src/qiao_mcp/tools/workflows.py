"""High-level workflows that build bridges using backend-resolved entity IDs."""

import math
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import BridgeWorkflowResult, PositiveInteger, PositiveNumber


def _record_id(record: dict, *keys: str) -> int:
    for key in keys:
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        if isinstance(value, str) and value.isdecimal() and int(value) > 0:
            return int(value)
    raise ToolError(f"Cannot resolve a positive entity ID from {record!r} (无法读回有效编号)")


def _material_id(provider: BridgeProvider, name: str) -> int | None:
    matches = {
        _record_id(row, "index", "mat_id", "material_id", "id")
        for row in provider.get_material_data()
        if row.get("name") == name
    }
    if len(matches) > 1:
        raise ToolInputError(f"Material name {name!r} is ambiguous (材料名不唯一)")
    return next(iter(matches), None)


def _section_id(provider: BridgeProvider, name: str) -> int | None:
    sections = provider.get_section_names()
    if isinstance(sections, dict):
        rows = [{"id": key, "name": value} for key, value in sections.items()]
    elif isinstance(sections, list):
        rows = []
        for section in sections:
            if isinstance(section, dict):
                rows.append(section)
            else:
                index = _record_id({"id": section}, "id")
                rows.append({**provider.get_section_data(index), "id": index})
    else:
        raise ToolError("Cannot read section names (无法读取截面名称)")
    matches = {
        _record_id(row, "index", "sec_id", "section_id", "id")
        for row in rows if row.get("name") == name
    }
    if len(matches) > 1:
        raise ToolInputError(f"Section name {name!r} is ambiguous (截面名不唯一)")
    return next(iter(matches), None)


def _positive(value: float, name: str) -> None:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ToolInputError(f"{name} must be finite and positive ({name} 必须为有限正数)")


def _element_count(value: int, minimum: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ToolInputError(f"{name} must be an integer >= {minimum}")


def _build_bridge(
    provider: BridgeProvider,
    *,
    spans: list[float],
    elements_per_span: int,
    material_name: str,
    section_name: str,
    self_weight_case: str,
    rectangle: tuple[float, float] | None,
) -> BridgeWorkflowResult:
    """Resolve properties first, then build from actual node IDs without clearing the model."""
    for label, value in (
        ("material_name", material_name), ("section_name", section_name),
        ("self_weight_case", self_weight_case),
    ):
        if not value.strip():
            raise ToolInputError(f"{label} must not be empty ({label} 不能为空)")

    # Read references before creating geometry; never pick an unrelated first section.
    sec_id = _section_id(provider, section_name)
    if sec_id is None and rectangle is None:
        raise ToolInputError(
            f"Section {section_name!r} must already exist; create it with create_section "
            "before this workflow (请先创建指定截面)"
        )
    mat_id = _material_id(provider, material_name)
    first_element_id = 1 + max(
        (_record_id(row, "index", "element_id", "ele_id", "id")
         for row in provider.get_element_data()), default=0,
    )
    load_groups = provider.get_load_group_names()
    load_cases = provider.get_load_case_names()

    if mat_id is None:
        provider.add_material(
            name=material_name, mat_type=1, standard=1, database=material_name,
        )
        mat_id = _material_id(provider, material_name)
        if mat_id is None:
            raise ToolError(f"Material {material_name!r} could not be read back after creation")
    if sec_id is None:
        assert rectangle is not None
        provider.add_section(name=section_name, sec_type="矩形", sec_info=list(rectangle))
        sec_id = _section_id(provider, section_name)
        if sec_id is None:
            raise ToolError(f"Section {section_name!r} could not be read back after creation")
    if "默认荷载组" not in load_groups:
        provider.add_load_group(name="默认荷载组")
    if self_weight_case not in load_cases:
        provider.add_load_case(name=self_weight_case, case_type="施工阶段荷载")

    node_data: list[list[float]] = []
    start = 0.0
    for span in spans:
        node_data.extend(
            [start + span * i / elements_per_span, 0.0, 0.0]
            for i in range(elements_per_span)
        )
        start += span
    node_data.append([start, 0.0, 0.0])
    node_ids = provider.add_nodes_returning_ids(node_data=node_data, is_merged=True)
    if (
        len(node_ids) != len(node_data)
        or len(set(node_ids)) != len(node_ids)
        or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in node_ids)
    ):
        raise ToolError(
            "Could not resolve one distinct node ID per coordinate; no elements or supports "
            "were written. Inspect get_model_data(kind='nodes') before retrying "
            "(节点编号读回不完整，尚未创建单元和支座)"
        )
    geometry = provider.check_node_chain_geometry(node_ids)
    if not geometry.get("ok") or "total_length" not in geometry:
        raise ToolError(
            f"Node geometry could not be verified: {geometry.get('reason', 'unknown')}. "
            "No elements or supports were written (节点几何未通过验证，尚未创建单元和支座)"
        )

    element_ids = list(range(first_element_id, first_element_id + len(node_ids) - 1))
    provider.add_elements(ele_data=[
        [element_id, 1, mat_id, sec_id, 0.0, node_i, node_j, 0, 0.0]
        for element_id, node_i, node_j in zip(
            element_ids, node_ids[:-1], node_ids[1:], strict=True,
        )
    ])
    support_positions = list(range(0, len(node_ids), elements_per_span))
    support_ids = [node_ids[position] for position in support_positions]
    for position, node_id in zip(support_positions, support_ids, strict=True):
        # One span uses a pin/roller. For multiple spans the piers restrain X.
        fixed_x = position == 0 if len(spans) == 1 else 0 < position < len(node_ids) - 1
        provider.add_general_support(
            node_id=node_id, boundary_info=[fixed_x, True, True, False, False, False],
        )
    return BridgeWorkflowResult.model_validate({
        "status": "success",
        "message": (
            "Bridge geometry and load case created (桥梁几何与荷载工况已创建). "
            "Self-weight is controlled by construction-stage settings; "
            "merge_operation_stage → apply loads → configure_analysis → run_analysis "
            "→ get_analysis_results."
        ),
        "spans": spans,
        "node_ids": node_ids,
        "element_ids": element_ids,
        "support_node_ids": support_ids,
        "material_id": mat_id,
        "section_id": sec_id,
        "load_case": self_weight_case,
    })


def register_workflow_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register workflows for standard straight bridge layouts."""

    @mcp.tool()
    def create_simple_beam_bridge(
        span: PositiveNumber = 20.0,
        num_elements: Annotated[int, Field(ge=2)] = 10,
        material_name: str = "C50",
        section_name: str = "矩形梁",
        section_width: PositiveNumber = 1.0,
        section_height: PositiveNumber = 1.5,
        self_weight_case: str = "SW",
    ) -> BridgeWorkflowResult:
        """Build a straight, simply supported beam along global X (创建简支梁桥).

        Use this for a standard pin/roller layout. For custom geometry or supports,
        use create_nodes_linear, create_beam_elements_linear and set_support.
        Requires an open model in an editable base stage. Reuses a material and
        section by exact name; creates missing concrete material / rectangle section.
        Nodes at matching coordinates are reused; elements receive unused IDs.
        Repeating the workflow can add duplicate elements and supports. It does not
        clear the model or roll back partial writes on error; save_model_file first.
        (复用同名属性及重合节点，追加梁和支座；失败不会自动回滚。)

        Args:
            span: Positive span in meters (正跨径，m)
            num_elements: Integer number of elements, at least 2 (单元数，至少2)
            material_name: Existing material name, or concrete database grade to create
                such as C50 (复用同名材料；缺失时按此混凝土牌号创建)
            section_name: Existing section name, or name of a new rectangle
                (复用同名截面；缺失时创建矩形截面)
            section_width: Positive rectangle width in meters; used only for a new section
                (新建矩形截面的正宽度，m)
            section_height: Positive rectangle height in meters; used only for a new section
                (新建矩形截面的正高度，m)
            self_weight_case: Load case to create or reuse. Self-weight itself is enabled
                through stage settings, not this name (荷载工况名，自重由阶段设置控制)

        Returns:
            Actual ordered node_ids, element_ids, support_node_ids, material_id,
            section_id, spans and load_case. Finish staging with merge_operation_stage,
            then configure_analysis and run_analysis before querying results.
        """
        _positive(span, "span")
        _element_count(num_elements, 2, "num_elements")
        _positive(section_width, "section_width")
        _positive(section_height, "section_height")
        try:
            return _build_bridge(
                provider, spans=[span], elements_per_span=num_elements,
                material_name=material_name, section_name=section_name,
                self_weight_case=self_weight_case, rectangle=(section_width, section_height),
            )
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"Could not complete simple beam bridge: {exc}. "
                "Earlier writes may remain; inspect the model before retrying (请先检查已写入的模型)."
            ) from exc

    @mcp.tool()
    def create_continuous_beam_bridge(
        spans: Annotated[list[PositiveNumber], Field(min_length=1)] | None = None,
        num_elements_per_span: PositiveInteger = 8,
        material_name: str = "C50",
        section_name: str = "箱梁截面",
        self_weight_case: str = "SW",
    ) -> BridgeWorkflowResult:
        """Build a straight continuous girder along global X (创建连续梁桥).

        Uses rollers at abutments and X/Y/Z restraints at interior piers, with free
        rotations. A single span uses a pin/roller. For different bearings, use the
        individual modeling tools. Requires an editable base-stage model and the named
        section already created. Reuses the named material, or creates concrete of that
        database grade. Coincident nodes are reused; new element IDs follow the existing
        maximum. Repeating adds elements/supports; failures can leave partial writes.
        Save the model before running (复用重合节点，追加单元；不清空模型、不自动回滚).

        Args:
            spans: Nonempty list of positive spans in meters; None uses [30, 50, 30]
                (正跨径列表，m；省略时为30+50+30)
            num_elements_per_span: Positive integer elements per span (每跨正整数单元数)
            material_name: Existing material name or concrete grade to create (材料名称/牌号)
            section_name: Exact name of an existing section; missing section fails before
                geometry is written (已有截面全名，缺失时在建模前报错)
            self_weight_case: Load case to create or reuse; self-weight is controlled by
                construction-stage settings (荷载工况名，自重由施工阶段设置控制)

        Returns:
            Actual ordered node_ids, element_ids, support_node_ids, material_id,
            section_id, spans and load_case. Then merge_operation_stage, apply loads,
            configure_analysis, run_analysis and get_analysis_results.
        """
        if spans is None:
            spans = [30.0, 50.0, 30.0]
        if not spans:
            raise ToolInputError("spans must not be empty (跨径列表不能为空)")
        for span in spans:
            _positive(span, "span")
        _positive(sum(spans), "total span")
        _element_count(num_elements_per_span, 1, "num_elements_per_span")
        try:
            return _build_bridge(
                provider, spans=spans, elements_per_span=num_elements_per_span,
                material_name=material_name, section_name=section_name,
                self_weight_case=self_weight_case, rectangle=None,
            )
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"Could not complete continuous beam bridge: {exc}. "
                "Earlier writes may remain; inspect the model before retrying (请先检查已写入的模型)."
            ) from exc
