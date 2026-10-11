# 🌉 Qiao-MCP

[English](./README.md) · **简体中文**

> 桥梁全过程结构分析 MCP 服务器 — 建模、施工阶段、规范验算  
> Full-lifecycle bridge structural analysis — modeling, staging, code checks

Qiao-MCP 是一个基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) 的服务器，让 AI 助手能够与桥梁结构分析软件交互。它提供了创建桥梁模型、施加荷载、运行结构分析和查看结果的工具。

## 功能特性

### 🔧 工具（开发版 150 个，按功能分组）

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

148 个非图片工具提供输出 Schema，并返回 MCP 结构化内容（`{status, message, ...}`）。连接诊断另有 `connection_status`、`connected` 等字段；一键建桥返回实际节点、单元、材料和截面编号；`get_model_status` 的 `status` 保留桥通状态。两个支持图片的工具返回可预览的 MCP 图像或文本说明。执行失败使用类型化 MCP 错误；工具注解说明只读、破坏性和开放世界行为。调用长尾 API 前，请先使用 `list_qtmodel_api` 查询真实签名。

输入 Schema 包含参数说明、固定枚举、分页范围和坐标/自由度数组长度约束，不符合 Schema 的输入会在调用后端前被拒绝。梁端 `release_i` / `release_j` 中 **True 表示释放**，省略某端表示该端六自由度均不释放。荷载组合分项顺序为 `[工况类型, 工况名, 系数]`，`combine_type=3` 才是包络。

### 开发中：B1 查询与诊断（未发布）

开发目录新增 `get_model_edit_readiness`、`query_model_data`，不计入下文 0.4.0 的纯参数补齐版本。
编辑就绪诊断在模型读写被阻断时仍可调用；`success` 仅表示收到响应，不表示可以编辑，应查看原始 `readiness` 对象。
工具不会保存/重用准备令牌，不切阶段、不删除结果。

`query_model_data` 使用按 `kind` 区分的类型化 `request`，例如：

```json
{"request": {"kind": "nodes", "structure_group_names": ["主梁"], "limit": 20, "offset": 0}}
```

支持 `nodes`、`elements`、`boundaries`、`loads`、`node_local_axes`、`section_summaries`。
名称须用列表；ID 用正整数或列表，不接受范围字符串；节点至少提供一个条件，`near` 与 `tolerance` 必须配对。
Qiao-MCP 自定列表/单页上限为 500；截面摘要按上游约束最多 100 个显式 ID、单页最多 100 条。
结构化 `data` 保留原生分页字段，不推算总数、不二次切片；缺接口明确报错，不全量下载后本地过滤。

`get_model_data` 增加 `material_summaries`、`material_detail`、`load_case_summaries`、`load_case_detail`、
`load_combination_summaries`、`load_combination_detail`、`construction_stage_summaries`、`element_section`、`spans`。
新详情通过 `ids` 指定一个正整数或单项整数列表；实际单元截面用 `position=0|1` 指定端部。
工况/组合详情在服务端分页，其他列表维持原文本分页。摘要不等于可无损写回的完整快照，施工阶段编号随当前阶段顺序变化。

`configure_live_load_system` 显式选择五类活载体系，默认不清理旧定义。`configure_operation_stage` 必须给出四类工况列表，`[]` 关闭对应分析；两个工具只提交设置，不启动求解。

横向定义使用 `set_transversal_vehicle` / `set_transversal_lane`，以完整的类型化
`request` 和 `action="add"|"update"` 增改；同名或指定编号可能覆盖已有定义。
先显式选择 `china_transversal`。荷载固定 kN、长度固定 m，不跟随显示单位。
车道节点保留输入顺序，相邻节点必须已有梁直接连接；`distribution_widths` 是米。
实际编号取返回的 `data.index` 或 `get_transversal_data`，不能猜测。
回读保留原生字段 `load_factors`，编辑时映射为 `distribution_widths`。

`set_transversal_case` 核验车辆/车道实际编号，使用正数 `reduction_factors` 列表
表示 1..N 车道系数，另传 `greater_lane_factor` 表示超过 N 车道的系数。
`remove_transversal_data` 必须指定目标，车辆/车道默认 `cascade=False`；工况删除
不接受 cascade。荷载组合和运营设置的引用须先显式解除。

基础模型配筋使用 `set_section_reinforcement` 的完整 UI 导出快照，或通过
`remove_section_reinforcement` 按 `1`、`1-I`、`1-J`、`G7-2` 等完整标识删除。
所有快照字段必填，空数组清空对应部分；外/内侧六项行、模型长度单位与旧参数配筋
工具不同。当前 CSAN 查询不是可无损写回的模型快照；新工具要求模型写权限并提交一次。

`set_check_stirrup_snapshot` 保存完整导出定义，改编号时显式传 `original_id`。
`set_element_stirrups` 分别完整替换剪力五项行、扭转三项行；`null` 保持该类、`[]`
清空，箍筋号 `0` 表示该方向未配置。既有 CSAN 箍筋工具保留原有接口。

