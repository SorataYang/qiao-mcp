# 领域工具目录

0.6.0 默认列出 15 个领域工具，完整覆盖原有 153 项操作。
先选择领域，再在 `request.operation` 中选择具体操作，其余字段使用原操作的参数。
每个操作的完整说明、必填项、默认值、单位和嵌套 Schema 都随目录发布。
完整 Schema 仍然较大；这次组织调整主要减少客户端需要选择的并列入口。

## 调用示例

读取模型状态，MCP `tools/call` 参数：

```json
{
  "name": "inspect_bridge",
  "arguments": {
    "request": {"operation": "get_model_status"}
  }
}
```

原操作本来就使用 `request` 时，保留该层。例如按节点号筛选：

```json
{
  "name": "query_model",
  "arguments": {
    "request": {
      "operation": "query_model_data",
      "request": {"kind": "nodes", "node_ids": [1, 2], "limit": 20}
    }
  }
}
```

`operation` 是固定选项。其他领域的操作、不属于该操作的字段、无效的嵌套参数会在
调用后端前被拒绝。例如 `inspect_bridge` 不接受 `initialize_model`。

## 兼容方式

原调用仍有效，例如 `tools/call` 的 `name="get_model_status"`、`arguments={}`。
两种目录都调用同一原处理函数，原参数默认值、省略与 `null` 的区别、空列表清空语义、
状态守卫、结构化内容、错误和求解进度都保留。

如果客户端要求旧名称必须出现在 `tools/list` 中，在其 MCP 服务器配置加入：

```json
{"env": {"QIAO_MCP_CATALOG_LAYOUT": "flat"}}
```

应把该环境变量合入现有 `env`，保留原有连接地址等设置。重启 MCP 服务器后，
`flat` 列出原有 153 个名称；`domains`（默认）列出 15 个领域入口。
不支持的配置值会明确报错。0.5.1 默认使用旧目录；从该版本升级后应刷新客户端目录缓存。

## 选择边界与响应

| 需求 | 入口 |
| --- | --- |
| 连接、当前阶段和可用权限 | `inspect_bridge` |
| 模型定义、实体查找、几何检查 | `query_model` |
| 保存、打开、初始化项目 | `manage_model_files` |
| 节点和单元、标准建桥流程 | `edit_geometry` |
| 材料、截面、板厚和时变属性 | `edit_properties` |
| 支座、弹簧、连接、梁端释放 | `edit_boundaries` |
| 分组、施工阶段、激活与钝化 | `edit_construction` |
| 静力工况、组合、荷载 | `edit_loads` |
| 动力输入、求解设置、结构计算 | `analyze_model` |
| 钢束属性、线形、预应力 | `edit_prestress` |
| 车辆、车道、横向和国际活载 | `edit_traffic` |
| 检算快照、当前检算窗口、规范验算 | `manage_checks` |
| 数值结果、模态、活载包络、钢束结果 | `query_results` |
| 视图、阶段显示、截图和云图 | `view_model` |
| 原生接口检索与长尾调用 | `access_backend` |

14 个领域入口合并其操作的原输出模型。`view_model` 同时支持 MCP 图像与文本/结构化
响应，因此不声明统一输出 Schema。每项操作仍使用原输出协议。
领域提示按所含操作的行为合并：只读诊断和查询保持只读；含写入、删除或外部调用的
领域保留相应提示。实际权限始终由所选操作的原守卫判断。

施工阶段钝化在 `edit_construction` 的 `update_construction_stage` 中完成；
`delete_structures`、`delete_boundaries`、`delete_loads` 钝化对应组，保留模型定义。
阶段显示属于 `view_model`，结构求解属于 `analyze_model`，混凝土检算属于
`manage_checks`。调用流程仍需满足原有的桥通版本、活动阶段和能力要求。
