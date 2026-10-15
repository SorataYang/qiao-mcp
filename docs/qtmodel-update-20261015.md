# qtmodel 发布前更新核对

2026-10-15。Qiao-MCP 本地版本为 0.5.9，核对源码提交
`d62f02c`。本轮同步参考仓库并检查兼容性，未修改应用代码、依赖范围或锁文件。

## 版本与来源

| 项目 | 核对结果 |
| --- | --- |
| 参考仓库原提交 | `0687ffe3fa481747c53f9521ee1503a2a043fc08`，qtmodel 2.9.2 |
| 参考仓库最新提交 | `0a36bc50b1def254fd40dbfeb5fc6e5e960cde9f`，qtmodel 2.9.3 |
| 新增提交 | `814ee3f`（10 月 13 日）、`0a36bc5`（10 月 14 日） |
| PyPI 最新版本 | 2.9.3，wheel 上传于 2026-10-13 16:40:54（北京时间） |
| 同仓库 Agent 包 | qiaotong-agent-kit 0.22.2 → 0.23.0 |
| 本项目当前锁定版本 | qtmodel 2.9.2 |

已执行 `git fetch origin` 和 `git merge --ff-only origin/master`；参考工作区保持干净。
来源：[参考仓库提交](https://gitee.com/jack0443/qtmodel-release/commit/0a36bc50b1def254fd40dbfeb5fc6e5e960cde9f)、
[PyPI 2.9.3](https://pypi.org/project/qtmodel/2.9.3/)。

下载的 `qtmodel-2.9.3-py3-none-any.whl` SHA-256：
`41c4bcf2704f465a6f7e016a6c0272144aa44e6432aa711cd87816df59ea07e6`。
与 PyPI 提供的校验值一致；与最新参考源码比较，双方均为 74 个 Python 文件，
无新增或缺失文件，统一 CRLF/LF 后内容逐文件相同。
这次参考仓库更新与此前审计过的 PyPI 2.9.3 对齐，没有发现更新的已发布 SDK。

## 对 Qiao-MCP 的影响

| 上游变化 | 当前处理与发布影响 |
| --- | --- |
| `QtServer.require_model_instance` 与 `require_model_revision` | 新增可选写入上下文。Qiao-MCP 当前使用已有模型状态守卫，尚未接入新事务能力；接入时还须核对桌面端的实例与修订协议。 |
| 17 个历史命令缺少桌面路由 | SDK 在连接前抛出 `API_NOT_OPEN`。当前工具已记录检算快照、规划车道等限制，并验证错误保留且不继续提交。 |
| `remove_elements` 加强编号校验 | 显式空集合和非法编号被拒绝。当前工具已拒绝危险选择，删除全部单元且移除孤立节点时先回读实际编号。 |
| API 帮助标注不可用命令 | 方法存在仍不能视为桌面路由已经开放，现有工具说明保留这一边界。 |
| qiaotong-agent-kit 0.23.0 的事务、分页及目录操作 | Qiao-MCP 不依赖此包，这些功能不会随 qtmodel 升级自动接入。 |

这些 SDK 限制已在[逐工具审计](qtmodel-code-audit.md)记录。
本次未发现需要修改当前适配层的新阻断；此前真实桥通构建上的
`clear_existing` 和其他工程验收限制仍需通过专用测试环境核实。

## 本次验证

通过 `PYTHONPATH=reference_codes/qtmodel-release/packages/qtmodel/src:src`
加载最新参考源码，运行当前项目完整离线测试：**1978 通过，0 失败，0 跳过**，
耗时 51.256 秒。测试前断言实际导入文件来自参考仓库且 SDK 版本为 2.9.3。

测试显式排除 `tests/test_end_to_end.py`，设置
`QIAOTONG_HTTP_URL=http://localhost:1/pythonForQt/`，并将真实
`requests.sessions.Session.request` 替换为抛出 `ConnectionError` 的离线桩。
已有模拟传输和 FakeDb 测试照常执行；本轮未连接真实桥通。

原始 PyPI 元数据、wheel、源码比较、测试 XML 和验证摘要保存在忽略目录
`dist/qtmodel-update-20261015-yi0pyy5f/`。
测试 XML SHA-256：
`fffcd7ee1bd050da80fef5a9a034d42477506d8d07f4a89296086136d49e0913`。

## 发布建议

正式发布时建议将 `uv.lock` 中 qtmodel 从 2.9.2 更新到已核对的 2.9.3，
让锁定安装与当前 PyPI 解析结果一致。现有
`qtmodel>=2.6.3,!=2.9.0,<2.10` 范围已经包含 2.9.3，无须因此放宽范围。
本次没有增加 Qiao-MCP 版本号，也没有推送、打标签或发布。
