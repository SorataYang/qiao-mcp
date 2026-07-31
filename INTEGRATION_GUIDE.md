# Qiao-MCP 接入指南 / Integration Guide

## 快速接入 Quick Start

### 1️⃣ 克隆项目 Clone Repository

```bash
git clone https://github.com/SorataYang/qiao-mcp.git
cd qiao-mcp
```

### 2️⃣ 安装依赖 Install Dependencies

**前置要求 Prerequisites:**
- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) 包管理器

```bash
# 安装 uv (如果还没安装)
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 3️⃣ 测试 MCP 服务器 Test Server

```bash
# 方法 1: 直接运行
uv run qiao-mcp

# 方法 2: 使用 MCP Inspector 测试
npx @modelcontextprotocol/inspector uv run qiao-mcp
```

---

## 🤖 在 AI Agent 中接入 Integration with AI Agents

### A. Claude Desktop 配置

**配置文件位置:**
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**配置内容:**
```json
{
  "mcpServers": {
    "qiao-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "D:/GitHub/qiao-mcp",
        "run",
        "qiao-mcp"
      ],
      "env": {
        "UV_PYTHON": "3.11"
      }
    }
  }
}
```

> ⚠️ 注意：将 `D:/GitHub/qiao-mcp` 替换为你的实际项目路径

**重启 Claude Desktop** 即可生效。

---

### B. Cursor 配置

**配置文件位置:**
项目根目录下创建 `.cursor/mcp.json`

**配置内容:**
```json
{
  "mcpServers": {
    "qiao-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/qiao-mcp",
        "run",
        "qiao-mcp"
      ]
    }
  }
}
```

**重启 Cursor** 即可生效。

---

### C. Python SDK 集成 (通用方法)

如果你在开发自己的 AI Agent，可以使用 MCP Python SDK：

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置 MCP 服务器
server_params = StdioServerParameters(
    command="uv",
    args=["--directory", "/path/to/qiao-mcp", "run", "qiao-mcp"],
    env=None
)

# 连接并使用
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        # 初始化
        await session.initialize()
        
        # 列出可用工具
        tools = await session.list_tools()
        print(f"Available tools: {[tool.name for tool in tools.tools]}")
        
        # 调用工具示例
        result = await session.call_tool("get_model_info", arguments={})
        print(result)
```

---

### D. Node.js/TypeScript SDK 集成

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

// 创建传输层
const transport = new StdioClientTransport({
  command: "uv",
  args: ["--directory", "/path/to/qiao-mcp", "run", "qiao-mcp"],
});

// 创建客户端
const client = new Client(
  {
    name: "my-bridge-agent",
    version: "1.0.0",
  },
  {
    capabilities: {},
  }
);

// 连接
await client.connect(transport);

// 列出工具
const { tools } = await client.listTools();
console.log("Available tools:", tools);

// 调用工具
const result = await client.callTool({
  name: "get_model_info",
  arguments: {},
});
console.log(result);
```

---

## 🛠️ 可用功能 Available Features

### Tools (工具)
- ✅ `get_model_info` - 获取模型概要
- ✅ `create_nodes` - 创建节点
- ✅ `create_elements` - 创建单元
- ✅ `create_material` - 创建材料
- ✅ `create_section` - 创建截面
- ✅ `set_support` - 设置支承
- ✅ `apply_nodal_force` - 施加节点荷载
- ✅ `apply_beam_distributed_load` - 施加分布荷载
- ✅ `add_construction_stage` - 添加施工阶段
- ✅ `configure_analysis` - 配置分析
- ✅ `validate_model` - 验证模型
- ✅ `get_analysis_results` - 获取分析结果

### Resources (资源)
- `bridge://model/summary` - 模型概览
- `bridge://model/materials` - 材料列表
- `bridge://model/sections` - 截面列表
- `bridge://model/load-cases` - 荷载工况
- `bridge://model/stages` - 施工阶段
- `bridge://model/structure-groups` - 结构组
- `bridge://model/boundaries` - 边界条件

### Prompts (工作流)
- `design-simple-beam` - 简支梁设计
- `design-continuous-beam` - 连续梁设计
- `check-structure` - 结构检算
- `construction-stage-analysis` - 施工阶段分析

