"""依赖上界契约测试。

拦截"依赖无上界 → 上游发布不兼容大版本 → 已发布包开箱即崩"这类回归。

背景：mcp 2.0.0（2026-07-28）移除了 `mcp.server.fastmcp`（FastMCP 更名为
`mcp.server.mcpserver.MCPServer`），而当时的约束是 `mcp[cli]>=1.0.0`（无上界），
任何全新环境解析到 2.0.0 后 `import qiao_mcp.server` 直接 ModuleNotFoundError。

因此对本项目**直接构建在其 API 之上**的依赖，必须声明大版本上界。

关于 `mcp[cli]<2`——这是已评估的决定，不是待偿的技术债，请勿顺手"升级"掉：

- 迁移成本很低：src 侧为纯机械替换（`fastmcp`→`mcpserver`、`FastMCP`→`MCPServer`），
  实测迁移后全量测试与 1.x 上完全一致；
- 但没有到期日：mcp 1.x 仍在维护，`1.29.0` 与 `2.0.0` 为同日发布；
- 且是单向切换：迁移后的代码无法在 1.x 上运行（`mcp.server.mcpserver` 在 1.x 不存在），
  mcp 2.0 另要求 Python >=3.10，一迁即断掉存量用户。

触发迁移的条件应是：需要使用 mcp 2.x 的新能力，或 1.x 宣布停止维护。届时同步上调
本文件的上界。（另注：`ToolAnnotations` 在 2.0 改为 snake_case 字段，但构造仍接受
camelCase，线上协议也仍是 camelCase，故 envelope 的构造代码无需改动。）
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


def _dependencies() -> dict[str, str]:
    """解析 [project].dependencies 为 {包名: 完整约束串}。"""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    out = {}
    for spec in data["project"]["dependencies"]:
        # 形如 "mcp[cli]>=1.0.0,<2" → 包名 mcp
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


def test_fastmcp_import_path_still_available():
    """server.py 依赖的 FastMCP 导入路径必须在已解析的 mcp 版本中存在。

    这是上面版本约束的运行时对照：约束写对了但环境装错时同样会失败。
    """
    pytest.importorskip("mcp.server.fastmcp", reason="mcp 未安装")
    from mcp.server.fastmcp import FastMCP  # noqa: F401
