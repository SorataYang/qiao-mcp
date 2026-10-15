"""MCPServer 2.3.0 迁移基线与关键依赖上界契约。"""

from __future__ import annotations

import pathlib
import re
import tomllib

import pytest

PYPROJECT = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"

# 这些依赖的 API 被本项目直接使用，跨大版本必然破坏，必须有上界。
# 值为该依赖被直接依赖的原因，断言失败时打印，便于判断是放宽还是迁移。
MUST_HAVE_UPPER_BOUND = {
    "mcp": "全部工具注册基于 mcp.server.mcpserver.MCPServer",
    "qtmodel": "provider 直接调用 mdb/odb/cdb，次版本间已多次删除函数与改参数单位",
}

# 已完成全量测试的最低维护版本。提高基线时应同步更新锁文件并重新验证。
MUST_HAVE_TESTED_FLOOR = {
    "mcp": ">=2.3.0",
}


def _dependencies() -> dict[str, str]:
    """解析 [project].dependencies 为 {包名: 完整约束串}。"""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    out = {}
    for spec in data["project"]["dependencies"]:
        # 形如 "mcp[cli]>=2.3.0,<2.4" → 包名 mcp
        name = re.split(r"[<>=!~\[]", spec, maxsplit=1)[0].strip().lower()
        out[name] = spec
    return out


@pytest.mark.parametrize("pkg", sorted(MUST_HAVE_UPPER_BOUND))
def test_critical_dependency_has_upper_bound(pkg: str):
    """核心依赖必须声明上界，否则上游大版本发布会击穿已发布的包。"""
    deps = _dependencies()
    assert pkg in deps, f"{pkg} 不在 [project].dependencies 中"
    spec = deps[pkg]
    assert "<" in spec, (
        f"依赖 {pkg} 缺少版本上界（当前: {spec!r}）。\n"
        f"原因: {MUST_HAVE_UPPER_BOUND[pkg]}\n"
        f"请改为形如 {pkg}>=X.Y,<Z 的形式；确认已适配新大版本后再上调上界。"
    )


@pytest.mark.parametrize("pkg", sorted(MUST_HAVE_TESTED_FLOOR))
def test_critical_dependency_uses_tested_floor(pkg: str):
    """关键 SDK 的最低版本必须与已验证基线一致。"""
    deps = _dependencies()
    expected = MUST_HAVE_TESTED_FLOOR[pkg]
    assert expected in deps[pkg], (
        f"依赖 {pkg} 未使用已验证的最低版本 {expected}（当前: {deps[pkg]!r}）。\n"
        "若要调整基线，请同步刷新 uv.lock 并运行完整测试。"
    )


def test_mcpserver_import_path_available():
    """server.py 依赖的 MCPServer 导入路径必须在已解析的 mcp 版本中存在。

    这是上面版本约束的运行时对照：约束写对了但环境装错时同样会失败。
    """
    from mcp.server.mcpserver import MCPServer  # noqa: F401
