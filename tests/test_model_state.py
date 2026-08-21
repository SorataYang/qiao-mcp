"""Model lifecycle state and MCP operation guard tests."""

import pytest
from conftest import ready_model_state, tool_fns

from qiao_mcp.tools import register_modeling_tools
from qiao_mcp.tools.api_gateway import register_api_gateway_tools
from qiao_mcp.tools.checking import register_checking_tools
from qiao_mcp.tools.envelope import ToolError, _operation_for
from qiao_mcp.tools.modifications import register_modification_tools
from qiao_mcp.tools.queries import register_query_tools


def state_with(**updates):
    result = ready_model_state()
    model = result["model_state"]
    for key, value in updates.items():
        if key == "capabilities":
            model["capabilities"].update(value)
        else:
            model[key] = value
    return result


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("get_model_status", "connection"),
        ("create_nodes", "model_write"),
        ("get_model_info", "model_read"),
        ("get_analysis_results", "result_read"),
        ("run_analysis", "analysis_run"),
        ("set_view_angle", "view"),
        ("update_construction_stage", "stage_write"),
        ("initialize_model", "lifecycle"),
        ("setup_concrete_check", "check_write"),
        ("get_check_data", "check_read"),
        ("run_concrete_check", "check_run"),
        ("get_tendon_loss_results", "result_read"),
        ("get_tendon_position_result", "result_read"),
        ("calculate_section_property", "model_read"),
        ("set_render", "view"),
        ("reset_display", "view"),
        ("set_unit", "view"),
        ("change_construct_stage", "view"),
    ],
)
def test_tool_operation_classification(name, expected):
    assert _operation_for(name) == expected


def test_get_model_status_returns_structured_snapshot(fake_provider):
    fns = tool_fns(register_api_gateway_tools, fake_provider)
    result = fns["get_model_status"]()
    assert result["status"] == "model_state"
    assert result["model_state"]["is_base_stage"] is True
    assert result["model_state"]["capabilities"]["modify_model"] is True


def test_model_write_is_blocked_without_open_model(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        model_opened=False,
        phase="start_page",
        stage_name=None,
        is_base_stage=False,
        capabilities={"modify_model": False},
    )
    fns = tool_fns(register_modeling_tools, fake_provider)

    with pytest.raises(ToolError) as exc:
        fns["create_nodes"](node_data=[[0.0, 0.0, 0.0]])

    assert "model_write" in str(exc.value)
    assert fake_provider._mdb.calls == []


def test_model_write_is_blocked_in_postprocessing(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        phase="postprocessing",
        stage_name="运营阶段",
        is_base_stage=False,
        has_result_data=True,
        capabilities={"modify_model": False, "query_results": True},
    )
    fns = tool_fns(register_modeling_tools, fake_provider)

    with pytest.raises(ToolError):
        fns["create_nodes"](node_data=[[0.0, 0.0, 0.0]])

    assert fake_provider._mdb.calls == []


def test_result_read_requires_result_capability(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        capabilities={"query_results": False}
    )
    fake_provider.get_vibration_modal_results = lambda mode: []
    fns = tool_fns(register_query_tools, fake_provider)

    with pytest.raises(ToolError):
        fns["get_special_results"](kind="vibration_modal")


def test_run_check_requires_result_data(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        capabilities={"run_check": False}
    )
    fns = tool_fns(register_checking_tools, fake_provider)

    with pytest.raises(ToolError):
        fns["run_concrete_check"](name="C1")


def test_run_check_is_allowed_with_result_data(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        phase="postprocessing",
        stage_name="运营阶段",
        is_base_stage=False,
        has_result_data=True,
        capabilities={"run_check": True},
    )
    fns = tool_fns(register_checking_tools, fake_provider)

    fns["run_concrete_check"](name="C1")
    assert fake_provider._cdb.last("solve_concrete_check") is not None


def test_check_setup_is_allowed_before_analysis(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        has_result_data=False,
        capabilities={"check_model": True, "run_check": False},
    )
    fns = tool_fns(register_checking_tools, fake_provider)

    fns["setup_concrete_check"](name="C1")
    assert fake_provider._cdb.last("add_concrete_check_case") is not None


def test_lifecycle_is_blocked_while_solving(fake_provider):
    fake_provider.get_model_state = lambda: state_with(
        phase="solving",
        is_solving=True,
    )
    fns = tool_fns(register_modification_tools, fake_provider)

    with pytest.raises(ToolError) as exc:
        fns["initialize_model"](confirm=True)

    assert "正在求解" in str(exc.value)


def test_lifecycle_requires_known_state(fake_provider):
    fake_provider.get_model_state = lambda: {
        "status": "state_unknown",
        "message": "状态不可用",
        "action": "升级桥通",
    }
    fns = tool_fns(register_modification_tools, fake_provider)

    with pytest.raises(ToolError) as exc:
        fns["initialize_model"](confirm=True)

    assert "状态不可用" in str(exc.value)
