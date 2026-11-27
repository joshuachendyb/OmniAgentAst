# [68] delegate_to_agent 与 AgentConfig 多 Agent 委托机制设计

> 文档名称: delegate_to_agent与AgentConfig多Agent委托机制设计-小欧-2026-11-27

版本历史:
- v1.0 2026-11-27 小欧 初版创建
- v1.1 2026-11-27 小欧 代码契约核验后修订：补子 Agent 独立事件缓冲；修正空集合语义反转、工具过滤双重失效、ContextVar token 模式、工具返回体契约、摘要提取字段；删除未消费字段；补 system_prompt 注入、并行上限落点、取消联动与临时授权约束

---

## 1 概述

### 1.1 目标

为 OmniAgent 引入**多 Agent 委托能力**：主 Agent 通过一个 tool（`delegate_to_agent`）创建独立子 Agent，子 Agent 拥有独立上下文、独立工具子集、有界 ReAct 循环，完成后回传摘要和 token 用量。

### 1.2 设计约束

| 约束 | 说明 |
|------|------|
| **不引入框架** | 不引入 LangGraph、AutoGen 等外部编排框架 |
| **不引入 DAG** | 不做多 Agent 图编排，保持"一个 tool 调一个有界子循环" |
| **不引入消息总线** | 子 Agent 与父 Agent 之间无异步消息，同步 await 结果 |
| **复用 UniversalAgent** | 子 Agent 实例化复用现有 `UniversalAgent`，不新增 Agent 子类 |
| **工具层零越层** | 子 Agent 创建/运行通过 ContextVar 回调注入，工具内不 import services |
| **递归防护** | 子 Agent 不可再调 `delegate_to_agent`（防 token 爆炸） |
| **并行有界** | 单轮最多 6 个并行子 Agent（asyncio.gather 有界并发） |

### 1.3 适用场景

| 场景 | 子 Agent 工具子集 | 特点 |
|------|-------------------|------|
| 独立并行搜索 | NETWORK + FUNDAMENTAL | 不同关键词同时搜，各回传摘要 |
| 独立审查验证 | FUNDAMENTAL + FILE | 干净上下文审查代码/方案 |
| 工具专精 | 按需分配 | 限定工具域的专用 Agent |
| 插件/Skill | manifest 声明 | 可注册的 AgentConfig 包 |
| 知识库多域对照 | FILE + FUNDAMENTAL | 隔离上下文避免膨胀 |

---

## 2 核心设计

### 2.1 AgentConfig 数据类

**文件位置**：`backend/app/services/agent/agent_config.py`

```python
# -*- coding: utf-8 -*-
"""
agent_config — Agent 配置数据类 + AgentRegistry

小欧 2026-11-27
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.logger import logger
from app.tools.tool_types import ToolCategory


@dataclass
class AgentConfig:
    """子 Agent 配置 — 定义一个可委托的 Agent 实例的全部参数"""
    agent_id: str                          # 唯一标识，如 "researcher" / "reviewer" / "kb_analyst"
    description: str                       # 一句话说明（给 LLM 看，帮助主 Agent 选择委托目标）
    system_prompt: str = ""                # 子 Agent 的 system prompt（注入方式见 §2.6）
    tool_categories: Set[ToolCategory] = field(default_factory=lambda: {ToolCategory.FUNDAMENTAL})
    tool_names: Optional[List[str]] = None # P1 工具名粒度；P0 不消费（见 §3.2）
    max_steps: int = 8                     # 子 Agent 最大 ReAct 步数（有界）
    output_format: str = "summary"         # 输出格式约束：summary / structured
    allow_delegate: bool = False           # 是否允许子 Agent 再委托（默认 False 防递归）


class AgentRegistry:
    """AgentConfig 注册表 — 管理所有可委托的子 Agent 配置"""

    def __init__(self):
        self._configs: Dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig) -> None:
        """注册一个 AgentConfig"""
        self._configs[config.agent_id] = config

    def get(self, agent_id: str) -> Optional[AgentConfig]:
        """按 agent_id 获取配置"""
        return self._configs.get(agent_id)

    def list_available(self) -> List[str]:
        """列出所有可用 agent_id（供 LLM 看）"""
        return list(self._configs.keys())

    def load_from_manifest(self, path: str) -> None:
        """从插件 manifest.json 加载 AgentConfig（见 §6）"""
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        categories = set()
        for name in data.get("tool_categories", ["fundamental"]):
            try:
                categories.add(ToolCategory(name))
            except ValueError:
                logger.warning(f"[AgentRegistry] 未知工具分类 {name!r}，跳过")
        config = AgentConfig(
            agent_id=data["name"],
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            tool_categories=categories or {ToolCategory.FUNDAMENTAL},
            tool_names=data.get("tool_names"),
            max_steps=data.get("max_steps", 8),
            output_format=data.get("output_format", "summary"),
        )
        self.register(config)


# 全局单例
_agent_registry: Optional[AgentRegistry] = None

def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
        _register_builtin_agents(_agent_registry)
    return _agent_registry


def _register_builtin_agents(registry: AgentRegistry) -> None:
    """内置 Agent 注册（P0 阶段 3 个内置子 Agent）"""
    registry.register(AgentConfig(
        agent_id="researcher",
        description="独立搜索研究员：用网络搜索工具多路并行搜索，回传结构化摘要",
        tool_categories={ToolCategory.NETWORK, ToolCategory.FUNDAMENTAL},
        max_steps=10,
        output_format="summary",
    ))
    registry.register(AgentConfig(
        agent_id="reviewer",
        description="独立审查员：用文件读取+搜索工具在干净上下文中审查代码/方案，回传结论",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        max_steps=12,
        output_format="structured",
    ))
    registry.register(AgentConfig(
        agent_id="kb_analyst",
        description="知识库分析师：检索知识库做多域对照分析，回传结论摘要",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        max_steps=10,
        output_format="summary",
    ))
```

