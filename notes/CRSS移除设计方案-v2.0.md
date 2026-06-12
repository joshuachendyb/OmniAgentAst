# CRSS 移除 + 子 Agent 工具化设计方案

**创建时间**: 2026-06-12 22:30:32
**更新时间**: 2026-06-12 23:45:00
**版本**: v2.3（基于 OpenCode Agent Tool 模式 + 动态加载）
**作者**: 小沈
**状态**: 设计方案

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v2.0 | 2026-06-12 22:30:32 | 初始版本，子 Agent 工具化设计 | 小沈 |
| v2.1 | 2026-06-12 22:55:24 | 修正架构（主Agent=FILE+FUND_RUNTIME）；新增 tool_search 动态加载机制 | 小沈 |
| v2.2 | 2026-06-12 23:45:00 | 移除 tool_help/pipeline 引用；修正工具数量为 50 | 小沈 |

---

## 一、OpenCode Agent Tool 模式研究

### 1.1 OpenCode 核心架构

OpenCode 有两层概念：

| 概念 | 说明 | 示例 |
|------|------|------|
| **Tool** | 确定性函数，执行具体操作 | read, write, edit, bash, glob, grep |
| **Agent** | 自主 LLM 会话，有自己的模型、prompt、工具集 | build, plan, explore, general |
| **Task Tool** | 唯一的 Agent 委托工具，创建子 Agent 会话 | `task(subagent_type="explore", prompt="...")` |

**关键设计**：
- Task Tool 是**唯一**的 Agent 委托机制
- 每个子 Agent 获得**独立上下文窗口**（不共享父 Agent 的上下文）
- 子 Agent 运行完毕后返回**文本结果**给父 Agent
- Task Tool 的描述**动态生成**，列出所有可用子 Agent 及其描述

### 1.2 OpenCode 子 Agent 定义方式

**方式1：Markdown 文件**（`~/.config/opencode/agents/` 或 `.opencode/agents/`）

```markdown
---
description: 快速探索代码库结构
mode: subagent
model: anthropic/claude-sonnet-4-20250514
temperature: 0.1
permission:
  edit: deny
  bash: deny
---

你是一个代码探索助手。你的任务是快速搜索和分析代码库结构。
```

**方式2：JSON 配置**（`opencode.json`）

```json
{
  "agent": {
    "code-reviewer": {
      "description": "审查代码质量和最佳实践",
      "mode": "subagent",
      "model": "anthic/claude-sonnet-4-20250514",
      "prompt": "你是一个代码审查专家...",
      "permission": { "edit": "deny", "bash": "deny" }
    }
  }
}
```

### 1.3 OpenCode Task Tool 执行流程

```
主 Agent (Build)
  │
  │  LLM 决定调用 task 工具
  │  task(subagent_type="explore", prompt="搜索所有 API 端点")
  │
  ▼
Task Tool.execute()
  │
  ├── 1. 查找子 Agent 定义 → Agent.get("explore")
  ├── 2. 创建子会话 → sessions.create({parentID, agent, permission})
  ├── 3. 子 Agent 获得独立上下文窗口 + 自己的工具集
  ├── 4. Session.prompt() → 子 Agent 自主运行
  ├── 5. 子 Agent 返回文本结果
  │
  ▼
主 Agent 收到结果，继续工作
```

---

## 二、本项目设计：子 Agent 工具化

### 2.1 设计目标

借鉴 OpenCode 的 Task Tool 模式，将 4 个领域子 Agent 暴露为**工具**，LLM 自主决定是否调用：

**主 Agent（UniversalAgent）保持不变**：加载 FILE + FUND_RUNTIME 工具（24 个直接工具，含 6 meta）

| 子 Agent 工具 | 对应领域 | 包含的 ToolCategory | 说明 |
|--------------|---------|-------------------|------|
| `system_agent` | 系统管理 | SYSTEM | 系统信息、进程管理、环境变量、注册表 |
| `network_agent` | 网络与进程 | NET_PROCESS | 网络请求、进程管理 |
| `document_agent` | 文档内容 | DOC_CONTENT | 文档读写、数据库、数据分析 |
| `desktop_agent` | 屏幕交互 | SCREEN | 截图、录屏、鼠标键盘操作 |

### 2.2 工具总览

