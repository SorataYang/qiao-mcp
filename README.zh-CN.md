# 🌉 Bridge-MCP

[English](./README.md) · **简体中文**

> 桥梁智能设计 MCP 服务器  
> MCP server for intelligent bridge structural design and analysis

Bridge-MCP 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务器，让 AI 助手能够与桥梁结构分析软件交互。它提供了创建桥梁模型、施加荷载、运行结构分析和查看结果的工具。

## 功能特性

### 🔧 工具 (12个)
| 工具 | 描述 |
|------|-------------|
| `get_model_info` | 获取桥梁模型概要 |
| `create_nodes` | 创建节点 |
| `create_elements` | 创建梁/桁架/索/板单元 |
| `create_material` | 创建材料 — 混凝土、钢材等 |
| `create_section` | 创建截面 |
| `set_support` | 设置边界条件 |
| `apply_nodal_force` | 施加节点荷载 |
| `apply_beam_distributed_load` | 施加分布荷载 |
| `add_construction_stage` | 定义施工阶段 |
| `configure_analysis` | 设置分析参数 |
| `validate_model` | 检查模型问题 |
| `get_analysis_results` | 获取分析结果 |

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
├── src/bridge_mcp/
│   ├── server.py              # MCP 服务器入口
│   ├── config.py              # 配置管理
│   ├── tools/                 # MCP 工具
│   ├── resources/             # MCP 资源
│   ├── prompts/               # MCP 提示词
│   └── providers/             # 后端适配器
│       ├── __init__.py        # BridgeProvider 抽象基类
│       └── qtmodel_provider.py  # 桥通软件适配器
└── reference-docs/            # API 和软件文档
```

**Provider 模式**支持未来接入多种桥梁分析软件后端。当前支持：
- **QTModel** — [桥通 (QiaoTong)](https://www.qt-model.com/) 桥梁分析软件

## 快速开始

### 前置要求
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- 桥通软件已运行（可选 — 如果软件未运行，工具会返回错误信息）

### 安装与运行

```bash
# 安装依赖
uv sync

# 运行服务器
uv run bridge-mcp
```

### 在 Claude Desktop 中配置

编辑 `claude_desktop_config.json` 文件：

```json
{
  "mcpServers": {
    "bridge-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/qiao-mcp", "run", "bridge-mcp"]
    }
  }
}
```

### 在 Cursor 中配置

创建 `.cursor/mcp.json` 文件：

```json
{
  "mcpServers": {
    "bridge-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/qiao-mcp", "run", "bridge-mcp"]
    }
  }
}
```

### 在 Reasonix 中配置（UI 界面）

打开 **Settings** → **MCP & Tools**，然后添加新的 MCP 服务器：

- **Name**: `bridge-mcp`
- **Transport**: `stdio`（保持默认）
- **Command**: `uv --directory /path/to/qiao-mcp run bridge-mcp`
  - 将 `/path/to/qiao-mcp` 替换为你的实际项目路径
  - Windows: 使用反斜杠 `D:\path\to\qiao-mcp`
  - macOS/Linux: 使用正斜杠 `/path/to/qiao-mcp`
- **Environment**（可选）: `UV_PYTHON=3.11`

点击 **Add** 保存。

### 在 Cherry Studio 中配置（UI 界面）

打开 **设置** → **扩展** → **MCP Servers**，然后添加新服务器：

- **名称**: `bridge-mcp`
- **描述**: 可选描述
- **类型**: `标准输入 / 输出 (stdio)`
- **命令**: `uv`
- **包管理器**: 选择 `默认`
- **参数**: 
  ```
  /path/to/qiao-mcp
  run
  bridge-mcp
  ```
  （每行一个参数，无需 `--directory` 前缀）
  - 将 `/path/to/qiao-mcp` 替换为你的实际项目路径

点击 **保存**。

### 使用 MCP Inspector 测试

```bash
npx @modelcontextprotocol/inspector uv run bridge-mcp
```

## 开发

```bash
# 开发模式安装
uv sync

# 直接运行
uv run python -m bridge_mcp.server
```

## 后端软件：QTModel（桥通）

本 MCP 服务器封装了 `qtmodel` Python API，提供以下功能：
- **mdb** — 模型数据库：构建和修改桥梁模型
- **odb** — 输出数据库：查询分析结果和可视化
- **cdb** — 验算数据库：结构验算和规范检查

## 许可证

Apache-2.0
