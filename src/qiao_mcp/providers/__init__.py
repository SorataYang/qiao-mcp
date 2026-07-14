"""
Qiao-MCP Provider abstraction layer.
桥梁分析软件后端抽象层

BridgeProvider 定义所有后端适配器都必须实现的**稳定契约**——身份、
可用性、面向 LLM 的软件规则，以及少数生命周期操作。

除此之外的建模/查询/分析方法数量庞大且随后端演进，不适合逐一在此
枚举（历史上曾声明 100+ 抽象方法，其中多数与具体实现漂移、沦为装饰）。
这些方法由各 Provider 直接实现，工具层按需调用；`__getattr__` 的类型
存根让静态检查器理解"其余方法转发给后端"这一开放扩展面。

要新增一个后端（如 MIDAS/SAP2000 适配器），实现下方抽象方法并提供
工具层实际调用的那些建模/查询/分析方法即可。
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class BridgeProvider(ABC):
    """Abstract base for bridge-analysis software adapters (桥梁分析软件后端抽象基类)."""

    # ── 稳定契约：身份与可用性 ─────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'qtmodel')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider version string."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend software is available and properly configured."""
        ...

    @abstractmethod
    def get_software_name(self) -> str:
        """Human-readable backend name (e.g., 'QiaoTong (桥通)')."""
        ...

    @abstractmethod
    def get_llm_instructions(self) -> str:
        """Software-specific behavioral rules injected into the MCP system prompt.

        每个 Provider 说明自己的约定，使 LLM 无论对接哪个后端都能正确行事。
        """
        ...

    # ── 生命周期（工具层高频依赖的通用操作）─────────────────────────────

    @abstractmethod
    def update_model(self) -> None:
        """Refresh the model view in the backend software. 刷新模型界面"""
        ...

    @abstractmethod
    def get_model_summary(self) -> dict[str, Any]:
        """Return counts of nodes/elements/materials/… 模型概要统计。"""
        ...

    @abstractmethod
    def validate_model(self) -> dict[str, Any]:
        """Validate the model; returns {is_valid, errors, warnings, summary}. 验证模型。"""
        ...

    @abstractmethod
    def run_analysis(self) -> None:
        """Run the structural analysis (执行计算/分析)."""
        ...

    # ── 开放扩展面 ─────────────────────────────────────────────────────
    # 建模/查询/分析等大量后端方法不在此逐一声明，由具体 Provider 实现。
    # 该存根让类型检查器接受 provider.<any_method>(...) 的转发式调用。
    if False:  # 仅供静态分析；运行时由具体 Provider 的真实方法提供
        def __getattr__(self, name: str) -> Callable[..., Any]: ...
