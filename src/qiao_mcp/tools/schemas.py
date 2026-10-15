"""Shared, executable input constraints and stable MCP response schemas."""

from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

PositiveNumber = Annotated[float, Field(gt=0, allow_inf_nan=False)]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]
NonnegativeNumber = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveInteger = Annotated[int, Field(ge=1)]
PageLimit = Annotated[int, Field(ge=1, le=500)]
PageOffset = Annotated[int, Field(ge=0)]
TwoNumbers = Annotated[list[FiniteNumber], Field(min_length=2, max_length=2)]
ThreeNumbers = Annotated[list[FiniteNumber], Field(min_length=3, max_length=3)]
FourNumbers = Annotated[list[FiniteNumber], Field(min_length=4, max_length=4)]
FiveNumbers = Annotated[list[FiniteNumber], Field(min_length=5, max_length=5)]
NodeRows = Annotated[list[ThreeNumbers | FourNumbers], Field(min_length=1)]
SixFlags = Annotated[list[bool], Field(min_length=6, max_length=6)]
SixNumbers = Annotated[list[FiniteNumber], Field(min_length=6, max_length=6)]
SpringValues = TwoNumbers | SixNumbers
SupportExtraParameters = Annotated[list[FiniteNumber], Field(min_length=8, max_length=8)]
NonemptyName = Annotated[str, Field(min_length=1)]
TendonNames = NonemptyName | Annotated[list[NonemptyName], Field(min_length=1)]
FunctionReference = tuple[NonemptyName, FiniteNumber]
# 时间-数值曲线（徐变/收缩函数）；qtmodel 2.9 起空表在客户端即被拒绝
CurvePoints = Annotated[list[TwoNumbers], Field(min_length=1)]
ConstraintTerm = tuple[PositiveInteger, Literal[1, 2, 3, 4, 5, 6], FiniteNumber]
# TV 为横向移动荷载工况（qtmodel 2.9 横向分析），直接使用工况名
LoadCaseKind = Literal["ST", "CS", "CB", "MV", "SM", "RS", "TH", "TV"]
LoadCombinationItem = tuple[LoadCaseKind, NonemptyName, FiniteNumber]
SectionLoop = Annotated[list[TwoNumbers], Field(min_length=3)]


def _section_property_layout(values: list[float]) -> list[float]:
    if len(values) not in (26, 29):
        raise ValueError("sec_property must contain 26 (legacy) or 29 (full) values")
    return values


# 截面特性表只有两种布局：26 项旧格式与 29 项完整格式（qtmodel 2.9 客户端校验）
SectionProperties = Annotated[
    list[FiniteNumber],
    Field(min_length=26, max_length=29),
    AfterValidator(_section_property_layout),
]


