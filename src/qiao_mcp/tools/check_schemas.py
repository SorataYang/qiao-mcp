"""Base-model checking snapshots copied from QiaoTong exports, not CSAN guesses."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool

from qiao_mcp.tools.schemas import ObjectResult, QueryName


def _native_integer(value):
    # QiaoTong stores integer slots of dense numeric rows as JSON numbers (1.0).
    if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError("Expected an integer-valued number, not a boolean/string")
    if value != int(value):
        raise ValueError("Expected an integer-valued number")
    return int(value)


SnapshotInteger = Annotated[int, BeforeValidator(_native_integer), Field(strict=True, ge=0, le=2147483647)]
SnapshotId = Annotated[SnapshotInteger, Field(gt=0)]
SnapshotNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
SnapshotNonnegative = Annotated[SnapshotNumber, Field(ge=0)]
SnapshotPositive = Annotated[SnapshotNumber, Field(gt=0)]
ReinforcementLayer = tuple[SnapshotPositive, SnapshotId, SnapshotNonnegative, SnapshotInteger, SnapshotNonnegative, SnapshotId]
ReinforcementPart = tuple[SnapshotId, SnapshotInteger, SnapshotNumber, SnapshotNumber, SnapshotId, SnapshotPositive, SnapshotInteger, SnapshotNonnegative, SnapshotInteger, SnapshotNonnegative, SnapshotId]
ReinforcementPoint = tuple[SnapshotNumber, SnapshotNumber, SnapshotPositive, SnapshotId]


class SectionReinforcementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id_name: QueryName = Field(description="Complete exported section identifier, e.g. 1, 1-I, 1-J or G7-2; retain it verbatim.")
    section_reference_id: SnapshotId = Field(description="Referenced section/group ID from the same exported snapshot.")
    section_type: QueryName = Field(description="Native exported section type, e.g. Section; do not infer it from a legacy CSAN query.")
    generation_method: SnapshotInteger = Field(description="Native model enum copied from the export; not the legacy reinforcement-tool selector.")
    has_parameters: StrictBool = Field(description="Whether generated parameters are stored; false does not imply deleting the stored rows.")
    has_outer: StrictBool = Field(description="Whether outer reinforcement is active; inactive rows are still preserved.")
    has_inner: StrictBool = Field(description="Whether inner reinforcement is active; inactive rows are still preserved.")
    outer_type: SnapshotInteger = Field(description="Native outer distribution enum from the export, without index conversion.")
    inner_type: SnapshotInteger = Field(description="Native inner distribution enum from the export, without index conversion.")
    outer: list[ReinforcementLayer] = Field(description="Complete outer rows [diameter, material ID, spacing, count, layer edge distance, bars per bundle]; lengths use model units. [] clears rows.")
    inner: list[ReinforcementLayer] = Field(description="Complete inner rows in the same six-field layout; [] clears rows.")
    parts: list[ReinforcementPart] = Field(description="Complete rows [baseline ID, direction enum, first offset, last offset, material ID, diameter, distribution enum, spacing, count, edge distance, bars per bundle]; lengths use model units.")
    points: list[ReinforcementPoint] = Field(description="Complete actual bar points [X, Y, diameter, material ID] in model units; [] clears points.")


class CheckSnapshotResult(ObjectResult):
    committed: Literal[True] = Field(description="The base-model snapshot command and update_model commit completed.")
    message: str = Field(description="What was committed; no lossless CSAN readback or engineering validation is implied.")
