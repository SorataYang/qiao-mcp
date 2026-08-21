"""
MCP escape-hatch tool — controlled access to the full qtmodel API.
逃生舱工具：受控访问 qtmodel 全量 API

The curated tools cover common bridge workflows. For the long tail of
qtmodel's 240+ mdb / 90+ odb / 60+ cdb methods, this gateway exposes a
single discover-then-call surface instead of one wrapper tool per method.
"""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from qiao_mcp.providers import BridgeProvider
from qiao_mcp.tools.envelope import ToolError


def register_api_gateway_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register the qtmodel API discovery + call gateway."""

    @mcp.tool()
    def check_qiaotong_connection() -> str:
        """
        Diagnose the connection to QiaoTong software (诊断桥通软件连接状态).

        CALL THIS FIRST when any tool reports the backend is unavailable.
        It distinguishes the three failure modes, which need different fixes:
        （任一工具报后端不可用时先调用本工具，它区分三种需要不同处置的状态）

        - connected (已连接): ready to model.
        - version_mismatch (版本不匹配): the QiaoTong API version and the
          installed qtmodel differ. qtmodel pins an exact version, so the
          user must upgrade QiaoTong (or install a matching qtmodel).
          （桥通与 qtmodel 版本必须精确一致，需升级桥通软件）
        - software_not_running (软件未启动): start QiaoTong and wait for the
          main window, then retry. （启动桥通并等待主界面加载）

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

        return "\n".join(lines)

    @mcp.tool()
    def get_model_status() -> dict[str, Any]:
        """Get QiaoTong's current model lifecycle and operation capabilities.

        获取桥通当前是否打开模型、前处理/求解/后处理阶段、当前显示阶段是否
        为基本阶段、是否存在结果，以及 MCP 当前可执行的读模型、改模型、
        修改施工阶段、结果查询、分析和视图操作能力。

        Call this before starting a model workflow and whenever an operation is
        rejected. This tool only observes state; it never switches stages,
        deletes results, or changes the model.
        """
        try:
            return provider.get_model_state()
        except Exception as e:
            raise ToolError(f"Error checking model status (模型状态查询失败): {e}") from e

    @mcp.tool()
    def list_qtmodel_api(api_object: str, pattern: str = "") -> str:
        """
        Discover qtmodel API methods and their real signatures (检索 qtmodel API 方法及签名).

        Use this to find long-tail methods NOT covered by the curated tools,
        then invoke them with call_qtmodel_api. ALWAYS discover the real
        signature here before calling — do not guess parameter names.
        （先用本工具查到真实签名，再用 call_qtmodel_api 调用，切勿臆测参数名。）

        Args:
            api_object: Which database to inspect (数据库对象):
                "mdb" (建模), "odb" (结果/查询), "cdb" (检算)
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
        api_object: str,
        method: str,
        kwargs: dict[str, Any] | None = None,
    ) -> str:
        """
        Call a qtmodel API method not covered by a curated tool (调用 qtmodel 长尾 API).

        ESCAPE HATCH — prefer a dedicated tool when one exists. Discover the
        real signature with list_qtmodel_api first. Arguments are validated
        against the real signature before dispatch, so a wrong parameter name
        fails fast with the correct signature rather than corrupting the model.

        Destructive/long-running methods (initial 清空模型, do_solve 求解) are
        blocked here — use initialize_model / run_analysis instead.
        （清空模型、求解等危险或长耗时操作已禁止经此调用，请用对应专用工具。）

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
