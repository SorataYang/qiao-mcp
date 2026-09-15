# 🌉 Qiao-MCP

<!-- mcp-name: io.github.SorataYang/qiao-mcp -->

**English** · [简体中文](./README.zh-CN.md)

> Full-lifecycle bridge structural analysis — modeling, staging, code checks  
> 桥梁全过程结构分析 MCP 服务器 — 建模、施工阶段、规范验算

Qiao-MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to interact with bridge structural analysis software. It provides tools for creating bridge models, applying loads, running structural analysis, and reviewing results.

## Features

### 🔧 Tools (133 tools, grouped)

Tools are organized by workflow area. Highlights per group:

| Group | Representative tools |
|-------|----------------------|
| **Core modeling** | `create_nodes_linear`, `create_beam_elements_linear`, `create_material`, `create_section` (all parametric section types), `create_polygon_section`, `add_thickness` (optional out-of-plane thickness) |
| **Loads** | `create_load_group`, `create_load_case`, `set_self_weight_stage`, `set_gravity`, `apply_nodal_force`, `apply_beam_distributed_load`, temperature/settlement loads |
| **Boundary** | `set_support`, `add_elastic_link`, `add_master_slave_link`, `add_elastic_support`, `add_beam_constraint` |
| **Groups** | `create_structure_group`, `add_to_structure_group`, `merge_operation_stage` |
| **Stages & analysis** | `add_construction_stage`, `merge_operation_stage`, `configure_analysis`, `run_analysis` (async, progress-reporting, optional `show_view`), `get_analysis_results` |
| **Tendons** | `create_tendon_property`, `create_tendon_2d`, `apply_prestress`, `get_tendon_info` |
| **Traffic (moving load)** | `add_node_tandem`, `add_influence_plane`, `add_traffic_lane`, `add_standard_vehicle`, `create_live_load_case` |
| **Checking** | `setup_concrete_check`, `add_check_load_combination`, `add_parametric_reinforcement`, `run_concrete_check`, `get_check_data` |
| **Queries** | `get_model_info`, `get_model_data` (by kind, incl. qtmodel 2.8 overview kinds `summary` / `analysis_context` / `project_metadata` / `check_context`), `find_entities`, `calc_section_property`, `get_special_results` (paginated where applicable) |
| **Modification** | `initialize_model`, `save_model_file`, `open_model_file`, `update_node`, `move_nodes`, `update_element`, `remove_nodes`, `remove_elements` |
| **Visualization** | `save_model_screenshot`, `plot_analysis_result` (optionally return viewable images), `set_view_angle`, `display_ids` |
| **Workflows** | `create_simple_beam_bridge`, `create_continuous_beam_bridge` |
| **Gateway & diagnostics** | `check_qiaotong_connection`, `get_model_status`, `list_qtmodel_api`, `call_qtmodel_api` — diagnose the bridge connection and model state, or discover and call long-tail qtmodel methods with signature validation |

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

