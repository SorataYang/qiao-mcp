"""节点链几何校验测试 —— 拦截折返几何。

背景（qtmodel 2.6.3 实机实测）：后端分配节点编号的顺序**无法从请求推算**。
同一份代码、同样形状的入参，一批返回 [304,303,302,301,300]（完整倒序），
另一批返回 [300,304,303,302,301]（既非升序也非纯倒序）。

于是"按 node_id_start 递推连接相邻编号"这一假设会静默建出折返几何：
实测在乱序批上建 4 个单元，长度为 [3, 12, 3, 3]、方向 [-, +, -, -]，
中间夹着一个 12m 的折返段。**后端不报错**，求解器照算，只是算的是另一座桥。

这是最坏的一类失效——模型能建、能算、能出结果，但结果是错的。因此在
写入前按真实坐标校验单调性，宁可拒绝也不建出坏模型。
"""

from __future__ import annotations

import pytest
from conftest import FakeDb, tool_fns

from qiao_mcp.providers.qtmodel_provider import QtModelProvider
from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.envelope import ToolInputError


def _provider(coords: dict[int, tuple[float, float, float]] | None = None):
    """Provider with a fake odb whose get_node_data returns the given coordinates."""
    p = QtModelProvider.__new__(QtModelProvider)
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeDb()
    p._odb = FakeDb()
    p._cdb = FakeDb()
    if coords is not None:
        rows = [
            {"node_id": nid, "x": x, "y": y, "z": z}
            for nid, (x, y, z) in coords.items()
        ]
        p._odb.get_node_data = lambda *a, **k: rows
    return p


def _linear(n: int, spacing: float = 3.0, reverse_ids: bool = False):
    """n 个沿 X 等间距的节点。reverse_ids=True 时编号与坐标反向（实测常见）。"""
    ids = list(range(n, 0, -1)) if reverse_ids else list(range(1, n + 1))
    return {ids[i]: (i * spacing, 0.0, 0.0) for i in range(n)}


# ── provider 层：几何判定 ─────────────────────────────────────────────


def test_monotonic_ascending_chain_passes():
    p = _provider(_linear(5))
    got = p.check_node_chain_geometry([1, 2, 3, 4, 5])
    assert got["ok"] is True
    assert got["total_length"] == pytest.approx(12.0)


def test_monotonic_descending_chain_passes():
    """编号与坐标反向是后端的常见行为，几何上仍单调，必须放行。"""
    coords = _linear(5, reverse_ids=True)
    p = _provider(coords)
    got = p.check_node_chain_geometry([5, 4, 3, 2, 1])
    assert got["ok"] is True
    assert got["total_length"] == pytest.approx(12.0)


def test_folded_chain_is_rejected():
    """实测的非单调批：ID 升序对应 x=[300,312,309,306,303]。"""
    coords = {
        300: (300.0, 0.0, 0.0),
        301: (312.0, 0.0, 0.0),
        302: (309.0, 0.0, 0.0),
        303: (306.0, 0.0, 0.0),
        304: (303.0, 0.0, 0.0),
    }
    p = _provider(coords)
    got = p.check_node_chain_geometry([300, 301, 302, 303, 304])
    assert got["ok"] is False
    assert "fold" in got["reason"].lower() or "折返" in got["reason"]


def test_same_batch_in_true_coordinate_order_passes():
    """同一批节点按真实坐标顺序排列即合法 —— 校验不应误拒。"""
    coords = {
        300: (300.0, 0.0, 0.0),
        301: (312.0, 0.0, 0.0),
        302: (309.0, 0.0, 0.0),
        303: (306.0, 0.0, 0.0),
        304: (303.0, 0.0, 0.0),
    }
    p = _provider(coords)
    got = p.check_node_chain_geometry([300, 304, 303, 302, 301])
    assert got["ok"] is True
    assert got["total_length"] == pytest.approx(12.0)


def test_curved_girder_is_not_rejected():
    """折线/曲线桥相邻段方向渐变，点积仍为正，必须放行。"""
    coords = {1: (0.0, 0.0, 0.0), 2: (10.0, 1.0, 0.0), 3: (20.0, 3.0, 0.0), 4: (30.0, 6.0, 0.0)}
    p = _provider(coords)
    assert p.check_node_chain_geometry([1, 2, 3, 4])["ok"] is True


def test_missing_node_is_reported():
    p = _provider(_linear(3))
    got = p.check_node_chain_geometry([1, 2, 99])
    assert got["ok"] is False
    assert 99 in got["missing"]


def test_coincident_nodes_rejected():
    """零长单元会让刚度矩阵奇异，应在写入前拒绝。"""
    p = _provider({1: (0.0, 0.0, 0.0), 2: (0.0, 0.0, 0.0)})
    got = p.check_node_chain_geometry([1, 2])
    assert got["ok"] is False
    assert "coincident" in got["reason"].lower()


def test_check_skipped_when_coordinates_unavailable():
    """查询不可用时不应阻断建模 —— 校验能力缺失不等于几何有问题。"""
    p = _provider()  # get_node_data 返回 FakeDb 的记录器（非列表）
    assert p.check_node_chain_geometry([1, 2, 3])["ok"] is True


# ── 工具层：拦截与放行 ────────────────────────────────────────────────


def _fns(p):
    return tool_fns(register_modeling_tools, p)


def test_tool_refuses_folded_chain_before_writing():
    coords = {
        300: (300.0, 0.0, 0.0),
        301: (312.0, 0.0, 0.0),
        302: (309.0, 0.0, 0.0),
        303: (306.0, 0.0, 0.0),
        304: (303.0, 0.0, 0.0),
    }
    p = _provider(coords)
    with pytest.raises(ToolInputError) as exc:
        _fns(p)["create_beam_elements_linear"](
            mat_id=1, sec_id=1, node_id_start=300, count=4
        )
    assert "monotonic" in str(exc.value) or "折返" in str(exc.value)
    assert p._mdb.count("add_elements") == 0, "拒绝时不得下发任何写入"


def test_tool_accepts_explicit_ids_in_true_order():
    coords = {
        300: (300.0, 0.0, 0.0),
        301: (312.0, 0.0, 0.0),
        302: (309.0, 0.0, 0.0),
        303: (306.0, 0.0, 0.0),
        304: (303.0, 0.0, 0.0),
    }
    p = _provider(coords)
    _fns(p)["create_beam_elements_linear"](
        mat_id=1, sec_id=1, node_ids=[300, 304, 303, 302, 301]
    )
    _, _, kw = p._mdb.last("add_elements")
    ele = kw["ele_data"]
    assert len(ele) == 4
    # [id, type, mat, sec, beta, nodeI, nodeJ, initType, initVal]
    assert [row[5:7] for row in ele] == [[300, 304], [304, 303], [303, 302], [302, 301]]


def test_tool_requires_node_ids_or_start_and_count():
    p = _provider(_linear(3))
    with pytest.raises(ToolInputError):
        _fns(p)["create_beam_elements_linear"](mat_id=1, sec_id=1)


def test_tool_rejects_duplicate_node_ids():
    p = _provider(_linear(3))
    with pytest.raises(ToolInputError):
        _fns(p)["create_beam_elements_linear"](
            mat_id=1, sec_id=1, node_ids=[1, 2, 2, 3]
        )


def test_tool_rejects_single_node():
    p = _provider(_linear(3))
    with pytest.raises(ToolInputError):
        _fns(p)["create_beam_elements_linear"](mat_id=1, sec_id=1, node_ids=[1])
