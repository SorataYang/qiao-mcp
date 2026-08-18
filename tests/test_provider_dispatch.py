"""后端选择（BRIDGE_PROVIDER）与 unavailable_reason 契约测试。

在此之前 server.py 硬编码 `provider = QtModelProvider()`，而
INTEGRATION_GUIDE 已经承诺了 `BRIDGE_PROVIDER=qtmodel` —— 文档写了、代码
没实现。本项目的目标是成为多后端的中立入口（桥通之外还要接 MIDAS Civil
等），所以"选后端"必须是代码事实而非文档承诺。

两个设计决定在这里被锁住：

1. **未知取值必须报错，不得静默回落到默认后端。** 回落会让写错名字的人
   以为连上了自己想用的软件，实际连的是另一套，这种误解要到建模结果出错
   时才暴露 —— 属于最坏的一类失败。
2. **"不可用原因"是抽象契约的一部分。** 启动日志此前直接读
   QtModelProvider._unavailable_reason（私有属性），第二个后端接上就会在
   启动路径上 AttributeError。
"""

from __future__ import annotations

import pytest

from qiao_mcp.providers import (
    DEFAULT_PROVIDER,
    PROVIDER_ENV,
    BridgeProvider,
    available_providers,
    create_provider,
)


class StubProvider(BridgeProvider):
    """最小后端实现，模拟未来的 MIDAS 适配器。

    刻意**不**定义 `_unavailable_reason` —— 用来证明契约不依赖
    QtModelProvider 的私有属性命名。
    """

    @property
    def name(self) -> str:
        return "stub"

    @property
    def version(self) -> str:
        return "0.0.0"

    def is_available(self) -> bool:
        return False

    def get_software_name(self) -> str:
        return "Stub Backend"

    def get_llm_instructions(self) -> str:
        return ""

    def update_model(self) -> None: ...

    def get_model_summary(self) -> dict:
        return {}

    def validate_model(self) -> dict:
        return {}

    def run_analysis(self, read_timeout: int = 3600) -> None: ...


# ── 注册表 ────────────────────────────────────────────────────────────


def test_default_provider_is_registered():
    assert DEFAULT_PROVIDER in available_providers()


def test_qtmodel_is_available_as_a_choice():
    """桥通是当前唯一后端；新增后端时本断言仍应成立。"""
    assert "qtmodel" in available_providers()


# ── 选择逻辑 ──────────────────────────────────────────────────────────


def test_creates_default_provider_without_env(monkeypatch):
    monkeypatch.delenv(PROVIDER_ENV, raising=False)
    assert create_provider().name == DEFAULT_PROVIDER


def test_env_var_selects_provider(monkeypatch):
    monkeypatch.setenv(PROVIDER_ENV, "qtmodel")
    assert create_provider().name == "qtmodel"


def test_explicit_argument_overrides_env(monkeypatch):
    """显式传参优先于环境变量，便于测试与嵌入式调用。"""
    monkeypatch.setenv(PROVIDER_ENV, "qtmodel")
    assert create_provider("qtmodel").name == "qtmodel"


@pytest.mark.parametrize("raw", ["qtmodel", "QtModel", "QTMODEL", "  qtmodel  "])
def test_selection_tolerates_case_and_whitespace(raw):
    """取值多来自 shell 配置或 MCP 客户端 JSON，最容易混进大写与空格。"""
    assert create_provider(raw).name == "qtmodel"


def test_empty_env_falls_back_to_default(monkeypatch):
    """未设置与设为空串应等价 —— 空串是 shell 里常见的"没配"表现。"""
    monkeypatch.setenv(PROVIDER_ENV, "")
    assert create_provider().name == DEFAULT_PROVIDER


# ── 未知取值：报错，不回落 ────────────────────────────────────────────


@pytest.mark.parametrize("bad", ["midas", "qtmodl", "sap2000", "etabs"])
def test_unknown_provider_raises_instead_of_falling_back(bad):
    """拼错或选择未实现的后端必须失败。

    静默回落到 qtmodel 是最危险的行为：用户以为在驱动 MIDAS，实际在改
    桥通的模型。启动即失败远好于事后从错误的计算结果里发现。
    """
    with pytest.raises(ValueError) as exc:
        create_provider(bad)
    assert bad in str(exc.value), "错误消息应回显用户输入，便于定位拼写错误"


def test_unknown_provider_error_lists_valid_choices():
    """报错必须给出出路，而不是只说"不认识"。"""
    with pytest.raises(ValueError) as exc:
        create_provider("nonexistent-backend")
    message = str(exc.value)
    assert DEFAULT_PROVIDER in message, "应列出可选后端"
    assert PROVIDER_ENV in message, "应点明该改哪个环境变量"


def test_unknown_env_var_also_raises(monkeypatch):
    """经环境变量传入的错误取值同样不得被放过。"""
    monkeypatch.setenv(PROVIDER_ENV, "midas")
    with pytest.raises(ValueError):
        create_provider()


# ── unavailable_reason 契约 ───────────────────────────────────────────


def test_unavailable_reason_is_on_the_abstract_base():
    """必须由基类提供，否则启动日志只能去读具体后端的私有属性。"""
    assert "unavailable_reason" in vars(BridgeProvider)


def test_backend_without_private_attribute_does_not_crash():
    """回归：不带 _unavailable_reason 的后端调用该方法不应 AttributeError。

    这正是第二个后端接入时会踩到的启动路径。
    """
    assert StubProvider().unavailable_reason() == ""


def test_unavailable_reason_surfaces_qtmodel_detail():
    """兼容既有实现：qtmodel 用 _unavailable_reason 记录原因，应被读出。"""
    p = create_provider("qtmodel")
    p._unavailable_reason = "桥通软件尚未启动"
    assert p.unavailable_reason() == "桥通软件尚未启动"


def test_unavailable_reason_returns_str_when_attribute_is_none():
    """属性为 None 时也要返回字符串 —— 调用方直接拼进日志，不做判空。"""
    p = create_provider("qtmodel")
    p._unavailable_reason = None
    assert p.unavailable_reason() == ""


# ── 契约完备性 ────────────────────────────────────────────────────────


def test_stub_provider_satisfies_the_contract():
    """一个只实现抽象方法的后端应可被实例化。

    若此测试因缺少抽象方法而失败，说明有新的 @abstractmethod 加进了
    BridgeProvider —— 那是对所有后端作者的破坏性变更，需同步更新
    providers/__init__.py 顶部的"如何新增后端"说明。
    """
    stub = StubProvider()
    assert isinstance(stub, BridgeProvider)
    assert stub.get_software_name() == "Stub Backend"


def test_created_provider_satisfies_the_contract():
    p = create_provider()
    assert isinstance(p, BridgeProvider)
    assert isinstance(p.name, str) and p.name
    assert isinstance(p.get_software_name(), str) and p.get_software_name()
