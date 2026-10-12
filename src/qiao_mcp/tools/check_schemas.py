"""Base-model checking snapshots copied from QiaoTong exports, not CSAN guesses."""

import math
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    model_validator,
)

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


class CheckStirrupDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    StirrupTypeId: SnapshotId = Field(description="Target stirrup ID; pass original_id separately when renumbering.")
    StirrupTypeName: QueryName = Field(description="Complete stirrup name from the UI export.")
    StirrupType: SnapshotInteger = Field(description="Native model enum (exports use 0 for ordinary stirrups); not the legacy tool's one-based selector.")
    ReinforcementTypeId: SnapshotId = Field(description="Referenced reinforcement material ID.")
    LimbsNumber: SnapshotInteger = Field(description="Stored number of ordinary stirrup limbs; retain inactive fields too.")
    LoopsNumber: SnapshotInteger = Field(description="Stored spiral loop count; zero is valid for the inactive ordinary-stirrup field.")
    StirrupDiameter: SnapshotPositive = Field(description="Exported stirrup diameter; preserve storage units (e.g. 12.0), without a global length conversion.")
    StirrupSpacing: SnapshotPositive = Field(description="Exported stirrup spacing; preserve storage units (e.g. 0.1).")
    CoreDiameter: SnapshotNonnegative = Field(description="Exported spiral core diameter; zero is valid when unused.")


ShearStirrupRow = tuple[SnapshotId, SnapshotInteger, SnapshotInteger, SnapshotInteger, SnapshotInteger]
TorsionStirrupRow = tuple[SnapshotId, SnapshotInteger, SnapshotInteger]


class ElementStirrupsDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shear: list[ShearStirrupRow] | None = Field(default=None, description="Complete shear rows [element ID, Iy, Ix, Jy, Jx]. Stirrup ID 0 means unassigned. null/omitted preserves the family; [] clears it.")
    torsion: list[TorsionStirrupRow] | None = Field(default=None, description="Complete torsion rows [element ID, I, J]. Stirrup ID 0 means unassigned. null/omitted preserves the family; [] clears it.")

    @model_validator(mode="after")
    def unique_elements_per_family(self):
        for rows in (self.shear, self.torsion):
            if rows is not None and len({row[0] for row in rows}) != len(rows):
                raise ValueError("Each family must contain unique element IDs (每类配箍不得重复单元号)")
        return self


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Snapshot values must be finite")
    if isinstance(value, dict):
        for item in value.values():
            _finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _finite_json(item)
    return value


SnapshotProperties = Annotated[dict[str, JsonValue], AfterValidator(_finite_json)]
CheckFamily = Literal["concrete", "seismic", "strengthening"]


class CheckMaterialDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: SnapshotId = Field(description="Existing base-model material ID whose check override is being replaced.")
    name: QueryName = Field(description="Material name from the complete exported definition.")
    kind: SnapshotInteger = Field(description="Native model material-kind enum from the export; no legacy-index conversion.")
    standard: SnapshotInteger = Field(description="Native material standard enum from the export.")
    model: SnapshotInteger = Field(description="Native material curve/model enum from the export.")
    elastic_modulus: SnapshotNonnegative = Field(description="Stored elastic modulus from the export, e.g. 30000000000; passed without unit scaling.")
    properties: SnapshotProperties = Field(description="Complete backend-owned properties, preserving all legal keys and stored units, including inactive/zero-valued properties.")
    parameters: SnapshotProperties = Field(description="Complete backend-owned curve parameters from the same export; not inferred from a partial material query.")


class SetCheckMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["set"] = Field(description="Replace the full check-material override.")
    definition: CheckMaterialDefinition = Field(description="Complete UI-exported material snapshot.")


class ResetCheckMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["reset"] = Field(description="Remove the override and restore use of the base material; does not delete the material.")
    index: SnapshotId = Field(description="Explicit base-material ID whose override is reset.")


CheckMaterialRequest = Annotated[SetCheckMaterial | ResetCheckMaterial, Field(discriminator="action")]


class CheckCaseDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: CheckFamily = Field(description="Base-model check-case family; only concrete is run by the existing run_concrete_check tool.")
    index: SnapshotId = Field(description="Explicit case ID within this family; set can add or replace that ID.")
    name: QueryName = Field(description="Complete case name from the exported definition.")
    standard: SnapshotInteger = Field(description="Native zero-based model standard enum; not the legacy setup tool's selector.")
    structure_type: SnapshotInteger = Field(description="Native zero-based structure-type enum from the export.")
    group_names: list[QueryName] = Field(description="Complete referenced structure-group names; no implicit selection of all groups.")
    component_force_type: SnapshotInteger = Field(description="Native concrete force-component selection enum; retain its stored value for other families too.")
    force_components: tuple[StrictBool, StrictBool, StrictBool, StrictBool, StrictBool, StrictBool] = Field(description="Six force-component flags in the exported native order; do not reorder or infer them.")
    calculation_setting: SnapshotInteger = Field(description="Stored concrete calculation-setting enum/flags; retained in the full snapshot for every family.")
    seismic_import_type: SnapshotInteger = Field(description="Stored seismic import mode; retain its exported value even for other families.")
    strengthening_method: SnapshotInteger = Field(description="Stored strengthening method; retain its exported value even for other families.")


class SetCheckCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["set"] = Field(description="Add or completely replace a base-model check case by family/ID.")
    definition: CheckCaseDefinition = Field(description="Full exported definition including the inactive fields emitted for this family.")


class RemoveCheckCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["remove"] = Field(description="Delete the explicit case and invalidate its corresponding check file; this is a model command.")
    family: CheckFamily = Field(description="Case family to remove.")
    index: SnapshotId = Field(description="Explicit positive case ID within that family; no default delete-all.")


CheckCaseRequest = Annotated[SetCheckCase | RemoveCheckCase, Field(discriminator="action")]
