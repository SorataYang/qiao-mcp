"""is_available() 真实连通性探测测试。

修复前 is_available() 只回报 import 结果：绑定 qtmodel.mdb/odb/cdb **不会**
因桥通未启动而抛错（三个对象是惰性的，只在真正调用方法时才发 HTTP），
于是无论桥通是否运行都返回 True，server 启动日志恒打印 "✅ loaded successfully"。

本测试锁定三件事：
1. 不可达 / 版本不匹配时 is_available() 必须为 False，且原因指向正确处置；
2. 探测结果有缓存（否则每次调用都发 HTTP），但缓存必须过期（用户常先起
   MCP server、后开桥通，不能要求重启）；
3. 无从判断时（qtmodel < 2.6 无握手 API）保持乐观——缺少手段不等于不可用。

注意 _available 的语义未变，仍是"import 成功"，182 个 _require_available()
调用点依赖它；本测试只针对 is_available() 这一层。
"""

from __future__ import annotations

from typing import Any

import pytest

from qiao_mcp.providers.qtmodel_provider import QtModelProvider

CONNECTED: dict[str, Any] = {
    "status": "connected",
    "connected": True,
    "compatible": True,
    "message": "已连接桥通 HTTP 服务。",
    "action": "可以调用需要桥通的模型工具。",
}

NOT_RUNNING: dict[str, Any] = {
    "status": "software_not_running",
    "connected": False,
    "compatible": None,
    "message": "未发现桥通 HTTP 服务，桥通软件可能尚未启动。",
    "action": "请启动桥通并等待主界面加载完成，然后重新调用本工具。",
}

MISMATCH: dict[str, Any] = {
    "status": "version_mismatch",
    "connected": True,  # 关键：TCP 层连上了
    "compatible": False,  # 但 API 版本不匹配，同样不可用
    "message": "桥通 API 版本 2.5.0 与 qtmodel 2.6.3 不兼容。",
    "action": "请升级桥通软件或安装与软件 API 版本匹配的 qtmodel。",
}


def _provider(monkeypatch, status: dict[str, Any] | None, count: list[int] | None = None):
    """构造一个 import 已成功、握手返回 status 的 provider。

    status=None 模拟 qtmodel < 2.6：删掉握手 API。
    """
    from qtmodel.core.qt_server import QtServer

    if status is None:
        monkeypatch.delattr(QtServer, "get_connection_status", raising=False)
    else:

        def fake():
            if count is not None:
                count[0] += 1
            return status

        monkeypatch.setattr(
            QtServer, "get_connection_status", staticmethod(fake)
        )

    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True  # import 成功
    p._unavailable_reason = ""
    p._mdb = object()
    p._odb = object()
    p._cdb = object()
    return p


# ── 核心：不可用必须被识别 ────────────────────────────────────────────


def test_reports_unavailable_when_software_not_running(monkeypatch):
    """桥通未启动时必须为 False——修复前恒为 True。"""
    p = _provider(monkeypatch, NOT_RUNNING)
    assert p.is_available() is False


def test_reports_unavailable_on_version_mismatch(monkeypatch):
    """版本不匹配时 connected=True 但 compatible=False，仍属不可用。

    这一条最容易漏：只看 connected 会把"连上了但版本不对"判为可用，
    而 qtmodel 对版本是精确字符串比对，此时所有调用都会失败。
    """
    p = _provider(monkeypatch, MISMATCH)
    assert p.is_available() is False


def test_reports_available_when_connected(monkeypatch):
    p = _provider(monkeypatch, CONNECTED)
    assert p.is_available() is True


def test_import_failure_short_circuits_probe(monkeypatch):
    """import 都没成功时不该再探测，直接 False。"""
    count = [0]
    p = _provider(monkeypatch, CONNECTED, count)
    p._available = False
    assert p.is_available() is False
    assert count[0] == 0, "import 失败时不应发起网络探测"


# ── 原因必须可操作 ────────────────────────────────────────────────────


def test_not_running_reason_says_start_software(monkeypatch):
    """server.py 与 _require_available 都展示这条原因，必须告诉用户做什么。"""
    p = _provider(monkeypatch, NOT_RUNNING)
    p.is_available()
    assert "启动桥通" in p._unavailable_reason


