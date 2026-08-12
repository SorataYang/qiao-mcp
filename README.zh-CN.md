# 🌉 Qiao-MCP

[English](./README.md) · **简体中文**

> 桥梁智能设计 MCP 服务器  
> MCP server for intelligent bridge structural design and analysis

Qiao-MCP 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务器，让 AI 助手能够与桥梁结构分析软件交互。它提供了创建桥梁模型、施加荷载、运行结构分析和查看结果的工具。

## 功能特性

### 🔧 工具（132 个，按功能分组）

工具按桥梁建模与分析工作流分组。以下是各组代表工具：

| 分组 | 代表工具 |
|------|----------|
| **核心建模** | `create_nodes_linear`、`create_beam_elements_linear`、`create_material`、`create_section`（支持参数化截面）、`create_polygon_section` |
| **荷载** | `create_load_group`、`create_load_case`、`set_self_weight_stage`、`set_gravity`、`apply_nodal_force`、`apply_beam_distributed_load`、温度/沉降荷载 |
| **边界条件** | `set_support`、`add_elastic_link`、`add_master_slave_link`、`add_elastic_support`、`add_beam_constraint` |
| **分组与阶段** | `create_structure_group`、`add_elements_to_group`、`merge_operation_stage`、`add_construction_stage` |
| **分析** | `configure_analysis`、`run_analysis`（异步并报告进度）、`get_analysis_results` |
| **预应力钢束** | `create_tendon_property`、`create_tendon_2d`、`apply_prestress`、`get_tendon_info` |
| **移动荷载** | `add_node_tandem`、`add_influence_plane`、`add_traffic_lane`、`add_standard_vehicle`、`create_live_load_case` |
| **结构验算** | `setup_concrete_check`、`add_check_load_combination`、`add_parametric_reinforcement`、`run_concrete_check`、`get_check_data` |
| **查询** | `get_model_info`、`get_model_data`、`find_entities`、`calc_section_property`、`get_special_results`（适用时支持分页） |
| **模型修改** | `initialize_model`、`save_model_file`、`open_model_file`、`update_node`、`move_nodes`、`update_element`、`remove_nodes`、`remove_elements` |
| **可视化** | `save_model_screenshot`、`plot_analysis_result`（可直接返回图像）、`set_view_angle`、`display_ids` |
| **工作流** | `create_simple_beam_bridge`、`create_continuous_beam_bridge` |
| **网关与诊断** | `check_qiaotong_connection`、`list_qtmodel_api`、`call_qtmodel_api`（连接诊断、长尾 API 检索与签名校验调用） |

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

**Provider 模式**支持未来接入多种桥梁分析软件后端。当前支持：
- **QTModel** — [桥通 (QiaoTong)](https://www.qt-model.com/) 桥梁分析软件

## 快速开始

### 前置要求
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- `qtmodel` 2.6.3（`uv sync` 会自动安装）
- 调用建模、分析或可视化工具时，需要运行兼容的桥通软件 2.6.3

桥通未启动时 MCP 服务器仍可启动。调用 `check_qiaotong_connection` 可以区分已连接、版本不匹配和软件未启动三种状态。

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

隧道运行期间，客户端使用 `http://127.0.0.1:45125/pythonForQt/`。

## 开发

```bash
# 开发模式安装
uv sync

# 直接运行
uv run python -m qiao_mcp.server

# 质量检查
uv run ruff check src/ tests/
uv run mypy src/qiao_mcp/
uv run pytest tests/ -q
```

测试设计为离线运行，不要求桥通软件。Provider/tool 调用会根据已安装的 `qtmodel` 真实 API 签名进行契约校验，并通过进程内 fake backend 验证分发逻辑。

## 后端软件：QTModel（桥通）

本 MCP 服务器封装了 `qtmodel` Python API，提供以下功能：
- **mdb** — 模型数据库：构建和修改桥梁模型
- **odb** — 输出数据库：查询分析结果和可视化
- **cdb** — 验算数据库：结构验算和规范检查

当前项目版本为 `0.2.63`，对应已验证的 `qtmodel 2.6.3`。依赖约束为 `qtmodel>=2.6.3,<2.7`；桥通软件与客户端 API 版本需要匹配。

## 许可证

Apache-2.0
