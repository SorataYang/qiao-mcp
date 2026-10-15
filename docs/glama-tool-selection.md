# 相近工具的选择依据

最初整理于 2026-10-12，2026-10-14 按本地逐工具代码审计更新。保留 153 个工具；这是源码和 SDK 契约的人工审查，
不是模型选型成功率测试。先用 `get_model_status` 检查可用操作，写入后需要结果时显式求解。
下面的场景只描述选型，没有对真实工程执行。

## 场景与入口

| 场景 | 推荐入口 | 相邻入口的边界与证据 |
| --- | --- | --- |
| 把节点和单元一起加入已有结构组 | `add_to_structure_group(group_name, node_ids, element_ids)` | 通用成员操作；`add_elements_to_group` 只暴露单元。两者最终都调用 provider 的组增员接口。 |
| 只把一批单元加入已有组 | `add_elements_to_group(group_name, element_ids)` | 便捷入口，通用工具只传 element_ids 也可；不新建模型实体。 |
| 从组移除单元，但保留组及单元 | `remove_from_structure_group` | `remove_structure_group` 删除组；`remove_elements` 删除模型实体，三者副作用不同。 |
| 只把节点 7 改号为 17 | `update_node_id(7, 17)` | 不查询坐标；`update_node` 在省略部分坐标时才回读补齐。完成后回读编号及引用。 |
| 把节点 7 的绝对 Z 改为 -1.5 | `update_node(7, z=-1.5)` | `move_nodes` 是相对位移；重试会再次累加偏移。 |
| 平移整段节点 | `move_nodes(ids, offset_z=...)` | 显式选择节点；不会改号。原坐标和既有荷载需复核后重新分析。 |
| 批量按位置映射改号 | `renumber_nodes(ids=[7,9], new_ids=[17,19])` | 两列须成对等长且各自唯一；仅两列同时省略才全模型重排，单列省略拒绝。只改一个可用单点入口。 |
| 按“悬臂施工2”查看建模阶段 | `switch_display_stage(stage_name="悬臂施工2")` | 调用 MDB 建模显示，参数为名称；不计算结果。 |
| 在后处理窗口查看阶段 2 | `change_construct_stage(stage=2)` | 调用 ODB 显示，参数为编号；0 是基本模型。两者都走 view 守卫，能否显示由桥通当前状态决定；结果读取另走 result_read 守卫。 |
| 未建截面，试算候选多边形或线宽几何 | `calc_section_property` | 二选一传 loop_segments/sec_lines；返回消息中的计算值，不创建截面。 |
| 读取截面 5 的既有特性 | `get_model_data(kind="section_property", sec_id=5)` | 只读存储值，不重算；与 `calculate_section_property` 的模型写权限不同。 |
| 全模型已有截面需要重算并保存特性 | `calculate_section_property` | 没有单截面选择参数；重写所有截面。`calc_section_property` 只是候选几何试算。 |
| 一次改一个单元的材料和截面 | `update_element(old_id=7, mat_id=2, sec_id=3)` | 先回读补齐记录中已有字段；旧响应缺失字段仍可能取 SDK 默认值。两端节点必须成对给，单给一个不改连接。 |
| 批量只改材料、截面或贝塔角 | `update_element_material/section/beta` | 专用批量写接口，不重建整条单元记录；section 仅适用于杆系单元。 |
| 改杆系单元两端连接或只改编号 | `update_element_nodes` / `update_element_id` | 专用单属性入口。板四节点改接通过已发现的 `mdb.update_element_node` 网关；不推断索无应力长度会自动重算。 |
| 反转 I/J 与绕杆轴旋转局部 Y/Z | `revert_local_orientation` / `update_element_beta` | 前者反转杆系方向，后者设绝对贝塔角；不能据此假定每个内力分量都变号。 |
| 分析前核对钢束定义 | `get_tendon_info(tendon_name="T1")` | 查询保存的原生定义并包装为消息；不承诺提供阶段损失。 |
| 查询阶段 2 的钢束应力/损失分布 | `get_tendon_loss_results(name="T1", stage_id=2)` | SDK 要求阶段已激活钢束且有结果；消息内是带 effective_s 等字段的原生表。 |
| 核对离散后的钢束全局坐标 | `get_tendon_position_result(name="T1")` | 按钢束走向返回原生坐标表，当前长度单位；SDK 未明确分析前可用性，空数据不能单独判定钢束不存在。 |
| 指定单元整个截面一个均匀温度 | `add_system_temperature` | 实际调 `mdb.add_element_temperature`，SDK 称“最终温度”；不自动把 ΔT 换算为终温。 |
| 给梁/板输入线性温差 | `add_gradient_temperature` | 梁截面方向 0=Y、1=Z；与自定义温度的方向编号不同。 |
| 按规范给 t1–t4/thick | `add_beam_section_temperature` | code_index 1/2、sec_type 1/2 有 SDK 依据；完整温度剖面和单位需对照相应规范 UI/export。 |
| 输入实测分段温度点 | `add_custom_temperature` | 三列 `[参考位置1顶/2底, 高度, 温度]`；orientation 1=局部Z、2=局部Y。缺少参考位置的两列输入会被拒绝。 |
| 对索/杆输入初始轴力控制 | `add_initial_tension_load` | tension_type 0增量/1全量；application_type 1体外/2体内/3转索长。物理量不是钢束损失结果。 |
| 对索输入无应力长度控制 | `add_cable_length_load` | 输入 length 和0增量/1全量；不把长度换算成张拉力。两类索荷载原生单位均须核验。 |
| 对命名钢束施加预应力 | `apply_prestress` | 前置钢束特性、几何和工况；张拉端0始/1末/2两端。不是索单元初始力；返回原生值确认，不臆造 kN 换算。 |
| 直接给指定板单元施加力/矩 | `add_plate_element_load` | 指定作用位置、类型和方向；无需先定义分配面荷载图式。 |
| 将已有面荷载图式放到三点定义的平面 | `add_distribute_plane_load` | 先通过网关创建图式；本工具引用图式并放置。plate_ids 省略选全部板，coord_system 的代码解释待桥通证据，不能借用板荷载枚举。 |

