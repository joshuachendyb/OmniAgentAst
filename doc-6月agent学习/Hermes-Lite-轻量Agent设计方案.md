# Hermes-Lite：轻量 Agent 模式设计方案

> **设计日期：** 2026-06-02  
> **目标：** 在不重写 Agent 的前提下，提供一个对标 OpenCode 的精简模式  
> **原则：** 只加条件分支，不改核心逻辑；瘦掉的子系统做成可插拔模块  

---

## 目录

- [1. 设计目标](#1-设计目标)
- [2. 瘦身清单](#2-瘦身清单)
- [3. 实现方案](#3-实现方案)
- [4. 瘦掉的部分如何模块化复用](#4-瘦掉的部分如何模块化复用)
- [5. 模块重组架构图](#5-模块重组架构图)
- [6. 用户接口设计](#6-用户接口设计)
- [7. 效果预估](#7-效果预估)
- [8. 渐进式升级路径](#8-渐进式升级路径)

---

## 1. 设计目标

| 目标 | 指标 |
|------|------|
| 初始化路径 | 从 ~1,400 行 → ~200 行 |
| 系统提示词 | 从 ~15,000 字符 → ~500 字符 |
| 循环每轮开销 | 去掉记忆/技能/压缩/护栏检查 |
| 等效功能 | 对标 OpenCode（编码 + 基础工具） |
| 兼容性 | 不改现有 API，不影响 Full 模式 |

---

## 2. 瘦身清单

### 2.1 初始化阶段瘦掉的部分

| 子系统 | 代码位置 | 行数 | 可模块化？ |
|--------|---------|------|-----------|
| MemoryManager | `agent_init.py` | ~20 行 init | ✅ → memory plugin |
| ContextCompressor | `agent_init.py` | ~15 行 init | ✅ → context_engine plugin |
| ToolGuardrailController | `agent_init.py` | ~10 行 init | ✅ → security plugin |
| CredentialPool | `agent_init.py` | ~30 行 init | ✅ → credential plugin |
| Skills 扫描 | `agent_init.py` | ~50 行 init | ✅ → skills plugin |
| StreamingThinkScrubber | `agent_init.py` | ~5 行 init | ✅ → think plugin |
| StreamingContextScrubber | `agent_init.py` | ~5 行 init | ✅ → memory plugin |
| SubdirectoryHintTracker | `agent_init.py` | ~10 行 init | ✅ → context plugin |
| Checkpoints | `agent_init.py` | ~20 行 init | ✅ → checkpoint plugin |

### 2.2 循环阶段瘦掉的部分

| 操作 | 代码位置 | 行数 | 可模块化？ |
|------|---------|------|-----------|
| 记忆 prefetch | `conversation_loop.py` | ~30 行 | ✅ → memory plugin hook |
| 记忆 sync | `conversation_loop.py` | ~20 行 | ✅ → memory plugin hook |
| 技能 nudge 检查 | `conversation_loop.py` | ~15 行 | ✅ → skills plugin hook |
| /steer 排空 | `conversation_loop.py` | ~50 行 | ✅ → steer plugin |
| 上下文压缩预检 | `conversation_loop.py` | ~40 行 | ✅ → context_engine plugin |
| 凭证池轮换 | `conversation_loop.py` | ~10 行 | ✅ → credential plugin |
| TODO 状态恢复 | `conversation_loop.py` | ~25 行 | ✅ → todo plugin |
| 思考内容擦除 | `conversation_loop.py` | ~10 行 | ✅ → think plugin |

### 2.3 提示词阶段瘦掉的部分

| 内容块 | 来源 | 字符数 | 可模块化？ |
|--------|------|--------|-----------|
| 技能索引 | `prompt_builder.py` | ~5,000 | ✅ skills plugin |
| 记忆快照 | `prompt_builder.py` | ~3,000 | ✅ memory plugin |
| 用户档案 | `prompt_builder.py` | ~1,000 | ✅ memory plugin |
| AGENTS.md 注入 | `prompt_builder.py` | ~3,000 | ✅ context plugin |
| 专项指导 (Memory/Kanban) | `prompt_builder.py` | ~2,000 | ✅ 各 plugin |
| 平台提示 | `prompt_builder.py` | ~500 | ✅ platform plugin |

### 2.4 瘦不掉的（Agent 本质）

| 组件 | 原因 |
|------|------|
| Provider 适配 | 调用 LLM 必须 |
| 工具注册 + 派发 | 执行操作必须 |
| 消息序列化 | API 通信必须 |
| 环境提示 (OS/Shell/CWD) | LLM 需要知道在哪 |
| 消息角色交替修复 | API 要求 |
| 错误重试 | 健壮性必须 |

---

## 3. 实现方案

### 3.1 核心改动：3 个文件

```
agent/agent_init.py         ← 加 lite 短路 (~50行新增)
agent/system_prompt.py      ← 加 lite 路径 (~30行新增)
agent/conversation_loop.py  ← 加 lite 跳过 (~30行新增)
                                   ─────────
                                    约 110 行新代码
```

### 3.2 agent_init.py 改法

```python
# agent/agent_init.py

def init_agent(agent, ..., lite: bool = False):
    """初始化 AIAgent。
    
    lite=True: 轻量模式，跳过记忆/技能/压缩/护栏/凭证池。
    对标 OpenCode 的精简编码助手。
    """
    # ──── 通用初始化 (所有模式都需要) ────
    _resolve_model_provider(agent, ...)       # Provider 解析
    _resolve_api_credentials(agent, ...)       # API Key
    _load_toolsets(agent, enabled_toolsets)    # 工具加载
    _install_safe_stdio()
    _setup_logging(agent)
    
    # ──── Lite 模式短路 ────
    if lite:
        agent.lite_mode = True
        agent.memory_enabled = False
        agent.compression_enabled = False
        agent.checkpoints_enabled = False
        agent.save_trajectories = False
        agent._memory_manager = None
        agent._context_compressor = None
        agent._tool_guardrails = None
        agent._credential_pool = None
        agent._think_scrubber = None
        agent._context_scrubber = None
        agent._subdirectory_hints = None
        agent.skills = []
        agent._skill_nudge_interval = 0
        agent._memory_nudge_interval = 0
        agent._cached_user_profile = ""
        # 使用最简提示词
        agent._custom_identity = (
            "You are a helpful coding assistant. "
            "Use the available tools to read, search, edit, and run code. "
            "Be concise and direct."
        )
        # 加载 lite 插件（只加载必须的）
        _load_lite_plugins(agent)
        return

    # ──── Full 模式（现有代码，不变）───
    agent._memory_manager = MemoryManager()
    agent._context_compressor = ContextCompressor(...)
    agent._tool_guardrails = ToolGuardrailController(...)
    # ... 现有 ~1,200 行保持不变 ...
```

### 3.3 system_prompt.py 改法

```python
# agent/system_prompt.py

def build_system_prompt_parts(agent, system_message=None):
    if getattr(agent, 'lite_mode', False):
        return _build_lite_prompt_parts(agent, system_message)
    # ... 现有的三段式 ...

def _build_lite_prompt_parts(agent, system_message=None):
    """Lite 模式：单层提示词，~500 字符"""
    from agent.prompt_builder import build_environment_hints
    
    parts = [
        agent._custom_identity,          # 简短身份
        build_environment_hints(agent),  # OS/Shell/CWD (50字符)
    ]
    if system_message:
        parts.append(system_message)
    
    return {
        "stable":   "\n\n".join(parts),
        "context":  "",
        "volatile": "",
    }
```

### 3.4 conversation_loop.py 改法

```python
# agent/conversation_loop.py

def run_conversation(agent, user_message, ...):
    lite = getattr(agent, 'lite_mode', False)
    
    # ──── 通用前置 ────
    _install_safe_stdio()
    set_session_context(agent.session_id)
    agent._ensure_db_session()
    
    if not lite:
        # Full 模式的额外前置
        _hydrate_todo_store(...)
        _hydrate_memory_counters(...)
        _prefetch_memory(...)
    
    # ──── 主循环 (统一) ────
    while (api_call_count < max_iterations and budget > 0) or grace_call:
        if agent._interrupt_requested:
            break
        
        api_call_count += 1
        
        if not lite:
            # Full 模式的每轮检查
            _drain_pending_steer(agent)
            _check_skill_nudge(agent)
            _preflight_compression_check(agent)
            _rotate_credentials(agent)
        
        # ──── 核心：API 调用 + 工具派发（所有模式共用）───
        response = _interruptible_api_call(agent, api_messages)
        if response.tool_calls:
            for tc in response.tool_calls:
                result = handle_function_call(tc.name, tc.args)
                messages.append(tool_result_message(result))
        else:
            final_response = response.content
            break
    
    if not lite:
        # Full 模式的后置处理
        _sync_memory(agent)
        _background_skill_review(agent)
    
    return {"final_response": final_response, "messages": messages}
```

---

## 4. 瘦掉的部分如何模块化复用

### 4.1 核心思想：Lite Plugin Hook 接口

被 Lite 模式跳过的子系统，不删掉，而是改造成 **可插拔模块**。定义统一的 Hook 接口：

```python
# agent/lite_hooks.py — 新增文件

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class LiteHook(ABC):
    """Lite 模式的可选钩子。Full 模式自动加载全部，Lite 模式按需加载。"""
    
    name: str = ""              # 唯一标识
    
    # ──── 初始化钩子 ────
    def on_init(self, agent: Any) -> None:
        """Agent 初始化时调用"""
        pass
    
    # ──── 提示词钩子 ────
    def build_prompt_block(self, agent: Any) -> str:
        """返回要注入系统提示词的文本块。返回空字符串表示不注入。"""
        return ""
    
    # ──── 循环钩子 ────
    def before_loop(self, agent: Any, messages: List[Dict]) -> None:
        """主循环开始前调用"""
        pass
    
    def before_api_call(self, agent: Any, messages: List[Dict]) -> None:
        """每次 API 调用前调用"""
        pass
    
    def after_tool_execution(self, agent: Any, tool_name: str, result: str) -> None:
        """工具执行后调用"""
        pass
    
    def after_loop(self, agent: Any, final_response: str) -> None:
        """主循环结束后调用"""
        pass
    
    # ──── 工具钩子 ────
    def get_tool_schemas(self) -> List[Dict]:
        """返回此模块提供的额外工具 Schema"""
        return []
    
    def handle_tool_call(self, name: str, args: Dict) -> Optional[str]:
        """处理此模块注册的工具调用"""
        return None
```

### 4.2 各子系统改造为 LiteHook

#### MemoryHook

```python
# plugins/lite_hooks/memory_hook.py

class MemoryHook(LiteHook):
    name = "memory"
    
    def on_init(self, agent):
        agent._memory_manager = MemoryManager()
        agent._memory_manager.add_provider(BuiltinMemoryProvider())
    
    def build_prompt_block(self, agent):
        if not agent._memory_manager:
            return ""
        return build_memory_context_block(agent)
    
    def before_api_call(self, agent, messages):
        if agent._memory_manager:
            context = agent._memory_manager.prefetch_all(messages[-1]["content"])
            _inject_ephemeral_context(messages, context)
    
    def after_loop(self, agent, final_response):
        if agent._memory_manager:
            agent._memory_manager.sync_all(user_msg, final_response)
    
    def get_tool_schemas(self):
        # memory 工具 Schema
        return [...]
    
    def handle_tool_call(self, name, args):
        # 路由到 MemoryManager
        return agent._memory_manager.handle_tool_call(name, args)
```

#### SkillsHook

```python
# plugins/lite_hooks/skills_hook.py

class SkillsHook(LiteHook):
    name = "skills"
    
    def on_init(self, agent):
        agent.skills = _discover_skills()
    
    def build_prompt_block(self, agent):
        if not agent.skills:
            return ""
        return build_skills_system_prompt(agent)
    
    def after_loop(self, agent, final_response):
        if agent._iters_since_skill >= agent._skill_nudge_interval:
            _nudge_skill_review(agent)
```

#### CompressionHook

```python
# plugins/lite_hooks/compression_hook.py

class CompressionHook(LiteHook):
    name = "compression"
    
    def on_init(self, agent):
        agent._context_compressor = ContextCompressor(...)
    
    def before_api_call(self, agent, messages):
        if agent._context_compressor.should_compress(messages):
            agent._context_compressor.compress(messages)
```

#### GuardrailHook

```python
class GuardrailHook(LiteHook):
    name = "guardrails"
    
    def on_init(self, agent):
        agent._tool_guardrails = ToolCallGuardrailController(...)
    
    def after_tool_execution(self, agent, tool_name, result):
        # 跟踪工具调用统计
        pass
```

### 4.3 加载策略

```python
# agent/agent_init.py

# 默认 Lite Hooks（Full 模式自动加载全部）
_DEFAULT_LITE_HOOKS = [
    "memory",
    "skills", 
    "compression",
    "guardrails",
    "steer",
    "todo",
]

# Lite 模式默认不加载任何 Hook
_LITE_MODE_DEFAULT_HOOKS = []

def _load_hooks(agent, hook_names: List[str]):
    """加载指定的 Lite Hook"""
    registry = _get_lite_hook_registry()
    for name in hook_names:
        hook_cls = registry.get(name)
        if hook_cls:
            hook = hook_cls()
            hook.on_init(agent)
            agent._lite_hooks.append(hook)

# Full 模式
_load_hooks(agent, _DEFAULT_LITE_HOOKS)

# Lite 模式
_load_hooks(agent, _LITE_MODE_DEFAULT_HOOKS)
```

---

## 5. 模块重组架构图

```
Full 模式:                         Lite 模式:
                                    
┌────────────┐                    ┌────────────┐
│  AIAgent   │                    │  AIAgent   │
│  (初始化)   │                    │  (初始化)   │
└─────┬──────┘                    └─────┬──────┘
      │                                 │
      ├─ MemoryHook  ✅                 ├─ MemoryHook  ❌
      ├─ SkillsHook  ✅                 ├─ SkillsHook  ❌
      ├─ CompressHook ✅               ├─ CompressHook ❌
      ├─ GuardrailHk ✅                ├─ GuardrailHk ❌
      ├─ SteerHook   ✅                 ├─ SteerHook   ❌
      ├─ TodoHook    ✅                 ├─ TodoHook    ❌
      ├─ CredPoolHk  ✅                 ├─ CredPoolHk  ❌
      ├─ CheckptHook ✅                 ├─ CheckptHook ❌
      ├─ ThinkScrub  ✅                 ├─ ThinkScrub  ❌
      └─ CtxScrubHk  ✅                 └─ CtxScrubHk  ❌
                                             │
                                     可随时按需加回来:
                                     hermes chat --lite --hooks memory,skills
```

**关键洞察：瘦掉的子系统没有消失，它们改造成了 LiteHook，从"默认自动加载"变成了"按需加载"。**

---

## 6. 用户接口设计

### 6.1 CLI

```bash
# 纯 Lite 模式
hermes chat --lite "修一下这个 bug"

# Lite + 加回记忆
hermes chat --lite --hooks memory "上周改的那个文件在哪"

# Lite + 记忆 + 技能
hermes chat --lite --hooks memory,skills "用上次那个流程部署"

# 配置文件持久化
hermes config set agent.mode lite
hermes config set agent.lite_hooks "[memory, compression]"
```

### 6.2 API

```python
from run_agent import AIAgent

# Lite 模式
agent = AIAgent(
    provider="anthropic",
    model="claude-sonnet-4",
    lite=True,                      # 轻量模式
    hooks=["memory", "skills"],     # 可选：加回子系统
    enabled_toolsets=["safe"],      # 最小工具集
)

# 运行
result = agent.chat("找出所有 TODO 注释")
```

### 6.3 配置

```yaml
# ~/.hermes/config.yaml
agent:
  mode: lite              # "full" | "lite"
  lite_hooks: []          # Lite 模式下额外加载的子系统
                          # 可选: memory, skills, compression, guardrails
  lite_prompt_extra: ""   # Lite 提示词额外内容

# Lite 模式下工具集默认用 safe
# 需要更多工具时:
toolsets:
  lite:
    - safe
    - terminal      # 可选加回终端
```

---

## 7. 效果预估

| 指标 | Full | Lite | OpenCode |
|------|------|------|----------|
| 初始化有效代码 | ~1,400 行 | ~200 行 | ~100 行 |
| 系统提示词 | ~15,000 字符 | ~500 字符 | ~2,500 字符 |
| 循环每轮操作 | 20+ 步 | 5 步 | 4 步 |
| 内存占用 | ~500MB | ~50MB | ~30MB |
| 启动时间 | ~0.8s | ~0.3s | ~0.05s |
| 总等效代码 | ~20,000 行 | ~1,500 行 | 758 行 |

---

## 8. 渐进式升级路径

Lite 模式不是一次性开关。用户可以渐进式加回子系统：

```
Level 0: Pure Lite (对标 OpenCode)
    └─ 编码 + 基础工具
    └─ hooks: []

Level 1: + Memory
    └─ 跨会话记住偏好
    └─ hooks: [memory]

Level 2: + Skills  
    └─ 积累可复用的工作流
    └─ hooks: [memory, skills]

Level 3: + Compression
    └─ 长对话自动压缩
    └─ hooks: [memory, skills, compression]

Level 4: + Guardrails
    └─ 工具安全护栏
    └─ hooks: [memory, skills, compression, guardrails]

Level 5: Full Mode
    └─ 什么都不缺
    └─ mode: full
```

---

**总结：瘦掉的部分不应该"删掉"，而是改造成 LiteHook 接口，从默认加载变成按需加载。Full 和 Lite 的区别只是加载了哪些 Hook，核心 Agent 循环是同一套代码。**
