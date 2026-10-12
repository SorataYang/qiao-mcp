"""International live-load definitions, with explicit system selection elsewhere."""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.international_schemas import (
    En1991FactoryRequest,
    InternationalCaseWrite,
    InternationalVehicleWrite,
    ModelCommandResult,
    PlannedLaneWrite,
)
from qiao_mcp.tools.live_load_schemas import ModelDefinitionResult, ModelId, ModelRecordsResult
from qiao_mcp.tools.schemas import PageLimit, PageOffset, QueryName

_VEHICLE_ADAPTER: TypeAdapter[InternationalVehicleWrite] = TypeAdapter(InternationalVehicleWrite)
_FACTORY_ADAPTER: TypeAdapter[En1991FactoryRequest] = TypeAdapter(En1991FactoryRequest)


def register_international_load_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Keep the catalog stable across SDK versions; probe capabilities on use."""

    @mcp.tool()
    def set_international_vehicle(request: InternationalVehicleWrite) -> ModelDefinitionResult:
        """Add or fully replace an AASHTO/BS/EN1991 vehicle (完整定义国际车辆).

        Select the matching system explicitly with configure_live_load_system.
        Vehicle fields are separated by standard. Omitted/null scalar parameters
        use new-definition defaults, including on update; this is not a patch.
        Axles use [N, m] for AASHTO, [kN, m] for EN1991, and unscaled native BS export
        values (the SDK does not specify the BS axle-force unit). r is a percent.
        Query results retain inactive native fields; select this standard's fields
        for this typed tool, or use the gateway for an unchanged full native snapshot.
        Commits once and reads the exact name back to return its actual ID.

        Args:
            request: add/update identity plus standard-specific complete definition;
                parameters and load_items are required, even for {} and [].
        """
        try:
            spec = _VEHICLE_ADAPTER.validate_python(request)
            data = provider.set_international_vehicle(spec.action, spec.model_dump(mode="json", exclude={"action"}, exclude_none=True))
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error defining international vehicle (定义国际车辆失败): {exc}") from exc

    @mcp.tool()
    def get_international_live_load_data(
        kind: Literal["vehicles", "cases"], name: QueryName | None = None,
        index: ModelId | None = None, limit: PageLimit = 50, offset: PageOffset = 0,
    ) -> ModelRecordsResult:
        """Read complete international vehicle/case definitions (回读国际活载定义).

        Native endpoints return the whole list; exact name/ID selection and
        pagination are local. All backend fields and stored units are preserved.
        Case results include only cases whose subcases all use international
        vehicles. There is no planned-lane getter; inspect a model export/UI.

        Args:
            kind: vehicles or cases; both return full native definitions.
            name: Optional exact name; name and index must both match if supplied.
            index: Optional positive ID obtained from a query, not a guessed sequence.
            limit: Maximum selected definitions in this page, 1..500.
            offset: Zero-based offset into the locally selected definitions.
        """
        try:
            records = provider.get_international_live_load_data(kind)
            data = [item for item in records if (name is None or item.get("name") == name)
                    and (index is None or item.get("index") == index)]
            return ModelRecordsResult(status="success", data=data[offset:offset + limit], total=len(data),
                                      limit=limit, offset=offset, has_more=offset + limit < len(data))
        except Exception as exc:
            raise ToolError(f"Error reading international definitions (回读国际活载定义失败): {exc}") from exc

    @mcp.tool()
    def create_en1991_vehicle(request: En1991FactoryRequest) -> ModelDefinitionResult:
        """Create/overwrite a named EN1991 vehicle through its native factory (欧规车辆工厂).

        Select en1991 explicitly first. source=standard uses code-generated uniform
        loads, loaded lengths and spacings; the native compatibility arguments that
        are ignored by that factory are not exposed. source=user retains those
        controls plus p/dis, load_length, num and point_load. Forces use kN, lengths
        m and uniform loads kN/m. An existing name is completely overwritten.
        Commits once and returns the actual definition/ID read back by exact name.

        Args:
            request: source=standard|user, explicit name and the corresponding
                factory controls; user LM71 defaults to four 250 kN axles when
                p/dis are both null. No automatic system change or analysis.
        """
        try:
            spec = _FACTORY_ADAPTER.validate_python(request)
            data = provider.create_en1991_vehicle(spec.source, spec.model_dump(mode="json", exclude={"source"}, exclude_none=True))
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error creating EN1991 vehicle (欧规车辆工厂失败): {exc}") from exc

    @mcp.tool()
    def set_planned_lane(request: PlannedLaneWrite) -> ModelCommandResult:
        """Add or completely replace a planned lane (完整定义规划车道).

        Uses the dedicated planned-lane endpoint, distinct from add_traffic_lane's
        optimize flag. Every physical field is explicit; lengths use model units.
        add can overwrite a same-named planned lane. update can rename while
        preserving references. QiaoTong validates the influence plane and tandem.
        There is no independent planned-lane getter: after the single commit,
        inspect a model export/UI. Deletion through the gateway must explicitly
        pass lane_kind="planned" to remove_lane_line.

        Args:
            request: Complete add/update identity, influence plane, tandem, width,
                vehicle count, signed offset and direction, with optional rename.
        """
        try:
            spec = PlannedLaneWrite.model_validate(request)
            provider.set_planned_lane(spec.action, spec.model_dump(mode="json", exclude={"action"}, exclude_none=True))
            return ModelCommandResult(status="success", committed=True,
                                      message="Planned lane committed; inspect the model export/UI for verification (规划车道已提交；请通过模型导出或界面核对)")
        except Exception as exc:
            raise ToolError(f"Error defining planned lane (定义规划车道失败): {exc}") from exc

    @mcp.tool()
    def set_international_live_load_case(request: InternationalCaseWrite) -> ModelDefinitionResult:
        """Add or fully replace an international live-load case (完整定义国际活载工况).

        Validates referenced vehicle names and standards by query before mutation;
        EN1991 also rejects repeated lane assignments. QiaoTong authoritatively
        validates lane existence/kind and membership in the influence plane, for
        which no independent query endpoint exists. Complete factor objects retain
        native capitalization, units and inactive fields; null uses server defaults.
        Writes commit once and return the exact case's actual ID. Configure the
        operating-stage live_load_cases explicitly, then use run_analysis and
        get_analysis_results(case_name_mode="full") with a verified result name.

        Args:
            request: Full add/update definition, expected vehicle standard,
                influence plane, typed subcases and optional complete factors.
                Update retains references by original name, with optional new_name.
        """
        try:
            spec = InternationalCaseWrite.model_validate(request)
            data = provider.set_international_live_load_case(
                spec.action, spec.standard, spec.model_dump(mode="json", exclude={"action", "standard"}, exclude_none=True),
            )
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error defining international case (定义国际工况失败): {exc}") from exc
