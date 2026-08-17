# 🌉 Qiao-MCP

**English** · [简体中文](./README.zh-CN.md)

> MCP server for intelligent bridge structural design and analysis  
> 桥梁智能设计 MCP 服务器

Qiao-MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to interact with bridge structural analysis software. It provides tools for creating bridge models, applying loads, running structural analysis, and reviewing results.

## Features

### 🔧 Tools (132 tools, grouped)

Tools are organized by workflow area. Highlights per group:

| Group | Representative tools |
|-------|----------------------|
| **Core modeling** | `create_nodes_linear`, `create_beam_elements_linear`, `create_material`, `create_section` (all parametric section types), `create_polygon_section` |
| **Loads** | `create_load_group`, `create_load_case`, `set_self_weight_stage`, `set_gravity`, `apply_nodal_force`, `apply_beam_distributed_load`, temperature/settlement loads |
| **Boundary** | `set_support`, `add_elastic_link`, `add_master_slave_link`, `add_elastic_support`, `add_beam_constraint` |
| **Groups** | `create_structure_group`, `add_to_structure_group`, `merge_operation_stage` |
| **Stages & analysis** | `add_construction_stage`, `merge_operation_stage`, `configure_analysis`, `run_analysis` (async, progress-reporting), `get_analysis_results` |
| **Tendons** | `create_tendon_property`, `create_tendon_2d`, `apply_prestress`, `get_tendon_info` |
| **Traffic (moving load)** | `add_node_tandem`, `add_influence_plane`, `add_traffic_lane`, `add_standard_vehicle`, `create_live_load_case` |
| **Checking** | `setup_concrete_check`, `add_check_load_combination`, `add_parametric_reinforcement`, `run_concrete_check`, `get_check_data` |
| **Queries** | `get_model_info`, `get_model_data` (by kind), `find_entities`, `calc_section_property`, `get_special_results` (paginated where applicable) |
| **Modification** | `initialize_model`, `save_model_file`, `open_model_file`, `update_node`, `move_nodes`, `update_element`, `remove_nodes`, `remove_elements` |
| **Visualization** | `save_model_screenshot`, `plot_analysis_result` (optionally return viewable images), `set_view_angle`, `display_ids` |
| **Workflows** | `create_simple_beam_bridge`, `create_continuous_beam_bridge` |
| **Gateway & diagnostics** | `check_qiaotong_connection`, `list_qtmodel_api`, `call_qtmodel_api` — diagnose the bridge connection or discover and call long-tail qtmodel methods with signature validation |

Tool responses are normalized to structured content (`{status, ...}`), while image
tools can return MCP image content directly. Tool failures use typed MCP errors, and
read-only, destructive, and open-world operations carry MCP tool annotations. The
server instructions include the full tool-group overview; use `list_qtmodel_api`
before calling an uncovered backend method through the gateway.

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
├── tests/                     # Offline unit, integration, and API contract tests
└── reference-docs/            # Review notes and project documentation
```

The **Provider pattern** keeps the 132 tools decoupled from any single backend. Select one with
`BRIDGE_PROVIDER`; each provider declares its own software-specific rules, so the LLM adapts
without prompt changes. Currently supports:
- **QTModel** (`qtmodel`, default) — [QiaoTong (桥通)](https://www.brdi.com.cn/Software.html) bridge analysis software ([user manual](https://soratayang.github.io/))

Adding a backend means implementing `BridgeProvider` and registering one line — no tool-layer
changes. See [Backend Selection](./INTEGRATION_GUIDE.md#后端选择-backend-selection).

## Quick Start

### Prerequisites
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- `qtmodel` 2.6.3 (installed by `uv sync`)
- QiaoTong software 2.6.3 running when calling backend model, analysis, or visualization operations

The MCP server can start without QiaoTong. Use `check_qiaotong_connection` to
distinguish a connected server, a version mismatch, and software that is not running.

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

### LAN debugging proxy

For cross-machine debugging, [`scripts/qiaotong_lan_proxy.py`](./scripts/qiaotong_lan_proxy.py)
forwards a LAN-facing port to the QiaoTong API on the same machine. It uses
`45125` for the proxy and forwards to the selected QiaoTong process on
`127.0.0.1:55125`:

```bash
python scripts/qiaotong_lan_proxy.py
```

Then point the client machine at:

```python
from qtmodel import mdb

mdb.set_url("http://<proxy-machine-LAN-IP>:45125/pythonForQt/")
```

The proxy prints each forwarded request and response. When several QiaoTong
processes are running, keep one process on `55125` for this fixed proxy, or use
separate proxy instances and ports for separate processes.

An SSH tunnel is an alternative that does not expose the API port on the LAN:

```bash
ssh -N -L 45125:127.0.0.1:55125 <user>@<qiaotong-machine-LAN-IP>
```

Use `http://127.0.0.1:45125/pythonForQt/` in the client machine while the tunnel
is running.

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

The test suite is designed to run offline — it does not require the QiaoTong software.
Provider/tool calls are validated against the installed `qtmodel` API signatures
(contract tests) and dispatched against an in-process fake backend.

## Backend: QTModel (桥通)

This MCP server wraps the `qtmodel` Python API which provides access to:
- **mdb** — Model database: building & modifying bridge models
- **odb** — Output database: querying analysis results & visualization
- **cdb** — Check database: structural verification & code checking

## Versioning

Qiao-MCP versions independently from `qtmodel` — the project iterates on its own
(bug fixes, new tools, docs) without waiting for a backend release, and a backend
release does not force a version bump here. The backend requirement is expressed
where it belongs: in the dependency constraint.

### Compatibility

| Qiao-MCP | qtmodel       | QiaoTong software |
|----------|---------------|-------------------|
| 0.3.x    | 2.6.3 – 2.6.x | 2.6.3             |
| 0.2.x    | 2.5.0 – 2.5.x | 2.5.0             |

The QiaoTong software API version and the installed `qtmodel` must match
**exactly** — qtmodel 2.6+ performs a precise version handshake and refuses to
connect otherwise. Run `check_qiaotong_connection` to see both versions and what
to do when they differ.

`0.x` signals the API is still free to change; it is not a statement about
release quality. When moving to a new qtmodel minor line, raise the dependency
bound and add a row to the table above.

## License

Copyright 2026 Sorata (https://github.com/SorataYang)

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE).
Additional attribution notices are available in [NOTICE](./NOTICE).
