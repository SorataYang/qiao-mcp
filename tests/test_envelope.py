"""结构化返回协议测试：envelope 包装的成功/失败/校验三条路径。"""

import asyncio
import json

import pytest
from mcp.server.fastmcp import Context, FastMCP

from qiao_mcp.tools.envelope import (
    ToolError,
    ToolInputError,
    _parse_arg_descriptions,
    register_tools_with_envelope,
)


def _call_json(mcp, name, args):
    """调用工具并把返回的 JSON 文本解析为 dict。"""
    result = asyncio.run(mcp.call_tool(name, args))
    # 结构化输出可用时返回 (content, structured)；否则返回 content 列表
    if isinstance(result, tuple):
        return result[1]
    text = result[0].text
    return json.loads(text)


def _register_sample(mcp, provider):
    @mcp.tool()
    def make_thing(name: str, count: int = 3) -> str:
        return f"made {count} {name}"

    @mcp.tool()
    def structured(name: str) -> dict:
        return {"created": name, "id": 7}

    @mcp.tool()
    def bad_input(x: int) -> str:
        if x < 0:
            raise ToolInputError("x must be >= 0 (x 需非负)")
        return "ok"

    @mcp.tool()
    def backend_fails() -> str:
        raise RuntimeError("后端炸了")


@pytest.fixture
def mcp():
    m = FastMCP("test")
    register_tools_with_envelope(m, _register_sample, provider=None)
    return m


def test_signature_preserved_after_wrapping(mcp):
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    props = tools["make_thing"].inputSchema["properties"]
    assert set(props) == {"name", "count"}, "包装后参数签名必须保持不变"
    assert tools["make_thing"].inputSchema["required"] == ["name"]


def test_string_return_wrapped_as_structured_success(mcp):
    assert _call_json(mcp, "make_thing", {"name": "X", "count": 2}) == {
        "status": "success",
        "message": "made 2 X",
    }


def test_dict_return_gets_status_success(mcp):
    assert _call_json(mcp, "structured", {"name": "梁"}) == {
        "status": "success",
        "created": "梁",
        "id": 7,
    }


def test_backend_failure_becomes_tool_error(mcp):
    with pytest.raises(ToolError) as exc:
        asyncio.run(mcp.call_tool("backend_fails", {}))
    assert "后端炸了" in str(exc.value)


def test_input_error_becomes_tool_error(mcp):
    with pytest.raises(ToolError) as exc:
        asyncio.run(mcp.call_tool("bad_input", {"x": -1}))
    assert "x must be >= 0" in str(exc.value)


def test_tool_input_error_is_tool_error_subclass():
    assert issubclass(ToolInputError, ToolError)


# ── docstring Args → schema 参数描述注入 ──────────────────────────────────
# FastMCP 不解析 docstring；envelope 在包装处把 Args 说明注入参数 schema。
# 这些测试锁住该行为（Glama 等目录站的"工具定义质量"评分依赖参数 description）。

_DOC_BILINGUAL = (
    "\n"
    "    Create nodes (创建节点).\n"
    "\n"
    "    Args:\n"
    "        node_data: List of coords. Format: [[x,y,z], ...]\n"
    "                   节点坐标列表\n"
    "        merge_error: Merge tolerance, default 1e-3 (合并容差)\n"
    "    "
)

_DOC_NESTED = (
    "\n"
    "    Configure (配置).\n"
    "\n"
    "    Args:\n"
    "        kind: Setting group (设置类别):\n"
    '            "limit_state" (极限状态法):\n'
    "                cal_fatigue, fatigue_limit_steel_bar (MPa),\n"
    "                is_consider_construction_load\n"
    "        settings: Parameter dict; only pass changed keys (参数字典)\n"
    "\n"
    "    Returns:\n"
    "        A summary string.\n"
    "    "
)


def test_parse_single_and_multiline_bilingual():
    d = _parse_arg_descriptions(_DOC_BILINGUAL)
    assert set(d) == {"node_data", "merge_error"}
    assert d["node_data"].startswith("List of coords")
    assert "节点坐标列表" in d["node_data"]  # 对齐续行并入同一参数
    assert "1e-3" in d["merge_error"]


def test_parse_ignores_nested_fields_and_stops_at_returns():
    d = _parse_arg_descriptions(_DOC_NESTED)
    assert set(d) == {"kind", "settings"}  # 嵌套字段行、Returns 段都不算参数
    assert "cal_fatigue" in d["kind"]  # 深缩进的嵌套清单并入 kind 说明
    assert "fatigue_limit_steel_bar" in d["kind"]
    assert "summary" not in "".join(d.values())  # Returns 段被排除


def test_parse_no_args_section_returns_empty():
    assert _parse_arg_descriptions("Just a one-line summary, no Args.") == {}
    assert _parse_arg_descriptions(None) == {}
    assert _parse_arg_descriptions("") == {}


def _register_documented(mcp, provider):
    @mcp.tool()
    def documented(node_data: list, merge_error: float = 1e-3) -> str:
        """Create nodes (创建节点).

        Args:
            node_data: List of node coordinates (节点坐标列表)
            merge_error: Merge tolerance in model units (合并容差)
        """
        return "ok"


def test_docstring_descriptions_injected_into_schema():
    m = FastMCP("test")
    register_tools_with_envelope(m, _register_documented, provider=None)
    tool = {t.name: t for t in asyncio.run(m.list_tools())}["documented"]
    props = tool.inputSchema["properties"]
    assert set(props) == {"node_data", "merge_error"}
    assert "节点坐标列表" in props["node_data"]["description"]
    assert "合并容差" in props["merge_error"]["description"]
    # 注入描述不得破坏必填/默认语义
    assert tool.inputSchema["required"] == ["node_data"]


def _register_with_context(mcp, provider):
    @mcp.tool()
    async def with_ctx(ctx: Context, read_timeout: int = 60) -> str:
        """Run something long (运行).

        Args:
            read_timeout: Max total seconds (求解总时限秒数)
        """
        return "done"


def test_context_param_excluded_but_others_described():
    m = FastMCP("test")
    register_tools_with_envelope(m, _register_with_context, provider=None)
    tool = {t.name: t for t in asyncio.run(m.list_tools())}["with_ctx"]
    props = tool.inputSchema["properties"]
    assert "ctx" not in props  # Context 注入参数不进 schema，注解须保持原样
    assert "求解总时限秒数" in props["read_timeout"]["description"]