---

## ⚙️ 配置选项 Configuration Options

可以通过环境变量配置服务器行为：

```bash
# 日志级别
export LOG_LEVEL=DEBUG

# 结果图片保存目录
export RESULT_IMAGE_DIR=/path/to/images

# Provider 类型 (默认 qtmodel)
export BRIDGE_PROVIDER=qtmodel
```

---

## 🔧 后端软件要求 Backend Requirements

### QiaoTong (桥通软件)
- **必须**: QiaoTong 软件已安装并运行
- **依赖**: `qtmodel>=2.3.3` (从 PyPI 自动安装)
- **连接**: MCP 通过 `qtmodel` Python API 连接到运行中的 QiaoTong 软件

**如果软件未运行:**
- Tools 会返回友好的错误信息
- 不会导致 MCP 服务器崩溃
- 软件启动后自动恢复连接

---

## 📝 调试 Debugging

### 1. 查看 MCP 服务器日志

```bash
# 直接运行查看实时日志
uv run qiao-mcp

# 或设置详细日志级别
LOG_LEVEL=DEBUG uv run qiao-mcp
```

### 2. 使用 MCP Inspector 测试

```bash
npx @modelcontextprotocol/inspector uv run qiao-mcp
```

浏览器打开 `http://localhost:5173` 可视化调试。

### 3. 检查 Claude Desktop 日志

**Windows:**
```
%APPDATA%\Claude\logs\mcp*.log
```

**macOS:**
```
~/Library/Logs/Claude/mcp*.log
```

---

## 📚 示例对话 Example Conversations

### 示例 1: 创建简支梁模型

```
User: 帮我创建一个 20 米跨径的简支梁桥模型

Agent 会调用:
1. create_nodes - 创建节点
2. create_material - 创建 C50 混凝土
3. create_section - 创建箱梁截面
4. create_elements - 创建梁单元
5. set_support - 设置边界条件
6. validate_model - 验证模型
```

### 示例 2: 查询模型信息

```
User: 当前模型有多少个节点和单元？

Agent 会调用:
- get_model_info - 返回模型统计信息
```

### 示例 3: 施加荷载并分析

```
User: 施加恒载和活载，然后运行静力分析

Agent 会调用:
1. apply_beam_distributed_load - 施加分布荷载
2. configure_analysis - 配置静力分析
3. get_analysis_results - 获取结果
```

---

## 🤝 协作建议 Collaboration Tips

### 对于 Agent 开发者:

1. **先测试工具可用性**
   ```python
   tools = await session.list_tools()
   # 检查需要的工具是否存在
   ```

2. **处理错误响应**
   - 工具调用可能返回错误（如软件未运行）
   - 需要优雅地处理并提示用户

3. **使用 Prompts 快速开始**
   - 使用预定义的 `design-simple-beam` 等 prompts
   - 可以快速生成完整的设计流程

4. **查看完整 API 文档**
   ```bash
   # 查看工具列表和参数
   npx @modelcontextprotocol/inspector uv run qiao-mcp
   ```

---

## 🆘 常见问题 FAQ

### Q: MCP 服务器启动失败？
**A**: 检查：
1. Python >= 3.11 已安装
2. `uv sync` 已执行
3. 路径配置正确（绝对路径）

### Q: 工具调用返回 "qtmodel unavailable"？
**A**: 确保 QiaoTong 软件正在运行。MCP 服务器可以启动，但需要软件运行才能执行建模操作。

### Q: 如何更新到最新版本？
**A**: 
```bash
cd qiao-mcp
git pull
uv sync
# 重启 Claude Desktop 或你的 Agent
```

### Q: 支持哪些编程语言？
**A**: MCP 协议支持任何语言，官方提供：
- Python SDK
- TypeScript/Node.js SDK
- 也可以直接使用 stdio 协议

---

## 📞 联系方式 Contact

- **Issues**: GitHub Issues
- **文档**: [MCP Protocol Docs](https://modelcontextprotocol.io/)
- **示例代码**: 查看 `examples/` 目录（如果有）

---

## 🔗 相关链接 Related Links

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [QiaoTong 软件](https://www.qt-model.com/)
- [qtmodel PyPI](https://pypi.org/project/qtmodel/)