`manage_check_material` 完整设置导出的材料覆盖值，或按编号恢复基础材料；
`manage_check_case_definition` 完整设置/删除混凝土、抗震、加固三类模型检算工况，
保留模型枚举原值。提交后既有 `run_concrete_check` 会先导入具名混凝土工况再检算，
它不负责抗震或加固求解。材料 properties/parameters 和存储单位须取自完整导出。

国际车辆使用 `set_international_vehicle`，`request` 按
`standard="AASHTO"|"BS"|"EN1991"` 选择独立参数 Schema。先显式选择相应活载体系；
`parameters` 和 `load_items` 必须给出，包括 `{}`/`[]`。新增和修改都是完整替换，
省略或为 null 的标量采用新建默认值；修改按原名称定位并保留实际编号与引用。
写入只提交一次，随后按精确名称回读完整定义和实际编号。

| 规范 | 原生单位与约定 |
|------|----------------|
| AASHTO | 轴列 `[N, m]`，`w` 为 N/m，长度 m，`r` 为百分数（90 表示 90%） |
| BS | `pa`/`pb` 为 kN，`w3` 为 kN/m，长度 m；`w1`/`w2` 为公式系数，指数无量纲 |
| EN1991 | 轴列 `[kN, m]`，均布荷载 kN/m，点荷载 kN，长度 m；受载长度与间距分别传递 |

上游 SDK 未明确 BS 轴列的力单位。须使用已核实的 BS 原生导出/查询值并保持不变，
不能套用其他规范的单位。`get_international_live_load_data(kind="vehicles"|"cases")`
保留完整原生字段，对上游返回的全量列表做本地筛选与分页。车辆导出可能含其他规范的
非活动参数：专用工具只接收对应规范的字段；完整原生定义原样回放仍可使用网关。
以上接口不统一缩放荷载值。

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

### 💬 提示词 (5个工作流)
| 提示词 | 描述 |
|--------|-------------|
| `design_simple_beam` | 简支梁桥设计工作流 |
| `design_continuous_beam` | 连续梁桥设计 |
| `check_structure` | 结构规范验算 |
| `construction_stage_analysis` | 施工阶段分析 |
| `analyze_transversal` | 横向定义、配置、求解及完整结果工况名查询 |

普通静力结果仍默认自动加 `ST:`。其他结果使用 `case_name_mode="full"`，传入桥通
结果界面或已验证接口给出的完整工况标识，工具原样转交；不能把组合类型 TV/MV 当作
结果接口的前缀约定。

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

