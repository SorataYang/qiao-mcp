# 工具审计修复进度

## 目标与统计口径

目标是修复 2026-10-15 起的 156 项工具审计中剩余的 **9 项部分通过、
9 项不支持、3 项失败**，按独立逻辑改动提交代码、测试和文档。
拒绝危险请求、离线测试通过或返回空结果，都不能代替原工具功能的实机验收。

2026-10-22 本轮只关闭原清单中的 **1 项**，另有 **1 项从失败推进到部分通过**。
当前总计 **136 通过 / 10 部分通过 / 9 不支持 / 1 失败**，目标尚未完成。

## 已提交修复

`8b07e18 fix(qtmodel): 修复国际活载请求的版本字段兼容问题`

qtmodel 2.9.3 的 `send_dict` 为请求增加 `version`，而当前桌面端的国际车辆、
国际活载工况完整定义 DTO 不接受该字段。适配器仅处理这四个新增/更新方法，
保留原生默认值、输入校验、返回值解码、模型实例/编辑上下文和不重发行为。
专用工具与 API 网关共用此适配器；没有删除安全参数或放开未开放的命令。

验证结果：

- 全量测试：`uv run --no-sync pytest -q`，**2229 passed, 1 skipped**。
- 改动文件的 Ruff 检查通过，`git diff --check` 通过。
- EN1991 车辆新增、完整更新、改名、保存并重开通过；编号 122、轴载、
  均布荷载、长度、间距、alpha 和显式 false 开关保持。
- 国际工况新增、更新和改名已不再被 `version` 拒绝；跨度、子工况、
  车辆/车道引用及保存子工况开关可回读并持久化。
- **工况编号仍存在桌面问题**：请求编号 133 首次回读为 133，随后变为 1；
  另一个新增工况请求编号 233，已提交后的回读却为 2，工具正确报告编号不匹配。
  保存重开和 SQLite `LiveLoadCase.Id` 均确认最终编号为 1、2。
  不能仅归因于更新或改名，也不能通过额外查询、强行回填编号或放宽断言宣称解决。
  探索性的编号回填补丁已撤回，未提交。
- 修复前后均为 9 节点、8 梁单元、1 截面；独立副本的 SQLite 完整性检查为 `ok`。

## 原始 21 项清单

“历史待补测”表示沿用此前的实机证据，本轮没有把它重新计为已验证成功。

| 工具 | 原状态 → 当前状态 | 验收结果或剩余要求 |
| --- | --- | --- |
| `set_international_vehicle` | 失败 → 通过 | 本轮 EN1991 完整定义增改及保存重开通过；不代表所有规范组合均已实测 |
| `set_international_live_load_case` | 失败 → 部分通过 | `version` 问题修复；显式编号及编号保持仍未满足 |
| `get_live_load_results` | 失败 → 失败 | 历史待补测：原生查询空引用、结果分量全零；须以非零载荷验收力和位移 |
| `start_analysis_job` | 不支持 → 不支持 | 本轮复现：桌面未提供 `model_instance_id`，不能安全启动持久任务 |
| `get_analysis_job` | 部分通过 → 部分通过 | 缺少可真实创建的持久任务，不能仅以未知 ID 拒绝用例算通过 |
| `configure_live_load_system` | 不支持 → 不支持 | 本轮复现：桌面拒绝 `clear_existing`；不得删掉清理许可参数绕过 |
| `set_planned_lane` | 不支持 → 不支持 | 本轮复现：`ADD-PLANNED-LANE-LINE` 被 SDK 的 `API_NOT_OPEN` 拒绝 |
| `manage_check_material` | 不支持 → 不支持 | 本轮复现：`SET-CHECK-MATERIAL` 未开放 |
| `manage_check_case_definition` | 不支持 → 不支持 | 本轮复现：`SET-CHECK-CASE` 未开放 |
| `set_check_stirrup_snapshot` | 不支持 → 不支持 | 本轮复现：`SET-CHECK-STIRRUP` 未开放 |
| `set_element_stirrups` | 不支持 → 不支持 | 本轮复现：`SET-ELEMENT-STIRRUPS` 未开放 |
| `set_section_reinforcement` | 不支持 → 不支持 | 本轮复现：`SET-SECTION-REINFORCEMENT` 未开放 |
| `remove_section_reinforcement` | 不支持 → 不支持 | 本轮复现：`REMOVE-SECTION-REINFORCEMENT-BY-NAME` 未开放 |
| `add_influence_plane` | 部分通过 → 部分通过 | 历史待补测：显式 true 未保存为 true，需要验证真实划分选项 |
| `run_concrete_check` | 部分通过 → 部分通过 | 历史待补测：求解成功但 stress 为空，缺少工程检算数值 |
| `get_check_data` | 部分通过 → 部分通过 | 历史待补测：输入及箍筋筛选已验证，检算 stress 结果仍未验收 |
| `configure_check_analysis` | 部分通过 → 部分通过 | 历史待补测：活动字段保持，裂缝相关字段发生变化，须按规范验证 |
| `manage_check_case_file` | 部分通过 → 部分通过 | 历史待补测：钢筋等输入可重开，裂缝配置和检算结果往返未完整通过 |
| `get_special_results` | 部分通过 → 部分通过 | 历史待补测：模态可读，屈曲查询失败，其余变体待验证 |
| `plot_analysis_result` | 部分通过 → 部分通过 | 历史待补测：位移通过，屈曲绘图曾崩溃；安全拒绝不等于绘图通过 |
| `change_construct_stage` | 部分通过 → 部分通过 | 历史待补测：stage=0 返回成功但未切回基本阶段 |