```
主 Agent (UniversalAgent) — 24 个直接工具
  ├── 10 FUND_RUNTIME（含 6 meta: time_now, time_add, time_diff, query_calendar, timer, tool_search）
  └── 10 FILE

子 Agent 工具 — 4 个，LLM 决定是否调用
  ├── system_agent → 9 SYSTEM + 6 meta = 15
  ├── network_agent → 6 NET_PROCESS + 6 meta = 12
  ├── document_agent → 9 DOC_CONTENT + 6 meta = 15
  └── desktop_agent → 6 SCREEN + 6 meta = 12
```

### 2.3 架构图

```
用户输入
  │
  ▼
主 Agent (UniversalAgent) — 24 个直接工具
  ├── 10 FUND_RUNTIME（含 6 meta: time_now, time_add, time_diff, query_calendar, timer, tool_search）
  └── 10 FILE
  │
  │  LLM 自主决定调用哪个
  │
  ├── 调用直接工具（read_file, execute_shell, time_now 等）
  │     → 直接执行，返回结果
  │
  ├── 调用 tool_search → 搜索全部 50 个工具
  │     → 发现跨域工具 → 动态加载单个工具到当前 Agent
  │     → LLM 下一步可直接调用该工具
  │
  └── 调用子 Agent 工具（system_agent, network_agent 等）
        │
        ▼
      子 Agent 执行（独立上下文窗口）
        ├── 该领域工具 + 6 meta
        ├── tool_search 可动态加载跨域工具
        │
        ▼
      返回文本结果给主 Agent
```

### 2.4 与 OpenCode 模式的差异

| 维度 | OpenCode | 本项目 |
|------|---------|--------|
| **委托机制** | Task Tool（单一通用工具） | 4 个领域专用工具 |
| **子 Agent 数量** | 动态（用户可自定义） | 固定 4 个（system/network/document/desktop） |
| **子 Agent 工具集** | 继承父 Agent 工具（权限过滤） | 只加载该领域的工具 + meta |
| **跨域工具访问** | 无（子 Agent 只用自己工具） | tool_search 动态加载单个跨域工具 |
| **上下文** | 独立上下文窗口 | 独立上下文窗口 |
| **返回值** | 文本结果 | 文本结果 |

### 2.5 为什么用领域专用工具而非单一 Task Tool

| 优势 | 说明 |
|------|------|
| **LLM 更容易选择** | 4 个工具各有明确描述，比 1 个通用 Task Tool + 动态描述更清晰 |
| **工具描述更精准** | 每个子 Agent 工具的描述可以直接说明该领域能做什么 |
| **减少 token 开销** | 不需要动态生成子 Agent 列表描述 |
| **符合 SRP** | 每个子 Agent 工具只负责一个领域 |

---

## 三、详细设计

### 3.1 子 Agent 工具定义

每个子 Agent 工具是一个**普通工具**，注册到 ToolRegistry，暴露给 LLM。

```python
# app/services/tools/agent_tools/system_agent_tool.py

import uuid
from pydantic import BaseModel, Field
from typing import Any, Dict

class SystemAgentInput(BaseModel):
    task: str = Field(description="要执行的系统管理任务描述")

async def execute_system_agent(task: str) -> Dict[str, Any]:
    """执行系统管理任务 — 委托给 SystemSubAgent"""
    from app.services.agent.sub_agent_factory import create_sub_agent
    
    agent = create_sub_agent(
        domain="system",
        task_id=f"sub-{uuid.uuid4()}",
    )
    
    result_parts = []
    async for event in agent.run_react_cycle(task=task):
        if event.type == "final":
            result_parts.append(event.response)
        elif event.type == "chunk":
            result_parts.append(event.content)
    
    return {
        "code": 0,
        "data": {"result": "\n".join(result_parts)},
        "message": "子Agent执行完成"
    }
```

### 3.2 子 Agent 工具 Schema（FC Schema）

```json
{
  "name": "system_agent",
  "description": "执行系统管理任务：查看系统信息（CPU/内存/磁盘）、进程管理、环境变量、注册表查询。当用户需要操作系统级信息或管理进程时使用此工具。",
  "parameters": {
    "type": "object",
    "properties": {
      "task": {
        "type": "string",
        "description": "要执行的系统管理任务描述，例如：'查看CPU使用率'、'查看内存使用情况'、'管理进程'"
      }
    },
    "required": ["task"]
  }
}
```

### 3.3 子 Agent 配置

