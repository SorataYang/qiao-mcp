# 🌉 Qiao-MCP

<!-- mcp-name: io.github.SorataYang/qiao-mcp -->

**English** · [简体中文](./README.zh-CN.md)

> Full-lifecycle bridge structural analysis — modeling, staging, code checks  
> 桥梁全过程结构分析 MCP 服务器 — 建模、施工阶段、规范验算

Qiao-MCP is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI assistants to interact with bridge structural analysis software. It provides tools for creating bridge models, applying loads, running structural analysis, and reviewing results.

## Features

### 🔧 Tools (15 domain entry points, 153 operations)

The local development version exposes 15 domain tools. Each takes a `request`
with an `operation` selector and the matching fields; its schema includes every
operation's full parameter descriptions, defaults and constraints. All 153 legacy
names remain directly callable with their original arguments.

| Domain tool | Scope |
| --- | --- |
| `inspect_bridge` | Connection, model state and edit readiness |
| `manage_model_files` | Open, save and initialize a project |
| `query_model` | Definitions, entity searches and geometry checks |
| `edit_geometry` | Nodes, elements and bridge layouts |
| `edit_properties` | Materials, sections, thickness and time effects |
| `edit_boundaries` | Ground supports, node links and beam-end releases |
| `edit_construction` | Groups, stages, activation and deactivation |
| `edit_loads` | Static cases, combinations and physical loads |
| `analyze_model` | Solver settings, dynamics and structural analysis |
| `edit_prestress` | Tendon properties, geometry and prestress |
| `edit_traffic` | Moving, transversal and international live loads |
| `manage_checks` | Model checking snapshots and current code-check context |
| `query_results` | Structural, modal, live-load and tendon results |
| `view_model` | Display settings, stage views, screenshots and plots |
| `access_backend` | Native method discovery and long-tail API calls |

For example, send `{"request":{"operation":"get_model_status"}}` to
`inspect_bridge`. See [request examples and compatibility](docs/tool-catalog.md).
Set `QIAO_MCP_CATALOG_LAYOUT=flat` to list the original 153 names instead.
Published 0.5.1 continues to use that flat catalog.

The 151 non-image operations retain their output schemas and MCP structured content
(`{status, message, ...}`). Connection diagnostics also expose `connection_status`
and `connected`; bridge templates return the resolved node, element and property IDs.
`get_model_status` preserves QiaoTong's state in `status`. The two image-capable tools
return viewable MCP image content or a text summary. At domain level, 14 entry points
publish combined output schemas; `view_model` supports mixed image/text content.
Tool failures use typed MCP errors, and
read-only, destructive, and open-world operations carry MCP tool annotations. The
server instructions include the full tool-group overview; use `list_qtmodel_api`
before calling an uncovered backend method through the gateway.

Input schemas include parameter descriptions, closed-set selectors, pagination bounds
and fixed-size coordinate/DOF arrays. Invalid schema inputs are rejected before a
backend call. A beam end `release_i` / `release_j` flag means **True = release**;
omitting an end keeps all six DOFs connected. Load combination components use
`[case_type, case_name, factor]`, with `combine_type=3` for an envelope.

Support overrides preserve omitted coordinate/additional settings. Supplying
`extra_parameters` enables them unless `extra_enabled=False` explicitly clears
them; this behavior also applies to older SDKs that support these options.

### 0.5.6: tool optimizations (local version)

The current development version retains all 153 operations and legacy calls behind 15
domain entry points. These changes are not in published 0.5.1. Section
creation/deletion, stage deletion and vertical prestress checking now explain their
prerequisites, selection boundaries and write behavior. `add_custom_temperature` accepts
native `[reference, height, temperature]` rows (reference 1=top, 2=bottom; orientation
1=local Z, 2=local Y). Two-value rows are rejected because they omit the reference.
Mutation selections reject blank, Boolean and fractional IDs; renumbering requires BOTH
complete lists, or BOTH omitted to intentionally renumber the whole model.

Screenshots and plots now retrieve PNG bytes for storage on the MCP host. Partial
updates require unique, complete readback; checking queries preserve typed fields.
Live-load results expose `envelope_type=1` (maximum) or `2` (minimum). Inspect the
audit for solver, section-numbering, group-query and idealized support corrections.