## 源码证据

- 组成员、阶段名称显示：[group_management.py](../src/qiao_mcp/tools/group_management.py)；通用成员、节点和单元修改：[modifications.py](../src/qiao_mcp/tools/modifications.py)。
- 候选截面试算和既有截面读取：[queries.py](../src/qiao_mcp/tools/queries.py)；全模型截面计算、温度与索/板荷载：[tools/__init__.py](../src/qiao_mcp/tools/__init__.py)。
- 定义与阶段损失/坐标：[tendon.py](../src/qiao_mcp/tools/tendon.py)；阶段编号视图：[visualization.py](../src/qiao_mcp/tools/visualization.py)。
- 实际 MDB/ODB 分发、读回合并：[qtmodel_provider.py](../src/qiao_mcp/providers/qtmodel_provider.py)；权限分类和返回包装：[envelope.py](../src/qiao_mcp/tools/envelope.py)。
- 具体 SDK 文件摘要、哈希与未决项见 [39 项审计](glama-improvement-audit.md) 和对应 JSON。命令探针 mock 了 `QtServer.send_dict`，只证明发出的载荷，不证明桥通执行语义。

## 历史名称

`tapper` 表示 tapered section（变截面）；`bulking` 表示 buckling（屈曲）；保留历史调用名。
`calc_section_property` 是几何试算，`calculate_section_property` 是全模型重算。
Glama 评语中的 `calculate_ection_property` 是评语拼写错误，不是缺失的 MCP API。

## 目录取舍

| 分类 | 入口 | 本轮决定及后续条件 |
| --- | --- | --- |
| 完全重复 | 本轮未确认可无损删除的入口 | 须同时比较目标、输入域、副作用和调用成本；相似名称或 TDQS shadow-candidate 不构成证据。 |
| 便利封装 | `add_elements_to_group` 相对 `add_to_structure_group` | 单元子集等价，但输入域更窄，保留兼容。未来统一入口需先给迁移路径。 |
| 便利封装 | 单实体综合修改与 `update_*_id/material/section/beta/nodes` | 保留。专用入口支持不同批量范围、部分接口少一次读回；不能只按名称合并。 |
| 便利封装 | `create_nodes_linear`、`create_beam_elements_linear`、两种桥梁模板 | 保留。模板/批量减少客户端调用，但前置、支承和部分写失败行为不同。 |
| 领域必需 | 三种截面特性入口、两种阶段显示、钢束定义/损失/坐标 | 读写范围、输入对象、桥通模块和前置条件不同；保留并强化选型。 |
| 领域必需 | 温度四类、索力/索长/钢束预应力、板荷载/分配图式 | 物理输入不同；不做有损的参数合并。 |
| 领域必需 | MDB 模型完整快照与旧 CDB/CSAN 检算入口 | 模型枚举、单位、身份与当前检算状态不同；不能用旧查询拼凑无损快照。 |
| 待确认 | 原生单位、重复定义、插值、自动引用/荷载迁移 | 已在工具说明披露；需专用测试工程或可信 C# 导出补证，不以猜测换取评分。 |
| 后续设计 | 按真实工作流选择目录组 | 若 G6 仍因数量扣分，再设计建模/修改/施工/结果/检算的可选工具组，评估客户端发现和兼容迁移；本轮不创建评分专用 profile。 |

本轮数量仍是 153。注册层仅移除已完整注入 input schema 的重复 Args；该优化减少文本，
没有删工具，也不能证明“工具数量适当性”或线上评级已提升。