### 2.2 delegate_to_agent 工具 Schema

**文件位置**：`backend/app/tools/agent/delegate_schema.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegate_schema — delegate_to_agent 工具参数模型
小欧 2026-11-27
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DelegateInput(BaseModel):
    """delegate_to_agent 工具入参 — LLM 侧看到的参数结构"""
    agent_id: str = Field(
        ...,
        description="目标子Agent ID（从可用列表中选取）"
    )
    task: str = Field(
        ...,
        description="委托给子Agent的任务描述（自包含，含必要背景，≤500字）"
    )
    context: Optional[Dict[str, Any]] = Field(
        None,
        description="附加上下文（文件路径/数据片段/约束条件等，按需传入）"
    )
    parallel: bool = Field(
        False,
        description="是否并行执行（True时可同时委托多个子Agent，需与并行批次配合）"
    )
```

**设计说明**：

- `agent_id`：从 `AgentRegistry.list_available()` 枚举中选取，LLM 通过工具描述中内嵌的可用列表做路由。
- `task`：自包含任务描述。子 Agent **不继承父 Agent 的完整对话历史**，只接收这里传入的任务描述 + context。这是上下文隔离的核心。
- `context`：可选结构化附加信息（如文件路径、代码片段、约束条件）。
- `parallel`：标记是否可并行。主 Agent 可以在同一轮发多个 `delegate_to_agent` 调用（工具并行执行框架已支持），每个调用指定不同 `agent_id` 或不同 `task`。

### 2.3 delegate_to_agent 工具实现

**文件位置**：`backend/app/tools/agent/delegate.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegate — delegate_to_agent 工具实现
小欧 2026-11-27

核心逻辑：
  1. 从 ContextVar 取 delegate_callback（入口层注入）
  2. 调 callback(agent_id, task, context, parallel)
  3. callback 内部：查 AgentRegistry → 创建子 Agent → 跑 ReAct → 回传摘要 + usage
  4. 工具层零越层：不 import services/agent，只消费 ContextVar 回调
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_delegate_callback
from app.tools.tool_response import build_error, build_success


async def delegate(
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    parallel: bool = False,
) -> Dict[str, Any]:
    """委托子 Agent 执行任务 — 工具入口"""
    start = time.time()

    # 取回调（tool_executor 入口层注入）
    callback = get_current_delegate_callback()
    if callback is None:
        return build_error(llm_data={
            "summary": "delegate_to_agent，失败：委托通道未注入",
            "action": {"tool": "delegate_to_agent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": "无可用 delegate_callback",
                       "hint": "请确认当前运行环境支持多 Agent 委托"},
        })

    try:
        result = await callback(agent_id=agent_id, task=task, context=context, parallel=parallel)
    except Exception as e:
        return build_error(llm_data={
            "summary": f"delegate_to_agent，失败：子 Agent 执行异常 {e}",
            "action": {"tool": "delegate_to_agent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": f"子 Agent 内部错误: {e}",
                       "hint": "可换其他 agent_id 重试或自行处理"},
        })

    duration_ms = int((time.time() - start) * 1000)

    # result 结构由 callback 保证: {"summary", "usage", "status", "steps"}，llm_data 统一走项目契约
    status = result.get("status", "failed")
    if status == "success":
        _summary = result.get("summary", "")
        return build_success(
            data={
                "agent_id": agent_id,
                "summary": _summary,
                "usage": result.get("usage", {}),
                "steps": result.get("steps", 0),
            },
            llm_data={
                "summary": f"委托子Agent({agent_id})完成: {_summary[:120]}",
                "action": {"tool": "delegate_to_agent", "tool_zh": "委托子Agent",
                           "params": {"agent_id": agent_id}},
                "status": {"exec_code": "success", "message": "成功"},
            },
            other_data={"duration_ms": duration_ms},
        )
    else:
        return build_error(llm_data={
            "summary": f"delegate_to_agent，失败：子Agent({agent_id})执行未成功",
            "action": {"tool": "delegate_to_agent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": result.get("summary", "未知原因"),
                       "hint": "可检查任务描述是否清晰后重试，或自行处理"},
        })
```

