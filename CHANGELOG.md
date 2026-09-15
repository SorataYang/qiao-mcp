# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.3] - 2026-09-15

### Added

- **Real structured MCP outputs.** All 131 non-image tools publish output schemas.
  Explicit response models cover connection diagnostics, model state and bridge
  workflows; text tools retain the compatible `status`/`message` envelope. Images
  remain MCP image content. The SDK no longer silently treats bare `dict` annotations
  as unstructured output.
- **Executable input constraints.** The catalog exposes 59 parameters containing
  closed-set selectors and 32 parameters containing fixed-size or nonempty arrays,
  pagination ranges, positive workflow dimensions, and fixed-size DOF/coordinate
  rows. Node coordinates retain both `[x,y,z]` and `[id,x,y,z]` formats; tendon
  inputs retain straight and track positioning, and boundary removal accepts both
  English tokens and native Chinese names. Malformed schema inputs fail before
  connection/state probes or backend dispatch. Extensible design-code
  indices, backend-owned payloads and stage-number conventions remain documented
  rather than being constrained to a guessed list.
- **Protocol regression gates.** CI checks the built wheel's initialization,
  instructions, complete parameter descriptions, output schemas, a real structured
  response and MCP error handling without QiaoTong. The offline catalog uses the
  same registration function as the server.
- **Catalog startup is independent of bridge discovery.** Initializing the MCP
  server and listing tools do not probe QiaoTong. Diagnostics and guarded operations
  perform the connectivity checks when needed, so inspection does not wait on a
  desktop session or a scan of candidate HTTP ports.

### Fixed

- **Load combinations use `[case_type, case_name, factor]`.** Correct the previously
  reversed documentation and reject reversed/malformed rows before writing. The
  envelope rule is `combine_type=3`; `2` is discriminant combination. Document MDB
  versus CDB combinations and the backend's overwrite behavior.
- **Polygon sections use the native custom-loop section type and list container.**
  Validate finite 2D points, distinct vertices and nonzero signed area; close rings
  without modifying caller-owned data and wrap the outline/holes in the SDK's list.
  The payload is checked with qtmodel's actual local geometry builder.
- **Beam-end release flags match their documented meaning.** MCP `True=released`
  is converted to native qtmodel `False=free`; omitted ends are fully connected.
  Previously flags were forwarded with the opposite meaning and omitted ends used
  the SDK's all-free defaults. Tests inspect the actual SDK request payload.
- **Prestress and file-operation guidance.** Document dependencies, retry behavior,
  recovery queries, model-host file paths and `.bfmd` as the SDK-documented format.
  Empty tendon selections and zero-node creation no longer report success.
- **Additional parameter guidance.** Clarify native cable initialization modes,
  concrete/composite section-temperature categories and track-positioned tendon
  insertion triples, rather than describing them as strain, section shapes or XYZ
  coordinates in every mode.
- **Accurate operation annotations.** Connection diagnostics are read-only; generic
  API calls, combination replacement, deletion-capable check tools and file saves disclose destructive
  potential. Model state keeps the backend's status rather than forcing success.

## [0.3.2] - 2026-09-14

### Added

- **Parameter descriptions in MCP input schemas.** The registration wrapper
  copies Google-style docstring argument descriptions into the actual JSON Schema,
  including multiline descriptions while keeping injected Context out of inputs.
- **Optional `t_out` on `add_thickness` and `show_view` on `run_analysis`.**
  Separate in-plane/out-of-plane thickness and the QiaoTong solver progress
  window are exposed without changing existing defaults. Real API signatures
  are checked before opt-in calls, so unsupported builds fail before any write
  or solve rather than silently ignoring the option. The window does not alter
  background execution, polling or the total solve budget.
- **Offline coverage and usage guidance for fifteen new MDB management APIs:**
  twelve analysis-setting resets plus `copy_thicknesses`,
  `arrange_thickness_ids` and `remove_thicknesses`, using the existing gateway.
- **`get_model_status` tool and a model-state guard on every tool.** qtmodel 2.8
  exposes `QtServer.get_model_state()`, a snapshot QiaoTong owns: whether a model
  is open, whether the UI is in preprocessing / solving / postprocessing, whether
  the displayed stage is the base stage, and a `capabilities` map. Each tool is
  now classified (`model_read`, `model_write`, `stage_write`, `result_read`,
  `check_*`, `analysis_run`, `view`, `lifecycle`) and refused up-front when the
  bridge says that operation is not allowed, instead of failing half-way through
  a write.
  - Two "state unavailable" cases are deliberately handled differently:
    `guard_unavailable` (the installed qtmodel has no `get_model_state`) passes
    through, preserving 0.3.1 behaviour; `state_unknown` (qtmodel has the API but
    QiaoTong did not send `model_state`, i.e. the software is too old) fails
    closed, because with the 2.8.2 handshake gone this is the only signal that
    the software predates the feature.
