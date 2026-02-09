# 1 目标与核心思路

## 1.1 目标

- LangGraph 做 **Plan / Router / Memory / Policy / Tool orchestration**
    
- Claude Code CLI 做 **执行层 Agent**：充分利用它的 tools/skills/grep、会话记忆、cwd 绑定、`.env` 注入（API_KEY/BASE_URL）
    

## 1.2 核心思路

- **每个 LangGraph step 启一个 Claude CLI 
gent 可独立配置不同网关/模型/权限策略
    

---

# 2 组件架构
```
┌───────────────────────────────┐
│            App / API           │  (可选：HTTP API / CLI / UI)
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│         Session Manager         │ 负责：workspace/session_id/锁/回收
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│        LangGraph Orchestrator   │ Plan/Tool routing/Memory/Policy
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│       Claude CLI Executor       │ spawn + stream-json parser + resume
└───────────────┬───────────────┘
                │
         ┌──────▼───────┐
         │ claude (CLI) │  tools/skills/grep/session persistence
         └──────────────┘

```

> 关键点：**LangGraph 不直接执行 bash/grep**，而是把“执行任务”交给 Claude CLI；LangGraph 做上层策略与审计。

---

# 3 目录与脚手架规范（推荐）

每个 Agent 一个 workspace（便于 KB + skills + .env 隔离）：
```
agents/
  my_agent/
    agent.yaml            # agent 元信息（模型、permissionMode、策略）
    system_prompt.md      # 让 Claude CLI 执行时遵守的总指令
    policies.md           # 允许/禁止的行为（可选）
    skills/               # 你扩展的 Claude CLI skills/插件（按 CLI 支持方式组织）
workspaces/
  my_agent/
    .env                  # ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL / MODEL 等
    kb/                   # 文档库（grep/read 的目标）
    repo/                 # 可选：代码仓库（CLI tools 会用）
    runs/                 # 每次运行日志与事件归档

```


> 你可以把 `workspaces/<agent>/kb` 当 “简单知识库”，让 Claude CLI 直接 grep/Read。

---

# 4 会话模型与生命周期

## 4.1 Session 的定义

- 一个 Session = `{agent_id, workspace_path, claude_session_id, created_at, last_active_at, lock_state}`
    

## 4.2 生命周期

- `create_session(agent_id)`
    
    - 选择/创建 workspace
        
    - 读 `.env`
        
    - 初始化 LangGraph state
        
    - `claude_session_id` 为空（首次调用时由 CLI 生成）
        
- `run_step(session, instruction)`
    
    - spawn `claude -p --verbose --output-format stream-json`
        
    - 如果存在 `claude_session_id`：追加 `--resume <id>`
        
    - 实时解析事件流
        
    - 更新 `claude_session_id`（从 init/result 事件取）
        
- `close_session(session)`
    
    - 写入 session 元数据（最近 session_id、摘要、统计）
        
    - 可选：归档 runs
        

## 4.3 并发与分支（LangGraph 分叉）

- 如果一个会话可能被并发调用：必须加 **会话锁**
    
- LangGraph 需要分支推演（what-if）：
    
    - 用 CLI 参数 `--fork-session --resume <session_id>` 开新 session，避免互相污染
        

---

# 5 Claude CLI Executor 设计（接口与行为）

## 5.1 执行器接口（概念）

- `execute(instruction, workspace, session_id?, options) -> EventStream + FinalResult`
    
- `abort(run_id)`（可选，杀子进程）
    

## 5.2 关键 options（建议支持）

- `permission_mode`: default / dontAsk / bypassPermissions / plan（按你的安全策略）
    
- `model`: 可从 `.env` 或 agent.yaml 控制
    
- `timeout_s`: 超时强制终止
    
- `max_cost` / `budget`（可选：你可以在上层做）
    
- `continue_mode`: resume/session_id/continue（默认 resume）
    

## 5.3 固定参数（你已验证）

- `-p --verbose --output-format stream-json`
    

## 5.4 事件流解析（你需要的最小事件集合）

从 stream-json 中抽象成统一事件：

- `InitEvent`
    
    - `session_id`
        
    - `cwd`
        
    - `tools[]`, `skills[]`, `model`, `permissionMode`, `apiKeySource`
        
- `AssistantDeltaEvent`
    
    - `kind`: thinking / text
        
    - `delta`: 逐段文本
        
- `ToolEvent`（可选，取决于 CLI 是否输出）
    
    - tool_name, input, output, status
        
- `ResultEvent`
    
    - `is_error`
        
    - `result_text`
        
    - `usage/cost`
        
    - `session_id`
        
- `ErrorEvent`
    
    - error code/message（例如 auth failed）
        

> 你可以先只实现 Init/Assistant(text)/Result/Error，工具细节后续再增强。

---

# 6 LangGraph 侧设计（节点与状态）

## 6.1 State（建议字段）

- `agent_id`
    
- `workspace_path`
    
- `claude_session_id`（关键）
    
- `conversation_history`（可选：你也可以只依赖 CLI session）
    
