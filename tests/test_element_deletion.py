"""Preserve nodes and their data unless endpoint cleanup was requested."""

from types import SimpleNamespace

import pytest
from conftest import tool_fns

from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.modifications import register_modification_tools


def test_preserved_nodes_keep_supports_and_connected_elements(fake_provider):
    nodes = {index: SimpleNamespace(node_id=index) for index in (1, 2, 3, 9)}
    elements = {7: [nodes[1], nodes[2]], 90: [nodes[2], nodes[3]]}
    support = SimpleNamespace(node=nodes[1], stiffness=[1, 2, 3])
    original_nodes = dict(nodes)
    fake_provider.get_element_data = lambda **kwargs: [{"index": index} for index in elements]

    def delete(object_type, index):
        assert object_type == "element"
        del elements[index]

    fake_provider._mdb.delete_model_object = delete
    tool_fns(register_modification_tools, fake_provider)["remove_elements"](ids=[7])
    assert elements == {90: [nodes[2], nodes[3]]}
    assert nodes == original_nodes
    assert support.node is original_nodes[1]
    assert support.stiffness == [1, 2, 3]
    assert fake_provider._mdb.count("remove_elements") == 0
    assert fake_provider._mdb.count("update_model") == 1


@pytest.mark.parametrize("ids", ["7to9by2", [7, 9, 7]])
def test_preserved_node_batch_expands_ranges_and_deletes_each_id_once(qtmodel_wire, ids):
    provider, requests = qtmodel_wire
    provider.get_element_data = lambda **kwargs: [{"index": 7}, {"index": 9}]
    tool_fns(register_modification_tools, provider)["remove_elements"](ids=ids)
    assert [header for header, _ in requests] == ["DELETE-MODEL-OBJECT"] * 2 + ["UPDATE"]
    assert [payload["index"] for _, payload in requests[:-1]] == [7, 9]
    assert all(payload["object_type"] == "element" for _, payload in requests[:-1])


def test_missing_element_fails_before_any_deletion(fake_provider):
    fake_provider.get_element_data = lambda **kwargs: [{"index": 7}]
    with pytest.raises(ValueError, match="Elements not found"):
        fake_provider.remove_elements([7, 90])
    assert fake_provider._mdb.calls == []


def test_missing_precise_deletion_api_never_uses_destructive_legacy_route(fake_provider):
    fake_provider._mdb.delete_model_object = None
    with pytest.raises(ValueError, match="delete_model_object"):
        fake_provider.remove_elements([7])
    assert fake_provider._mdb.calls == []


def test_partial_failure_stops_without_retry_or_commit(fake_provider):
    fake_provider.get_element_data = lambda **kwargs: [{"index": 7}, {"index": 8}, {"index": 9}]
    calls = []

    def delete(object_type, index):
        calls.append(index)
        if index == 8:
            raise TimeoutError("reply lost")

    fake_provider._mdb.delete_model_object = delete
    with pytest.raises(ToolError, match="partial|partially|部分"):
        tool_fns(register_modification_tools, fake_provider)["remove_elements"](ids=[7, 8, 9])
    assert calls == [7, 8]
    assert fake_provider._mdb.count("remove_elements") == 0
    assert fake_provider._mdb.count("update_model") == 0


def test_explicit_cleanup_preserves_the_requested_selection(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)["remove_elements"](ids="7to9by2", remove_free_nodes=True)
    assert [header for header, _ in requests] == ["REMOVE-ELEMENTS", "UPDATE"]
    assert requests[0][1]["ids"] == [7, 9]
    assert requests[0][1]["remove_free"] is True


def test_empty_model_does_not_send_a_global_delete(fake_provider):
    fake_provider.get_element_data = lambda **kwargs: []
    fake_provider.remove_elements()
    fake_provider.remove_elements(remove_free=True)
    assert fake_provider._mdb.calls == []
