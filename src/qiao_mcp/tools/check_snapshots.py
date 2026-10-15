"""Complete base-model definitions, separate from legacy CSAN editing tools."""

from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.check_schemas import (
    CheckCaseRequest,
    CheckMaterialRequest,
    CheckSnapshotResult,
    CheckStirrupDefinition,
    ElementStirrupsDefinition,
    SectionReinforcementDefinition,
    SnapshotId,
)
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import QueryName

_MATERIAL_ADAPTER: TypeAdapter[CheckMaterialRequest] = TypeAdapter(CheckMaterialRequest)
_CASE_ADAPTER: TypeAdapter[CheckCaseRequest] = TypeAdapter(CheckCaseRequest)


def _commit_snapshot(provider: BridgeProvider, method: str, message: str, **kwargs) -> CheckSnapshotResult:
    try:
        provider.write_check_snapshot(method, **kwargs)
        return CheckSnapshotResult(status="success", committed=True, message=message)
    except Exception as exc:
        raise ToolError(f"Error writing model check snapshot (写入基础模型检算快照失败): {exc}") from exc


def register_check_snapshot_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register fixed snapshot operations without changing legacy check contracts."""

    @mcp.tool()
    def manage_check_material(request: CheckMaterialRequest) -> CheckSnapshotResult:
        """Set a full check-material override or restore the base material (设置/恢复检算材料).

        set requires the complete UI-exported definition, including native model
        enums, stored modulus, properties and parameters. Keep all legal keys and
        units; do not build a replacement from an incomplete CSAN/material query.
        reset removes only the override for an explicit material ID. This is a
        base-model write with one commit, not a current-CSAN partial update.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            request: action=set with full definition, or action=reset with index.
        """
        try:
            spec = _MATERIAL_ADAPTER.validate_python(request)
        except ValueError as exc:
            raise ToolInputError(f"Invalid material snapshot request (检算材料请求无效): {exc}") from exc
        if spec.action == "set":
            return _commit_snapshot(provider, "set_check_material", "Check material snapshot committed (检算材料快照已提交)",
                                    definition=spec.definition.model_dump(mode="json"))
        return _commit_snapshot(provider, "remove_check_material", "Base material restored (已恢复使用基础材料)", index=spec.index)

    @mcp.tool()
    def manage_check_case_definition(request: CheckCaseRequest) -> CheckSnapshotResult:
        """Set/remove a complete base-model check case (完整设置或删除检算工况).

        Supports concrete, seismic and strengthening definitions. Native enums
        start at zero and all exported fields must be retained, including inactive
        family fields. Removing a case invalidates its corresponding check file.
        This does not import or solve a current CSAN case. For concrete only, use
        run_concrete_check after committing; it imports the named model case first.
        No seismic/strengthening solver is promised by that concrete tool.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            request: action=set plus full definition, or action=remove plus
                explicit family and index; both require model-write permission.
        """
        try:
            spec = _CASE_ADAPTER.validate_python(request)
        except ValueError as exc:
            raise ToolInputError(f"Invalid check-case snapshot request (检算工况请求无效): {exc}") from exc
        if spec.action == "set":
            return _commit_snapshot(provider, "set_check_case", "Check case snapshot committed (检算工况快照已提交)",
                                    definition=spec.definition.model_dump(mode="json"))
        return _commit_snapshot(provider, "remove_check_case_snapshot", "Check case deletion committed (检算工况删除已提交)",
                                family=spec.family, index=spec.index)

    @mcp.tool()
    def set_check_stirrup_snapshot(
        definition: CheckStirrupDefinition, original_id: SnapshotId | None = None,
    ) -> CheckSnapshotResult:
        """Set a complete base-model stirrup snapshot (完整设置箍筋快照).

        Retain exported field capitalization, stored dimensions and zero-based
        model enums. These differ from legacy check-stirrup tool arguments.
        When changing an ID, provide original_id so QiaoTong migrates element
        references; no source ID is inferred. Requires model-write permission.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            definition: Complete UI stirrup snapshot, including inactive fields.
            original_id: Explicit existing stirrup ID when renumbering; omitted
                uses the target StirrupTypeId without guessing a source ID.
        """
        try:
            spec = CheckStirrupDefinition.model_validate(definition)
        except ValueError as exc:
            raise ToolInputError(f"Invalid stirrup snapshot (箍筋快照不完整或无效): {exc}") from exc
        return _commit_snapshot(provider, "set_check_stirrup", "Stirrup snapshot committed (箍筋快照已提交)",
                                definition=spec.model_dump(mode="json"), original_id=original_id)

    @mcp.tool()
    def set_element_stirrups(request: ElementStirrupsDefinition) -> CheckSnapshotResult:
        """Replace base-model stirrup assignments by family (批量完整替换单元配箍).

        shear and torsion are separate complete snapshots. None/omitted keeps a
        family; [] clears it. A zero stirrup ID means unassigned in that direction.
        The same element may occur in both families, but not twice in one family.
        References are validated by QiaoTong. Legacy assign_element_stirrup remains
        available for its existing current-CSAN workflow.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            request: shear five-entry rows and/or torsion three-entry rows, or
                explicit null to preserve a family. Both null changes no assignments.
        """
        try:
            spec = ElementStirrupsDefinition.model_validate(request)
        except ValueError as exc:
            raise ToolInputError(f"Invalid stirrup assignments (配箍快照无效): {exc}") from exc
        return _commit_snapshot(provider, "set_element_stirrups", "Stirrup assignment request committed (配箍请求已提交；None 保持、空列表清空)",
                                **spec.model_dump(mode="json"))

    @mcp.tool()
    def set_section_reinforcement(definition: SectionReinforcementDefinition) -> CheckSnapshotResult:
        """Replace a complete base-model reinforcement snapshot (完整替换截面配筋).

        Use a full UI-exported definition including generation parameters AND
        actual bar points. Every field is required; empty arrays clear that part.
        Outer/inner rows have six entries, unlike the legacy five-entry tool.
        Lengths use model units. Native enum/type values must come from the export.
        Supports ordinary, I/J-end and tapered-group identifiers. This requires
        model-write permission and commits once. Existing get_check_data results
        describe current CSAN data and are not a lossless source for this snapshot.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            definition: Complete exported section definition; retain inactive
                parameter rows, identity, native types and all actual points.
        """
        try:
            spec = SectionReinforcementDefinition.model_validate(definition)
        except ValueError as exc:
            raise ToolInputError(f"Invalid reinforcement snapshot (配筋快照不完整或无效): {exc}") from exc
        return _commit_snapshot(provider, "set_section_reinforcement",
                                f"Reinforcement snapshot for {spec.section_id_name} committed (截面配筋快照已提交)",
                                definition=spec.model_dump(mode="json"))

    @mcp.tool()
    def remove_section_reinforcement(section_id_name: QueryName) -> CheckSnapshotResult:
        """Delete reinforcement by complete base-model section identifier (按完整标识删除配筋).

        Uses the snapshot by-name endpoint, including tapered groups. It does not
        use the legacy current-CSAN sec_id/position endpoint or default to all sections.
        Requires an SDK/bridge exposing the snapshot route. qtmodel 2.9.3
        rejects this historical route with API_NOT_OPEN before sending it.

        Args:
            section_id_name: Explicit exported identifier such as 1, 1-I, 1-J,
                or G7-2; obtain it from the model/export, not a guessed sequence.
        """
        return _commit_snapshot(provider, "remove_section_reinforcement_by_name",
                                f"Reinforcement for {section_id_name} removed (指定截面配筋已删除)",
                                section_id_name=section_id_name)
