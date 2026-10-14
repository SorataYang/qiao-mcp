"""Transversal model definitions with explicit configuration and readback."""

from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.live_load_schemas import (
    ModelDefinitionResult,
    ModelId,
    ModelRecordsResult,
    TransversalCaseWrite,
    TransversalLaneWrite,
    TransversalRemoval,
    TransversalVehicleWrite,
)
from qiao_mcp.tools.schemas import MessageResult, PageLimit, PageOffset, QueryName

_REMOVAL_ADAPTER: TypeAdapter[TransversalRemoval] = TypeAdapter(TransversalRemoval)


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
    def set_transversal_case(request: TransversalCaseWrite) -> ModelDefinitionResult:
        """Add or completely replace a transversal case (完整定义横向工况).

        Reference existing vehicle/lane IDs obtained from readback. Both are
        checked before mutation. Factors are dimensionless multipliers; the
        provider builds the native reduction string. add may overwrite an
        existing name/ID; update can rename while retaining combination references.
        This commits a definition without changing operation selections or solving.

        Args:
            request: Complete case, IDs, impact multiplier, factors for 1..N lanes,
                factor for more than N lanes, description, and add/update identity.
        """
        try:
            spec = TransversalCaseWrite.model_validate(request)
            data = provider.set_transversal_data("case", spec.action, spec.model_dump(exclude={"action"}, exclude_none=True))
            return ModelDefinitionResult(status="success", committed=True, data=data)
        except Exception as exc:
            raise ToolError(f"Error defining transversal case (定义横向工况失败): {exc}") from exc

    @mcp.tool()
    def remove_transversal_data(request: TransversalRemoval) -> MessageResult:
        """Delete one explicit transversal object (删除明确指定的横向对象).

        Vehicles/lanes default to cascade=False. Opting into cascade can delete
        dependent cases, but references from model/check combinations or operation
        settings still block deletion. Case deletion has no cascade option. Never
        removes external references or retries with more destructive options.

        Args:
            request: kind=vehicle|lane|case and explicit name/index. Only vehicle
                and lane selectors support the optional cascade boolean.
        """
        try:
            spec = _REMOVAL_ADAPTER.validate_python(request)
            provider.remove_transversal_data(spec.kind, **spec.model_dump(exclude={"kind"}, exclude_none=True))
            return MessageResult(status="success", message=f"Transversal {spec.kind} deletion committed (横向对象删除已提交)")
        except Exception as exc:
            raise ToolError(f"Error deleting transversal object (删除横向对象失败): {exc}") from exc

    @mcp.tool()
    def get_transversal_data(
        kind: Literal["vehicles", "lanes", "cases"], name: QueryName | None = None,
        index: ModelId | None = None, limit: PageLimit = 50, offset: PageOffset = 0,
    ) -> ModelRecordsResult:
        """Read complete native transversal definitions (回读横向定义).

        Exact name/ID filters are applied by QiaoTong; pagination is local to its
        returned list. Native fields and node order are retained, including
        load_factors in meters. Use the returned index for case references.

        Use before editing with set_transversal_vehicle/lane/case and after a
        write to verify actual IDs and stored fields. For international definitions
        use get_international_live_load_data; get_analysis_results reads solved
        responses. This query requires no new solve and does not mutate the model.

        When both name and index are provided they identify the same object, not
        an either/or search. With neither, all available definitions in kind are
        selected before local pagination. Returns data, total, limit, offset and
        has_more; use these fields to request the next page. Empty data can mean
        no exact match or an offset beyond the selected list.
        (同时给名称与编号时必须同时匹配；省略两者查询该类全部定义，按返回的分页字段续查。)

        Args:
            kind: Definition family: vehicles (车辆), lanes (车道) or cases (工况).
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
