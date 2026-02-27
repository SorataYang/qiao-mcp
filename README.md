# 🌉 Bridge-MCP

> MCP server for intelligent bridge structural design and analysis  
> 桥梁智能设计 MCP 服务器

Bridge-MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to interact with bridge structural analysis software. It provides tools for creating bridge models, applying loads, running structural analysis, and reviewing results.

## Features

### 🔧 Tools (12 tools)
| Tool | Description |
|------|-------------|
| `get_model_info` | Get bridge model summary (获取模型概要) |
| `create_nodes` | Create nodes (创建节点) |
| `create_elements` | Create beam/truss/cable/plate elements (创建单元) |
| `create_material` | Create materials — concrete, steel, etc. (创建材料) |
| `create_section` | Create cross-sections (创建截面) |
| `set_support` | Set boundary conditions (设置支承) |
| `apply_nodal_force` | Apply forces at nodes (施加节点荷载) |
| `apply_beam_distributed_load` | Apply distributed loads on beams (施加分布荷载) |
| `add_construction_stage` | Define construction stages (添加施工阶段) |
| `configure_analysis` | Set up analysis parameters (配置分析) |
| `validate_model` | Check model for issues (验证模型) |
| `get_analysis_results` | Retrieve results (获取分析结果) |

### 📦 Resources (7 resources)
| URI | Description |
|-----|-------------|
| `bridge://model/summary` | Model overview |
| `bridge://model/materials` | Material list |
| `bridge://model/sections` | Section list |
| `bridge://model/load-cases` | Load cases |
| `bridge://model/stages` | Construction stages |
| `bridge://model/structure-groups` | Structure groups |
| `bridge://model/boundaries` | Boundary conditions |

### 💬 Prompts (4 workflows)
| Prompt | Description |
|--------|-------------|
| `design-simple-beam` | Simple beam bridge design workflow (简支梁设计) |
| `design-continuous-beam` | Continuous beam bridge design (连续梁设计) |
| `check-structure` | Structural code checking (结构检算) |
| `construction-stage-analysis` | Construction stage analysis (施工阶段分析) |

## Architecture

```
bridge-mcp/
├── src/bridge_mcp/
│   ├── server.py              # MCP server entry point
│   ├── config.py              # Configuration
│   ├── tools/                 # MCP Tools
│   ├── resources/             # MCP Resources
│   ├── prompts/               # MCP Prompts
│   └── providers/             # Backend adapters
│       ├── __init__.py        # BridgeProvider abstract base
│       └── qtmodel_provider.py  # QiaoTong adapter
└── reference-docs/            # API & software documentation
```

The **Provider pattern** allows future support for multiple bridge analysis backends. Currently supports:
- **QTModel** — [桥通 (QiaoTong)](https://www.qt-model.com/) bridge analysis software

## Quick Start

### Prerequisites
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- QiaoTong software running (optional — tools return error messages if unavailable)

### Install & Run

```bash
# Install dependencies
uv sync

# Run the server
uv run bridge-mcp
```

### Configure in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bridge-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/bridge-mcp", "run", "bridge-mcp"]
    }
  }
}
```

### Configure in Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bridge-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/bridge-mcp", "run", "bridge-mcp"]
    }
  }
}
```

### Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run bridge-mcp
```

## Development

```bash
# Install in dev mode
uv sync

# Run directly
uv run python -m bridge_mcp.server
```

## Backend: QTModel (桥通)

This MCP server wraps the `qtmodel` Python API which provides access to:
- **mdb** — Model database: building & modifying bridge models
- **odb** — Output database: querying analysis results & visualization
- **cdb** — Check database: structural verification & code checking

## License

Apache-2.0
