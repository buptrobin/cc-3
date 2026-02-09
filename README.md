# CC-3

> LangGraph 编排 + Claude Code CLI 执行的 AI Agent 框架

CC-3 将 **LangGraph** 作为编排层（规划 / 路由 / 策略 / 审计），将 **Claude Code CLI** 作为执行层（工具调用 / 检索 / 代码操作），实现了一套可观测、可续接、安全可控的 Agent 运行框架。

## 架构概览

```
┌──────────────────────────────┐
│       App / API / CLI        │  Typer CLI · FastAPI · React 前端
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│       Session Manager        │  workspace / session_id / 锁 / 回收
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│    LangGraph Orchestrator    │  Plan → Exec → (Reflect) → END
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│     Claude CLI Executor      │  spawn + stream-json 解析 + resume
└──────────────┬───────────────┘
               │
         ┌─────▼──────┐
         │ claude CLI  │  tools / skills / grep / session
         └────────────┘
```

**核心原则**：LangGraph 不直接执行 bash/grep，所有执行任务交给 Claude Code CLI；LangGraph 负责上层策略与审计。

## 功能特性

- **Agent 脚手架** — `init-agent` 一键生成 agent 配置与 workspace 目录结构
- **会话续接与分支** — 基于 `session_id` 支持 `--resume` 续接和 `--fork-session` 分支推演
- **三级安全策略** — safe（只读）/ dev（可编辑）/ open（可联网），双重保障（CLI 权限 + 系统提示词）
- **完整可观测性** — 每次执行输出 `events.ndjson`、`meta.json`、`result.txt` 等 artifacts
- **并发安全** — workspace 级文件锁，防止并发执行污染
- **Chat 应用** — 内置 FastAPI 后端 + React 前端，支持 SSE 实时事件推送

## 快速开始

### 前置要求

- Python >= 3.13
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) 已安装并完成认证
- (可选) Node.js >= 18（如需运行前端）

### 安装

```bash
# 克隆项目
git clone <repo-url> cc-3
cd cc-3

# 方式一：pip 安装（推荐）
pip install -e ".[dev]"

# 方式二：不安装直接运行
python main.py --help
```

### 创建 Agent

```bash
# 通过脚手架初始化一个 agent
cc3 init-agent my_agent
# 或不安装时：python main.py init-agent my_agent
```

会生成以下结构：

```
agents/my_agent/
├── agent.yaml            # agent 配置（模型、权限模式、策略）
├── system_prompt.md      # Claude CLI 系统提示词
├── policies.md           # 行为策略说明
└── skills/               # 自定义 skills（预留）

workspaces/my_agent/
├── .env                  # API Key / Base URL 等环境变量
├── kb/                   # 知识库（grep/read 的目标目录）
└── runs/                 # 执行日志与 artifacts 归档
```

### 配置

编辑 `workspaces/my_agent/.env` 设置 API Key：

```env
ANTHROPIC_API_KEY=sk-ant-xxx
# 可选：自定义网关
# ANTHROPIC_BASE_URL=https://your-gateway/v1
```

编辑 `agents/my_agent/agent.yaml` 调整策略：

```yaml
agent_id: my_agent
model: null                    # 使用 CLI 默认模型，或指定如 claude-sonnet-4-20250514
permission_mode: dontAsk       # dontAsk / default / bypassPermissions
policy_preset: safe            # safe / dev / open
```

### 运行

```bash
# 以 safe 模式执行（只读）
cc3 run -a my_agent --mode safe --goal "在 kb/ 目录下搜索关于认证的文档并总结"

# 以 dev 模式执行（可编辑）
cc3 run -a my_agent --mode dev --goal "重构 src/utils.py 中的错误处理逻辑"

# 续接上次会话
cc3 run -a my_agent --resume --goal "继续上次的任务"
```

## 安全策略

通过 `--mode` 参数控制 Claude CLI 可使用的工具集：

| 模式 | 允许的工具 | 适用场景 |
|------|-----------|---------|
| `safe` | Read / Grep / Glob | 文档检索、代码审查、只读分析 |
| `dev` | + Edit / Write / Bash | 代码开发、重构、脚本执行 |
| `open` | + WebFetch / WebSearch | 需要联网查询的任务 |

安全通过两层保障：
1. Claude CLI `--permission-mode` 参数限制
2. `system_prompt.md` 中的行为约束

## 可观测性

每次执行生成完整 artifacts 到 `workspaces/<agent>/runs/<run_id>/`：

| 文件 | 说明 |
|------|------|
| `events.ndjson` | 原始 stream-json 事件流（最重要的调试产物） |
| `events_norm.ndjson` | 归一化事件（session_id / delta / result 等） |
| `meta.json` | 运行元信息（argv / cwd / 耗时 / exit_code / session_id） |
| `result.txt` | 最终输出文本 |
| `step.json` | 本次 step 的输入输出摘要 |
| `stderr.log` | 标准错误输出 |

## Chat 应用

项目内置了一个完整的 Chat 界面原型：

### 启动后端

```bash
cd apps/chat_api
pip install -r requirements.txt
uvicorn cc3_chat_api.main:app --reload --port 8000
```

### 启动前端

```bash
cd apps/chat_frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，通过 SSE 实时接收执行事件。

## 项目结构

```
cc-3/
├── src/cc3/                  # 核心库
│   ├── cli.py                #   Typer CLI 入口
│   ├── executor.py           #   Claude CLI 执行器
│   ├── claude_cmd.py         #   CLI 命令构建器
│   ├── stream_parser.py      #   NDJSON 流解析
│   ├── events.py             #   事件归一化
│   ├── session.py            #   会话管理
│   ├── locking.py            #   workspace 文件锁
│   ├── scaffold.py           #   agent 脚手架
│   ├── config.py             #   配置加载
│   ├── paths.py              #   路径工具
│   ├── runner.py             #   服务端 library 入口
│   └── orchestrator/
│       └── graph.py          #   LangGraph 编排图
├── agents/                   # Agent 配置目录
│   └── demo/                 #   示例 agent
├── apps/
│   ├── chat_api/             # FastAPI 后端
│   └── chat_frontend/        # React + Vite 前端
├── tests/                    # 单元测试
├── main.py                   # 运行入口（无需安装）
├── pyproject.toml            # 项目配置与依赖
└── design.md                 # 架构设计文档
```

## 测试

```bash
# 运行全部测试（需禁用 langsmith 插件避免冲突）
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q

# 或使用 pytest.ini 中已配置的选项
pytest
```

测试覆盖：NDJSON 解析、事件归一化、workspace 锁、session 持久化、executor artifacts 生成。

## 依赖

| 包 | 用途 |
|----|------|
| `langgraph` >= 0.2.0 | Agent 编排框架 |
| `typer` >= 0.12 | CLI 框架 |
| `pyyaml` >= 6.0 | YAML 配置解析 |
| `filelock` >= 3.13 | workspace 文件锁 |
| `fastapi` >= 0.110 | Chat API 后端（可选） |
| `uvicorn` >= 0.25 | ASGI 服务器（可选） |

## License

MIT
