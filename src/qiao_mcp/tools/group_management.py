"""
MCP Tools for structure group, boundary group, and load group management.
结构组、边界组、荷载组管理工具

Groups are the foundation of construction stage analysis:
- Structure groups (结构组): collections of elements activated/deactivated per stage
- Boundary groups (边界组): collections of boundary conditions per stage
- Load groups (荷载组): collections of loads applied per stage
"""


import json
from typing import Any, Literal, get_args

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError, ToolInputError
from qiao_mcp.tools.schemas import (
    BoundariesQuery,
    LoadsQuery,
    NonnegativeNumber,
    PageLimit,
    PageOffset,
    QueryName,
    SelectedIds,
)


def register_group_tools(mcp: FastMCP, provider: BridgeProvider):
    """Register group management MCP tools."""

    @mcp.tool()
    def create_structure_group(
        name: str,
        element_ids: SelectedIds | None = None,
    ) -> str:
        """
        Create a structure group and optionally assign elements to it (创建结构组).

        Structure groups are used to control which elements are active during
        each construction stage (施工阶段分析中控制单元激活状态).

        Use for a new group. To append nodes/elements to an existing group, use
        add_to_structure_group; create_boundary_group groups supports/links and
        create_load_group groups loads. Creating a structure group does not
        activate its members in a stage; configure that with add_construction_stage
        or update_construction_stage after the group exists.

        Omit element_ids to create an empty group. A supplied selection must be
        nonempty and identify existing elements. Creation and membership assignment
        are separate writes with refreshes: if assignment fails, the newly created
        group may remain. Inspect list_group_members before retrying. Returns a
        confirmation rather than a group snapshot; duplicate-name policy is owned
        by the bridge. (新建与加成员分步写入，第二步失败后应先检查，不能假定整个操作回滚。)

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

        Use when retaining a group's membership but changing its label. For a
        new group use create_structure_group; to change members use
        add_to_structure_group or remove_from_structure_group. Read existing
        group names first and provide the exact old name and intended new name.

        Writes the rename, refreshes the model and returns a confirmation.
        The bridge handles name collisions and dependent stage references;
        this wrapper does not preflight them. After renaming, use the new name
        in later operations and inspect list_group_members and affected stages
        before reusing cached references. (仅更名；重名与阶段引用由桥通处理，后续使用新名称。)

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

        This creates the named group, not the boundary conditions. Create it
        before passing its name to set_support, add_elastic_support or link tools;
        then use update_construction_stage to activate/deactivate the group.
        Use create_structure_group for model entities and create_load_group for
        loads; these three group namespaces serve different stage controls.

        Writes and refreshes the model, returning a confirmation with the name.
        No supports or stage assignments are added automatically. Existing-name
        handling is delegated to the bridge, so inspect the model before reusing
        a group name. (只建边界组；边界定义和施工阶段激活需后续分别配置。)

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
        group_type: Literal["structure", "boundary", "load"],
        name: QueryName,
        limit: PageLimit = 20,
        offset: PageOffset = 0,
    ) -> str:
        """
        List members of a structure/boundary/load group (查看分组的成员信息).

        Structure groups return node and element IDs. Boundary/load groups use
        native filtered queries and return a separate page for each supported
        family: six boundary families or seven nodal/beam/plate load families.
        These pages do not cover temperature, prestress or other special loads.
        Page metadata comes from the bridge; use offset/limit for further pages.
        Requires a bridge/SDK with native queries for boundary/load groups.
        (结构组返回节点和单元；边界/荷载按支持的原生类别分页，不含温度、预应力等特殊荷载。)

        Args:
            group_type: Type of group (分组类型): 'structure', 'boundary', 'load'
            name: Group name (分组名称)
            limit: Maximum members per family/page, 1–500 (每类每页最多成员数)
            offset: Starting offset for each page (各类查询的分页偏移)
        """
        try:
            if group_type == "structure":
                groups = provider.get_structure_group_names()
                if name not in groups:
                    return f"Structure group '{name}' not found (未找到结构组 '{name}')"
                from qiao_mcp.tools.queries import _paginate

                members = {
                    "nodes": provider.get_group_nodes(group_name=name),
                    "elements": provider.get_structure_group_elements(name=name),
                }
                pages = {kind: _paginate(ids, limit, offset) for kind, ids in members.items()}
                return f"Structure group '{name}' members (结构组成员): {json.dumps(pages, ensure_ascii=False)}"
            if group_type not in {"boundary", "load"}:
                raise ToolInputError("group_type must be 'structure', 'boundary', or 'load'")
            schema, field, kind = (
                (BoundariesQuery, "boundary_type", "boundaries")
                if group_type == "boundary" else (LoadsQuery, "load_family", "loads")
            )
            pages = {
                family: provider.query_model_data(
                    kind=kind, **{field: family}, group_names=[name], limit=limit, offset=offset,
                )
                for family in get_args(schema.model_fields[field].annotation)
            }
            return f"{group_type} group '{name}' member pages (支持类别的成员页): {json.dumps(pages, ensure_ascii=False)}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error listing group members (查询分组成员失败): {e}") from e

    @mcp.tool()
    def add_elements_to_group(
        group_name: str,
        element_ids: SelectedIds,
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

        Use remove_from_structure_group to remove selected members while keeping
        the group and model entities. remove_structure_group deletes the group.

        (写模型并刷新。是向组内现有成员追加、而非替换；结构组须已存在。选型：本工具是便捷
        封装，底层与 add_to_structure_group 走同一个调用、只是仅传 element_ids。需要同时
        加节点、或一次加节点+单元时用 add_to_structure_group。移除指定成员用
        remove_from_structure_group，保留组和模型实体；删除整个组用 remove_structure_group。)

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
        Merge the current construction-stage definitions into a named operation
        stage (将当前施工阶段定义合并为指定名称的运营阶段).

        Use when intentionally consolidating the stage sequence. To add one stage
        while retaining the sequence, use add_construction_stage; to change
        activation/deactivation in one stage use update_construction_stage.
        configure_operation_stage instead selects operating load cases and factors.

        This rewrites stage definitions and refreshes the model; save a checkpoint
        if the original sequence is needed. It does not solve or combine already
        computed result arrays. Read get_model_data(kind="stages") afterwards,
        configure analysis and call run_analysis when new results are required.

        The wrapper uses the SDK merge defaults: deformation-based installation,
        self-weight in the merged stage and loading age 5 days. Use the verified
        mdb.merge_all_stages signature through call_qtmodel_api for other options.
        Returns a confirmation with the requested name, not analysis results.
        (修改阶段定义而非求解；采用 SDK 合并默认设置，需要其他合并选项时先查真实签名。)

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
        Delete a named construction-stage definition, or all stage definitions
        when name is omitted or empty (删除指定施工阶段；省略名称或空串删除全部阶段).

        Read get_model_data(kind="stages") and supply the exact stage name for
        a single deletion. Omitting name is an explicit all-stages operation,
        not a way to select the current stage. Save a model checkpoint first
        if the stage sequence may need to be restored.

        To keep a stage and deactivate its structures, boundaries or loads, use
        update_construction_stage with delete_structures, delete_boundaries or
        delete_loads. To change only the displayed stage, use switch_display_stage
        for the model view or change_construct_stage for the results view.

        Writes stage definitions, refreshes the model and returns a confirmation.
        It does not rerun analysis or verify the validity of existing results.
        Reference cleanup is handled by the bridge; reread stages after deletion.
        (只需钝化组或荷载时保留阶段并调用 update_construction_stage；只切换显示
        时使用视图工具。删除操作不重新求解，后续使用阶段和结果前须核对模型。)

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
        duration: NonnegativeNumber = 0,
        active_structures: list[list] | None = None,
        delete_structures: list[str] | None = None,
        active_boundaries: list[list] | None = None,
        delete_boundaries: list[str] | None = None,
        active_loads: list[list] | None = None,
        delete_loads: list[list] | None = None,
        temp_loads: list[str] | None = None,
        sub_steps: list[NonnegativeNumber] | None = None,
    ) -> str:
        """
        Edit one construction stage, including activation and deactivation of
        structure groups, boundary groups and load groups (修改阶段及各类组的激活/钝化).

        Use this dedicated stage-editing tool for both activation and deactivation:
        delete_structures, delete_boundaries and delete_loads deactivate groups
        within this stage while retaining their model definitions. To delete the
        stage itself use remove_construction_stage; to select a modeling view use
        switch_display_stage. Create a missing stage with add_construction_stage.

        name must identify an existing stage and all group references must exist.
        new_name and duration are always sent, including their defaults. Optional
        group lists are omitted only when None; supplied empty lists are sent
        explicitly, so they are not a request to preserve current entries. Load
        activation/deactivation rows pair a group name with time 0=start or 1=end.

        Writes and refreshes the model and returns a confirmation without solving.
        Read stages before and after editing when retaining an existing schedule;
        sub_steps requires SDK support, and [] explicitly clears sub-steps.
        (钝化不等于删除组；None 省略列表，空列表会下发。名称和工期默认值仍会提交。)

        Args:
            name: Existing stage name (现有阶段名称)
            new_name: New stage name (新名称)
            duration: Stage duration in days, including fractional days (阶段时长，天，支持小数)
            active_structures: Structures to activate [[name, age, install_method, weight_stage_id], ...]
                               (激活结构组 [[名称, 龄期, 安装方法, 计自重施工阶段号], ...])
            delete_structures: Structure group names to deactivate (钝化的结构组名称列表)
            active_boundaries: Boundaries to activate [[name, position], ...]
                               (激活的边界组信息 [[名称, 位置], ...])
            delete_boundaries: Boundary group names to deactivate (钝化的边界组名称列表)
            active_loads: Loads to activate [[name, time], ...]; time=0 start, 1 end
                          (激活荷载组 [[名称, 时间], ...]；0=阶段开始，1=阶段结束)
            delete_loads: Loads to deactivate [[name, time], ...]; time=0 start, 1 end
                          (钝化荷载组 [[名称, 时间], ...]；0=阶段开始，1=阶段结束)
            temp_loads: Temporary load group names (临时荷载组名称列表)
            sub_steps: Sub-step durations in days; None omits the option, [] clears
                       sub-steps. Requires a supporting qtmodel build
                       (子步时长列表；省略不传，空列表清除子步，需新版 qtmodel)
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
            if sub_steps is not None:
                kwargs["sub_steps"] = sub_steps

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
