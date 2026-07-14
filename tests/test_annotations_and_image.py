"""工具注解与图像返回测试。"""

import asyncio
import struct
import zlib

from mcp.server.fastmcp.utilities.types import Image as FastMCPImage

from qiao_mcp.tools.envelope import _annotations_for
from qiao_mcp.tools.visualization import register_visualization_tools

from conftest import tool_fns


def _png_1x1() -> bytes:
    """构造一张最小合法 PNG，避免依赖 Pillow。"""
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


_PNG_BYTES = _png_1x1()


# ── 注解分类 ──────────────────────────────────────────────────────────


def test_readonly_annotation():
    a = _annotations_for("get_model_data")
    assert a.readOnlyHint is True
    assert a.destructiveHint is False
    assert a.idempotentHint is True


def test_destructive_annotation():
    for name in ("remove_nodes", "initialize_model", "open_model_file", "merge_nodes"):
        a = _annotations_for(name)
        assert a.destructiveHint is True, f"{name} 应标记为破坏性"
        assert a.readOnlyHint is False


def test_write_tool_is_neither_readonly_nor_destructive():
    a = _annotations_for("create_nodes")
    assert a.readOnlyHint is False
    assert a.destructiveHint is False


def test_gateway_call_is_open_world():
    assert _annotations_for("call_qtmodel_api").openWorldHint is True
    assert _annotations_for("list_qtmodel_api").readOnlyHint is True


def test_annotations_applied_on_registered_tools():
    from mcp.server.fastmcp import FastMCP
    from qiao_mcp.tools.envelope import register_tools_with_envelope
    from qiao_mcp.tools import register_modeling_tools

    mcp = FastMCP("t")
    register_tools_with_envelope(mcp, register_modeling_tools, provider=None)
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert tools["get_model_info"].annotations.readOnlyHint is True
    assert tools["create_nodes"].annotations.readOnlyHint is False


# ── 截图/云图返回图像内容 ──────────────────────────────────────────────


def test_screenshot_returns_image_content(fake_provider, tmp_path, monkeypatch):
    out = tmp_path / "shot.png"
    monkeypatch.setattr(
        fake_provider, "save_model_image",
        lambda file_path: out.write_bytes(_PNG_BYTES),
    )
    fns = tool_fns(register_visualization_tools, fake_provider)
    result = fns["save_model_screenshot"](file_path=str(out), view_angle="current")
    assert isinstance(result, FastMCPImage), "默认应返回可预览的图像内容"


def test_screenshot_path_only_when_disabled(fake_provider, tmp_path, monkeypatch):
    out = tmp_path / "shot.png"
    monkeypatch.setattr(
        fake_provider, "save_model_image",
        lambda file_path: out.write_bytes(_PNG_BYTES),
    )
    fns = tool_fns(register_visualization_tools, fake_provider)
    result = fns["save_model_screenshot"](
        file_path=str(out), view_angle="current", return_image=False
    )
    assert isinstance(result, dict) and "saved to" in result["message"]
