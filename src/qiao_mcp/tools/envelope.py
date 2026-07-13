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
from typing import Any, Callable

from mcp.server.fastmcp.exceptions import ToolError


class ToolInputError(ToolError):
    """Invalid tool input (无效的工具输入/参数)。语义上区别于后端执行失败。"""


def _wrap(fn: Callable) -> Callable:
    """Preserve the tool signature; normalize the return to structured content.

    - dict 原样返回（结构化）；
    - str 包裹为 {"status": "success", "message": str}；
    - None 视为无返回值的成功；
    - 异常向上抛出，由 FastMCP 转为 ToolError 响应。
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            result.setdefault("status", "success")
            return result
        if result is None:
            return {"status": "success"}
        return {"status": "success", "message": result}

    # 覆盖返回注解为 dict，让 FastMCP 生成结构化输出；参数签名保持不变。
    wrapper.__signature__ = sig.replace(return_annotation=dict)
    annotations = dict(getattr(fn, "__annotations__", {}))
    annotations["return"] = dict
    wrapper.__annotations__ = annotations
    # 断开 functools.wraps 设置的 __wrapped__，否则 inspect 会回溯到原函数注解。
    if hasattr(wrapper, "__wrapped__"):
        del wrapper.__wrapped__
    return wrapper


def register_tools_with_envelope(mcp, register_fn, provider) -> None:
    """Call a register_* function with mcp.tool patched to wrap every tool.

    register_fn 内部照常使用 @mcp.tool()，但每个工具函数都会先经 _wrap 包装，
    从而统一获得结构化成功返回与 ToolError 失败通道。
    """
    original_tool = mcp.tool

    def patched_tool(*t_args: Any, **t_kwargs: Any):
        decorator = original_tool(*t_args, **t_kwargs)

        def apply(fn: Callable):
            return decorator(_wrap(fn))

        return apply

    mcp.tool = patched_tool
    try:
        register_fn(mcp, provider)
    finally:
        mcp.tool = original_tool
