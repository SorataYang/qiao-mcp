"""
MCP escape-hatch tool — controlled access to the full qtmodel API.
逃生舱工具：受控访问 qtmodel 全量 API

The curated tools cover common bridge workflows. For the long tail of
qtmodel's mdb / odb / cdb methods, this gateway exposes a
single discover-then-call surface instead of one wrapper tool per method.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.schemas import (
    ApiObject,
    ConnectionResult,
    ModelEditReadinessResult,
    ModelStateResult,
)


def register_api_gateway_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register the qtmodel API discovery + call gateway."""

    @mcp.tool()
    def check_qiaotong_connection() -> ConnectionResult:
        """
        Diagnose the connection to QiaoTong software (诊断桥通软件连接状态).

        CALL THIS FIRST when any tool reports the backend is unavailable.
        It distinguishes the failure modes, which need different fixes:
        （任一工具报后端不可用时先调用本工具，它区分需要不同处置的状态）

        - connected (已连接): HTTP service is reachable; use get_model_status
          to check whether the current model permits the intended operation.
        - software_not_running (软件未启动): start QiaoTong and wait for the
          main window, then retry. （启动桥通并等待主界面加载）
        - version_mismatch (版本不匹配): only with qtmodel 2.6/2.7, which pinned
          an exact QiaoTong API version — the user must upgrade QiaoTong (or
          install a matching qtmodel). qtmodel 2.8.2 removed that handshake, so
          this status no longer occurs there; mismatched pairs connect, and an
          older QiaoTong instead shows up as `state_unknown` in get_model_status.
          （仅 qtmodel 2.6/2.7 会出现：两侧版本须精确一致，需升级桥通；2.8.2 起
          已取消该握手，桥通偏旧时改由 get_model_status 报 state_unknown）

        Returns the status, a human-readable message, the recommended action,
        and the client/server versions involved.

        IMPORTANT: when connecting through a port forward (e.g. an SSH tunnel to
        QiaoTong on another machine), the URL host must be `localhost`, not
        `127.0.0.1`. Windows HTTP.sys validates the Host header and rejects the
        bare IP with "400 Invalid Hostname" even though the port is reachable.
        （经端口转发访问时必须用 localhost；Windows HTTP.sys 会以
        400 Invalid Hostname 拒绝 127.0.0.1 的 Host 头）
        """
        try:
            status = provider.get_connection_status()
        except Exception as e:
            raise ToolError(f"Error checking connection (连接诊断失败): {e}") from e

        lines = [
            f"status: {status.get('status', 'unknown')}",
            f"connected: {status.get('connected')}",
        ]
        if status.get("compatible") is not None:
            lines.append(f"compatible: {status['compatible']}")
        for key in ("message", "action"):
            if status.get(key):
                lines.append(f"{key}: {status[key]}")

        client = status.get("client") or {}
        if client.get("qtmodel_version"):
            lines.append(f"qtmodel (client): {client['qtmodel_version']}")
        if client.get("active_url"):
            lines.append(f"active url: {client['active_url']}")

        server = status.get("server") or {}
        if server.get("api_version"):
            lines.append(f"QiaoTong API (server): {server['api_version']}")

        model_state = status.get("model_state") or server.get("model_state")
        if isinstance(model_state, dict):
            lines.extend(
                [
                    f"model opened: {model_state.get('model_opened')}",
                    f"phase: {model_state.get('phase')}",
                    f"stage: {model_state.get('stage_name')}",
                    f"base stage: {model_state.get('is_base_stage')}",
                    f"has result data: {model_state.get('has_result_data')}",
                ]
            )

        # 未连上且配置里用了裸 IP：Windows HTTP.sys 会以 400 Invalid Hostname
        # 拒绝 127.0.0.1 的 Host 头，端口通也连不上，必须改用 localhost。
        # 实测于 SSH 端口转发访问远端桥通的场景。
        if not status.get("connected"):
            configured = str(client.get("configured_url") or "")
            active = str(client.get("active_url") or "")
            if "127.0.0.1" in configured or "127.0.0.1" in active:
                lines.append(
                    "hint: the URL uses 127.0.0.1 — Windows HTTP.sys rejects that "
                    "Host header with '400 Invalid Hostname' even when the port is "
                    "reachable. Set QIAOTONG_HTTP_URL to use localhost instead, "
                    "e.g. http://localhost:55125/pythonForQt/ "
                    "（请改用 localhost，而非 127.0.0.1）"
                )

        return ConnectionResult(
            status="success", message="\n".join(lines),
            connection_status=status.get("status", "unknown"),
            connected=bool(status.get("connected")), compatible=status.get("compatible"),
            client=client, server=server, action=status.get("action") or "",
        )

    @mcp.tool()
    def get_model_status() -> ModelStateResult:
        """Get QiaoTong's current model lifecycle and operation capabilities.

        获取桥通当前是否打开模型、前处理/求解/后处理阶段、当前显示阶段是否
        为基本阶段、是否存在结果，以及 MCP 当前可执行的读模型、改模型、
        修改施工阶段、结果查询、分析和视图操作能力。

        Call this before starting a model workflow and whenever an operation is
        rejected. This tool only observes state; it never switches stages,
        deletes results, or changes the model.
        Newer desktops also report opaque model_instance_id, model_revision,
        history_revision and pending_command_count fields. These identify the
        opened model and command state; do not derive or reuse them across models.
        """
        try:
            return ModelStateResult.model_validate(provider.get_model_state())
        except Exception as e:
            raise ToolError(f"Error checking model status (模型状态查询失败): {e}") from e

    @mcp.tool()
    def get_model_edit_readiness() -> ModelEditReadinessResult:
        """Diagnose why the current model cannot be edited (只读检查编辑准备项).

        Available even when model reads/writes are blocked, including solving,
        postprocessing and an unknown model state. The readiness object contains
        only bridge-reported fields: success means a response was received, NOT
        that editing is safe. Missing API, connection failure and unknown data
        are reported explicitly. Any preparation_token is opaque and must not
        be cached or reused. This tool never calls prepare_model_edit, switches
        stages or deletes results; ask the user to handle preparation in QiaoTong.
        """
        try:
            return ModelEditReadinessResult.model_validate(provider.get_model_edit_readiness())
        except Exception as e:
            raise ToolError(f"Error checking edit readiness (编辑就绪诊断失败): {e}") from e

    @mcp.tool()
    def list_qtmodel_api(api_object: ApiObject, pattern: str = "") -> str:
        """
        Discover qtmodel API methods and their real signatures (检索 qtmodel API 方法及签名).

        Use this to find long-tail methods NOT covered by the curated tools,
        then invoke them with call_qtmodel_api. ALWAYS discover the real
        signature here before calling — do not guess parameter names.
        （先用本工具查到真实签名，再用 call_qtmodel_api 调用，切勿臆测参数名。）

        New qtmodel builds expose model queries on mdb; older releases use odb.
        For existing-model section geometry use mdb.get_model_section_shape,
        not mdb.get_section_shape (the local geometry builder).

        Updated source builds also expose reset_*_setting analysis resets and
        copy_thicknesses / arrange_thickness_ids / remove_thicknesses through mdb.
        Search "reset_" or "thickness" to check availability in the installed build.
        qtmodel 2.9 adds, among others, transversal analysis (search "transversal"),
        international and planned-lane live loads ("international", "planned"),
        strengthening ("strengthen"), exact object deletion ("delete_model_object")
        and complete reinforcement/check snapshots on cdb ("snapshot", "set_").
        Search "update_operation_stage_setting" for transversal_load_cases support;
        search "remove_material" / "remove_tendon_property" for cascade defaults.
        Current source also adds mass/stiffness factor definitions ("_factor"),
        flange definitions/effective-width calculation ("flange", "effective_width"),
        model statistics ("statistics", "weight_table"), merge_node_groups,
        merge_frame_elements, merge_plate_elements and move_nodes_by_offsets.
        These long-tail methods remain available here; common transversal,
        international and model-check snapshots also have dedicated tools.

        Args:
            api_object: Which database to inspect (数据库对象):
                "mdb" (模型查询/建模), "odb" (结果/视图；旧版模型查询), "cdb" (检算)
            pattern: Case-insensitive substring filter on method name
                     (方法名关键字过滤，如 "tendon"、"spectrum")
        """
        try:
            methods = provider.list_api_methods(api_object, pattern)
            if not methods:
                hint = f" matching '{pattern}'" if pattern else ""
                return f"No {api_object} methods found{hint} (未找到匹配方法)"
            lines = [f"{m['method']}{m['signature']}" for m in methods]
            return (
                f"{len(methods)} {api_object} method(s)"
                + (f" matching '{pattern}'" if pattern else "")
                + ":\n"
                + "\n".join(lines)
            )
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error listing API (检索 API 失败): {e}") from e

    @mcp.tool()
    def call_qtmodel_api(
        api_object: ApiObject,
        method: str,
        kwargs: dict[str, Any] | None = None,
    ) -> str:
        """
        Call a qtmodel API method not covered by a curated tool (调用 qtmodel 长尾 API).

        ESCAPE HATCH — prefer a dedicated tool when one exists. Discover the
        real signature with list_qtmodel_api first. Arguments are validated
        against the real signature before dispatch, so a wrong parameter name
        fails fast with the correct signature rather than corrupting the model.
        A listed SDK method does not prove the desktop route is available.
        qtmodel 2.9.3 rejects several historical routes, including model-check
        snapshots, with API_NOT_OPEN; that error is preserved without a commit.

        With supporting SDK/desktop protocols, writes and commits are bound to
        the model instance checked at entry. undo_model additionally binds the
        model/history revisions and rejects pending or uncertain changes.
        Mismatch errors require model/history inspection, not automatic retries.
        Older protocols keep state checks. open_file/save_file/import_file use
        legacy raw-path payloads and cannot carry the new instance guard.

        Destructive/long-running methods (initial 清空模型, do_solve/wait_solve 求解)
        are blocked here — use initialize_model / run_analysis instead. So are methods
        that act on the MCP host or the connection rather than the bridge model
        (post_python_file, ensure_running, set_url, set_version, export_api_help,
        export_qt_helper) and prepare_model_edit, which can irreversibly delete
        results and is reserved for the host application after explicit user approval.
        （清空模型、求解等危险或长耗时操作已禁止经此调用，请用对应专用工具；
        作用于 MCP 主机或连接目标的方法，以及可能不可逆删除结果的
        prepare_model_edit 同样禁止。）

        MDB get_/query_/calc_ methods are read-only model operations, as are the
        local helpers list_parameter_section_types, build_parameter_section_*_spec
        and generate_curve_node_data, and resolve_node_selection. Other MDB methods,
        including calculate_section_property and calculate_effective_width,
        require model-write permission.
        Every MDB write is committed with update_model afterwards, as QiaoTong
        requires; project/file/view management calls (save_file, close_project,
        undo_model, update_to_pre, …) are not.
        （MDB 写方法调用后统一以 update_model 提交；工程、文件和视图管理命令除外。）

        CDB base-model snapshots also require model-write permission and one
        update_model commit: set_section_reinforcement,
        remove_section_reinforcement_by_name, set_check_stirrup,
        set_element_stirrups, set_check_material, remove_check_material,
        set_check_case, remove_check_case_snapshot and
        set_steel_bar_material_convention. Legacy CDB queries/files/solvers do not
        get an MDB commit (新快照操作基础模型；既有 CSAN 操作保留原权限和提交语义).

        New MDB management APIs are available here without additional wrapper tools.
        copy_thicknesses / remove_thicknesses accept positive integer IDs or lists,
        not range strings; remove_thicknesses([]) deletes nothing. Analysis resets
        delete settings, and arrange_thickness_ids renumbers thickness references;
        only call them when that change is intended.
        （板厚批量操作不接受区间字符串；重置会删除分析设置，整理板厚会更改编号。）

        On supporting source builds, get_mass_factor/get_stiffness_factor use
        None for all definitions and [] for none. Their update methods preserve
        omitted fields; supplying element_ids/group_names replaces the selection.
        calculate_effective_width writes generated width/factor definitions and
        is committed once. get_element_weight/get_element_weight_table and
        material weight statistics use fixed N, independent of display units.
        Merges may remove nodes/elements/associated loads; use explicit targets
        and the actual returned merged_count, not a guessed count.

        Current cdb.solve_concrete_check starts a background task and no longer
        accepts show_view/modal/auto_close/sync. Prefer run_concrete_check for
        named-case import and bounded waiting. cdb.remove_section_reinforcement
        uses sec_id/position for current CSAN data; the base-model snapshot tool
        uses remove_section_reinforcement_by_name and commits separately.

        Operation analysis: mdb.update_operation_stage_setting accepts
        transversal_load_cases on supporting builds. Pass the existing final_stage
        and ALL desired static_load_cases / sink_load_cases / live_load_cases too:
        omitted or empty lists disable their corresponding analysis, not preserve it.
        The transversal cases must already exist; None/[] disables transversal analysis.
        （运营阶段设置为整体替换：需同时提供最终阶段及所有需计算的工况列表，
        省略/空列表会关闭对应分析；transversal_load_cases 引用已建横向工况。）

        Deletion: mdb.remove_material defaults to cascade=True on qtmodel 2.9 and
        also deletes associated tendon properties and tendons; cascade=False retains
        tendon properties. mdb.remove_tendon_property defaults to cascade=False,
        refusing deletion of referenced properties; True deletes referencing tendons
        AND their loads without a dialog. With neither name nor index these methods
        delete ALL materials/properties. Discover the installed signature first and
        confirm the target and cascade scope with the user before calling.
        （删除材料默认级联删除相关钢束特性和钢束；删除钢束特性默认不级联，
        True 会无弹窗删除引用钢束及其荷载。不指定名称/编号会删除全部，调用前须确认范围。）

        Args:
            api_object: Database object (数据库对象): "mdb", "odb", "cdb"
            method: Exact method name (精确方法名), e.g. "add_spectrum_function"
            kwargs: Keyword arguments as a dict, matching the real signature
                    (与真实签名一致的关键字参数字典)

        Example:
            call_qtmodel_api("mdb", "add_tendon_group", {"name": "钢束组1"})
        """
        try:
            result = provider.call_api(api_object, method, kwargs or {})
            suffix = f"\n{json.dumps(result, ensure_ascii=False, default=str)}" if result is not None else ""
            return f"Called {api_object}.{method} successfully (调用成功){suffix}"
        except ToolError:
            raise  # 保留 ToolError/ToolInputError 的原始类型与消息
        except Exception as e:
            raise ToolError(f"Error calling {api_object}.{method} (调用失败): {e}") from e
