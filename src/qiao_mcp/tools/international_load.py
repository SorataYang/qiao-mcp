"""International live-load definitions, with explicit system selection elsewhere."""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.international_schemas import InternationalVehicleWrite
from qiao_mcp.tools.live_load_schemas import ModelDefinitionResult, ModelId, ModelRecordsResult
from qiao_mcp.tools.schemas import PageLimit, PageOffset, QueryName

_VEHICLE_ADAPTER: TypeAdapter[InternationalVehicleWrite] = TypeAdapter(InternationalVehicleWrite)


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
