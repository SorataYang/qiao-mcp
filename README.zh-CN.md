# 🌉 Qiao-MCP

[English](./README.md) · **简体中文**

> 桥梁全过程结构分析 MCP 服务器 — 建模、施工阶段、规范验算  
> Full-lifecycle bridge structural analysis — modeling, staging, code checks

Qiao-MCP 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务器，让 AI 助手能够与桥梁结构分析软件交互。它提供了创建桥梁模型、施加荷载、运行结构分析和查看结果的工具。

## 功能特性

### 🔧 工具（132 个，按功能分组）

工具按桥梁建模与分析工作流分组。以下是各组代表工具：

| 分组 | 代表工具 |
|------|----------|
| **核心建模** | `create_nodes_linear`、`create_beam_elements_linear`、`create_material`、`create_section`（支持参数化截面）、`create_polygon_section`、`add_thickness`（支持独立面外厚度） |
| **荷载** | `create_load_group`、`create_load_case`、`set_self_weight_stage`、`set_gravity`、`apply_nodal_force`、`apply_beam_distributed_load`、温度/沉降荷载 |
| **边界条件** | `set_support`、`add_elastic_link`、`add_master_slave_link`、`add_elastic_support`、`add_beam_constraint` |
| **分组与阶段** | `create_structure_group`、`add_elements_to_group`、`merge_operation_stage`、`add_construction_stage` |
| **分析** | `configure_analysis`、`run_analysis`（异步并报告进度，可选 `show_view`）、`get_analysis_results` |
| **预应力钢束** | `create_tendon_property`、`create_tendon_2d`、`apply_prestress`、`get_tendon_info` |
| **移动荷载** | `add_node_tandem`、`add_influence_plane`、`add_traffic_lane`、`add_standard_vehicle`、`create_live_load_case` |
| **结构验算** | `setup_concrete_check`、`add_check_load_combination`、`add_parametric_reinforcement`、`run_concrete_check`、`get_check_data` |
| **查询** | `get_model_info`、`get_model_data`（按 kind 查询，含 qtmodel 2.8 概览类型 `summary` / `analysis_context` / `project_metadata` / `check_context`）、`find_entities`、`calc_section_property`、`get_special_results`（适用时支持分页） |
| **模型修改** | `initialize_model`、`save_model_file`、`open_model_file`、`update_node`、`move_nodes`、`update_element`、`remove_nodes`、`remove_elements` |
| **可视化** | `save_model_screenshot`、`plot_analysis_result`（可直接返回图像）、`set_view_angle`、`display_ids` |
| **工作流** | `create_simple_beam_bridge`、`create_continuous_beam_bridge` |
| **网关与诊断** | `check_qiaotong_connection`、`get_model_status`、`list_qtmodel_api`、`call_qtmodel_api`（连接与模型状态诊断、长尾 API 检索与签名校验调用） |

工具返回会统一规范为结构化内容（`{status, ...}`）；图像工具可以直接返回 MCP 图像内容。工具失败会使用类型化 MCP 错误；只读、破坏性和开放世界操作带有 MCP 工具注解。调用网关中的未封装 API 前，请先使用 `list_qtmodel_api` 查询真实签名。

### 📦 资源 (7个)
| URI | 描述 |
|-----|-------------|
| `bridge://model/summary` | 模型概览 |
| `bridge://model/materials` | 材料列表 |
| `bridge://model/sections` | 截面列表 |
| `bridge://model/load-cases` | 荷载工况 |
| `bridge://model/stages` | 施工阶段 |
| `bridge://model/structure-groups` | 结构组 |
| `bridge://model/boundaries` | 边界条件 |

### 💬 提示词 (4个工作流)
| 提示词 | 描述 |
|--------|-------------|
| `design-simple-beam` | 简支梁桥设计工作流 |
| `design-continuous-beam` | 连续梁桥设计 |
| `check-structure` | 结构规范验算 |
| `construction-stage-analysis` | 施工阶段分析 |

## 架构设计

```
qiao-mcp/
├── src/qiao_mcp/
│   ├── server.py              # MCP 服务器入口
│   ├── tools/                 # MCP 工具（统一返回协议包装）
│   ├── resources/             # MCP 资源
│   ├── prompts/               # MCP 提示词
│   └── providers/             # 后端适配器
│       ├── __init__.py        # BridgeProvider 抽象基类
│       └── qtmodel_provider.py  # 桥通软件适配器
├── tests/                     # 离线单元、集成与 API 契约测试
└── reference-docs/            # 评审记录与项目文档
```

