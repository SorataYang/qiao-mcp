"""remove_boundary 边界类型枚举映射测试。

qtmodel 的 remove_boundary 只接受中文 kind 标识
（"一般支承"/"主从约束"/"梁端约束"...），
工具层的英文 token 必须映射为中文后再下发。
"""

import pytest
from conftest import tool_fns

from qiao_mcp.tools.advanced_boundary import register_advanced_boundary_tools
from qiao_mcp.tools.envelope import ToolInputError


def _fns(fake_provider):
    return tool_fns(register_advanced_boundary_tools, fake_provider)


def test_english_kind_mapped_to_chinese(fake_provider):
    fns = _fns(fake_provider)
    result = fns["remove_boundary"](remove_id=11, kind="master_slave")
    _, _, kwargs = fake_provider._mdb.last("remove_boundary")
    assert kwargs["kind"] == "主从约束"
    assert result["status"] == "success"


def test_all_english_tokens_map_to_valid_chinese(fake_provider):
    fns = _fns(fake_provider)
    expected = {
        "support": "一般支承",
        "elastic_support": "弹性支承",
        "general_elastic_support": "一般弹性支承",
        "master_slave": "主从约束",
        "elastic_link": "一般弹性连接",
        "tension_elastic_link": "受拉弹性连接",
        "compression_elastic_link": "受压弹性连接",
        "rigid_elastic_link": "刚性弹性连接",
        "constraint_equation": "约束方程",
        "beam_constraint": "梁端约束",
    }
    for token, chinese in expected.items():
        fns["remove_boundary"](remove_id=1, kind=token)
        _, _, kwargs = fake_provider._mdb.last("remove_boundary")
        assert kwargs["kind"] == chinese, f"{token} 应映射为 {chinese}"


def test_chinese_kind_passthrough(fake_provider):
    fns = _fns(fake_provider)
    fns["remove_boundary"](remove_id=3, kind="梁端约束")
    _, _, kwargs = fake_provider._mdb.last("remove_boundary")
    assert kwargs["kind"] == "梁端约束"


def test_unknown_kind_rejected_without_dispatch(fake_provider):
    fns = _fns(fake_provider)
    with pytest.raises(ToolInputError):
        fns["remove_boundary"](remove_id=1, kind="bogus")
    assert fake_provider._mdb.count("remove_boundary") == 0, "无效类型不得下发删除请求"


def test_extra_name_forwarded(fake_provider):
    fns = _fns(fake_provider)
    fns["remove_boundary"](remove_id=12, kind="constraint_equation", extra_name="约束方程1")
    _, _, kwargs = fake_provider._mdb.last("remove_boundary")
    assert kwargs["extra_name"] == "约束方程1"
