"""Regression checks for ID scope, readback failures and partial model writes."""

from unittest.mock import Mock

import pytest
from conftest import tool_fns

from qiao_mcp.tools.modifications import register_modification_tools


def test_group_removal_is_committed_once(qtmodel_wire):
    provider, requests = qtmodel_wire
    tool_fns(register_modification_tools, provider)["remove_from_structure_group"](group_name="G", element_ids=[7])
    assert [header for header, _ in requests] == ["REMOVE-STRUCTURE-FROM-GROUP", "UPDATE"]


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
