# 根据 Glama 0.3.1 评分改进当前版本的执行计划

日期：2026-10-12。状态：G0–G5 离线候选已完成，G6 待单独执行。

执行结果：[0.5.1 候选验收](0.5.1-validation.md)、[39+21 项审计](glama-improvement-audit.md)、
[选型及目录取舍](glama-tool-selection.md)、[TDQS 提醒处置](glama-tdqs-review.md)。
分支 `improve/glama-tool-quality`，实现提交 `b4ae38f`；本轮仅本地提交及候选交付。

本计划使用 Glama 已评分的 **0.3.1 快照**定位问题，在当前 **0.5.0 代码基础**上实施改进。
推荐先用一个 goal 完成 G0–G5 的离线优化和候选交付；平台恢复后，再用另一个 goal 完成 G6 的发布、采集和线上复评。
线上效果目标仍为 **A（当前 TDQS 阈值为 3.5）**，本地检查通过不能证明该目标已经达到。

## 依据与已经完成的工作

来源：[Glama 公网页](https://glama.ai/mcp/servers/SorataYang/qiao-mcp)、
[现有评分基线](glama-baseline-20261012.json)、[质量记录](glama-quality.md)、
[本次实施对象清单](glama-improvement-targets.json)。

完整的旧逐工具评分与 0.5.0 目录已分别冻结在
`reference-docs/glama-improvement-baseline-20261012/glama-0.3.1.json` 和
`reference-docs/glama-improvement-baseline-20261012/qiao-mcp-0.5.0-catalog.json`；
清单记录了路径及 SHA256。它们位于本地忽略目录，跨机器执行时需保留这些证据文件。

旧质量评分时间为 `2026-09-09T17:50:38.437293Z`。
本次代码基线为 `develop@8065f31`，与 `main@fa3ae8d` 文件内容相同。

| 项目 | 已评分 0.3.1 | 已发布 0.5.0 |
| --- | ---: | ---: |
| 工具数量 | 132 | 153 |
| 有描述的顶层参数 | 0 / 543 | 596 / 596 |
| 输出 schema | 0 | 151；另有 2 个图片工具 |
| 工具评级 | 10 C、29 B、93 A | 尚未取得线上评分 |
| 所有工具 description 字符总数 | 76,205 | 153,192 |

Glama 的整体扣分为：工具区分 **2/5**、工具数量适当性 **2/5**、命名一致性 **4/5**、能力完整性 **4/5**。
描述质量为 3.4，单工具平均 3.8、最低 2.7，整体为 B 3.3。

39 个旧 B/C 级工具中，37 个的使用指引不超过 2 分，32 个的行为透明度不超过 2 分，
14 个的上下文完整性不超过 2 分，4 个的参数语义不超过 2 分。
因此优先解决选型、前置条件、作用范围和调用结果；参数描述数量已经达标。
许可证和维护统计单列观察，与这里的工具质量分分别记录。

已用正式发布包导出的目录比对：这 39 个工具中 **34 个已经改过 description**，包含全部 10 个 C 级工具。
改过文字不等于缺陷已经关闭，后续需要逐项核验，而不是重新整批改写。

仍沿用旧 description 的 5 个工具是：

| 工具 | 旧分数 | 本轮首先核查的内容 |
| --- | ---: | --- |
| `add_creep_function` | 3.4 | 自定义曲线与规范收缩徐变参数的选型、缩放含义、绑定与重名行为 |
| `add_support_settlement` | 3.4 | 强制位移荷载与支承约束的边界、单位/符号、前置条件 |
| `get_tendon_position_result` | 3.4 | 几何与结果查询的边界、是否要求分析、坐标系/单位及空结果 |
| `renumber_nodes` | 3.4 | 单个与批量改号、参数省略时的全模型范围、编号冲突与引用关系 |
| `set_gravity` | 3.4 | 全局重力、自重计入阶段和重新分析之间的关系 |

## 本轮实现边界

- 采用兼容路线：153 个已有工具名称和合法调用方式继续可用，保持模型状态守卫、错误通道和图片返回约定。
- 说明中的工程事实必须对应当前 provider、已安装 SDK、上游实现或可信导出。单位、枚举、覆盖/叠加及重名行为没有证据时明确说明限制，不能为补齐评分而推断。
- Glama 的评语作为检查线索。例如评语中的 `calculate_ection_property` 是拼写错误；实际旧目录和当前目录均为 `calculate_section_property`，不应据此新增或重命名 API。
- 当前主线以工具契约、说明、schema 和选型一致性为主。必要的契约修正应附证据、兼容影响和行为测试。
- 大幅收缩默认目录、移除旧入口或新增公开工具配置属于后续接口设计阶段。G2 会交付具体取舍依据，本轮不把兼容入口删减作为硬指标。
- 使用离线环境；协议检查的桥通地址固定为 `http://localhost:1/pythonForQt/`。真实业务工程不用于验证，离线 pytest 排除 `tests/test_end_to_end.py`。

## G0：建立逐条问题与证据的对应关系

在实际启动 goal 时，先检查工作区和分支，再确认本计划与当前源码的差异。
沿用本次清单，把 39 个对象逐项映射到“旧扣分 → 当前定义 → 实现/SDK 证据 → 处置”。

处置状态分为：已有改进且证据充分、仍需修补、旧评语与事实不符、后端事实暂未证实。
最后一类必须记录公开说明如何避免误导，以及需要什么后续证据；不需要因此停止其他工作。

交付：`docs/glama-improvement-audit.md` 及相应 JSON。
验收：39 项均有状态、源码定位和理由；所有“已解决”项都有具体证据。
当前版本比旧快照多出的 21 个工具单列，不能沿用不存在的旧评分。

## G1：补齐调用所需的行为说明

先处理上述 5 个未更新的 B 级工具，再核验 10 个旧 C 级工具，最后审查其余 24 个已改过的 B 级工具。
实施对象及优先级见 `glama-improvement-targets.json`。

10 个 C 级对象为：

`assign_tendon_elements`、`activate_structure`、`add_beam_section_temperature`、
`add_cable_length_load`、`add_distribute_plane_load`、`add_initial_tension_load`、
`add_plate_element_load`、`add_system_temperature`、`add_time_history_function`、`update_node_id`。

每项按实际复杂度回答：

1. 何时选它，最容易混淆的相邻工具何时选。
2. 哪些实体、工况、阶段或分析结果必须先存在。
3. 改的是模型、视图、求解设置、结果还是文件；目标和省略参数的范围是什么。
4. 重复调用、重名、完整替换、空列表、默认值各意味着什么。
5. 单位、坐标系、编号与必要输入组合是什么。
6. 返回什么、失败如何报告、成功后合理的下一步是什么。

已有正确内容予以保留。对简单工具用少量句子说明，复杂工具只增加决定正确调用所必需的内容。
正文、Args 注入的字段说明、annotations 和返回 schema 必须一致；不能仅将限制藏在全局 instructions 中。

重点文件：`tools/__init__.py`、`tools/tendon.py`、`tools/modifications.py`、`tools/visualization.py`，
以及对应 provider 方法。

验收：5 个未更新对象有具体改进或充分的保留理由；10 个旧 C 级对象的历史缺口逐项有处置；
全部 39 项不存在已确认却未处理的调用歧义或错误陈述。没有新线上评分时不宣称已经消除所有 C 级评级。

## G2：解决工具之间的选型歧义

针对实际调用路径建立双向选择说明，并与 server instructions、prompts、README 保持一致。

| 工具族 | 应明确的选择依据 |
| --- | --- |
| `add_to_structure_group` / `add_elements_to_group` | 通用节点/单元成员操作与仅单元便捷入口；成员移除与删除组分别处理 |
| `update_node` / `update_node_id` / `renumber_nodes` / `move_nodes` | 绝对坐标、单个改号、批量改号和相对位移；额外查询及写入范围 |
| `switch_display_stage` / `change_construct_stage` | 建模视图按阶段名选择与结果视图按阶段编号选择；不同状态要求 |
| `calc_section_property` / `get_model_data(kind=section_property)` / `calculate_section_property` | 给定几何试算、读取已存特性与重算全模型截面特性 |
| `update_element` 及 `update_element_id/material/section/beta/nodes` | 单实体综合修改与专用/批量操作；保留字段、额外查询和适用类型 |
| `get_tendon_info` / `get_tendon_loss_results` / `get_tendon_position_result` | 定义查询、损失分布与坐标查询；计算和阶段要求按真实接口核验 |
| 四种温度工具、两种索张拉工具、板荷载与分配面荷载 | 物理输入不同、前置步骤不同，分别给出最短选型路径 |

对 `tapper`、`bulking`、`calc/calculate` 等历史名称，在说明和术语表中使用准确术语并解释旧名，保持调用兼容。
评语所谓“重复”只有在目标、输入、行为、副作用和调用成本都一致时才认定为可合并。

交付：`docs/glama-tool-selection.md`，至少覆盖上表各组的两个有区分度的任务场景，
写清推荐入口、相邻入口不适用的条件及证据。人工审查用例不标记为模型选型测试通过。

另交付一份目录取舍记录：列明真正重复、便利封装、领域必需及待确认的入口。
如果未来需要更紧凑的目录，应以真实用户工作流设计，并保留明确的兼容路径；不能建立仅供 Glama 评分的空壳目录。
本轮工具数量仍为 153 时应如实报告，底层代码去重不能算作工具数量减少。

验收：上述工具族都有可核验的选择依据；单工具说明与全局指引没有冲突；所有已有名称仍可发现和调用。

## G3：审查定义体积、元数据及新增工具

当前工具 description 共 153,192 字符，既有新增能力，也有中英文和参数内容的重复。
先移除不增加语义的信息，再考虑注册层是否需要减少重复展示。

需要保留 Args 到 input schema 的现有说明注入机制；如果改变 description 的生成方式，必须验证字段说明、嵌套格式及跨工具引用没有丢失。
保留中英文可用性，避免机械加长每个工具或使用统一空泛的说明模板。

审查全部 153 个工具的：

- 参数描述是否表达真实含义，而非仅仅非空；关键嵌套结构、单位和枚举是否明确。
- annotations 是否与实际副作用一致，不能为提高分数将写操作标成只读或幂等。
- 输出 schema 是否符合实际返回；图片工具继续返回 MCP Image。
- 21 个新增工具是否复现相同缺口，尤其是完整快照替换、`None`/`[]`、固定单位和后端能力差异。
- 全局 instructions 是否引用实际存在的 MCP 名称，示例与 schema 是否相符。

已确认一个可修复实例：`provider.get_llm_instructions()` 的自重/结果示例使用了
`add_load_case`，而实际 MCP 目录只有 `create_load_case`。核验示例参数后修正引用，
避免将 SDK 方法名误当作 MCP 工具名。

交付：修改前后目录、逐工具说明长度和关键元数据差异摘要。
验收：没有以缩短文本为代价删除必要调用信息；参数说明 596/596、输出 schema 151/153、resources 7、prompts 5 继续成立。
对任何数量变化单独说明真实原因和影响，不静默修改检查预期。

## G4：完成适合本次改动的离线验证

优先运行相关现有测试。仅在修改契约、schema 生成或分发行为时补充有行为意义的测试，
不为文案建立“包含某关键词”的重复测试。

收尾时按 CI 使用的 **uv 0.11.6 / Python 3.11** 验证：

```bash
uv run --locked ruff check src/ tests/ scripts/
uv run --locked mypy src/qiao_mcp/
uv run --locked pytest tests/ --ignore=tests/test_end_to_end.py -q

GLAMA_CHECK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/qiao-glama-check.XXXXXX")"
uvx --from uv==0.11.6 uv build --out-dir "$GLAMA_CHECK_DIR"
uv run --locked python scripts/check_release.py "$GLAMA_CHECK_DIR"
uv run --locked python scripts/check_mcp_package.py "$GLAMA_CHECK_DIR"/*.whl \
  --output "$GLAMA_CHECK_DIR/catalog.json"

uvx --from tdqs==0.1.0 tdqs lint \
  --file "$GLAMA_CHECK_DIR/catalog.json" --server-name qiao-mcp \
  --format json --output "$GLAMA_CHECK_DIR/tdqs-lint.json" --fail-on warning
```

最后一项单独记录退出码和报告。当前基线为 0 error、39 条 `shadow-candidate` warning、2 条图片 schema info；
这些 warning 是调用成本预筛选，不能直接证明用途重复。逐条分类并保留理由，严格模式非零时如实报告。
新增 error 必须修复；不能通过停用规则或修改检查预期来掩盖退化。

使用 `mcp-proxy@6.7.19` 再检查打包候选的真实初始化和目录：
版本正确，153 个工具、596 个参数说明、151 个输出 schema、7 resources、5 prompts；
instructions 与直接 stdio 完全一致。代理进程仅监听本地，结束后关闭；无需真实桥通。
此项必须检查本轮候选的安装环境，不能引用此前临时源码目录的成功结果作为本轮证据。

若已有可用的语义评分模型配置，可固定 TDQS 规范、模型和参数，对 0.3.1、发布的 0.5.0 及候选分别评分。
先验证评分模型与规范的校准情况；这类结果标记为本地评估，不当作 Glama 线上评分。
没有可用配置时交付待评分目录与评估步骤，不阻塞其余离线工作，也不虚构分数或选型成功率。

## G5：交付可评审的优化结果

整理一个功能分支、本地提交和候选包，交付以下材料：

- 39 项问题处置表及 21 个新增工具的审查结果。
- 工具族选择说明、目录取舍记录、候选目录与差异摘要。
- 实际测试结果、TDQS lint 原始报告和 warning 处置。
- 所有尚未证实的后端语义、处理方式及后续所需证据。
- 发布说明草稿和 Glama 复评清单。

纯兼容质量修正可按 **0.5.1 候选**组织；进入发版阶段时统一修改版本文件，沿用仓库发布检查。
如果工作证明需要改变默认目录或调用契约，将该部分形成独立的 0.6.0 设计议题，先交付已完成的兼容优化。

G0–G5 的完成条件是：计划内已确认问题全部处理、必要检查通过、兼容性证据齐全、剩余未知项准确披露、候选可以评审。
Glama 暂时不可用不会阻止本阶段交付。最终报告区分“代码与离线验收完成”和“线上评级尚未验证”。

## G6：平台恢复后的发布与线上复评

维护者已发送 Glama 报障邮件。最新失败 build 为 `01a12ed9-eeaa-7fcd-8047-d625dff73baf`，
仍报 `ECONNREFUSED 10.90.0.1:80` 且 `logs: []`。
新 Configuration 已保存并进入生成的 Dockerfile：Python 3.11，Build steps 包含代理 6.7.19 和锁定依赖安装。
这部分配置无需重新准备；当前故障需要平台处理。

恢复后按顺序：

1. 对候选履行正常 PR、CI 和发布流程，确认默认分支包含最终改动；以实际发版范围更新版本。
2. Glama 构建成功后核对源码 commit、MCP 版本、工具目录、关键 schema 和 instructions；只更新 README 不算采集成功。
3. 保存新的评分时间、整体与逐工具评分、扣分理由以及可访问链接。
4. 比较两个参照：0.3.1 的线上旧分与新的线上分；若平台曾成功评估未改动的 0.5.0，也保留该中间参照。
5. 目标为整体 A；优先检查旧 10 个 C 级工具是否仍有对应缺陷、工具区分是否改善，以及新增工具是否引入新的低分。
6. 若仍未达到目标，依据新理由迭代。只有新的目录和实际线上评分共同证明改善后，才报告线上目标完成。

若工具数量仍是主要瓶颈，再执行 G2 所准备的目录设计议题，而不是不断延长文案。

## 可直接交给下一次 goal 的指令

```text
按照 docs/glama-improvement-plan.md 执行 G0–G5。
以 Glama 0.3.1 的 B 3.3 评分及 docs/glama-improvement-targets.json 为问题基线，
在当前代码上完成兼容的工具质量优化。先检查工作区状态，保留已有改动。

优先补齐 5 个仍未更新说明的工具，核验 10 个旧 C 级工具，再审查其余 B 级工具；
逐项记录旧扣分、当前实现证据和处置，不重写已经解决的问题。
处理计划列出的易混工具族，审查全目录元数据和 21 个新增工具，控制无必要的描述重复。

保留已有 153 个工具的名称和合法调用，维持状态守卫、错误通道及图片返回；
任何单位、枚举和覆盖/叠加语义均以实现及可信上游证据为准。
使用离线验证，排除 tests/test_end_to_end.py，不触碰真实业务工程。
完成适当测试、构建、包检查、mcp-proxy 6.7.19 协议检查和 TDQS lint，并如实记录 warning。

在功能分支完成本地提交，交付问题处置表、目录比较、验证报告、候选包及发布说明草稿。
本轮不执行推送或正式发布；完成条件是 G0–G5 的交付标准全部满足。
不等待 Glama 服务恢复。线上发布与复评留待 G6；不得把本地检查或本地评分称为线上 A。
```

后续单独执行 G6 时，以新的 Glama 目录和真实评分作为完成依据。