### 2.4 ContextVar 注入（工具层零越层）

**文件位置**：`backend/app/tools/context.py`（扩展）

```python
# 2026-11-27 小欧 - 新增 _current_delegate_callback ContextVar
# 签名: async (agent_id, task, context, parallel) -> Dict
# 入口层(tool_executor)持 agent + AgentRegistry 注入; 工具层零越层, 未注入返回 None 自行降级
_current_delegate_callback: ContextVar[Optional[object]] = ContextVar(
    "current_delegate_callback", default=None
)

def get_current_delegate_callback():
    return _current_delegate_callback.get()

def set_current_delegate_callback(callback):
    """返回 token 供 reset 恢复上一作用域值（与 hooks/notice/question 同模式）"""
    return _current_delegate_callback.set(callback)

def reset_current_delegate_callback(token) -> None:
    _current_delegate_callback.reset(token)
```

### 2.5 入口层注入（tool_executor 扩展）

**文件位置**：`backend/app/services/agent/tool_executor.py`（扩展 `execute_tool` 的 ContextVar 注入段）

在 `execute_tool` 函数中，与现有的 hooks/text_task/notice/question/generate/precheck/session_id 注入同层，新增：

```python
# 2026-11-27 小欧 - 注入 delegate 回调(同 notice/question 模式)
from app.tools.context import (
    set_current_delegate_callback,
    reset_current_delegate_callback,
)

# 构建闭包：捕获当前 agent（registry 由 run_delegate 内部惰性查单例）
from app.services.agent.delegate_runner import run_delegate

async def _delegate_cb(**kwargs):
    return await run_delegate(agent=agent, **kwargs)

token = set_current_delegate_callback(_delegate_cb)
try:
    # ... 工具执行逻辑 ...
finally:
    reset_current_delegate_callback(token)
```

### 2.6 子 Agent 运行器（核心）

