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
from qiao_mcp.tools.envelope import ToolError, ToolInputError


def register_api_gateway_tools(mcp: FastMCP, provider: BridgeProvider) -> None:
    """Register the qtmodel API discovery + call gateway."""

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
