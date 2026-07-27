# corps: DPEF AI Agent (Pure Python)

`corps` 是一个基于 **任务分解、计划、执行、反馈 (DPEF)** 闭环设计的现代 AI Agent 工具集。

目前采用 **纯 Python** 架构，提供轻量级的启动响应、灵活的插件扩展以及交互式的终端体验。它专注于提供一个高性能、易于定制的 AI 编排框架。

## 核心理念：DPEF 闭环
- **Planning (计划)**：基于项目上下文生成动态执行计划（Checklist）。
- **Execution (执行)**：调用 Python 编写的原子 Tools 或复合 Skills。
- **Feedback (反馈)**：实时分析结果，自动调整后续决策路径。

## 工作流 (Workflow)

`corps` 采用自适应的循环推理机制来执行用户任务：

1.  **计划阶段 (Planning)**:
    - LLM 接收用户任务并分析当前项目上下文。
    - 生成一份 **Checklist**，列出完成任务所需的步骤。
2.  **执行阶段 (Execution)**:
    - 系统进入循环模式（默认最多 5 步）。
    - LLM 根据当前 Checklist 和反馈，从工具箱中选择最合适的 **Action** (Tool 或 Skill)。
    - **Action 解析**: 系统支持 JSON 格式或启发式文本解析来识别指令名及其参数。
    - **安全确认**: 对于敏感操作，系统会请求用户确认。
    - **反馈循环**: 动作执行的结果（Success/Failure）会立即回馈给 LLM，用于下一步决策。
3.  **验证阶段 (Verify)**:
    - 任务完成后，LLM 对执行过程进行总结。
    - 提供最终的任务结果报告（通常使用中文）。

### 复合技能 (Skills) 工作流
对于复杂的预定义任务，`corps` 支持基于 **DAG (有向无环图)** 的工作流引擎：
- **编排**: 在 `skill.yaml` 中定义多个步骤及其依赖关系。
- **数据流**: 前一步骤的输出可以自动注入到后一步骤的参数中。
- **混合执行**: 一个 Skill 中可以包含原子工具调用和其他 Agent 节点的推理。

## 架构概览

- **Core (Python)**：负责会话管理、多供应商 LLM 通信（OpenAI, Gemini, Anthropic 等）、多步推理循环及工具调度。
- **Tools & Skills**:
    - **Tools**: 原子化任务处理（如文件编辑、数据库操作、爬虫等）。
    - **Skills**: 预定义的复合工作流，通过 YAML 编排多个工具。
- **CLI (交互界面)**：提供交互式终端模式，支持自动补全、Markdown 渲染和实时反馈。

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行
```bash
# 启动交互式聊天
python src/main.py chat

# 执行单次任务
python src/main.py exec "请分析当前目录结构"

# 管理技能 (Skills)
python src/main.py skill list
```

## 核心功能

### 1. Model Context Protocol (MCP) 集成
系统现已原生支持 MCP 协议，允许接入外部工具服务器（如 Google Maps, GitHub, Slack 等）。

#### 配置方法
在 `.env` 文件中通过环境变量定义 MCP 服务器：
- **简单命令**: `MCP_SERVER_<NAME>="command args..."`
- **JSON 配置**: `MCP_SERVER_<NAME>='{"command": "node", "args": ["path/to/server.js"], "env": {"KEY": "VALUE"}}'`

例如接入 Google Maps:
```bash
MCP_SERVER_MAPS="npx -y @modelcontextprotocol/server-google-maps"
GOOGLE_MAPS_API_KEY="your_api_key"
```

#### 使用方法
- **自动加载**: 启动时系统会自动连接所有配置的 MCP 服务器。
- **工具发现**: MCP 工具会自动注入到 Agent 的能力索引中，名称前缀为 `mcp_<server_name>_`。
- **无缝调用**: LLM 会像调用普通工具一样自动识别并调用 MCP 工具。

### 2. 现代化 CLI 交互
- **自动补全**: 支持命令、文件名、会话名的智能补全。
- **多行输入**: 支持代码块等复杂内容输入。
- **实时渲染**: 采用 Rich 库提供美观的 Markdown 渲染和状态显示。

### GitHub MCP 快捷任务
如果已经配置了名为 `github` 的 MCP 服务器，可以在聊天界面里直接使用。
这里不需要安装 `gh`，只要给 MCP server 提供 GitHub token 即可。

最常见的方式是在环境变量里放一个 token：
```bash
GITHUB_TOKEN=ghp_xxx
```

也可以直接写进 `MCP_SERVER_GITHUB` 的 `env` 配置：
```bash
MCP_SERVER_GITHUB='{"command":"npx","args":["-y","<github-mcp-server>"],"env":{"GITHUB_TOKEN":"ghp_xxx"}}'
```