**文件位置**：`backend/app/services/agent/delegate_runner.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegate_runner — 子 Agent 创建与运行
小欧 2026-11-27

职责：
  1. 查 AgentRegistry 获取 AgentConfig
  2. 创建子 UniversalAgent（独立 task_id、工具子集）
  3. 组装子 Agent 的 task 描述（父传入的 task + context + 输出格式约束）
  4. 在私有事件总线 + 克隆上下文中跑有界 run_react_cycle
  5. 从 FinalStep.response 提取结果 + accumulated_usage，组装返回值

事件总线（关键设计）：
  run_react_cycle 入口强制 get_stream_buffer(task_id) 非空，否则抛 RuntimeError。
  子 Agent 在 delegate_scope 内用 create_task_stream_buffer(sub_task_id, "") 领一张
  纯内存通行证（无 journal_sink / persist_sink）：不进父 SSE、不落 chat_task_steps。
  上下文副本使 clear_temp_auth / reset_current_task_id 只作用于子作用域，父零污染。
  不用走 run_agent_in_background：那是用户任务语义（台账/取消/重连/统计），
  子过程是同步计算，套完整 runner 属类别错误。

递归防护：
  - AgentConfig.allow_delegate=False 时，子 Agent 的 tool_categories 不含 AGENT
    （即子 Agent 看不到 delegate_to_agent 工具）
  - 子 Agent 不可再委托
"""
import asyncio
import contextvars
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from app.logger import logger
from app.services.agent.agent_config import AgentConfig, get_agent_registry
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_state import create_task_stream_buffer, reclaim_memory_buffer
from app.tools.tool_types import ToolCategory


@asynccontextmanager
async def _delegate_scope(sub_task_id: str):
    """私有事件总线 + 克隆上下文：子 Agent 的框架准入与全局状态隔离收口于此"""
    create_task_stream_buffer(sub_task_id, "")   # journal_sink=None → 纯内存，无 SSE/DB sink
    ctx = contextvars.copy_context()
    try:
        yield ctx
    finally:
        reclaim_memory_buffer(sub_task_id)       # 用完即收，防 agent_streams 泄漏


async def run_delegate(
    agent,              # 父 Agent 实例（提供 llm_client）
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    parallel: bool = False,
) -> Dict[str, Any]:
    """执行一次子 Agent 委托"""
    from app.services.agent.status_table import AgentStatus
    from app.services.task.task_state import is_cancel_requested

    registry = get_agent_registry()
    config = registry.get(agent_id)
    if config is None:
        available = registry.list_available()
        return {
            "status": "error",
            "summary": f"未知 agent_id '{agent_id}'，可用: {available}",
        }

    # 父任务已取消 → 不启动子 Agent（P0 只做入口检查；运行中子 Agent 随父轮次结束自然收口）
    if is_cancel_requested(agent.task_id):
        return {"status": "error", "summary": "父任务已取消，跳过委托"}

    # 递归防护：allow_delegate=False 时，子 Agent 工具集不含 AGENT 分类
    sub_categories = set(config.tool_categories)
    if not config.allow_delegate:
        sub_categories.discard(ToolCategory.AGENT)

    # 创建子 Agent（独立 task_id，复用父的 llm_client）
    # initial_categories 显式传集合：空集就是零工具；不可写 `or None`——那会回落到
    # UniversalAgent._INITIAL_CATEGORIES（含 AGENT），把刚剔除的 delegate 又装回来。
    sub_task_id = f"sub-{agent.task_id}-{agent_id}-{uuid.uuid4().hex[:6]}"
    sub_agent = UniversalAgent(
        llm_client=agent.llm_client,
        task_id=sub_task_id,
        max_steps=config.max_steps,
        initial_categories=sub_categories,
    )

    # system_prompt 注入：initialize_run_state 每轮以 _get_system_prompt() 重写 _sys_prompt，
    # 故必须在实例上覆盖该方法，直接设 _sys_prompt 会被下一轮覆盖。
    if config.system_prompt:
        sub_agent._get_system_prompt = lambda: (
            config.system_prompt + "\n\n" + sub_agent.prompts.build_full_system_prompt()
        )

    sub_task = _build_sub_task(config, task, context)

    # 私有事件总线 + 克隆上下文：子 Agent 的终态清理（clear_temp_auth /
    # reset_current_task_id）与工具回调 set/reset 全落在副本，父作用域零污染。
    try:
        async with _delegate_scope(sub_task_id) as scope_ctx:
            await asyncio.create_task(
                sub_agent.run_react_cycle(task=sub_task, max_steps=config.max_steps),
                context=scope_ctx,
            )
    except Exception as e:
        logger.warning(f"[delegate_runner] 子Agent {agent_id} 异常: {e}")
        return {"status": "error", "summary": f"子Agent执行异常: {e}"}

    success = getattr(sub_agent, "status", None) == AgentStatus.COMPLETED
    summary = _extract_summary(sub_agent)
    usage = dict(sub_agent.accumulated_usage)  # 由 tool_executor 合并进父 Agent

    logger.info(
        f"[delegate_runner] 子Agent {agent_id} 完成: "
        f"status={'success' if success else 'failed'}, steps={sub_agent.llm_call_count}, "
        f"usage={usage}"
    )

    return {
        "status": "success" if success else "failed",
        "summary": summary,
        "usage": usage,
        "steps": sub_agent.llm_call_count,
    }


def _build_sub_task(config: AgentConfig, task: str, context: Optional[Dict[str, Any]]) -> str:
    """组装子 Agent 的 task 描述（自包含，不继承父历史，长度有界）"""
    parts = [f"## 任务\n{task[:500]}"]
    if context:
        lines = []
        for k, v in list(context.items())[:20]:          # 键数上限，防塞满
            lines.append(f"- {k}: {str(v)[:200]}")        # 单值上限，防大段文本
        if lines:
            parts.append("## 附加上下文\n" + "\n".join(lines))
    if config.output_format == "structured":
        parts.append("## 输出要求\n请以结构化格式输出结论（分点列出）")
    else:
        parts.append("## 输出要求\n请输出简洁摘要（≤300字），包含关键发现和结论")
    return "\n\n".join(parts)


def _extract_summary(sub_agent) -> str:
    """从子 Agent 终态提取结果：FinalStep.response 是正文，reasoning 只是推理轨迹"""
    steps = getattr(sub_agent, "steps", []) or []
    for step in reversed(steps):
        if getattr(step, "TYPE", "") == "final":
            return (getattr(step, "response", "") or getattr(step, "error_message", "")
                    or getattr(step, "reasoning", "") or "")
    return steps[-1].get_content() if steps else ""      # 无终态时降级取末步正文
```

