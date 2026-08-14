# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.0]: https://github.com/SorataYang/qiao-mcp/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/SorataYang/qiao-mcp/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/SorataYang/qiao-mcp/releases/tag/v0.2.0
