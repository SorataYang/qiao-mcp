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
_READONLY_PREFIXES = ("get_", "list_", "find_", "calc_", "query_")
# Destructive includes overwriting existing values, not only deleting entities.
_DESTRUCTIVE_PREFIXES = ("remove_", "delete_", "update_", "renumber_")
_DESTRUCTIVE_NAMES = {
    "initialize_model",   # 清空整个模型
    "open_model_file",    # 覆盖当前模型
    "merge_nodes",        # 合并会删除重合节点
    "remove_unused_sections",
    "call_qtmodel_api",  # 长尾调用可能删除或覆盖数据
    "save_model_file",   # 保存到已有路径会覆盖文件
    "add_load_combine",  # qtmodel 明确支持覆盖既有组合
    "set_gravity",  # 总体设置 API 同时下发元数据/基准温度默认值，不能保证保留原值
    "create_material",  # SDK 明确支持同名覆盖
    "create_section",  # SDK add_section 可覆盖已有截面编号
    "create_polygon_section",
    "create_line_width_section",
    "create_section_from_properties",
    "create_tendon_2d",  # SDK 同名覆盖
    "add_tendon_3d",
    "calculate_section_property",  # 重写全部已有截面特性
    "set_support",  # 可替换约束并清空附加参数
    "set_self_weight_stage",  # 重写既有结构组的自重阶段
    "move_nodes",  # 修改已有节点坐标
    "revert_local_orientation",  # 修改已有单元方向
    "merge_operation_stage",  # 重组已有施工阶段
    "configure_analysis",  # 覆盖分析开关
    "configure_check_analysis",  # 修改检算设置
    "manage_check_stirrup",  # 可删除箍筋定义
    "assign_element_stirrup",  # 可删除所有单元箍筋
    "manage_check_case_file",  # 可替换当前检算工况或覆盖文件
    "configure_live_load_system",  # 显式允许时可清理旧体系定义
    "configure_operation_stage",  # 完整替换各类运营工况选择
    "set_transversal_vehicle",  # 按同名或编号完整覆盖
    "set_transversal_lane",
    "set_transversal_case",
    "set_international_vehicle",
    "create_en1991_vehicle",
    "set_planned_lane",
    "set_international_live_load_case",
    "set_section_reinforcement",
    "set_check_stirrup_snapshot",
    "set_element_stirrups",
    "manage_check_material",
    "manage_check_case_definition",
}
# 逃生舱：可调用任意 qtmodel 方法，对外部世界开放
_OPEN_WORLD_NAMES = {"call_qtmodel_api"}

_CONNECTION_NAMES = {
    "check_qiaotong_connection",
    "get_model_status",
    "get_model_edit_readiness",
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
    "configure_operation_stage",
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
_MODEL_WRITE_NAMES = {
    "set_international_vehicle", "create_en1991_vehicle",
    "set_planned_lane", "set_international_live_load_case",
    "set_section_reinforcement", "remove_section_reinforcement",
    "set_check_stirrup_snapshot", "set_element_stirrups",
    "manage_check_material", "manage_check_case_definition",
}


def _operation_for(name: str) -> str:
    """Map every MCP tool to the bridge capability it requires."""
    if name in _CONNECTION_NAMES:
        return "connection"
    if name in _LIFECYCLE_NAMES:
        return "lifecycle"
    if name in _MODEL_WRITE_NAMES:
        return "model_write"
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


# 后端"写命令已发出、结果未收到"的异常类名。qtmodel 2.9 起写命令遇断连、读超时
# 或 504 时抛 CommandOutcomeUnknownError 且不再自动重发（2.8.2 会重发一次，可能
# 重复写入）。按类名识别，envelope 不必导入具体后端。
_OUTCOME_UNKNOWN_ERRORS = frozenset({"CommandOutcomeUnknownError"})


def _outcome_unknown(error: BaseException) -> bool:
    """Whether a lost-reply write error appears anywhere in the exception chain.

    工具普遍以 ``raise ToolError(...) from e`` 包装后端异常，故沿
    __cause__/__context__ 链查找，而不只看最外层。
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        if type(current).__name__ in _OUTCOME_UNKNOWN_ERRORS:
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _outcome_unknown_error(error: BaseException) -> ToolError:
    return ToolError(
        f"{error} — OUTCOME UNKNOWN: the command was sent but its reply was lost, so "
        "the model may or may not have changed. Do NOT retry automatically: read the "
        "affected objects back (or call get_model_status) and let the user decide. "
        "(写命令已发出但未收到结果，模型可能已改也可能未改；切勿自动重试，"
        "先回读相关对象或调用 get_model_status，再由用户决定。)"
    )


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


def _compact_description(fn: Callable, sig: inspect.Signature) -> str | None:
    """Remove only an Args block that is fully represented in the input schema.

    Keep the original docstring for _describe_params. Unknown, duplicate or
    undocumented parameters and ambiguous layouts fall back to the full text.
    Returns/Examples/Notes and bilingual continuation text remain discoverable.
    """
    doc = inspect.getdoc(fn)
    if not doc:
        return None
    lines = doc.splitlines()
    headers = [i for i, line in enumerate(lines) if line.strip() in _ARG_HEADERS]
    if len(headers) != 1:
        return None
    start = headers[0]
    header_indent = len(lines[start]) - len(lines[start].lstrip())
    names = {
        p.name for p in sig.parameters.values()
        if not _is_context_annotation(p.annotation)
    }
    descriptions = _parse_arg_descriptions(doc)
    if not names or set(descriptions) != names:
        return None

    arg_indent: int | None = None
    seen: set[str] = set()
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= header_indent or _DOC_SECTION_RE.match(line.strip()):
            end = i
            break
        match = _DOC_ARG_RE.match(line)
        if arg_indent is None:
            if not match:
                return None
            arg_indent = indent
        if indent < arg_indent:
            return None
        if match and indent == arg_indent:
            name = match.group(2)
            if name not in descriptions or name in seen:
                return None
            seen.add(name)
    if seen != names:
        return None
    # Do not remove the whole description of a tool documented only by Args.
    compact = "\n\n".join(
        part for part in ("\n".join(lines[:start]).rstrip(), "\n".join(lines[end:]).strip())
        if part
    )
    return compact or None


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
            try:
                return _normalize(await fn(*args, **kwargs))
            except Exception as e:
                if not _outcome_unknown(e):
                    raise
                raise _outcome_unknown_error(e) from e

    else:

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ensure_allowed()
            try:
                return _normalize(fn(*args, **kwargs))
            except Exception as e:
                if not _outcome_unknown(e):
                    raise
                raise _outcome_unknown_error(e) from e

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
            options = dict(t_kwargs)
            if "annotations" not in options:
                options["annotations"] = _annotations_for(name)
            wrapped = _wrap(fn, provider, _operation_for(name))
            if not t_args and "description" not in options:
                description = _compact_description(fn, inspect.signature(wrapped))
                if description is not None:
                    options["description"] = description
            decorator = original_tool(*t_args, **options)
            return decorator(wrapped)

        return apply

    mcp.tool = patched_tool
    try:
        register_fn(mcp, provider)
    finally:
        mcp.tool = original_tool