每个子 Agent 拥有**独立的角色描述（Persona）**，定义其专业领域和操作规则。角色描述来自对应的 prompt 模块，由 LLM 在子 Agent 上下文中执行。

| 子 Agent | 角色描述 | 操作规则 |
|---------|---------|---------|
| system | 系统全能助手：命令执行、系统查询、时间操作 | 查询类直接执行；执行命令/修改配置需确认 |
| network | 网络操作助手：HTTP请求、文件下载、网页获取、网络搜索 | 无破坏性操作，可直接执行 |
| document | 文档处理助手：PDF/Word/Excel/PPT读写、数据分析 | 读取直接执行；写入/修改需确认 |
| desktop | 桌面操作助手：窗口管理、鼠标键盘控制、截图、剪贴板 | 操作类需确认；查询类直接执行 |

```python
# app/services/agent/sub_agent_configs.py

SUB_AGENT_CONFIGS = {
    "system": {
        "description": "执行系统管理任务：查看系统信息（CPU/内存/磁盘）、进程管理、环境变量、注册表",
        "category": ToolCategory.SYSTEM,
        "extra_categories": [],  # system_agent 只加载 SYSTEM 工具
        "prompt_module": "app.services.prompts.system.system_prompts",
        "prompt_class_name": "SystemPrompts",
        "max_steps": 50,
    },
    "network": {
        "description": "执行网络与进程任务：网络请求、进程管理、端口查询",
        "category": ToolCategory.NET_PROCESS,
        "extra_categories": [],
        "prompt_module": "app.services.prompts.network.network_prompts",
        "prompt_class_name": "NetworkPrompts",
        "max_steps": 30,
    },
    "document": {
        "description": "执行文档内容任务：文档读写、数据库查询、数据分析",
        "category": ToolCategory.DOC_CONTENT,
        "extra_categories": [],
        "prompt_module": "app.services.prompts.document.document_prompts",
        "prompt_class_name": "DocumentPrompts",
        "max_steps": 30,
    },
    "desktop": {
        "description": "执行屏幕交互任务：截图、录屏、鼠标键盘操作、窗口管理",
        "category": ToolCategory.SCREEN,
        "extra_categories": [],
        "prompt_module": "app.services.prompts.desktop.desktop_prompts",
        "prompt_class_name": "DesktopPrompts",
        "max_steps": 30,
    },
}
```

### 3.4 子 Agent 工具注册

4 个子 Agent 工具结构相同（DRY：用工厂函数统一创建）：

```python
# app/services/tools/agent_tools/__init__.py

from app.services.tools.agent_tools.agent_tool_factory import create_agent_tool_definitions

# 工厂函数：根据 SUB_AGENT_CONFIGS 自动生成 4 个工具定义
AGENT_TOOL_DEFINITIONS = create_agent_tool_definitions()
```

```python
# app/services/tools/agent_tools/agent_tool_factory.py

def create_agent_tool_definitions():
    """DRY: 根据 SUB_AGENT_CONFIGS 自动生成子 Agent 工具定义"""
    from app.services.agent.sub_agent_configs import SUB_AGENT_CONFIGS
    definitions = []
    for domain, config in SUB_AGENT_CONFIGS.items():
        definitions.append({
            "name": f"{domain}_agent",
            "description": config["description"],
            "category": config["category"],
            "implementation": _create_agent_executor(domain),
            "input_model": _create_input_model(domain),
        })
    return definitions
```

### 3.5 主 Agent 工具加载策略

主 Agent（UniversalAgent）加载**两层工具**：

| 层级 | 工具 | 说明 |
|------|------|------|
| **直接工具** | FUND_RUNTIME 工具（10个） | 含 meta(6) + shell/code_execution(4) |
| **直接工具** | FILE 工具（10个） | read_file, write_file, list_files 等 |
| **子 Agent 工具** | 4 个领域工具 | system_agent, network_agent, document_agent, desktop_agent |

**总工具数**：10 FUND_RUNTIME + 10 FILE + 4 agent = **24 个工具**暴露给主 Agent 的 LLM。

### 3.6 子 Agent 内部工具加载

子 Agent 内部加载**该领域工具 + meta 工具**：

| 子 Agent | 领域工具 | meta 工具 | 总计 |
|---------|---------|----------|------|
| system_agent | SYSTEM(9) | 6 | 15 |
| network_agent | NET_PROCESS(6) | 6 | 12 |
| document_agent | DOC_CONTENT(9) | 6 | 15 |
| desktop_agent | SCREEN(6) | 6 | 12 |

