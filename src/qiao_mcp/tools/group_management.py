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

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError


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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating structure group (创建结构组失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error renaming structure group (重命名结构组失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing structure group (删除结构组失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error creating boundary group (创建边界组失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error listing group members (查询分组成员失败): {e}") from e

    @mcp.tool()
    def add_elements_to_group(
        group_name: str,
        element_ids: list[int] | str,
    ) -> str:
        """
        Add elements to an existing structure group — elements only
        (向已有结构组添加单元，仅单元).

        Writes to the model and refreshes it. Adds to the group's existing
        members rather than replacing them; the group must already exist
        (create_structure_group).

        When to use vs. siblings: this is a convenience wrapper — it forwards to
        the same underlying call as add_to_structure_group with only
        element_ids. Use add_to_structure_group when you also have nodes to add,
        or to do nodes and elements in one call.

        Neither tool can take members out. remove_structure_group deletes the
        whole group; to drop individual members use the escape hatch:
        call_qtmodel_api(api_object="mdb",
                         method="remove_structure_from_group", kwargs={...}).

        (写模型并刷新。是向组内现有成员追加、而非替换；结构组须已存在。选型：本工具是便捷
        封装，底层与 add_to_structure_group 走同一个调用、只是仅传 element_ids。需要同时
        加节点、或一次加节点+单元时用 add_to_structure_group。两者都不能移除成员；
        remove_structure_group 是删掉整个组，要移除单个成员需经逃生舱调
        remove_structure_from_group。)

        Args:
            group_name: Structure group name, must already exist
                        (结构组名称，须已存在)
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error adding elements to group (添加单元到结构组失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error merging stages (合并施工阶段失败): {e}") from e

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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error removing construction stage (删除施工阶段失败): {e}") from e

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
            kwargs: dict[str, Any] = {"name": name, "new_name": new_name, "duration": duration}
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
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error updating construction stage (修改施工阶段失败): {e}") from e

    @mcp.tool()
    def switch_display_stage(stage_name: str) -> str:
        """
        Switch the modelling view to a construction stage, BY NAME
        (按阶段名切换建模视图的施工阶段).

        Display-only: changes which stage the software shows, and refreshes the
        model view. It does not re-run the analysis and does not change results.
        The stage must already exist (add_construction_stage).

        When to use vs. change_construct_stage: this one takes the stage NAME
        and drives the modelling view (mdb). change_construct_stage takes an
        integer stage INDEX and drives the results/post-processing view (odb) —
        use that when stepping through stages to read results.

        (纯显示操作：切换软件显示的阶段并刷新视图，不重新求解、不改变结果；阶段须已存在。
        选型：本工具收阶段"名"、作用于建模视图(mdb)；change_construct_stage 收阶段"号"、
        作用于结果/后处理视图(odb)，逐阶段读结果时用它。)

        Args:
            stage_name: Name of the stage to display, must already exist
                        (要显示的阶段名称，须已存在)
        """
        try:
            provider.switch_display_stage(stage_name=stage_name)
            return f"Successfully switched display to stage '{stage_name}' (成功切换显示阶段)"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error switching display stage (切换显示阶段失败): {e}") from e
