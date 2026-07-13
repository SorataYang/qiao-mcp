"""qtmodel API 签名契约测试。

静态解析源代码中对 qtmodel（mdb/odb/cdb）的全部调用点，
用 inspect.signature().bind() 验证参数可绑定，拦截两类回归：

1. provider 层：QtModelProvider 方法内对 self._mdb/_odb/_cdb 的直接调用
   （含 getattr(self._mdb, "name")(...) 形式）；
2. tools 层：@mcp.tool() 函数对 provider.<method>(...) 的调用，
   经 provider 方法体解析出最终落到的 qtmodel 方法后合并校验。

已知尚未修复的错配登记在 KNOWN_FAILURES（对应整改任务），
修复后必须从清单移除——若清单中的条目意外通过，测试同样失败，
防止清单腐化。
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from dataclasses import dataclass, field

import pytest
import qtmodel

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "qiao_mcp"
PROVIDER_FILE = SRC / "providers" / "qtmodel_provider.py"
TOOLS_DIR = SRC / "tools"

DB_OBJECTS = {"_mdb": qtmodel.mdb, "_odb": qtmodel.odb, "_cdb": qtmodel.cdb}

_DUMMY = object()

# ── 已知错配清单（键: "层级::位置::qt方法"）──────────────────────────
# 修复对应任务后必须删除相应条目。
KNOWN_FAILURES: dict[str, str] = {
    # 任务 1.2 附带发现：支座沉降参数名错误
    "provider::add_support_settlement::_mdb.add_node_displacement": "displacement_info 应为 load_info",
    "tools::__init__.add_support_settlement::_mdb.add_node_displacement": "同上",
    # 契约测试新发现（review 遗漏）——归入就近任务
    "provider::add_gradient_temperature::_mdb.add_gradient_temperature": "temperature_g 应为 temperature（归任务 1.4x 荷载修复）",
    "tools::__init__.add_gradient_temperature::_mdb.add_gradient_temperature": "另传了不存在的 temperature_type（真实为 section_oriental/element_type）",
    "provider::get_structure_group_elements::_odb.get_group_elements": "name 应为 group_name（归组查询修复）",
    "tools::group_management.list_group_members::_odb.get_group_elements": "同上",
    "tools::queries.get_structure_group_members::_odb.get_group_elements": "同上",
    "tools::modifications.add_to_structure_group::add_structure_to_group": "QtModelProvider 无此方法（应为 add_elements_to_structure_group）",
}


# ── AST 解析 ──────────────────────────────────────────────────────────


@dataclass
class QtCall:
    """一次对 qtmodel 数据库对象方法的调用点。"""

    db: str  # "_mdb" / "_odb" / "_cdb"
    qt_name: str
    pos_count: int = 0
    kw_names: set[str] = field(default_factory=set)
    has_star_args: bool = False
    # 转发了无法静态解析键名的 **kwargs（含转发 provider 方法自身的 **kwargs）
    has_dynamic_kwargs: bool = False
    # 转发的正是所在 provider 方法签名中的 **kwargs 参数
    forwards_own_kwargs: bool = False


@dataclass
class ProviderMethod:
    name: str
    param_names: set[str]  # 显式具名参数（不含 self/*args/**kwargs）
    has_var_kwargs: bool
    qt_calls: list[QtCall] = field(default_factory=list)


def _collect_dict_keys(func_node: ast.FunctionDef, var_name: str) -> tuple[set[str], bool]:
    """解析局部 dict 变量的静态键集合。返回 (键集合, 是否含动态成分)。"""
    keys: set[str] = set()
    dynamic = False
    for node in ast.walk(func_node):
        # kwargs = {...}
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == var_name:
                    if isinstance(node.value, ast.Dict):
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                keys.add(k.value)
                            else:
                                dynamic = True
                    else:
                        dynamic = True
        # kwargs["k"] = v
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (
                    isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == var_name
                ):
                    if isinstance(tgt.slice, ast.Constant) and isinstance(tgt.slice.value, str):
                        keys.add(tgt.slice.value)
                    else:
                        dynamic = True
        # kwargs.update(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "update"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == var_name
        ):
            dynamic = True
    return keys, dynamic


def _extract_call_args(
    call: ast.Call, func_node: ast.FunctionDef, own_kwargs_name: str | None
) -> tuple[int, set[str], bool, bool, bool]:
    """提取调用点的 (位置参数数, 关键字集合, *args, 动态**kwargs, 转发自身**kwargs)。"""
    pos_count = 0
    kw_names: set[str] = set()
    has_star_args = False
    has_dynamic = False
    forwards_own = False

    for a in call.args:
        if isinstance(a, ast.Starred):
            has_star_args = True
        else:
            pos_count += 1

    for kw in call.keywords:
        if kw.arg is not None:
            kw_names.add(kw.arg)
            continue
        # **something
        if isinstance(kw.value, ast.Name):
            if kw.value.id == own_kwargs_name:
                forwards_own = True
            else:
                keys, dynamic = _collect_dict_keys(func_node, kw.value.id)
                kw_names |= keys
                if dynamic:
                    has_dynamic = True
        else:
            has_dynamic = True
    return pos_count, kw_names, has_star_args, has_dynamic, forwards_own


def _qt_target(call: ast.Call) -> tuple[str, str] | None:
    """识别 self._mdb.foo(...) 或 getattr(self._mdb, "foo")(...)，返回 (db, 方法名)。"""
    f = call.func
    # self._mdb.foo(...)
    if (
        isinstance(f, ast.Attribute)
        and isinstance(f.value, ast.Attribute)
        and isinstance(f.value.value, ast.Name)
        and f.value.value.id == "self"
        and f.value.attr in DB_OBJECTS
    ):
        return f.value.attr, f.attr
    # getattr(self._mdb, "foo")(...)
    if (
        isinstance(f, ast.Call)
        and isinstance(f.func, ast.Name)
        and f.func.id == "getattr"
        and len(f.args) >= 2
        and isinstance(f.args[0], ast.Attribute)
        and isinstance(f.args[0].value, ast.Name)
        and f.args[0].value.id == "self"
        and f.args[0].attr in DB_OBJECTS
        and isinstance(f.args[1], ast.Constant)
        and isinstance(f.args[1].value, str)
    ):
        return f.args[0].attr, f.args[1].value
    return None


def parse_provider() -> dict[str, ProviderMethod]:
    tree = ast.parse(PROVIDER_FILE.read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "QtModelProvider"
    )
    methods: dict[str, ProviderMethod] = {}
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        arg_names = {a.arg for a in fn.args.args if a.arg != "self"}
        arg_names |= {a.arg for a in fn.args.kwonlyargs}
        own_kwargs = fn.args.kwarg.arg if fn.args.kwarg else None
        pm = ProviderMethod(fn.name, arg_names, own_kwargs is not None)
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                target = _qt_target(node)
                if target is None:
                    continue
                pos, kws, star, dyn, fwd = _extract_call_args(node, fn, own_kwargs)
                pm.qt_calls.append(
                    QtCall(target[0], target[1], pos, kws, star, dyn, fwd)
                )
        methods[fn.name] = pm
    return methods


@dataclass
class ToolCall:
    """@mcp.tool() 函数内对 provider 方法的一次调用。"""

    module: str
    tool_name: str
    provider_method: str
    pos_count: int
    kw_names: set[str]
    has_dynamic_kwargs: bool


def parse_tools() -> list[ToolCall]:
    calls: list[ToolCall] = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            is_tool = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr == "tool"
                for d in fn.decorator_list
            )
            if not is_tool:
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                if not (
                    isinstance(f, ast.Attribute)
                    and isinstance(f.value, ast.Name)
                    and f.value.id == "provider"
                ):
                    continue
                pos, kws, _star, dyn, fwd = _extract_call_args(node, fn, None)
                calls.append(
                    ToolCall(path.stem, fn.name, f.attr, pos, kws, dyn or fwd)
                )
    return calls


# ── 绑定校验 ──────────────────────────────────────────────────────────


def _bind(qt_fn, pos_count: int, kw_names: set[str], strict: bool) -> str | None:
    """尝试绑定，返回错误信息或 None。strict=False 时仅做部分绑定（存在动态成分）。"""
    sig = inspect.signature(qt_fn)
    args = [_DUMMY] * pos_count
    kwargs = {k: _DUMMY for k in kw_names}
    try:
        if strict:
            sig.bind(*args, **kwargs)
        else:
            sig.bind_partial(*args, **kwargs)
    except TypeError as e:
        return f"{e}；真实签名: {sig}"
    return None


PROVIDER_METHODS = parse_provider()
TOOL_CALLS = parse_tools()


def _provider_cases():
    for pm in PROVIDER_METHODS.values():
        for qc in pm.qt_calls:
            yield pytest.param(
                pm, qc, id=f"provider::{pm.name}::{qc.db}.{qc.qt_name}"
            )


def _tool_cases():
    for tc in TOOL_CALLS:
        yield pytest.param(tc, id=f"tools::{tc.module}.{tc.tool_name}::{tc.provider_method}")


def _check_known(key: str, error: str | None):
    """处理 KNOWN_FAILURES 清单：已知失败→xfail；已知却通过→要求移除。"""
    if key in KNOWN_FAILURES:
        if error is None:
            pytest.fail(f"{key} 已通过，请从 KNOWN_FAILURES 移除该条目")
        pytest.xfail(f"已知错配（{KNOWN_FAILURES[key]}）: {error}")
    if error is not None:
        pytest.fail(error)


# ── 测试 1：provider → qtmodel ────────────────────────────────────────


@pytest.mark.parametrize("pm,qc", list(_provider_cases()))
def test_provider_calls_bind_to_qtmodel(pm: ProviderMethod, qc: QtCall):
    key = f"provider::{pm.name}::{qc.db}.{qc.qt_name}"
    db = DB_OBJECTS[qc.db]
    qt_fn = getattr(db, qc.qt_name, None)
    if qt_fn is None:
        _check_known(key, f"qtmodel 中不存在 {qc.db}.{qc.qt_name}")
        return
    if qc.has_star_args and not qc.kw_names and qc.pos_count == 0:
        return  # 纯 *args/**kwargs 直通，静态无信息，由 tools 层校验
    strict = not (qc.has_dynamic_kwargs or qc.forwards_own_kwargs or qc.has_star_args)
    error = _bind(qt_fn, qc.pos_count, qc.kw_names, strict)
    _check_known(key, error)


# ── 测试 2：tools → provider → qtmodel ────────────────────────────────


@pytest.mark.parametrize("tc", list(_tool_cases()))
def test_tool_calls_bind_through_provider(tc: ToolCall):
    from qiao_mcp.providers.qtmodel_provider import QtModelProvider

    key = f"tools::{tc.module}.{tc.tool_name}::{tc.provider_method}"

    # (a) provider 方法必须存在，且 tool 调用能绑定其签名
    method = getattr(QtModelProvider, tc.provider_method, None)
    if method is None:
        _check_known(key, f"QtModelProvider 缺少方法 {tc.provider_method}")
        return
    sig_err = _bind(
        method,
        tc.pos_count + 1,  # +1 = self
        tc.kw_names,
        strict=False,  # provider 签名普遍含默认值，仅查参数名
    )
    if sig_err is not None:
        _check_known(key, f"tool 调用无法绑定 provider 签名: {sig_err}")
        return

    # (b) 合并 tool 关键字后校验 provider 内每个 qtmodel 调用点
    pm = PROVIDER_METHODS.get(tc.provider_method)
    if pm is None or not pm.qt_calls:
        return  # 无直接 qtmodel 调用（如 no-op / _safe_get 动态分发）
    errors = []
    for qc in pm.qt_calls:
        qkey = f"tools::{tc.module}.{tc.tool_name}::{qc.db}.{qc.qt_name}"
        db = DB_OBJECTS[qc.db]
        qt_fn = getattr(db, qc.qt_name, None)
        if qt_fn is None:
            errors.append((qkey, f"qtmodel 中不存在 {qc.db}.{qc.qt_name}"))
            continue
        merged = set(qc.kw_names)
        if qc.forwards_own_kwargs or (qc.has_star_args and not pm.param_names):
            # tool 的关键字中未被 provider 显式参数消费的部分透传给 qtmodel
            merged |= tc.kw_names - pm.param_names
        strict = not (tc.has_dynamic_kwargs or qc.has_dynamic_kwargs or qc.has_star_args)
        err = _bind(qt_fn, qc.pos_count, merged, strict)
        if err is not None:
            errors.append((qkey, err))
    if not errors:
        # 若整条链路在清单中却已通过，提示移除
        for qc in pm.qt_calls:
            qkey = f"tools::{tc.module}.{tc.tool_name}::{qc.db}.{qc.qt_name}"
            if qkey in KNOWN_FAILURES:
                pytest.fail(f"{qkey} 已通过，请从 KNOWN_FAILURES 移除该条目")
        return
    # 全部错误都已登记 → xfail；否则报出未登记部分
    unknown = [(k, e) for k, e in errors if k not in KNOWN_FAILURES]
    if unknown:
        pytest.fail("; ".join(f"[{k}] {e}" for k, e in unknown))
    pytest.xfail("; ".join(f"[{k}] 已知错配: {e}" for k, e in errors))
