"""自重相关工具行为测试。

回归 review 的 P0：apply_self_weight 曾是纯 no-op 却报告"已施加自重"，
且 LLM 指令谎称"建工况即含自重"。
现自重由施工阶段计自重设置控制，工具须真实下发对应 qtmodel 调用。
"""

import pytest
from conftest import tool_fns

from qiao_mcp.tools import register_modeling_tools


@pytest.fixture
def fns(fake_provider):
    return tool_fns(register_modeling_tools, fake_provider)


def test_no_phantom_apply_self_weight_tool(fns):
    assert "apply_self_weight" not in fns, "误导性的 apply_self_weight 应已移除"
    assert "set_self_weight_stage" in fns
    assert "set_gravity" in fns


def test_set_self_weight_stage_dispatches_weight_stage(fake_provider, fns):
    fns["set_self_weight_stage"](
        stage_name="施工阶段1", structure_group_name="主梁组", weight_stage_id=1
    )
    _, _, kw = fake_provider._mdb.last("update_weight_stage")
    assert kw == {
        "name": "施工阶段1",
        "structure_group_name": "主梁组",
        "weight_stage_id": 1,
    }


def test_set_gravity_updates_project_setting(fake_provider, fns):
    fns["set_gravity"](gravity=9.81)
    _, _, kw = fake_provider._mdb.last("update_project_setting")
    assert kw == {"gravity": 9.81}


def test_llm_instructions_do_not_claim_load_case_holds_self_weight(fake_provider):
    text = fake_provider.get_llm_instructions()
    assert "NO element loads needed" not in text
    # 不再宣称"建一个自重工况即可"
    assert "Self-weight is now included" not in text
    assert "set_self_weight_stage" in text
