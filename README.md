# 🌉 Qiao-MCP

**English** · [简体中文](./README.zh-CN.md)

> MCP server for intelligent bridge structural design and analysis  
> 桥梁智能设计 MCP 服务器

Qiao-MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to interact with bridge structural analysis software. It provides tools for creating bridge models, applying loads, running structural analysis, and reviewing results.

## Features

### 🔧 Tools (126 tools, grouped)

Tools are organized by workflow area. Highlights per group:

| Group | Representative tools |
|-------|----------------------|
| **Core modeling** | `create_nodes_linear`, `create_beam_elements_linear`, `create_material`, `create_section` (all parametric section types), `create_polygon_section` |
| **Loads** | `create_load_group`, `create_load_case`, `set_self_weight_stage`, `set_gravity`, `apply_nodal_force`, `apply_beam_distributed_load`, temperature/settlement loads |
| **Boundary** | `set_support`, `add_elastic_link`, `add_master_slave_link`, `add_elastic_support`, `add_beam_constraint` |
| **Groups** | `create_structure_group`, `add_to_structure_group`, `merge_operation_stage` |
| **Stages & analysis** | `add_construction_stage`, `configure_analysis`, `run_analysis` (async, progress-reporting), `get_analysis_results` |
| **Tendons** | `create_tendon_property`, `create_tendon_2d`, `apply_prestress`, `get_tendon_info` |
| **Traffic (moving load)** | `add_node_tandem`, `add_influence_plane`, `add_traffic_lane`, `add_standard_vehicle`, `create_live_load_case` |
| **Checking** | `setup_concrete_check`, `add_check_load_combination`, `add_parametric_reinforcement`, `run_concrete_check` |
| **Queries** | `get_model_info`, `get_model_data` (by kind), `find_entities`, `calc_section_property`, `get_special_results` — all paginated |
| **Visualization** | `save_model_screenshot`, `plot_analysis_result` (return viewable images), `set_view_angle` |
| **Workflows** | `create_simple_beam_bridge`, `create_continuous_beam_bridge` |
| **Gateway (escape hatch)** | `list_qtmodel_api`, `call_qtmodel_api` — discover & call long-tail qtmodel methods with signature validation |

All tools return structured content (`{status, …}`) and raise typed errors; read-only
and destructive operations carry MCP tool annotations. See the server startup
instructions for the full tool list.

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
qiao-mcp/
├── src/qiao_mcp/
│   ├── server.py              # MCP server entry point
│   ├── tools/                 # MCP Tools (envelope-wrapped)
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
uv run qiao-mcp
```

### Configure in Claude Desktop

Add to your `claude_desktop_config.json`:

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

### Configure in Cursor

Add to `.cursor/mcp.json`:

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

### Configure in Reasonix (UI)

Open **Settings** → **MCP & Tools**, then add a new MCP server:

- **Name**: `qiao-mcp`
- **Transport**: `stdio` (keep default)
- **Command**: `uv --directory /path/to/qiao-mcp run qiao-mcp`
  - Replace `/path/to/qiao-mcp` with your actual project path
  - Windows: use backslashes `D:\path\to\qiao-mcp`
  - macOS/Linux: use forward slashes `/path/to/qiao-mcp`
- **Environment** (optional): `UV_PYTHON=3.11`

Click **Add** to save.

### Configure in Cherry Studio (UI)

Open **设置** → **扩展** → **MCP Servers**, then add a new server:

- **名称 (Name)**: `qiao-mcp`
- **描述 (Description)**: Optional description
- **类型 (Type)**: `标准输入 / 输出 (stdio)`
- **命令 (Command)**: `uv`
- **包管理器 (Package Manager)**: Select `默认` (Default)
- **参数 (Args)**: 
  ```
  /path/to/qiao-mcp
  run
  qiao-mcp
  ```
  (Each line is one argument, no `--directory` prefix needed)
  - Replace `/path/to/qiao-mcp` with your actual project path

Click **保存** to save.

### Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run qiao-mcp
```

## Development

```bash
# Install in dev mode (includes ruff, mypy, pytest)
uv sync

# Run directly
uv run python -m qiao_mcp.server

# Quality gate (same checks as CI)
uv run ruff check src/ tests/
uv run mypy src/qiao_mcp/
uv run pytest tests/ -q
```

The test suite runs fully offline — it does not require the QiaoTong software.
Provider/tool calls are validated against the real `qtmodel` API signatures
(contract tests) and dispatched against an in-process fake backend.

## Backend: QTModel (桥通)

This MCP server wraps the `qtmodel` Python API which provides access to:
- **mdb** — Model database: building & modifying bridge models
- **odb** — Output database: querying analysis results & visualization
- **cdb** — Check database: structural verification & code checking

## Versioning

The version number mirrors the `qtmodel` release it is verified against:

```
0 . 2 . 33
│   │   └── qtmodel minor + patch concatenated (qtmodel 次版本+补丁拼接, 3.3 -> 33)
│   └────── qtmodel major (qtmodel 主版本, 2)
└────────── pre-1.0 (1.0 = stable API)
```

So `0.2.33` corresponds to `qtmodel 2.3.3`; a later `0.2.50` corresponds to
`qtmodel 2.5.0`. Releases track qtmodel one-to-one. The dependency is pinned to the
verified range (`qtmodel>=2.3.3,<2.4`); bump both the version and the bound together
when moving to a new qtmodel release.

> Note: the encoding assumes single-digit qtmodel minor/patch (e.g. `2.3.3` -> `33`).
> qtmodel versions with two-digit segments (e.g. `2.3.10`) would break sort order and
> require a scheme revision before use.

## License

Copyright 2026 Sorata (https://github.com/SorataYang)

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE).
Additional attribution notices are available in [NOTICE](./NOTICE).