## 环境与证据

本轮桌面为 **26.1.116.1015 / API 2.9.3**，客户端使用仓库锁定的 qtmodel 2.9.3。
桌面插件 SHA-256：

```text
3bda7dd669404d1fe70485f5b025dacd66a00fc4a93f52082bcb11a3d81afb59
```

已只读同步上游引用至 `6759387`，检查其 qtmodel 2.9.4 源码：上述 7 个未开放命令
仍在 `UNAVAILABLE_HTTP_COMMANDS` 中，国际完整定义构造器未变更。
这并不证明升级 SDK 能解决桌面问题；本轮没有修改依赖锁、替换桌面文件或重启桌面。

完整请求/响应及数据库副本位于本机忽略目录
`reference-docs/tool-audit-20261015-156/raw/`，不随仓库分发：

- `86-fix-international-20261022-result.json`：保护原模型并另存实验副本；
  首次车辆请求因缺少两个必填布尔字段而被输入校验拒绝，没有发送该写入。
- `87-fix-international-20261022-result.json`：车辆及工况增改；工况编号变化证据。
- `88-fix-case-identity-20261022-result.json`：第二个工况已提交但编号不匹配；未重放该写入。
- `89-save-identity-evidence-20261022-result.json`：保存、重开及定义回读。
- `91-unsupported-contracts-20261022-result.json`：9 项不支持的最新实机拒绝记录；
  持久任务列表前后为空，未启动求解。
- `92-native-snapshot-20261022/inspection.json`：插件哈希、模型副本哈希、表计数和完整性检查。

模型快照 SHA-256：

```text
before: c2eed82a41a1a93a95629e604d561f33a1fdd4c513c3fb58b56839356af07f4b
after:  f5847086aa2673da147f5f053ca559ac95c1a113f048cc0f98feb3bb75f35940
```

## 后续验收条件

1. 在桌面端定位工况编号重排，确认请求编号、内存对象、引用及持久化编号的契约；
   同时验证影响面 true 参数、基本阶段切换及求解结果接口。
2. 对七个未开放命令，需要实际存在的桌面路由和载荷契约，不能删除 SDK 拒绝列表，
   也不能拿检算窗口的不同接口冒充基础模型快照写入。
3. 持久任务需要桌面提供有效模型实例标识及相应写入守卫；清理活载需要桌面实现
   `clear_existing` 的许可与回滚语义，不能以工程路径或预查询代替原子守卫。
4. 对尚未验收的检算、活载、屈曲和绘图，用隔离的非零载荷模型完成真实求解、
   数值/图像回读及文件往返，再更新对应项；不重跑已发生崩溃的绘图来冒险验证。
