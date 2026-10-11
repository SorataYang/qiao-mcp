"""Explicit live-load definitions; units belong to each native load system."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from qiao_mcp.tools.schemas import ObjectResult, QueryName

LiveLoadSystem = Literal["china_longitudinal", "aashto", "china_transversal", "bs", "en1991"]
LiveLoadCaseNames = Annotated[list[QueryName], Field(max_length=500)]
ModelId = Annotated[int, Field(strict=True, gt=0, le=2147483647)]
LaneCount = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
LoadNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveLoadNumber = Annotated[LoadNumber, Field(gt=0)]
NonnegativeLoadNumber = Annotated[LoadNumber, Field(ge=0)]


class TransversalWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["add", "update"] = Field(description="add can overwrite an existing name/ID; update requires an existing object. Both replace the complete definition.")
    name: QueryName = Field(description="Exact object name; on update this is the original name.")
    index: ModelId | None = Field(default=None, description="Explicit object ID; null uses the name, allocating an ID on add only if it does not exist.")
    new_name: QueryName | None = Field(default=None, description="Optional new name on update; references retain the original ID.")

    @model_validator(mode="after")
    def check_rename(self):
        if self.action == "add" and self.new_name is not None:
            raise ValueError("new_name is only valid for update (仅修改时允许改名)")
        return self


class TransversalVehicleWrite(TransversalWrite):
    wheel_load: PositiveLoadNumber = Field(description="Load of one wheel, fixed kN, independent of display units.")
    wheel_distance: PositiveLoadNumber = Field(description="Left/right wheel spacing Dw, fixed m.")
    min_vehicle_distance: NonnegativeLoadNumber = Field(description="Minimum vehicle separation Dv, m.")
    wheel_margin: NonnegativeLoadNumber = Field(description="Wheel-to-edge clearance De, m.")
    sidewalk_width: NonnegativeLoadNumber = Field(description="Pedestrian/nonmotorized width Dm, m.")
    model_length: PositiveLoadNumber = Field(description="Longitudinal model length, m.")
    left_lane_count: LaneCount = Field(description="Left lane count; total lane count when no central divider is present.")
    right_lane_count: LaneCount = Field(description="Right lane count, counted only when a divider is present.")
    has_medial_divider: StrictBool = Field(description="Whether the model has a central divider.")
    medial_divider_position: NonnegativeLoadNumber = Field(description="Divider center measured horizontally from the lane left end, m.")
    medial_divider_width: NonnegativeLoadNumber = Field(description="Central divider width, m.")

    @model_validator(mode="after")
    def require_active_lane(self):
        if self.left_lane_count + (self.right_lane_count if self.has_medial_divider else 0) < 1:
            raise ValueError("At least one active lane is required (有效车道数至少为 1)")
        return self


class TransversalLaneWrite(TransversalWrite):
    node_ids: Annotated[list[ModelId], Field(min_length=2)] = Field(description="Existing nodes in lane order, without duplicates. Adjacent nodes must be directly joined by beam elements; QiaoTong validates connectivity.")
    distribution_widths: list[NonnegativeLoadNumber] = Field(description="One vehicle-load distribution width per node, fixed m; at least one must be positive. These are widths, not dimensionless factors.")

    @model_validator(mode="after")
    def check_widths_and_order(self):
        if len(set(self.node_ids)) != len(self.node_ids):
            raise ValueError("node_ids must not repeat (节点号不得重复)")
        if len(self.distribution_widths) != len(self.node_ids) or not any(self.distribution_widths):
            raise ValueError("distribution_widths must match nodes and contain a positive width (分布宽度须等长且至少一项为正)")
        return self


class ModelDefinitionResult(ObjectResult):
    committed: Literal[True] = Field(description="The model command and its update_model commit completed.")
    data: dict[str, Any] = Field(description="Definition read back by exact name/ID after commit, including the actual assigned ID and native fields.")


class ModelRecordsResult(ObjectResult):
    data: list[dict[str, Any]] = Field(description="Native model definitions; unknown backend fields are retained.")
    total: int = Field(description="Number of definitions returned by the native query before local pagination.")
    offset: int = Field(description="Zero-based offset into that list.")
    limit: int = Field(description="Requested maximum number of definitions in this response.")
    has_more: bool = Field(description="Whether the native query returned more definitions beyond this page.")
