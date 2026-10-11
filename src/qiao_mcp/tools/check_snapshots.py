"""Complete base-model definitions, separate from legacy CSAN editing tools."""

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.check_schemas import (
    CheckSnapshotResult,
    CheckStirrupDefinition,
    ElementStirrupsDefinition,
    SectionReinforcementDefinition,
    SnapshotId,
)
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import QueryName


def _commit_snapshot(provider: BridgeProvider, method: str, message: str, **kwargs) -> CheckSnapshotResult:
    try:
        provider.write_check_snapshot(method, **kwargs)
        return CheckSnapshotResult(status="success", committed=True, message=message)
    except Exception as exc:
        raise ToolError(f"Error writing model check snapshot (写入基础模型检算快照失败): {exc}") from exc


def register_check_snapshot_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register fixed snapshot operations without changing legacy check contracts."""

    @mcp.tool()
    def set_check_stirrup_snapshot(
        definition: CheckStirrupDefinition, original_id: SnapshotId | None = None,
    ) -> CheckSnapshotResult:
        """Set a complete base-model stirrup snapshot (完整设置箍筋快照).

        Retain exported field capitalization, stored dimensions and zero-based
        model enums. These differ from legacy check-stirrup tool arguments.
        When changing an ID, provide original_id so QiaoTong migrates element
        references; no source ID is inferred. Requires model-write permission.

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

        Args:
            section_id_name: Explicit exported identifier such as 1, 1-I, 1-J,
                or G7-2; obtain it from the model/export, not a guessed sequence.
        """
        return _commit_snapshot(provider, "remove_section_reinforcement_by_name",
                                f"Reinforcement for {section_id_name} removed (指定截面配筋已删除)",
                                section_id_name=section_id_name)
