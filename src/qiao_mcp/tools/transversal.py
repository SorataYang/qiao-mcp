"""Transversal model definitions with explicit configuration and readback."""

from typing import Literal

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.live_load_schemas import (
    ModelDefinitionResult,
    ModelId,
    ModelRecordsResult,
    TransversalLaneWrite,
    TransversalVehicleWrite,
)
from qiao_mcp.tools.schemas import PageLimit, PageOffset, QueryName


def register_transversal_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register transversal definition tools independently of installed capabilities."""

    @mcp.tool()
    def set_transversal_vehicle(request: TransversalVehicleWrite) -> ModelDefinitionResult:
        """Add or completely replace a transversal vehicle (完整定义横向车辆).

        Requires the China transversal system to be selected explicitly first.
        add overwrites the same name/ID; update requires an existing vehicle and
        can rename it while retaining references. Every physical field is required.
        Fixed kN/m units do not follow display units. Commits once and reads back
        the actual ID. Never switches systems, clears results or runs analysis.

        Args:
            request: Complete vehicle definition, action and optional identity/rename;
                use get_transversal_data(kind="vehicles") to inspect existing definitions.
        """
        try:
            spec = TransversalVehicleWrite.model_validate(request)
            data = provider.set_transversal_data("vehicle", spec.action, spec.model_dump(exclude={"action"}, exclude_none=True))
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error defining transversal vehicle (定义横向车辆失败): {exc}") from exc

    @mcp.tool()
    def set_transversal_lane(request: TransversalLaneWrite) -> ModelDefinitionResult:
        """Add or completely replace a transversal lane (完整定义横向车道).

        Node order is retained. Each adjacent pair must already have a direct
        beam connection; QiaoTong rejects invalid connectivity. No node sorting
        or beam creation occurs. distribution_widths are fixed meters, mapped
        to native load_factors. add may overwrite, update may rename; both commit
        once and return the actual ID after an exact readback.

        Args:
            request: Full lane definition with ordered nodes and corresponding
                distribution widths, plus action and optional identity/rename.
        """
        try:
            spec = TransversalLaneWrite.model_validate(request)
            data = provider.set_transversal_data("lane", spec.action, spec.model_dump(exclude={"action"}, exclude_none=True))
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error defining transversal lane (定义横向车道失败): {exc}") from exc

    @mcp.tool()
    def get_transversal_data(
        kind: Literal["vehicles", "lanes"], name: QueryName | None = None,
        index: ModelId | None = None, limit: PageLimit = 50, offset: PageOffset = 0,
    ) -> ModelRecordsResult:
        """Read complete native transversal definitions (回读横向定义).

        Exact name/ID filters are applied by QiaoTong; pagination is local to its
        returned list. Native fields and node order are retained, including
        load_factors in meters. Use the returned index for case references.

        Args:
            kind: Definition family: vehicles (车辆) or lanes (车道).
            name: Optional exact name; when an ID is also supplied both must match.
            index: Optional positive object ID; omitted means no ID filter.
            limit: Maximum definitions to return, 1..500 (每页上限).
            offset: Zero-based offset into the selected definitions (偏移量).
        """
        try:
            data = provider.get_transversal_data(kind, name=name or "", index=index if index is not None else -1)
            return ModelRecordsResult(status="success", data=data[offset:offset + limit], total=len(data),
                                      limit=limit, offset=offset, has_more=offset + limit < len(data))
        except Exception as exc:
            raise ToolError(f"Error reading transversal definitions (回读横向定义失败): {exc}") from exc
