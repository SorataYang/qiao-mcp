"""依赖上界契约测试。

拦截"依赖无上界 → 上游发布不兼容大版本 → 已发布包开箱即崩"这类回归。

背景：mcp 2.0.0（2026-07-28）移除了 `mcp.server.fastmcp`（FastMCP 更名为
`mcp.server.mcpserver.MCPServer`），而当时的约束是 `mcp[cli]>=1.0.0`（无上界），
任何全新环境解析到 2.0.0 后 `import qiao_mcp.server` 直接 ModuleNotFoundError。

因此对本项目**直接构建在其 API 之上**的依赖，必须声明大版本上界。

关于 `mcp[cli]>=1.29,<2`——这是已评估的兼容策略，请勿只修改版本号：

- 1.29.0 是与 2.0.0 同日发布的 1.x 维护版本，包含本项目使用的
  `Context.report_progress()` 路由修复；
- 2.0 的装饰器 API 基本不变，但需要迁移模块/类名、snake_case 模型字段和
  `call_tool()` 返回结构；
- 更重要的是，2.0 会在线程池并发执行同步 handler。本项目的工具共享同一个有状态
  QtModelProvider，升级前必须验证或约束模型读写的并发语义；
- 本项目已经要求 Python >=3.11，因此 2.0 的 Python >=3.10 要求不是迁移障碍。

触发迁移的条件应是：需要使用 mcp 2.x 的新能力，或项目完成真实 QtModel 环境下的
并发与客户端兼容验证。届时同步上调本文件的上界。（另注：`ToolAnnotations` 在 2.0
改为 snake_case 字段，但构造仍接受 camelCase，线上协议也仍是 camelCase。）
"""

from __future__ import annotations

import pathlib
import re
import tomllib

import pytest

PYPROJECT = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"

# 这些依赖的 API 被本项目直接使用，跨大版本必然破坏，必须有上界。
# 值为该依赖被直接依赖的原因，断言失败时打印，便于判断是放宽还是迁移。
MUST_HAVE_UPPER_BOUND = {
    "mcp": "全部工具注册基于 mcp.server.fastmcp.FastMCP，2.0 已移除该模块",
    "qtmodel": "provider 直接调用 mdb/odb/cdb，次版本间已多次删除函数与改参数单位",
}

# 已完成全量测试的最低维护版本。提高基线时应同步更新锁文件并重新验证。
MUST_HAVE_TESTED_FLOOR = {
    "mcp": ">=1.29",
}


def _dependencies() -> dict[str, str]:
    """解析 [project].dependencies 为 {包名: 完整约束串}。"""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    out = {}
    for spec in data["project"]["dependencies"]:
        # 形如 "mcp[cli]>=1.29,<2" → 包名 mcp
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


def test_fastmcp_import_path_still_available():
    """server.py 依赖的 FastMCP 导入路径必须在已解析的 mcp 版本中存在。

    这是上面版本约束的运行时对照：约束写对了但环境装错时同样会失败。
    """
    pytest.importorskip("mcp.server.fastmcp", reason="mcp 未安装")
    from mcp.server.fastmcp import FastMCP  # noqa: F401
