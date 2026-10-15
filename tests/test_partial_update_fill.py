"""部分更新回填测试。

节点绝对修改先读取当前坐标，再平移既有节点以保持单元引用。
单元更新回填未指定字段，避免原生默认值覆盖现有属性。
"""

from types import SimpleNamespace

import pytest


@pytest.fixture
def provider(fake_provider):
    return fake_provider


# ── update_node ──────────────────────────────────────────────────────


def test_update_node_fills_unspecified_coordinates(provider, monkeypatch):
    query_calls = []
    monkeypatch.setattr(
        provider,
        "get_node_data",
        lambda ids: (query_calls.append(ids), [{"node_id": 5, "x": 2.0, "y": 3.0, "z": 7.0}])[1],
    )
    provider.update_node(5, x=10.0, new_id=-1)

    _, _, kwargs = provider._mdb.last("translate_nodes")
    assert kwargs == {"node_ids": 5, "dx": 8.0, "dy": 0.0, "dz": 0.0}
    assert provider._mdb.count("update_node") == 0
    assert query_calls == [5]


def test_update_node_supports_query_model_objects(provider, monkeypatch):
    node = SimpleNamespace(node_id=5, x=2.0, y=3.0, z=7.0)
    monkeypatch.setattr(provider, "get_node_data", lambda ids: [node])
    provider.update_node(5, z=-1.5)

    _, _, kwargs = provider._mdb.last("translate_nodes")
    assert (kwargs["dx"], kwargs["dy"], kwargs["dz"]) == (0.0, 0.0, -8.5)


def test_update_node_reads_current_position_even_with_all_coordinates(provider, monkeypatch):
    monkeypatch.setattr(provider, "get_node_data", lambda ids: [
        {"node_id": 5, "x": 2.0, "y": 3.0, "z": 7.0},
    ])
    provider.update_node(5, x=1.0, y=2.0, z=3.0)
    _, _, kwargs = provider._mdb.last("translate_nodes")
    assert (kwargs["dx"], kwargs["dy"], kwargs["dz"]) == (-1.0, -1.0, -4.0)


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


def test_update_element_preserves_thick_plate(provider, monkeypatch):
    """板单元的 plate_type 必须回填，否则厚板会被 qtmodel 默认值 0 静默改成薄板。"""
    element = SimpleNamespace(
        index=7,
        ele_type="PLATE",
        node_ids=[1, 2, 3, 4],
        beta_angle=0.0,
        mat_id=1,
        sec_id=2,
        initial_type=1,
        initial_value=0.0,
        plate_type=1,  # 1=厚板
    )
    monkeypatch.setattr(provider, "get_element_data", lambda ids: [element])
    provider.update_element(7, mat_id=5)

    _, _, kwargs = provider._mdb.last("update_element")
    assert kwargs["mat_id"] == 5
    assert kwargs["plate_type"] == 1, "厚板必须保持，不能被默认值 0(薄板) 覆盖"


def test_update_element_omits_plate_type_when_query_lacks_it(provider, monkeypatch):
    """旧版查询模型不返回 plate_type 时不得凭空下发，保持既有行为。"""
    element = SimpleNamespace(
        index=8,
        ele_type="BEAM",
        node_ids=[1, 2],
        beta_angle=0.0,
        mat_id=1,
        sec_id=2,
        initial_type=1,
        initial_value=0.0,
    )
    monkeypatch.setattr(provider, "get_element_data", lambda ids: [element])
    provider.update_element(8, mat_id=5)

    _, _, kwargs = provider._mdb.last("update_element")
    assert "plate_type" not in kwargs


def test_update_element_missing_element_raises(provider, monkeypatch):
    monkeypatch.setattr(provider, "get_element_data", lambda ids: [])
    with pytest.raises(ValueError, match="not found"):
        provider.update_element(99, mat_id=1)
    assert provider._mdb.calls == []
