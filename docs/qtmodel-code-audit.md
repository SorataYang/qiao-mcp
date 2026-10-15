# qtmodel 逐工具代码审计

2026-10-14。153 个已注册工具均已逐项检查，未审查项为 0。确认并处理了
27 类适配层问题；8 类 SDK/工程限制单独保留。本轮仅本地交付，没有连接桥通、
操作业务工程、推送或发布。

逐项证据：[qtmodel-code-audit.json](qtmodel-code-audit.json)。
检查结果与产物哈希：[qtmodel-code-audit-validation.json](qtmodel-code-audit-validation.json)。
早先的 [Glama 优化验收](0.5.1-validation.md) 是历史记录，不用于证明本轮改动。

## 范围与证据

- Qiao-MCP 基准：`8ce2715433f3168b36fadc605f5135f231c95565`；本地分支
  `audit/qtmodel-tool-correctness`。保持 153 个工具名称、依赖范围及 Provider 基类设计。
- 主对照：已安装 PyPI qtmodel 2.9.2，以及上游源码
  `0687ffe3fa481747c53f9521ee1503a2a043fc08`。另核对 2026-10-13 发布的 2.9.3
  相对 2.9.2 的 66 个新增/变化函数，并验证声明范围内的全部六个 PyPI 版本。
- 每项记录工具、provider、原生 SDK 的字段布局、分派、默认值、范围、提交次数、
  返回处理及说明。原始 `source` 保留基准位置；`current_source` 和
  `current_provider_sources` 另记录修改后的函数位置与 SHA256，整文件哈希也已保存。
- 网关两个工具审查的是目录检索、真实签名绑定、守卫、禁止名单、错误与提交机制。
  运行时 SDK 目录有 MDB 411、ODB 121、CDB 127 个方法；没有把它们全部算成已通过工程验收。

逐项状态为：42 项已修正、10 项已修正且有已知限制、91 项经检查未发现需改动的问题、
10 项已检查且有已知限制。这里的“未发现”只说明此次源码与离线检查结果。
F27 的提交错误说明属于共享路径修正，影响面另见 findings 表，不据此夸大工具问题数量。

## 已处理的问题

| 编号 | 问题与结果 |
| --- | --- |
| F01–F02 | 不再把请求坐标数冒充实际新增节点数；按实际前后 ID 集合及容差回读节点，遇到歧义或缺项不拼出错误梁链。 |
| F03 | 新截面显式使用 `index=-1` 自动编号，避免沿用 SDK 默认值覆盖 1 号截面。 |
| F04 | 修改选择拒绝空串/空表、布尔和分数编号；合法的显式全模型模式保留，全删和初始化采用严格布尔确认。 |
| F05、F15、F26 | 自定义温度、活载子工况、检算组合执行原生三列布局；不再接受缺少顶底参考的两列温度，或拆开车道字符串、忽略多余组合列。 |
| F06–F07 | 求解器选择和关闭振动真正下发；分析/检算必须取得明确成功状态，停止、取消、缺状态不能当作成功。 |
| F08、F10 | 模型计数、截面编号和组成员保留真实数据；失败不主动伪装成空模型。结构组含节点和单元，边界/荷载组按真实组名及原生类别分页。 |
| F09、F17 | CDB 类型化结果先转 JSON 对象再分页；21 类检算查询逐项使用真实参数，修复通用参数误传给 17 个 getter。 |
| F11、F14 | 螺纹钢筋要求六项明细；二维/三维钢束的同名覆盖反映在 destructiveHint。 |
| F12–F13 | 通过 Base64 获取 PNG 并写到 MCP 主机；九类绘图使用正确原生分量，模态使用 `mode/mode_kind`。 |
| F16、F21 | 节点纵列、影响面和移出结构组后补一次提交。 |
| F18–F19 | 检算设置明确为整体替换；活载结果新增最大/最小选择，单次只查询选定极值。 |
| F20 | 部分更新必须唯一回读目标并保留适用字段；缺项停止写入，单端改接不再静默忽略。保留板的完整后端连接。 |
| F22 | 改号两列必须成对、等长且各自唯一，范围串先展开；只有同时省略两列才全模型重排。 |
| F23 | 全删单元且要求删除孤立节点时，先读取实际单元 ID 再传 `remove_free=True`，避免 SDK 的 None 分支丢弃该标志。 |
| F24 | 快捷直线梁首支座补全局 Rx，消除共线支座剩余的刚体转动；六刚体运动约束矩阵验证满秩，实际支座仍须按工程确定。 |
| F25 | 单元类型查询只接收一个正整数或单元素列表，避免给单值 SDK 接口传范围。 |
| F27 | 64 处原有直接提交改走统一错误包装；连同本轮补齐的设置/提交路径，共 67 处调用统一包装。提交失败提示此前写入可能已生效、先回读/检查撤销记录，不重放写命令。 |

最初对主分析结果分页的 F09 怀疑未获证实：SDK 的 `send_dict` 已返回 JSON 数据。
该项已从 `get_analysis_results` 撤下；F09 仅保留已复现的 CDB 类型化结果序列化问题。

## 兼容性验证