### 2.7 并行模式

**机制**：主 Agent 在同一轮 LLM 响应中发出多个 `delegate_to_agent` 工具调用（每个不同 `agent_id` 或不同 `task`）。现有 `tool_executor.execute_tool` 的并行分支（`asyncio.gather`）天然支持多工具调用并发。

**约束**：
- 单轮并行子 Agent 数 ≤ 6
- 子 Agent 内部**串行**（每个子 Agent 自身是单线程 ReAct 循环）
- 所有子 Agent 共享父 Agent 的 `llm_client`（连接池安全，非并发写）

**LLM 侧感知**：主 Agent 看到多个 `delegate_to_agent` 的 observation 同时返回（各带摘要 + usage），自行整合。

```python
# tool_runner.execute_tools(agent, all_calls, ...) 的 B' 并行分组调度已用
# asyncio.gather(*tasks) 并发执行；delegate_to_agent 作为普通 tool 参与，无需额外代码。
# 唯一新增：子 Agent 数量上限校验。
```

**上限校验落点**：必须在 `tool_runner.execute_tools` —— 它是唯一持有 `all_calls` 全量的一层。
`delegate()` 与 `tool_executor.execute_tool()` 都是单工具粒度，放在那里看不到同轮其它调用，校验无效。

```python
MAX_PARALLEL_SUB_AGENTS = 6  # tool_constants.py

# tool_runner.execute_tools 内、三分支调度之前：
delegate_calls = [c for c in all_calls if c.get("tool_name") == "delegate_to_agent"]
if len(delegate_calls) > MAX_PARALLEL_SUB_AGENTS:
    # 超出部分回统一错误体（不静默丢弃），其余照常执行
    for c in delegate_calls[MAX_PARALLEL_SUB_AGENTS:]:
        ...
```

---

## 3 与现有代码的集成

### 3.1 工具注册（agent_register.py 扩展）

在 `_register_agent_tools()` 中增加 `delegate_to_agent` 注册：

```python
# agent_register.py 扩展
from app.tools.agent.delegate import delegate
from app.tools.agent.delegate_schema import DelegateInput

AGENT_TOOL_DESCRIPTIONS["delegate_to_agent"] = (
    "委托子Agent执行独立任务。子Agent拥有独立上下文和工具子集，"
    "适用于：并行搜索不同来源、独立审查验证、工具专精任务、知识库多域对照分析。"
    "参数：agent_id(可用列表见下) + task(自包含任务描述) + context(可选附加信息)。"
    "子Agent完成后回传摘要和token用量，父Agent整合结果继续。"
    "可用agent_id: researcher(搜索研究), reviewer(独立审查), kb_analyst(知识库分析)。"
)
AGENT_INPUT_MODELS["delegate_to_agent"] = DelegateInput
AGENT_TOOL_EXAMPLES["delegate_to_agent"] = [
    {
        "agent_id": "researcher",
        "task": "搜索 2026年 Windows 桌面 Agent 框架的最新进展，重点关注上下文隔离和工具子集设计",
        "context": {"focus": "上下文隔离", "time_range": "2026"},
    }
]
# hide_from_steps 不加：delegate_to_agent 是业务工具，前端步骤流可见
```

注意：`delegate_to_agent` **不加入** `AGENT_HIDE_FROM_STEPS`（它是有业务产出的工具，前端步骤流应展示"正在委托 researcher 子Agent..."）。

### 3.2 工具子集注入

子 Agent 的工具注入复用 `ToolLoader.init_tools(initial_categories)`：

```python
# delegate_runner.py 中
sub_agent = UniversalAgent(
    llm_client=agent.llm_client,
    task_id=sub_task_id,
    max_steps=config.max_steps,
    initial_categories=sub_categories,  # AgentConfig.tool_categories
)
```

**P0 只做分类粒度**，`initial_categories` 一次传到位：`ToolLoader.init_tools` 同时写入 `_tools_dict` 与 `_loaded_categories`，两者天然一致。

**`tool_names` 为 P1，不可按原方案在 `init_tools` 后改 `_tools_dict`**——它两头不靠：

- LLM 可见性由 `_loaded_categories` 决定（`tool_cache_manager.get_openai_tools` 以 `categories=agent._loaded_categories` 调 `to_openai_tools`），改 `_tools_dict` 不影响 LLM 看到什么；
- 可执行性由 `_retry_engine._tools` 决定（`UniversalAgent.__init__:75` 构造 `ToolRetryEngine(self._tools_dict)`，引擎持有 `self._tools = tools` 引用），构造后重新赋值 `_tools_dict` 不会更新引擎，被"过滤掉"的工具照样能执行。

