"""
MCP Tools for structure group, boundary group, and load group management.
结构组、边界组、荷载组管理工具

Groups are the foundation of construction stage analysis:
- Structure groups (结构组): collections of elements activated/deactivated per stage
- Boundary groups (边界组): collections of boundary conditions per stage
- Load groups (荷载组): collections of loads applied per stage
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bridge_mcp.providers import BridgeProvider


def register_group_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register group management MCP tools."""

    @mcp.tool()
    def create_structure_group(
        name: str,
        element_ids: list[int] | str | None = None,
    ) -> str:
        """
        Create a structure group and optionally assign elements to it (创建结构组).

        Structure groups are used to control which elements are active during
        each construction stage (施工阶段分析中控制单元激活状态).

        Args:
            name: Structure group name (结构组名称)
            element_ids: Element IDs to add, int list or range string like '1to20'
                         (单元编号列表或范围字符串，如 '1to20')
        """
        try:
            provider.add_structure_group(name=name)
            if element_ids is not None:
                provider.add_elements_to_structure_group(
                    name=name, element_ids=element_ids
                )
                return (
                    f"Structure group '{name}' created with elements {element_ids} "
                    f"(结构组 '{name}' 创建成功，已添加单元)"
                )
            return f"Structure group '{name}' created (结构组 '{name}' 创建成功)"
        except Exception as e:
            return f"Error creating structure group (创建结构组失败): {e}"

    @mcp.tool()
    def update_structure_group_name(name: str, new_name: str) -> str:
        """
        Rename an existing structure group (重命名结构组).

        Args:
            name: Current structure group name (当前结构组名称)
            new_name: New structure group name (新结构组名称)
        """
        try:
            provider.update_structure_group_name(name=name, new_name=new_name)
            return f"Successfully renamed structure group '{name}' to '{new_name}' (成功重命名结构组)"
        except Exception as e:
            return f"Error renaming structure group (重命名结构组失败): {e}"

    @mcp.tool()
    def remove_structure_group(name: str = "") -> str:
        """
        Remove a structure group (删除结构组).
        If no name is provided, removes all structure groups.

        Args:
            name: Name of the structure group to remove, leave empty to remove all (待删除的结构组名称，不填则删除全部)
        """
        try:
            provider.remove_structure_group(name=name)
            target = f"'{name}'" if name else "all"
            return f"Successfully removed structure group(s) {target} (成功删除结构组)"
        except Exception as e:
            return f"Error removing structure group (删除结构组失败): {e}"

    @mcp.tool()
    def create_boundary_group(
        name: str,
    ) -> str:
        """
        Create a boundary condition group (创建边界组).

        Boundary groups collect supports/links to be activated or deactivated
        together during construction stages (施工阶段中统一控制边界条件激活状态).

        Args:
            name: Boundary group name (边界组名称)
        """
        try:
            provider.add_boundary_group(name=name)
            return f"Boundary group '{name}' created (边界组 '{name}' 创建成功)"
        except Exception as e:
            return f"Error creating boundary group (创建边界组失败): {e}"

    @mcp.tool()
    def create_load_group(
        name: str,
    ) -> str:
        """
        Create a load group (创建荷载组).

        Load groups collect loads to be applied or removed together during
        construction stages (施工阶段中统一控制荷载施加状态).

        Args:
            name: Load group name (荷载组名称)
        """
        try:
            provider.add_load_group(name=name)
            return f"Load group '{name}' created (荷载组 '{name}' 创建成功)"
        except Exception as e:
            return f"Error creating load group (创建荷载组失败): {e}"

    @mcp.tool()
    def list_group_members(
        group_type: str,
        name: str,
    ) -> str:
        """
        List members of a structure/boundary/load group (查看分组的成员信息).

        Args:
            group_type: Type of group (分组类型): 'structure', 'boundary', 'load'
            name: Group name (分组名称)
        """
        try:
            if group_type == "structure":
                groups = provider.get_structure_group_names()
                if name not in groups:
                    return f"Structure group '{name}' not found (未找到结构组 '{name}')"
                members = provider.get_structure_group_elements(name=name)
                return f"Structure group '{name}' elements (结构组成员): {members}"
            elif group_type == "boundary":
                groups = provider.get_boundary_data()
                return f"All boundary groups (所有边界组): {list(groups.keys())}"
            elif group_type == "load":
                cases = provider.get_load_case_names()
                return f"All load cases/groups (所有荷载工况): {cases}"
            else:
                return "group_type must be 'structure', 'boundary', or 'load'"
        except Exception as e:
            return f"Error listing group members (查询分组成员失败): {e}"

    @mcp.tool()
    def add_elements_to_group(
        group_name: str,
        element_ids: list[int] | str,
    ) -> str:
        """
        Add elements to an existing structure group (向已有结构组添加单元).

        Args:
            group_name: Structure group name (结构组名称)
            element_ids: Element IDs to add (单元编号，支持列表或范围字符串 '1to20')
        """
        try:
            provider.add_elements_to_structure_group(
                name=group_name, element_ids=element_ids
            )
            return (
                f"Added elements {element_ids} to structure group '{group_name}' "
                f"(已向结构组 '{group_name}' 添加单元)"
            )
        except Exception as e:
            return f"Error adding elements to group (添加单元到结构组失败): {e}"

    @mcp.tool()
    def merge_operation_stage(
        name: str = "运营阶段",
    ) -> str:
        """
        Merge all construction stages into a final operation stage (合并为运营阶段).

        This finalizes the construction stage analysis by creating an operation
        stage that accumulates all previous stage results.
        通过合并所有施工阶段创建运营阶段，作为施工阶段分析的最终状态。

        Args:
            name: Name for the merged operation stage (运营阶段名称)
        """
        try:
            provider.merge_all_stages(name=name)
            return (
                f"Successfully merged all stages into operation stage '{name}' "
                f"(成功合并为运营阶段 '{name}')"
            )
        except Exception as e:
            return f"Error merging stages (合并施工阶段失败): {e}"

    @mcp.tool()
    def remove_construction_stage(name: str = "") -> str:
        """
        Remove a construction stage (删除施工阶段).

        Args:
            name: Name of the stage to remove. If empty, removes all stages.
                  (要删除的施工阶段名称。如果为空，则删除所有施工阶段)
        """
        try:
            provider.remove_construction_stage(name=name)
            target = f"stage '{name}'" if name else "all stages"
            return f"Successfully removed {target} (成功删除施工阶段)"
        except Exception as e:
            return f"Error removing construction stage (删除施工阶段失败): {e}"

    @mcp.tool()
    def update_construction_stage(
        name: str,
        new_name: str = "",
        duration: int = 0,
        active_structures: list[list] | None = None,
        delete_structures: list[str] | None = None,
        active_boundaries: list[list] | None = None,
        delete_boundaries: list[str] | None = None,
        active_loads: list[list] | None = None,
        delete_loads: list[list] | None = None,
        temp_loads: list[str] | None = None,
    ) -> str:
        """
        Update an existing construction stage (修改施工阶段).

        Used to activate/deactivate structure groups, boundaries, and loads
        in a specific construction stage.
        (用于在特定施工阶段激活/钝化结构组、边界条件和荷载)

        Args:
            name: Existing stage name (现有阶段名称)
            new_name: New stage name (新名称)
            duration: Stage duration in days (阶段时长，天)
            active_structures: Structures to activate [[name, age, mat_id, time_param_id], ...]
                               (激活的结构组信息 [[名称, 材龄, 材料号, 时间参数号], ...])
            delete_structures: Structure group names to deactivate (钝化的结构组名称列表)
            active_boundaries: Boundaries to activate [[name, position], ...]
                               (激活的边界组信息 [[名称, 位置], ...])
            delete_boundaries: Boundary group names to deactivate (钝化的边界组名称列表)
            active_loads: Loads to activate [[name, day], ...] (激活的荷载组信息 [[名称, 天数], ...])
            delete_loads: Loads to deactivate [[name, day], ...] (钝化的荷载组信息 [[名称, 天数], ...])
            temp_loads: Temporary load group names (临时荷载组名称列表)
        """
        try:
            kwargs = {"name": name, "new_name": new_name, "duration": duration}
            if active_structures is not None:
                kwargs["active_structures"] = [tuple(item) for item in active_structures]
            if delete_structures is not None:
                kwargs["delete_structures"] = delete_structures
            if active_boundaries is not None:
                kwargs["active_boundaries"] = [tuple(item) for item in active_boundaries]
            if delete_boundaries is not None:
                kwargs["delete_boundaries"] = delete_boundaries
            if active_loads is not None:
                kwargs["active_loads"] = [tuple(item) for item in active_loads]
            if delete_loads is not None:
                kwargs["delete_loads"] = [tuple(item) for item in delete_loads]
            if temp_loads is not None:
                kwargs["temp_loads"] = temp_loads

            provider.update_construction_stage(**kwargs)
            return f"Successfully updated construction stage '{name}' (成功修改施工阶段 '{name}')"
        except Exception as e:
            return f"Error updating construction stage (修改施工阶段失败): {e}"

    @mcp.tool()
    def switch_display_stage(stage_name: str) -> str:
        """
        Switch the view to a specific construction stage (切换显示阶段).

        Updates the software UI to display the model at the specified stage.
        (更新软件界面，显示指定施工阶段的模型状态)

        Args:
            stage_name: Name of the stage to display (要显示的阶段名称)
        """
        try:
            provider.switch_display_stage(stage_name=stage_name)
            return f"Successfully switched display to stage '{stage_name}' (成功切换显示阶段)"
        except Exception as e:
            return f"Error switching display stage (切换显示阶段失败): {e}"
