# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

Qiao-MCP 是一个 MCP 服务器,把桥梁结构分析软件(当前仅支持桥通/QiaoTong,经 `qtmodel` Python API)的能力暴露给 AI 助手:建模、施工阶段、荷载、预应力、活载、规范验算、结果查询。共 132 个工具、7 个资源、4 个提示模板。

## 常用命令

```bash
uv sync                                        # 安装依赖(含 ruff/mypy/pytest)
uv run qiao-mcp                                # 启动服务器(stdio;无需桥通运行也能启动)
npx @modelcontextprotocol/inspector uv run qiao-mcp   # MCP Inspector 手动测试

uv run ruff check src/ tests/                  # Lint
uv run mypy src/qiao_mcp/                      # 类型检查(渐进式,不强制全量注解)
uv run pytest tests/ --ignore=tests/test_end_to_end.py -q   # 离线全量测试(默认应这样跑)

# 单个测试文件 / 单个用例
uv run pytest tests/test_provider_dispatch.py -q
uv run pytest tests/test_solve_semantics.py::test_specific -q

# 用上游源码跑离线测试(不替换已装的包)
PYTHONPATH=reference_codes/qtmodel-release/packages/qtmodel/src:src \
  uv run pytest tests/ --ignore=tests/test_end_to_end.py -q
```

- 离线测试不需要桥通软件:provider 层用 `tests/conftest.py` 的 `FakeDb`(记录全部调用的假 mdb/odb/cdb)+ `__new__` 跳过 `__init__` 构造的 provider 实例。
- `tests/test_end_to_end.py` 需要桥通运行且设置 `QIAOTONG_HTTP_URL`,会**清空并重建活动模型**——本机没有桥通时它自行 skip(CI 里就是靠 skip 通过的),但本地跑全量时仍建议 `--ignore` 它。
- CI(`.github/workflows/ci.yml`)跑 ruff + mypy + pytest,push 到 develop/main 时触发。

## 架构

### Provider 模式(核心解耦)

```
src/qiao_mcp/
├── server.py                  # 入口:构造 provider → 动态生成 server instructions → 注册工具
├── tools/                     # 工具层,按工作域分模块(按 Phase 1–5 演进而来)
│   ├── __init__.py            # 建模核心(create_nodes、create_section 等)
│   ├── envelope.py            # 统一返回协议 + 工具分类(权限映射)— 关键模块,见下
│   ├── api_gateway.py         # list_qtmodel_api / call_qtmodel_api 逃生舱
│   ├── queries.py / modifications.py / checking.py / tendon.py / moving_load.py
│   ├── advanced_boundary.py / group_management.py / visualization.py / workflows.py
├── providers/
│   ├── __init__.py            # BridgeProvider 抽象基类 + 注册表 + create_provider
│   └── qtmodel_provider.py    # 唯一后端:桥通适配器(约 2200 行)
├── resources/  prompts/       # MCP Resources / Prompts
```

- **`BridgeProvider`** 只声明稳定契约(身份、可用性、`get_llm_instructions`、生命周期方法);大量建模/查询方法由具体 Provider 直接实现,工具层经 `__getattr__` 类型存根直接调用——**不要**往基类回填抽象方法(历史上 100+ 抽象方法与实现漂移,已被刻意删掉)。
- 后端由 `BRIDGE_PROVIDER` 环境变量选择(默认 `qtmodel`),注册表在 `providers/__init__.py` 的 `_PROVIDERS`。未知取值抛 ValueError,不静默回落。
- 新增后端 = 实现 `BridgeProvider` + 注册一行,工具层零改动。

### 工具返回协议(envelope)

所有工具经 `register_tools_with_envelope` 包装(`server.py` 的 `_TOOL_REGISTRARS` 列表统一注册):

- 成功:返回 dict(结构化内容)或 str(自动包裹为 `{status, message}`)
- 失败:`raise ToolError(...)`;输入不合法用 `ToolInputError`(`tools/envelope.py`)
- `envelope.py` 同时把每个工具名映射到桥通能力类别(`model_read`/`model_write`/`stage_write`/`result_read`/`check_*`/`analysis_run`/`view`/`lifecycle`/`connection`),用于模型状态守卫

### 模型状态守卫

每个工具调用前经 `provider.ensure_operation_allowed(operation)` 检查桥通报告的模型状态(`QtServer.get_model_state`)。两种"状态不可用"要区分:

- `guard_unavailable`(安装的 qtmodel 没有该方法)→ 放行,保持旧行为
- `state_unknown`(qtmodel 有 API 但桥通太旧没发状态)→ fail closed

## qtmodel 上游的关键事实(改动依赖相关代码前必读)

- **锁 mcp 1.x**:`mcp[cli]>=1.29,<2`——mcp 2.0 移除了 `mcp.server.fastmcp`,迁移未完成前不要升。
- **"2.8.2" 不是同一个东西**:PyPI wheel(2026-08-20 打包自上游 340e94e)没有 `get_model_state`;上游源码同样标 2.8.2 却有。**按能力探测判断,不能按版本号判断**。`reference_codes/qtmodel-release/` 是嵌套的上游仓库(非 submodule),可 `git -C reference_codes/qtmodel-release log` 考证。
- **qtmodel 2.6/2.7 有精确版本握手**(不匹配拒连),2.8.2 起移除——所以 `check_qiaotong_connection` 的 `version_mismatch` 状态在 2.8.2 上不会再出现。
- 依赖上界 `qtmodel>=2.6.3,<2.9` 的注释(pyproject.toml)记录了每次收放的原因,调整前先读。
- `do_solve` 的 `sync=True` 默认值(2.6.3 起)会禁用 `max_wait` 等待语义——provider 调用时**始终显式传 `sync=False`**。
- 模型查询方法 2.8 起从 `odb` 迁到 `mdb`(provider 优先 `mdb`、缺方法时回落 `odb`);上游返回的 typed record 需递归转成纯 JSON(`to_dict()`/`Mapping`)。
- MDB 查询用读权限、不刷新模型;`calculate_section_property` 等仍需模型写权限。

## 测试约定

- `pyproject.toml` 的 `testpaths = ["tests"]` 是为了**防止 pytest 递归收集 `reference_codes/` 下嵌套上游仓库的同名测试**(会 import file mismatch)。不要移除。
- 合同测试(`test_qtmodel_contract.py`)对着**已安装的** qtmodel 真实签名校验 provider 调用;`test_qtserver_integration.py` 等用 FakeDb 做分发测试。
- 测试经 `from conftest import ...` 导入(靠 pytest rootdir 注入),`tests/*` 对 E402 有豁免。

## 发版注意

版本号散在四处,没有一致性测试:`pyproject.toml`、`server.json` 的顶层 `version`、`server.json` packages 里的 `version`、`CHANGELOG.md`。发版时四处都要改。兼容性表格(README + CHANGELOG)在换 qtmodel minor 线时要加行。
