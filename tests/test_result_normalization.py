"""查询结果规范化测试。

qtmodel 的查询返回自定义数据对象，工具层最终走 json.dumps(default=str)。
若对象未被拍平为普通 dict，序列化结果会是**字符串化的 Python dict**——
形如 "{'index': 1, 'node_ids': [5, 4]}"（单引号、外层再套双引号）。
这种输出对 LLM 是有害的：它看起来像数据，但取任何字段都要二次解析。

实测 qtmodel 2.6.3：只有 Node 提供 to_dict()，Element/Material/ElasticLink
等 40+ 个数据类一律没有，因此 `_to_dicts` 必须能靠 __dict__ 兜底。
"""

from __future__ import annotations

import json

from qiao_mcp.providers.qtmodel_provider import QtModelProvider

_to_dicts = QtModelProvider._to_dicts


class FakeElement:
    """仿 qtmodel.core.model_db.Element：有 __dict__，无 to_dict()。"""

    def __init__(self, index: int, node_ids: list[int]):
        self.ele_type = "BEAM"
        self.node_ids = node_ids
        self.index = index
        self.mat_id = 1
        self.sec_id = 1
        self.beta_angle = 0.0


class FakeNode:
    """仿 qtmodel.core.model_db.Node：提供 to_dict()，须优先使用它。"""

    def __init__(self, node_id: int, x: float):
        self.node_id = node_id
        self.x = x
        self.y = 0.0
        self.z = 0.0
        # 上游 to_dict() 的字段命名可能与属性名不同，必须尊重它
        self._internal = "should not leak"

    def to_dict(self):
        return {"node_id": self.node_id, "x": self.x, "y": self.y, "z": self.z}


# ── 核心回归：无 to_dict() 的对象必须被拍平 ────────────────────────────


def test_object_without_to_dict_is_flattened():
    """Element 类对象缺 to_dict()，必须靠 __dict__ 拍平为真 dict。"""
    out = _to_dicts([FakeElement(1, [5, 4])])
    assert isinstance(out[0], dict), (
        "无 to_dict() 的对象未被拍平；json.dumps(default=str) 会把它变成"
        "字符串化 dict，LLM 需二次解析才能取字段"
    )
    assert out[0]["index"] == 1
    assert out[0]["node_ids"] == [5, 4]


def test_flattened_result_survives_json_roundtrip():
    """判据落在最终出口：序列化后字段必须仍可直接索引。"""
    out = _to_dicts([FakeElement(7, [2, 3])])
    revived = json.loads(json.dumps(out, ensure_ascii=False, default=str))
    assert revived[0]["node_ids"] == [2, 3]
    assert isinstance(revived[0], dict)


def test_no_stringified_dict_in_serialized_output():
    """反向断言：输出里不能出现 "{'...'}" 这种字符串化 dict。"""
    payload = json.dumps(
        _to_dicts([FakeElement(1, [1, 2]), FakeElement(2, [2, 3])]),
        ensure_ascii=False,
        default=str,
    )
    assert "\"{'" not in payload, f"仍存在字符串化 dict: {payload[:120]}"


# ── to_dict() 优先级 ──────────────────────────────────────────────────


def test_to_dict_takes_precedence_over_dunder_dict():
    """有 to_dict() 时必须用它，以尊重上游的字段命名与筛选。"""
    out = _to_dicts([FakeNode(1, 12.0)])
    assert out[0] == {"node_id": 1, "x": 12.0, "y": 0.0, "z": 0.0}
    assert "_internal" not in out[0], "应使用 to_dict() 而非 __dict__"


def test_private_attributes_are_dropped_when_flattening():
    """靠 __dict__ 兜底时，下划线开头的内部字段不应外泄给 LLM。"""

    class WithPrivate:
        def __init__(self):
            self.visible = 1
            self._hidden = "internal"

    out = _to_dicts([WithPrivate()])
    assert out[0] == {"visible": 1}


def test_flattening_copies_and_does_not_mutate_source():
    """拍平结果应是拷贝，调用方改动不得写回 qtmodel 对象。"""
    ele = FakeElement(1, [5, 4])
    out = _to_dicts([ele])
    out[0]["index"] = 999
    assert ele.index == 1


# ── 边界：不该被拍平的输入 ────────────────────────────────────────────


def test_plain_dicts_pass_through():
    rows = [{"node_id": 1, "x": 0.0}]
    assert _to_dicts(rows) == rows


def test_single_dict_is_wrapped_in_list():
    assert _to_dicts({"node_id": 1}) == [{"node_id": 1}]


def test_scalars_are_left_alone():
    """结构组名之类的字符串列表必须原样透传，不能被误拍平。"""
    assert _to_dicts(["组1", "组2"]) == ["组1", "组2"]
    assert _to_dicts([1, 2.5, True]) == [1, 2.5, True]


def test_none_and_non_list_inputs():
    assert _to_dicts(None) == []
    assert _to_dicts("not a list") == []
    assert _to_dicts(42) == []


def test_mixed_list_flattens_only_objects():
    out = _to_dicts([{"a": 1}, FakeElement(2, [1, 2]), "组名"])
    assert out[0] == {"a": 1}
    assert isinstance(out[1], dict) and out[1]["index"] == 2
    assert out[2] == "组名"


def test_object_with_empty_dict_is_left_alone():
    """__dict__ 为空的对象拍平后无信息，应原样保留而非退化成 {}。"""

    class Empty:
        pass

    obj = Empty()
    assert _to_dicts([obj]) == [obj]


# ── 与真实 qtmodel 类型的对照 ─────────────────────────────────────────


def test_real_qtmodel_element_lacks_to_dict():
    """守住本修复的前提：一旦上游给 Element 加了 to_dict()，此断言会失败，
    提示复核 _to_dicts 的降级顺序是否仍然必要。"""
    from qtmodel.core.model_db import Element, Node

    assert not hasattr(Element, "to_dict"), (
        "qtmodel 已为 Element 提供 to_dict()，请复核 _to_dicts 的兜底逻辑"
    )
    assert hasattr(Node, "to_dict"), "Node 一直提供 to_dict()，若消失需同步调整"


def test_real_element_instance_is_flattened():
    """用真实 Element 实例（非仿制）验证拍平结果含全部字段。"""
    from qtmodel.core.model_db import Element

    ele = Element(index=3, ele_type="BEAM", node_ids=[3, 2], mat_id=1, sec_id=1)
    out = _to_dicts([ele])
    assert isinstance(out[0], dict)
    for field in ("index", "ele_type", "node_ids", "mat_id", "sec_id", "beta_angle"):
        assert field in out[0], f"拍平结果缺字段 {field}"
    assert out[0]["node_ids"] == [3, 2]