Python 3.11.15、uv 0.11.6、MCP 1.29.0。完整测试均显式排除
`tests/test_end_to_end.py`；SDK HTTP 出口被拦截，不访问实际桥通。
各版本的 wheel SHA256、XML 文件路径、跳过原因和耗时见验证 JSON。

| qtmodel | 完整离线测试通过 | 跳过 | 最后定向检查通过 / 跳过 |
| --- | ---: | ---: | ---: |
| PyPI 2.6.3 | 1801 | 147 | 248 / 18 |
| PyPI 2.6.4 | 1803 | 145 | 248 / 18 |
| PyPI 2.8.2 | 1803 | 145 | 248 / 18 |
| PyPI 2.9.1 | 1859 | 89 | 260 / 6 |
| PyPI 2.9.2 | 1924 | 24 | 264 / 2 |
| PyPI 2.9.3 | 1948 | 0 | 266 / 0 |
| 上游 `0687ffe` | 1924 | 24 | 264 / 2 |

最后定向检查覆盖说明/全局指引调整、新增规划车道拒绝测试，以及显式零/极小合并容差
不被放大的边界修正；与完整测试重叠，不能把数字相加。各版本使用独立临时目录，均无警告。

旧 SDK 缺少横向/国际活载、模型快照、原生分页等能力，相关测试按能力跳过或验证明确拒绝。
2.6.3 缺少 `get_load_group_names`，快捷桥梁工作流在写入前报错。
2.9.2/上游的 24 个跳过项是 2.9.3 新增 `api_contract` 拒绝清单对应的测试。

Ruff、Mypy（现有渐进式类型检查，26 个源码模块）和 `git diff --check` 通过。
已安装 SDK 的 71 个文件及上游 73 个文件与审计开始时哈希一致，上游工作区干净。

## 本地构建与 MCP 协议

本轮新包在 `dist/qtmodel-audit-20261014/packages/`，不复用早先 Glama 候选产物。
`scripts/check_release.py` 已验证 wheel/sdist 中 26 个源码模块与当前工作区一致。
`scripts/check_mcp_package.py` 使用 `http://localhost:1/pythonForQt/` 完成真实 stdio 检查：

| 项目 | 结果 |
| --- | ---: |
| 注册工具 | 153 |
| 有描述的顶层参数 | 601 |
| 输出 schema / 图片工具 | 151 / 2 |
| 资源 / 提示模板 | 7 / 5 |
| 结构化响应及非法输入错误通道 | 通过 |

这些包沿用工作区 `0.5.1` 元数据，仅用于此次本地验证，不能冒充已发布产物。
验证 JSON 保存各包 SHA256；发布审计修正前须分配新版本号。
GitHub 查询确认已发布版本为 [v0.5.1](https://github.com/SorataYang/qiao-mcp/releases/tag/v0.5.1)，
时间 `2026-10-13T07:39:50Z`。本轮改动列在 CHANGELOG 的 Unreleased。

## 保留的 SDK 与工程限制

| 编号 | 限制 |
| --- | --- |
| L01 | 四标量截面其余特性补零，不能视为完整真实工程特性。 |
| L02 | 重力设置的 SDK 接口同时下发其他工程默认字段，缺少无损回写证据。 |
| L03–L04 | 屈曲/分析设置为整组替换，未暴露项用 SDK 默认值。 |
| L05 | 部分检算字段单位需要目标 UI 或可靠导出确认，保持原生值透传。 |
| L06 | 2.9.3 的 `core/api_contract.py` 明确禁止 17 个历史路由。直接影响六个检算快照工具和规划车道 add/update；保留 `API_NOT_OPEN` 错误，已验证不会继续连接或提交。 |
| L07 | SDK 的 Element 构造器会给缺失的板类型/索初始字段等补默认值，适配层不能还原补值前的缺失状态。 |
| L08 | SDK 的 `ModelDataObject.from_dicts/from_json` 会把 None/空串折叠成空列表；适配层无法在这种情况下区分合法空集合与缺失响应。 |

历史真桥通 26.1.116.1010 的 `clear_existing`、检算快照路由及 Rz 返回问题没有在本轮解除。
本轮未实测结构求解、支承反力、温度应力或规范检算数值，也没有取得 Glama 新评分。
后续工程验证仍需专用测试模型和支持所需路由的桥通构建。

## 复查入口

```sh
uv run --locked ruff check src/ tests/ scripts/
uv run --locked mypy src/qiao_mcp/
uv run --locked pytest tests/ --ignore=tests/test_end_to_end.py -q
PYTHONPATH=reference_codes/qtmodel-release/packages/qtmodel/src:src \
  uv run --locked pytest tests/ --ignore=tests/test_end_to_end.py -q
uv build --out-dir dist/qtmodel-audit-20261014/packages
uv run --locked python scripts/check_release.py dist/qtmodel-audit-20261014/packages
uv run --locked python scripts/check_mcp_package.py \
  dist/qtmodel-audit-20261014/packages/qiao_mcp-0.5.1-py3-none-any.whl
```

原始 SDK wheel、XML、协议目录和辅助脚本位于忽略目录 `dist/qtmodel-audit-20261014/`。
跨机器复查需按验证 JSON 下载对应 wheel 并重新执行；受版本控制的 JSON 保留摘要和哈希。
