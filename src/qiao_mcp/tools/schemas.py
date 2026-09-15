"""Shared, executable input constraints and stable MCP response schemas."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

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
NonemptyName = Annotated[str, Field(min_length=1)]
TendonNames = NonemptyName | Annotated[list[NonemptyName], Field(min_length=1)]
FunctionReference = tuple[NonemptyName, FiniteNumber]
ConstraintTerm = tuple[PositiveInteger, Literal[1, 2, 3, 4, 5, 6], FiniteNumber]
LoadCaseKind = Literal["ST", "CS", "CB", "MV", "SM", "RS", "TH"]
LoadCombinationItem = tuple[LoadCaseKind, NonemptyName, FiniteNumber]
SectionLoop = Annotated[list[TwoNumbers], Field(min_length=3)]


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
        default=None, description="Backend snapshot: model_opened, phase, stage_name, capabilities and result availability.",
    )
    message: str | None = Field(default=None, description="State explanation or reason state reporting is unavailable.")


class BridgeWorkflowResult(MessageResult):
    spans: list[PositiveNumber] = Field(description="Span lengths in model coordinate order, in meters.")
    node_ids: list[PositiveInteger] = Field(description="Resolved node IDs in girder coordinate order, including reused nodes.")
    element_ids: list[PositiveInteger] = Field(description="IDs assigned to the newly created beam elements.")
    support_node_ids: list[PositiveInteger] = Field(description="Abutment and pier node IDs in coordinate order.")
    material_id: PositiveInteger = Field(description="ID of the material selected by exact name.")
    section_id: PositiveInteger = Field(description="ID of the section selected by exact name.")
    load_case: str = Field(description="Created or reused load case; self-weight is controlled separately by stage settings.")
