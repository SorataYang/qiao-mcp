"""结构化返回协议测试：envelope 包装的成功/失败/校验三条路径。"""

import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP

from qiao_mcp.tools.envelope import (
    ToolError,
    ToolInputError,
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
