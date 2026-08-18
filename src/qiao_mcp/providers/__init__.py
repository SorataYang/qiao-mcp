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

import os
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

    def unavailable_reason(self) -> str:
        """Actionable reason the backend is unusable, or "" when it is usable.

        属于稳定契约：server 启动日志与工具层都要向用户解释"为什么用不了"，
        不能去读某个 Provider 的私有属性——那样换后端就会 AttributeError。

        默认实现兼容以 `_unavailable_reason` 记录原因的适配器；新后端可以
        直接覆写本方法，无需沿用那个属性名。
        """
        return getattr(self, "_unavailable_reason", "") or ""

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
    def run_analysis(self, read_timeout: int = 3600) -> None:
        """Run the structural analysis (执行计算/分析). read_timeout: 最大等待秒数。"""
        ...

    # ── 开放扩展面 ─────────────────────────────────────────────────────
    # 建模/查询/分析等大量后端方法不在此逐一声明，由具体 Provider 实现。
    # 该存根让类型检查器接受 provider.<any_method>(...) 的转发式调用。
    if False:  # 仅供静态分析；运行时由具体 Provider 的真实方法提供
        def __getattr__(self, name: str) -> Callable[..., Any]: ...


# ── Provider 选择 ──────────────────────────────────────────────────────

#: 环境变量名：选择后端适配器。
PROVIDER_ENV = "BRIDGE_PROVIDER"

#: 默认后端。改动前请确认 README 与 INTEGRATION_GUIDE 的说明同步更新。
DEFAULT_PROVIDER = "qtmodel"

#: 已注册的后端：{取值: (模块路径, 类名)}。
#:
#: 用惰性导入的字符串而非直接 import 类，这样一个后端的依赖缺失
#: 不会连带拖垮其它后端——例如未装 qtmodel 的环境仍能选用别的适配器。
#: 新增后端只需在此登记一行，并让该类实现 BridgeProvider。
_PROVIDERS: dict[str, tuple[str, str]] = {
    "qtmodel": ("qiao_mcp.providers.qtmodel_provider", "QtModelProvider"),
}


def available_providers() -> list[str]:
    """Return the registered provider keys (已注册的后端取值列表)."""
    return sorted(_PROVIDERS)


def create_provider(name: str | None = None) -> "BridgeProvider":
    """Instantiate a backend adapter by name (按名称构造后端适配器).

    name 为 None 时读取 BRIDGE_PROVIDER 环境变量，未设置则用 DEFAULT_PROVIDER。
    取值不区分大小写并忽略首尾空白，因为它多半来自 shell 配置或 MCP 客户端的
    JSON，那里最容易混进大写和空格。

    未知取值直接抛 ValueError 并列出可选项——**不静默回落到默认后端**。
    回落会让写错名字的人以为连上了自己想用的软件，实际连的是另一个，
    这种误解要到建模结果出错时才会暴露。
    """
    requested = name if name is not None else os.environ.get(PROVIDER_ENV, "")
    key = (requested or DEFAULT_PROVIDER).strip().lower()

    if key not in _PROVIDERS:
        raise ValueError(
            f"Unknown bridge provider {key!r}. "
            f"Available: {', '.join(available_providers())}. "
            f"Set the {PROVIDER_ENV} environment variable to one of these "
            f"(未知的后端名称，请设置 {PROVIDER_ENV} 为上述取值之一)."
        )

    module_path, class_name = _PROVIDERS[key]
    try:
        module = __import__(module_path, fromlist=[class_name])
    except ImportError as e:
        # 后端自身的依赖缺失（如未安装 qtmodel）——区别于"名字写错"，
        # 这里要点明是依赖问题，否则用户会去改 BRIDGE_PROVIDER 而非装包。
        raise ImportError(
            f"Provider {key!r} is registered but its dependencies are missing "
            f"({type(e).__name__}: {e}). Install the backend package, or select "
            f"another provider via {PROVIDER_ENV} "
            f"(后端依赖缺失，请安装对应包或改用其它后端)."
        ) from e

    return getattr(module, class_name)()