def _database_name(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


ApiObject = Annotated[Literal["mdb", "odb", "cdb"], BeforeValidator(_database_name)]
ModelDataKind = Literal[
    "nodes", "elements", "materials", "sections", "section_detail", "section_shape",
    "section_property", "thickness", "boundaries", "node_local_axis", "constraint_equations",
    "effective_widths", "reinforcement", "structure_groups", "group_elements", "group_nodes",
    "load_cases", "nodal_force_loads", "nodal_displacement_loads", "beam_element_loads",
    "plate_element_loads", "initial_tension_loads", "cable_length_loads", "pre_stress_loads",
    "node_masses", "tendon_properties", "deviation_parameters", "deviation_loads", "stages",
    "stage_elements", "stage_nodes", "stage_groups", "summary", "analysis_context",
    "project_metadata", "check_context", "structure_group_summaries",
    "material_summaries", "material_detail", "load_case_summaries", "load_case_detail",
    "load_combination_summaries", "load_combination_detail", "construction_stage_summaries",
    "element_section", "spans",
]
EntitySearch = Literal[
    "node_at_point", "elements_at_point", "elements_by_material", "elements_by_section",
    "element_type", "element_weight", "span_supports", "span_elements",
]
SpecialResultKind = Literal[
    "vibration_modal", "buckling_modal", "period_vibration", "buckling_eigenvalue",
    "self_concurrent_reaction", "all_concurrent_reaction", "concurrent_force",
    "elastic_link_force", "constraint_equation_force", "cable_element_length",
]
CheckDataKind = Literal[
    "stress", "solve_status", "case", "basic_info", "materials", "load_table",
    "section_property", "element_table", "reinforcement", "stirrups", "shear_stirrup",
    "torsion_stirrup", "vertical_prestress", "tendon_section", "normal_section_bearing_setting",
    "oblique_shear_bearing_setting", "limit_state_setting", "normal_stress_setting",
    "crack_width_setting", "moment_curvature_setting", "bearing_curve_setting",
]
CheckSettingKind = Literal[
    "normal_section_bearing", "oblique_shear_bearing", "limit_state", "normal_stress",
    "crack_width", "moment_curvature", "bearing_curve",
]
ViewPreset = Literal["iso", "front", "side", "top", "right", "back", "bottom"]
ViewAngle = Literal[ViewPreset, "current"]
ViewSelection = Literal[ViewPreset, "custom"]
BoundaryKind = Literal[
    "support", "elastic_support", "general_elastic_support", "master_slave",
    "elastic_link", "tension_elastic_link", "compression_elastic_link",
    "rigid_elastic_link", "constraint_equation", "beam_constraint",
    "一般支承", "弹性支承", "一般弹性支承", "主从约束", "一般弹性连接",
    "受拉弹性连接", "受压弹性连接", "刚性弹性连接", "约束方程", "梁端约束",
]
PlotResultKind = Literal[
    "displacement", "reaction", "beam_force", "beam_stress", "truss_force", "truss_stress",
    "plate_force", "plate_stress", "modal",
]


QueryId = Annotated[int, Field(strict=True, gt=0)]
QueryIds = QueryId | Annotated[list[QueryId], Field(min_length=1, max_length=500)]
QueryName = Annotated[str, Field(min_length=1, pattern=r"\S")]
QueryNames = Annotated[list[QueryName], Field(min_length=1, max_length=500)]
SelectedIds = QueryId | Annotated[list[QueryId], Field(min_length=1)] | QueryName


class ModelQueryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: Annotated[int, Field(strict=True, ge=0)] = Field(default=0, description="Server-side offset, starting at zero.")
    limit: Annotated[int, Field(strict=True, ge=1, le=500)] = Field(
        default=20, description="Server-side page size; Qiao-MCP caps it at 500 (not a declared server limit).",
    )


class SpatialModelQuery(ModelQueryPage):
    node_ids: QueryIds | None = Field(default=None, description="Positive node ID or a nonempty list, at most 500 IDs.")
    structure_group_names: QueryNames | None = Field(default=None, description="Structure group names, intersected with other filters.")
    near: ThreeNumbers | None = Field(default=None, description="Global point [x,y,z] in model length units; requires tolerance.")
    tolerance: PositiveNumber | None = Field(default=None, description="Positive Euclidean distance from near, in model length units.")
    bbox: SixNumbers | None = Field(default=None, description="Global bounding box [xmin,ymin,zmin,xmax,ymax,zmax].")

    @model_validator(mode="after")
    def validate_spatial_filters(self):
        if (self.near is None) != (self.tolerance is None):
            raise ValueError("near and tolerance must be supplied together (near 与 tolerance 必须配对)")
        if self.bbox is not None and any(self.bbox[i] > self.bbox[i + 3] for i in range(3)):
            raise ValueError("bbox minimum must not exceed maximum (包围框下界不能大于上界)")
        return self


class NodesQuery(SpatialModelQuery):
    kind: Literal["nodes"] = Field(description="Filter node records on the bridge.")

    @model_validator(mode="after")
    def require_filter(self):
        if all(value is None for value in (self.node_ids, self.structure_group_names, self.near, self.bbox)):
            raise ValueError("nodes requires at least one filter (节点查询至少需要一个筛选条件)")
        return self


class NodeLocalAxesQuery(SpatialModelQuery):
    kind: Literal["node_local_axes"] = Field(description="Filter node local coordinate systems; coord_info contains basis vectors, not angles.")


class ElementsQuery(ModelQueryPage):
    kind: Literal["elements"] = Field(description="Filter element records on the bridge.")
    element_ids: QueryIds | None = Field(default=None, description="Element ID or list of IDs.")
    structure_group_names: QueryNames | None = Field(default=None, description="Structure group names.")
    element_type: Literal["", "beam", "link", "cable", "plate"] = Field(default="", description="Element family; empty means no type filter.")
    node_ids: QueryIds | None = Field(default=None, description="Connected node ID or list of IDs.")
    node_match: Literal["any", "all"] = Field(default="any", description="Match any or all of the supplied node IDs.")
    material_ids: QueryIds | None = Field(default=None, description="Material ID or list of IDs.")
    section_ids: QueryIds | None = Field(default=None, description="Beam/link/cable section ID or list of IDs.")
    thickness_ids: QueryIds | None = Field(default=None, description="Plate thickness ID or list of IDs; not a beam section ID.")


class BoundariesQuery(ModelQueryPage):
    kind: Literal["boundaries"] = Field(description="Filter one boundary family on the bridge.")
    boundary_type: Literal[
        "general_support", "elastic_support", "elastic_link", "master_slave_constraint",
        "beam_end_constraint", "constraint_equation",
    ] = Field(description="Native query boundary family (different from the deletion tool's kind names).")
    boundary_ids: QueryIds | None = Field(default=None, description="Boundary ID or list of IDs.")
    group_names: QueryNames | None = Field(default=None, description="Boundary group names.")
    node_ids: QueryIds | None = Field(default=None, description="Target node ID or list of IDs.")
    element_ids: QueryIds | None = Field(default=None, description="Target element ID or list of IDs.")


class LoadsQuery(ModelQueryPage):
    kind: Literal["loads"] = Field(description="Filter one static load family on the bridge.")
    load_family: Literal[
        "nodal_force", "nodal_displacement", "beam_concentrated_load", "beam_distributed_load",
        "plate_concentrated_load", "plate_line_load", "plate_area_load",
    ] = Field(description="Native static load family; this endpoint does not query moving-load definitions.")
    load_ids: QueryIds | None = Field(default=None, description="Load record ID or list of IDs.")
    target_ids: QueryIds | None = Field(default=None, description="Target node/element ID or list, according to load_family.")
    case_names: QueryNames | None = Field(default=None, description="Load case names.")
    group_names: QueryNames | None = Field(default=None, description="Load group names.")


class SectionSummariesQuery(ModelQueryPage):
    kind: Literal["section_summaries"] = Field(description="Filter lightweight section summaries, not full geometry.")
    section_ids: Annotated[list[QueryId], Field(min_length=1, max_length=100)] | None = Field(
        default=None, description="At most 100 explicit section IDs, preserving order; no range strings.",
    )
    query: str = Field(default="", description="Case-insensitive substring of the section name.")
    section_type: str = Field(default="", description="Exact native section type name; empty means no type filter.")
    limit: Annotated[int, Field(strict=True, ge=1, le=100)] = Field(default=50, description="Page size, 1..100 as required by the upstream contract.")


ModelQuery = Annotated[
    NodesQuery | ElementsQuery | BoundariesQuery | LoadsQuery | NodeLocalAxesQuery | SectionSummariesQuery,
    Field(discriminator="kind"),
]


class ObjectResult(BaseModel):
    """The common envelope; backend-owned fields are preserved."""

    model_config = ConfigDict(extra="allow")
    status: str = Field(description="Operation outcome or backend state; execution failures use MCP isError.")


class MessageResult(ObjectResult):
    """Existing text responses also have a machine-readable status and message."""

    status: Literal["success"] = Field(description="The tool completed without an execution error.")
    message: str = Field(description="Operation summary, query results, or instructions for the next step.")


class ConnectionResult(MessageResult):
    connection_status: str = Field(description="Backend connection state, for example connected or software_not_running.")
    connected: bool = Field(description="Whether the bridge endpoint was reached.")
    compatible: bool | None = Field(description="Version compatibility reported by the backend, or null if unknown.")
    client: dict[str, Any] = Field(description="Client package version and endpoint diagnostics.")
    server: dict[str, Any] = Field(description="QiaoTong API version and other server-reported metadata.")
    action: str = Field(description="Recommended recovery action; empty when no action is needed.")


class ModelStateResult(ObjectResult):
    connected: bool | None = Field(default=None, description="Whether QiaoTong is connected, when reported.")
    compatible: bool | None = Field(default=None, description="Backend compatibility, when reported.")
    model_state: dict[str, Any] | None = Field(
        default=None, description="Backend snapshot: lifecycle, capabilities, result availability, and optional model_instance_id, model_revision, history_revision and pending_command_count.",
    )
    message: str | None = Field(default=None, description="State explanation or reason state reporting is unavailable.")


class ModelQueryResult(ObjectResult):
    data: dict[str, Any] = Field(
        description="Bridge-owned query page, including items and any total/has_more/truncated metadata; never paginated again.",
    )


class ModelEditReadinessResult(ObjectResult):
    readiness: dict[str, Any] | None = Field(
        default=None, description="Unmodified bridge readiness response, including any opaque preparation_token; null when unknown.",
    )
    connection: dict[str, Any] | None = Field(
        default=None, description="Connection diagnostic when the readiness query cannot be sent.",
    )
    message: str | None = Field(default=None, description="Diagnostic explanation; success does not itself mean editable.")
    action: str | None = Field(default=None, description="Suggested manual action; no automatic state changes are performed.")


class BridgeWorkflowResult(MessageResult):
    spans: list[PositiveNumber] = Field(description="Span lengths in model coordinate order, in meters.")
    node_ids: list[PositiveInteger] = Field(description="Resolved node IDs in girder coordinate order, including reused nodes.")
    element_ids: list[PositiveInteger] = Field(description="IDs assigned to the newly created beam elements.")
    support_node_ids: list[PositiveInteger] = Field(description="Abutment and pier node IDs in coordinate order.")
    material_id: PositiveInteger = Field(description="ID of the material selected by exact name.")
    section_id: PositiveInteger = Field(description="ID of the section selected by exact name.")
    load_case: str = Field(description="Created or reused load case; self-weight is controlled separately by stage settings.")
