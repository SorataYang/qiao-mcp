"""International definitions with each standard's native fields and units."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, model_validator

from qiao_mcp.tools.live_load_schemas import (
    LaneCount,
    LoadNumber,
    ModelId,
    NonnegativeLoadNumber,
    PositiveLoadNumber,
)
from qiao_mcp.tools.schemas import ObjectResult, QueryName


def _integer_number(value):
    # Native parameter dictionaries can encode integer enums/counts as 1.0.
    if type(value) is int:
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError("Expected an integer number, not a boolean/string/fraction")


NativeInteger = Annotated[int, BeforeValidator(_integer_number), Field(ge=-2147483648, le=2147483647)]
DefinitionMode = Annotated[Literal[1, 2], BeforeValidator(_integer_number)]
InternationalStandard = Literal["AASHTO", "BS", "EN1991"]
NativeAxles = list[tuple[LoadNumber, NonnegativeLoadNumber]]


class InternationalNamedWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["add", "update"] = Field(description="add can overwrite the same name; update requires an existing object. Both replace the definition, not selected fields.")
    name: QueryName = Field(description="Exact object name; update locates the original object by this name.")
    new_name: QueryName | None = Field(default=None, description="Optional rename on update, retaining the object's ID and references; not accepted on add.")

    @model_validator(mode="after")
    def check_rename(self):
        if self.action == "add" and self.new_name is not None:
            raise ValueError("new_name is only valid for update (仅修改时允许改名)")
        return self


class InternationalIndexedWrite(InternationalNamedWrite):
    index: ModelId | None = Field(default=None, description="On add, an explicit positive ID can be overwritten; null uses name matching/automatic allocation. On update, this only carries a queried ID: QiaoTong still locates by original name and retains its actual ID.")


class AashtoParameters(BaseModel):
    """Omitted/null scalars use new-definition defaults, including on update."""

    model_config = ConfigDict(extra="forbid")
    dynamic_coefficient: LoadNumber | None = Field(default=None, description="AASHTO dimensionless dynamic multiplier, e.g. 1.33; omitted/null uses the server's new-definition default.")
    r: LoadNumber | None = Field(default=None, description="AASHTO r in percent: 90 means 90%, not 0.90; omitted/null uses the new-definition default.")
    dist: LoadNumber | None = Field(default=None, description="AASHTO Dist, fixed m; omitted/null uses the new-definition default.")
    d2: LoadNumber | None = Field(default=None, description="AASHTO D2 axle distance, fixed m; omitted/null uses the new-definition default.")
    d3: LoadNumber | None = Field(default=None, description="AASHTO D3 axle distance, fixed m; omitted/null uses the new-definition default.")
    w: LoadNumber | None = Field(default=None, description="AASHTO uniform load W, fixed N/m; omitted/null uses the new-definition default.")


class BsParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    w1: LoadNumber | None = Field(default=None, description="BS HA first uniform-load formula coefficient W1; retain the native formula convention.")
    w2: LoadNumber | None = Field(default=None, description="BS HA second uniform-load formula coefficient W2; retain the native formula convention.")
    w3: LoadNumber | None = Field(default=None, description="BS HA third uniform load W3, kN/m.")
    l_invert1: LoadNumber | None = Field(default=None, description="Dimensionless exponent of (1/L) in the first BS HA formula.")
    l_invert2: LoadNumber | None = Field(default=None, description="Dimensionless exponent of (1/L) in the second BS HA formula.")
    l1: LoadNumber | None = Field(default=None, description="BS HA first transition length L1, m.")
    l2: LoadNumber | None = Field(default=None, description="BS HA second transition length L2, m.")
    pa: LoadNumber | None = Field(default=None, description="BS HA concentrated load Pa, kN.")
    d1: LoadNumber | None = Field(default=None, description="BS HB distance D1, m.")
    pb: LoadNumber | None = Field(default=None, description="BS HB load parameter Pb, kN.")
    d: LoadNumber | None = Field(default=None, description="BS HB distance increment d, m.")
    d2: LoadNumber | None = Field(default=None, description="BS HB distance D2, m.")
    d3: LoadNumber | None = Field(default=None, description="BS HB distance D3, m.")
    d4: LoadNumber | None = Field(default=None, description="BS HB distance D4, m.")
    d5: LoadNumber | None = Field(default=None, description="BS HB distance D5, m.")
    d6: LoadNumber | None = Field(default=None, description="BS HB distance D6, m.")
    number_of_units: LoadNumber | None = Field(default=None, description="BS HB Number of Units; a load-unit count in the native definition, not a force conversion.")


class En1991Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    uniform_load1: LoadNumber | None = Field(default=None, description="EN1991 first uniform load, kN/m.")
    uniform_load2: LoadNumber | None = Field(default=None, description="EN1991 second uniform load, kN/m.")
    loaded_length1: LoadNumber | None = Field(default=None, description="EN1991 first loaded length, m; distinct from spacing1.")
    loaded_length2: LoadNumber | None = Field(default=None, description="EN1991 second loaded length, m; distinct from spacing2.")
    spacing1: LoadNumber | None = Field(default=None, description="EN1991 first uniform-load spacing, m.")
    spacing2: LoadNumber | None = Field(default=None, description="EN1991 second uniform-load spacing, m.")
    load_number: NativeInteger | None = Field(default=None, description="EN1991 native 32-bit integer load count; retain the exported value.")
    train_length: LoadNumber | None = Field(default=None, description="EN1991 train length, m.")
    load_gap: LoadNumber | None = Field(default=None, description="EN1991 load gap, m.")
    point_load: LoadNumber | None = Field(default=None, description="EN1991 point load, kN.")
    fai1: LoadNumber | None = Field(default=None, description="EN1991 dimensionless dynamic-effect coefficient phi1.")
    fai2: LoadNumber | None = Field(default=None, description="EN1991 dimensionless dynamic-effect coefficient phi2.")
    alpha: LoadNumber | None = Field(default=None, description="EN1991 dimensionless adjustment factor alpha.")
    support_gap: LoadNumber | None = Field(default=None, description="EN1991 support gap for point loads, m.")
    displacement_bias: LoadNumber | None = Field(default=None, description="EN1991 displacement bias, m.")
    hslm_a_kind: Annotated[NativeInteger, Field(ge=1, le=10)] | None = Field(default=None, description="EN1991 HSLM A model, 1..10 for A1..A10.")


class AashtoVehicleWrite(InternationalIndexedWrite):
    standard: Literal["AASHTO"] = Field(description="AASHTO; the model must already use this live-load system.")
    vehicle_type: Annotated[Literal[0, 1, 2], BeforeValidator(_integer_number)] = Field(description="0 HL93TRK, 1 HL93TDM, 2 HS20FTG.")
    definition_mode: DefinitionMode = Field(description="1 standard definition, 2 user definition. This is a complete replacement in either mode.")
    parameters: AashtoParameters = Field(description="AASHTO scalars only; omitted/null fields use new-definition defaults, not existing values. An explicit {} selects all defaults.")
    load_items: NativeAxles = Field(description="Complete AASHTO axle rows [force in N, spacing in m]; [] supplies an empty axle list. No conversion follows display units.")


class BsVehicleWrite(InternationalIndexedWrite):
    standard: Literal["BS"] = Field(description="BS; the model must already use this live-load system.")
    vehicle_type: Annotated[Literal[0, 1, 2, 3], BeforeValidator(_integer_number)] = Field(description="0 HA, 1 HB, 2 HAHB, 3 pedestrian loading.")
    definition_mode: DefinitionMode = Field(description="1 standard definition, 2 user definition; complete replacement in either mode.")
    parameters: BsParameters = Field(description="BS scalars only; omitted/null fields use new-definition defaults, not existing values. An explicit {} selects all defaults.")
    load_items: NativeAxles = Field(description="Complete BS native axle rows [exported force, spacing in m]. The upstream SDK does not document the BS axle-force unit: copy verified BS export/query values unchanged, do not assume the AASHTO N or EN1991 kN convention. [] supplies no axles.")


class En1991VehicleWrite(InternationalIndexedWrite):
    standard: Literal["EN1991"] = Field(description="EN1991; the model must already use this live-load system.")
    vehicle_type: Annotated[Literal[1, 2, 3, 4, 5, 6], BeforeValidator(_integer_number)] = Field(description="1 LM71, 2 SW0, 3 SW2, 4 UnloadedTrain, 5 HSLM A, 6 HSLM B.")
    definition_mode: DefinitionMode = Field(description="1 standard definition, 2 user definition; complete replacement in either mode.")
    parameters: En1991Parameters = Field(description="EN1991 scalars only; omitted/null fields use new-definition defaults, not existing values. An explicit {} selects all defaults.")
    load_items: NativeAxles = Field(description="Complete EN1991 axle rows [force in kN, spacing in m]; [] supplies an empty axle list. No conversion follows display units.")
    consider_point_load: StrictBool = Field(description="Whether to include the EN1991 point load; retained explicitly even when false.")
    consider_displacement_bias: StrictBool = Field(description="Whether to include EN1991 displacement bias; retained explicitly even when false.")


InternationalVehicleWrite = Annotated[AashtoVehicleWrite | BsVehicleWrite | En1991VehicleWrite, Field(discriminator="standard")]


En1991LoadType = Literal["LoadModel71", "LM71", "SW0", "SW2", "UnloadedTrain", "HSLMA", "HSLMB"]


class En1991FactoryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: QueryName = Field(description="Explicit target vehicle name; an existing name is completely overwritten. Required so the created definition can be read back without guessing its name.")
    load_type: En1991LoadType = Field(default="LoadModel71", description="EN1991 load model; LM71 is an alias for LoadModel71.")
    load_gap: NonnegativeLoadNumber = Field(default=3.5, description="Load gap, m; must be positive for HSLMA/HSLMB.")
    fai1: NonnegativeLoadNumber = Field(default=0, description="Dimensionless dynamic-effect coefficient phi1, nonnegative.")
    fai2: NonnegativeLoadNumber = Field(default=0, description="Dimensionless dynamic-effect coefficient phi2, nonnegative.")
    alpha: PositiveLoadNumber = Field(default=1, description="Dimensionless adjustment factor alpha, strictly positive.")
    consider_point_load: StrictBool = Field(default=False, description="Whether to consider a point load.")
    support_gap: NonnegativeLoadNumber = Field(default=.75, description="Support gap for point loading, m; must be positive when consider_point_load is true.")
    consider_displacement_bias: StrictBool = Field(default=False, description="Whether to consider load displacement bias.")
    displacement_bias: LoadNumber = Field(default=0, description="Load displacement bias, m; signed values are retained.")

    @model_validator(mode="after")
    def check_active_gaps(self):
        if self.load_type in {"HSLMA", "HSLMB"} and self.load_gap <= 0:
            raise ValueError("HSLM load_gap must be positive (HSLM 荷载间距必须为正)")
        if self.consider_point_load and self.support_gap <= 0:
            raise ValueError("Point loading requires a positive support_gap (考虑点荷载时支点间距必须为正)")
        return self


class En1991StandardFactory(En1991FactoryOptions):
    source: Literal["standard"] = Field(description="Use the native standard factory; standard uniform loads/lengths/spacings are generated by QiaoTong and cannot be overridden here.")
    load_number: ModelId = Field(default=10, description="Positive HSLM B load count; other load models do not use this control.")
    hslm_a_kind: Annotated[NativeInteger, Field(ge=1, le=10)] = Field(default=1, description="HSLM A model 1..10 (A1..A10); other load models do not use this control.")


class En1991UserFactory(En1991FactoryOptions):
    source: Literal["user"] = Field(description="Use the native user factory, retaining its uniform-load and axle controls.")
    uniform_load1: NonnegativeLoadNumber = Field(default=80, description="First uniform load, kN/m.")
    uniform_load2: NonnegativeLoadNumber = Field(default=80, description="Second uniform load, kN/m.")
    loaded_length1: NonnegativeLoadNumber = Field(default=1.7976931348623157e308, description="First loaded length, m; the maximum finite float means unlimited length, matching the factory.")
    loaded_length2: NonnegativeLoadNumber = Field(default=1.7976931348623157e308, description="Second loaded length, m; the maximum finite float means unlimited length.")
    spacing1: NonnegativeLoadNumber = Field(default=.8, description="First uniform-load spacing, m; distinct from loaded_length1.")
    spacing2: NonnegativeLoadNumber = Field(default=.8, description="Second uniform-load spacing, m; distinct from loaded_length2.")
    p: Annotated[list[PositiveLoadNumber], Field(min_length=1)] | None = Field(default=None, description="Axle loads, kN, paired with an equal-length dis list. For LM71, both null use four 250 kN axles; other models use their native factory rules.")
    dis: Annotated[list[NonnegativeLoadNumber], Field(min_length=1)] | None = Field(default=None, description="Axle spacings, m, paired with p. For LM71, both null use [1.6, 1.6, 1.6, 0].")
    load_length: PositiveLoadNumber = Field(default=18, description="HSLM A vehicle length, m, strictly positive.")
    num: ModelId = Field(default=18, description="Positive user-factory load count.")
    point_load: NonnegativeLoadNumber = Field(default=170, description="Point load, kN; must be positive for HSLMA/HSLMB.")

    @model_validator(mode="after")
    def check_axles_and_hslm(self):
        if (self.p is None) != (self.dis is None) or self.p is not None and len(self.p) != len(self.dis or []):
            raise ValueError("p and dis must both be null or equal-length lists (轴载与间距须同时为空或等长)")
        if self.load_type in {"HSLMA", "HSLMB"} and self.point_load <= 0:
            raise ValueError("HSLM point_load must be positive (HSLM 点荷载必须为正)")
        return self


En1991FactoryRequest = Annotated[En1991StandardFactory | En1991UserFactory, Field(discriminator="source")]


class PlannedLaneWrite(InternationalNamedWrite):
    influence_name: QueryName = Field(description="Existing influence-plane name; QiaoTong validates the reference before applying the command.")
    tandem_name: QueryName = Field(description="Existing reference node-tandem name, validated by QiaoTong.")
    lane_width: PositiveLoadNumber = Field(description="Positive planned-lane width in model length units.")
    vehicle_number: LaneCount = Field(description="Nonnegative vehicle count; zero delegates loading behavior to QiaoTong.")
    offset: LoadNumber = Field(description="Signed offset from the reference tandem in model length units.")
    direction: Annotated[Literal[0, 1], BeforeValidator(_integer_number)] = Field(description="0 forward, 1 reverse.")


class ModelCommandResult(ObjectResult):
    committed: Literal[True] = Field(description="The command and its model commit completed; this is not an independent definition readback.")
    message: str = Field(description="Commit outcome and the available way to inspect the definition.")


class InternationalSubCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vehicle_name: QueryName = Field(description="Existing international vehicle; its exact name and standard are checked by query before writing.")
    lane_names: Annotated[list[QueryName], Field(min_length=1)] = Field(description="Existing lanes belonging to the case's influence plane; QiaoTong validates names, plane membership and lane kind.")
    factor: PositiveLoadNumber = Field(default=1, description="Positive dimensionless subcase factor.")
    optimized: StrictBool = Field(default=False, description="False selects ordinary lanes; true selects planned lanes, not an ordinary lane's optimize flag.")
    lane_count: LaneCount = Field(default=0, description="Nonnegative native loaded-lane count; zero retains the server's loading behavior.")
    hb_lane_names: list[QueryName] = Field(default_factory=list, description="Complete native HB lane-name selection; [] selects none. QiaoTong validates these lane references too.")


class InternationalCrossReduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    CrossReduceSet: dict[Annotated[str, Field(pattern=r"^(0|[1-9][0-9]*)$")], LoadNumber] = Field(description="Native map from decimal lane-count strings to finite dimensionless factors; retain the queried map, including an empty map.")
    Code: NativeInteger = Field(description="Native reduction-code enum from the complete query; no display-index conversion.")


class InternationalImpactFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    IsDefinedByUser: StrictBool = Field(description="Native flag selecting the supplied impact value instead of code calculation.")
    ImpactValue: LoadNumber = Field(description="Stored dimensionless impact multiplier; retain the native value.")
    Span: LoadNumber = Field(description="Stored impact-calculation span in native model units.")
    FillThick: LoadNumber = Field(description="Stored fill thickness in native model units.")
    Rise: LoadNumber = Field(description="Stored bridge rise in native model units.")
    LambDa: LoadNumber = Field(description="Stored dimensionless lambda; retain this exact field capitalization.")
    BaseFrequency: LoadNumber = Field(description="Stored base frequency in Hz.")
    Code: NativeInteger = Field(description="Native impact-code enum; retain the query value.")
    BridgeKind: NativeInteger = Field(description="Native bridge-kind enum; retain the query value.")


class InternationalLongitudeReduction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    IsDefinedByUser: StrictBool = Field(description="Whether the stored longitudinal factor is user-defined.")
    Value: LoadNumber = Field(description="Stored dimensionless longitudinal reduction factor.")
    Code: NativeInteger = Field(description="Native longitudinal reduction-code enum.")
    Span: LoadNumber = Field(description="Stored longitudinal reduction span in native model units.")


class InternationalRelativeFactors(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ReduceCode: NativeInteger = Field(description="Native reduction-code enum from the complete factor query.")
    CrossReduceCoefficient: InternationalCrossReduction = Field(description="Full native transverse reduction object, preserving its map and code.")
    ImpactCoefficient: InternationalImpactFactor = Field(description="Full native strength-impact object, including inactive values.")
    LongitudeReduceCoefficient: InternationalLongitudeReduction = Field(description="Full native longitudinal reduction object.")
    FatigueImpactCoefficient: InternationalImpactFactor = Field(description="Full native fatigue-impact object, including inactive values.")
    IsCalculatedFatigue: StrictBool = Field(description="Whether fatigue is calculated; false does not discard the other stored fields.")
    FatigueLaneLineCount: LaneCount = Field(description="Stored nonnegative number of fatigue lane lines.")


class InternationalCaseWrite(InternationalIndexedWrite):
    standard: InternationalStandard = Field(description="Expected standard of all referenced vehicles; must also match the model's explicitly selected live-load system.")
    influence_plane: QueryName = Field(description="Existing influence plane; QiaoTong checks all lane memberships before applying the command.")
    sub_cases: Annotated[list[InternationalSubCase], Field(min_length=1)] = Field(description="Complete replacement subcase list; EN1991 cannot assign the same lane twice within a case.")
    span: NonnegativeLoadNumber = Field(default=1, description="Case span in model length units; zero means unspecified.")
    save_sub_case_result: StrictBool = Field(default=False, description="Whether to save subcase results; this does not run analysis.")
    highway_factor: InternationalRelativeFactors | None = Field(default=None, description="Full queried highway factor object; null/omitted uses server defaults, including on update. Nested fields cannot be null.")
    railway_factor: InternationalRelativeFactors | None = Field(default=None, description="Full queried railway factor object; null/omitted uses server defaults, including on update.")
    light_rail_factor: InternationalRelativeFactors | None = Field(default=None, description="Full queried light-rail factor object; null/omitted uses server defaults, including on update.")

    @model_validator(mode="after")
    def check_en1991_lane_assignments(self):
        if self.standard == "EN1991":
            names = [name for case in self.sub_cases for name in [*case.lane_names, *case.hb_lane_names]]
            if len(names) != len(set(names)):
                raise ValueError("EN1991 lanes cannot be assigned twice in one case (欧规工况内车道不得重复分配)")
        return self
