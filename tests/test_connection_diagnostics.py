"""桥通连接诊断测试。

qtmodel 2.6 起 QtServer.get_connection_status() 区分三种状态：
connected / version_mismatch / software_not_running，各带 message 与 action。

version_mismatch 是 2.6 新增的**硬失败**：QT_VERSION 硬编码在客户端，
与桥通上报的 api_version 精确字符串比对，不等即拒绝连接。此前
_try_import 把它和"软件未启动"混成同一条模糊消息，而两者处置相反
（升级软件 vs 启动软件），因此必须分开告知。

本测试不需要桥通软件，也不需要 qtmodel 的真实网络探测——
统一 monkeypatch QtServer.get_connection_status。
"""

from __future__ import annotations

import pytest
from conftest import FakeDb, tool_fns

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.envelope import ToolError

CONNECTED = {
    "status": "connected",
    "connected": True,
    "compatible": True,
    "message": "已连接桥通 HTTP 服务。",
    "action": "可以调用需要桥通的模型工具。",
    "client": {"qtmodel_version": "2.6.3", "active_url": "http://127.0.0.1:55125"},
    "server": {"api_version": "2.6.3"},
}

MISMATCH = {
    "status": "version_mismatch",
    "connected": True,
    "compatible": False,
    "message": "桥通 API 版本 2.5.0 与 qtmodel 2.6.3 不兼容。",
    "action": "请升级桥通软件或安装与软件 API 版本匹配的 qtmodel。",
    "client": {"qtmodel_version": "2.6.3", "active_url": None},
    "server": {"api_version": "2.5.0"},
}

NOT_RUNNING = {
    "status": "software_not_running",
    "connected": False,
    "compatible": None,
    "message": "未发现桥通 HTTP 服务，桥通软件可能尚未启动。",
    "action": "请启动桥通并等待主界面加载完成，然后重新调用本工具。",
    "client": {"qtmodel_version": "2.6.3", "active_url": None},
    "server": None,
}


@pytest.fixture
def provider():
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeDb()
    p._odb = FakeDb()
    p._cdb = FakeDb()
    return p


@pytest.fixture
def patch_status(monkeypatch):
    """替换 qtmodel 的握手探测，返回指定状态字典。"""

    def apply(status):
        from qtmodel.core.qt_server import QtServer

        monkeypatch.setattr(
            QtServer, "get_connection_status", staticmethod(lambda: status)
        )

    return apply


# ── provider 层 ───────────────────────────────────────────────────────


@pytest.mark.parametrize("status", [CONNECTED, MISMATCH, NOT_RUNNING])
def test_provider_passes_through_handshake_status(provider, patch_status, status):
    patch_status(status)
    assert provider.get_connection_status() == status


def test_provider_reports_missing_probe_without_raising(provider, monkeypatch):
    """qtmodel < 2.6 无 get_connection_status，必须降级而非抛错。"""
    from qtmodel.core.qt_server import QtServer

    monkeypatch.delattr(QtServer, "get_connection_status", raising=False)
    status = provider.get_connection_status()
    assert status["status"] == "unknown"
    assert status["compatible"] is None


def test_provider_survives_probe_exception(provider, monkeypatch):
    """探测本身抛错（如端口扫描失败）时也必须返回可读状态。"""
    from qtmodel.core.qt_server import QtServer

    def boom():
        raise OSError("socket exhausted")

    monkeypatch.setattr(QtServer, "get_connection_status", staticmethod(boom))
    status = provider.get_connection_status()
    assert status["status"] == "probe_failed"
    assert "socket exhausted" in status["message"]


# ── 工具层 ────────────────────────────────────────────────────────────


def _check(provider):
    return tool_fns(register_api_gateway_tools, provider)["check_qiaotong_connection"]


def test_tool_surfaces_version_mismatch_as_actionable_text(provider, patch_status):
    """版本不匹配必须报出双方版本号，而不是笼统的"连接失败"。"""
    patch_status(MISMATCH)
    out = _check(provider)()
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "version_mismatch" in text
    assert "2.5.0" in text and "2.6.3" in text, "必须同时给出服务端与客户端版本"
    assert "升级桥通" in text


def test_tool_distinguishes_not_running_from_mismatch(provider, patch_status):
    patch_status(NOT_RUNNING)
    out = _check(provider)()
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "software_not_running" in text
    assert "启动桥通" in text
    assert "version_mismatch" not in text