**Provider 模式**让 132 个工具与具体后端解耦。用 `BRIDGE_PROVIDER` 选择后端；每个后端自己声明软件专有规则，因此换后端无需改提示词。当前支持：
- **QTModel**（`qtmodel`，默认）— [桥通 (QiaoTong)](https://www.brdi.com.cn/Software.html) 桥梁分析软件（[用户手册](https://soratayang.github.io/)）

接入新后端只需实现 `BridgeProvider` 并登记一行，不改工具层代码。详见 [后端选择](./INTEGRATION_GUIDE.md#后端选择-backend-selection)。

## 快速开始

### 前置要求
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- `qtmodel` 2.6.3 – 2.8.x（`uv sync` 会自动安装，当前锁定 2.8.2）
- 调用建模、分析或可视化工具时，需要运行桥通软件（版本搭配见下文[兼容性对照](#兼容性对照)）

桥通未启动时 MCP 服务器仍可启动。调用 `check_qiaotong_connection` 可以区分已连接与软件未启动；调用 `get_model_status` 可以查看是否已打开模型、以及当前桥通状态允许哪些操作。

### 安装与运行

```bash
# 安装依赖
uv sync

# 运行服务器
uv run qiao-mcp
```

### 在 Claude Desktop 中配置

编辑 `claude_desktop_config.json` 文件：

```json
{
  "mcpServers": {
    "qiao-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/qiao-mcp", "run", "qiao-mcp"]
    }
  }
}
```

### 在 Cursor 中配置

创建 `.cursor/mcp.json` 文件：

```json
{
  "mcpServers": {
    "qiao-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/qiao-mcp", "run", "qiao-mcp"]
    }
  }
}
```

### 在 Reasonix 中配置（UI 界面）

打开 **Settings** → **MCP & Tools**，然后添加新的 MCP 服务器：

- **Name**: `qiao-mcp`
- **Transport**: `stdio`（保持默认）
- **Command**: `uv --directory /path/to/qiao-mcp run qiao-mcp`
  - 将 `/path/to/qiao-mcp` 替换为你的实际项目路径
  - Windows: 使用反斜杠 `D:\path\to\qiao-mcp`
  - macOS/Linux: 使用正斜杠 `/path/to/qiao-mcp`
- **Environment**（可选）: `UV_PYTHON=3.11`

点击 **Add** 保存。

### 在 Cherry Studio 中配置（UI 界面）

打开 **设置** → **扩展** → **MCP Servers**，然后添加新服务器：

- **名称**: `qiao-mcp`
- **描述**: 可选描述
- **类型**: `标准输入 / 输出 (stdio)`
- **命令**: `uv`
- **包管理器**: 选择 `默认`
- **参数**: 
  ```
  /path/to/qiao-mcp
  run
  qiao-mcp
  ```
  （每行一个参数，无需 `--directory` 前缀）
  - 将 `/path/to/qiao-mcp` 替换为你的实际项目路径

点击 **保存**。

### 使用 MCP Inspector 测试

```bash
npx @modelcontextprotocol/inspector uv run qiao-mcp
```

### 局域网调试转发

跨机器调试时，可以运行 [`scripts/qiaotong_lan_proxy.py`](./scripts/qiaotong_lan_proxy.py)，将局域网端口转发到代理所在机器上的桥通 API。脚本默认监听 `45125`，并转发到选定桥通进程的 `127.0.0.1:55125`：

```bash
python scripts/qiaotong_lan_proxy.py
```

客户端机器设置：

```python
from qtmodel import mdb

mdb.set_url("http://<代理机器局域网IP>:45125/pythonForQt/")
```

代理会在终端输出每次转发请求和响应。多个桥通进程同时运行时，请为该固定代理保留 `55125`，或者为不同进程分别启动不同监听端口的代理实例。

也可以使用 SSH 隧道，不直接暴露局域网 API 端口：

```bash
ssh -N -L 45125:127.0.0.1:55125 <用户名>@<桥通机器局域网IP>
```

隧道运行期间，客户端使用 `http://localhost:45125/pythonForQt/`。此场景下
Windows HTTP.sys 会校验 `Host` 请求头，并以 `400 Invalid Hostname` 拒绝
`127.0.0.1`。

## 开发

```bash
# 开发模式安装
uv sync

# 直接运行
uv run python -m qiao_mcp.server

# 质量检查
uv run ruff check src/ tests/
uv run mypy src/qiao_mcp/
uv run pytest tests/ --ignore=tests/test_end_to_end.py -q
```

测试设计为离线运行，不要求桥通软件。Provider/tool 调用会根据已安装的 `qtmodel` 真实 API 签名进行契约校验，并通过进程内 fake backend 验证分发逻辑。

## 后端软件：QTModel（桥通）

本 MCP 服务器封装了 `qtmodel` Python API，提供以下功能：
- **mdb** — 模型数据库：查询、构建和修改桥梁模型
- **odb** — 输出数据库：查询分析结果和可视化
- **cdb** — 验算数据库：结构验算和规范检查

## 版本策略

Qiao-MCP 的版本号独立于 `qtmodel`：本项目可以自行迭代（修 bug、加工具、补文档）而不必等后端发版，后端发版也不强制本项目跟着跳版本。对后端的要求写在依赖约束里，而不是编码进版本号。

### 兼容性对照

| Qiao-MCP        | qtmodel       | 桥通软件                               |
|-----------------|---------------|----------------------------------------|
| 0.3.2（未发布） | 2.6.3 – 2.8.x | 2.6.3+；2.8.x 不再要求两侧版本精确一致 |
| 0.3.0 – 0.3.1   | 2.6.3 – 2.6.x | 2.6.3（qtmodel 强制精确匹配）          |
| 0.2.x           | 2.5.0 – 2.5.x | 2.5.0                                  |

两侧版本的匹配方式在 qtmodel 2.8.2 发生了变化：

- **qtmodel 2.6 / 2.7** 做精确版本握手——桥通 API 版本与已安装的 `qtmodel` 必须完全一致，否则 `check_qiaotong_connection` 报 `version_mismatch` 并拒绝连接。
- **qtmodel 2.8.2** 取消了该握手。任何暴露 Python API 的桥通都能连上，`version_mismatch` 不再出现。代价是偏旧的桥通可能缺少新命令；`get_model_status` 会把这种情况报为 `state_unknown`（桥通早于模型状态握手），工具据此 fail closed，而不是盲写。

不同构建可能都标记为 qtmodel 2.8.2：PyPI 上的 wheel（2026-08-20）不含 `QtServer.get_model_state`，而同版本号的上游源码已带上它。Qiao-MCP 按能力而非版本号探测——没有该方法时跳过模型状态守卫（`guard_unavailable`），行为与 0.3.1 一致；有该方法时，每个工具都会按桥通上报的状态放行或拦截。

### 2026-09-04 至 09-08 上游源码变更

参考仓库已同步至 `2316654`，版本号仍为 `2.8.2`：

- `ac4dbad`：模型查询由 `odb` 迁移至 `mdb`。本项目优先使用新接口，方法不存在时回退至旧版 `odb`；查询已有截面几何使用 `mdb.get_model_section_shape`，不会误调用本地几何生成器 `mdb.get_section_shape`。分析结果与视图仍使用 `odb`。
- `bc1ee99`：模型查询改为返回支持 `to_dict()` / `Mapping` 的类型化对象。本项目统一递归转换为普通 JSON 数据，覆盖工具、资源和 API 网关，保留服务端原始字段。MDB 查询按只读权限检查，不再要求修改模型权限，也不会触发模型刷新；`calculate_section_property` 等会改变模型的调用仍要求修改权限。
- `6821413`：模型对象按结构、材料、荷载等领域拆分，`core.model_db` 保留兼容导出；本项目适配层不依赖这些内部类型路径。
- 9 月 7–8 日：新增板厚 `t_out`、求解 `show_view`、12 个分析设置重置接口和 3 个板厚批量管理接口。本项目在现有工具中增加这两个参数，15 个管理接口继续通过 API 网关检索和调用，无需增加重复封装工具。

**构建兼容性：** `2316654` 已恢复 `6821413` 缺失的 `core/data_helper.py`，最新源码可正常导入并通过离线测试。PyPI 上 8 月 20 日发布的 2.8.2 仍不含这些新参数和管理接口。依赖范围 `qtmodel>=2.6.3,<2.9` 和锁文件保持不变；默认调用兼容旧版，显式指定 `t_out` 或 `show_view=True` 时，会先检查真实签名，不支持则在写入或启动求解之前明确报错，不能仅凭版本号判断功能是否可用。

使用支持这些功能的 qtmodel 构建时，MCP 工具调用示例：

```text
add_thickness(name="桥面板", t=0.20, t_out=0.30, thick_type=0)
run_analysis(read_timeout=3600, show_view=True)
list_qtmodel_api(api_object="mdb", pattern="thickness")
call_qtmodel_api(api_object="mdb", method="copy_thicknesses", kwargs={"ids": [1, 2]})
list_qtmodel_api(api_object="mdb", pattern="reset_")
```

`thick_type` 的实际语义是 **0=普通板、1=加劲肋板**，不是面内/面外等厚或不等厚；省略 `t_out` 时面外厚度与 `t` 相同。`show_view` 仅控制桥通的分析进度窗口，不改变后台求解、轮询等待和 MCP 进度心跳。

板厚批量接口仅接受正整数或整数列表，不接受 `"1to3"` 这类区间字符串；`remove_thicknesses([])` 不删除任何板厚。分析重置会删除对应设置，`arrange_thickness_ids` 会修改编号及引用，调用前应检索真实签名并确认修改目标。

不替换已安装包，直接对参考源码运行离线测试（macOS/Linux）：

```bash
PYTHONPATH=reference_codes/qtmodel-release/packages/qtmodel/src:src uv run pytest tests/ --ignore=tests/test_end_to_end.py -q
```

上述开发测试命令排除了 `test_end_to_end.py`；该测试会清空并重建桥通当前模型，只能在可丢弃的模型环境中单独运行。

第一位 `0` 表示 API 仍可能变化，与发布质量无关。升级到新的 qtmodel 次版本线时，同步提高依赖上界并在上表增加一行。

## 许可证

Apache-2.0