**Provider 模式**让 150 个工具与具体后端解耦。用 `BRIDGE_PROVIDER` 选择后端；每个后端自己声明软件专有规则，因此换后端无需改提示词。当前支持：
- **QTModel**（`qtmodel`，默认）— [桥通 (QiaoTong)](https://www.brdi.com.cn/Software.html) 桥梁分析软件（[用户手册](https://soratayang.github.io/)）

接入新后端只需实现 `BridgeProvider` 并登记一行，不改工具层代码。详见 [后端选择](./INTEGRATION_GUIDE.md#后端选择-backend-selection)。

## 快速开始

### 前置要求
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器
- `qtmodel` 2.6.3 – 2.9.x，不含 2.9.0（`uv sync` 会自动安装，当前锁定 2.9.2）
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
| 0.4.0          | 2.6.3 – 2.9.x，不含 2.9.0 | 2.6.3+；配 2.9.x 时桥通须上报模型状态  |
| 0.3.2 – 0.3.3  | 2.6.3 – 2.8.x | 2.6.3+；2.8.x 不再要求两侧版本精确一致 |
| 0.3.0 – 0.3.1   | 2.6.3 – 2.6.x | 2.6.3（qtmodel 强制精确匹配）          |
| 0.2.x           | 2.5.0 – 2.5.x | 2.5.0                                  |

**最低版本已知限制：** qtmodel 2.6.3 缺少 `get_load_group_names`，不能使用一键建桥工作流工具。这是早于本次 0.4.0 参数扩展的既有问题；这些工作流请使用 2.6.4 或更新版本（仍排除 2.9.0）。

两侧版本的匹配方式在 qtmodel 2.8.2 发生了变化：

- **qtmodel 2.6 / 2.7** 做精确版本握手——桥通 API 版本与已安装的 `qtmodel` 必须完全一致，否则 `check_qiaotong_connection` 报 `version_mismatch` 并拒绝连接。
- **qtmodel 2.8.2** 取消了该握手。任何暴露 Python API 的桥通都能连上，`version_mismatch` 不再出现。代价是偏旧的桥通可能缺少新命令；`get_model_status` 会把这种情况报为 `state_unknown`（桥通早于模型状态握手），工具据此 fail closed，而不是盲写。

不同构建可能都标记为 qtmodel 2.8.2：PyPI 上的 wheel（2026-08-20）不含 `QtServer.get_model_state`，而同版本号的上游源码已带上它。Qiao-MCP 按能力而非版本号探测——没有该方法时跳过模型状态守卫（`guard_unavailable`），行为与 0.3.1 一致；有该方法时，每个工具都会按桥通上报的状态放行或拦截。qtmodel 2.9.0 是首个带该方法的 PyPI 正式发布，因此在 2.9.x 上守卫始终生效。

### qtmodel 2.9 上游变更（2026-09-11 至 09-24）

参考仓库已同步至 `8ae651e`，其 qtmodel 包与 PyPI 2.9.2 wheel 完全一致（源码中 `QT_VERSION` 仍写作 `"2.9.1"`）：

- **写入安全：** 写命令的响应丢失时抛 `CommandOutcomeUnknownError`，不再自动重发。本项目将其报为"结果未知"，并提示客户端先回读模型，不要重试。
- **客户端校验：** 许多写接口会在下发前拒绝不合法的数值。本项目的参数 schema 已对齐：徐变/收缩曲线不能为空，截面特性表只能是 26 或 29 项，各规范的徐变参数个数固定，自定义材料必须提供 `data_info`。
- **节点质量字段：** `add_nodal_mass` 的 `mass_info` 实为 `(平动质量, 绕X, 绕Y, 绕Z 转动惯量)`，并新增 `mass_xyz` 表达各向不同的平动质量。本项目已按此布局下发（字段修正见更新日志）。
- **现有工具补齐新参数：** 施工阶段支持小数工期和 `sub_steps`；`create_material` 增加 `is_orthotropic` / `ey`；`set_support`、`add_elastic_support` 增加 `coordinate`、`extra_enabled` 和 8 项 `extra_parameters`，单向弹性支承另支持正负轴 `axis_direction`；`add_influence_plane` 增加 `always_divided_by_beam_shape`，`create_live_load_case` 增加与子工况等长的布尔列表 `sub_case_optimized`。省略选项保持旧行为，显式指定则在写入前按真实签名检查；旧版会截断的小数工期创建请求改为明确报错。工具总数仍为 133。
- **运营设置和级联删除继续走网关：** 检索 `update_operation_stage_setting` 后可传 `transversal_load_cases`，必须同时提供全部需计算的工况列表，省略/空列表会关闭对应分析。`remove_material` 默认 `cascade=True`，连同相关钢束特性和钢束删除；`remove_tendon_property` 默认 `False`，设为 `True` 会无弹窗删除引用钢束及其荷载。删除前须确认范围，不指定名称和编号会删除全部对象。
- **新接口经 API 网关使用：** 横向分析、国际/规划车道活载、加固、按身份精确删除对象（`delete_model_object`）、`cdb` 的完整配筋与检算快照，以及修改前准备检查（`get_model_edit_readiness`）。网关会在每次 MDB 写操作后调用 `update_model` 提交，这是这些接口的要求。
- **网关禁用：** `post_python_file`（读取本地文件并发往任意 URL 执行）、`prepare_model_edit`（可能不可逆地删除结果，应由宿主程序在用户确认后调用）、`export_api_help`（把 SDK 帮助写到本机任意路径），以及原有的 `ensure_running`、`set_url`、`set_version`、`export_qt_helper` 和 `wait_solve`（默认无限期轮询，请用 `run_analysis`）。

### 2026-09-04 至 09-08 上游源码变更

以下变更最初在 `2316654`（版本号仍为 `2.8.2`）时同步，现已包含在 2.9.0 中：

- `ac4dbad`：模型查询由 `odb` 迁移至 `mdb`。本项目优先使用新接口，方法不存在时回退至旧版 `odb`；查询已有截面几何使用 `mdb.get_model_section_shape`，不会误调用本地几何生成器 `mdb.get_section_shape`。分析结果与视图仍使用 `odb`。
- `bc1ee99`：模型查询改为返回支持 `to_dict()` / `Mapping` 的类型化对象。本项目统一递归转换为普通 JSON 数据，覆盖工具、资源和 API 网关，保留服务端原始字段。MDB 查询按只读权限检查，不再要求修改模型权限，也不会触发模型刷新；`calculate_section_property` 等会改变模型的调用仍要求修改权限。
- `6821413`：模型对象按结构、材料、荷载等领域拆分，`core.model_db` 保留兼容导出；本项目适配层不依赖这些内部类型路径。
- 9 月 7–8 日：新增板厚 `t_out`、求解 `show_view`、12 个分析设置重置接口和 3 个板厚批量管理接口。本项目在现有工具中增加这两个参数，15 个管理接口继续通过 API 网关检索和调用，无需增加重复封装工具。

**构建兼容性：** 这些新参数和管理接口已包含在 PyPI 2.9.x 正式发布中；PyPI 上 8 月 20 日发布的 2.8.2 不含。默认调用在两者上都能正常工作；显式指定 `t_out` 或 `show_view=True` 时，会先检查真实签名，不支持则在写入或启动求解之前明确报错，不能仅凭版本号判断功能是否可用。

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
