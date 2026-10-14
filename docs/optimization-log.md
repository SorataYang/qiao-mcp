# MCP 优化记录

目标：通过官方 TDQS API 对实际 MCP 工具目录持续复评，达到综合分至少 4.5、
区分度至少 4。每轮从上一份完整报告确定改进范围，独立改动分别提交；出现可验证的
指标改善时递增补丁版本。分支为 `optimize/mcp-tools`。

评估保留完整的 153 个工具。报告依据构建 wheel 的真实 stdio `tools/list`，
工具定义同时用于协议检查；不是另行维护的评分专用文本。API 密钥不写入仓库。
托管模型未公开，未修改的工具及工具集维度也可能波动，故同时记录升降与具体改动。

| 轮次 | 本地版本 | 综合分 | 描述质量 | 工具集一致性 | 区分度 | 最低分 | 报告 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 基线 | 0.5.1 后的审计版 | 3.7 | 3.8 | 3.3 | 3 | 3.0 | [基线](https://tdqs.dev/reports/x2109gtuk4) |
| 1 | 0.5.2 | 3.6 | 3.9 | 3.0 | 3 | 3.3 | [第 1 轮](https://tdqs.dev/reports/t0kcd799y0) |
| 2 | 0.5.3 | 3.7 | 4 | 3 | 3 | 3.4 | [第 2 轮](https://tdqs.dev/reports/s3dfew1edh) |
| 3 | 0.5.4 | 4 | 4.2 | 3.5 | 4 | 3.8 | [第 3 轮](https://tdqs.dev/reports/pm14kyk2jr) |
| 4 | 0.5.5 | 4.1 | 4.4 | 3.3 | 3 | 4.2 | [第 4 轮](https://tdqs.dev/reports/ebsqf06gtb) |

## 第 1 轮：最低分工具的使用边界

评分源码提交：`0b6e5b103d315fdaa67a03866b38186968aada34`。
输入 SHA-256：`cfc73ae6d380c3b2bea96a12aaa11dd4795e8a5748a5d01eea8200688b6de335`。
原始产物位于本地 `dist/optimization-20261014/round-01/`。

| 工具 | 修改前 | 修改后 | 改进内容 |
| --- | --- | --- | --- |
| `create_tapered_section` | 3.0 | 4.6 | 端截面前提、真实编号回读、后续赋值和变化规律的边界 |
| `remove_section` | 3.2 | 4.6 | 显式选择、引用检查、自动清理与指定删除的区别 |
| `remove_construction_stage` | 3.2 | 4.6 | 空名称删除全部、删除阶段与钝化组/切换视图的区别 |
| `update_vertical_steel_tendon` | 3.2 | 4.8 | 完整设置覆盖、单肢面积、单位换算和检算流程 |

描述质量上升 0.1，最低分上升 0.3；命名一致性从 4 降至 3，使综合分暂时下降 0.1。
本轮没有改动工具名称，不能将命名分变化当作已证明的命名回归。版本递增依据四个
实际改动工具的明确改善及描述质量提升，未将本轮记为综合分提升。

验证：Ruff 通过；Mypy 通过（项目现有渐进式类型检查范围）；相关测试 128 项通过；
完整离线测试 1926 项通过、26 项跳过；wheel 协议检查保留 153 个工具、601 个有说明
的参数、151 个输出 Schema、7 个资源和 5 个提示模板。工程软件实测不在本次定义优化中。

下一轮依据新报告处理剩余 3.3–3.5 分工具，完善清理、荷载、分组、检算和视图工具的
使用范围与执行影响，并继续核对工具集评价中的误判。

## 第 2 轮：常用工具的操作范围与工程语义

本地版本：0.5.3。评分源码提交：`990428495a4c6a1277dca6b881fa5cdeb97038f7`。
输入 SHA-256：`b6bfcabb6fb4669db771170ed0bef76e17a18edd11abadaa2b0c214c8e5457da`。
原始产物：`dist/optimization-20261014/round-02/`。本轮修改 20 个工具。

本轮 20 个改动工具全部提高。综合分从 3.6 升至 3.7，描述质量从 3.9 升至 4.0，平均分从 4.3 升至 4.4。工具集指标保持区分度 3、命名一致性 3、数量适宜性 2、完整性 4；仍未达到收尾目标。施工阶段钝化现有明确专用工具，报告继续称其只能通过通用入口实现，该评价与本次工具定义不符。按报告原值保留，不将误判当作新增工具的需求。SDK 文档与现安装版本均确认参数化配筋直径使用米、第四列在本工具为间距，既有配筋会覆盖；相应说明与标记已经修正。

| 工具 | 上轮 | 本轮 |
| --- | --- | --- |
| `update_section_bias` | 3.4 | 4.5 |
| `set_support` | 3.4 | 4.6 |
| `apply_beam_distributed_load` | 3.4 | 4.5 |
| `add_load_to_mass` | 3.5 | 4.7 |
| `configure_analysis` | 3.5 | 4.9 |
| `create_structure_group` | 3.5 | 4.9 |
| `update_structure_group_name` | 3.5 | 4.3 |
| `create_boundary_group` | 3.4 | 4.3 |
| `merge_operation_stage` | 3.4 | 4.7 |
| `update_construction_stage` | 4.1 | 4.9 |
| `add_tendon_3d` | 3.4 | 4.5 |
| `remove_boundary` | 3.4 | 4.5 |
| `set_view_angle` | 3.4 | 4.7 |
| `setup_concrete_check` | 3.4 | 4.7 |
| `add_check_load_combination` | 3.4 | 4.5 |
| `add_parametric_reinforcement` | 3.4 | 4.5 |
| `add_check_stirrup` | 3.4 | 4.6 |
| `assign_element_stirrup` | 3.4 | 4.5 |
| `manage_check_case_file` | 3.4 | 4.8 |
| `remove_unused_sections` | 3.3 | 4.6 |

验证：完整离线测试 1926 项通过、26 项跳过；构建 wheel 的协议检查保持 153 个工具。

下一轮方向：处理本轮剩余 3.4–4.1 分工具，优先直线节点创建、截图、显示编号和模型检查；同步核对服务器整体评估实际使用的输入，定位区分度持续停滞的原因。

## 第 3 轮：几何创建、只读查询与图像行为

本地版本：0.5.4。评分源码提交：`d174045b400b5e89ab871475a345409656f9b0cf`。
输入 SHA-256：`122c0fa0e7aae05a59865ffd2d651b5198cf176e40f340387ec6b9f066e835a0`。
原始产物：`dist/optimization-20261014/round-03/`。本轮修改 20 个工具。

本轮 20 个改动工具全部提高。综合分从 3.7 升至 4.0，描述质量从 4.0 升至 4.2，单工具最低分从 3.4 升至 3.8；区分度从 3 升至 4，已满足该项收尾标准。命名一致性为 4，数量适宜性仍为 2，完整性为 4。官方参考实现的整体评估包含全部工具名称和说明，没有发现截断工具目录的代码；数量维度有明确的工具数锚点。当前仍保持全部 153 个公开工具，下一轮优先提高新的最低分项。

| 工具 | 上轮 | 本轮 |
| --- | --- | --- |
| `create_nodes_linear` | 3.4 | 4.8 |
| `create_beam_element` | 4 | 4.7 |
| `create_elements` | 3.9 | 4.3 |
| `create_load_group` | 3.8 | 4.3 |
| `add_thickness` | 3.7 | 4.5 |
| `update_section_property` | 4.1 | 4.8 |
| `validate_model` | 3.5 | 4.6 |
| `remove_structure_group` | 3.8 | 4.8 |
| `list_group_members` | 4.1 | 4.6 |
| `create_tendon_property` | 3.6 | 4.5 |
| `get_tendon_length_result` | 3.6 | 4.7 |
| `add_elastic_link` | 4.1 | 4.6 |
| `add_master_slave_link` | 3.9 | 4.5 |
| `save_model_screenshot` | 3.4 | 4.5 |
| `plot_analysis_result` | 4.4 | 4.5 |
| `display_ids` | 3.5 | 4.3 |
| `add_influence_plane` | 4 | 4.5 |
| `add_traffic_lane` | 4 | 4.6 |
| `add_standard_vehicle` | 3.7 | 4.6 |
| `find_entities` | 4 | 4.6 |

验证：完整离线测试 1926 项通过、26 项跳过；构建 wheel 的协议检查保持 153 个工具。

下一轮方向：优先完善模型概要、二维钢束、约束方程和混凝土检算执行说明，继续向综合分 4.5 推进。

## 第 4 轮：执行语义、模型概况与交通查询

本地版本：0.5.5。评分源码提交：`d719d6973e9c0e22a62b45abdfa4e05329a3b941`。
输入 SHA-256：`a8e6cd738763e724787475ee8be82026d394e60c8ead2d26771399d9df3a94b5`。
原始产物：`dist/optimization-20261014/round-04/`。本轮修改 9 个工具。

本轮 9 个改动工具全部提高。综合分从 4.0 升至 4.1，描述质量从 4.2 升至 4.4，平均分从 4.5 升至 4.6，最低分从 3.8 升至 4.2。区分度从 4 回落到 3，工具集一致性从 3.5 降至 3.3；命名一致性 4、数量适宜性 2、完整性 4。本轮未改变工具名称和入口数量，保留这一波动，不将上一轮区分度达标视为持续保证。新的整体报告再次指出分组入口重叠以及分配面荷载模板缺少专用创建入口；前者需要考虑接口组织，后者已核对上游方法和 Windows 导出样例。

| 工具 | 上轮 | 本轮 |
| --- | --- | --- |
| `get_model_info` | 3.8 | 4.9 |
| `create_tendon_2d` | 3.9 | 4.6 |
| `add_constraint_equation` | 4 | 4.6 |
| `set_render` | 4.2 | 4.7 |
| `set_unit` | 4.2 | 4.3 |
| `get_live_load_results` | 4.2 | 4.4 |
| `get_transversal_data` | 4.2 | 4.6 |
| `run_concrete_check` | 3.9 | 4.8 |
| `merge_nodes` | 4.2 | 4.6 |

验证：完整离线测试 1926 项通过、26 项跳过；构建 wheel 的协议检查保持 153 个工具。

下一轮方向：先处理节点创建、荷载工况、活载节点纵列、箍筋修改四个最低分工具，补强更新与结果查询的调用语义；结合入口重叠反馈继续改进实际工具目录。