def test_tool_hints_localhost_when_configured_with_bare_ip(provider, patch_status):
    """配置用了 127.0.0.1 且未连上时，必须提示改用 localhost。

    经端口转发（如 SSH 隧道）访问远端桥通时，Windows HTTP.sys 会校验 Host 头，
    对裸 IP 回 "400 Invalid Hostname"——端口明明是通的，却连不上，
    没有这条提示极难定位。
    """
    status = dict(NOT_RUNNING)
    status["client"] = {
        "qtmodel_version": "2.6.3",
        "configured_url": "http://127.0.0.1:45125/pythonForQt/",
        "active_url": None,
    }
    patch_status(status)
    out = _check(provider)()
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "localhost" in text, "应提示改用 localhost"
    assert "Invalid Hostname" in text, "应点明后端的拒绝原因"


def test_tool_survives_null_active_url(provider, patch_status):
    """回归：software_not_running 时 active_url 为 None，
    提示逻辑若直接对它做子串判断会抛 TypeError。"""
    status = dict(NOT_RUNNING)
    status["client"] = {"qtmodel_version": "2.6.3", "active_url": None}
    patch_status(status)
    out = _check(provider)()  # 不应抛错
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "software_not_running" in text


def test_tool_omits_localhost_hint_when_connected(provider, patch_status):
    """已连上时不该再提示换 host——即使配置里就是裸 IP。"""
    status = dict(CONNECTED)
    status["client"] = {
        "qtmodel_version": "2.6.3",
        "configured_url": "http://127.0.0.1:45125/pythonForQt/",
        "active_url": "http://127.0.0.1:45125/pythonForQt/",
    }
    patch_status(status)
    out = _check(provider)()
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "Invalid Hostname" not in text


def test_tool_reports_connected_state(provider, patch_status):
    patch_status(CONNECTED)
    out = _check(provider)()
    text = out["message"] if isinstance(out, dict) else str(out)
    assert "connected" in text
    assert "2.6.3" in text


def test_tool_wraps_provider_failure_as_tool_error(provider, monkeypatch):
    def boom():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(provider, "get_connection_status", boom)
    with pytest.raises(ToolError):
        _check(provider)()


# ── _try_import 的失败原因分流 ────────────────────────────────────────


def test_handshake_detail_names_version_mismatch(monkeypatch):
    """握手判定为版本不匹配时，原因串必须点明版本问题与处置动作。"""
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: MISMATCH)
    )
    reason = QtModelProvider._handshake_detail()
    assert "不兼容" in reason or "版本" in reason
    assert "升级桥通" in reason


def test_try_import_failure_prefers_handshake_reason(monkeypatch):
    """连接失败走 except 分支时，_unavailable_reason 应采用握手给出的精确原因。

    回归点：此前该分支只会说"请确保桥通软件已启动"，
    而真实原因可能是版本不匹配——启动软件并不能解决。
    """
    import sys
    import types

    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: MISMATCH)
    )

    # 用桩模块替换 qtmodel：访问 mdb 即抛错，驱动 _try_import 的 except 分支
    stub = types.ModuleType("qtmodel")
    stub.__version__ = "2.6.3"

    def _raise(name):
        raise RuntimeError("connection refused")

    stub.__getattr__ = _raise  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "qtmodel", stub)

    p = QtModelProvider()
    assert p.is_available() is False
    assert "升级桥通" in p._unavailable_reason, (
        "版本不匹配时不能只提示启动软件"
    )
    assert "2.5.0" in p._unavailable_reason


def test_try_import_falls_back_when_handshake_silent(monkeypatch):
    """握手无话可说（如 qtmodel < 2.6）时，保留原有的通用提示。"""
    import sys
    import types

    from qtmodel.core.qt_server import QtServer

    monkeypatch.delattr(QtServer, "get_connection_status", raising=False)

    stub = types.ModuleType("qtmodel")
    stub.__version__ = "2.5.0"

    def _raise(name):
        raise RuntimeError("connection refused")

    stub.__getattr__ = _raise  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "qtmodel", stub)

    p = QtModelProvider()
    assert p.is_available() is False
    assert "桥通软件已启动" in p._unavailable_reason


def test_handshake_detail_empty_when_connected(monkeypatch):
    """已连接时不应产生"不可用原因"文本。"""
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: CONNECTED)
    )
    assert QtModelProvider._handshake_detail() == ""
