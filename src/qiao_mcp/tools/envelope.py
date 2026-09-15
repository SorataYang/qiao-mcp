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
import re
import textwrap
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from qiao_mcp.tools.schemas import MessageResult, ObjectResult


class ToolInputError(ToolError):
    """Invalid tool input (无效的工具输入/参数)。语义上区别于后端执行失败。"""


# 只读工具前缀：不改变模型状态，可安全重复调用
_READONLY_PREFIXES = ("get_", "list_", "find_", "calc_")
# 破坏性工具前缀/名称：删除或清空模型数据
_DESTRUCTIVE_PREFIXES = ("remove_", "delete_")
_DESTRUCTIVE_NAMES = {
    "initialize_model",   # 清空整个模型
    "open_model_file",    # 覆盖当前模型
    "merge_nodes",        # 合并会删除重合节点
    "remove_unused_sections",
    "call_qtmodel_api",  # 长尾调用可能删除或覆盖数据
    "save_model_file",   # 保存到已有路径会覆盖文件
    "add_load_combine",  # qtmodel 明确支持覆盖既有组合
    "manage_check_stirrup",  # 可删除箍筋定义
    "assign_element_stirrup",  # 可删除所有单元箍筋
    "manage_check_case_file",  # 可替换当前检算工况或覆盖文件
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
    is_readonly = name.startswith(_READONLY_PREFIXES) or name in {
        "validate_model", "check_qiaotong_connection",
    }
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
    if isinstance(result, BaseModel):
        result = result.model_dump(mode="json", exclude_unset=True)
    if isinstance(result, dict):
        return {"status": "success", **result}
    if result is None:
        return {"status": "success"}
    if isinstance(result, str):
        return {"status": "success", "message": result}
    # 其它类型（如 MCP Image / 富内容对象）原样透传，交由 FastMCP 序列化
    return result


# ── docstring Args → JSON Schema 参数描述 ────────────────────────────────
# FastMCP 只从函数签名(类型注解 + Annotated 内的 Field)生成参数 schema，不解析
# docstring。本项目各工具的参数说明都写在 Google 风格 docstring 的 Args 段里；
# 若不回填到 schema，目录站(如 Glama)的"工具定义质量"评分会因参数 description
# 覆盖率为 0 而偏低，客户端 LLM 也读不到参数级说明。这里在注册包装处解析
# docstring 并注入 Annotated[..., Field(description=...)]，使 docstring 保持唯一
# 事实源、工具文件零改动、后续新增工具自动生效。

_ARG_HEADERS = frozenset({"Args:", "Arguments:", "Parameters:"})
_DOC_SECTION_RE = re.compile(
    r"^(?:Args|Arguments|Parameters|Returns?|Raises?|Yields?"
    r"|Examples?|Notes?|Warnings?|See Also|References?)\s*:\s*$"
)
_DOC_ARG_RE = re.compile(r"^(\s*)([A-Za-z_]\w*)\s*(?:\([^)]*\))?\s*:\s?(.*)$")


def _parse_arg_descriptions(doc: str | None) -> dict[str, str]:
    """解析 Google 风格 docstring 的 Args 段，返回 {参数名: 说明}。

    - 首个参数行的缩进确定"参数级"，此后仅同级 ``name:`` 行视为新参数，更深
      缩进的行(含 kind 那种嵌套字段清单)并入上一个参数的说明；
    - 遇到更浅缩进或其它段头(Returns/Example…)即结束；
    - 无 Args 段或无 docstring 时返回空 dict(该工具不注入，保持原样)。
    """
    if not doc:
        return {}
    lines = doc.splitlines()
    start: int | None = None
    header_indent = 0
    for idx, line in enumerate(lines):
        if line.strip() in _ARG_HEADERS:
            start, header_indent = idx + 1, len(line) - len(line.lstrip())
            break
    if start is None:
        return {}

    result: dict[str, str] = {}
    arg_indent: int | None = None
    name: str | None = None
    first = ""
    cont: list[str] = []

    def flush() -> None:
        nonlocal name, first, cont
        if name is not None:
            block = textwrap.dedent("\n".join(cont)).strip("\n") if cont else ""
            desc = "\n".join(p for p in (first.rstrip(), block) if p).strip()
            if desc:
                result[name] = desc
        name, first, cont = None, "", []

    for line in lines[start:]:
        if not line.strip():  # 空行：并入当前参数(尾部空行最终会被 strip 掉)
            if name is not None:
                cont.append("")
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= header_indent:  # 退回 Args 同级或更浅 → 段结束
            break
        if _DOC_SECTION_RE.match(line.strip()):  # 新段头(Returns/Example…)
            break
        m = _DOC_ARG_RE.match(line)
        if m and (arg_indent is None or len(m.group(1)) == arg_indent):
            arg_indent = len(m.group(1))  # 首个参数行确定参数级缩进
            flush()
            name, first, cont = m.group(2), m.group(3), []
        elif name is not None:  # 更深缩进/非参数行 → 上一个参数的续行
            cont.append(line)
    flush()
    return result


def _is_context_annotation(annotation: Any) -> bool:
    """FastMCP 注入的 Context 参数必须保持原注解(它不进 schema)。"""
    return isinstance(annotation, type) and issubclass(annotation, Context)


def _describe_params(fn: Callable, sig: inspect.Signature) -> inspect.Signature:
    """把 docstring Args 的说明注入签名各形参的 Annotated Field(description=...)。

    仅处理在 Args 中有说明、且非 Context 注入参数的形参；无可注入项时原样返回。
    """
    descriptions = _parse_arg_descriptions(getattr(fn, "__doc__", None))
    if not descriptions:
        return sig
    new_params = []
    changed = False
    for param in sig.parameters.values():
        desc = descriptions.get(param.name)
        if not desc or _is_context_annotation(param.annotation):
            new_params.append(param)
            continue
        base = (
            param.annotation
            if param.annotation is not inspect.Parameter.empty
            else Any
        )
        new_params.append(
            param.replace(annotation=Annotated[base, Field(description=desc)])
        )
        changed = True
    return sig.replace(parameters=new_params) if changed else sig


def _wrap(fn: Callable, provider: Any = None, operation: str = "connection") -> Callable:
    """Preserve the tool signature; normalize the return to structured content.

    - dict 原样返回（结构化）；
    - str 包裹为 {"status": "success", "message": str}；
    - None 视为无返回值的成功；
    - 异常向上抛出，由 FastMCP 转为 ToolError 响应。

    同时支持同步与异步（async def）工具函数。
    """
    try:
        # eval_str=True：即便某工具模块启用 from __future__ import annotations
        # 也能拿到真实类型对象(当前无一启用，此处为面向未来的稳妥写法)。
        sig = inspect.signature(fn, eval_str=True)
    except Exception:
        sig = inspect.signature(fn)
    sig = _describe_params(fn, sig)

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

    # Bare dict has no output schema in FastMCP 1.29. Preserve explicit response
    # models, and describe normalized text/dict envelopes with concrete models.
    original_return = sig.return_annotation
    if isinstance(original_return, type) and issubclass(original_return, BaseModel):
        output_type = original_return
    elif original_return is str:
        output_type = MessageResult
    else:
        output_type = ObjectResult
    wrapper.__signature__ = sig.replace(return_annotation=output_type)  # type: ignore[attr-defined]
    annotations = dict(getattr(fn, "__annotations__", {}))
    annotations["return"] = output_type
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