常用命令：
```bash
/gh help
/gh status
/gh issue create octo-org octo-repo "Fix bug" body="..."
/gh issue list octo-org octo-repo
/gh pr create octo-org octo-repo "Fix bug" feature-branch main body="..."
/gh pr merge octo-org octo-repo 42
```
当前实现会根据 GitHub 常用工作流任务名称自动匹配 MCP 工具，包括：
- 列出仓库、Issue、PR
- 创建 Issue、PR
- 评论
- 合并 PR
- 触发 workflow dispatch

#### 多账号切换
如果你有多个 GitHub 账号，建议用“不同终端窗口 + 不同环境变量”来切换，而不是在同一个进程里混用。

例如：
```bash
# 账号 A
set GITHUB_TOKEN=ghp_account_a
python src/main.py chat

# 账号 B
set GITHUB_TOKEN=ghp_account_b
python src/main.py chat
```

如果你使用的是 `MCP_SERVER_GITHUB` 的 JSON 配置，也可以给不同账号准备不同的启动脚本或不同的 `.env` 文件。

#### 如何查看当前状态
在 CLI 里输入：
```bash
/gh status
```
它会显示：
- 当前 GitHub MCP server 名称
- 哪些 token 环境变量已设置
- 是否检测到多个 token 来源
- 是否配置了账号标识类环境变量

注意：
- 本地只能可靠判断“用了哪套环境变量”
- 精确的 GitHub 账号名，通常要由 MCP server 本身或 GitHub API 返回
- 如果同时设置了多个 token 变量，真正生效的顺序取决于你的 MCP server 实现

## 环境变量配置

在根目录创建 `.env` 文件：
- `CORPS_PROVIDER`: 默认供应商 (openai, gemini, groq, anthropic, ollama)。
- `CORPS_MODEL`: 默认模型。
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` 等 API 密钥。

---

## 技术实现细节

`corps` 的核心是一个基于 Python 实现的高级 Agent 编排框架，其主要技术特点如下：

### 1. DPEF 状态机引擎
系统的核心逻辑由 `DPEFOrchestrator` 驱动，它维护一个显式的状态机：
- **Planning**: 使用 LLM 生成结构化的 Checklist。
- **Execute**: 采用“渐进式展示 (Progressive Disclosure)”技术，将工具/技能的摘要和参数结构（而非全部文档）提供给 LLM，以优化上下文窗口利用率。
- **Verify**: 在任务结束时进行一致性验证和总结。

### 2. 基于 DAG 的技能引擎
Skills 不仅仅是工具的集合，而是一个由 `WorkflowEngine` 驱动的**有向无环图 (DAG)**：
- **拓扑排序**: 自动计算步骤间的执行顺序。
- **上下文注入**: 前序步骤的输出 (`outputKey`) 会自动映射到后续步骤的输入参数中。
- **混合节点**: 支持 `ToolNode` (执行原子工具) 和 `AgentNode` (进行递归推理)。

### 3. MCP 动态发现机制
通过 `mcp_manager` 实现与 Model Context Protocol 的无缝集成：
- **即插即用**: 外部 MCP 服务器通过环境变量注册，启动时动态发现能力。
- **工具映射**: 自动将 MCP 工具转换为系统内部可调用的 Action 格式。

### 4. 交互式 CLI 实现
底层基于 `prompt-toolkit` 和 `rich` 构建：
- **响应式 UI**: 提供带语法高亮的 Markdown 渲染。
- **智能补全**: 基于当前环境和可用工具的动态补全。

---

## 打包与分发 (给非技术人员)

如果你希望将 `corps` 打包给不熟悉 Python 的同事或用户使用，可以参考以下方案：

### 1. 使用 PyInstaller 打包成单文件 (推荐 Windows)

在 Windows 环境下，你可以使用 `PyInstaller` 将程序打包为独立的可执行文件 (`.exe`)。

**步骤**:
1. 安装打包工具：
   ```bash
   pip install pyinstaller
   ```
2. 执行打包命令 (在项目根目录)：
   ```bash
   pyinstaller --onefile --name corps --collect-all charset_normalizer --add-data "src;src" src/main.py
   ```
   *注意：如果你的 Skills 或 Tools 存放在非 `src` 目录下，需要使用 `--add-data` 包含它们。*
3. 打包完成后，在 `dist/` 目录下会生成 `corps.exe`。

**分发清单**:
- `corps.exe`
- `.env` (需要用户填入自己的 API Key)
- `corps.properties` (如果需要)

### 2. 使用快捷启动脚本 (Windows)

如果不想打包，可以提供一个简单的 `start.bat` 脚本：

```batch
@echo off
echo Starting corps Agent...
python src/main.py chat
pause
```

### 3. 用户使用说明
对于非技术用户，建议告知其：
1. **获取 API Key**: 注册 OpenAI 或 Gemini 并获取 Key。
2. **配置 .env**: 将 Key 填入 `.env` 文件。
3. **双击运行**: 运行 `corps.exe` 或 `start.bat`。

---
*本项目已转为纯 Python 架构。如有问题请通过 `/help` 或查阅源码了解更多细节。*
