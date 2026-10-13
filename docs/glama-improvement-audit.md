# Glama 工具质量审计

2026-10-12，0.5.1 本地候选。问题基线是 Glama 0.3.1 的 **B 3.3**，不是本候选的评分。
39 个旧 B/C 工具逐项记录于[完整 JSON](glama-improvement-audit.json)，含旧扣分原文、源码行号、provider 分发、SDK 签名/说明和文件哈希。
34 个对象在 0.5.0 已改过说明；本轮核验事实并保留有效内容。SDK 说明与 mock 命令只能证明契约/传输，不能替代真实桥通工程实测。

## 39 项处置

| 工具（旧级别/分数） | 处置 | 剩余后端证据 |
| --- | --- | --- |
| [assign_tendon_elements](../src/qiao_mcp/tools/tendon.py#L272)（C 2.7） | 保留全模型预应力单元声明解释，补充不能当成单根钢束增量绑定；先建钢束再声明、施加载荷。 | 重复声明合并/替换需专用工程或 C# 实现证据。 |
| [activate_structure](../src/qiao_mcp/tools/visualization.py#L203)（C 2.9） | 明确只过滤显示；两类选择均空恢复全显，恢复、视角、阶段选择分别路由。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [add_beam_section_temperature](../src/qiao_mcp/tools/__init__.py#L1760)（C 2.9） | 区分四类温度、已有工况、确认消息和不求解；保留已证实的规范/截面类型编号。 | t1–t4/thick 的完整规范剖面、固定单位和重复策略需 UI/export。 |
| [add_cable_length_load](../src/qiao_mcp/tools/__init__.py#L1884)（C 2.9） | 明确无应力长度控制相对索力控制，0增量/1全量，去除无证据的固定 m 承诺。 | 长度固定单位和重复加载策略待桥通证据。 |
| [add_distribute_plane_load](../src/qiao_mcp/tools/__init__.py#L2013)（C 2.9） | 明确先建图式再施加；三点框架和缺省全部板范围；移除借用其他 API 的 coord_system 枚举。 | coord_system 原生枚举、空点默认和重用编号策略需实际导出/后端实现。 |
| [add_initial_tension_load](../src/qiao_mcp/tools/__init__.py#L1821)（C 2.9） | 保留0增量/1全量及1体外/2体内/3转索长；区分钢束预应力与索长；不返回索力结果。 | 固定力单位与重复加载规则未被 SDK 声明。 |
| [add_plate_element_load](../src/qiao_mcp/tools/__init__.py#L1936)（C 2.9） | 明确板荷载类型/位置/方向，和分配图式分开；SDK 自动 ID，返回确认，不是按 ID 更新。 | 集中/分布及力/矩的固定单位需原生导出核验。 |
| [add_system_temperature](../src/qiao_mcp/tools/__init__.py#L1604)（C 2.9） | 修正实际调用为选定单元 add_element_temperature；SDK 称最终温度，不自动把温差转终温；四类选型同步。 | 目标桥通温度约定及重复定义规则需 UI/export。 |
| [add_time_history_function](../src/qiao_mcp/tools/__init__.py#L2366)（C 2.9） | 明确波形与工况、谱函数的区别；点序/重复点原样、不排序或单位换算。 | 固定物理单位和同名处理需实际后端定义。 |
| [update_node_id](../src/qiao_mcp/tools/modifications.py#L185)（C 2.9） | 保留单点改号路由；修正综合修改仅在省略部分坐标时额外查询；明确确认非记录，完成后回读引用。 | 编号冲突和引用迁移由桥通实现，不承诺自动修复全部引用。 |
| [add_nodal_mass](../src/qiao_mcp/tools/__init__.py#L2152)（B 3） | 保留三向质量及转动惯量、2.9能力检查；去除仅自振才有效的限制，说明定义后再分析、值不换算。 | 固定质量/惯量单位及重复赋值规则需原生模型证据。 |
| [add_tapper_section_group](../src/qiao_mcp/tools/__init__.py#L1075)（B 3） | 保留变化阶数/参考端与参数化网关；区分普通结构组成员操作，注明 tapper 历史拼写。 | 同名变化组处理待桥通核验。 |
| [apply_nodal_force](../src/qiao_mcp/tools/__init__.py#L1494)（B 3） | 更正自动自重指引；保留全局六分量和集中/分布/强制位移区分；自动 ID、回读后修改，去除未证实单位换算例。 | 固定力/矩单位需已知原生荷载导出；不从显示单位推断。 |
| [switch_display_stage](../src/qiao_mcp/tools/group_management.py#L298)（B 3） | 保留按名称的 MDB 建模显示，与 ODB 按编号视图双向区分；不求解。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [update_element_nodes](../src/qiao_mcp/tools/modifications.py#L564)（B 3） | 保留杆系两节点和板四节点网关边界；移除索无应力长度自动变化的承诺，修改后核对几何/局部荷载。 | 连接变化对附属数据的自动迁移需后端证据。 |
| [add_custom_temperature](../src/qiao_mcp/tools/__init__.py#L1704)（B 3.1） | 更正 SDK 三列 [基准1顶/2底,高度,温度] 和方向1Z/2Y；输入 schema 兼容扩展；旧两列原样保留、不推断基准；None/[] 明示。 | 旧两列在具体桥通上的解释、单位、插值、空值和重复定义行为未实测。 |
| [add_spectrum_case](../src/qiao_mcp/tools/__init__.py#L2297)（B 3.1） | 保留函数/质量/自振前置和方向组合不等于SRSS/CQC；补齐与时域/普通工况选型、确认返回。 | 重名处理由桥通决定。 |
| [add_time_history_case](../src/qiao_mcp/tools/__init__.py#L2422)（B 3.1） | 保留质量→波形→工况→地震动输入流程、线性无阻尼限制及完整网关选项；补确认返回/同名限制。 | 重名处理待桥通；定义本身不触发分析。 |
| [add_time_parameter](../src/qiao_mcp/tools/__init__.py#L613)（B 3.1） | 保留规范/自定义1000、函数名+龄期和各规范长度校验；补充材料绑定经网关及确认返回。 | 同名定义处理待后端核验。 |
| [create_line_width_section](../src/qiao_mcp/tools/__init__.py#L940)（B 3.1） | 更正线段必须形成单一路径及“创建不计算特性”的旧断言；保留实际薄壁线段、初始计算交给桥通、回读与全模型重算区分。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [reset_display](../src/qiao_mcp/tools/visualization.py#L264)（B 3.1） | 明确取消显示过滤且不改模型；补充视角、渲染、阶段选型及确认返回。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [revert_local_orientation](../src/qiao_mcp/tools/modifications.py#L433)（B 3.1） | 保留反转杆系方向与贝塔角旋转边界；移除全部结果符号翻转/简单双调恢复全部状态的承诺。 | 局部荷载转换和结果符号需专用模型前后对照。 |
| [update_bulking_setting](../src/qiao_mcp/tools/__init__.py#L2488)（B 3.1） | 保留历史名及最后阶段语义；区分全局分析开关/阶段内容；披露未暴露字段使用 SDK 默认值，不回读合并。 | constant_cases/variable_cases=None 对已有桥通设置的处理须验证，当前不保证保留。 |
| [add_effective_width](../src/qiao_mcp/tools/__init__.py#L1189)（B 3.2） | 保留边界组激活和 Iy/形心作用；修正“SDK 所有扩展参数说明相同”的过期说法，当前2.9.2已明确 Iz/局部y/轴向面积。 | 形心偏移单位、重复边界定义规则需桥通证据。 |
| [get_tendon_loss_results](../src/qiao_mcp/tools/tendon.py#L312)（B 3.2） | 保留已激活且已求解阶段、应力字段及工程单位；修正返回为消息内原生列表，与保存定义区分。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [update_element_id](../src/qiao_mcp/tools/modifications.py#L378)（B 3.2） | 保留单个改号与综合属性修改/批量改号的选择；将 update/renumber 元数据标记为可覆盖。 | 碰撞与引用更新仍需桥通校验；不得依赖缓存 ID。 |
| [add_construction_stage](../src/qiao_mcp/tools/__init__.py#L2546)（B 3.3） | 保留激活范围/阶段累积与网关钝化路径；更正前置为 create_load_group；空激活列表省略、返回请求名。 | 重名处理由桥通决定；工具不承诺回滚。 |
| [add_gradient_temperature](../src/qiao_mcp/tools/__init__.py#L1653)（B 3.3） | 保留线性温差及0Y/1Z、1梁/2板；同步均匀终温与三列自定义温度选型，返回确认不求解。 | 固定温度单位、梯度正负和重复定义组合/替换需目标桥通核验。 |
| [add_load_combine](../src/qiao_mcp/tools/__init__.py#L487)（B 3.3） | 保留模型组合与当前检算组合区分、已存在引用、自动覆盖和原生 [type,name,factor] 顺序。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [apply_prestress](../src/qiao_mcp/tools/tendon.py#L139)（B 3.3） | 保留钢束/工况前置与索力/索长选型；输入仍原样传递，确认消息不再做未经证实的 kN 换算。 | force 原生固定单位和重名/重复叠加策略需后端/导出；不改变实际写入。 |
| [create_polygon_section](../src/qiao_mcp/tools/__init__.py#L894)（B 3.3） | 保留几何试算/标准截面/线宽区分、自动闭合、点数/面积验证及拓扑由用户核验；补齐可覆盖 annotation。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [save_model_file](../src/qiao_mcp/tools/modifications.py#L53)（B 3.3） | 保留桥通主机路径、覆盖/无备份/无下载、空路径当前文件；明确返回仅确认且不独立验证远程文件。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [add_creep_function](../src/qiao_mcp/tools/__init__.py#L715)（B 3.4） | 补自定义曲线与规范材料、收缩函数的选择；引用名+加载龄期；保留点序和重复值、不自动赋材/求解。 | 缩放含义、重名和插值行为需原生导出/后端实现。 |
| [add_support_settlement](../src/qiao_mcp/tools/__init__.py#L2095)（B 3.4） | 补沉降与约束/集中力区分、六分量原样、自动ID和既有工况前置；给出回读荷载路径。 | SDK 未明示固定平动/转角单位，需桥通核验，不能直接承诺 m/rad。 |
| [create_continuous_beam_bridge](../src/qiao_mcp/tools/workflows.py#L241)（B 3.4） | 保留已有截面/材料、实际编号回读、复用节点/追加单元、支承范围及失败可能部分写入的说明。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [create_material](../src/qiao_mcp/tools/__init__.py#L547)（B 3.4） | 补齐数据库/自定义/组合选择；SDK 同名覆盖、返回名非 ID、回读后赋值；creep_id/composite_info 通过网关。 | 本项当前契约有源码/SDK依据；仍不代表工程验收。 |
| [get_tendon_position_result](../src/qiao_mcp/tools/tendon.py#L355)（B 3.4） | 补保存定义/损失/离散坐标区分，结果守卫、不求解、原生表在消息中及两种点形状。 | SDK 未明确分析前可用性；空数据不足以区分无名称与无可用几何。 |
| [renumber_nodes](../src/qiao_mcp/tools/modifications.py#L221)（B 3.4） | 补单点/绝对坐标/位移边界；任一 None 为全模型，局部两列成对；回读后再用 ID。 | 冲突和引用更新由桥通处理，不承诺自动预检/映射返回。 |
| [set_gravity](../src/qiao_mcp/tools/__init__.py#L1463)（B 3.4） | 补自重阶段路由和不求解；SDK 同时发送工程信息空值、温度0，本工具不回读合并；标为可覆盖。 | 仅证明默认值被发出，未证明桥通会清空原字段；需要总体设置前后完整导出。 |

## 新增 21 项：不沿用不存在的旧评分

| 工具 | 本轮审查 | 限制与后续 |
| --- | --- | --- |
| `configure_live_load_system` | 五体系显式选择；清理需显式 true，不升级重试；能力检查在写前。 | 旧桥通拒绝 clear_existing，工程流程仍待新后端。 |
| `configure_operation_stage` | 四列表必填、[]关闭对应类，完整替换，单次提交不求解。 | 需服务端支持运营阶段设置。 |
| `create_en1991_vehicle` | 标准/用户工厂区分、显式名称、有效参数、kN/m和默认四轴，回读实际 ID。 | 完整工程验收受旧桥通体系选择阻断。 |
| `get_international_live_load_data` | 原生车辆/工况完整数据，查询后本地精确筛选分页，保留未激活字段。 | 无独立规划车道 getter。 |
| `get_model_edit_readiness` | 只读诊断；success 不代表可编辑；令牌不缓存，不切阶段或删结果。 | 返回状态以桥通报告为准。 |
| `get_model_status` | 启动不主动探测，诊断按需；缺 SDK API 与桥通未知状态分开。 | 缺 API 放行旧行为；有 API 而状态未知则关闭写权限。 |
| `get_transversal_data` | 服务端精确名称/ID筛选、本地分页；保留车道顺序与米制 load_factors。 | 需原生横向定义接口。 |
| `manage_check_case_definition` | 完整模型工况快照、零基枚举和非活动字段；只混凝土工具承诺导入/求解。 | 旧桥通不识别快照命令；地震/加固求解不由混凝土工具承诺。 |
| `manage_check_material` | set 全快照/reset 指定覆盖，模型权限和单次提交；不从 CSAN 摘要拼写回。 | 完整快照需 UI/export，旧桥通命令未支持。 |
| `query_model_data` | 按 kind 分支的嵌套 schema；服务端交集筛选/分页；near+tolerance、必需过滤、数量上限。 | 缺端点显式失败，不降级下载全模型。 |
| `remove_section_reinforcement` | 完整模型标识支持 I/J/变截面；无默认全删，与旧 CSAN 接口分开。 | 需支持模型快照端点。 |
| `remove_transversal_data` | 明确对象删除；可选级联仅车/道；不清外部引用，不放大破坏参数重试。 | 真实引用检查归桥通。 |
| `set_check_stirrup_snapshot` | 完整大小写/原生存储字段；改号须 original_id，不推断来源。 | 需支持快照端点及可信完整导出。 |
| `set_element_stirrups` | 剪力5列/扭转3列；None保留、[]清空、0未配置；同族不重复单元。 | 引用校验归桥通。 |
| `set_international_live_load_case` | 车辆名称/规范预查，EN不重复车道，完整因子快照；定义不自动启用运营求解。 | 车道/影响面引用由桥通校验，结果完整名称需已验证来源。 |
| `set_international_vehicle` | AASHTO/BS/EN分型参数；更新也用新定义默认值；AASHTO N,m / EN kN,m，r为百分比。 | BS轴力单位未明确，保持原生值。 |
| `set_planned_lane` | 专用规划车道与普通车道optimize分开；全部物理字段必填，模型长度单位，提交一次。 | 无独立 getter，须 UI/export核验；删除须 planned类别。 |
| `set_section_reinforcement` | 完整模型快照、所有字段必填，6列层信息及实际点，空数组清空，不用CSAN片段。 | 模型单位与原生枚举需完整导出；旧桥通端点缺失。 |
| `set_transversal_case` | 实际车/道 ID预查、正系数和维数一致；保留引用重命名，回读ID，不求解。 | 完整工程验收待支持体系切换的后端。 |
| `set_transversal_lane` | 节点顺序、相邻直接梁连接、宽度固定m，单次提交并精确回读。 | 连通性由桥通检查；不排序/自动造梁。 |
| `set_transversal_vehicle` | 完整 add/update 可覆盖；固定kN/m，系统显式选择；回读实际 ID。 | 旧桥通 clear_existing 阻断仍未解除。 |

## 元数据、兼容与选型

全目录的实际差异、每工具文本长度、参数和输出保真记录见 [目录报告](glama-catalog-diff.json)；选型场景与目录取舍见 [工具选择](glama-tool-selection.md)。
参数说明继续来自原始 Args；只有完整覆盖参数、没有未知/重复名称或不明确结构时才从对外 description 移除 Args。保留原始 docstring、嵌套字段、示例、中英文说明及跨工具引用。
已有名称、参数默认值和输出 schema 保留；唯一输入结构扩展是自定义温度支持三列，同时保留旧两列原样透传。预应力确认消息改成原生值，不再标注未经证实的 kN；解析自由文本的消费者须检查此变化。
已确认会覆盖的材料/截面、改号/更新/设置等工具补齐 destructiveHint；未改模型状态守卫和错误通道。

## 未决项如何关闭

对表中每个后端未知项，在专用测试工程取得同版本 UI/API 导出或 C# 实现依据，记录输入、调用前后完整对象和单位/重复规则，再决定能否收紧公开说明。
优先验证总体设置与屈曲默认字段是否覆盖、温度/索荷载/质量的单位和重复规则、改号/反向/改接的引用及附属荷载迁移，以及钢束坐标分析前的可用性。
0.5.0 实测暴露的 clear_existing、快照端点和 Rz 限制继续有效，详见 [实测记录](0.5.0-live-validation.md)。本轮没有连接或修改真实业务工程。
旧评语中的 calculate_ection_property 属于拼写错误；并未据此新建 API。旧“重复”指控按调用路径审查，没有因筛选 warning 删除工具。

G4 实际结果、候选包和 G6 复评步骤见 [候选验收](0.5.1-validation.md)与[发布说明草稿](0.5.1-release-notes.md)。