### 3.7 tool_search 动态加载机制

**问题**：子 Agent 的 `tool_search` 搜索全局 Registry，能找到跨域工具但无法执行（未加载）。

**解决方案**：通过 contextvars 传递当前 Agent，`tool_search` 发现跨域工具后**动态加载单个工具**到当前 Agent。主 Agent 和子 Agent 都能用。

```python
# context_vars.py — 新增
_current_agent: ContextVar[Optional[Any]] = ContextVar("current_agent", default=None)
```

```python
# tool_manager.py — 执行工具前设置 contextvar
from app.services.context_vars import _current_agent
_current_agent.set(self.agent)
```

```python
# meta_tools.py — tool_search 动态加载
def tool_search(query: str) -> Dict[str, Any]:
    all_tools = tool_registry.list_tools()  # 使用公共方法
    # ... 搜索逻辑不变 ...
    
    # 动态加载：发现的工具不在当前 Agent 中则加载
    from app.services.context_vars import _current_agent
    agent = _current_agent.get()
    if agent:
        for match in top_results:
            tool_name = match["name"]
            if tool_name not in agent._tools_dict:
                impl = tool_registry.get_implementation(tool_name)
                if impl:
                    agent._tools_dict[tool_name] = impl
                    match["loaded"] = True
    
    return result
```

**执行流程**：

```
任意 Agent 调用 tool_search("截图")
  │
  ├── 搜索全局 Registry → 找到 take_screenshot
  ├── 从 contextvars 获取当前 Agent
  ├── 检查 agent._tools_dict → 不在已加载列表中
  ├── 动态加载: agent._tools_dict["take_screenshot"] = impl
  └── 返回结果（标记 loaded=True）
        │
        ▼
  LLM 下一步调用 take_screenshot → 直接执行（已加载）
```

**设计原则**：
- `tool_search` 是普通工具，主 Agent 和子 Agent 都能调用（统一接口）
- 搜索全局 Registry（发现能力）
- 通过 contextvars 获取当前 Agent，发现后动态加载单个工具（加载能力）
- 加载后 LLM 可直接调用（执行能力）
- 不破坏领域隔离（按需加载，不是全量加载）
- **DRY**：4 个子 Agent 工具结构相同，用工厂函数统一创建，避免重复代码

---

## 四、文件变更计划

### 4.1 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/tools/agent_tools/__init__.py` | 子 Agent 工具模块初始化 |
| `app/services/tools/agent_tools/agent_tool_factory.py` | DRY: 工厂函数统一创建子 Agent 工具 |
| `app/services/agent/sub_agent_factory.py` | 子 Agent 创建工厂 |
| `app/services/agent/sub_agent_configs.py` | 子 Agent 配置定义 |

### 4.2 删除文件

| 文件 | 说明 |
|------|------|
| `app/services/intents/crss_scorer.py` | CRSS 评分器 |
| `app/services/intents/crss_definitions.py` | CRSS 动作定义 |
| `app/services/intents/intent_mapper.py` | 意图映射 |
| `app/services/intents/__init__.py` | 模块初始化 |
| `app/services/intents/definitions/` | 整个目录 |
| `app/api/v1/chat/detect_intent.py` | 意图检测入口 |

### 4.3 重构文件

| 文件 | 变更 |
|------|------|
| `app/services/tools/tool_types.py` | 删除 IntentType、INTENT_MAPPING、CRSS_TYPE_KEYWORDS、_CRSS_REGISTRY；保留 ToolCategory、ToolMetadata |
| `app/services/agent/agent_config.py` | 删除 AGENT_REGISTRY；新增 UNIVERSAL_AGENT_CONFIG（主 Agent 配置） |
| `app/services/agent/agent_factory.py` | 删除 intent_type 分支；直接创建主 Agent |
| `app/services/agent/core_agent/tool_manager.py` | 改为加载 FUND_RUNTIME + FILE + agent 工具；设置 `_current_agent` contextvar |
| `app/services/context_vars.py` | 新增 `_current_agent` ContextVar |
| `app/services/tools/meta/meta_tools.py` | tool_search 改造：通过 contextvars 动态加载跨域工具 |
| `app/api/v1/chat/chat_stream_v2.py` | 删除 detect_intent 调用 |
| `app/services/react_sse_wrapper/run_sse_stream.py` | 删除 intent_type 参数 |
| `app/services/tools/__init__.py` | 新增 agent_tools 导出 |
| `app/services/tools/lazy_loader.py` | 新增 agent_tools 注册 |

