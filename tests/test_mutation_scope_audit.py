"""Regression checks for ID scope, readback failures and partial model writes."""

from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools.envelope import ToolError
from qiao_mcp.tools.modifications import register_modification_tools
from qiao_mcp.tools.queries import register_query_tools


@pytest.mark.parametrize("name", ["remove_nodes", "remove_elements"])
@pytest.mark.parametrize("ids", ["", "  ", [], ";", True, 1.5, [1.5], [True], [None], "0", "-1to2"])
def test_invalid_ids_never_turn_into_delete_all(fake_provider, name, ids):
    functions = tool_fns(register_modification_tools, fake_provider)
    with pytest.raises(ToolError):
        functions[name](ids=ids)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("name", ["remove_nodes", "remove_elements"])
def test_explicit_confirmed_delete_all_still_works(qtmodel_wire, name):
    provider, requests = qtmodel_wire
    functions = tool_fns(register_modification_tools, provider)
    functions[name](ids=None, confirm_delete_all=True)
    assert [header for header, _ in requests] == [name.replace("_", "-").upper(), "UPDATE"]
    assert requests[0][1] is None


@pytest.mark.parametrize("name", ["remove_nodes", "remove_elements"])
def test_text_is_not_an_explicit_delete_all_confirmation(fake_provider, name):
    functions = tool_fns(register_modification_tools, fake_provider)
    functions[name](ids=None, confirm_delete_all="false")
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("name, key", [("renumber_nodes", "ids"), ("renumber_elements", "element_ids")])
@pytest.mark.parametrize("ids, new_ids", [
    ([1], None), (None, [2]), ([], []), ("", ""), ([1, 2], [3]),
    ([1, 1], [2, 3]), ([1, 2], [3, 3]), ([1.5], [3]), ([1], [True]),
])
def test_incomplete_renumber_mapping_never_reaches_sdk(fake_provider, name, key, ids, new_ids):
    functions = tool_fns(register_modification_tools, fake_provider)
    with pytest.raises(ToolError):
        functions[name](**{key: ids, "new_ids": new_ids})
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("name, key, wire_key", [
    ("renumber_nodes", "ids", "node_ids"), ("renumber_elements", "element_ids", "element_ids"),
])
def test_renumber_ranges_are_expanded_to_ordered_lists(qtmodel_wire, name, key, wire_key):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)[name](**{key: "1to5by2", "new_ids": "7to9"})
    assert requests[0][1][wire_key] == [1, 3, 5]
    assert requests[0][1]["new_ids"] == [7, 8, 9]
    assert requests[1][0] == "UPDATE"


@pytest.mark.parametrize("name", ["renumber_nodes", "renumber_elements"])
def test_omitting_both_renumber_lists_keeps_explicit_global_mode(qtmodel_wire, name):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)[name]()
    assert requests[0][1] is None
    assert requests[1][0] == "UPDATE"


def test_group_removal_is_committed_once(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)["remove_from_structure_group"](group_name="G", element_ids=[7])
    assert [header for header, _ in requests] == ["REMOVE-STRUCTURE-FROM-GROUP", "UPDATE"]


@pytest.mark.parametrize("tool", ["add_to_structure_group", "remove_from_structure_group"])
@pytest.mark.parametrize("selection", [{}, {"node_ids": ""}, {"element_ids": []}, {"element_ids": [True]}])
def test_group_membership_requires_an_explicit_valid_selection(fake_provider, tool, selection):
    with pytest.raises(ToolError):
        tool_fns(register_modification_tools, fake_provider)[tool](group_name="G", **selection)
    assert fake_provider._mdb.calls == []


def test_remove_all_with_free_nodes_uses_actual_ids(qtmodel_wire):
    provider, requests = qtmodel_wire
    provider.get_element_data = lambda: [{"index": 7}, {"index": 90}]
    tool_fns(register_modification_tools, provider)["remove_elements"](
        confirm_delete_all=True, remove_free_nodes=True,
    )
    assert requests[0][0] == "REMOVE-ELEMENTS"
    assert requests[0][1]["ids"] == [7, 90]
    assert requests[0][1]["remove_free"] is True


def test_element_type_query_passes_one_id(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_query_tools, provider)["find_entities"](by="element_type", ids=[7])
    assert requests[0][1]["element_id"] == 7


@pytest.mark.parametrize("ids", [[1, 2], "1to2", [], True, 0])
def test_element_type_query_rejects_non_single_id(fake_provider, ids):
    with pytest.raises(ToolError, match="one positive integer"):
        tool_fns(register_query_tools, fake_provider)["find_entities"](by="element_type", ids=ids)
    assert fake_provider._mdb.calls == []


@pytest.mark.parametrize("method, arguments", [
    ("add_nodes", {"node_data": [[0, 0, 0]]}),
    ("add_node_tandem", {"name": "T", "node_ids": [1, 2]}),
    ("remove_structure_from_group", {"name": "G", "element_ids": [7]}),
])
def test_commit_failure_explains_partial_write_without_replaying(fake_provider, method, arguments):
    fake_provider._mdb.update_model = Mock(side_effect=RuntimeError("commit rejected"))
    with pytest.raises(RuntimeError, match="earlier writes may have changed"):
        getattr(fake_provider, method)(**arguments)
    assert fake_provider._mdb.count(method) == 1
    fake_provider._mdb.update_model.assert_called_once_with()