- **qtmodel 2.8 overview kinds in `get_model_data`** — `summary`,
  `analysis_context`, `project_metadata`, `check_context`,
  `structure_group_summaries`. These are the single-round-trip, agent-oriented
  endpoints upstream added in 2.8 (`odb_model_overview`). Payloads are passed
  through unmapped (their schema is defined server-side); on qtmodel 2.6.3 they
  return an explicit "requires 2.8+" message rather than an error.

### Changed

- **Sync qtmodel source through `2316654` (2026-09-08), including the query
  migration (`ac4dbad`, `bc1ee99`, `6821413`).** Model queries now prefer `mdb`, with capability-based fallback
  to legacy `odb` builds. Existing-model section geometry maps to
  `mdb.get_model_section_shape`, not the local `get_section_shape` builder.
  Analysis results and visualization remain on `odb`. MDB `get_`, `query_` and
  `calc_` gateway calls require read permission and do not refresh the model;
  state-changing calls such as `calculate_section_property` retain the write guard.
- **Keep the published qtmodel dependency and lock unchanged.** Upstream still
  labels these commits 2.8.2. Source revision `2316654` restores the helper
  deleted by `6821413`; offline compatibility checks now cover this latest
  source and the PyPI 2.8.2 build. The published wheel does not yet include the
  new options or management APIs; support is detected by capability, not version.
- **Dependency bound widened to `qtmodel>=2.6.3,<2.9`.** qtmodel 2.8.2 removed
  the strict version handshake (`get_connection_status` now always reports
  `compatible=True` once connected), so a qtmodel minor bump no longer forces a
  matching QiaoTong upgrade. `version_mismatch` can therefore only appear with
  qtmodel 2.6/2.7; docs and the `check_qiaotong_connection` description say so.
- **Compatibility table rewritten** to describe the pre- and post-2.8.2 matching
  rules, and to note that two builds of "2.8.2" exist: the PyPI wheel
  (2026-08-20, built from upstream `340e94e`) lacks `get_model_state`, while the
  upstream source at the same version (merged in `5f4f4eb`) has it. Qiao-MCP
  detects the capability, not the version.

### Fixed

- **Bridge workflows use resolved entity IDs.** Both templates build elements and
  supports from the node IDs read back in coordinate order, reuse the requested
  material and section by exact name, and allocate element IDs above the existing
  maximum. Incomplete node readback or unverifiable geometry stops before elements
  and supports are written. Missing continuous-bridge sections and invalid dimensions
  fail before geometry creation; property creation errors are no longer swallowed.
  Results include node, element, support, material and section IDs. Partial writes
  are not rolled back, and repeated workflows can add duplicate elements/supports.
- **Tool guidance matches the exposed catalog.** Material and section lookups now
  point to `get_model_data`. Load, stage, temperature, tendon, display and modification
  descriptions clarify units, prerequisites, tool selection and side effects.
- **MCP initialization reports the Qiao-MCP package version**, rather than the SDK
  version, so clients and directory inspections can identify the running release.
- **Partial plate updates retain `plate_type`.** Updating another property no longer
  silently changes a thick plate into a thin plate.
- **Correct the plate-thickness type description:** `thick_type=0` is an ordinary
  plate and `1` is a ribbed plate; unequal thickness is controlled by `t_out`.
- **Section-property recalculation retains model-write protection.** Both the
  dedicated tool and API gateway now require `modify_model`; the gateway no
  longer treats every `calculate_*` MDB method as a read-only query.
- **Typed query records stay structured.** Recursively normalize `to_dict()` /
  `Mapping` objects, including nested records and section properties, before
  MCP serialization. Materials, loads, boundaries, tendons, overviews, resources
  and gateway responses no longer become Python object representations.
  Public-attribute fallback remains for older qtmodel classes.
- **Import diagnostics distinguish an absent qtmodel package from a broken
  installation.** Missing internal modules or dependencies are reported with
  their original exception instead of misleadingly asking to install qtmodel.
- **`run_analysis` ignored its `read_timeout` budget on qtmodel 2.6.3+.** Since
  2.6.3 `mdb.do_solve` defaults to `sync=True`, under which QiaoTong blocks
  inside the HTTP request and `wait` / `max_wait` / `poll_interval` are never
  read (`if wait and not sync`). The provider passed `wait=True, max_wait=3600`
  believing it was polling; the effective limit was the request's default
  600-second read timeout, after which the tool reported a timeout while the
  solve carried on in the background. The provider now passes `sync=False`,
  restoring the background-task + poll path so `read_timeout` is the real total
  budget — the path upstream itself recommends for large models. Guarded by a
  new semantics test.

---

## [0.3.1] - 2026-08-15

### Added

