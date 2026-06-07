# OpenCode 插件深度研究报告

**创建时间**: 2026-05-25 08:01:57  
**版本**: v1.4  
**作者**: 小沈  
**项目**: OmniAgentAs-desk（React+FastAPI 全栈应用，Windows 平台）  
**来源**: [opencode.ai/docs/ecosystem](https://opencode.ai/docs/ecosystem/), [awesome-opencode](https://github.com/awesome-opencode/awesome-opencode)

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-25 08:01:57 | 小沈 | 初始版本，9 个候选插件深度研究 |
| v1.1 | 2026-05-25 10:30:00 | 小沈 | 补充 opencode-snip、opencode-mem 两个插件研究，更新推荐配置 |
| v1.2 | 2026-05-25 11:00:00 | 小沈 | Claude Code 兼容插件分析，新增 cc-safety-net |
| v1.3 | 2026-05-25 11:35:00 | 小沈 | oh-my-opencode → oh-my-openagent 更名，更新配置示例 |
| v1.4 | 2026-05-25 09:28:33 | 小沈 | 安装 oh-my-openagent 实际过程记录：CLI 安装器、订阅问答、agent 模型配置生成与自定义 |

---

## 一、研究背景与目标

### 1.1 背景

当前 `opencode.jsonc` 中已配置 3 个插件：
- `@tarquinen/opencode-smart-title@latest` — 智能标题生成
- `opencode-antigravity-auth@1.4.6` — 免费模型认证
- `opencode-superpowers@latest` — 超级工具集

为进一步提升开发效率，从 [OpenCode 官方生态系统](https://opencode.ai/docs/ecosystem/) 中筛选出 9 个候选插件进行深度研究。

### 1.2 评估标准

| 维度 | 权重 | 说明 |
|------|------|------|
| **项目相关性** | 高 | 对 React+FastAPI 全栈、Windows 平台的适用性 |
| **成熟度** | 高 | Stars 数、维护状态、更新频率 |
| **成本效益** | 中 | 安装复杂度 vs 收益 |
| **兼容性** | 中 | Windows 平台支持程度 |
| **风险** | 中 | 是否需要额外 API key、是否需要 WSL |

---

## 二、插件深度分析

### 2.1 opencode-dynamic-context-pruning（DCP）

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/Tarquinen/opencode-dynamic-context-pruning |
| **Stars** | ~3,000 |
| **最新版本** | v3.1.12（2026-05-12） |
| **npm 包名** | `@tarquinen/opencode-dcp` |
| **推荐度** | **✅ P1 - 强烈推荐** |

**功能描述**：智能管理对话上下文，通过压缩、去重和错误清理优化 token 使用。会话历史本身不被修改——仅发送给 LLM 前用占位符替换。

**关键特性**：
- **Compress（压缩）**：已关闭的对话替换为技术摘要，支持 `range`（连续跨度）和 `message`（独立消息）模式
- **Deduplication（去重）**：相同工具+相同参数调用仅保留最近一次输出
- **Purge Errors（错误清理）**：可配置轮次后修剪错误工具调用
- **保护机制**：子代理、技能、文件操作不被修剪
- **6 个可编辑提示词**：system、compress-range、compress-message 等
- **配置灵活**：全局/项目级配置文件，按模型设置上下文限制

**平台兼容性**：✅ Windows / Linux / Mac（纯 TypeScript，无平台依赖）

**项目相关性**：**高** — 项目中的 Agent 系统在 ReAct 循环中会生成大量工具调用输出，DCP 能显著减少 token 消耗。配置优先级（项目 > 全局）与多环境开发流程匹配。

**安装方式**：
```json
// opencode.jsonc
{
  "plugin": ["@tarquinen/opencode-dcp"]
}
```

---

### 2.2 opencode-type-inject

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/nick-vi/opencode-type-inject |
| **Stars** | ~125 |
| **npm 包名** | `@nick-vi/opencode-type-inject` |
| **推荐度** | **❓ P3 - 可选** |

**功能描述**：AI 读取 TypeScript/Svelte 文件时自动注入类型签名，提供类型错误反馈和类型查找工具。

**关键特性**：
- **自动类型注入（Read Hook）**：读文件时提取类型签名，解析 4 层深度导入
- **类型检查（Write Hook）**：写文件后自动运行类型检查并报告
- **3 个 MCP 工具**：`lookup_type`、`list_types`、`type_check`
- **Token 预算**：基于优先级的排序（函数签名 > 使用类型 > 其他）

**平台兼容性**：✅ Windows / Linux / Mac（需要 tsconfig.json）

**项目相关性**：**中** — 前端（TypeScript）有帮助，后端（Python）无帮助。AGENTS.md 已包含架构说明，额外价值有限。

---

### 2.3 opencode-vibeguard

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/inkdust2021/opencode-vibeguard |
| **Stars** | ~121 |
| **npm 包名** | `opencode-vibeguard` |
| **推荐度** | **✅ P2 - 推荐** |

**功能描述**：敏感字符串（API 密钥、令牌、PII）在发送到 LLM 前替换为 HMAC-SHA256 占位符，输出后自动恢复。

**关键特性**：
- **请求前脱敏**：`__VG_CATEGORY_hash__` 格式占位符替换
- **输出后自动恢复**：模型输出+工具执行前恢复原始值
- **历史工具输入/输出脱敏**：防纯文本泄露
- **HMAC-SHA256 哈希**：会话随机密钥，对提供商不可逆

**平台兼容性**：✅ Windows / Linux / Mac（纯 JavaScript）

**项目相关性**：**高** — 项目中处理 API 密钥、数据库凭证、配置文件敏感信息。`command_security.py` 已有安全检查，vibeguard 作为补充层。

---

### 2.4 opencode-pty

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/shekohex/opencode-pty |
| **Stars** | ~437 |
| **npm 包名** | `opencode-pty` |
| **推荐度** | **❌ 不推荐** |

**功能描述**：交互式 PTY（伪终端）管理，支持后台进程、交互式输入、多会话管理。包含 Web UI。

**关键特性**：
- 后台执行（dev server、watch 模式、数据库）
- 多会话管理 + 交互式输入
- 输出缓冲（分页/正则过滤）
- Web UI（React + WebSocket）

**平台兼容性**：⚠️ Windows 有限（依赖 Bun PTY 实现）

**项目相关性**：**低** — 依赖简单（uvicorn + npm run dev），不需要复杂后台进程管理。Windows PTY 支持不稳定。

---

### 2.5 opencode-shell-strategy

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/JRedeker/opencode-shell-strategy |
| **Stars** | ~101 |
| **安装方式** | `opencode.jsonc` 的 `"instructions"` 数组引用 |
| **推荐度** | **✅ P0 - 立即安装** |

**功能描述**：纯 Markdown 指令文件，教导 LLM 在无 TTY 环境使用正确命令行标志，防止命令挂起。

**关键特性**：
- **包管理器**：`npm init -y`、`apt install -y`、`pip install --no-input`
- **Git 操作**：`commit -m`、`merge --no-edit`、`add .`
- **安全命令**：`rm -f`、`ssh -o BatchMode=yes`、`unzip -o`
- **禁用命令**：`vim`、`nano`、`less`、`man`、`python` REPL
- **零运行时开销**：纯文本指令，无需编译

**平台兼容性**：✅ Windows / Linux / Mac

**项目相关性**：**高** — Windows PowerShell 环境下，LLM 经常生成交互式命令导致挂起。零成本解决问题。

**安装方式**：
```json
{
  "instructions": [
    "https://raw.githubusercontent.com/JRedeker/opencode-shell-strategy/main/shell_strategy.md"
  ]
}
```

---

### 2.6 opencode-skillful

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/zenobi-us/opencode-skillful |
| **Stars** | ~304 |
| **npm 包名** | `@zenobius/opencode-skillful` |
| **推荐度** | **❌ 不推荐** |

**功能描述**：按需延迟加载技能提示，支持技能发现、注入和资源读取。实现 Anthropic Agent Skills 规范。

**关键特性**：
- 按需加载（`skill_find` / `skill_use` / `skill_resource`）
- 多格式渲染（XML/JSON/Markdown）
- 全局/项目级技能目录

**平台兼容性**：✅ Windows / Linux / Mac

**项目相关性**：**低** — **项目已于 2026-02-14 归档（只读）**。AGENTS.md 已提供结构化指令，不需要额外技能系统。

---

### 2.7 opencode-supermemory

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/supermemoryai/opencode-supermemory |
| **Stars** | ~1,200 |
| **npm 包名** | `opencode-supermemory` |
| **推荐度** | **✅ P1 - 强烈推荐** |

**功能描述**：跨会话持久记忆。AI 能跨会话、跨项目记住用户告诉它的内容。支持画像、项目知识、语义搜索和自动记忆提取。

**关键特性**：
- **上下文注入**：用户画像（跨项目）+ 项目记忆（所有知识）+ 语义搜索
- **关键词检测**："remember"、"save this" 等自动保存
- **`/supermemory-init`**：探索并记忆代码库结构、模式和约定
- **主动压缩**：上下文达 80% 容量时自动摘要保存
- **隐私保护**：`<private>` 标签中内容不存储

**平台兼容性**：✅ Windows / Linux / Mac（需要 Supermemory API key）

**项目相关性**：**高** — 复杂架构（React+FastAPI、多个 Agent 类型、工具注册系统），跨会话记忆能帮助 AI 记住项目约定。

**注意事项**：需要 [supermemory.ai](https://supermemory.ai) 账户和 API key。

---

### 2.8 opencode-morph-fast-apply

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/JRedeker/opencode-morph-fast-apply |
| **Stars** | ~140 |
| **npm 包名** | `github:JRedeker/opencode-morph-fast-apply` |
| **推荐度** | **❓ P3 - 可选** |

**功能描述**：通过 Morph Fast Apply API 实现 10,500+ tokens/sec 代码编辑。支持惰性编辑标记和智能合并。

**关键特性**：
- 超高速编辑（10.5k tokens/sec）
- 惰性编辑标记 `// ... existing code ...`
- 98% 准确率代码合并
- 飞行前验证 + 灾难性截断检测
- 优雅降级（API 失败退回原生 `edit`）

**平台兼容性**：✅ Windows / Linux / Mac（需要 Morph API key）

**项目相关性**：**中** — 对大型重构有价值。但需额外付费 API，内置 `edit` 工具已能满足日常需求。

---

### 2.9 oh-my-opencode → oh-my-openagent（已正式更名）

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/code-yeongyu/oh-my-openagent |
| **Stars** | ~59,300 |
| **npm 包名** | `oh-my-openagent`（旧名 `oh-my-opencode` 仍可用但报警告） |
| **opencode.jsonc 插件名** | `oh-my-openagent`（旧名 `oh-my-opencode` 兼容加载报警告） |
| **推荐度** | **✅ P0 - 立即安装** |

**功能描述**：最受欢迎的 OpenCode 增强包。多 agent 编排、后台 agent、LSP/AST 工具、哈希锚定编辑、团队模式、Prometheus 规划器。本质上是 OpenCode 的"超级增强版"。

**关键特性**：

| 特性 | 说明 |
|------|------|
| **`ultrawork`/`ulw`** | 一键启动所有 agent，不完成不停止 |
| **多 Agent 编排** | Sisyphus（编排器）、Hephaestus（工作者）、Prometheus（规划器） |
| **团队模式（v4.0）** | 1 领导 + 最多 8 并行成员，tmux 可视化 |
| **哈希锚定编辑（Hashline）** | 基于内容哈希的行引用，编辑成功率 6.7%→68.3% |
| **LSP + AST-Grep** | 工作区重命名、AST 感知代码搜索 |
| **后台 Agent** | 并行 5+ 专业 agent，上下文保持精简 |
| **内置 MCP** | Exa（搜索）、Context7（文档）、Grep.app（GitHub 搜索） |

**平台兼容性**：⚠️ 核心功能 Windows 可用，团队模式 tmux 可视化需 WSL

**项目相关性**：**高** — 多 agent 编排适合复杂架构（多个 Agent 类型、工具注册系统）。哈希锚定编辑解决编辑错误问题。

### 2.9.1 安装过程（实际操作记录）

`oh-my-openagent` **不是简单加到 `plugin` 数组就完事**，它自带的 CLI 安装器负责完整的配置流程：

**安装命令**：
```bash
# 非交互式安装（需根据订阅情况传参）
npx oh-my-openagent install --no-tui --claude=no --openai=no --gemini=no --copilot=no --opencode-go=yes
```

**安装前需回答的订阅问题**（CLI 安装器会逐一询问）：

| 问题 | 影响 |
|------|------|
| 是否有 Claude Pro/Max 订阅？ | 决定 Sisyphus 主控 agent 模型 |
| 是否有 OpenAI/ChatGPT Plus？ | 决定 Hephaestus/Oracle 等 GPT-native agent |
| 是否有 Gemini？ | 决定视觉/前端 agent |
| 是否有 GitHub Copilot？ | 作为 fallback provider |
| 是否有 OpenCode Go？ | 提供 GLM-5/5.1, Kimi K2.5/K2.6, MiniMax M2.7 |
| 是否有 Z.ai Coding Plan？ | GLM-5/GLM-4.6v |
| 是否有 Kimi for Coding？ | Kimi K2.5 |
| 是否有 OpenCode Zen？ | opencode/ 前缀模型 |
| 是否有 Vercel AI Gateway？ | 通用代理 |

**安装器执行流程**：
1. 检查 OpenCode 安装
2. 自动添加 `oh-my-openagent` 到 `opencode.jsonc` 的 `plugin` 数组
3. 根据订阅参数生成 `~/.config/opencode/oh-my-openagent.json`（独立配置文件）
4. 配置各 agent 的默认模型和 fallback chain

**本机实际安装结果**（用户仅持 OpenCode Go 订阅）：
- `opencode.jsonc` 已加入 `oh-my-openagent@latest` ✅
- `~/.config/opencode/oh-my-openagent.json` 已生成 ✅
- 各 agent 模型按 OpenCode Go 订阅自动配置

### 2.9.2 Agent 模型配置（oh-my-openagent.json）

安装器生成的独立配置文件位于 `~/.config/opencode/oh-my-openagent.json`，包含所有 agent 的模型分配。

**初始配置（OpenCode Go 订阅自动分配）**：
```json
{
  "agents": {
    "sisyphus":  { "model": "opencode-go/kimi-k2.6" },
    "oracle":    { "model": "opencode-go/glm-5.1" },
    "prometheus":{ "model": "opencode-go/glm-5.1" },
    "metis":     { "model": "opencode-go/glm-5.1" },
    "momus":     { "model": "opencode-go/glm-5.1" },
    "librarian": { "model": "opencode-go/qwen3.5-plus",
                   "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] },
    "explore":   { "model": "opencode-go/qwen3.5-plus",
                   "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] },
    "multimodal-looker": { "model": "opencode-go/kimi-k2.6" },
    "atlas":     { "model": "opencode-go/kimi-k2.6",
                   "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] },
    "sisyphus-junior": { "model": "opencode-go/kimi-k2.6",
                         "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] }
  },
  "categories": {
    "visual-engineering": { "model": "opencode-go/glm-5.1" },
    "ultrabrain":         { "model": "opencode-go/glm-5.1" },
    "deep":              { "model": "opencode-go/kimi-k2.6", "fallback_models": [{"model": "opencode-go/glm-5.1"}] },
    "artistry":          { "model": "opencode-go/kimi-k2.6", "fallback_models": [{"model": "opencode-go/glm-5.1"}] },
    "quick":             { "model": "opencode-go/minimax-m2.7" },
    "unspecified-low":   { "model": "opencode-go/kimi-k2.6", "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] },
    "unspecified-high":  { "model": "opencode-go/kimi-k2.6", "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] },
    "writing":           { "model": "opencode-go/kimi-k2.6", "fallback_models": [{"model": "opencode-go/minimax-m2.7"}] }
  }
}
```

**用户自定义后的最终配置**（2026-05-25）：

| Agent | 初始模型（OpenCode Go） | 自定义后 |
|-------|------------------------|---------|
| **Sisyphus** | `opencode-go/kimi-k2.6` | `opencode/big-pickle` |
| **Oracle** | `opencode-go/glm-5.1` | `opencode/deepseek-v4-flash-free` |
| **Prometheus** | `opencode-go/glm-5.1` | `opencode/deepseek-v4-flash-free` |
| **Metis** | `opencode-go/glm-5.1` | `opencode/deepseek-v4-flash-free` |
| **Momus** | `opencode-go/glm-5.1` | `opencode/deepseek-v4-flash-free` |
| 其他 agent | 保持不变 | 保持不变 |

**注意事项**：
- Windows tmux 集成可能需要 WSL
- 功能丰富，需学习曲线
- 会显著改变开发体验
- 建议从 `ultrawork` + 哈希锚定编辑开始
- **安装的特殊性**：不能仅通过 `plugin` 数组安装，必须运行 CLI 安装器，它会创建独立配置文件和 model fallback chain

---

### 2.10 opencode-snip

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/VincentHardouin/opencode-snip |
| **Stars** | ~100 |
| **npm 包名** | `opencode-snip@latest` |
| **推荐度** | **❓ P3 - 可选（需额外安装 snip CLI）** |

**功能描述**：自动使用 `tool.execute.before` 钩子将所有 shell 命令前缀加上 [snip](https://github.com/edouard-claude/snip) CLI 代理，将 shell 输出过滤后再进入 LLM 上下文窗口，减少 60-90% token 消耗。

**关键特性**：
- **零配置 hook**：安装后自动为所有命令加 `snip` 前缀
- **大幅节省 token**：

  | 命令 | 原始 tokens | 过滤后 | 节省率 |
  |------|------------|--------|--------|
  | `go test ./...` | 689 | 16 | **97.7%** |
  | `git log` | 371 | 53 | **85.7%** |
  | `cargo test` | 591 | 5 | **99.2%** |

- **127 个内置 YAML 过滤器**：覆盖 git、go、cargo、python、npm、docker、k8s 等 80+ 工具
- **19 种管道动作**：keep_lines、remove_lines、truncate_lines、json_extract、aggregate 等
- **自定义过滤器**：用户可在 `~/.config/snip/filters/` 下写 YAML 文件
- **被动退场**：不匹配过滤器的命令原样通过

**前置依赖**：
```bash
# 需先安装 snip CLI（Go 语言编写，跨平台）
go install github.com/edouard-claude/snip/cmd/snip@latest
```

**平台兼容性**：⚠️ snip CLI 为 Go 语言编写（CGO_ENABLED=0），支持 Windows 编译。但 snip 的工具过滤匹配逻辑主要针对 Unix 生态（bash/zsh），Windows PowerShell 下验证不足。OpenCode 的 `tool.execute.before` 钩子本身在 Windows 上正常工作。

**项目相关性**：**中** — 对减少 token 消耗有价值，尤其在频繁运行 `pytest`、`git`、`npm` 命令的场景。但需要额外安装 snip CLI，Windows 兼容性未验证。

**注意事项**：
- 需先 `go install snip` 或下载预编译二进制
- snip 的过滤器生态以 Unix 命令为主（`go test`、`cargo` 等），PowerShell 命令（`Select-String`、`Get-ChildItem`）可能不被识别
- 插件的 `v1.6.1` 版本已支持管道命令（修复 jq 表达式问题）
- snip 项目本身 v0.16.0，更新活跃（266 stars, 26 个 release）

---

### 2.11 opencode-mem

| 字段 | 值 |
|------|-----|
| **GitHub** | https://github.com/tickernelz/opencode-mem |
| **Stars** | ~719 |
| **npm 包名** | `opencode-mem` |
| **推荐度** | **✅ P1 - 强烈推荐（本地记忆替代方案）** |

**功能描述**：为 AI 编程助手提供持久化记忆的本地向量数据库插件。使用 SQLite + USearch 实现本地优先的语义搜索，无需外部 API。

**关键特性**：

| 特性 | 说明 |
|------|------|
| **本地优先架构** | SQLite 持久化存储 + USearch 向量索引（失败自动回退 ExactScan） |
| **自动用户画像** | 分析交互模式，学习编码风格、技术栈偏好、项目模式 |
| **Web UI** | 内置管理界面，访问 http://127.0.0.1:4747 |
| **12+ 本地嵌入模型** | 支持 text-embedding-3-small、all-MiniLM-L6-v2 等，默认 opt-in |
| **多 Provider 支持** | 复用 OpenCode 的 session API，无需额外 API key |
| **智能去重** | 基于语义相似度的记忆去重 |
| **信息自主提取** | LLM 自动决定何时保存/检索记忆，无侵入 |
| **自动对话捕获** | 可选自动同步会话内容到记忆库 |

**平台兼容性**：✅ Windows / Linux / Mac（纯 Node.js/Bun 实现）

**项目相关性**：**高** — 与 opencode-supermemory 功能定位重叠但架构不同。

**与 opencode-supermemory 对比**：

| 维度 | opencode-supermemory | opencode-mem |
|------|---------------------|-------------|
| 数据存储 | 云端（supermemory.ai） | 本地 SQLite + USearch |
| 是否需要 API key | ✅ 需要 supermemory.ai key | ❌ 不需要（复用 opencode providers） |
| 嵌入模型 | 云端模型 | 本地模型（12+ 可选） |
| Stars | ~1,200 | ~719 |
| 版本 | 无版本号 | v2.14.3（59 个 release，非常活跃） |
| 隐私性 | 数据在云端 | 数据在本地 |
| 安装 | 一键 npm | 一键 npm |
| Web UI | 无 | 有（http://127.0.0.1:4747） |

**注意事项**：
- 推荐使用 Bun 运行时（性能更优）
- macOS 需要 Homebrew SQLite（Apple 内置 SQLite 禁用扩展加载）
- 项目目前在寻找新的维护者（Issue #79: "[Maintainer Wanted]"）
- 社区活跃度很高：22 名贡献者，59 个 release
- 与 supermemory 二选一即可，不建议同时安装

---

## 三、总结与优先级建议

### 3.1 推荐度总览

| 优先级 | 插件 | 推荐度 | Stars | 复杂度 | 关键价值 |
|--------|------|--------|-------|--------|---------|
| **P0** | oh-my-openagent | ✅ 立即安装 | 59.3k | 高 | 多 Agent 编排，哈希编辑 |
| **P0** | opencode-shell-strategy | ✅ 立即安装 | 101 | 零 | 防命令挂起 |
| **P1** | opencode-dynamic-context-pruning | ✅ 强烈推荐 | 3k | 低 | 节省 token |
| **P1** | opencode-supermemory | ✅ 强烈推荐 | 1.2k | 中 | 跨会话记忆（云端） |
| **P1** | opencode-mem | ✅ 强烈推荐 | 719 | 中 | 跨会话记忆（本地） |
| **P2** | cc-safety-net | ✅ 推荐 | 1.4k | 低 | 防 AI 误删代码，跨5种 AI 工具 |
| **P2** | opencode-vibeguard | ✅ 推荐 | 121 | 低 | 安全防护 |
| **P3** | opencode-snip | ❓ 可选 | 100 | 低 | 需额外安装 snip CLI |
| **P3** | opencode-type-inject | ❓ 可选 | 125 | 低 | 仅 TS 帮助 |
| **P3** | opencode-morph-fast-apply | ❓ 可选 | 140 | 中 | 需要付费 API |
| **❌** | opencode-pty | ❌ 不推荐 | 437 | 高 | Windows 受限 |
| **❌** | opencode-skillful | ❌ 不推荐 | 304 | 低 | 已归档 |

### 3.2 推荐安装顺序

```
第1步（零成本）：
  - opencode-shell-strategy（instructions 引用，纯 Markdown）
  - oh-my-openagent（npm 包，立即提升）

第2步（低成本高收益）：
  - opencode-dynamic-context-pruning（节省 token）
  - opencode-supermemory 或 opencode-mem（二选一）

第3步（安全加固）：
  - cc-safety-net（防 AI 误删代码，1.4k stars，跨5种 AI）
  - opencode-vibeguard（敏感信息脱敏）

第4步（按需）：
  - opencode-type-inject（仅 TS 项目）
  - opencode-morph-fast-apply（大量重构时）
  - opencode-snip（安装 snip CLI 后启用）
```

### 3.3 当前配置与建议配置对比

**当前（6 个插件 + 1 个独立配置文件，2026-05-25）**：

`opencode.jsonc` 的 `plugin` 数组：
```json
{
  "plugin": [
    "@tarquinen/opencode-smart-title@latest",
    "opencode-antigravity-auth@1.4.6",
    "opencode-superpowers@latest",
    "oh-my-openagent@latest",
    "opencode-supermemory@latest",
    "cc-safety-net@latest"
  ]
}
```

`oh-my-openagent` 独立配置 `~/.config/opencode/oh-my-openagent.json`（含 agent 模型分配，详见 2.9.2）。

**建议最终配置（7 个插件 + 1 指令 + 1 独立配置）**：
```json
{
  "plugin": [
    "@tarquinen/opencode-smart-title@latest",
    "opencode-antigravity-auth@latest",
    "opencode-superpowers@latest",
    "oh-my-openagent@latest",
    "opencode-supermemory@latest",
    "cc-safety-net@latest",
    "@tarquinen/opencode-dcp@latest"
  ],
  "instructions": [
    // ... 现有 instructions ...
    "https://raw.githubusercontent.com/JRedeker/opencode-shell-strategy/main/shell_strategy.md"
  ]
}
```

**记忆插件二选一说明**：
- `opencode-supermemory` — 云端记忆，需 supermemory.ai API key，无需本地资源
- `opencode-mem` — 本地记忆，无需外部 API key，需本地 CPU 做向量嵌入
- 建议：如有 supermemory.ai 账户 → 用 supermemory；如注重隐私或不想注册 → 用 opencode-mem

---

## 四、参考资料

- [OpenCode 官方文档 - 插件](https://opencode.ai/docs/plugins/)
- [OpenCode 官方文档 - 生态系统](https://opencode.ai/docs/ecosystem/)
- [awesome-opencode](https://github.com/awesome-opencode/awesome-opencode)
- [opencode.cafe](https://opencode.cafe) — 社区聚合站
- [OpenCode CLI Cheat Sheet](http://computingforgeeks.com/opencode-cli-cheat-sheet)
- [OpenCode 插件开发指南](https://gist.github.com/rstacruz/946d02757525c9a0f49b25e316fbe715)

---

**文档完成时间**: 2026-05-25 09:28:33
