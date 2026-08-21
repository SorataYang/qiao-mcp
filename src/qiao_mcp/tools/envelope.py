"""工具返回协议与注册包装。

统一约定（供全部 @mcp.tool() 使用）：
- 成功：返回 dict（结构化内容），或返回 str（自动包裹为 {status, message}）；
- 失败：raise ToolError(...)（经 FastMCP 变为 isError 响应，客户端可识别）；
- 校验拒绝：raise ToolInputError(...)，语义同 ToolError，但便于区分"用户/LLM
  输入不合法"与"后端执行失败"。

register_tools_with_envelope 在 mcp.tool 注册入口统一包装，
使各工具函数体只需专注 return dict / raise，无需自行拼接 "Error: ..." 字符串。
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations


class ToolInputError(ToolError):
    """Invalid tool input (无效的工具输入/参数)。语义上区别于后端执行失败。"""


# 只读工具前缀：不改变模型状态，可安全重复调用
_READONLY_PREFIXES = ("get_", "list_", "find_", "calc_", "calculate_")
# 破坏性工具前缀/名称：删除或清空模型数据
_DESTRUCTIVE_PREFIXES = ("remove_", "delete_")
_DESTRUCTIVE_NAMES = {
    "initialize_model",   # 清空整个模型
    "open_model_file",    # 覆盖当前模型
    "merge_nodes",        # 合并会删除重合节点
    "remove_unused_sections",
}
# 逃生舱：可调用任意 qtmodel 方法，对外部世界开放
_OPEN_WORLD_NAMES = {"call_qtmodel_api"}

_CONNECTION_NAMES = {
    "check_qiaotong_connection",
    "get_model_status",
    "list_qtmodel_api",
    "call_qtmodel_api",  # 具体 mdb/odb/cdb 权限由 provider.call_api 再判断
}
_LIFECYCLE_NAMES = {"initialize_model", "open_model_file"}
_STAGE_WRITE_NAMES = {
    "add_construction_stage",
    "merge_operation_stage",
    "remove_construction_stage",
    "update_construction_stage",
    "set_self_weight_stage",
    "configure_analysis",
}
_RESULT_NAMES = {
    "get_analysis_results",
    "plot_analysis_result",
    "get_special_results",
    "get_live_load_results",
}
_VIEW_NAMES = {
    "switch_display_stage",
    "set_view_angle",
    "save_model_screenshot",
    "activate_structure",
    "set_render",
    "reset_display",
    "set_unit",
    "change_construct_stage",
}
_CHECK_READ_NAMES = {
    "get_check_data",
}
_CHECK_RUN_NAMES = {
    "run_concrete_check",
}


def _operation_for(name: str) -> str:
    """Map every MCP tool to the bridge capability it requires."""
    if name in _CONNECTION_NAMES:
        return "connection"
    if name in _LIFECYCLE_NAMES:
        return "lifecycle"
    if name == "run_analysis":
        return "analysis_run"
    if name in _CHECK_RUN_NAMES:
        return "check_run"
    if name in _CHECK_READ_NAMES:
        return "check_read"
    if name in _STAGE_WRITE_NAMES:
        return "stage_write"
    if name in _RESULT_NAMES:
        return "result_read"
    if any(token in name for token in ("result", "results")):
        return "result_read"
    if any(token in name for token in ("check", "stirrup", "reinforcement")):
        return "check_write"
    if name in _VIEW_NAMES or name.startswith(("plot_", "display_", "set_view_")):
        return "view"
    if name == "save_model_file":
        return "model_read"
    if name.startswith(_READONLY_PREFIXES) or name == "validate_model":
        return "model_read"
    return "model_write"


def _annotations_for(name: str) -> ToolAnnotations:
    """Classify a tool by name into read-only / destructive / open-world hints."""
    is_readonly = name.startswith(_READONLY_PREFIXES) or name == "validate_model"
    is_destructive = name.startswith(_DESTRUCTIVE_PREFIXES) or name in _DESTRUCTIVE_NAMES
    return ToolAnnotations(
        readOnlyHint=is_readonly,
        destructiveHint=is_destructive,
        # 大多数写工具重复调用会累积状态；只读工具天然幂等
        idempotentHint=is_readonly,
        openWorldHint=name in _OPEN_WORLD_NAMES,
    )


def _normalize(result: Any) -> Any:
    """Normalize a tool return value to structured content."""
    if isinstance(result, dict):
        result.setdefault("status", "success")
        return result
    if result is None:
        return {"status": "success"}
    if isinstance(result, str):
        return {"status": "success", "message": result}
    # 其它类型（如 MCP Image / 富内容对象）原样透传，交由 FastMCP 序列化
    return result


def _wrap(fn: Callable, provider: Any = None, operation: str = "connection") -> Callable:
    """Preserve the tool signature; normalize the return to structured content.

    - dict 原样返回（结构化）；
    - str 包裹为 {"status": "success", "message": str}；
    - None 视为无返回值的成功；
    - 异常向上抛出，由 FastMCP 转为 ToolError 响应。

    同时支持同步与异步（async def）工具函数。
    """
    sig = inspect.signature(fn)

    def ensure_allowed() -> None:
        if provider is None:
            return
        guard = getattr(provider, "ensure_operation_allowed", None)
        if guard is None:
            return
        try:
            guard(operation)
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"Operation blocked by QiaoTong state (桥通状态禁止操作): {e}") from e

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            ensure_allowed()
            return _normalize(await fn(*args, **kwargs))

    else:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ensure_allowed()
            return _normalize(fn(*args, **kwargs))

    # 覆盖返回注解为 dict，让 FastMCP 生成结构化输出；参数签名保持不变。
    wrapper.__signature__ = sig.replace(return_annotation=dict)  # type: ignore[attr-defined]
    annotations = dict(getattr(fn, "__annotations__", {}))
    annotations["return"] = dict
    wrapper.__annotations__ = annotations
    # 断开 functools.wraps 设置的 __wrapped__，否则 inspect 会回溯到原函数注解。
    if hasattr(wrapper, "__wrapped__"):
        del wrapper.__wrapped__
    return wrapper


def register_tools_with_envelope(mcp, register_fn, provider) -> None:
    """Call a register_* function with mcp.tool patched to wrap every tool.

    register_fn 内部照常使用 @mcp.tool()，但每个工具都会：
    1. 经 _wrap 统一获得结构化成功返回与 ToolError 失败通道；
    2. 按工具名自动附加 ToolAnnotations（只读/破坏性/开放世界提示），
       使客户端可据此做权限分级与确认提示。
    显式传入的 annotations / name 会被尊重（不覆盖）。
    """
    original_tool = mcp.tool

    def patched_tool(*t_args: Any, **t_kwargs: Any):
        def apply(fn: Callable):
            name = t_kwargs.get("name") or fn.__name__
            if "annotations" not in t_kwargs:
                t_kwargs["annotations"] = _annotations_for(name)
            decorator = original_tool(*t_args, **t_kwargs)
            return decorator(_wrap(fn, provider, _operation_for(name)))

        return apply

    mcp.tool = patched_tool
    try:
        register_fn(mcp, provider)
    finally:
        mcp.tool = original_tool
