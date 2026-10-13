"""结构化返回协议测试：envelope 包装的成功/失败/校验三条路径。"""

import asyncio
import json
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import Context, FastMCP

from qiao_mcp.tools.catalog import register_tool_catalog
from qiao_mcp.tools.envelope import (
    ToolError,
    ToolInputError,
    _parse_arg_descriptions,
    register_tools_with_envelope,
)


def _call_json(mcp, name, args):
    """Require actual structured output, not merely JSON encoded inside text."""
    result = asyncio.run(mcp.call_tool(name, args))
    assert isinstance(result, tuple), "FastMCP must produce structuredContent"
    assert json.loads(result[0][0].text) == result[1]
    return result[1]


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

    @mcp.tool()
    def reply_lost() -> str:
        # 与工具的惯用写法一致：后端异常被包成 ToolError 再抛出
        try:
            raise CommandOutcomeUnknownError("命令 ADD-NODE 的执行结果未知")
        except Exception as e:
            raise ToolError(f"Error creating nodes: {e}") from e


class CommandOutcomeUnknownError(RuntimeError):
    """与 qtmodel 2.9 同名的替身；envelope 按类名识别，不导入后端。"""


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
    assert "OUTCOME UNKNOWN" not in str(exc.value)


def test_lost_write_reply_warns_against_retry(mcp):
    """写命令结果未知时必须明确要求先回读、不得自动重试。"""
    with pytest.raises(ToolError) as exc:
        asyncio.run(mcp.call_tool("reply_lost", {}))
    msg = str(exc.value)
    assert "Error creating nodes" in msg and "ADD-NODE" in msg
    assert "OUTCOME UNKNOWN" in msg and "Do NOT retry" in msg


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


def test_compact_description_keeps_nested_fields_examples_and_original_docstring():
    original = []

    def register(mcp, provider):
        @mcp.tool()
        def configure(kind: str, settings: dict) -> str:
            """Choose the setting family (选择设置类别); inspect with get_model_data.

            Args:
                kind: Setting group (设置类别):
                    limit_state:
                        fatigue (MPa), steel_bar
                settings: Complete values; [] clears the selection (完整参数)

            Returns:
                Confirmation only (仅返回确认).

            Example:
                configure(kind="limit_state", settings={"fatigue": 10})

            Notes:
                get_check_data reads the result (读取结果).
            """
            return "ok"

        original.append(configure.__doc__)

    m = FastMCP("compact")
    register_tools_with_envelope(m, register, None)
    tool = asyncio.run(m.list_tools())[0]
    assert "Args:" in original[0]  # The source remains available for parameter injection.
    assert "Args:" not in tool.description
    assert tool.inputSchema["properties"]["kind"]["description"] == (
        "Setting group (设置类别):\nlimit_state:\n    fatigue (MPa), steel_bar"
    )
    assert "[] clears" in tool.inputSchema["properties"]["settings"]["description"]
    assert "Returns:" in tool.description and "仅返回确认" in tool.description
    assert 'configure(kind="limit_state"' in tool.description
    assert "get_model_data" in tool.description and "get_check_data" in tool.description
    assert _call_json(m, "configure", {"kind": "limit_state", "settings": {}})["status"] == "success"


@pytest.mark.parametrize("doc", [
    "Summary.\n\nArgs:\n    name: A name.",  # missing count
    "Summary.\n\nArgs:\n    name: A name.\n    count: Count.\n    old: Orphan.",
    "Summary.\n\nArgs:\n    name: First.\n    name: Second.\n    count: Count.",
    "Summary.\n\nArgs:\n    Intro before parameters.\n    name: A name.\n    count: Count.",
    "Summary.\n\nArgs:\n    name: A name.\n    count: Count.\n\nArgs:\n    old: Old.",
])
def test_ambiguous_or_incomplete_args_layout_keeps_full_description(doc):
    def register(mcp, provider):
        def example(name: str, count: int = 1) -> str:
            return name * count

        example.__doc__ = doc
        mcp.tool()(example)

    m = FastMCP("fallback")
    register_tools_with_envelope(m, register, None)
    assert asyncio.run(m.list_tools())[0].description == doc


def test_explicit_description_is_respected_while_parameters_are_still_injected():
    def register(mcp, provider):
        @mcp.tool(description="Explicit public description.")
        def example(name: str) -> str:
            """Original summary.

            Args:
                name: Name with domain semantics (名称).
            """
            return name

    m = FastMCP("explicit")
    register_tools_with_envelope(m, register, None)
    tool = asyncio.run(m.list_tools())[0]
    assert tool.description == "Explicit public description."
    assert "domain semantics" in tool.inputSchema["properties"]["name"]["description"]


def test_catalog_compaction_preserves_all_input_output_metadata_and_references(fake_provider):
    full = FastMCP("full")
    with patch("qiao_mcp.tools.envelope._compact_description", return_value=None):
        register_tool_catalog(full, fake_provider)
    compact = FastMCP("compact")
    register_tool_catalog(compact, fake_provider)
    before = {t.name: t.model_dump() for t in asyncio.run(full.list_tools())}
    after = {t.name: t.model_dump() for t in asyncio.run(compact.list_tools())}
    assert before.keys() == after.keys()
    for name in before:
        old_description = before[name].pop("description")
        new_description = after[name].pop("description")
        assert before[name] == after[name], name
        field_text = json.dumps(after[name]["inputSchema"], ensure_ascii=False)
        for reference in before:
            if reference in old_description:
                assert reference in new_description or reference in field_text, (name, reference)
