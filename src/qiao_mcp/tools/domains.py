"""Domain entry points over the complete, backwards-compatible operation catalog."""

from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True)
class ToolDomain:
    name: str
    title: str
    description: str
    operations: tuple[str, ...]


def _domain(name: str, title: str, description: str, operations: str) -> ToolDomain:
    return ToolDomain(name, title, dedent(description).strip(), tuple(operations.split()))


TOOL_DOMAINS = (
    _domain(
        "inspect_bridge", "Bridge connection and readiness / 连接与就绪状态",
        """
        Diagnose the QiaoTong connection, active model state and edit readiness
        before choosing an engineering operation (只读检查连接、模型状态与编辑条件).

        Start with check_qiaotong_connection; get_model_status reports the active
        phase and allowed operations, while get_model_edit_readiness explains
        why an edit is blocked. These are diagnostics, not requests to open a
        model, clear results, prepare edits or switch stages. Use query_model
        for engineering records and manage_model_files to open/save a project.

        Supply request.operation only; these diagnostic operations have no
        arguments. They return structured state and suggested next actions,
        including an unavailable connection as data. A successful diagnostic
        call does not itself mean the bridge is connected or editable. Read
        connected/status and capability fields before proceeding; the state can
        change between this check and a later command.
        """,
        "check_qiaotong_connection get_model_status get_model_edit_readiness",
    ),
    _domain(
        "manage_model_files", "Model files and initialization / 模型文件与初始化",
        """
        Open, save or initialize the active bridge project (打开、保存或初始化模型).

        Choose save_model_file to persist current work, open_model_file to replace
        the active project with a saved one, or initialize_model to clear it for
        a new model. Use edit_geometry for entity edits and manage_checks for
        separate concrete-checking files. Inspect connection/readiness first.

        request.operation selects the matching fields. File paths are interpreted
        by the QiaoTong host, which may be a remote Windows machine, not by the
        MCP client's local filesystem. initialize_model requires confirm=true;
        open can discard unsaved work and save can overwrite an existing file.
        No automatic backup or rollback is provided. Save important work first
        and verify the active model after opening or initializing. Returns a
        completion message, without model contents or analysis results.
        """,
        "initialize_model open_model_file save_model_file",
    ),
    _domain(
        "query_model", "Model records and geometry checks / 模型数据与几何检查",
        """
        Read saved model definitions, locate entities or inspect model geometry
        without changing it (只读查询模型定义、实体与几何).

        get_model_info counts entities; get_model_data reads records by kind;
        query_model_data uses typed server filters/pages; find_entities locates
        IDs by geometry or attributes. list_group_members reads memberships.
        Named tendon, transversal and international getters read definitions.
        calc_section_property evaluates supplied candidate geometry without
        storing a section; validate_model checks connectivity and definition
        consistency, not structural adequacy. Use inspect_bridge for connection
        and permission diagnostics, query_results for solved responses, and
        manage_checks for the current concrete-checking context.

        request.operation selects one schema branch. For query_model_data,
        its own typed request remains nested, e.g. operation="query_model_data",
        request={"kind":"nodes","node_ids":[1,2]}. IDs and names refer to the
        current model. List pagination belongs to the selected operation:
        generic getters slice locally, native queries page on the bridge.
        Preserve selectors between pages and inspect truncation metadata. These
        calls neither solve nor make the model editable; empty data is not proof
        of a missing entity when a filter or unavailable backend is involved.
        """,
        """
        get_model_info get_model_data query_model_data find_entities list_group_members
        get_tendon_info get_transversal_data get_international_live_load_data
        calc_section_property validate_model
        """,
    ),
    _domain(
        "edit_geometry", "Nodes, elements and bridge layouts / 节点单元与桥梁布置",
        """
        Create, edit, renumber, merge or remove model nodes and elements, including
        standard straight-girder workflows (编辑节点、单元与标准直线梁布置).

        Choose explicit coordinate rows or evenly spaced nodes, one frame or a
        node chain, and native element rows for plates/mixed batches. Targeted
        update_element_* operations change one property; update_element edits a
        record. update_node sets absolute coordinates, move_nodes adds offsets,
        and renumbering changes IDs. Simple/continuous bridge workflows create
        geometry and supports with their documented bearing assumptions. Use
        edit_properties to define materials/sections, edit_boundaries for other
        supports, and view_model to change only the display.

        Supply request.operation and that branch's fields. Referenced materials,
        sections and nodes must exist; plate thickness is distinct from a frame
        section. Explicit IDs can be reassigned or reused by merging, so read
        query_model before constructing dependent connectivity. Renumbering
        requires both paired lists, or neither for a global renumber; deletion
        of all entities requires the operation's explicit confirmation.

        Writes require an editable model and can invalidate solved data. Batch
        and workflow calls are not transactions: earlier writes can remain after
        failure. Inspect actual IDs/connectivity before retrying; a confirmation
        is not always a readback. Solving is a separate analyze_model operation.
        """,
        """
        create_nodes create_nodes_linear create_beam_element create_beam_elements_linear
        create_elements update_node update_node_id renumber_nodes move_nodes
        update_element update_element_id renumber_elements revert_local_orientation
        update_element_material update_element_section update_element_beta
        update_element_nodes remove_nodes remove_elements merge_nodes
        create_simple_beam_bridge create_continuous_beam_bridge
        """,
    ),
    _domain(
        "edit_properties", "Materials, sections and time effects / 材料截面与时变属性",
        """
        Create or modify the shared material, section and thickness definitions
        used by structural elements (编辑单元共用的材料、截面和板厚定义).

        Choose request.operation by how the property is specified:

        - create_material and time/creep/shrinkage operations define material data.
        - create_section uses a parameterized shape; create_polygon_section uses
          closed loops/holes; create_line_width_section uses thin-wall segments;
          create_section_from_properties uses supplied engineering properties.
        - create_tapered_section references two existing end-section IDs;
          add_tapper_section_group sets variation along selected frame elements.
        - add_thickness supplies a plate thickness definition, not a frame section.

        Use edit_geometry to assign an existing definition to elements;
        edit_prestress defines tendon properties. query_model reads saved values
        or trial-calculates candidate geometry without storing it. The selected
        branch determines shape fields and units: a thickness ID and a section
        ID occupy different namespaces even if their integers match.

        update_section_property writes one full property vector at the selected
        end; calculate_section_property recalculates and stores properties for
        ALL existing sections. Do not use the latter as a readback of a manual
        override. remove_section deletes an explicit selection, while
        remove_unused_sections lets the bridge identify unreferenced definitions.
        Check element references before overwriting or removing shared data.

        Writes refresh the model and return status/message confirmations. Requested
        IDs are not a guaranteed allocation result: read saved IDs and values
        through query_model before assigning them. There is no automatic backup,
        rollback or solve, and a definition change can affect many existing
        elements. Inspect an uncertain write before repeating it.
        """,
        """
        create_material add_time_parameter add_creep_function add_shrink_function
        create_section create_polygon_section create_line_width_section
        create_section_from_properties create_tapered_section add_tapper_section_group
        add_thickness add_effective_width update_section_bias remove_section
        update_section_property calculate_section_property remove_unused_sections
        """,
    ),
    _domain(
        "edit_boundaries", "Supports, links and constraints / 支承连接与约束",
        """
        Edit mechanical boundary conditions on existing nodes and frame elements
        (编辑已有节点和杆系单元的力学边界条件).

        Use this domain for restraint or connection behavior. Choose
        request.operation by the physical relationship:

        - Node to ground: set_support for fixed/free DOFs; add_elastic_support
          for finite stiffness or one-way contact.
        - Node to node: add_elastic_link for a two-node connection;
          add_master_slave_link for one master and multiple coupled slaves.
        - Frame end: add_beam_constraint for I/J-end releases or end springs.
        - Weighted DOF relation: add_constraint_equation; remove_boundary removes
          a selected family using its node, element, name or boundary selector.

        For group creation or stage activation use edit_construction; for actual
        node connectivity use edit_geometry. Resolve existing IDs with query_model.
        The same boolean has different mechanical meanings: True fixes a DOF in
        set_support, couples it in add_master_slave_link, and RELEASES it in
        add_beam_constraint. Use the selected branch's DOF order and stiffness units.
        For support extras, supplied extra_parameters enables them by default;
        extra_enabled=False clears them, while omitting both preserves the setting.

        Writes can overwrite supports/releases or remove constraints and change
        stability. There is no backup, undo or automatic solve. The response is
        a confirmation, not a verified saved definition. Read boundaries back and
        check local axes before analyze_model; inspect an uncertain write before
        retrying to avoid duplicating a link or removing the wrong constraint.
        """,
        """
        set_support add_elastic_link add_master_slave_link add_elastic_support
        add_beam_constraint add_constraint_equation remove_boundary
        """,
    ),
    _domain(
        "edit_construction", "Groups and construction schedules / 分组与施工阶段",
        """
        Manage structure/boundary/load groups and construction or operation-stage
        schedules, including activation and deactivation (管理分组与阶段激活、钝化).

        Group operations create/rename/remove groups or change memberships;
        add_to_structure_group accepts nodes and elements, and add_elements_to_group
        is its element-only compatibility form. add_construction_stage creates a
        stage; update_construction_stage edits its activation/deactivation lists.
        delete_structures/delete_boundaries/delete_loads deactivate groups in that
        stage without deleting their definitions. remove_construction_stage removes
        stages; merge_operation_stage builds the operation stage. set_self_weight_stage
        assigns self-weight timing and configure_operation_stage selects case families.
        Use edit_loads for physical loads and view_model for stage display only.

        Select request.operation and its fields. Group names are exact references
        in three separate namespaces; referenced definitions must already exist.
        A missing optional list and an explicit empty list have different effects.
        configure_operation_stage requires all four case-family lists; [] disables
        that family. Removing a group does not remove its model entities; removing
        a stage and deactivating a group are separate operations. Writes refresh
        the model, with no solve or automatic schedule rollback. Read groups/stages
        through query_model before and after changing an existing schedule.
        """,
        """
        create_load_group create_structure_group update_structure_group_name
        remove_structure_group create_boundary_group add_to_structure_group
        remove_from_structure_group add_elements_to_group add_construction_stage
        merge_operation_stage remove_construction_stage update_construction_stage
        set_self_weight_stage configure_operation_stage
        """,
    ),
    _domain(
        "edit_loads", "Static load definitions / 静力荷载与组合",
        """
        Define static load cases/combinations and assign nodal, beam, plate,
        temperature, cable or settlement loads (定义静力工况组合并施加载荷).

        Create a case before assigning loads. Nodal forces target nodes, beam
        distributions target frames, and plate loads target plates. A distributed
        plane load places an existing pattern, whose native definition can be
        created through access_backend. Choose system temperature for the SDK's
        final-temperature input, gradient for a linear difference, code section
        temperature for standard parameters, or custom temperature for layer rows.
        Cable initial-force and unstressed-length loads have separate inputs.
        Use edit_prestress for named tendons, edit_traffic for vehicle/lane cases,
        and edit_construction for groups, self-weight timing and activation.

        request.operation selects the matching units, coordinate system and ID
        namespace. A static case categorized as "活载" does not create a moving
        vehicle case. Native row layouts, local directions and load magnitudes
        belong to the selected operation; no cross-family unit conversion is
        implied. Writes add or replace definitions and refresh the model without
        solving. Verify cases, groups and referenced entities with query_model;
        repeated load calls can accumulate effects, so read back uncertain writes.
        """,
        """
        create_load_case add_load_combine apply_nodal_force apply_beam_distributed_load
        add_system_temperature add_gradient_temperature add_custom_temperature
        add_beam_section_temperature add_initial_tension_load add_cable_length_load
        add_plate_element_load add_distribute_plane_load add_support_settlement
        """,
    ),
    _domain(
        "analyze_model", "Structural analysis and dynamics / 结构求解与动力设置",
        """
        Configure and run structural analysis, including masses, response spectra,
        time-history functions/cases and buckling settings (配置并执行结构分析).

        configure_analysis sets construction/creep/modal solver switches;
        update_bulking_setting sets basic buckling controls. Mass and dynamic
        function/case operations define solver inputs. set_gravity writes the
        project gravity setting. These configuration operations do not solve:
        choose run_analysis explicitly after model, loads and stages are ready.
        Use query_results for solved responses and manage_checks for concrete
        code verification, which is a separate computation.

        request.operation selects its own fields and units. Spectrum/time-history
        functions and cases must be linked through the appropriate backend
        settings; use access_backend for options absent from a dedicated operation.
        Configuration defaults can overwrite prior settings: read them first
        when preserving an existing setup. run_analysis reports periodic progress
        while the solver runs, and only a successful terminal state is completion.
        Its read_timeout limits waiting, not the backend computation; timeout or
        connection loss does not cancel the solve. Check inspect_bridge before
        retrying. Neither a completed solve nor a configuration confirmation
        establishes structural safety or a passing code check.
        """,
        """
        set_gravity add_nodal_mass add_load_to_mass add_spectrum_function
        add_spectrum_case add_time_history_function add_time_history_case
        update_bulking_setting configure_analysis run_analysis
        """,
    ),
    _domain(
        "edit_prestress", "Tendon geometry and prestress / 钢束几何与预应力",
        """
        Create tendon properties and geometry, assign tendon elements, or apply
        prestress to named tendons (定义钢束属性、线形、单元匹配及预应力).

        create_tendon_property supplies mechanical/loss parameters. Then choose
        create_tendon_2d for a planar profile or add_tendon_3d for a spatial path
        using that property name. assign_tendon_elements matches tendons to model
        elements; apply_prestress assigns tension in a load case. Use edit_loads
        for cable-element force/length loads, query_model for saved tendon
        definitions, and query_results for discretized geometry or solved losses.

        Supply request.operation and its own coordinate/force fields. Profile
        control points are positioned by insertion/rotation options; a property
        definition alone creates no tendon path or applied force. Existing property,
        element and case references must be valid. Reusing a tendon name can
        replace its geometry, and prestress calls can change load definitions.
        Writes refresh the model without solving. Verify the resulting geometry
        and assignments before activating the load in edit_construction and
        running analyze_model; confirmations are not effective-prestress results.
        """,
        """
        create_tendon_property create_tendon_2d add_tendon_3d
        assign_tendon_elements apply_prestress
        """,
    ),
    _domain(
        "edit_traffic", "Moving and transversal traffic / 移动与横向活载",
        """
        Configure the live-load system and define moving, transversal or
        international vehicles, lanes and cases (配置活载体系及车辆车道工况).

        Select the matching system explicitly. Traditional moving-load setup uses
        node tandem, influence plane, lane, vehicle and create_live_load_case.
        set_transversal_vehicle/lane/case define the transverse family;
        set_international_vehicle, create_en1991_vehicle, set_planned_lane and
        set_international_live_load_case handle AASHTO/BS/EN1991 definitions.
        remove_transversal_data removes an explicit transverse target. Use
        edit_loads for static loads, query_model for saved definitions,
        edit_construction to include cases in the operation stage and
        query_results for solved envelopes.

        request.operation selects the family's exact schema. Operations with a
        typed request keep that request nested. Names/IDs refer to existing
        matching definitions; unit conventions differ between standards and
        must follow the selected schema rather than a blanket conversion.
        Full-definition updates reset omitted scalar fields; preserve verified
        exported values when retaining settings. Switching systems clears old
        definitions only with explicit clear_existing=true. Writes refresh the
        model without analysis; API availability also depends on the desktop
        build. Read back actual IDs/names before case activation and solving.
        """,
        """
        configure_live_load_system add_node_tandem add_influence_plane add_traffic_lane
        add_standard_vehicle create_live_load_case set_transversal_vehicle
        set_transversal_lane set_transversal_case remove_transversal_data
        set_international_vehicle create_en1991_vehicle set_planned_lane
        set_international_live_load_case
        """,
    ),
    _domain(
        "manage_checks", "Code-check definitions and execution / 规范检算定义与执行",
        """
        Set up, edit, execute and inspect code-checking data, with distinct model
        snapshots and current concrete-checking context (管理模型检算定义及当前检算窗口).

        Model snapshot operations manage check materials/cases, reinforcement and
        stirrups using complete native definitions. setup_concrete_check imports
        an existing concrete case; check-context operations configure combinations,
        reinforcement, stirrups and analysis options, and manage_check_case_file
        opens/saves separate check files. run_concrete_check imports the named
        case and executes verification. get_check_data reads context definitions,
        settings or computed checking results. Use edit_properties for structural
        materials/sections and analyze_model for the structural solve.

        request.operation selects the namespace, units and replacement behavior.
        Snapshot inputs preserve native exported units/enums; convenience length
        fields can use meters with documented internal conversions. A context read
        is not a lossless model snapshot. Full replacements require carrying
        forward retained values, and explicit empty assignment lists can clear
        data. Desktop capabilities are checked; unavailable routes fail without
        a successful commit. Save important data before destructive updates.
        Verification timeout does not cancel background computation; inspect
        state before retrying. Completion means the calculation finished, not
        that the structure passed: read and interpret the engineering results.
        """,
        """
        setup_concrete_check add_check_load_combination run_concrete_check
        add_parametric_reinforcement add_check_stirrup update_vertical_steel_tendon
        get_check_data configure_check_analysis manage_check_stirrup assign_element_stirrup
        manage_check_case_file manage_check_material manage_check_case_definition
        set_check_stirrup_snapshot set_element_stirrups set_section_reinforcement
        remove_section_reinforcement
        """,
    ),
    _domain(
        "query_results", "Structural responses and tendon results / 结构响应与钢束结果",
        """
        Retrieve numerical structural responses from the bridge's result data
        (从桥通结果数据读取结构数值响应).

        Use after analyze_model has completed the relevant solve. Choose
        request.operation for the result family:

        - get_analysis_results: displacement/reaction uses node IDs; force/stress
          uses element IDs. stage_id=-1 is operation, 0 is the stage envelope,
          and a positive value selects one construction stage.
        - get_special_results: use kind plus mode for modal output, or the
          documented node/link/element selector for concurrent and special results.
        - get_live_load_results: request one maximum or minimum envelope extreme;
          get_tendon_loss_results reads losses for a named, activated stage tendon.
        - get_tendon_position_result/get_tendon_length_result: discretized tendon
          geometry; pre-solve availability depends on the bridge.

        Example: request={"operation":"get_analysis_results","result_type":"force",
        "ids":[10,11],"stage_id":-1,"case_name":"Dead"} selects static operation
        results for elements 10 and 11. Full case identifiers must come from
        QiaoTong results/UI; never derive TV:/MV: prefixes from combination codes.
        Use query_model for saved definitions, manage_checks for code-check results
        and view_model for plots. Envelopes do not represent simultaneous loads.

        Returns status/message with formatted numerical data. For paged list
        operations, follow the next-offset hint with unchanged selectors; slicing
        occurs locally after backend retrieval. Tendon and live-load operations
        have no pagination fields. These calls do not solve, refresh or certify
        result freshness. An empty response can indicate an absent case, inactive
        tendon or unavailable results; verify context before interpreting it as
        zero. Multiple calls need a stable solved model for comparison.
        """,
        """
        get_analysis_results get_special_results get_live_load_results
        get_tendon_loss_results get_tendon_position_result get_tendon_length_result
        """,
    ),
    _domain(
        "view_model", "Desktop view and images / 桌面显示与图像",
        """
        Control the desktop view and capture PNG images of the model or existing
        analysis results (控制桌面视图并截取模型或已有结果图像).

        Choose request.operation for the presentation task:

        - set_view_angle, set_render, display_ids, activate_structure and
          reset_display control camera, shading, labels and visible entities.
        - switch_display_stage selects a modeling stage by name;
          change_construct_stage selects a results stage by integer index.
        - save_model_screenshot captures the view; plot_analysis_result draws a
          selected solved component. Use query_results for numerical values.
        - set_unit changes display units; tool input units remain as documented.

        Defaults are assignments, not toggles: set_render(flag=true) requests
        solid shading; display_ids applies BOTH flags and an omitted flag hides
        that label family. set_unit sends both force and length units each time.
        A screenshot defaults to the iso camera; view_angle="current" preserves
        the camera. If applying a preset fails, the current view is captured and
        the reply is a saved-path warning even when return_image=true.

        A connected desktop view is required. Display operations return a
        confirmation and change presentation only; edit_geometry and
        edit_construction change entities and schedules. The two image operations
        write PNG bytes to file_path on the MCP host and overwrite that path.
        Use a distinct path to retain an earlier capture. return_image=true
        normally returns MCP Image content; false returns a saved-path message.
        No solve runs and no previous view is restored automatically. Confirm
        the selected stage/component before treating a plot as evidence.
        """,
        """
        save_model_screenshot plot_analysis_result set_view_angle display_ids
        activate_structure set_render reset_display set_unit change_construct_stage
        switch_display_stage
        """,
    ),
    _domain(
        "access_backend", "Native API discovery and calls / 原生 API 检索与调用",
        """
        Discover installed qtmodel methods and call a native API when a dedicated
        domain operation does not expose the required feature (检索并调用长尾原生接口).

        Start with list_qtmodel_api for the mdb/odb/cdb object and a method pattern;
        then call_qtmodel_api with the verified method name and keyword arguments.
        Prefer the relevant domain operation for supported tasks because it
        supplies typed arguments and engineering guidance. Use inspect_bridge
        for connection diagnostics; method discovery alone does not establish
        desktop route availability or permission to mutate a model.

        request.operation distinguishes inspection from execution. kwargs are
        native backend parameters with method-specific units; do not translate
        field names, invent signatures or infer units from another endpoint.
        Calls retain model-state guards and gateway management rules, but the
        selected method may overwrite/delete data or perform external effects.
        Review its discovered contract and current state before execution. The
        result is the normalized native response; unsupported routes and failed
        calls are errors. A lost write reply has an unknown outcome: inspect the
        affected objects before any retry, since no automatic rollback is offered.
        """,
        "list_qtmodel_api call_qtmodel_api",
    ),
)
