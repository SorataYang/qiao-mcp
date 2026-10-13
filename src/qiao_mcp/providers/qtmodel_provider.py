"""
QTModel Provider — adapter for 桥通 (QiaoTong) bridge analysis software.

This provider wraps the `qtmodel` Python API (mdb/odb/cdb) to implement
the BridgeProvider interface.

桥通软件后端适配器，封装 qtmodel Python API。
"""

import ast
import json
import math
import time
from collections.abc import Mapping
from typing import Any

from qiao_mcp.providers import BridgeProvider


class QtModelProvider(BridgeProvider):
    """
    Provider for QiaoTong bridge analysis software via the `qtmodel` Python API.

    The qtmodel API exposes three main objects:
    - mdb: Model database (querying / building / modifying the model)
    - odb: Output database (querying results and visualization)
    - cdb: Check database (structural verification)

    桥通软件 qtmodel API 适配器。
    """

    # 连通性探测结果的缓存时长（秒）。探测要走 HTTP，不能每次调用都发；
    # 但也不能永久缓存——用户常常先起 MCP、后开桥通，缓存必须能自愈。
    _PROBE_TTL = 3.0

    # 类级默认值：测试普遍用 __new__ 跳过 __init__ 注入假 mdb/odb/cdb，
    # 没有这两个默认值，那些实例一调 is_available() 就 AttributeError。
    _probe_cache: dict[str, Any] | None = None
    _probe_at: float = 0.0

    def __init__(self):
        """Initialize the qtmodel provider and bind the qtmodel API objects.

        只做 import 与绑定，**不做**网络探测：MCP server 在 import 期就构造
        provider，而探测最坏要枚举 461 个候选端口（psutil 在 macOS 上常因
        AccessDenied 回退到逐端口连接），不能让 server 启动同步等待。
        真实连通性由 is_available() 惰性探测并缓存。
        """
        self._mdb = None
        self._odb = None
        self._cdb = None
        self._available = False
        self._unavailable_reason = ""
        self._probe_cache: dict[str, Any] | None = None
        self._probe_at = 0.0
        self._try_import()

    def _try_import(self):
        """Import qtmodel and bind mdb/odb/cdb.

        注意：绑定 qtmodel.mdb/odb/cdb **不会**因桥通未启动而抛错——这三个
        对象是惰性的，只有真正调用其方法时才发 HTTP。因此下面的 except 分支
        实际只拦得住 import 期的异常（如依赖缺失），"软件没启动"走不到这里，
        由 is_available() / get_connection_status() 负责识别。
        """
        try:
            import qtmodel
            self._mdb = qtmodel.mdb
            self._odb = qtmodel.odb
            self._cdb = qtmodel.cdb
            self._available = True
        except ImportError as exc:
            self._available = False
            if exc.name == "qtmodel":
                self._unavailable_reason = (
                    "qtmodel package not found. Run: uv add qtmodel "
                    "(qtmodel 包未安装，请运行: uv add qtmodel)"
                )
            else:
                self._unavailable_reason = (
                    f"qtmodel import failed ({type(exc).__name__}: {exc}). "
                    "Install a complete qtmodel release and its dependencies. "
                    "(qtmodel 导入失败，请安装完整发行版并检查缺失的模块或依赖)"
                )
        except Exception as e:
            # qtmodel is installed but QiaoTong software is likely not running.
            # qtmodel 2.6 起能区分"软件未启动"与"桥通 API 版本不匹配"，
            # 后者要求用户升级软件而非启动软件，必须分开告知。
            self._available = False
            detail = self._handshake_detail()
            self._unavailable_reason = detail or (
                f"qtmodel imported but connection failed ({type(e).__name__}: {e}). "
                "Please ensure QiaoTong software is running. "
                "(qtmodel 已安装，但连接失败，请确保桥通软件已启动)"
            )

    @staticmethod
    def _handshake_detail() -> str:
        """Return a precise reason from qtmodel's version handshake, or "" if unavailable."""
        try:
            from qtmodel.core.qt_server import QtServer

            probe = getattr(QtServer, "get_connection_status", None)
            if probe is None:
                return ""
            status = probe()
        except Exception:
            return ""
        if not isinstance(status, dict) or status.get("status") == "connected":
            return ""
        message = str(status.get("message", "")).strip()
        action = str(status.get("action", "")).strip()
        return " ".join(p for p in (message, action) if p)

    def get_connection_status(self) -> dict[str, Any]:
        """Probe QiaoTong and return an actionable, structured connection status.

        qtmodel 2.6 起提供 QtServer.get_connection_status()，返回带 message 与
        action 的结构化状态，比 is_available() 的布尔值有用得多。

        注意各版本可返回的状态并不相同：
        - 2.6/2.7：connected / version_mismatch（桥通 API 版本与 qtmodel 不精确
          相符）/ software_not_running。
        - 2.8.2 起：**version_mismatch 已被移除**，探测到桥通即返回
          connected 且 compatible 恒为 True，只余 connected /
          software_not_running 两态。跨版本混用不再被拦下。

        故调用方不可假定 version_mismatch 仍会出现；判定可用性请用
        is_available() 的 connected + compatible 组合，它对两代行为都成立。

        qtmodel 未安装或该 API 不存在时降级为本地推断的状态，保证工具永不抛错。
        """
        try:
            from qtmodel.core.qt_server import QtServer
        except ImportError:
            return {
                "status": "qtmodel_not_installed",
                "connected": False,
                "compatible": None,
                "message": "qtmodel 包未安装。",
                "action": "运行 uv add qtmodel 或重装 qiao-mcp。",
            }

        probe = getattr(QtServer, "get_connection_status", None)
        if probe is None:
            # qtmodel < 2.6：无握手 API，只能回报本地探测结果
            return {
                "status": "unknown",
                "connected": self._available,
                "compatible": None,
                "message": (
                    f"当前 qtmodel {self.version} 不提供连接状态查询"
                    "（2.6 起可用）。"
                ),
                "action": self._unavailable_reason or "无需处理。",
                "client": {"qtmodel_version": self.version},
            }

        try:
            return probe()
        except Exception as e:
            return {
                "status": "probe_failed",
                "connected": False,
                "compatible": None,
                "message": f"探测桥通服务失败（{type(e).__name__}: {e}）。",
                "action": "确认桥通软件已启动，并检查 QIAOTONG_HTTP_URL 是否指向正确端口。",
                "client": {"qtmodel_version": self.version},
            }

    def get_model_state(self) -> dict[str, Any]:
        """Return the bridge-owned lifecycle and operation-capability snapshot.

        状态不可得有两种成因，处置完全不同，故用两个 status 区分：

        - ``guard_unavailable``：**qtmodel 侧**没有 get_model_state API。注意这与
          版本号无关：PyPI 上的 2.8.2 wheel（2026-08-20）是从上游 340e94e 打包的，
          该分支早于模型状态特性（67e2f03，2026-08-21）合入（5f4f4eb），因此没有
          这个方法；而上游源码（如 fb19a6a）仍标 2.8.2 却已带上它。同一个版本号
          下两种 qtmodel 并存，只能按能力探测、不能按版本判断。守卫能力不存在
          谈不上"状态未知"——沿用 2.6.x 的行为放行即可，否则装着 PyPI wheel 的
          用户一升级 qiao-mcp 就把全部工具锁死。
        - ``state_unknown``：qtmodel 有该 API，但**桥通**没在握手里给 model_state
          （桥通版本偏旧）。此时守卫可用而状态确实未知，必须 fail closed：
          2.8.2 已删除版本握手，这条阻断是"桥通太旧"的唯一信号。

        判定由 ensure_operation_allowed 消费，见其 guard_unavailable 分支。
        """
        try:
            from qtmodel.core.qt_server import QtServer
        except ImportError:
            return {
                "status": "qtmodel_not_installed",
                "connected": False,
                "compatible": None,
                "message": "qtmodel 包未安装。",
                "action": "运行 uv add qtmodel 或重装 qiao-mcp。",
            }

        probe = getattr(QtServer, "get_model_state", None)
        if probe is None:
            return {
                "status": "guard_unavailable",
                "connected": self._available,
                "compatible": None,
                "message": (
                    f"当前安装的 qtmodel {self.version} 不提供模型状态查询 API，"
                    "已跳过状态守卫。"
                ),
                "action": (
                    "如需状态感知保护，请安装带 get_model_state 的 qtmodel 构建"
                    "（2.9.0 起的 PyPI 正式发布，或上游源码 ≥ 5f4f4eb）并同步升级桥通。"
                ),
            }
        try:
            result = probe()
            return result if isinstance(result, dict) else {
                "status": "state_unknown",
                "message": "qtmodel 返回了无效的模型状态。",
                "action": "请升级 qtmodel 和桥通软件。",
            }
        except Exception as e:
            return {
                "status": "probe_failed",
                "connected": False,
                "compatible": None,
                "message": f"探测模型状态失败（{type(e).__name__}: {e}）。",
                "action": "确认桥通软件已启动并重试。",
            }

    def get_model_edit_readiness(self) -> dict[str, Any]:
        """Read edit preparation diagnostics without requiring edit permission."""
        method = getattr(self._mdb, "get_model_edit_readiness", None)
        if not callable(method):
            return {
                "status": "api_unavailable",
                "message": "当前 qtmodel 不提供 get_model_edit_readiness，无法判断编辑就绪状态。",
                "action": "请安装支持该 API 的 qtmodel；不要据此尝试修改模型。",
            }
        connection = self.get_connection_status()
        if connection.get("status") == "probe_failed":
            return {"status": "probe_failed", "connection": connection,
                    "message": "连接探测失败，编辑就绪状态未知。"}
        if connection.get("connected") is not True or connection.get("compatible") is False:
            return {"status": "not_connected", "connection": connection,
                    "message": "桥通连接不可用，编辑就绪状态未知。"}
        try:
            result = self._parse(method())
        except NotImplementedError as e:
            return {"status": "server_unsupported", "message": str(e),
                    "action": "请升级桥通以支持编辑就绪诊断。"}
        except Exception as e:
            return {"status": "probe_failed",
                    "message": f"编辑就绪探测失败（{type(e).__name__}: {e}）。"}
        if not isinstance(result, dict) or not result:
            return {
                "status": "state_unknown",
                "message": "桥通未返回有效编辑就绪数据，服务端可能不支持该接口；不能认定可编辑。",
                "action": "请检查桥通版本；不要自动切换阶段或删除结果。",
            }
        # The bridge owns all readiness fields. Never infer ready=True or retain its token.
        return {"status": "success", "readiness": result}

    def ensure_operation_allowed(self, operation: str) -> None:
        """Fail closed when the current bridge state rejects an MCP operation.

        唯一的放行例外是 guard_unavailable——所装 qtmodel 没有 get_model_state
        （PyPI 2.8.2 wheel 及更早版本），守卫能力缺失不等于状态危险，按 2.6.x 的
        旧行为放行（否则这些用户升级 qiao-mcp 后每个工具都会被锁死）。
        桥通侧的 state_unknown 仍 fail closed。
        """
        if operation == "connection":
            return

        result = self.get_model_state()
        if result.get("status") == "guard_unavailable":
            return

        state = result.get("model_state")
        if not isinstance(state, dict):
            message = str(result.get("message") or "桥通未提供模型状态快照。").strip()
            action = str(result.get("action") or "请先调用 get_model_status。").strip()
            raise RuntimeError(f"模型状态不可用：{message} {action}".strip())

        if operation == "lifecycle":
            if state.get("is_solving") is not False:
                raise RuntimeError(
                    "桥通当前正在求解，不能初始化模型或打开模型文件。"
                    "或当前求解状态未知，请等待求解结束并刷新状态后重试。"
                )
            return

        capability_by_operation = {
            "model_read": "read_model",
            "model_write": "modify_model",
            "stage_write": "modify_stage_data",
            "result_read": "query_results",
            "check_read": "check_model",
            "check_write": "check_model",
            "check_run": "run_check",
            "analysis_run": "run_analysis",
            "view": "view_model",
        }
        capability = capability_by_operation.get(operation)
        if capability is None:
            raise RuntimeError(f"未知的模型操作类型：{operation}")

        capabilities = state.get("capabilities")
        allowed = isinstance(capabilities, dict) and capabilities.get(capability) is True
        if allowed:
            return

        raise RuntimeError(
            "桥通当前状态不允许该操作："
            f"operation={operation}, capability={capability}, "
            f"model_opened={state.get('model_opened')}, "
            f"phase={state.get('phase')}, stage_name={state.get('stage_name')}, "
            f"is_base_stage={state.get('is_base_stage')}, "
            f"is_solving={state.get('is_solving')}, "
            f"has_result_data={state.get('has_result_data')}。"
            "请先调用 get_model_status，并由用户在桥通中切换到满足条件的状态。"
        )

    @property
    def name(self) -> str:
        return "qtmodel"

    @property
    def version(self) -> str:
        try:
            import qtmodel
            return getattr(qtmodel, "__version__", "unknown")
        except ImportError:
            return "not installed"

    def _probe_connection(self, force: bool = False) -> dict[str, Any] | None:
        """Probe QiaoTong's HTTP service, caching the result for _PROBE_TTL seconds.

        返回 qtmodel 的结构化状态字典；无法探测时返回 None（qtmodel 未安装，
        或 qtmodel < 2.6 没有握手 API）——"探不到"与"不可用"是两回事，
        调用方需自行决定降级策略。

        缓存是必需的：探测要发 HTTP，而 is_available() 可能被频繁调用；
        但缓存必须过期，因为用户常常先起 MCP server、后开桥通软件。
        """
        now = time.monotonic()
        cache = self._probe_cache
        if not force and cache is not None and now - self._probe_at < self._PROBE_TTL:
            return cache
        try:
            from qtmodel.core.qt_server import QtServer

            probe = getattr(QtServer, "get_connection_status", None)
            if probe is None:
                return None
            status = probe()
        except Exception:
            return None
        if not isinstance(status, dict):
            return None
        self._probe_cache = status
        self._probe_at = now
        return status

    def is_available(self) -> bool:
        """Report whether the backend is usable **right now**.

        绑定 qtmodel 对象成功不等于后端可用：桥通未启动、或桥通 API 版本与
        qtmodel 不精确匹配时，绑定照样成功（mdb/odb/cdb 是惰性的），直到真正
        调用方法才失败。此前本方法只回报 import 结果，于是无论桥通是否运行
        都返回 True，server 启动日志也总是打印"✅ loaded successfully"。

        因此在 import 成功的基础上再做一次连通性探测，结果缓存 _PROBE_TTL 秒。
        无法探测时（qtmodel < 2.6 无握手 API）退回 import 结果——缺少判定手段
        不等于后端不可用，此时保持原有的乐观行为。

        注意：探测会发 HTTP，故本方法不适合放在 import 期的热路径上。
        """
        if not self._available:
            return False
        status = self._probe_connection()
        if status is None:
            return True  # 无从判断，保持乐观
        # compatible is False 只可能来自 2.6/2.7 的 version_mismatch（connected=True
        # 但版本不符，同样不可用）；2.8.2 起该状态已不存在，compatible 恒为 True，
        # 此处的 `is not False` 对两代都成立，故无需按版本分支。
        usable = bool(status.get("connected")) and status.get("compatible") is not False
        if not usable:
            # server.py 与 _require_available 都会展示这条原因，必须填上探测结论，
            # 否则用户只看到"不可用"却不知道该启动软件还是升级软件
            detail = " ".join(
                p
                for p in (
                    str(status.get("message", "")).strip(),
                    str(status.get("action", "")).strip(),
                )
                if p
            )
            if detail:
                self._unavailable_reason = detail
        return usable

    def get_software_name(self) -> str:
        return "QiaoTong (桥通)"

    def get_llm_instructions(self) -> str:
        return """
        ### Model lifecycle and operation state (模型生命周期与操作状态)
        Before starting or resuming a workflow, call `get_model_status`.
        The bridge is the source of truth for whether a model is open, whether
        the UI is in preprocessing, solving, or postprocessing, whether the
        selected display stage is the base stage, and which operations are
        currently allowed. Do not switch stages or delete results automatically
        to work around a rejected operation; report the returned reason and ask
        the user to change the bridge state.

        ### Self-Weight (自重) — QiaoTong (桥通) computes it automatically from geometry
        Self-weight in QiaoTong is NOT a load case and NOT an element load. The solver
        computes it from geometry, material properties and project gravity. What you control
        is WHICH construction stage accounts for each structure group's self-weight.

        CORRECT approach:
        • One-shot bridge (一次成桥): create the model, then call merge_operation_stage
          — self-weight is included automatically. No self-weight load case is needed.
        • Staged construction: use set_self_weight_stage(stage_name, structure_group_name,
          weight_stage_id) to choose the stage that carries each group's self-weight
          (weight_stage_id: 0=none, 1=this stage, n=stage n).
        • Gravity defaults to 9.8 m/s²; change it with set_gravity if needed.

        DO NOT do this (WRONG for QiaoTong):
        ✗ Create a load case named "自重" and expect it to hold self-weight
        ✗ Calculate area × density × g manually
        ✗ Call apply_beam_distributed_load with self-weight kN/m values

        ### Node & Element creation — use batch tools to keep AI calls concise
        ✓ create_nodes_linear(count=101, start_x=0, spacing_x=1.0)   # 101 nodes in 1 call
        ✓ create_beam_elements_linear(node_id_start=1, count=100, mat_id=1, sec_id=1)
        ✗ Do not pass a raw list of 101 coordinate pairs to create_nodes

        ### Initialization — 危险操作
        • Only call initialize_model(confirm=True) when the user explicitly says "新建模型"
        • Never call it to fix your own mistakes — ask the user
        • remove_nodes / remove_elements require confirm_delete_all=True when deleting all

        ### Load case types (case_type must be a Chinese string):
        "施工阶段荷载" | "恒载" | "活载" | "制动力" | "风荷载"
        "体系温度荷载" | "梯度温度荷载"
        "长轨伸缩挠曲力荷载" | "脱轨荷载" | "长轨断轨力荷载"
        "船舶撞击荷载" | "汽车撞击荷载" | "用户定义荷载"

        ### Result Query (结果查询) — operation stage load case naming
        For ordinary static operation results (stage_id=-1), get_analysis_results
        defaults to case_name_mode="static" and adds "ST:" to the original name.
        For transversal/international or other result families, first obtain the
        complete result identifier from QiaoTong results/UI, then use
        case_name_mode="full" to pass it unchanged. Never infer result prefixes
        from the TV/MV combination type codes.

        Example:
        • Create load case: create_load_case(name='荷载1', case_type='恒载')
        • Query results: get_analysis_results(result_type='deformation', case_name='荷载1', stage_id=-1)
          (The tool converts it to 'ST:荷载1' automatically)

        Result field structure:
        • Deformation: {node_id, dx, dy, dz, rx, ry, rz} — lowercase, meters/radians
        • Force: {element_id, force_i: {Fx,Fy,Fz,Mx,My,Mz}, force_j: {...}} — nested, kN/kN·m
        • Access fields like: result['dz'] for displacement, result['force_i']['My'] for moment
        """


    def _require_available(self):
        """Raise error if provider is not available."""
        if not self._available:
            raise RuntimeError(
                f"qtmodel provider unavailable: {self._unavailable_reason}"
            )

    def _optional_mdb_parameter(
        self, method: str, parameter: str, value: Any
    ) -> dict[str, Any]:
        """Validate opt-in parameters without relying on qtmodel's version label."""
        import inspect

        if value is None:
            return {}
        options = {parameter: value}
        try:
            inspect.signature(getattr(self._mdb, method)).bind_partial(**options)
        except TypeError as exc:
            raise ValueError(
                f"Installed qtmodel does not support {method} parameter '{parameter}'. "
                "Use a qtmodel source build or release that exposes this parameter, "
                "or omit the option to keep legacy behavior. "
                f"(当前 qtmodel 不支持 {method} 的 {parameter} 参数；"
                "请使用包含此功能的新版源码或发行版，或省略该选项)"
            ) from exc
        return options

    def _optional_mdb_parameters(self, method: str, **values: Any) -> dict[str, Any]:
        """Check all opt-in parameters before issuing any write."""
        options = {}
        for parameter, value in values.items():
            options.update(self._optional_mdb_parameter(method, parameter, value))
        return options

    def _validated_method(self, api_object: str, method: str, kwargs: dict[str, Any]):
        """Resolve an explicit capability and bind every argument before writes."""
        import inspect

        self._require_available()
        fn = getattr(self._resolve_api_object(api_object), method, None)
        if not callable(fn):
            raise ValueError(
                f"Installed qtmodel does not support {api_object}.{method} "
                "(当前 qtmodel 缺少该接口，请安装支持此功能的版本)"
            )
        try:
            inspect.signature(fn).bind(**kwargs)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Installed qtmodel does not support these {api_object}.{method} arguments "
                f"(当前接口参数不兼容，尚未写入): {exc}"
            ) from exc
        return fn

    def _execute_model_command(self, fn, method: str, kwargs: dict[str, Any]) -> Any:
        """Commit one successful model command; never replay after a lost reply."""
        result = fn(**kwargs)
        try:
            self.update_model()
        except Exception as exc:
            raise RuntimeError(
                f"{method} completed but update_model failed. The model may have changed; "
                "read it back before retrying (命令已执行但提交失败，模型可能已改变；请先回读，勿自动重试). "
                f"{exc}"
            ) from exc
        return self._parse(result)

    def configure_live_load_system(self, system: str, clear_existing: bool = False) -> Any:
        """Change the live-load system only on an explicit configuration call."""
        systems = {"china_longitudinal": 0, "aashto": 1, "china_transversal": 2, "bs": 3, "en1991": 4}
        if system not in systems:
            raise ValueError(f"Unknown live-load system: {system}")
        kwargs = {"kind": systems[system], "clear_existing": clear_existing}
        method = "set_live_load_type"
        fn = self._validated_method("mdb", method, kwargs)
        return self._execute_model_command(fn, method, kwargs)

    def configure_operation_stage(
        self, final_stage: str, static_load_cases: list[str], sink_load_cases: list[str],
        live_load_cases: list[str], transversal_load_cases: list[str], do_analysis: bool = True,
    ) -> Any:
        """Replace all operating-stage selections, including explicit empty lists."""
        kwargs = {
            "final_stage": final_stage, "static_load_cases": static_load_cases,
            "sink_load_cases": sink_load_cases, "live_load_cases": live_load_cases,
            "transversal_load_cases": transversal_load_cases, "do_analysis": do_analysis,
        }
        method = "update_operation_stage_setting"
        fn = self._validated_method("mdb", method, kwargs)
        return self._execute_model_command(fn, method, kwargs)

    # ── Transversal model definitions ─────────────────────────────────

    def get_transversal_data(self, kind: str, name: str = "", index: int = -1) -> list[dict]:
        """Read complete definitions with native exact selectors."""
        if kind not in {"vehicles", "lanes", "cases"}:
            raise ValueError(f"Unknown transversal data kind: {kind}")
        kwargs = {"name": name, "index": index}
        method = f"get_transversal_{kind}"
        fn = self._validated_method("mdb", method, kwargs)
        result = self._parse(fn(**kwargs))
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise RuntimeError(f"{method} returned no valid definition list (未返回有效定义列表)")
        return result

    def set_transversal_data(self, kind: str, action: str, definition: dict[str, Any]) -> dict:
        """Write one complete definition, commit once, and resolve its real ID."""
        if kind not in {"vehicle", "lane", "case"} or action not in {"add", "update"}:
            raise ValueError("Unsupported transversal kind/action")
        kwargs = dict(definition)
        kwargs.setdefault("index", -1)
        if kind == "lane":
            kwargs["load_factors"] = kwargs.pop("distribution_widths")
        if kind == "case":
            factors = kwargs["reduction_factors"]
            greater = kwargs.pop("greater_lane_factor")
            kwargs["reduction_factors"] = f"{len(factors)}|" + ",".join(str(value) for value in [*factors, greater])
        if action == "add" and "new_name" in kwargs:
            raise ValueError("new_name is only valid for update")
        method = f"{action}_transversal_{kind}"
        fn = self._validated_method("mdb", method, kwargs)
        target_name = kwargs.get("new_name") or kwargs["name"]
        selectors = {"name": target_name, "index": kwargs["index"]}
        plural = {"vehicle": "vehicles", "lane": "lanes", "case": "cases"}[kind]
        # Fail before mutation if the required readback capability is absent.
        self._validated_method("mdb", f"get_transversal_{plural}", selectors)
        if kind == "case":
            for family, key in (("vehicles", "vehicle_id"), ("lanes", "lane_id")):
                records = self.get_transversal_data(family, index=kwargs[key])
                if len(records) != 1 or type(records[0].get("index")) is not int or records[0]["index"] != kwargs[key]:
                    raise ValueError(f"No unique transversal {key}={kwargs[key]} (请先回读并使用已有车辆/车道编号)")
        self._execute_model_command(fn, method, kwargs)
        try:
            records = self.get_transversal_data(plural, **selectors)
            matches = [item for item in records if item.get("name") == target_name
                       and (kwargs["index"] == -1 or item.get("index") == kwargs["index"])]
            if len(matches) != 1 or type(matches[0].get("index")) is not int or matches[0]["index"] <= 0:
                raise ValueError("Cannot resolve a unique positive object ID (无法确认唯一的实际编号)")
            return matches[0]
        except Exception as exc:
            raise RuntimeError(
                f"{method} was committed, but readback failed. Do not repeat the write; "
                f"use get_transversal_data (写入已提交，但回读失败；请查询核对，勿重复写入): {exc}"
            ) from exc

    def remove_transversal_data(
        self, kind: str, name: str = "", index: int = -1, cascade: bool | None = None,
    ) -> Any:
        """Delete an explicit target; never change references or escalate cascade."""
        if kind not in {"vehicle", "lane", "case"} or (not name and index == -1):
            raise ValueError("A supported kind and explicit deletion target are required")
        kwargs: dict[str, Any] = {"name": name, "index": index}
        if kind == "case":
            if cascade is not None:
                raise ValueError("Transversal case deletion has no cascade option")
        else:
            kwargs["cascade"] = False if cascade is None else cascade
        method = f"remove_transversal_{kind}"
        fn = self._validated_method("mdb", method, kwargs)
        return self._execute_model_command(fn, method, kwargs)

    # ── International model definitions ───────────────────────────────

    _INTERNATIONAL_QUERIES = {
        "vehicles": "get_international_vehicles",
        "cases": "get_international_live_load_cases",
    }

    def get_international_live_load_data(self, kind: str) -> list[dict]:
        """Read the complete native list; these endpoints have no selectors/pages."""
        if kind not in self._INTERNATIONAL_QUERIES:
            raise ValueError(f"Unknown international data kind: {kind}")
        method = self._INTERNATIONAL_QUERIES[kind]
        fn = self._validated_method("mdb", method, {})
        result = self._parse(fn())
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise RuntimeError(f"{method} returned no valid definition list (未返回有效定义列表)")
        return result

    def _commit_international_definition(
        self, method: str, kwargs: dict[str, Any], kind: str, expected_standard: str | None = None,
    ) -> dict:
        fn = self._validated_method("mdb", method, kwargs)
        # An unavailable getter must fail before the definition is written.
        self._validated_method("mdb", self._INTERNATIONAL_QUERIES[kind], {})
        self._execute_model_command(fn, method, kwargs)
        target_name = kwargs.get("new_name") or kwargs["name"]
        try:
            records = self.get_international_live_load_data(kind)
            matches = [item for item in records if item.get("name") == target_name]
            if len(matches) != 1 or type(matches[0].get("index")) is not int or matches[0]["index"] <= 0:
                raise ValueError("Cannot resolve a unique positive object ID (无法确认唯一的实际编号)")
            # Update locates by name and ignores a supplied compatibility index.
            if method.startswith("add_") and kwargs.get("index", -1) != -1 and matches[0]["index"] != kwargs["index"]:
                raise ValueError("The readback ID does not match the explicit add ID")
            standard = kwargs.get("standard", expected_standard)
            if standard is not None and matches[0].get("standard") != standard:
                raise ValueError("The readback standard does not match the written vehicle")
            return matches[0]
        except Exception as exc:
            raise RuntimeError(
                f"{method} was committed, but readback failed. Do not repeat the write; "
                "use get_international_live_load_data (写入已提交，但回读失败；请查询核对，勿重复写入): "
                f"{exc}"
            ) from exc

    def set_international_vehicle(self, action: str, definition: dict[str, Any]) -> dict:
        if action not in {"add", "update"}:
            raise ValueError("Unsupported international vehicle action")
        kwargs = dict(definition)
        kwargs.setdefault("index", -1)
        if action == "add" and "new_name" in kwargs:
            raise ValueError("new_name is only valid for update")
        return self._commit_international_definition(f"{action}_international_vehicle", kwargs, "vehicles")

    def create_en1991_vehicle(self, source: str, options: dict[str, Any]) -> dict:
        if source not in {"standard", "user"}:
            raise ValueError("Unsupported EN1991 vehicle source")
        return self._commit_international_definition(
            f"add_international_{source}_vehicle", dict(options), "vehicles", expected_standard="EN1991",
        )

    def set_planned_lane(self, action: str, definition: dict[str, Any]) -> Any:
        if action not in {"add", "update"}:
            raise ValueError("Unsupported planned lane action")
        kwargs = dict(definition)
        if action == "add" and "new_name" in kwargs:
            raise ValueError("new_name is only valid for update")
        method = f"{action}_planned_lane_line"
        fn = self._validated_method("mdb", method, kwargs)
        return self._execute_model_command(fn, method, kwargs)

    def set_international_live_load_case(self, action: str, standard: str, definition: dict[str, Any]) -> dict:
        if action not in {"add", "update"} or standard not in {"AASHTO", "BS", "EN1991"}:
            raise ValueError("Unsupported international case action/standard")
        kwargs = dict(definition)
        kwargs.setdefault("index", -1)
        if action == "add" and "new_name" in kwargs:
            raise ValueError("new_name is only valid for update")
        method = f"{action}_international_live_load_case"
        self._validated_method("mdb", method, kwargs)
        self._validated_method("mdb", self._INTERNATIONAL_QUERIES["cases"], {})
        records = self.get_international_live_load_data("vehicles")
        for sub_case in kwargs["sub_cases"]:
            name = sub_case["vehicle_name"]
            matches = [item for item in records if item.get("name") == name]
            if len(matches) != 1 or matches[0].get("standard") != standard:
                raise ValueError(f"No unique {standard} vehicle named {name!r} (请先核对车辆名称及规范)")
        # No lane/plane query exists. The command's server-side validation checks
        # those references without inventing local definitions or silently fixing them.
        return self._commit_international_definition(method, kwargs, "cases")

    # ── Generic API gateway (逃生舱) ───────────────────────────────────

    # 禁止经逃生舱直呼的方法：
    # - initial / do_solve / wait_solve：危险或长耗时（wait_solve 默认无限期轮询），
    #   必须走各自带防护的专用工具；
    # - prepare_model_edit（2.9）：按确认切换阶段或删除结果，删除不可撤销；上游
    #   明确它只能由宿主在用户确认后调用，不能交给模型；
    # - post_python_file（2.9）/ ensure_running / set_url / set_version：作用于 MCP
    #   所在主机或改写连接目标——读任意本地文件并 POST 到任意 URL 让桥通执行、启动
    #   任意可执行文件、把后续请求改发别处——都超出"操作桥通模型"的范围；
    # - export_api_help（2.9）/ export_qt_helper：把 SDK 帮助写到 MCP 主机任意路径，
    #   对操作模型无用，却能覆盖本地文件。export_file 同样写本机，但导出的是模型
    #   交付物，与专用工具 save_model 同属正当用途，故保留。
    _API_BLOCKLIST = {
        "initial", "do_solve", "wait_solve", "prepare_model_edit",
        "post_python_file", "ensure_running", "set_url", "set_version",
        "export_api_help", "export_qt_helper",
    }
    # 名称不带 get_/query_/calc_ 前缀、却不改模型的 mdb 方法：前四个是纯本地计算
    # （不连桥通），resolve_node_selection 只在桥通内解析节点条件。按读操作守卫，
    # 调用后也不提交。未列出的方法一律按写处理（fail closed）。
    _API_MDB_READS = {
        "list_parameter_section_types", "build_parameter_section_copy_spec",
        "build_parameter_section_update_spec", "generate_curve_node_data",
        "resolve_node_selection",
    }
    # 桥通把每条 mdb 写命令放进当前复合命令，由 update_model 作为一条可撤销命令提交
    # （2.9 的 delete_model_object 等明确要求调用方提交）。以下工程/文件/视图管理
    # 命令不进复合命令，调用后不追加提交——close_project 之后更是无模型可提交。
    _API_NO_COMMIT = {
        "update_model", "undo_model", "redo_model", "update_to_pre", "update_to_post",
        "save_file", "open_file", "close_project", "export_file",
    }
    # These CDB methods edit base-model snapshots, unlike legacy CSAN operations.
    # Keep the list explicit: CDB queries, files and solvers must not commit MDB.
    _API_CDB_MODEL_WRITES = frozenset({
        "set_steel_bar_material_convention", "set_section_reinforcement",
        "remove_section_reinforcement_by_name", "set_check_stirrup", "set_element_stirrups",
        "set_check_material", "remove_check_material", "set_check_case", "remove_check_case_snapshot",
    })

    def write_check_snapshot(self, method: str, **kwargs: Any) -> Any:
        """Dispatch an explicit base-model snapshot command with model permissions."""
        if method not in self._API_CDB_MODEL_WRITES:
            raise ValueError(f"Not a model snapshot method: {method}")
        self.ensure_operation_allowed("model_write")
        fn = self._validated_method("cdb", method, kwargs)
        return self._execute_model_command(fn, method, kwargs)

    def _resolve_api_object(self, api_object: str):
        obj = {"mdb": self._mdb, "odb": self._odb, "cdb": self._cdb}.get(api_object)
        if obj is None:
            raise ValueError(f"Unknown api_object '{api_object}'. Use: mdb, odb, cdb")
        return obj

    def list_api_methods(self, api_object: str, pattern: str = "") -> list[dict]:
        """List callable qtmodel API methods with signatures, filtered by substring."""
        import inspect

        self._require_available()
        obj = self._resolve_api_object(api_object)
        out = []
        for name in dir(obj):
            if name.startswith("_") or name in self._API_BLOCKLIST:
                continue
            if pattern and pattern.lower() not in name.lower():
                continue
            fn = getattr(obj, name)
            if not callable(fn):
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                sig = "(...)"
            out.append({"method": name, "signature": sig})
        return out

    def call_api(self, api_object: str, method: str, kwargs: dict | None = None) -> Any:
        """Call a whitelisted qtmodel API method after validating the signature."""
        import inspect

        self._require_available()
        obj = self._resolve_api_object(api_object)
        if method.startswith("_") or method in self._API_BLOCKLIST:
            raise ValueError(
                f"Method '{method}' is not callable via the gateway "
                f"(该方法不允许经逃生舱调用，请使用对应的专用工具)"
            )
        fn = getattr(obj, method, None)
        if fn is None or not callable(fn):
            raise ValueError(
                f"{api_object} has no method '{method}' "
                f"(方法不存在，可用 list 模式按关键字检索)"
            )

        if api_object == "mdb":
            operation = (
                "model_read"
                if method.startswith(("get_", "query_", "calc_")) or method in self._API_MDB_READS
                else "model_write"
            )
        elif api_object == "cdb":
            if method in self._API_CDB_MODEL_WRITES:
                operation = "model_write"
            else:
                operation = "check_run" if method.startswith(("solve", "run", "do_")) else "check_write"
        elif method.startswith(("set_", "save_", "plot_", "change_", "display_", "reset_")):
            operation = "view"
        elif any(
            token in method
            for token in (
                "result", "force", "stress", "reaction", "displacement",
                "modal", "eigen", "period", "vibration", "buckling",
                "concurrent",
            )
        ):
            operation = "result_read"
        else:
            operation = "model_read"
        self.ensure_operation_allowed(operation)

        kwargs = kwargs or {}
        sig = inspect.signature(fn)
        try:
            sig.bind(**kwargs)
        except TypeError as e:
            raise ValueError(
                f"Arguments do not match (参数不匹配): {e}. Real signature (真实签名): {method}{sig}"
            ) from e
        if (
            api_object == "mdb"
            and operation == "model_write"
            and method not in self._API_NO_COMMIT
        ) or (api_object == "cdb" and method in self._API_CDB_MODEL_WRITES):
            return self._execute_model_command(fn, method, kwargs)
        return self._parse(fn(**kwargs))

    # ── Model Information ──────────────────────────────────────────────

    @staticmethod
    def _parse(result: Any) -> Any:
        """Parse qtmodel strings and normalize typed query objects recursively."""
        if isinstance(result, str):
            cleaned = result.strip()
            if not cleaned:
                return cleaned
            try:
                result = json.loads(cleaned)
            except ValueError:
                try:
                    result = ast.literal_eval(cleaned)
                except (ValueError, SyntaxError):
                    return result
        return QtModelProvider._normalize_result(result)

    @staticmethod
    def _normalize_result(result: Any) -> Any:
        """Keep HTTP fields from to_dict/Mapping objects, including nested records.

        Older qtmodel releases lack to_dict on many model classes, so their
        public instance attributes remain a compatibility fallback. Nested
        strings are data, not another JSON document to decode.
        """
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
        elif not isinstance(result, (Mapping, type)) and hasattr(result, "__dict__"):
            fields = {key: value for key, value in vars(result).items() if not key.startswith("_")}
            if fields:
                result = fields
        if isinstance(result, Mapping):
            return {key: QtModelProvider._normalize_result(value) for key, value in result.items()}
        if isinstance(result, (list, tuple)):
            return [QtModelProvider._normalize_result(item) for item in result]
        return result


    @staticmethod
    def _validate_ids(ids, required: bool = False, *, allow_empty: bool = False):
        """Preserve explicit scope; never truncate IDs or turn blank writes into all."""
        if ids is None:
            if required:
                raise ValueError("ids parameter is required but was empty or None.")
            return None
            
        if isinstance(ids, str):
            cleaned = ids.strip()
            if not cleaned:
                if allow_empty and not required:
                    return None
                raise ValueError("ids string cannot be empty; use explicit None only where all IDs are supported.")
            from qtmodel.core.data_helper import QtDataHelper

            parsed = QtDataHelper.parse_ids_to_array(cleaned)
            if not parsed or any(type(value) is not int or value <= 0 for value in parsed):
                raise ValueError("ids must select positive integers (编号必须为正整数)")
            return cleaned
            
        if isinstance(ids, (int, float)):
            if isinstance(ids, bool) or not math.isfinite(ids) or ids <= 0 or int(ids) != ids:
                raise ValueError(f"Invalid ID: {ids}. IDs must be positive integers.")
            return int(ids)
            
        if isinstance(ids, (list, tuple)):
            if not ids and (required or not allow_empty):
                raise ValueError("ids list cannot be empty.")
            valid_ids = []
            for i in ids:
                try:
                    if isinstance(i, str):
                        if not i.strip().isdecimal():
                            raise ValueError(f"Invalid ID in list: {i}")
                        val = int(i)
                    elif type(i) in (int, float) and math.isfinite(i) and int(i) == i:
                        val = int(i)
                    else:
                        raise ValueError(f"Invalid ID in list: {i}")
                    if val <= 0:
                        raise ValueError(f"Invalid ID in list: {i}. IDs must be positive.")
                    valid_ids.append(val)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid ID format in list: {i}") from e
            return valid_ids
            
        raise ValueError(f"Unsupported ids type: {type(ids)}. Expected int, list, or string.")

    def _model_query_method(self, fn_name: str):
        """Prefer MDB model queries, falling back to pre-migration ODB releases.

        MDB's local get_section_shape builder must not be confused with the
        existing-model query, which moved to get_model_section_shape.
        """
        mdb_name = "get_model_section_shape" if fn_name == "get_section_shape" else fn_name
        method = getattr(self._mdb, mdb_name, None)
        return method if callable(method) else getattr(self._odb, fn_name, None)

    def _query_model(self, fn_name: str, *args, **kwargs) -> Any:
        """Dispatch a model query and return plain, JSON-compatible data."""
        method = self._model_query_method(fn_name)
        if not callable(method):
            raise AttributeError(f"qtmodel has no model query '{fn_name}'")
        return self._parse(method(*args, **kwargs))

    def query_model_data(self, kind: str, **filters: Any) -> dict[str, Any]:
        """Use native server filtering/pagination, never full-download fallbacks."""
        methods = {
            "nodes": "query_node_data", "elements": "query_element_data",
            "boundaries": "query_boundary_data", "loads": "query_load_data",
            "node_local_axes": "query_node_local_axis_data",
            "section_summaries": "query_section_summaries",
        }
        if kind not in methods:
            raise ValueError(f"Unknown model query kind: {kind}")
        self._require_available()
        result = self._query_model(methods[kind], **filters)
        if not isinstance(result, dict) or not result:
            raise RuntimeError(
                f"{methods[kind]} returned no valid query page; the bridge may not support it "
                "(未返回有效查询页，请检查桥通是否支持该接口；不会回退到全量查询)"
            )
        return result

    def get_model_catalog_data(self, kind: str, **options: Any) -> Any:
        """Read native summaries/details while retaining backend-owned fields."""
        methods = {
            "material_summaries": "get_material_summaries",
            "material_detail": "get_material_detail",
            "load_case_summaries": "get_load_case_summaries",
            "load_case_detail": "get_load_case_detail",
            "load_combination_summaries": "get_load_combination_summaries",
            "load_combination_detail": "get_load_combination_detail",
            "construction_stage_summaries": "get_construction_stage_summaries",
            "element_section": "get_element_section", "spans": "get_span_data",
        }
        if kind not in methods:
            raise ValueError(f"Unknown model catalog kind: {kind}")
        self._require_available()
        result = self._query_model(methods[kind], **options)
        if result is None or isinstance(result, str):
            raise RuntimeError(f"{methods[kind]} returned no valid model data (未返回有效模型数据)")
        return result

    def _safe_get(self, fn_name: str, *args, **kwargs) -> Any:
        """Call an optional model query, returning None on error."""
        fn = self._model_query_method(fn_name)
        if fn is None:
            # Fallback: if this python version of qtmodel wrapper is missing the method, 
            # attempt to send it directly as a REST command header to the running QT Server.
            try:
                from qtmodel.core.qt_server import QtServer
                header = fn_name.replace("_", "-").upper()
                raw_result = QtServer.send_dict(header=header)
                return self._parse(raw_result)
            except Exception:
                return None
                
        try:
            return self._parse(fn(*args, **kwargs))
        except Exception:
            return None

    @staticmethod
    def _count(result) -> int:
        if isinstance(result, (list, dict)):
            return len(result)
        return 0

    def get_model_summary(self) -> dict[str, Any]:
        self._require_available()
        return {
            "node_count":            self._count(self._safe_get("get_node_data")),
            "element_count":         self._count(self._safe_get("get_element_data")),
            "material_count":        self._count(self._safe_get("get_material_data")),
            "section_count":         self._count(self.get_section_names()),
            "stage_count":           self._count(self.get_stage_names()),
            "load_case_count":       self._count(self.get_load_case_names()),
            "structure_group_count": self._count(self._safe_get("get_structure_group_names")),
            "boundary_group_count":  self._count(self._safe_get("get_boundary_group_names")),
        }

    # qtmodel 2.8 新增的轻量概览接口（现位于 mdb_model_overview / mdb_model_structure），
    # 专为 Agent 设计：一次往返拿到摘要，不必像 get_model_summary 那样拉全量再计数。
    # 以桥通 HTTP 返回字段为准，类型化对象统一转为普通字典，不做额外字段映射。
    _OVERVIEW_METHODS = {
        "summary": "get_model_summary",
        "analysis_context": "get_analysis_context",
        "project_metadata": "get_project_metadata",
        "check_context": "get_code_check_context",
        "structure_group_summaries": "get_structure_group_summaries",
    }

    def get_model_overview(self, kind: str) -> Any:
        """Return one of qtmodel 2.8's lightweight overview payloads, or None.

        2.6.3 没有这些方法：_safe_get 会退回按 header 直发，旧桥通不认识该命令
        时抛错被吞掉，最终返回 None——由工具层报"无数据"，不阻断其它查询。
        """
        self._require_available()
        method = self._OVERVIEW_METHODS.get(kind)
        if method is None:
            raise ValueError(
                f"unknown overview kind: {kind}. Use: {', '.join(self._OVERVIEW_METHODS)}"
            )
        return self._safe_get(method)

    @staticmethod
    def _to_dicts(result: Any) -> list[dict]:
        """Normalize a query result to a list of plain dicts.

        新版类型化对象使用 to_dict/Mapping 保留服务端原始字段；旧版对象回退
        到公开属性。列表中的标量（如结构组名）不做转换。
        """
        result = QtModelProvider._normalize_result(result)
        if isinstance(result, dict):
            return [result]
        return result if isinstance(result, list) else []

    def get_node_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        result = self._query_model("get_node_data", ids=ids)
        return self._to_dicts(result)

    def get_element_data(self, ids: Any = None) -> list[dict]:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        result = self._query_model("get_element_data", ids=ids)
        return self._to_dicts(result)

    def get_material_data(self) -> list[dict]:
        self._require_available()
        result = self._query_model("get_material_data")
        return result if isinstance(result, list) else []

    def get_section_data(self, sec_id: int, position: int = 0) -> dict:
        self._require_available()
        result = self._query_model("get_section_data", sec_id, position=position)
        return result if isinstance(result, dict) else {}

    def get_section_names(self) -> dict[str, str] | list:
        """Return section info (dict of id->name, or list of IDs/dicts depending on API version)."""
        self._require_available()
        
        # New API returns JSON dict {"3": "上横梁", "4": "下横梁", ...}
        for method in ("get_section_names", "get_section_ids", "get_all_section_data"):
            result = self._safe_get(method)
            # dict output: {"3": "SectionName"}
            if isinstance(result, dict):
                return {str(k): str(v) for k, v in result.items()}
            # list output: [{"id": 3, "name": "SectionName"}] or [3, 4]
            if isinstance(result, list) and result:
                if isinstance(result[0], dict):
                    return {str(d.get("id", i + 1)): d.get("name", f"Section {i + 1}") for i, d in enumerate(result)}
                return result
        return {}

    def get_boundary_data(self) -> dict[str, list[dict]]:
        self._require_available()
        return {
            "general_supports": self._safe_get("get_general_support_data") or [],
            "elastic_links":    self._safe_get("get_elastic_link_data") or [],
            "elastic_supports": self._safe_get("get_elastic_support_data") or [],
            "master_slave_links": self._safe_get("get_master_slave_link_data") or [],
            "beam_constraints": self._safe_get("get_beam_constraint_data") or [],
        }

    def get_load_group_names(self) -> list[str]:
        """Read load groups before a workflow decides whether creation is needed."""
        self._require_available()
        result = self._query_model("get_load_group_names")
        if not isinstance(result, list) or any(not isinstance(name, str) for name in result):
            raise ValueError("Cannot read load group names (无法读取荷载组名称)")
        return result

    def get_load_case_names(self) -> list[str]:
        """Return load case names."""
        self._require_available()
        # Older version uses get_load_case_names, newer uses get_case_names
        for method in ("get_load_case_names", "get_case_names"):
            result = self._safe_get(method)
            if isinstance(result, list):
                return result
        return []

    def get_stage_names(self) -> list[str]:
        """Return construction stage names."""
        self._require_available()
        for method in ("get_stage_names", "get_stage_name"):
            result = self._safe_get(method)
            if isinstance(result, list):
                return result
        return []

    def get_structure_group_names(self) -> list[str]:
        self._require_available()
        result = self._safe_get("get_structure_group_names")
        return result if isinstance(result, list) else []

    # ── Modeling Operations ────────────────────────────────────────────

    def initialize_model(self) -> None:
        self._require_available()
        self._mdb.initial()

    def update_model(self) -> None:
        """Commit model changes and preserve uncertainty if that commit fails."""
        self._require_available()
        try:
            self._mdb.update_model()
        except Exception as exc:
            raise RuntimeError(
                "update_model failed; earlier writes may have changed the model. "
                "Read the model/undo history before retrying "
                f"(提交失败，之前写入可能已生效；请先回读及检查撤销记录，勿自动重试): {exc}"
            ) from exc

    def save_model_file(self, file_path: str) -> None:
        self._require_available()
        self._mdb.save_file(file_path=file_path)

    def open_model_file(self, file_path: str) -> None:
        self._require_available()
        self._mdb.open_file(file_path=file_path)

    def remove_unused_sections(self) -> None:
        self._require_available()
        self._mdb.remove_unused_sections()
        self.update_model()

    def add_nodes(self, node_data: list[list[float]], **kwargs) -> None:
        self._require_available()
        if not node_data:
            raise ValueError("node_data cannot be empty")
        self._mdb.add_nodes(node_data=node_data, **kwargs)
        self.update_model()

    def add_nodes_returning_ids(
        self, node_data: list[list[float]], **kwargs
    ) -> list[int]:
        """Add nodes and return the ID occupying each requested coordinate.

        qtmodel 的 add_nodes 返回 None，而后端**不保证**采用调用方期望的编号：
        - numbering_type=0/1 时 start_id 被完全忽略（仅 2=用户定义号码才读它）；
        - start_id 被占用时后端自行改派（实测请求 500 得到 502）；
        - 坐标与最终 ID 的对应关系是倒序的（实测 x=10/20/30 -> 102/101/100）；
        - is_merged 生效时，新节点会被**合并到已存在的旧节点**上，该旧 ID 不属于
          "新增"，仅靠前后集合差会漏掉它。

        合并开启时，在实际合并容差内找最近节点；关闭时先读已有编号，随后只从
        新增节点中匹配。不得放大合并容差，也不得用查询返回顺序决定节点身份。
        返回列表与请求坐标一一对应（合并时可重复）。有任一位置无法确定或出现
        等距离候选时返回空列表，避免调用者把缺项后的列表当成连续节点链。
        """
        self._require_available()
        if not node_data:
            raise ValueError("node_data cannot be empty")

        def read_coords() -> dict[int, tuple[float, float, float]] | None:
            rows = self._safe_get("get_node_data")
            if not isinstance(rows, list):
                return None
            coords = {}
            for row in rows:
                if not isinstance(row, dict):
                    return None
                node_id = row.get("node_id", row.get("id"))
                if isinstance(node_id, bool) or not isinstance(node_id, int):
                    return None
                try:
                    xyz = (float(row["x"]), float(row["y"]), float(row["z"]))
                except (KeyError, TypeError, ValueError):
                    return None
                if not all(math.isfinite(value) for value in xyz):
                    return None
                coords[node_id] = xyz
            return coords

        merging = kwargs.get("is_merged", False)
        before = read_coords() if not merging else {}
        self._mdb.add_nodes(node_data=node_data, **kwargs)
        self.update_model()
        after = read_coords()
        if before is None or after is None:
            return []
        candidates = {nid: xyz for nid, xyz in after.items() if nid not in before}
        # An explicit merge radius, including zero, must never be enlarged.
        # Without merging, a tiny tolerance only covers coordinate round trips;
        # candidates are already restricted to IDs created by this call.
        tolerance = float(kwargs.get("merge_error", 1e-3)) if merging else 1e-9
        found: list[int] = []
        for coord in node_data:
            xyz = coord[1:4] if len(coord) == 4 else coord
            if len(xyz) != 3:
                return []
            matches = sorted(
                (math.dist(xyz, point), nid) for nid, point in candidates.items()
                if math.dist(xyz, point) <= tolerance
            )
            if not matches or (
                len(matches) > 1
                and math.isclose(matches[0][0], matches[1][0], rel_tol=1e-12, abs_tol=1e-12)
            ):
                return []
            found.append(matches[0][1])
            if not merging:
                candidates.pop(matches[0][1])
        return found

    def add_elements(self, ele_data: list[list], **kwargs) -> None:
        self._require_available()
        if not ele_data:
            raise ValueError("ele_data cannot be empty")
        self._mdb.add_elements(ele_data=ele_data, **kwargs)
        self.update_model()

    def get_node_coords(self, node_ids: list[int]) -> dict[int, tuple[float, float, float]]:
        """Return {node_id: (x, y, z)} for the requested IDs that actually exist.

        用于建单元前校验节点几何。缺失的编号不出现在返回值中，调用方据此
        识别无效引用；查询失败时返回空字典，由调用方决定是否降级放行。
        """
        self._require_available()
        rows = self._safe_get("get_node_data")
        if rows is None:
            return {}
        wanted = set(node_ids)
        out: dict[int, tuple[float, float, float]] = {}
        for row in self._to_dicts(rows):
            node_id = row.get("node_id", row.get("id"))
            if not isinstance(node_id, int) or node_id not in wanted:
                continue
            try:
                out[node_id] = (float(row["x"]), float(row["y"]), float(row["z"]))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def check_node_chain_geometry(self, node_ids: list[int]) -> dict[str, Any]:
        """Verify a node chain forms a monotonic polyline before building elements.

        后端会接受任意有效编号的连线，即使几何上来回折返——单元长度忽长忽短、
        方向正负交替，求解器照样计算，只是算的是另一座桥。实测在编号乱序的
        节点批上按编号递推建梁，得到长度 [3, 12, 3, 3] 的折返链且无任何报错。

        判定标准：相邻节点的位移向量方向一致（点积为正）。这允许折线桥（曲线
        梁、变坡），只拒绝真正的往回折返。

        返回 {ok, reason, total_length, missing}。查询不可用时 ok=True——
        校验能力缺失不应阻断建模，宁可放行也不误拒。
        """
        coords = self.get_node_coords(node_ids)
        if not coords:
            return {"ok": True, "reason": "coordinates unavailable, check skipped"}

        missing = [n for n in node_ids if n not in coords]
        if missing:
            return {
                "ok": False,
                "reason": f"node(s) not found in model: {missing}",
                "missing": missing,
            }

        total = 0.0
        prev_vec: tuple[float, float, float] | None = None
        for a, b in zip(node_ids, node_ids[1:], strict=False):
            xa, ya, za = coords[a]
            xb, yb, zb = coords[b]
            vec = (xb - xa, yb - ya, zb - za)
            length = (vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) ** 0.5
            if length < 1e-9:
                return {
                    "ok": False,
                    "reason": f"nodes {a} and {b} are coincident (zero-length element)",
                }
            total += length
            if prev_vec is not None:
                dot = sum(p * c for p, c in zip(prev_vec, vec, strict=False))
                if dot < 0:
                    return {
                        "ok": False,
                        "reason": (
                            f"chain folds back at node {a}: segment to {b} reverses "
                            f"direction (元素在此折返)"
                        ),
                    }
            prev_vec = vec
        return {"ok": True, "reason": "monotonic", "total_length": total}

    def add_material(
        self,
        name: str,
        mat_type: int,
        standard: int = 1,
        database: str = "",
        *,
        is_orthotropic: bool | None = None,
        ey: float | None = None,
        **kwargs,
    ) -> None:
        self._require_available()
        options = self._optional_mdb_parameters(
            "add_material", is_orthotropic=is_orthotropic, ey=ey
        )
        params = {"name": name, "mat_type": mat_type, "standard": standard}
        if database:
            params["database"] = database
        params.update(kwargs)
        params.update(options)
        self._mdb.add_material(**params)
        self.update_model()

    def add_time_parameter(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_parameter(**kwargs)
        self.update_model()

    def add_creep_function(self, name: str, creep_data: list, scale_factor: float = 1) -> None:
        self._require_available()
        self._mdb.add_creep_function(name=name, creep_data=creep_data, scale_factor=scale_factor)
        self.update_model()

    def add_shrink_function(self, name: str, shrink_data: list, scale_factor: float = 1) -> None:
        self._require_available()
        self._mdb.add_shrink_function(name=name, shrink_data=shrink_data, scale_factor=scale_factor)
        self.update_model()

    def add_thickness(self, *, t_out: float | None = None, **kwargs) -> None:
        self._require_available()
        options = self._optional_mdb_parameter("add_thickness", "t_out", t_out)
        self._mdb.add_thickness(**kwargs, **options)
        self.update_model()

    def add_effective_width(self, element_ids, **kwargs) -> None:
        self._require_available()
        self._mdb.add_effective_width(element_ids=element_ids, **kwargs)
        self.update_model()

    def add_tapper_section_group(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tapper_section_group(**kwargs)
        self.update_model()

    def add_section(self, name: str, sec_type: str, **kwargs) -> None:
        self._require_available()
        # add_section's SDK default is 1, which can overwrite section 1.
        # -1 is the automatic ID also used by add_single_section for ADD-SECTION.
        kwargs.setdefault("index", -1)
        self._mdb.add_section(name=name, sec_type=sec_type, **kwargs)
        self.update_model()

    def add_tapper_section_by_id(self, name: str, begin_id: int, end_id: int, shear_consider: bool = True, sec_normalize: bool = False) -> None:
        self._require_available()
        self._mdb.add_tapper_section_by_id(name=name, begin_id=begin_id, end_id=end_id, shear_consider=shear_consider, sec_normalize=sec_normalize)
        self.update_model()

    def remove_section(self, ids: Any) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.remove_section(ids=ids)
        self.update_model()

    def update_section_bias(self, index: int, bias_type: str, center_type: str = "质心", shear_consider: bool = True, bias_point: list[float] | None = None, side_i: bool = True) -> None:
        self._require_available()
        kwargs = {}
        if bias_point is not None:
            kwargs["bias_point"] = bias_point
        self._mdb.update_section_bias(index=index, bias_type=bias_type, center_type=center_type, shear_consider=shear_consider, side_i=side_i, **kwargs)

    def update_section_property(self, index: int, sec_property: list[float], side_i: bool = True) -> None:
        self._require_available()
        self._mdb.update_section_property(index=index, sec_property=sec_property, side_i=side_i)

    def calculate_section_property(self) -> None:
        self._require_available()
        self._mdb.calculate_section_property()

    # ── Modify Operations ──────────────────────────────────────────────

    # qtmodel 的 Element 查询模型用字符串表示单元类型，update_element 则要求整数
    _ELE_TYPE_TO_INT = {"BEAM": 1, "LINK": 2, "CABLE": 3, "PLATE": 4}

    @staticmethod
    def _field(entity: Any, name: str) -> Any:
        """Read a field from a query-model object (attr) or parsed dict."""
        if isinstance(entity, dict):
            return entity.get(name)
        return getattr(entity, name, None)

    def _one_entity(self, records: list, index: int, kind: str) -> Any:
        keys = ("node_id", "id", "index") if kind == "Node" else ("index", "element_id", "ele_id", "id")
        matches = [record for record in records if any(
            self._field(record, key) == index and not isinstance(self._field(record, key), bool)
            for key in keys
        )]
        if len(matches) != 1:
            raise ValueError(f"{kind} {index} not found uniquely; cannot fill unchanged fields (无法唯一回读目标，未修改)")
        return matches[0]

    def update_node(self, node_id: int, **kwargs) -> None:
        self._require_available()
        # qtmodel 的 update_node 会把未传入的坐标按默认值 1 整体下发，
        # 部分更新会静默改写其余坐标；此处先读回当前坐标补齐缺省分量。
        if not {"x", "y", "z"} <= kwargs.keys():
            nodes = self.get_node_data(ids=node_id)
            current = self._one_entity(nodes, node_id, "Node")
            for axis in ("x", "y", "z"):
                if axis not in kwargs:
                    value = self._field(current, axis)
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError(f"Node {node_id} is missing coordinate {axis}; no update was sent")
                    kwargs[axis] = value
        self._mdb.update_node(node_id=node_id, **kwargs)

    def update_node_id(self, node_id: int, new_id: int) -> None:
        self._require_available()
        self._mdb.update_node_id(node_id=node_id, new_id=new_id)

    def renumber_nodes(self, ids: Any = None, new_ids: Any = None) -> None:
        self._require_available()
        if ids is None and new_ids is None:
            self._mdb.renumber_nodes()
        else:
            ids, new_ids = self._renumber_mapping(ids, new_ids)
            self._mdb.renumber_nodes(ids, new_ids)

    def _renumber_mapping(self, ids: Any, new_ids: Any) -> tuple[list[int], list[int]]:
        from qtmodel.core.data_helper import QtDataHelper

        old = QtDataHelper.parse_ids_to_array(self._validate_ids(ids, required=True))
        new = QtDataHelper.parse_ids_to_array(self._validate_ids(new_ids, required=True))
        if len(old) != len(new) or len(set(old)) != len(old) or len(set(new)) != len(new):
            raise ValueError("Renumbering requires equal-length, unique old/new ID lists (改号须等长且两列各自无重复)")
        return old, new

    def move_nodes(self, ids: Any, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.move_nodes(ids=ids, offset_x=offset_x, offset_y=offset_y, offset_z=offset_z)

    def update_element(self, old_id: int, **kwargs) -> None:
        self._require_available()
        # 同 update_node：qtmodel 的 update_element 整体下发全部字段，
        # 未指定字段会被默认值覆盖（如 ele_type→1、beta_angle→0、plate_type→0 薄板），
        # 先读回唯一目标，并确认适用字段完整；不能把缺失字段当作默认值覆盖。
        fields = ("ele_type", "node_ids", "beta_angle", "mat_id", "sec_id",
                  "initial_type", "initial_value", "plate_type")
        missing = [f for f in fields if f not in kwargs]
        if missing:
            elements = self.get_element_data(ids=old_id)
            current = self._one_entity(elements, old_id, "Element")
            for f in missing:
                value = self._field(current, f)
                if f == "ele_type" and isinstance(value, str):
                    value = self._ELE_TYPE_TO_INT.get(value.upper(), value)
                if value is not None:
                    kwargs.setdefault(f, value)
        needed = {"ele_type", "node_ids", "beta_angle", "mat_id", "sec_id"}
        element_type = kwargs.get("ele_type")
        if element_type == 3:
            needed.update({"initial_type", "initial_value"})
        if element_type == 4:
            needed.add("plate_type")
        if needed - kwargs.keys() or any(kwargs.get(key) is None for key in needed):
            raise ValueError(
                "Element readback is incomplete; use a targeted update_element_* tool "
                "(单元回读缺少适用字段；请使用单字段修改工具，未提交修改)"
            )
        nodes = kwargs["node_ids"]
        # Frame connectivity has two ends. Preserve a plate's complete readback
        # without assuming every backend represents it with exactly four IDs.
        valid_nodes = isinstance(nodes, (list, tuple)) and (
            len(nodes) >= 3 if element_type == 4 else len(nodes) == 2
        )
        if element_type not in {1, 2, 3, 4} or not valid_nodes:
            raise ValueError("Element type/connectivity mismatch (单元类型与节点数量不一致，未提交修改)")
        self._mdb.update_element(old_id=old_id, **kwargs)

    def update_element_id(self, old_id: int, new_id: int) -> None:
        self._require_available()
        self._mdb.update_element_id(old_id=old_id, new_id=new_id)

    def renumber_elements(self, element_ids: Any = None, new_ids: Any = None) -> None:
        self._require_available()
        if element_ids is None and new_ids is None:
            self._mdb.renumber_elements()
        else:
            element_ids, new_ids = self._renumber_mapping(element_ids, new_ids)
            self._mdb.renumber_elements(element_ids, new_ids)

    def revert_local_orientation(self, ids: Any) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.revert_local_orientation(ids=ids)

    def update_element_material(self, ids: Any, mat_id: int) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.update_element_material(ids=ids, mat_id=mat_id)

    def update_frame_section(self, ids: Any, sec_id: int) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.update_frame_section(ids=ids, sec_id=sec_id)

    def update_element_beta(self, ids: Any, beta: float) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.update_element_beta(ids=ids, beta=beta)

    def update_element_node(self, element_id: int, node_ids: list) -> None:
        self._require_available()
        self._mdb.update_element_node(element_id, node_ids)

    def remove_structure_from_group(self, name: str, **kwargs) -> None:
        self._require_available()
        if all(kwargs.get(key) is None for key in ("node_ids", "element_ids")):
            raise ValueError("Explicit node_ids or element_ids are required (必须明确指定要移出的成员)")
        for key in ("node_ids", "element_ids"):
            if kwargs.get(key) is not None:
                kwargs[key] = self._validate_ids(kwargs[key], required=True)
        self._mdb.remove_structure_from_group(name=name, **kwargs)
        self.update_model()

    def remove_nodes(self, ids: Any = None) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is not None:
            self._mdb.remove_nodes(ids=ids)
        else:
            self._mdb.remove_nodes()

    def remove_elements(self, ids: Any = None, remove_free: bool = False) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        elif remove_free:
            # The SDK's ids=None branch omits remove_free entirely. Resolve the
            # actual selection so the requested free-node cleanup is transmitted.
            records = self.get_element_data()
            ids = [self._field(row, "index") if self._field(row, "index") is not None
                   else self._field(row, "element_id") for row in records]
            if not ids:
                return
            ids = self._validate_ids(ids, required=True)
        if ids is not None:
            self._mdb.remove_elements(ids=ids, remove_free=remove_free)
        else:
            self._mdb.remove_elements(remove_free=remove_free)

    def merge_nodes(self, ids: Any = None, tolerance: float = 1e-4) -> None:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids)
        if ids is not None:
            self._mdb.merge_nodes(ids=ids, tolerance=tolerance)
        else:
            self._mdb.merge_nodes(tolerance=tolerance)


    def add_general_support(
        self, node_id: Any, boundary_info: list, *, coordinate: int | None = None,
        extra_enabled: bool | None = None, extra_parameters: list[float] | None = None,
        **kwargs,
    ) -> None:
        self._require_available()
        if extra_parameters is not None and extra_enabled is None:
            extra_enabled = True
        options = self._optional_mdb_parameters(
            "add_general_support", coordinate=coordinate, extra_enabled=extra_enabled,
            extra_parameters=extra_parameters,
        )
        arguments = {"node_id": node_id, "boundary_info": boundary_info, **options, **kwargs}
        method = "add_general_support"
        fn = self._validated_method("mdb", method, arguments)
        self._execute_model_command(fn, method, arguments)

    def add_elastic_link(
        self, link_type: int, start_id: int, end_id: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_elastic_link(
            link_type=link_type, start_id=start_id, end_id=end_id, **kwargs
        )
        self.update_model()

    def add_beam_constraint(
        self, beam_id: int, info_i: list[bool] | None = None, info_j: list[bool] | None = None, group_name: str = ""
    ) -> None:
        self._require_available()
        kwargs: dict[str, Any] = {"beam_id": beam_id}
        if info_i is not None:
            kwargs["info_i"] = info_i
        if info_j is not None:
            kwargs["info_j"] = info_j
        if group_name:
            kwargs["group_name"] = group_name
        self._mdb.add_beam_constraint(**kwargs)
        self.update_model()

    def add_constraint_equation(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_constraint_equation(**kwargs)
        self.update_model()

    def remove_boundary(self, **kwargs) -> None:
        self._require_available()
        self._mdb.remove_boundary(**kwargs)
        self.update_model()

    # ── Load Operations ────────────────────────────────────────────────

    def add_load_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_load_group(name=name)
        self.update_model()

    def add_load_case(self, name: str, case_type: str = "施工阶段荷载", desc: str = "") -> None:
        self._require_available()
        self._mdb.add_load_case(name=name, case_type=case_type)
        self.update_model()

    def add_load_combine(self, index: int = -1, name: str = "", combine_type: int = 1, describe: str = "", combine_info: list[tuple] | None = None) -> None:
        self._require_available()
        kwargs = {"index": index, "name": name, "combine_type": combine_type, "describe": describe}
        if combine_info is not None:
            kwargs["combine_info"] = combine_info
        self._mdb.add_load_combine(**kwargs)
        self.update_model()

    def add_nodal_force(
        self, node_id: Any, case_name: str, load_info: list, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_nodal_force(
            node_id=node_id, case_name=case_name, load_info=load_info, **kwargs
        )
        self.update_model()

    def add_beam_element_load(
        self, element_id: Any, case_name: str, load_type: int, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_beam_element_load(
            element_id=element_id, case_name=case_name, load_type=load_type, **kwargs
        )
        self.update_model()

    def add_system_temperature(
        self, element_id: Any, case_name: str, temperature: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_element_temperature(
            element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
        )
        self.update_model()

    def add_gradient_temperature(
        self, element_id: Any, case_name: str, temperature: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_gradient_temperature(
            element_id=element_id, case_name=case_name, temperature=temperature, **kwargs
        )
        self.update_model()


    def add_custom_temperature(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_custom_temperature(element_id=element_id, case_name=case_name, **kwargs)
        self.update_model()

    def add_beam_section_temperature(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_beam_section_temperature(element_id=element_id, case_name=case_name, **kwargs)
        self.update_model()

    def add_initial_tension_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_initial_tension_load(element_id=element_id, case_name=case_name, **kwargs)
        self.update_model()

    def add_cable_length_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_cable_length_load(element_id=element_id, case_name=case_name, **kwargs)
        self.update_model()

    def add_plate_element_load(self, element_id, case_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_plate_element_load(element_id=element_id, case_name=case_name, **kwargs)
        self.update_model()

    def add_distribute_plane_load(self, index: int, case_name: str, type_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_distribute_plane_load(index=index, case_name=case_name, type_name=type_name, **kwargs)
        self.update_model()

    def add_support_settlement(
        self, node_id: Any, case_name: str, displacement_info: list, **kwargs
    ) -> None:
        self._require_available()
        # qtmodel 的参数名为 load_info
        self._mdb.add_node_displacement(
            node_id=node_id, case_name=case_name, load_info=displacement_info, **kwargs
        )
        self.update_model()

    # ── Tendon Operations ──────────────────────────────────────────────

    def add_tendon_property(self, name: str, tendon_type: int, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_property(name=name, tendon_type=tendon_type, **kwargs)
        self.update_model()

    def add_tendon_2d(self, name: str, property_name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_2d(name=name, property_name=property_name, **kwargs)
        self.update_model()

    def add_tendon_3d(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.add_tendon_3d(name=name, **kwargs)
        self.update_model()

    def add_tendon_elements(self, ids: Any) -> None:
        self._require_available()
        ids = self._validate_ids(ids, required=True)
        self._mdb.add_tendon_elements(ids=ids)
        self.update_model()

    def add_pre_stress(
        self, case_name: str, tendon_name: str, force: float, **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_pre_stress(
            case_name=case_name, tendon_name=tendon_name, force=force, **kwargs
        )
        self.update_model()

    # ── Construction Stage Operations ──────────────────────────────────

    def add_construction_stage(
        self, name: str, duration: float, *, sub_steps: list[float] | None = None, **kwargs
    ) -> None:
        self._require_available()
        # sub_steps 与 ADD 的浮点工期在上游同一变更引入；旧版会 int(duration)。
        if not float(duration).is_integer():
            try:
                self._optional_mdb_parameter("add_construction_stage", "sub_steps", [])
            except ValueError as exc:
                raise ValueError(
                    "Installed qtmodel does not support fractional duration for "
                    "add_construction_stage; upgrade qtmodel (旧版会截断小数工期，请升级)"
                ) from exc
        options = self._optional_mdb_parameter("add_construction_stage", "sub_steps", sub_steps)
        self._mdb.add_construction_stage(name=name, duration=duration, **options, **kwargs)
        self.update_model()

    def merge_all_stages(self, name: str, **kwargs) -> None:
        self._require_available()
        self._mdb.merge_all_stages(name=name, **kwargs)
        self.update_model()

    def remove_construction_stage(self, name: str = "") -> None:
        self._require_available()
        self._mdb.remove_construction_stage(name=name)
        self.update_model()

    def update_construction_stage(
        self, name: str, *, sub_steps: list[float] | None = None, **kwargs
    ) -> None:
        self._require_available()
        options = self._optional_mdb_parameter("update_construction_stage", "sub_steps", sub_steps)
        self._mdb.update_construction_stage(name=name, **options, **kwargs)
        self.update_model()

    def switch_display_stage(self, stage_name: str) -> None:
        self._require_available()
        self._mdb.update_view_stage(stage_name=stage_name)
        self.update_model()

    # ── Analysis Operations ────────────────────────────────────────────

    def update_project_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_project_setting(**kwargs)
        self.update_model()

    def update_construction_stage_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_construction_stage_setting(**kwargs)
        self.update_model()

    def update_self_vibration_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_self_vibration_setting(**kwargs)
        self.update_model()

    def update_bulking_setting(self, **kwargs) -> None:
        self._require_available()
        self._mdb.update_bulking_setting(**kwargs)
        self.update_model()

    def add_nodal_mass(
        self,
        node_id,
        mass_xyz: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        """Add a lumped nodal mass in QiaoTong's native field layout.

        qtmodel 的 mass_info 是 (平动质量, 绕X, 绕Y, 绕Z 转动惯量)，并非 2.8.2
        docstring 自称"示例"的 (mx, my, mz, mrx)——桥通 C# 导出日志、
        get_node_mass_data 的返回说明与 2.9 docstring 三方一致。旧格式只有一个平动
        质量；2.9 起可另传 mass_xyz=(mX, mY, mZ) 表达各向不同的平动质量，导出日志中
        此时 mass_info 首项取 mZ。

        三向相等时始终走旧格式（任何版本的桥通都认）；三向不等时必须由 qtmodel 提供
        mass_xyz，旧版直接拒绝，而不是把三个值静默合并成一个。
        """
        self._require_available()
        mass_x, mass_y, mass_z = mass_xyz
        options: dict[str, Any] = {}
        if not (mass_x == mass_y == mass_z):
            try:
                options = self._optional_mdb_parameter(
                    "add_nodal_mass", "mass_xyz", [mass_x, mass_y, mass_z]
                )
            except ValueError as exc:
                raise ValueError(
                    "Direction-specific translational masses need a qtmodel build whose "
                    "add_nodal_mass accepts mass_xyz (2.9.0+); older builds carry one "
                    "translational mass for all directions "
                    "(各向不同的平动质量需要支持 mass_xyz 的 qtmodel 2.9.0+，旧版只能三向相同)"
                ) from exc
        self._mdb.add_nodal_mass(node_id=node_id, mass_info=[mass_z, *rotation], **options)
        self.update_model()

    def add_load_to_mass(self, name: str, factor: float = 1.0) -> None:
        self._require_available()
        self._mdb.add_load_to_mass(name=name, factor=factor)
        self.update_model()

    def add_spectrum_function(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_spectrum_function(**kwargs)
        self.update_model()

    def add_spectrum_case(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_spectrum_case(**kwargs)
        self.update_model()

    def add_time_history_function(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_history_function(**kwargs)
        self.update_model()

    def add_time_history_case(self, **kwargs) -> None:
        self._require_available()
        self._mdb.add_time_history_case(**kwargs)
        self.update_model()

    def run_analysis(self, read_timeout: int = 3600, show_view: bool = False) -> Any:
        """启动后台求解并轮询至任务真正结束，返回 qtmodel 给出的最终状态。

        do_solve 有两条互斥路径，由 sync 选择：

        - sync=True：C# 在**本次 HTTP 请求内**阻塞到求解完成，此时 wait /
          poll_interval / max_wait 全部被忽略（源码 ``if wait and not sync``），
          实际时限退化为该请求的 read_timeout（默认 600 s）。2.6.3 起 sync 默认
          为 True，因此只传 wait=True 并不会进入轮询——调用方以为给了 3600 s
          预算，实则 600 s 一到就报"请求超时"，而求解仍在桥通后台继续。
        - sync=False：立即返回启动状态，再由 wait=True 轮询
          GET-PROJECT-SOLVE-STATUS，max_wait 才是真正的求解总时限。2.8.2 的
          docstring 也明确 sync=True "大型模型可能超过代理/网络超时"。

        本方法要的正是后一条：MCP 工具承诺 read_timeout 是总时限、且求解期间
        连接保持响应（工作线程 + 进度心跳），只有轮询路径能兑现。sync 参数在
        2.5.0–2.9.x 全部支持范围内都存在，可无条件传入。

        求解失败/取消时 qtmodel 抛 RuntimeError，超时抛 TimeoutError，
        均由上层转为 ToolError。但 wait_solve 并非对所有未成功的结局都抛错：
        用户在桥通中终止求解时返回 canceled 状态，is_running 为 false 而状态
        不在成功集合时也原样返回（2.8.2 甚至先判 is_running，连 failed 也会
        静默返回）。故必须把最终状态交给调用方核对，不能以"没抛错"当成功。

        show_view=True 请求桥通显示分析进度窗口，不改变后台求解和轮询语义。
        旧版 do_solve 没有该参数时拒绝显式开启；默认调用保持旧版兼容。
        """
        self._require_available()
        options = self._optional_mdb_parameter(
            "do_solve", "show_view", True if show_view else None
        )
        return self._mdb.do_solve(
            wait=True,
            sync=False,
            poll_interval=2.0,
            max_wait=read_timeout,
            status_read_timeout=30,
            **options,
        )

    def add_node_tandem(self, *args, **kwargs):
        self._require_available()
        result = self._mdb.add_node_tandem(*args, **kwargs)
        self.update_model()
        return result

    def add_influence_plane(
        self, *args, always_divided_by_beam_shape: bool | None = None, **kwargs
    ):
        self._require_available()
        options = self._optional_mdb_parameter(
            "add_influence_plane", "always_divided_by_beam_shape", always_divided_by_beam_shape
        )
        result = self._mdb.add_influence_plane(*args, **options, **kwargs)
        self.update_model()
        return result

    # ── Result Extraction ──────────────────────────────────────────────

    def get_deformation(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        return self._odb.get_deformation(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_force(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        return self._odb.get_element_force(ids=ids, stage_id=stage_id, **kwargs)

    def get_element_stress(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        return self._odb.get_element_stress(ids=ids, stage_id=stage_id, **kwargs)

    def get_reaction(self, ids: Any, stage_id: int, **kwargs) -> str:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        return self._odb.get_reaction(ids=ids, stage_id=stage_id, **kwargs)

    def get_vibration_modal_results(self, mode: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_vibration_modal_results(mode=mode)

    def get_buckling_modal_results(self, mode: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_buckling_modal_results(mode=mode)


    def get_thickness_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_thickness_data", *args, **kwargs)

    def get_node_id(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_node_id", *args, **kwargs)

    def get_group_nodes(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_group_nodes", *args, **kwargs)

    def get_elements_by_point(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_elements_by_point", *args, **kwargs)

    def get_elements_by_material(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_elements_by_material", *args, **kwargs)

    def get_elements_by_section(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_elements_by_section", *args, **kwargs)

    def get_element_type(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_element_type", *args, **kwargs)

    def get_element_weight(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_element_weight", *args, **kwargs)

    def get_span_supports(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_span_supports", *args, **kwargs)

    def get_span_elements(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_span_elements", *args, **kwargs)

    def get_section_shape(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_section_shape", *args, **kwargs)

    def get_section_property(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_section_property", *args, **kwargs)

    def get_section_property_by_loops(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_section_property_by_loops", *args, **kwargs)

    def get_section_property_by_lines(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_section_property_by_lines", *args, **kwargs)

    def get_node_local_axis_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_node_local_axis_data", *args, **kwargs)

    def get_constraint_equation_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_constraint_equation_data", *args, **kwargs)

    def get_effective_width_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_effective_width_data", *args, **kwargs)

    def get_tendon_property_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_tendon_property_data", *args, **kwargs)

    def get_pre_stress_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_pre_stress_load_data", *args, **kwargs)

    def get_node_mass_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_node_mass_data", *args, **kwargs)

    def get_nodal_force_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_nodal_force_load_data", *args, **kwargs)

    def get_nodal_displacement_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_nodal_displacement_load_data", *args, **kwargs)

    def get_beam_element_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_beam_element_load_data", *args, **kwargs)

    def get_plate_element_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_plate_element_load_data", *args, **kwargs)

    def get_initial_tension_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_initial_tension_load_data", *args, **kwargs)

    def get_cable_length_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_cable_length_load_data", *args, **kwargs)

    def get_deviation_parameters(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_deviation_parameters", *args, **kwargs)

    def get_deviation_load_data(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_deviation_load_data", *args, **kwargs)

    def get_elements_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_elements_of_stage", *args, **kwargs)

    def get_nodes_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_nodes_of_stage", *args, **kwargs)

    def get_groups_of_stage(self, *args, **kwargs):
        self._require_available()
        return self._query_model("get_groups_of_stage", *args, **kwargs)

    def get_self_concurrent_reaction(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_self_concurrent_reaction(*args, **kwargs)

    def get_all_concurrent_reaction(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_all_concurrent_reaction(*args, **kwargs)

    def get_concurrent_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_concurrent_force(*args, **kwargs)

    def get_elastic_link_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_elastic_link_force(*args, **kwargs)

    def get_constrain_equation_force(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_constrain_equation_force(*args, **kwargs)

    def get_cable_element_length(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_cable_element_length(*args, **kwargs)

    def get_period_and_vibration_results(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_period_and_vibration_results(*args, **kwargs)

    def get_buckling_eigenvalue(self, *args, **kwargs):
        self._require_available()
        return self._odb.get_buckling_eigenvalue(*args, **kwargs)
    def get_tendon_loss_results(self, name: str, stage_id: int = 1) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_loss_results(name=name, stage_id=stage_id)

    def get_tendon_position_result(self, name: str) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_position_result(name=name)

    def get_tendon_length_result(self) -> list[dict]:
        self._require_available()
        return self._odb.get_tendon_length_result()

    # ── Visualization ──────────────────────────────────────────────────

    def display_node_id(self, show_id: bool = True) -> None:
        self._require_available()
        self._odb.display_node_id(show_id=show_id)

    def display_element_id(self, show_id: bool = True) -> None:
        self._require_available()
        self._odb.display_element_id(show_id=show_id)

    def set_view_direction(self, **kwargs) -> None:
        self._require_available()
        self._odb.set_view_direction(**kwargs)

    def activate_structure(self, **kwargs) -> None:
        self._require_available()
        self._odb.activate_structure(**kwargs)

    def set_render(self, flag: bool = True) -> None:
        self._require_available()
        self._odb.set_render(flag=flag)

    def reset_display(self) -> None:
        self._require_available()
        self._odb.reset_display()

    def set_unit(self, unit_force: str = 'KN', unit_length: str = 'MM') -> None:
        self._require_available()
        self._odb.set_unit(unit_force=unit_force, unit_length=unit_length)

    def change_construct_stage(self, stage: int = 0) -> None:
        self._require_available()
        self._odb.change_construct_stage(stage=stage)

    def save_model_image(self, file_path: str) -> str:
        self._require_available()
        return self._odb.save_png(file_path=file_path)

    def plot_result(self, result_type: str, file_path: str, **kwargs) -> str:
        self._require_available()
        plot_methods = {
            "displacement": self._odb.plot_displacement_result,
            "reaction": self._odb.plot_reaction_result,
            "beam_force": self._odb.plot_beam_element_force,
            "beam_stress": self._odb.plot_beam_element_stress,
            "truss_force": self._odb.plot_truss_element_force,
            "truss_stress": self._odb.plot_truss_element_stress,
            "plate_force": self._odb.plot_plate_element_force,
            "plate_stress": self._odb.plot_plate_element_stress,
            "modal": self._odb.plot_modal_result,
        }
        method = plot_methods.get(result_type)
        if method is None:
            raise ValueError(
                f"Unknown result_type '{result_type}'. "
                f"Available types: {list(plot_methods.keys())}"
            )
        return method(file_path=file_path, **kwargs)

    # ── Validation ─────────────────────────────────────────────────────

    def validate_model(self) -> dict[str, Any]:
        self._require_available()
        errors = []
        warnings = []

        # Check for overlapping nodes
        overlap_nodes = self._query_model("get_overlap_nodes")
        if overlap_nodes:
            warnings.append(
                f"Found {len(overlap_nodes)} groups of overlapping nodes "
                f"(发现 {len(overlap_nodes)} 组重合节点): {overlap_nodes[:5]}..."
            )

        # Check for overlapping elements
        overlap_elements = self._query_model("get_overlap_elements")
        if overlap_elements:
            warnings.append(
                f"Found {len(overlap_elements)} groups of overlapping elements "
                f"(发现 {len(overlap_elements)} 组重合单元): {overlap_elements[:5]}..."
            )

        # Check basic model existence
        summary = self.get_model_summary()
        if summary["node_count"] == 0:
            errors.append("Model has no nodes (模型无节点)")
        if summary["element_count"] == 0:
            errors.append("Model has no elements (模型无单元)")
        if summary["material_count"] == 0:
            errors.append("Model has no materials (模型无材料)")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
        }

    # ── Structural Checking ────────────────────────────────────────────

    def add_check_load_combine(
        self, name: str, standard: int, combine_type: int, combine_method: int, **kwargs
    ) -> None:
        self._require_available()
        # 2.5.0 起：旧 kind → combine_type（组合类型：基本/偶然/标准…），
        # 旧 combine_type → combine_method（组合方式：1-相加并判别 2-包络），index 已移除
        self._cdb.add_check_load_combine(
            name=name,
            standard=standard,
            combine_type=combine_type,
            combine_method=combine_method,
            **kwargs,
        )

    def solve_concrete_check(
        self,
        name: str,
        wait: bool = True,
        max_wait: float | None = None,
        poll_interval: float = 5.0,
    ) -> Any:
        """同步指定检算工况后启动检算；返回启动或等待结束后的原生状态。

        2.5.0 起 solve_concrete_check 不再接受 name，改为对"当前检算数据"求解，
        故先用 import_concrete_check_case 把目标工况同步为当前 CSAN 检算数据。
        旧版等待器在 is_running=False 时直接返回，失败/取消也可能不抛错；
        调用方必须核对返回状态后再报告成功。
        """
        self._require_available()
        self._cdb.import_concrete_check_case(case_name=name)
        return self._cdb.solve_concrete_check(
            wait=wait,
            poll_interval=poll_interval,
            max_wait=max_wait,
        )

    def add_concrete_check_case(
        self, name: str, standard: int, structure_type: int, group_name: str
    ) -> None:
        self._require_available()
        self._cdb.add_concrete_check_case(name=name, standard=standard, structure_type=structure_type, group_name=group_name)

    def add_parameter_reinforcement(self, sec_id: int, **kwargs) -> None:
        self._require_available()
        self._cdb.add_parameter_reinforcement(sec_id=sec_id, **kwargs)

    def add_check_stirrup(
        self,
        stirrup_id: int,
        name: str,
        stirrup_type: int = 1,
        rebar_material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter_m: float = 0.020,
        spacing_m: float = 0.2,
        core_diameter_m: float = 0.0,
    ) -> None:
        """添加检算箍筋定义（2.5.0 起取代 add_steel_hoop）。

        入参统一用 SI（米），此处换算为 qtmodel 2.5.0 要求的单位：
        箍筋直径 m → mm；间距与核心直径仍为 m。
        """
        self._require_available()
        self._cdb.add_check_stirrup(
            stirrup_id=stirrup_id,
            name=name,
            stirrup_type=stirrup_type,
            rebar_material_id=rebar_material_id,
            limbs_number=limbs_number,
            loops_number=loops_number,
            stirrup_diameter=diameter_m * 1000.0,  # m → mm
            stirrup_spacing=spacing_m,
            core_diameter=core_diameter_m,
        )

    def update_vertical_steel_tendon(
        self,
        limbs_number: int = 0,
        area_m2: float = 0.000804,
        spacing_m: float = 0.2,
        effective_prestress_pa: float = 8.0e8,
        fpd_pa: float = 9.0e8,
    ) -> None:
        """修改竖向钢束设置（2.5.0 起取代 update_vertical_steel_hoop）。

        入参统一用 SI（m²/Pa），此处换算为 qtmodel 2.5.0 要求的单位：
        面积 m² → mm²（×1e6）；应力 Pa → MPa（÷1e6）。
        """
        self._require_available()
        self._cdb.update_vertical_steel_tendon(
            limbs_number=limbs_number,
            single_limb_area=area_m2 * 1.0e6,  # m² → mm²
            spacing=spacing_m,
            effective_prestress=effective_prestress_pa / 1.0e6,  # Pa → MPa
            strength_design_value=fpd_pa / 1.0e6,  # Pa → MPa
        )

    def get_reinforcement_data(self) -> dict[str, Any]:
        self._require_available()
        return self._cdb.get_reinforcement_data()

    # ── Concrete Check: 2.5.0 新增能力 ─────────────────────────────────
    #
    # 说明：cdb 的检算设置类接口（*_analysis_setting）在 qtmodel 源码与官方
    # 文档中均未标注量纲，但从默认值可判定为 mm/MPa（如保护层 30.0=30mm、
    # 钢筋疲劳限值 145.0=145MPa）。因未见权威单位说明，此处**不做换算**，
    # 按原生单位透传，由工具层 docstring 明确告知调用方。

    # 查询：全部为读操作，直接透传 qtmodel 返回值
    _CHECK_QUERY_METHODS = {
        "case": "get_concrete_check_case",
        "basic_info": "get_check_case_basic_info",
        "materials": "get_check_case_material_infos",
        "vertical_prestress": "get_check_case_vertical_prestress_info",
        "stirrups": "get_check_case_stirrup_infos",
        "reinforcement": "get_check_case_reinforcement_data",
        "tendon_section": "get_check_case_prestress_tendon_sec_info",
        "section_property": "get_check_case_section_property",
        "element_table": "get_element_table_info",
        "solve_status": "get_concrete_check_solve_status",
        "normal_section_bearing_setting": "get_normal_section_bearing_analysis_setting",
        "oblique_shear_bearing_setting": "get_oblique_section_shear_bearing_analysis_setting",
        "limit_state_setting": "get_limit_state_method_analysis_setting",
        "normal_stress_setting": "get_normal_stress_analysis_setting",
        "crack_width_setting": "get_crack_width_analysis_setting",
        "moment_curvature_setting": "get_moment_curvature_curve_analysis_setting",
        "bearing_curve_setting": "get_bearing_curve_analysis_setting",
    }

    def get_check_data(self, kind: str, **kwargs) -> Any:
        """按 kind 读取检算数据；kind 到 qtmodel 方法的映射见 _CHECK_QUERY_METHODS。"""
        self._require_available()
        if kind in self._CHECK_QUERY_METHODS:
            method = getattr(self._cdb, self._CHECK_QUERY_METHODS[kind])
            return method(**{k: v for k, v in kwargs.items() if v is not None})
        # 需要参数的查询单独分派
        if kind == "stress":
            return self._cdb.get_concrete_check_stress_info(
                stress_type=kwargs.get("stress_type", 1),
                specific_load_type_name=kwargs.get("name", ""),
            )
        if kind == "load_table":
            return self._cdb.get_check_case_load_table_info(
                combine_type=kwargs.get("combine_type", 1),
                specific_load_type_name=kwargs.get("name", ""),
            )
        if kind == "shear_stirrup":
            ele_id = kwargs.get("element_id")
            return self._cdb.get_element_shear_stirrup_data(
                ele_id=-1 if ele_id is None else ele_id
            )
        if kind == "torsion_stirrup":
            ele_id = kwargs.get("element_id")
            return self._cdb.get_element_torsion_stirrup_data(
                ele_id=-1 if ele_id is None else ele_id
            )
        raise ValueError(f"unknown check data kind: {kind}")

    # 分析设置：kind → qtmodel update 方法；参数原样透传（原生 mm/MPa）
    _CHECK_SETTING_METHODS = {
        "normal_section_bearing": "update_normal_section_bearing_analysis_setting",
        "oblique_shear_bearing": "update_oblique_section_shear_bearing_analysis_setting",
        "limit_state": "update_limit_state_method_analysis_setting",
        "normal_stress": "update_normal_stress_analysis_setting",
        "crack_width": "update_crack_width_analysis_setting",
        "moment_curvature": "update_moment_curvature_curve_analysis_setting",
        "bearing_curve": "update_bearing_curve_analysis_setting",
    }

    def configure_check_analysis(self, kind: str, settings: dict[str, Any]) -> None:
        """更新某一类检算分析设置；settings 按 qtmodel 原生参数名与单位传入。"""
        self._require_available()
        if kind not in self._CHECK_SETTING_METHODS:
            raise ValueError(f"unknown analysis setting kind: {kind}")
        getattr(self._cdb, self._CHECK_SETTING_METHODS[kind])(**settings)

    def update_check_stirrup(
        self,
        stirrup_id: int,
        name: str,
        stirrup_type: int = 1,
        rebar_material_id: int = 1,
        limbs_number: int = 2,
        loops_number: int = 2,
        diameter_m: float = 0.020,
        spacing_m: float = 0.2,
        core_diameter_m: float = 0.0,
    ) -> None:
        """修改检算箍筋定义；直径由 m 换算为 qtmodel 要求的 mm。"""
        self._require_available()
        self._cdb.update_check_stirrup(
            stirrup_id=stirrup_id,
            name=name,
            stirrup_type=stirrup_type,
            rebar_material_id=rebar_material_id,
            limbs_number=limbs_number,
            loops_number=loops_number,
            stirrup_diameter=diameter_m * 1000.0,  # m → mm
            stirrup_spacing=spacing_m,
            core_diameter=core_diameter_m,
        )

    def remove_check_stirrup(self, stirrup_id: int = -1, name: str = "") -> None:
        self._require_available()
        self._cdb.remove_check_stirrup(stirrup_id=stirrup_id, name=name)

    def set_element_shear_stirrup(
        self,
        element_id: int,
        stirrup_i_y: int = 1,
        stirrup_i_x: int = 1,
        stirrup_j_y: int = 1,
        stirrup_j_x: int = 1,
    ) -> None:
        self._require_available()
        self._cdb.add_element_shear_stirrup(
            ele_id=element_id,
            stirrup_i_y=stirrup_i_y,
            stirrup_i_x=stirrup_i_x,
            stirrup_j_y=stirrup_j_y,
            stirrup_j_x=stirrup_j_x,
        )

    def set_element_torsion_stirrup(
        self, element_id: int, stirrup_i: int = 1, stirrup_j: int = 1
    ) -> None:
        self._require_available()
        self._cdb.add_element_torsion_stirrup(
            ele_id=element_id, stirrup_i=stirrup_i, stirrup_j=stirrup_j
        )

    def remove_element_stirrup(
        self, element_id: int = -1, remove_shear: bool = True, remove_torsion: bool = True
    ) -> None:
        """删除单元箍筋设置；element_id<=0 表示删除全部。"""
        self._require_available()
        self._cdb.remove_element_stirrup(
            ele_id=element_id, remove_shear=remove_shear, remove_torsion=remove_torsion
        )

    def open_check_case(self, name: str = "", file_path: str = "") -> Any:
        self._require_available()
        return self._cdb.open_concrete_check_case(name=name, file_path=file_path)

    def save_check_case(self, file_path: str = "") -> Any:
        """保存当前检算工况；给出 file_path 时另存为该路径。"""
        self._require_available()
        if file_path:
            return self._cdb.save_as_check_case(file_path=file_path)
        return self._cdb.save_check_case()

    # ── Group Management ───────────────────────────────────────────────

    def add_structure_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_structure_group(name=name)
        self.update_model()

    def update_structure_group_name(self, name: str, new_name: str) -> None:
        self._require_available()
        self._mdb.update_structure_group_name(name=name, new_name=new_name)
        self.update_model()

    def remove_structure_group(self, name: str = "") -> None:
        self._require_available()
        if name:
            self._mdb.remove_structure_group(name=name)
        else:
            self._mdb.remove_structure_group()
        self.update_model()

    def add_structure_to_group(
        self, name: str, node_ids: Any = None, element_ids: Any = None
    ) -> None:
        """Add nodes and/or elements to a structure group. 向结构组添加节点/单元"""
        self._require_available()
        if node_ids is None and element_ids is None:
            raise ValueError("Explicit node_ids or element_ids are required (必须明确指定要加入的成员)")
        if node_ids is not None:
            node_ids = self._validate_ids(node_ids, required=True)
        if element_ids is not None:
            element_ids = self._validate_ids(element_ids, required=True)
        self._mdb.add_structure_to_group(
            name=name, node_ids=node_ids, element_ids=element_ids
        )
        self.update_model()

    def add_elements_to_structure_group(self, name: str, element_ids: Any) -> None:
        self.add_structure_to_group(name=name, element_ids=element_ids)

    def get_structure_group_elements(self, name: str) -> list:
        self._require_available()
        # qtmodel 的参数名为 group_name
        return self._query_model("get_group_elements", group_name=name) or []

    def add_boundary_group(self, name: str) -> None:
        self._require_available()
        self._mdb.add_boundary_group(name=name)
        self.update_model()

    # ── Advanced Boundary ──────────────────────────────────────────────

    def add_master_slave_link(self, master_id: int, slave_id: Any, **kwargs) -> None:
        self._require_available()
        self._mdb.add_master_slave_link(
            master_id=master_id, slave_id=slave_id, **kwargs
        )
        self.update_model()

    def add_elastic_support(
        self, node_id: Any, support_type: int = 1, boundary_info: list | None = None,
        *, coordinate: int | None = None, extra_enabled: bool | None = None,
        extra_parameters: list[float] | None = None, axis_direction: int | None = None,
        **kwargs,
    ) -> None:
        self._require_available()
        if extra_parameters is not None and extra_enabled is None:
            extra_enabled = True
        options = self._optional_mdb_parameters(
            "add_elastic_support", coordinate=coordinate, extra_enabled=extra_enabled,
            extra_parameters=extra_parameters, axis_direction=axis_direction,
        )
        arguments = {"node_id": node_id, "support_type": support_type,
                     "boundary_info": boundary_info, **options, **kwargs}
        method = "add_elastic_support"
        fn = self._validated_method("mdb", method, arguments)
        self._execute_model_command(fn, method, arguments)

    # ── Moving Loads ───────────────────────────────────────────────────

    def add_standard_vehicle(
        self, name: str, standard_code: int = 1, load_type: str = "公路I级车道", **kwargs
    ) -> None:
        self._require_available()
        self._mdb.add_standard_vehicle(
            name=name, standard_code=standard_code, load_type=load_type, **kwargs
        )
        self.update_model()

    def add_lane(self, name: str, **kwargs) -> None:
        self._require_available()
        # Real API method is add_lane_line
        self._mdb.add_lane_line(name=name, **kwargs)
        self.update_model()

    def add_live_load_case(
        self, name: str, *, sub_case_optimized: list[bool] | None = None, **kwargs
    ) -> None:
        self._require_available()
        options = self._optional_mdb_parameter(
            "add_live_load_case", "sub_case_optimized", sub_case_optimized
        )
        self._mdb.add_live_load_case(name=name, **options, **kwargs)
        self.update_model()

    def get_live_load_results(self, case_name: str, result_type: str, ids: Any) -> Any:
        self._require_available()
        if ids is not None:
            ids = self._validate_ids(ids, allow_empty=True)
        # Live load results are embedded in standard result queries (deformation/force/stress)
        # Query using the live load case name directly
        if result_type == "force":
            return self._odb.get_element_force(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "stress":
            return self._odb.get_element_stress(ids=ids, stage_id=-1, case_name=case_name)
        elif result_type == "deformation":
            return self._odb.get_deformation(ids=ids, stage_id=-1, case_name=case_name)
        else:
            raise ValueError(
                f"Unknown result_type '{result_type}'. "
                "Available: force, stress, deformation"
            )

    # ── Self-weight ────────────────────────────────────────────────────

    def set_weight_stage(
        self, stage_name: str, structure_group_name: str = "默认结构组", weight_stage_id: int = 1
    ) -> None:
        """Set which construction stage accounts for a structure group's self-weight.

        QiaoTong 中自重不是一个"荷载工况"，而是由施工阶段的"计自重阶段号"控制：
        weight_stage_id: 0=不计自重, 1=本阶段, n=第 n 阶段。
        重力加速度由 update_project_setting(gravity=...) 决定。
        """
        self._require_available()
        self._mdb.update_weight_stage(
            name=stage_name,
            structure_group_name=structure_group_name,
            weight_stage_id=weight_stage_id,
        )
        self.update_model()

    # ── Tendon Data ────────────────────────────────────────────────────

    def get_tendon_data(self) -> list[dict]:
        self._require_available()
        return self._query_model("get_tendon_data") or []

    # ── Visualization Control ──────────────────────────────────────────

    def set_view_angle(self, horizontal: float, vertical: float) -> None:
        self._require_available()
        self._odb.set_view_direction(
            horizontal_degree=horizontal, vertical_degree=vertical
        )