### 4.4 删除测试

| 测试文件 | 说明 |
|---------|------|
| `tests/test_crss_scorer.py` | CRSS 测试（整个文件删除） |
| `tests/test_agent_factory.py` | 重写（测试单一 Agent 创建） |

### 4.5 常量清理

| 常量 | 处理 |
|------|------|
| `CRSS_CONFIDENCE_THRESHOLD` | 删除 |
| `CRSS_ACTION_MODULATION_FACTOR` | 删除 |
| `CRSS_ACTION_INFERENCE_WEIGHT` | 删除 |
| `CRSS_DANGEROUS_COMMAND_BONUS` | 删除 |
| `META_TOOL_NAMES` | 保留（删除 timezone_convert） |

---

## 五、执行流程详解

### 5.1 用户请求 "查看CPU使用率"

```
1. chat_stream_v2.py 接收请求
2. 不再调用 detect_intent()
3. 直接创建主 Agent（UniversalAgent）
4. 主 Agent 加载 24 个工具（10 FUND_RUNTIME + 10 FILE + 4 agent）
5. 主 Agent 调用 LLM，LLM 分析任务：
   - "查看CPU使用率" 是系统管理任务
   - 选择调用 system_agent 工具
   - 参数: {task: "查看CPU使用率"}
6. system_agent 工具被执行：
   a. 创建 SystemSubAgent（加载 15 个工具：9 SYSTEM + 6 meta）
   b. SystemSubAgent 调用 LLM，选择调用 get_system_info 工具
   c. get_system_info 返回 CPU 使用率数据
   d. SystemSubAgent 生成最终回答
7. system_agent 工具返回文本结果给主 Agent
8. 主 Agent 收到结果，生成最终回答给用户
```

### 5.2 用户请求 "下载 example.com 的页面并保存为 HTML"

```
1. 主 Agent 调用 LLM，LLM 分析任务：
   - 需要网络请求（network_agent）+ 文件写入（直接工具 write_file）
   - LLM 先调用 network_agent 下载内容
   - network_agent 内部通过 tool_search 发现 write_file（跨域）
   - tool_search 动态加载 write_file 到 network_agent
   - network_agent 调用 write_file 保存文件
   - 或者：主 Agent 先调用 network_agent 下载，再直接调用 write_file 保存
2. 子 Agent 执行并返回结果
3. 主 Agent 综合结果，生成最终回答
```

### 5.3 用户请求 "截图当前屏幕"

```
1. 主 Agent 调用 LLM，LLM 分析任务：
   - "截图" 是屏幕交互任务
   - 选择调用 desktop_agent 工具
   - 参数: {task: "截图当前屏幕"}
2. desktop_agent 工具被执行：
   a. 创建 DesktopSubAgent（加载 12 个工具：6 SCREEN + 6 meta）
   b. DesktopSubAgent 调用 LLM，选择调用 take_screenshot 工具
   c. take_screenshot 返回截图数据
   d. DesktopSubAgent 生成最终回答
3. desktop_agent 工具返回文本结果给主 Agent
4. 主 Agent 收到结果，返回截图给用户
```

---

## 六、Token 开销分析

### 6.1 主 Agent 工具 Schema 开销

| 工具 | 数量 | Schema 大小（估算） |
|------|------|-------------------|
| FUND_RUNTIME 工具（含 meta） | 10 | ~3500 tokens |
| FILE 工具 | 10 | ~2500 tokens |
| 子 Agent 工具 | 4 | ~800 tokens |
| **总计** | **24** | **~6800 tokens** |

### 6.2 子 Agent 工具 Schema 开销

| 子 Agent | 直接工具 Schema | meta 工具 Schema | 总计 |
|---------|----------------|-----------------|------|
| system_agent | ~3000 tokens | ~1200 tokens | ~4200 tokens |
| network_agent | ~1500 tokens | ~1200 tokens | ~2700 tokens |
| document_agent | ~2000 tokens | ~1200 tokens | ~3200 tokens |
| desktop_agent | ~1500 tokens | ~1200 tokens | ~2700 tokens |

### 6.3 总开销