- `artifacts`（检索/摘要/引用片段）
    
- `policy_flags`（是否允许联网/编辑文件/执行 bash 等）
    
- `last_run_metrics`（成本/耗时/工具数）
    

## 6.2 Node 划分（推荐最小可用）

1. `PlannerNode`（LangGraph LLM 或规则）
    

- 输入：用户目标 + 当前 state 摘要
    
- 输出：一组 steps（每步给 “执行指令” + 是否需要工具/检索）
    

2. `ClaudeExecNode`（核心）
    

- 输入：step 指令（由 Planner 生成）
    
- 调用 Executor 执行 CLI
    
- 输出：step 结果文本 + 更新 session_id + 事件摘要（工具/检索证据）
    

3. `Verifier/ReflectNode`（可选但很有用）
    

- 检查结果是否满足目标
    
- 决定下一步（继续/修正/终止）
    

4. `MemoryNode`（可选）
    

- 将关键结论写入你自己的长期 memory（而不是依赖 CLI 上下文无限增长）
    

> 注意：你可以让 LangGraph 的 Planner 更轻量，真正检索/操作都交给 Claude CLI。

---

# 7 “把文档当 KB”的检索策略

你要的是“简单知识库”，推荐两层：

## 7.1 层 1：Claude CLI 自己 grep/read

- 让执行指令包含明确要求：
    
    - 在 `kb/` 下 grep 关键词
        
    - 输出命中片段 + 文件路径 + 行号
        
- 你在解析结果时可以再结构化这些引用
    

## 7.2 层 2：脚手架提供“约束与模板”

在 system_prompt.md 里要求：

- 引用必须包含：`file:line_start-line_end` 或 `path:line`
    
- 先检索再回答，避免编造
    
- 命中不足时要说明“不足”并建议补充文档
    

这样你不需要先做向量化，就能有可用的 KB 体验。

---

# 8 安全与权限策略（必须设计）

Claude CLI tools 能做很多事（读写文件、bash、webfetch 等）。你要脚手架可复用，建议支持三档：

- **safe**：只允许 Read/Grep/Glob，不允许 Edit/Write/Bash/Web
    
- **dev**：允许 Edit/Write/Bash，但限制在 workspace 内
    
- **open**：允许 WebFetch/WebSearch（若你允许联网）
    

落地方式：

- 通过 CLI 的 `--permission-mode`（你 help 里已经有）
    
- 以及系统 prompt 的强约束（双保险）
    
- 再加一层：在 Executor 启动前设置工作目录与文件系统边界（比如容器或沙箱，视你部署）
    

---

# 9 可观测性与回放（强烈建议内置）

每次执行（run）都写入 `workspaces/<agent>/runs/<timestamp>/`：

- `events.ndjson`：原始 stream-json（最重要）
    
- `result.txt`：最终输出
    
- `meta.json`：session_id、cwd、model、cost、duration、exit code
    
- `step.json`：LangGraph step 输入输出（用于复盘）
    

这样你调试 tool 行为、grep 结果、成本都很容易。

---

# 10 失败处理与重试策略

常见失败类型与处理：

1. **auth/config 错误**
    

- 从 InitEvent 的 `apiKeySource` 检测
    
- 若为 none：明确提示缺少 env 或登录态
    

2. **权限询问导致卡住**
    

- 设置 timeout；超时 kill
    
- 建议在“无人值守模式”下用 `permission_mode=dontAsk`（或按你的策略）
    

3. **CLI 崩溃/输出损坏**
    

- 记录 events.ndjson
    
- 重试一次（可选）
    
- 若 session_id 已拿到，用 `--resume` 继续
    

4. **并发污染**
    

- session 锁
    
- 分支用 `--fork-session`
    

---

# 11 你应当给 AI 编程工具的“开发任务拆分清单”

（你可以直接把这份拆分丢给代码生成工具）

1. 脚手架初始化命令：`init-agent <name>`
    

- 生成 agents/<name>/、workspaces/<name>/、模板文件
    

2. SessionManager
    

- create/load session
    
- per-session lock
    
- idle cleanup（可选）
    

3. ClaudeCliExecutor
    

- spawn（cwd/env）
    
- stream-json parser（必须）
    
- session_id 更新（init/result）
    
- timeout & kill
    
- 输出 events.ndjson + meta.json
    

4. LangGraph graph
    

- Planner → Exec → Reflect（最小闭环）
    
- state 持久化（session_id 关键）
    

5. 策略配置
    

- agent.yaml：permissionMode、默认模型、是否允许 web
    
- system_prompt.md：引用格式、先检索后回答、工具使用规范
    

---

# 12 推荐的默认“系统提示词”要点（给你的脚手架模板）

system_prompt.md 建议包含：

- 你是执行型 agent，优先使用工具在 workspace 下检索/读文件
    
- 回答必须带证据引用：`path:line` 或 `path:range`
    
- 不确定就说明不确定，并建议需要的文档
    
- 不允许越界访问 workspace 外
    
- 遵循 permissionMode（若是 safe 模式，不用写文件、不跑 bash）