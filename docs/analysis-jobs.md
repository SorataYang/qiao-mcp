# 可恢复分析与检算任务

新增 `start_analysis_job`、`get_analysis_job`、`list_analysis_jobs`，在默认目录中
通过搜索/执行入口使用，也可经 `analyze_model` 或直接名称调用。原来的
`run_analysis`、`run_concrete_check` 等待式接口继续可用。

```json
{
  "name": "execute_operation",
  "arguments": {
    "operation": "start_analysis_job",
    "arguments": {"request_id": "my-unique-run-20261015-01", "kind": "analysis"}
  }
}
```

每次新求解生成一个唯一 request_id（建议 UUID hex）。丢失 MCP 回执后，使用**同一个**
request_id 和参数再次调用，会取回原任务而不重复提交。相同 ID 携带不同参数会被拒绝。
混凝土检算使用 `kind="concrete_check", name="检算工况名"`，会导入指定工况并启动检算。

返回的 `job.job_id` 用于 `get_analysis_job(job_id=...)`，建议间隔 2–5 秒查询。
外层 `status="success"` 表示成功取得任务记录；必须检查 `job.state`：

- submitting：已持久化，正在提交；不要创建另一个 request_id 重试。
- running：已取得桥通启动回执，计算仍在运行。
- completed：匹配的桥通任务已确认成功结束；不代表规范验算合格。
- failed / cancelled：匹配任务的后端失败/取消状态。
- unknown：无法安全确认。查看 error 并回到桥通核对，不自动再求解。

SQLite 数据库默认在 MCP 主机的 `~/.qiao-mcp/jobs.sqlite3`，可通过绝对路径
`QIAO_MCP_JOB_DB` 指定位置。目录/数据库只在实际调用任务工具时创建。
重连或重启后保持同一个数据库，通过 `list_analysis_jobs` 找回句柄；列表仅展示最后
观察状态，`get_analysis_job` 才刷新。记录与 request_id 去重信息不自动过期；需要清理时，
先确认没有待处理/不确定任务，再由用户备份或移除数据库。移除会丢失恢复和去重信息。

求解在桥通后台运行，MCP 不维持一个长连接等待。停止轮询、取消 MCP 请求、关闭客户端，
都不会停止桥通计算。需要停止时使用桥通的终止控制，再查询任务确认取消状态。
提交 HTTP 请求最多等待 30 秒；回执丢失会保留 unknown 任务，不重放写命令。

可靠关联要求 SDK 提供实例保护、桌面声明 `model_instance_guard=1` 并报告
`model_instance_id`，以及启动回执/状态查询提供同一个非空 `started_at`。
读取时同时检查工程实例与任务开始时间，不将“最近一次成功”误认成原任务。
旧 SDK/桌面不满足要求时，在写入前拒绝新的持久任务；继续使用原有等待式接口。

恢复边界：

- 正常重连/服务重启：数据库保存启动时间，查询匹配任务得到最新状态和终态。
- 暂时断线或切换工程：返回 unknown 观察结果，保留关联信息；恢复原工程后可再次查询。
- 后续求解覆盖了“最近一次任务”状态：旧任务无法归属，明确 unknown。
- 进程在发送启动命令后、保存启动回执前退出：记录存在但无法证明执行结果，明确 unknown。
- completed 的持久结果是求解器状态，不是归档的全部内力/应力数据；读取数值结果仍须
  使用匹配工程和工况的结果工具。`submitted_model_revision` 是提交前观察值，不宣称
  为结果所属修订或多工具事务凭证。

离线测试验证协议与状态机；本轮没有新增真实桥通实测，不能由模拟测试证明某个桌面
版本必然提供上述关联字段。缺失字段时会显式拒绝或返回 unknown。
