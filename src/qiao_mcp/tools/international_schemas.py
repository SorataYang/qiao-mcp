"""International definitions with each standard's native fields and units."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, model_validator

from qiao_mcp.tools.live_load_schemas import LoadNumber, ModelId, NonnegativeLoadNumber
from qiao_mcp.tools.schemas import QueryName


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