- 主 Agent 调用：~6800 tokens（工具 schema）+ system prompt + 对话历史
- 子 Agent 调用：最多 ~4200 tokens（system_agent 最大情况）
- **总增量**：相比当前 CRSS 方案（50 个工具全加载 ~15000 tokens），主 Agent 减少 ~8200 tokens；子 Agent 按需加载，平均 ~4000 tokens

---

## 七、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 子 Agent 上下文窗口独立，可能丢失主 Agent 的对话上下文 | 中 | 子 Agent 的 task 参数应包含足够信息；主 Agent 可以在 task 中传递上下文 |
| 子 Agent 执行时间较长（需要额外 LLM 调用） | 中 | 子 Agent 可以并行执行；限制 max_steps |
| 子 Agent 内部工具加载较慢 | 低 | 只加载该领域的工具，比全量加载更快 |
| LLM 可能选择错误的子 Agent | 低 | 工具描述清晰；子 Agent 内部有 LLM 再次判断 |
| 嵌套 LLM 调用成本增加 | 中 | 子 Agent 可以使用更便宜的模型；限制 max_steps |

---

## 八、实施顺序

### Phase 1: 删除 CRSS 核心

1. 删除 `app/services/intents/` 整个目录（crss_scorer.py, crss_definitions.py, intent_mapper.py, definitions/）
2. 删除 `app/api/v1/chat/detect_intent.py`
3. 删除 `app/api/v1/chat/__init__.py` 中的 `detect_intent` 导出
4. 删除 `app/constants.py` 中的 CRSS 常量（CRSS_CONFIDENCE_THRESHOLD, CRSS_ACTION_MODULATION_FACTOR, CRSS_ACTION_INFERENCE_WEIGHT, CRSS_DANGEROUS_COMMAND_BONUS）
5. 删除 `app/services/task/task_tracker.py` 中的 CRSS 注释

### Phase 2: 简化 tool_types.py + 清理引用

6. 删除 IntentType、_CRSS_REGISTRY、INTENT_MAPPING、CRSS_TYPE_KEYWORDS、INTENT_TO_CATEGORY
7. 更新 `__all__`
8. 删除 `app/services/agent/agent_config.py` 中的 `normalize_intent` 导入（L88）

### Phase 3: 创建子 Agent 基础设施

9. 创建 `app/services/agent/sub_agent_configs.py`
10. 创建 `app/services/agent/sub_agent_factory.py`
11. 创建 `app/services/tools/agent_tools/__init__.py`
12. 创建 `app/services/tools/agent_tools/agent_tool_factory.py`（DRY 工厂函数）

### Phase 4: 重构主 Agent

13. 重构 agent_config.py：删除 AGENT_REGISTRY，新增 UNIVERSAL_AGENT_CONFIG
14. 重构 agent_factory.py：删除 intent_type 分支
15. 重构 tool_manager.py：加载 FUND_RUNTIME + FILE + agent 工具

### Phase 5: 更新 API 层

16. 更新 `chat_stream_v2.py`：删除 `detect_intent` 导入和调用
17. 更新 `run_sse_stream.py`：删除 `intent_type` 参数
18. 更新 `app/api/v1/chat/__init__.py`：删除 `detect_intent` 导出

### Phase 6: 注册子 Agent 工具

19. 更新 lazy_loader.py：注册 agent_tools
20. 更新 tools/__init__.py：导出 agent_tools

### Phase 7: 更新测试

21. 删除 test_crss_scorer.py
22. 重写 test_agent_factory.py
23. 运行完整测试套件

### Phase 8: 验证

24. pytest 全量测试
25. 手动测试：启动后端，发送各种意图的请求，验证子 Agent 正确执行

---

## 九、预期收益

| 收益 | 说明 |
|------|------|
| **架构简化** | 删除 CRSS + 意图映射 + 多 Agent 路由，代码量减少 ~500 行 |
| **主 Agent 轻量** | 加载 24 个工具（比当前 50 个少），token 开销降低 |
| **子 Agent 专业** | 每个子 Agent 只加载该领域的工具，LLM 决策更精准 |
| **符合 Hermes 模式** | LLM 自主选择工具，无需预分类 |
| **可扩展** | 新增领域只需新增一个子 Agent 工具 |

---

**文档更新时间**: 2026-06-12 23:45:00
**版本**: v2.3
**编写人**: 小沈