P1 正确做法：过滤发生在 `ToolRetryEngine` 构造之前（把筛选后的字典传进去），并让 `get_openai_tools` 同时接 `tool_names`（`to_openai_tools` 已原生支持 `tool_names` 形参）。

### 3.3 usage 合并

子 Agent 完成后，`run_delegate` 返回的 `usage` 字典（`accumulated_usage` 快照）由父 Agent 在 observation 中看到。父 Agent 的 `accumulated_usage` **不自动合并**（LLM 不知道子 Agent 花了多少 token）。

**设计决策**：usage 合并放在父 Agent 侧——`run_delegate` 返回后，父 Agent 的工具执行框架在 `tool_executor` 的 `execute_tool` 完成后，将子 Agent 的 usage 累加到父 Agent：

```python
# tool_executor.py 中，工具执行完成后：
if tool_name == "delegate_to_agent" and is_success(result):
    sub_usage = result.get("data", {}).get("usage", {})
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agent.accumulated_usage[key] += sub_usage.get(key, 0)
```

这样父 Agent 的 `FinalStep` 终态输出中已包含子 Agent 的 token 消耗。

### 3.4 SSE 隔离（P0 已实现）

子 Agent 的步骤**不透传**到父 Agent 的 SSE 流。父 Agent 步骤流中只看到：

```
Step N: delegate_to_agent(researcher, "搜索...") → observation: 摘要
```

**隔离机制**：`_delegate_scope` 为子 Agent 创建 `sub_task_id` 对应的**纯内存 StreamBuffer**（`journal_sink=None`，无 `persist_sink`）。`stream_reader(buffer, task_id)` 的 buffer 是参数传入的——父 SSE 读的是父 buffer 对象，子事件写入子 buffer，天然不可见；同时不写 `chat_task_steps` / `chat_tasks`，不产生幽灵任务行。循环结束 `reclaim_memory_buffer(sub_task_id)` 回收。

子 Agent 内部步骤只在日志中记录（`logger.debug`），前端不可见。

P2 阶段可考虑（暂不实施）：
- 父 Agent 步骤中嵌套显示子 Agent 的步骤（折叠/展开）
- 显式把子 Agent 的 StepEmitter 事件经父级 SSE 转发（需改 `stream_orchestrator._SSE_FORWARD_TYPES` 白名单与嵌套渲染）

---

## 4 防递归与安全防护

### 4.1 递归防护

| 防护层 | 机制 |
|--------|------|
| **配置层** | `AgentConfig.allow_delegate=False`（默认），子 Agent 工具集剔除 AGENT 分类 |
| **实例层** | 子 Agent 的 `_tools_dict` 中不含 `delegate_to_agent`，LLM 看不到该工具 |
| **硬顶** | 子 Agent `max_steps` 有界（默认 8），即使递归也无法无限跑 |
| **深度** | 当前设计只允许 1 层委托（主→子），`allow_delegate=True` 的场景 P1 再开放 |

> 粒度说明：AGENT 分类当前还含 `question` / `schedule`，剔除整类是粗粒度（子 Agent 本就不该做用户交互，可接受）；P1 开放 `allow_delegate=True` 时须改按工具名精确控制（见 §3.2），不能靠"放开整个分类"。

### 4.2 安全继承与作用域隔离

子 Agent 跑在 `contextvars.copy_context()` 的副本里（见 §2.6），副本继承父作用域的全部 ContextVar：

- `DefaultToolSecurityHooks`：安全确认/拒绝照常生效
- 沙箱预检：子 Agent 调 bash/file 工具时同样经过安全检查
- 临时授权（ `_authorized_paths` 是 ContextVar）：子 Agent 继承父的授权映射；其 `clear_temp_auth()` 只清副本，**父 Agent 的授权不受影响**
- 七组工具回调（hooks/notice/question/generate/session_id/task_id/delegate）在副本内 set/reset，父子互不干扰

> 不采用"手工保存/恢复授权"：ContextVar 本就是为这种作用域隔离设计的，克隆即用，零额外 API。

### 4.3 资源保护

