# TDQS 离线提醒处置

规范 1.2，tdqs 0.1.0。严格 `--fail-on warning` 退出码 **1**：0 error、39 warning、2 info。
不是严格检查全绿，也不产生线上评分。没有停用规则、降低阈值或删除兼容工具。
原始报告位于本地候选目录的 `tdqs-lint.json`，哈希和原始 findings 保存在[JSON 处置表](glama-tdqs-review.json)。
39 条 warning 均为调用成本预筛选的 shadow-candidate，逐对核对实际目的/对象/副作用如下；这是人工源码审查，不是模型语义评分。

| 工具 → 成本更低的候选 | 调用成本 | 处置理由 |
| --- | --- | --- |
| `create_beam_element` → `activate_structure` | 4 → 0 | 创建梁单元改变模型拓扑；activate_structure 只过滤显示。 保留两者。 |
| `create_section_from_properties` → `add_beam_constraint` | 5 → 1 | 创建/覆盖截面特性定义；add_beam_constraint 设置梁端释放，不提供截面。 保留两者。 |
| `add_effective_width` → `add_distribute_plane_load` | 7 → 3 | 修改边界组中的刚度/形心系数；add_distribute_plane_load 放置面荷载图式。 保留两者。 |
| `remove_section` → `add_beam_constraint` | 5 → 1 | 删除截面定义；add_beam_constraint 增加梁端约束，不能代替删除。 保留两者。 |
| `set_support` → `add_beam_constraint` | 5 → 1 | 约束节点自由度；add_beam_constraint 释放梁端与节点的连接，作用对象不同。 保留两者。 |
| `apply_nodal_force` → `add_check_stirrup` | 6 → 2 | 在节点加集中力/矩；add_check_stirrup 定义检算箍筋。 保留两者。 |
| `apply_beam_distributed_load` → `add_check_stirrup` | 6 → 2 | 沿梁分布力/矩；add_check_stirrup 是配筋定义，不是外荷载。 保留两者。 |
| `add_system_temperature` → `add_distribute_plane_load` | 7 → 3 | 指定单元均匀温度；add_distribute_plane_load 是既有面荷载图式的空间放置。 保留两者。 |
| `add_gradient_temperature` → `add_distribute_plane_load` | 7 → 3 | 截面线性温差；add_distribute_plane_load 不是温度剖面。 保留两者。 |
| `add_custom_temperature` → `add_check_stirrup` | 6 → 2 | 梁截面温度点表；add_check_stirrup 是钢筋几何/材料定义。 保留两者。 |
| `add_beam_section_temperature` → `add_check_stirrup` | 6 → 2 | 规范温度剖面；add_check_stirrup 不生成温度荷载。 保留两者。 |
| `add_initial_tension_load` → `add_check_stirrup` | 6 → 2 | 索/杆初始轴力荷载；add_check_stirrup 不提供张拉控制。 保留两者。 |
| `add_cable_length_load` → `add_check_stirrup` | 6 → 2 | 索无应力长度荷载；add_check_stirrup 不修改索长。 保留两者。 |
| `add_plate_element_load` → `add_check_stirrup` | 6 → 2 | 板单元外荷载；add_check_stirrup 是检算箍筋属性。 保留两者。 |
| `add_support_settlement` → `add_distribute_plane_load` | 7 → 3 | 节点强制位移；add_distribute_plane_load 是面荷载，不是位移边界。 保留两者。 |
| `add_nodal_mass` → `add_beam_constraint` | 5 → 1 | 节点惯性质量；add_beam_constraint 是梁端自由度释放，不生成质量。 保留两者。 |
| `add_elements_to_group` → `activate_structure` | 4 → 0 | 持久修改结构组成员；activate_structure 只影响显示过滤。真正便利关系是 add_to_structure_group。 保留两者。 |
| `create_tendon_2d` → `activate_structure` | 4 → 0 | 新增钢束几何；activate_structure 不创建钢束或模型实体。 保留两者。 |
| `apply_prestress` → `add_beam_constraint` | 5 → 1 | 对命名钢束加预应力；add_beam_constraint 设置梁端释放。 保留两者。 |
| `add_tendon_3d` → `activate_structure` | 4 → 0 | 新增空间钢束；activate_structure 只控制可见性。 保留两者。 |
| `assign_tendon_elements` → `add_beam_constraint` | 5 → 1 | 声明全模型预应力单元集合；add_beam_constraint 设置梁端自由度，不声明钢束宿主。 保留两者。 |
| `add_master_slave_link` → `activate_structure` | 4 → 0 | 建立节点自由度从属关系；activate_structure 是可见性过滤。 保留两者。 |
| `add_elastic_support` → `add_elements_to_group` | 8 → 4 | 弹簧支承及刚度；add_elements_to_group 只增加结构组成员。 保留两者。 |
| `configure_operation_stage` → `add_beam_constraint` | 5 → 1 | 完整替换运营阶段工况选择；add_beam_constraint 不配置求解工况。 保留两者。 |
| `add_node_tandem` → `activate_structure` | 4 → 0 | 定义用于车道/影响面的有序节点纵列；activate_structure 不创建纵列。 保留两者。 |
| `create_live_load_case` → `activate_structure` | 4 → 0 | 定义移动荷载工况；activate_structure 不生成工况或结果。 保留两者。 |
| `set_transversal_vehicle` → `add_elastic_support` | 16 → 8 | 完整横向车辆轴载/几何；add_elastic_support 设置支承刚度。 保留两者。 |
| `set_transversal_lane` → `add_distribute_plane_load` | 7 → 3 | 定义有序梁链车道与分配宽度；add_distribute_plane_load 将面荷载图式放置到平面。 保留两者。 |
| `set_transversal_case` → `add_nodal_mass` | 11 → 5 | 组合横向车/道引用和折减系数；add_nodal_mass 给节点惯性质量。 保留两者。 |
| `remove_transversal_data` → `add_check_stirrup` | 6 → 2 | 按明确身份删除横向对象并处理引用；add_check_stirrup 新增箍筋定义。 保留两者。 |
| `set_international_vehicle` → `add_elastic_support` | 18 → 8 | 按规范定义完整车辆；add_elastic_support 不表示车轴或车辆标准。 保留两者。 |
| `create_en1991_vehicle` → `add_distribute_plane_load` | 7 → 3 | 欧规原生车辆工厂；add_distribute_plane_load 不生成列车/车轴。 保留两者。 |
| `set_planned_lane` → `add_nodal_mass` | 11 → 5 | 完整规划车道和线位选择；add_nodal_mass 不表示行车路线。 保留两者。 |
| `set_international_live_load_case` → `add_beam_section_temperature` | 12 → 6 | 国际车辆/车道子工况与因子；add_beam_section_temperature 是规范温度荷载。 保留两者。 |
| `manage_check_material` → `add_elastic_support` | 17 → 8 | 设置/恢复模型检算材料覆盖；add_elastic_support 不修改材料。 保留两者。 |
| `manage_check_case_definition` → `add_elastic_support` | 20 → 8 | 完整模型检算工况快照或删除；add_elastic_support 是边界支承。 保留两者。 |
| `set_check_stirrup_snapshot` → `add_beam_section_temperature` | 12 → 6 | 完整模型箍筋快照，可显式改号并迁移引用；add_beam_section_temperature 是温度荷载。 保留两者。 |
| `set_section_reinforcement` → `add_elastic_support` | 16 → 8 | 完整截面配筋及实际钢筋点；add_elastic_support 是节点弹簧。 保留两者。 |
| `query_model_data` → `add_effective_width` | 15 → 7 | 只读服务端筛选/分页；add_effective_width 写入模型边界系数，读写权限也不同。 保留两者。 |

两条 info 来自 save_model_screenshot / plot_analysis_result 无 JSON outputSchema；它们保留 MCP Image 返回，已有图片协议测试覆盖，不伪造 JSON 结果。
若 G6 的实际语义评分仍发现重复，再按[目录取舍](glama-tool-selection.md)审查真实工作流及兼容迁移。当前未找到已配置且校准的语义评分器；不调用付费模型、不虚构 A 或选型成功率。