### 0.5.1: tool guidance and compatibility

Published 0.5.1 keeps all 153 tools. Complete Args text is published in parameter
schemas without repeating it in tool descriptions. It introduced clearer
selection guidance; the unreleased audit above corrects remaining behavior.

Choose absolute node edits with `update_node`, offsets with `move_nodes`, and
numbering with `update_node_id`/`renumber_nodes`. For sections,
`calc_section_property` evaluates supplied geometry, `get_model_data` reads stored
properties, and `calculate_section_property` rewrites all existing sections.
Tendon definitions, computed losses and coordinates have separate query tools.
Automatic self-weight is controlled by stages, not by creating a case named 自重.

### 0.5.0: queries, transversal analysis, check snapshots and international loads

This version implements B1–B4 with 20 new tools and one workflow prompt. It includes all
changes since 0.3.3, including work previously labeled 0.4.0. See
[upgrading from 0.3.3](#upgrading-from-033). New commands require a supporting QiaoTong
build. Live testing confirmed basic statics and partial B1 coverage; see the
[known backend limitations](#live-tested-backend-limitations).

`get_model_edit_readiness` is read-only and remains accessible when model operations are blocked. Its `success`
status means a response was received, not that editing is safe; inspect the raw
`readiness` object. No token is retained/reused, and no stages/results are changed.

`query_model_data` takes a typed `request`, for example:

```json
{"request": {"kind": "nodes", "structure_group_names": ["MainGirder"], "limit": 20, "offset": 0}}
```

Kinds: `nodes`, `elements`, `boundaries`, `loads`, `node_local_axes`,
`section_summaries`. Names are lists; IDs are positive integers/lists, not range
strings. Nodes need at least one filter; `near` and `tolerance` must be paired.
Qiao-MCP caps filter lists/pages at 500; section summaries allow only 100 explicit
IDs and 100 items per page. The structured `data` field preserves native page
metadata without recomputing totals or slicing again. Unsupported endpoints fail
explicitly rather than downloading everything for local filtering.

`get_model_data` additionally supports `material_summaries`, `material_detail`,
`load_case_summaries`, `load_case_detail`, `load_combination_summaries`,
`load_combination_detail`, `construction_stage_summaries`, `element_section` and
`spans`. New details use one positive integer (or one-item integer list) in `ids`;
`element_section` uses `position=0|1`. Load-case/combination detail pagination runs
on the server; other list kinds retain their existing text pagination. Summaries
are not full write-back snapshots, and construction stage IDs follow stage order.

`configure_live_load_system` explicitly selects one of the five live-load systems; clearing old definitions defaults to off. `configure_operation_stage` requires all four case lists; `[]` disables that family. These tools commit settings without running analysis.

Transversal definitions use `set_transversal_vehicle` / `set_transversal_lane`
with a complete typed `request` and `action="add"|"update"`. Both may replace
existing definitions. Select `china_transversal` first. Loads use kN and lengths
use m regardless of display units. Lane nodes remain in input order and must be
directly joined by beam elements; `distribution_widths` are meters. Use the
returned `data.index` or `get_transversal_data` for references. Readback retains
the native lane field `load_factors`; map it to `distribution_widths` when editing.

`set_transversal_case` validates the referenced vehicle/lane IDs and accepts
positive `reduction_factors` for 1..N lanes plus `greater_lane_factor` for more
than N. `remove_transversal_data` requires an explicit target; vehicle/lane
deletion defaults to `cascade=False`. Case deletion does not accept cascade.
Combination and operation-stage references must be removed explicitly first.

Base-model reinforcement uses `set_section_reinforcement` with a complete
UI-exported snapshot, or `remove_section_reinforcement` with an explicit full
section identifier (`1`, `1-I`, `1-J`, `G7-2`). Every snapshot field is required;
empty arrays clear that part. Six-entry outer/inner rows and model length units
differ from the legacy parametric tool. Current CSAN queries are not lossless
model snapshots. The new tools require model-write permission and commit once.

`set_check_stirrup_snapshot` preserves the full exported definition and accepts
`original_id` for renumbering. `set_element_stirrups` replaces complete shear
(five entries) and torsion (three entries) assignments independently: `null`
keeps a family, `[]` clears it, and stirrup ID `0` means unassigned. These are
separate from the legacy current-CSAN stirrup tools.

`manage_check_material` sets a full exported override or resets an explicit ID
to its base material. `manage_check_case_definition` sets/removes concrete,
seismic and strengthening model definitions with native enum values. The existing
`run_concrete_check` imports the named concrete case after these commits; it does
not run seismic or strengthening checks. Preserve the complete exported material
properties/parameters and stored units instead of constructing partial snapshots.
Reported failed, canceled or other non-success completion states are tool errors,
including on older SDKs whose waiters return them without raising.

International vehicles use `set_international_vehicle` with a `request`
discriminated by `standard="AASHTO"|"BS"|"EN1991"`. Select the matching model
system first. `parameters` and `load_items` must be explicit, even for `{}`/`[]`.
Both add and update replace the definition; omitted/null scalars use new-definition
defaults. Update locates the original name and retains its actual ID/references.
Writes commit once and return a definition read back by exact name.

| Standard | Native units and conventions |
|----------|------------------------------|
| AASHTO | Axles `[N, m]`, `w` N/m, lengths m, `r` percent (`90` = 90%) |
| BS | `pa`/`pb` kN, `w3` kN/m, lengths m; `w1`/`w2` formula coefficients and dimensionless exponents |
| EN1991 | Axles `[kN, m]`, uniform loads kN/m, point load kN, lengths m; loaded lengths and spacings are distinct |

The SDK does not specify the BS axle-force unit. Use verified native BS axle
export/query values unchanged; do not infer their unit from another standard.
`get_international_live_load_data(kind="vehicles"|"cases")` retains complete
native fields; selection and pagination run locally over its native whole-list
response. Vehicle exports may contain inactive parameters for other standards:
select the documented fields for the typed tool, or use the existing gateway to
replay an unchanged full native definition. No global unit conversion is applied.

`create_en1991_vehicle` selects a native `source="standard"|"user"` factory with
an explicit name. Standard vehicles expose effective factory controls only; their
code-generated uniform loads/lengths/spacings cannot be overridden. User vehicles
retain those fields plus `p`/`dis`, `load_length`, `num` and `point_load`; LM71 uses
four 250 kN axles when both `p`/`dis` are null. Factory writes also read back the
actual vehicle ID. For example, after selecting `en1991`:

```json
{"request": {"source": "standard", "name": "LM71", "load_type": "LM71"}}
```

`set_planned_lane` requires the plane, reference tandem, width, vehicle count,
signed offset and direction. It uses its own endpoint, distinct from
`add_traffic_lane(optimize=True)`. There is no independent planned-lane getter;
its response confirms the commit, and model export/UI inspection verifies the
definition. Gateway deletion must pass `lane_kind="planned"` to `remove_lane_line`.

`set_international_live_load_case` checks each vehicle's exact name and expected
`standard` before writing. Subcases select ordinary/planned lanes with
`optimized=False|True`; EN1991 rejects duplicate lane assignments. QiaoTong checks
lane existence, lane kind and influence-plane membership. Factor objects use
complete native field names and values; null means server defaults, including
on update. Configure `live_load_cases` explicitly with `configure_operation_stage`,
then use `run_analysis` and `get_analysis_results(case_name_mode="full")` with a
result identifier verified from QiaoTong. Definitions never start analysis.
Vehicle/case deletion remains available through `remove_international_vehicle`
and `remove_live_load_case` in the existing gateway.

0.5.0 also tracks upstream `0687ffe` through the existing gateway for mass/stiffness
factors, flange/effective-width definitions, statistics and structure merges. Model
weight queries use fixed N, independent of display units.

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

### 💬 Prompts (5 workflows)
| Prompt | Description |
|--------|-------------|
| `design_simple_beam` | Simple beam bridge design workflow (简支梁设计) |
| `design_continuous_beam` | Continuous beam bridge design (连续梁设计) |
| `check_structure` | Structural code checking (结构检算) |
| `construction_stage_analysis` | Construction stage analysis (施工阶段分析) |
| `analyze_transversal` | Explicit transversal definitions, configuration, solve and verified result identifiers |

For ordinary static cases, `get_analysis_results` keeps its automatic `ST:`
prefix. Use `case_name_mode="full"` with a complete identifier verified from
QiaoTong results/UI for other result families. It is passed unchanged; TV/MV
combination codes are not evidence of a result endpoint's naming convention.

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

The **Provider pattern** keeps the 153 operations decoupled from any single backend. Select one with
`BRIDGE_PROVIDER`; each provider declares its own software-specific rules, so the LLM adapts
without prompt changes. Currently supports:
- **QTModel** (`qtmodel`, default) — [QiaoTong (桥通)](https://www.brdi.com.cn/Software.html) bridge analysis software ([user manual](https://soratayang.github.io/))

Adding a backend means implementing `BridgeProvider` and registering one line — no tool-layer
changes. See [Backend Selection](./INTEGRATION_GUIDE.md#后端选择-backend-selection).

## Quick Start

### Prerequisites
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- `qtmodel` 2.6.3 – 2.9.x, except 2.9.0 (installed by `uv sync`; 2.9.2 is the current lock)
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
| 0.5.6 (local)      | 2.6.3 – 2.9.x, not 2.9.0 | Same backend requirements; 15 domain tools with all 153 legacy operations |
| 0.5.1              | 2.6.3 – 2.9.x, not 2.9.0 | With 2.9.x, QiaoTong must report model state; new commands require server support |
| 0.5.0              | 2.6.3 – 2.9.x, not 2.9.0 | With 2.9.x, QiaoTong must report model state; new commands require server support |
| 0.3.2 – 0.3.3     | 2.6.3 – 2.8.x | 2.6.3+; 2.8.x pairs are no longer pinned   |
| 0.3.0 – 0.3.1      | 2.6.3 – 2.6.x | 2.6.3 (exact match enforced by qtmodel)    |
| 0.2.x              | 2.5.0 – 2.5.x | 2.5.0                                      |

Known lower-bound limitation: qtmodel 2.6.3 lacks `get_load_group_names`, so the
one-shot bridge workflow tools cannot run on that version. This is an existing
limitation; use 2.6.4 or later for those workflows (2.9.0 remains excluded). The
dependency range does not guarantee every new tool on every build: missing methods or
incompatible parameters fail explicitly before writes. Capability differences were
checked on PyPI 2.6.3, 2.6.4, 2.8.2, 2.9.1, 2.9.2 and 2.9.3, plus reference `0687ffe`.
These tests verify software contracts; complete engineering acceptance remains pending.
qtmodel 2.9.3 explicitly rejects historical check-snapshot and planned-lane add/update
routes with `API_NOT_OPEN`; a method appearing in the SDK catalog does not prove that
its desktop route exists.

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
with it, every tool is gated on the state QiaoTong reports. qtmodel 2.9.0 is the
first PyPI release that includes it, so on 2.9.x the guard is always active.

### Live-tested backend limitations

Live testing on 2026-10-12 used QiaoTong **26.1.116.1010** with qtmodel **2.9.2**.
An isolated cantilever model passed reaction, bending-moment and translation checks;
tip displacement differed from the shear-inclusive hand calculation by about 0.00125%.
The same run confirmed these backend limitations:

- `GET-DEFORMATION` returns an incorrect `rz`, equal to `ry` in the tested cases.
  The solver database contains the correct Rz. Do not rely on the API Rz from
  this build; Qiao-MCP does not invent a replacement value.
- `configure_live_load_system` is rejected with `未知参数：clear_existing`.
  The transversal workflow stops at system selection. International workflows
  share that prerequisite and were not run; individual international interfaces
  were not established as unsupported by this test.
- `SET-SECTION-REINFORCEMENT`, `SET-CHECK-STIRRUP` and `SET-CHECK-CASE` are rejected
  as unknown commands. Full reinforcement/check-snapshot acceptance remains open.

`connected` or `compatible` does not certify these features. Use a supporting QiaoTong
build. BS axle-force units also remain unconfirmed upstream.

### Upgrading from 0.3.3

0.5.0 includes an incompatible correction to `add_nodal_mass`:

- Use `mass` for equal translational mass along X, Y and Z, for example
  `{"node_id": 1, "mass": 10}`. Optional `mass_x`/`mass_y`/`mass_z` override
  individual directions; omitted directions use `mass`, whose default is zero.
- `mass_rm` is removed. Specify the intended rotational inertia axis with
  `rot_x`, `rot_y` or `rot_z`; do not mechanically rename the old parameter.
- Unequal directional masses require an SDK with `mass_xyz` support (the supported
  PyPI 2.9 builds are 2.9.1 and 2.9.2). Older builds reject them before writing.

Earlier versions put some translational mass arguments into rotational fields.
Upgrading the package does not repair existing models: read back previously
written nodal masses and check them against the intended engineering values.
Also review the [changelog](CHANGELOG.md) for stricter creep/material validation,
fractional stage durations and the model-state requirements above.

### Upstream qtmodel 2.9 alignment

The current reference is `0687ffe`, labeled 2.9.2 but different from the PyPI 2.9.2
wheel. The earlier local baseline was `8ae651e`, whose package matched that wheel apart
from its older version label.

- **Write safety.** A write whose reply is lost raises `CommandOutcomeUnknownError`
  and is no longer resent. Qiao-MCP reports it as an unknown outcome and tells the
  client to read the model back before doing anything else.
- **Client-side validation.** Many writes now reject malformed values before sending
  them. Qiao-MCP's schemas match: nonempty creep/shrink curves, 26- or 29-value
  section property tables, per-code creep parameter counts and `data_info` for
  custom materials.
- **Nodal mass layout.** `add_nodal_mass` documents `mass_info` as
  `(mass, inertia X, Y, Z)` and adds `mass_xyz` for direction-specific masses.
  Qiao-MCP now sends that layout (see the changelog for the corrected fields).
- **Existing tools expose new parameters.** Construction stages support fractional
  durations and `sub_steps`; `create_material` adds `is_orthotropic` / `ey`;
  `set_support` and `add_elastic_support` add `coordinate`, `extra_enabled` and
  eight-value `extra_parameters`. Unidirectional elastic supports also accept
  signed `axis_direction`. `add_influence_plane` adds `always_divided_by_beam_shape`,
  and `create_live_load_case` adds the per-sub-case boolean list `sub_case_optimized`.
  Omitted options keep legacy behavior; explicit options are checked against the
  installed signature before writing. Fractional stage creation is rejected on
  builds that would truncate it. These additions are included in 0.5.0;
  its catalog has 153 tools.
- **Operation settings and cascade deletion.** `configure_operation_stage`
  exposes all four case lists, including transversal cases. The gateway method
  `update_operation_stage_setting` remains available; supply all intended case
  lists because omitted/empty lists disable their analysis.
  `remove_material` defaults to `cascade=True` (also deletes associated tendon
  properties and tendons). `remove_tendon_property` defaults to `False`; `True`
  deletes referencing tendons and their loads without a dialog. Confirm the
  deletion scope first; omitting both name and index targets all objects.
- **Dedicated tools and long-tail APIs.** 0.5.0 adds dedicated transversal,
  international/planned-lane, reinforcement/check-snapshot and edit-readiness
  tools. Exact object deletion (`delete_model_object`), factors, effective widths,
  statistics and structure merges remain available through the gateway. Every
  MDB write and the explicit CDB model-snapshot methods commit with `update_model`.
- **Blocked in the gateway.** `post_python_file` (reads a local file and posts it
  to any URL for execution), `prepare_model_edit` (can irreversibly delete results;
  for the host application after user approval), `export_api_help` (writes SDK help
  to any local path), and the pre-existing `ensure_running`, `set_url`,
  `set_version`, `export_qt_helper` and `wait_solve` (polls without a time limit;
  use `run_analysis`).

### Upstream Source Changes (2026-09-04–08)

These changes, first synced at `2316654` while still labeled `2.8.2`, are part of 2.9.0:

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

**Build compatibility:** these options and management APIs ship in the PyPI 2.9.x
releases; the PyPI 2.8.2 build (August 20) lacks them. Default tool calls keep
working on either; explicit `t_out` or `show_view=True` requests fail before
writing or starting a solve if the installed API does not accept them. A matching
version label alone does not establish feature support.

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
