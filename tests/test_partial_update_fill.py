"""部分更新回填测试。

qtmodel 的 update_node/update_element 会把未传入的字段按默认值整体下发
（update_node 坐标默认 1，update_element 的 ele_type 默认 1、beta_angle 默认 0），
partial update 若不回填会静默破坏数据。
本测试用假 mdb 断言：未指定字段以当前模型值补齐后再下发。
"""

from types import SimpleNamespace

import pytest

from qiao_mcp.providers.qtmodel_provider import QtModelProvider


class FakeMdb:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def last(self, name):
        matched = [c for c in self.calls if c[0] == name]
        assert matched, f"no call to {name}"
        return matched[-1]


@pytest.fixture
def provider(monkeypatch):
    p = QtModelProvider.__new__(QtModelProvider)  # 跳过 __init__ 的 import 探测
    p._available = True
    p._unavailable_reason = ""
    p._mdb = FakeMdb()
    p._odb = None
    p._cdb = None
    return p


# ── update_node ──────────────────────────────────────────────────────


def test_update_node_fills_unspecified_coordinates(provider, monkeypatch):
    query_calls = []
    monkeypatch.setattr(
        provider,
        "get_node_data",
        lambda ids: (query_calls.append(ids), [{"node_id": 5, "x": 2.0, "y": 3.0, "z": 7.0}])[1],
    )
    provider.update_node(5, x=10.0, new_id=-1)

    _, _, kwargs = provider._mdb.last("update_node")
    assert kwargs["x"] == 10.0
    assert kwargs["y"] == 3.0, "未指定的 y 必须回填当前值而非 qtmodel 默认值 1"
    assert kwargs["z"] == 7.0, "未指定的 z 必须回填当前值而非 qtmodel 默认值 1"
    assert query_calls == [5]


def test_update_node_supports_query_model_objects(provider, monkeypatch):
    node = SimpleNamespace(node_id=5, x=2.0, y=3.0, z=7.0)
    monkeypatch.setattr(provider, "get_node_data", lambda ids: [node])
    provider.update_node(5, z=-1.5)

    _, _, kwargs = provider._mdb.last("update_node")
    assert (kwargs["x"], kwargs["y"], kwargs["z"]) == (2.0, 3.0, -1.5)


def test_update_node_skips_query_when_all_coords_given(provider, monkeypatch):
    def boom(ids):
        raise AssertionError("全坐标显式给出时不应回查")

    monkeypatch.setattr(provider, "get_node_data", boom)
    provider.update_node(5, x=1.0, y=2.0, z=3.0)
    _, _, kwargs = provider._mdb.last("update_node")
    assert (kwargs["x"], kwargs["y"], kwargs["z"]) == (1.0, 2.0, 3.0)


def test_update_node_missing_node_raises(provider, monkeypatch):
    monkeypatch.setattr(provider, "get_node_data", lambda ids: [])
    with pytest.raises(ValueError, match="not found"):
        provider.update_node(99, x=1.0)
    assert provider._mdb.calls == [], "节点不存在时不得下发任何修改"


# ── update_element ────────────────────────────────────────────────────


def test_update_element_fills_unspecified_fields(provider, monkeypatch):
    element = SimpleNamespace(
        index=9,
        ele_type="CABLE",
        node_ids=[1, 2],
        beta_angle=15.0,
        mat_id=3,
        sec_id=4,
        initial_type=2,
        initial_value=5.0,
    )
    monkeypatch.setattr(provider, "get_element_data", lambda ids: [element])
    provider.update_element(9, mat_id=7)

    _, _, kwargs = provider._mdb.last("update_element")
    assert kwargs["mat_id"] == 7
    assert kwargs["ele_type"] == 3, "CABLE 必须映射回整数 3，而非 qtmodel 默认值 1(梁)"
    assert kwargs["beta_angle"] == 15.0, "未指定的 beta_angle 必须回填而非归零"
    assert kwargs["node_ids"] == [1, 2]
    assert kwargs["sec_id"] == 4
    assert kwargs["initial_type"] == 2
    assert kwargs["initial_value"] == 5.0


def test_update_element_missing_element_raises(provider, monkeypatch):
    monkeypatch.setattr(provider, "get_element_data", lambda ids: [])
    with pytest.raises(ValueError, match="not found"):
        provider.update_element(99, mat_id=1)
    assert provider._mdb.calls == []