| 保护 | 机制 |
|------|------|
| token 预算 | 子 Agent `max_steps` 有界 + LLM 上下文窗口限制 |
| 并行数 | 单轮 ≤ 6 个子 Agent（在 `tool_runner.execute_tools` 校验，见 §2.7） |
| 总耗时 | P0 靠 `max_steps` 间接限时间；`timeout` 为 P1 字段，当前未消费 |
| 连接池 | 子 Agent 共享父 Agent 的 `llm_client`（连接池天然并发安全） |
| 取消联动 | P0 入口检查父任务取消状态；运行中子 Agent 随父轮次结束自然收口，P1 做精确联动 |
| 事件总线 | 私有纯内存 buffer，用完 `reclaim_memory_buffer` 回收，不落库不进 SSE |
| 任务台账 | `BaseAgent.__init__` 仍为子 Agent 建 tracker 行并由 `_finalize_cycle` 收尾；不写 `chat_tasks`，用户不可见，P0 接受 |

---

## 5 实施文件清单

### 5.1 新增文件

| 文件 | 职责 | 预估行数 |
|------|------|----------|
| `backend/app/services/agent/agent_config.py` | AgentConfig 数据类 + AgentRegistry + 内置注册 | ~100 |
| `backend/app/services/agent/delegate_runner.py` | 子 Agent 创建/运行/私有事件总线/上下文克隆/摘要提取 | ~165 |
| `backend/app/tools/agent/delegate.py` | delegate_to_agent 工具函数 | ~60 |
| `backend/app/tools/agent/delegate_schema.py` | DelegateInput pydantic 模型 | ~30 |

### 5.2 修改文件

| 文件 | 改动 | 预估 |
|------|------|------|
| `backend/app/tools/agent/agent_register.py` | 注册 delegate_to_agent | +10 行 |
| `backend/app/tools/context.py` | 新增 delegate_callback ContextVar（token/reset 模式） | +15 行 |
| `backend/app/services/agent/tool_executor.py` | 注入 delegate 回调（token 模式）+ usage 合并 | +15 行 |
| `backend/app/services/agent/tool_runner.py` | 并行分支加 delegate 数量上限校验（唯一持有 all_calls 的层） | +8 行 |
| `backend/app/tools/tool_constants.py` | 新增 MAX_PARALLEL_SUB_AGENTS 常量 | +1 行 |

### 5.3 不改的文件

| 文件 | 原因 |
|------|------|
| `universal_agent.py` | 不改，子 Agent 复用现有构造；`system_prompt` 用实例覆盖 `_get_system_prompt` 注入 |
| `base_agent.py` | 不改 |
| `react_loop.py` | 不改，私有纯内存 buffer 满足其对 `get_stream_buffer` 的准入要求；全局清理由上下文副本隔离 |
| `agent_runner.py` | 不改，子 Agent 是同步子过程而非用户任务，不套完整 runner（无台账/取消/重连/统计） |
| `tool_loader.py` | 不改，`init_tools(initial_categories)` 已支持 |
| `step_emitter.py` | 不改，`emit_notice` / `emit_interact` 对 buffer 缺失已有降级分支 |

---

## 6 插件/Skill Manifest 格式

### 6.1 目录结构

```
plugins/
├── web-researcher/
│   ├── manifest.json
│   └── (可选) prompt.md    # system_prompt 全文（比 manifest 内联更长时放这里）
├── code-reviewer/
│   ├── manifest.json
└── kb-analyst/
    └── manifest.json
```

### 6.2 manifest.json 字段

```json
{
  "name": "web-researcher",
  "description": "多源并行网络搜索，回传结构化摘要",
  "system_prompt": "你是一个专业的网络研究员，擅长多源信息搜索与交叉验证...",
  "tool_categories": ["network", "fundamental"],
  "tool_names": null,
  "max_steps": 12,
  "output_format": "structured"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | agent_id，全局唯一 |
| `description` | 是 | 一句话（给 LLM 路由用） |
| `system_prompt` | 否 | 子 Agent 的 system prompt（空则用默认） |
| `tool_categories` | 否 | 工具分类列表（默认 `["fundamental"]`） |
| `tool_names` | 否 | P1 工具名粒度（null=用分类，P0 不消费） |
| `max_steps` | 否 | 最大步数（默认 8） |
| `output_format` | 否 | summary/structured（默认 summary） |

### 6.3 加载时机

应用启动时扫描 `plugins/` 目录，逐目录读 `manifest.json`，调 `AgentRegistry.load_from_manifest()` 注册。`load_from_manifest` 对未知 `tool_categories` 值逐项 warning 跳过并回落 `["fundamental"]`；JSON 格式错/字段缺失由扫描器捕获仅 warning 跳过，不阻塞启动。

---

## 7 数据流总览

```
主 Agent (UniversalAgent)
  │
  │  LLM 决定调用 delegate_to_agent(agent_id="researcher", task="...")
  │
  ▼
tool_executor.execute_tool()
  │  注入 delegate_callback ContextVar
  │  并行分支: asyncio.gather(多个 delegate_to_agent 调用)
  ▼