def test_mismatch_reason_says_upgrade_not_start(monkeypatch):
    """版本不匹配时提示"启动软件"是误导——软件已经在运行了。"""
    p = _provider(monkeypatch, MISMATCH)
    p.is_available()
    assert "升级桥通" in p._unavailable_reason
    assert "2.5.0" in p._unavailable_reason, "应报出双方版本便于定位"


def test_connected_leaves_reason_empty(monkeypatch):
    p = _provider(monkeypatch, CONNECTED)
    p.is_available()
    assert p._unavailable_reason == ""


# ── 缓存：必须有，也必须会过期 ────────────────────────────────────────


def test_probe_result_is_cached(monkeypatch):
    """探测走 HTTP，连续调用不能每次都发。"""
    count = [0]
    p = _provider(monkeypatch, CONNECTED, count)
    for _ in range(5):
        p.is_available()
    assert count[0] == 1, f"5 次调用应只探测 1 次，实际 {count[0]} 次"


def test_cache_expires_so_late_started_software_is_seen(monkeypatch):
    """用户常先起 MCP server、后开桥通——缓存必须自愈，不能要求重启。"""
    count = [0]
    p = _provider(monkeypatch, NOT_RUNNING, count)
    assert p.is_available() is False

    # 桥通此刻启动：换掉握手结果，并把缓存时间推到 TTL 之外
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: CONNECTED)
    )
    p._probe_at -= QtModelProvider._PROBE_TTL + 1

    assert p.is_available() is True, "TTL 过期后必须重新探测到已连接"


def test_force_bypasses_cache(monkeypatch):
    count = [0]
    p = _provider(monkeypatch, CONNECTED, count)
    p.is_available()
    assert count[0] == 1
    p._probe_connection(force=True)
    assert count[0] == 2, "force=True 应绕过缓存"


# ── 探不到 ≠ 不可用 ───────────────────────────────────────────────────


def test_stays_optimistic_without_handshake_api(monkeypatch):
    """qtmodel < 2.6 没有握手 API，此时保持修复前的乐观行为。"""
    p = _provider(monkeypatch, None)
    assert p._probe_connection() is None, "探不到应返回 None，而非 False"
    assert p.is_available() is True


def test_probe_exception_stays_optimistic(monkeypatch):
    """探测本身抛错也不能把后端判死。"""
    from qtmodel.core.qt_server import QtServer

    def boom():
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(QtServer, "get_connection_status", staticmethod(boom))
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    assert p._probe_connection() is None
    assert p.is_available() is True


def test_non_dict_handshake_is_ignored(monkeypatch):
    """握手返回非字典（上游改了返回类型）时不应崩，也不应误判。"""
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: "connected")
    )
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    assert p._probe_connection() is None
    assert p.is_available() is True


# ── 构造成本：不能在 import 期做网络探测 ──────────────────────────────


def test_init_does_not_probe(monkeypatch):
    """MCP server 在 import 期构造 provider，最坏要枚举 461 个候选端口，
    不能让 server 启动同步等待网络。"""
    count = [0]
    from qtmodel.core.qt_server import QtServer

    def fake():
        count[0] += 1
        return CONNECTED

    monkeypatch.setattr(QtServer, "get_connection_status", staticmethod(fake))
    QtModelProvider()
    assert count[0] == 0, "__init__ 不应发起连通性探测"


def test_new_without_init_does_not_crash(monkeypatch):
    """全套测试普遍用 __new__ 跳过 __init__ 注入假 db；
    缺少 _probe_cache/_probe_at 的类级默认值时这里会 AttributeError。"""
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    from qtmodel.core.qt_server import QtServer

    monkeypatch.setattr(
        QtServer, "get_connection_status", staticmethod(lambda: CONNECTED)
    )
    assert p.is_available() is True


def test_fake_provider_fixture_still_works(fake_provider):
    """conftest 的 fake_provider 走 __new__ 路径，必须不受本次改动影响。"""
    assert fake_provider._available is True
    assert fake_provider.is_available() in (True, False)  # 不抛错即可


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