The **Provider pattern** keeps the 133 tools decoupled from any single backend. Select one with
`BRIDGE_PROVIDER`; each provider declares its own software-specific rules, so the LLM adapts
without prompt changes. Currently supports:
- **QTModel** (`qtmodel`, default) — [QiaoTong (桥通)](https://www.brdi.com.cn/Software.html) bridge analysis software ([user manual](https://soratayang.github.io/))

Adding a backend means implementing `BridgeProvider` and registering one line — no tool-layer
changes. See [Backend Selection](./INTEGRATION_GUIDE.md#后端选择-backend-selection).

## Quick Start

### Prerequisites
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- `qtmodel` 2.6.3 – 2.8.x (installed by `uv sync`; 2.8.2 is the current lock)
- QiaoTong software running when calling backend model, analysis, or visualization operations
  (see [Compatibility](#compatibility) for which versions pair with which)

The MCP server can start without QiaoTong. Use `check_qiaotong_connection` to
distinguish a connected server from software that is not running, and
`get_model_status` to see whether a model is open and which operations the
current QiaoTong state allows.

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

Use `http://localhost:45125/pythonForQt/` in the client machine while the tunnel
is running. Windows HTTP.sys validates the `Host` header and rejects
`127.0.0.1` with `400 Invalid Hostname` in this setup.

## Development

```bash
# Install in dev mode (includes ruff, mypy, pytest)
uv sync

# Run directly
uv run python -m qiao_mcp.server

# Quality checks and offline regression tests
uv run ruff check src/ tests/
uv run mypy src/qiao_mcp/
uv run pytest tests/ --ignore=tests/test_end_to_end.py -q
```

The command above runs offline — it does not require the QiaoTong software.
Provider/tool calls are validated against the installed `qtmodel` API signatures
(contract tests) and dispatched against an in-process fake backend.
The excluded end-to-end test requires a disposable QiaoTong model: it clears and
rebuilds the active model before solving.

## Backend: QTModel (桥通)

This MCP server wraps the `qtmodel` Python API which provides access to:
- **mdb** — Model database: querying, building & modifying bridge models
- **odb** — Output database: querying analysis results & visualization
- **cdb** — Check database: structural verification & code checking

## Versioning

Qiao-MCP versions independently from `qtmodel` — the project iterates on its own
(bug fixes, new tools, docs) without waiting for a backend release, and a backend
release does not force a version bump here. The backend requirement is expressed
where it belongs: in the dependency constraint.

### Compatibility

| Qiao-MCP           | qtmodel       | QiaoTong software                          |
|--------------------|---------------|--------------------------------------------|
| 0.3.2             | 2.6.3 – 2.8.x | 2.6.3+; 2.8.x pairs are no longer pinned   |
| 0.3.0 – 0.3.1      | 2.6.3 – 2.6.x | 2.6.3 (exact match enforced by qtmodel)    |
| 0.2.x              | 2.5.0 – 2.5.x | 2.5.0                                      |

How the two sides are matched changed in qtmodel 2.8.2:

- **qtmodel 2.6 / 2.7** perform a strict version handshake — the QiaoTong API
  version and the installed `qtmodel` must match exactly, otherwise
  `check_qiaotong_connection` reports `version_mismatch` and refuses to connect.
- **qtmodel 2.8.2** removed that handshake. Any QiaoTong that exposes the Python
  API connects, so `version_mismatch` no longer occurs. The trade-off is that an
  older QiaoTong may simply lack newer commands; `get_model_status` surfaces that
  as `state_unknown` (the software predates the model-state handshake) so tools
  fail closed instead of writing blind.

Different builds report qtmodel 2.8.2: the PyPI wheel (2026-08-20) does not include
`QtServer.get_model_state`, while the upstream source at the same version does.
Qiao-MCP detects the capability rather than the version — without it the
model-state guard is skipped (`guard_unavailable`) and tools behave as in 0.3.1;
with it, every tool is gated on the state QiaoTong reports.

### Upstream Source Changes (2026-09-04–08)

The reference repository is synced through `2316654`, still labeled `2.8.2`:

- `ac4dbad` moves model queries from `odb` to `mdb`. Qiao-MCP prefers the new
  namespace and falls back to `odb` when the method is absent. Existing-model
  section geometry uses `mdb.get_model_section_shape`; `mdb.get_section_shape`
  remains the local geometry builder. Analysis results and views stay on `odb`.
- `bc1ee99` returns typed model records supporting `to_dict()` and `Mapping`.
  The provider recursively converts them to plain JSON data for tools, resources
  and the API gateway, preserving original server fields. MDB query calls use
  read permission, not model-write permission, and never refresh the model.
  State-changing calls such as `calculate_section_property` still require
  model-write permission.
- `6821413` splits model objects into domain modules and keeps `core.model_db`
  as a compatibility export. The adapter does not depend on those internal paths.
- The September 7–8 updates add `t_out` to thickness definitions, `show_view` to
  solving, twelve analysis-setting reset APIs and three batch thickness APIs.
  Qiao-MCP exposes the two new options on its existing tools; the fifteen
  management APIs are available through the discover-then-call gateway.

**Build compatibility:** `2316654` restores the `core/data_helper.py` missing in
`6821413`, and the latest source passes the offline tests. The PyPI 2.8.2 build
(August 20) still lacks these new options and management APIs. Dependencies and
the lock remain unchanged (`qtmodel>=2.6.3,<2.9`). Default tool calls keep working;
explicit `t_out` or `show_view=True` requests fail before writing or starting a
solve if the installed API does not accept them. A matching version label alone
does not establish feature support.

MCP tool-call examples with a supporting qtmodel build:

```text
add_thickness(name="Deck", t=0.20, t_out=0.30, thick_type=0)
run_analysis(read_timeout=3600, show_view=True)
list_qtmodel_api(api_object="mdb", pattern="thickness")
call_qtmodel_api(api_object="mdb", method="copy_thicknesses", kwargs={"ids": [1, 2]})
list_qtmodel_api(api_object="mdb", pattern="reset_")
```

`thick_type` means **0 = ordinary plate, 1 = ribbed plate**, not equal/unequal
in-plane and out-of-plane thickness. Omitting `t_out` uses `t` for both.
`show_view` controls the QiaoTong progress window only: solving still uses
background execution, polling and MCP progress heartbeats.

Batch thickness APIs accept positive integer IDs or lists, not range strings.
`remove_thicknesses([])` deletes nothing. Analysis resets delete settings, and
`arrange_thickness_ids` changes IDs and references; discover the intended method
and confirm the intended change before calling these write APIs.

To test the reference source without replacing the installed package (macOS/Linux):

```bash
PYTHONPATH=reference_codes/qtmodel-release/packages/qtmodel/src:src uv run pytest tests/ --ignore=tests/test_end_to_end.py -q
```

`0.x` signals the API is still free to change; it is not a statement about
release quality. When moving to a new qtmodel minor line, raise the dependency
bound and add a row to the table above.

## License

Copyright 2026 Sorata (https://github.com/SorataYang)

Licensed under the Apache License, Version 2.0. See [LICENSE](./LICENSE).
Additional attribution notices are available in [NOTICE](./NOTICE).