- **Backend selection via `BRIDGE_PROVIDER`** — the 132 tools are now decoupled from
  any single backend. `create_provider()` dispatches by name with lazy imports, so a
  missing dependency in one backend does not break the others. Adding a backend means
  implementing `BridgeProvider` and registering one line — no tool-layer changes.
  QiaoTong (`qtmodel`) remains the default.
  - Unknown values fail at startup and list the valid choices, rather than silently
    falling back to the default. Selecting the wrong backend and connecting to a
    different application would only surface as incorrect analysis results.
- **MCP Registry metadata** (`server.json`) for publication to the
  [official registry](https://registry.modelcontextprotocol.io/), including the
  `mcp-name` ownership marker required for PyPI verification.

### Fixed

- **Abstraction leak in the startup path** — the server log read
  `QtModelProvider._unavailable_reason`, a backend-private attribute. Any second
  backend that did not happen to use the same attribute name would raise
  `AttributeError` during import, before any tool could run. `unavailable_reason()`
  is now part of the `BridgeProvider` contract, with a default implementation that
  stays compatible with the existing attribute.

### Documentation

- Corrected the QiaoTong links: official page is
  <https://www.brdi.com.cn/Software.html>; the user manual is at
  <https://soratayang.github.io/>.
- Added a "Backend Selection" section and a three-step guide for adding a backend.

---

## [0.3.0] - 2026-08-14

### ⚠️ BREAKING CHANGES

- **Minimum QiaoTong version is now 2.6.3** (qtmodel API version 2.6.3)
  - Previous versions (0.1.x, 0.2.x) required qtmodel 2.6.2
  - Users must upgrade QiaoTong software to 2.6.3+ before installing qiao-mcp 0.3.0
  - See [Version Compatibility](README.md#version-compatibility) for the full compatibility matrix

### Added

- **`get_connection_status` tool** — comprehensive connection diagnostics that distinguish three failure modes:
  - `qtmodel_not_installed` — package missing, run `uv add qtmodel`
  - `software_not_running` — QiaoTong not launched, start the application
  - `version_mismatch` — QiaoTong API version incompatible with qtmodel, upgrade software
  - Returns structured JSON with `status`, `message`, `action`, and version metadata
- **Smart localhost guidance** — when connection fails and `QIAOTONG_HTTP_URL` points to localhost/127.0.0.1, the tool now suggests checking if the user is connecting from a different machine (e.g. macOS client → Windows QiaoTong) and prompts for the LAN IP
- **Node ID tracking** — `create_nodes_linear` now returns the actual node IDs assigned by QiaoTong backend, even when numbering differs from the requested `start_id`
  - Prevents silent numbering mismatches that would cause downstream element creation to fail
  - Reports ID sequences compactly (e.g. "1–10, 15, 20–25") while preserving order

### Changed

- **Version strategy shifted from mirroring qtmodel to independent semver** — qiao-mcp versions now evolve independently; qtmodel compatibility is declared via dependency bounds and documented in the compatibility table
- **Dependency pinning tightened**:
  - `qtmodel>=2.6.3,<2.7` (was `>=2.6.2` without upper bound in 0.2.x)
  - `mcp>=1.29,<2` (was `>=1.0.0,<2` — now reflects actual usage of 1.29+ APIs)
- **`create_nodes_linear` now honors `start_id`** — fixed silent ignore of `start_id` parameter (was hardcoded to `numbering_type=1`; now uses `numbering_type=2` to respect user-specified IDs)

### Fixed

- **Crash when qtmodel installed but QiaoTong not running** — `get_connection_status` no longer raises `TypeError: argument of type 'NoneType' is not iterable` when `active_url` is `None`
- **Misleading localhost connection advice** — corrected internal comment and tool message that incorrectly suggested "Windows HTTP.sys rejects 127.0.0.1 Host headers" (actual issue: localhost can't reach a different machine's QiaoTong instance)
- **Unhandled exceptions during provider initialization** — QtModelProvider now catches all connection errors and wraps them in actionable unavailability messages

### Documentation

- **README rewritten** — Version Compatibility section now shows a clear table mapping qiao-mcp versions to required qtmodel/QiaoTong versions, replacing the old encoding-based explanation
- **Bilingual error messages** — all tool error messages now include both English and Chinese (中文) guidance

---

## [0.2.1] - 2024-08-04

### Fixed

- CI: Fix backmerge and publish workflow issues

---

## [0.2.0] - 2024-08-03

### Added

- Initial public release
- Support for qtmodel 2.6.2
- Core modeling tools: nodes, elements, materials, sections, loads, boundary conditions
- Solve and query tools for structural analysis results
- Generic API gateway for qtmodel methods not yet wrapped

[Unreleased]: https://github.com/SorataYang/qiao-mcp/compare/v0.3.3...develop
[0.3.3]: https://github.com/SorataYang/qiao-mcp/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/SorataYang/qiao-mcp/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/SorataYang/qiao-mcp/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/SorataYang/qiao-mcp/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/SorataYang/qiao-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/SorataYang/qiao-mcp/releases/tag/v0.2.0
