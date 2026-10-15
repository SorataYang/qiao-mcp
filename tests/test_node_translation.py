"""Keep connected geometry intact when setting absolute or relative positions."""

from types import SimpleNamespace

import pytest
from conftest import tool_fns

from qiao_mcp.tools.modifications import register_modification_tools


def test_absolute_update_and_rename_preserve_the_existing_node(fake_provider):
    node = SimpleNamespace(node_id=5, x=2.0, y=3.0, z=7.0)
    nodes = {5: node}
    element = SimpleNamespace(node_i=node)
    fake_provider.get_node_data = lambda ids: [nodes[ids]] if ids in nodes else []
    fake_provider.query_model_data = lambda kind, **filters: {
        "items": [nodes[index] for index in filters["node_ids"] if index in nodes],
    }

    def translate(node_ids, dx, dy, dz):
        selected = nodes[node_ids]
        selected.x += dx
        selected.y += dy
        selected.z += dz

    def rename(node_id, new_id):
        selected = nodes.pop(node_id)
        selected.node_id = new_id
        nodes[new_id] = selected

    fake_provider._mdb.translate_nodes = translate
    fake_provider._mdb.update_node_id = rename
    tool_fns(register_modification_tools, fake_provider)["update_node"](
        node_id=5, z=-1.5, new_id=9,
    )
    assert list(nodes) == [9]
    assert nodes[9] is element.node_i
    assert vars(element.node_i) == {"node_id": 9, "x": 2.0, "y": 3.0, "z": -1.5}
    assert fake_provider._mdb.count("update_node") == 0
    assert fake_provider._mdb.count("update_model") == 1


def test_relative_move_uses_the_native_compound_command(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)["move_nodes"](
        ids=[9, 7, 5], offset_x=1.5, offset_y=-2, offset_z=3,
    )
    assert [header for header, _ in requests] == ["TRANSLATE-NODES", "UPDATE"]
    assert {key: value for key, value in requests[0][1].items() if key != "version"} == {
        "node_ids": [9, 7, 5], "dx": 1.5, "dy": -2, "dz": 3,
    }


def test_occupied_new_id_fails_before_moving(fake_provider):
    fake_provider.get_node_data = lambda ids: [{"node_id": ids, "x": 1, "y": 2, "z": 3}]
    fake_provider.query_model_data = lambda *args, **kwargs: {"items": [{"node_id": 9}]}
    with pytest.raises(ValueError, match="already exists"):
        fake_provider.update_node(5, z=10, new_id=9)
    assert fake_provider._mdb.calls == []


def test_missing_translation_api_never_falls_back_to_legacy_writes(fake_provider):
    fake_provider._mdb.translate_nodes = None
    with pytest.raises(ValueError, match="translate_nodes"):
        fake_provider.move_nodes([5], offset_z=1)
    assert fake_provider._mdb.calls == []


def test_failed_translation_is_not_retried_or_followed_by_rename(fake_provider):
    fake_provider.get_node_data = lambda ids: (
        [{"node_id": 5, "x": 1, "y": 2, "z": 3}] if ids == 5 else []
    )
    fake_provider.query_model_data = lambda *args, **kwargs: {"items": []}
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("reply lost")

    fake_provider._mdb.translate_nodes = fail
    with pytest.raises(TimeoutError, match="reply lost"):
        fake_provider.update_node(5, z=10, new_id=9)
    assert len(calls) == 1
    assert fake_provider._mdb.calls == []


def test_rename_failure_reports_partial_update_without_replaying(fake_provider):
    fake_provider.get_node_data = lambda ids: (
        [{"node_id": 5, "x": 1, "y": 2, "z": 3}] if ids == 5 else []
    )
    fake_provider.query_model_data = lambda *args, **kwargs: {"items": []}

    def fail(**kwargs):
        raise RuntimeError("rename failed")

    fake_provider._mdb.update_node_id = fail
    with pytest.raises(RuntimeError, match="coordinates may already have changed"):
        fake_provider.update_node(5, z=10, new_id=9)
    assert fake_provider._mdb.count("translate_nodes") == 1
    assert fake_provider._mdb.count("update_node") == 0


def test_absolute_offset_overflow_fails_before_writing(fake_provider):
    fake_provider.get_node_data = lambda ids: [{"node_id": 5, "x": -1e308, "y": 2, "z": 3}]
    with pytest.raises(ValueError, match="finite"):
        fake_provider.update_node(5, x=1e308)
    assert fake_provider._mdb.calls == []