tools/agent/delegate.py (工具函数)
  │  取 callback → await callback(agent_id, task, context, parallel)
  ▼
delegate_runner.run_delegate(agent=父agent, agent_id, task, context, parallel)
  │  1. 查 AgentRegistry.get(agent_id) → AgentConfig；父任务取消则跳过
  │  2. 递归防护: 剔除 AGENT 分类；system_prompt 覆盖 _get_system_prompt
  │  3. 创建 UniversalAgent(llm_client, sub_task_id, max_steps, initial_categories)
  │  4. 组装 sub_task 描述（task≤500字 / 单 context 值≤200字）
  │  5. _delegate_scope: 建 sub_task_id 纯内存 buffer + copy_context()
  │  6. asyncio.create_task(..., context=副本) 跑 run_react_cycle（有界 max_steps）
  │  7. 从 FinalStep.response 提取结果 + accumulated_usage；finally 回收 buffer
  ▼
返回 {"status", "summary", "usage", "steps"} → 工具 observation
  │
  ▼
tool_executor: usage 合并到 agent.accumulated_usage
  │
  ▼
主 Agent LLM 看到 observation（摘要+用量）→ 继续 ReAct 循环
```

---

## 8 优先级与里程碑

| 阶段 | 内容 | 预估工期 |
|------|------|----------|
| **P0** | AgentConfig + AgentRegistry + delegate_runner（含私有 buffer + 上下文克隆）+ delegate 工具 + ContextVar + 注册 + 内置 3 个 Agent | 2-3 天 |
| **P0** | 工具子集注入验证（子 Agent 确实看不到 AGENT 分类工具） | 同 P0 |
| **P0** | SSE/DB 隔离验证（子步骤不进父 SSE、不写 chat_task_steps）+ 父授权不被清零 | 同 P0 |
| **P0** | usage 合并到父 Agent accumulated_usage | 同 P0 |
| **P1** | 并行上限校验落地 `tool_runner.execute_tools` | 0.5 天 |
| **P1** | 插件 manifest 加载 + `plugins/` 目录扫描 | 1 天 |
| **P1** | `tool_names` 名粒度过滤（构造 retry_engine 前筛 + `get_openai_tools` 接 tool_names） | 1 天 |
| **P1** | `timeout` 字段、`allow_delegate=True` 精确多层委托（≤2层）、取消精确联动 | 1 天 |
| **P2** | SSE 子 Agent 步骤折叠透传（改 `_SSE_FORWARD_TYPES` + 嵌套渲染） | 暂缓 |
| **P2** | 事件 sink 注入（`react_loop._publish` 可注入 `agent.event_sink`），去掉私有 buffer 通行证 | 暂缓 |
| **P2** | 子 Agent 独立 model 支持（需 llm_client 克隆/参数化） | 暂缓 |

---

## 9 设计决策记录

| 决策 | 理由 |
|------|------|
| 子 Agent 复用 `UniversalAgent` 而非新 Agent 子类 | KISS-DIRECT：现有类已支持 `initial_categories`，无需新抽象 |
| 不走 `agent_runner.run_agent_in_background` | 子 Agent 是同步子过程不是用户任务；完整 runner 的台账/取消/重连/统计属用户任务语义，套上去是类别错误 |
| 私有纯内存 buffer 而非改 runner 加开关 | 复用 `create_task_stream_buffer(..., journal_sink=None)` 现成纯内存模式；框架零改动、SSE/DB 天然隔离 |
| 上下文副本（`copy_context` + `create_task(context=)`） | `clear_temp_auth` / `reset_current_task_id` 是 ContextVar 作用域操作，副本天然隔离父子，优于手工保存恢复 |
| `delegate_to_agent` 不 hide_from_steps | 业务产出工具，前端应展示 |
| usage 合并放在 tool_executor 侧 | 工具层不感知 Agent 内部字段，由执行框架统一收口（注意须按 `llm_data.status.exec_code` 契约判定成功） |
| 内置 3 个 Agent 而非动态生成 | P0 先固定，验证收益后再开放插件注册 |
| 子 Agent 不继承父对话历史 | 上下文隔离是核心价值，继承会失去隔离意义 |
| 子 Agent task 描述自包含（≤500字 / 单 context 值≤200字） | 防 LLM 把整个对话塞进 context 导致子 Agent 上下文膨胀 |
| P0 只做分类粒度工具集，名粒度推迟 P1 | 现成 `to_openai_tools(tool_names=)` 只控可见性不控执行，需与 `ToolRetryEngine` 构造前筛选联动 |
