"""Use actual CDB request constructors for the checking audit regressions."""


import pytest
from conftest import tool_fns

from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolError


@pytest.mark.parametrize("status", [
    None, {}, "", "success", {"is_running": False},
    {"state": "succeeded", "ok": False},
    {"state": "succeeded", "is_running": True},
])
def test_check_completion_requires_unambiguous_success(fake_provider, status):
    calls = []

    def stopped(**kwargs):
        calls.append(kwargs)
        return status

    fake_provider._cdb.solve_concrete_check = stopped
    functions = tool_fns(register_checking_tools, fake_provider)
    with pytest.raises(ToolError, match="did not complete"):
        functions["run_concrete_check"](name="C1")
    assert len(calls) == 1


