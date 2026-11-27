# [68] delegateagent 与 AgentConfig 多 Agent 委托机制设计

> 文档名称: delegateagent与AgentConfig多Agent委托机制设计-小欧-2026-11-27

版本历史:
- v1.0 2026-11-27 小欧 初版创建
- v1.1 2026-11-27 小欧 代码契约核验后修订：补子 Agent 独立事件缓冲；修正空集合语义反转、工具过滤双重失效、ContextVar token 模式、工具返回体契约、摘要提取字段；删除未消费字段；补 system_prompt 注入、并行上限落点、取消联动与临时授权约束
- v1.2 2026-11-27 小欧 主名称定为 delegateagent，其它生态名（subagent/delegate_task/delegate_to_agent/call_agent）经工具名别名层归一到本名；Schema 同步更名；新增 wait 参数，P0 同步、P1 异步；补别名映射改动清单
- v1.3 2026-11-27 小欧 §7 扩为通信交互与数据流总览：补主 Agent 四条通信通道（LLM/工具层/前端/子 Agent）与三条设计约束，明确子 Agent 结果经 FinalStep.response → summary → observation 回灌父 Agent 的路径
- v1.4 2026-11-27 小欧 明确执行模型：子 Agent 是同进程同事件循环的协程任务（非子进程/子线程），靠 ContextVar 副本做逻辑隔离；补入 §7.1 与架构边界约束、§1.2 设计约束、§9 决策记录
- v1.5 2026-11-27 小欧 明确子 Agent 复用主 Agent 同一 `react_loop.run_react_cycle`（零重写），差异全在配置/注入；补入 §2.6 与 §5.3
- v1.6 2026-11-27 小欧 `AgentConfig.model` 配置层扩展位：默认 None 继承父 Agent 的 LLM，非 None 时新建独立 llm_client（用完归还），不入工具参数；新增 §2.8 OCP 扩展点总表（13 个开放口 + 未列扩展点的封闭理由 + 灵活/可靠/高效三性）；补入 §2.1、§2.6、§6.2、§8、§9
- v1.7 2026-11-27 小欧 全文通读一致性修订：回调签名/工具描述补 wait、并行措辞统一到 tool_runner、旧名 delegate() 改正、§8 P0 model 行归位、§4.3 连接池补独立 client 说明、去"A+"口语化引用

---

## 1 概述

### 1.1 目标

为 OmniAgent 引入**多 Agent 委托能力**：主 Agent 通过一个 tool（`delegateagent`）创建独立子 Agent，子 Agent 拥有独立上下文、独立工具子集、有界 ReAct 循环，完成后回传摘要和 token 用量。

### 1.2 设计约束

| 约束 | 说明 |
|------|------|
| **不引入框架** | 不引入 LangGraph、AutoGen 等外部编排框架 |
| **不引入 DAG** | 不做多 Agent 图编排，保持"一个 tool 调一个有界子循环" |
| **不引入消息总线** | 不另立独立消息总线；P0 同步 `await`，P1 异步复用现成的完成通知通道回灌，不新增总线设施 |
| **协程而非进程/线程** | 子 Agent 是同一事件循环上的协程 Task，靠 ContextVar 副本隔离上下文；不新建 OS 执行单元（见 §7.1） |
| **复用 UniversalAgent** | 子 Agent 实例化复用现有 `UniversalAgent`，不新增 Agent 子类 |
| **工具层零越层** | 子 Agent 创建/运行通过 ContextVar 回调注入，工具内不 import services |
| **递归防护** | 子 Agent 不可再调 `delegateagent`（防 token 爆炸） |
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
    model: Optional[str] = None            # 指定模型（None=继承父 Agent 的 LLM，见 §2.6）
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
            model=data.get("model"),
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

### 2.2 delegateagent 工具 Schema

**文件位置**：`backend/app/tools/agent/delegateagent_schema.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent_schema — delegateagent 工具参数模型
小欧 2026-11-27
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DelegateAgentInput(BaseModel):
    """delegateagent 工具入参 — LLM 侧看到的参数结构"""
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
    wait: bool = Field(
        True,
        description="是否同步等待结果（True=本轮直接返回摘要+用量，P0 已实现；False=立即返回 delegate_id，后台跑完自动通知，P1）"
    )
```

**设计说明**：

- `agent_id`：从 `AgentRegistry.list_available()` 枚举中选取，LLM 通过工具描述中内嵌的可用列表做路由。
- `task`：自包含任务描述。子 Agent **不继承父 Agent 的完整对话历史**，只接收这里传入的任务描述 + context。这是上下文隔离的核心。
- `context`：可选结构化附加信息（如文件路径、代码片段、约束条件）。
- `parallel`：标记是否可并行。主 Agent 可以在同一轮发多个 `delegateagent` 调用（工具并行执行框架已支持），每个调用指定不同 `agent_id` 或不同 `task`。
- `wait`：同步/异步开关（默认 True）。
  - `True`（**P0 已实现**）：同步 `await` 子 Agent，本轮 observation 直接带摘要 + usage，父 Agent 继续 ReAct——即 §2.6 的同步委托路径。
  - `False`（**P1**）：`create_task` 后立即返回 `delegate_id` + `status=running`，子 Agent 在后台跑完后经完成通知通道回灌父会话（复用 `ShellInput.background` 的"完成自动通知"范式，父不轮询）。结果携带 `delegate_id` 以区分并发的多个异步委托；父任务取消时未完成后台委托一并终止。

### 2.3 delegateagent 工具实现

**文件位置**：`backend/app/tools/agent/delegateagent.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent — 子Agent委托工具实现
小欧 2026-11-27

核心逻辑：
  1. 从 ContextVar 取 delegate_callback（入口层注入）
  2. 调 callback(agent_id, task, context, parallel, wait)
  3. callback 内部：查 AgentRegistry → 创建子 Agent → 跑 ReAct → 回传摘要 + usage（P0 同步 / P1 异步）
  4. 工具层零越层：不 import services/agent，只消费 ContextVar 回调
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_delegate_callback
from app.tools.tool_response import build_error, build_success


async def delegateagent(
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    parallel: bool = False,
    wait: bool = True,
) -> Dict[str, Any]:
    """委托子 Agent 执行任务 — 工具入口"""
    start = time.time()

    # 取回调（tool_executor 入口层注入）
    callback = get_current_delegate_callback()
    if callback is None:
        return build_error(llm_data={
            "summary": "delegateagent，失败：委托通道未注入",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": "无可用 delegate_callback",
                       "hint": "请确认当前运行环境支持多 Agent 委托"},
        })

    try:
        result = await callback(agent_id=agent_id, task=task, context=context,
                                parallel=parallel, wait=wait)
    except Exception as e:
        return build_error(llm_data={
            "summary": f"delegateagent，失败：子 Agent 执行异常 {e}",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
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
                "action": {"tool": "delegateagent", "tool_zh": "委托子Agent",
                           "params": {"agent_id": agent_id}},
                "status": {"exec_code": "success", "message": "成功"},
            },
            other_data={"duration_ms": duration_ms},
        )
    else:
        return build_error(llm_data={
            "summary": f"delegateagent，失败：子Agent({agent_id})执行未成功",
            "action": {"tool": "delegateagent", "tool_zh": "委托子Agent", "params": {}},
            "status": {"exec_code": "error", "message": "失败",
                       "detail": result.get("summary", "未知原因"),
                       "hint": "可检查任务描述是否清晰后重试，或自行处理"},
        })
```

### 2.4 ContextVar 注入（工具层零越层）

**文件位置**：`backend/app/tools/context.py`（扩展）

```python
# 2026-11-27 小欧 - 新增 _current_delegate_callback ContextVar
# 签名: async (agent_id, task, context, parallel, wait) -> Dict
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
from app.services.agent.delegateagent_runner import run_delegate

async def _delegate_cb(**kwargs):
    return await run_delegate(agent=agent, **kwargs)

token = set_current_delegate_callback(_delegate_cb)
try:
    # ... 工具执行逻辑 ...
finally:
    reset_current_delegate_callback(token)
```

### 2.6 子 Agent 运行器（核心）

**引擎复用（关键架构决策）**：子 Agent **不另写 ReAct 循环**，调用的是主 Agent 同一个引擎——`sub_agent.run_react_cycle(...)` 继承自 `BaseAgent`，内部只做一层薄转发（`base_agent.py:133-138`：`return await _run(self, ...)`，`_run` 即 `react_loop.run_react_cycle`）。父子跑的是同一个函数，子 Agent 自动获得 LLM 调用与重试、安全门/沙箱/HITL、`execute_tools` 三分支、observation 回灌、StepEmitter、终态判定与全局清理等全套机制。

父子差异全在**配置与注入**，不在循环本身：`initial_categories`（工具子集）、`max_steps`（步数）、实例覆盖 `_get_system_prompt`（角色）、`_delegate_scope`（私有事件总线 + 上下文副本）、`_build_sub_task`（自包含任务描述）。即"同一个引擎，换配置、换上下文、换总线"，不是另写一台发动机。

**文件位置**：`backend/app/services/agent/delegateagent_runner.py`（新增）

```python
# -*- coding: utf-8 -*-
"""
delegateagent_runner — 子 Agent 创建与运行
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
    （即子 Agent 看不到 delegateagent 工具）
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
    wait: bool = True,  # P0 恒 True 同步；P1 False 走后台任务 + 完成通知
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

    # 创建子 Agent（独立 task_id，LLM 默认继承父；模型身份在 LLMClient 构造期定死）
    # initial_categories 显式传集合：空集就是零工具；不可写 `or None`——那会回落到
    # UniversalAgent._INITIAL_CATEGORIES（含 AGENT），把刚剔除的 AGENT 分类工具又装回来。
    sub_task_id = f"sub-{agent.task_id}-{agent_id}-{uuid.uuid4().hex[:6]}"
    _sub_client = None
    if config.model:
        # OCP 扩展位：配置指定模型 → 新建独立 llm_client（默认 None 则零开销继承父）
        from app.llm.client_sdk import create_llm_client
        from app.db.models.chat_models import ModelRef
        _parent_model = agent.llm_client.llm_model
        _model_ref = ModelRef(provider=_parent_model.provider, model=config.model,
                              api_base=_parent_model.api_base)
        _sub_client = create_llm_client(
            llm_model=_model_ref,
            api_key=agent.llm_client.api_key,   # 凭据沿用父，模型可切
        )
        _llm_client = _sub_client
    else:
        _llm_client = agent.llm_client
    sub_agent = UniversalAgent(
        llm_client=_llm_client,
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
    # P0：wait=True 同步 await，本轮 observation 直接带结果。
    # P1：wait=False 不 await，句柄存 _background_delegates[delegate_id]，立即返回
    #     {"status":"running","delegate_id":...}；完成经 notice 通道回灌（结果带 delegate_id）。
    try:
        async with _delegate_scope(sub_task_id) as scope_ctx:
            await asyncio.create_task(
                sub_agent.run_react_cycle(task=sub_task, max_steps=config.max_steps),
                context=scope_ctx,
            )
    except Exception as e:
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 异常: {e}")
        return {"status": "error", "summary": f"子Agent执行异常: {e}"}
    finally:
        if _sub_client is not None:            # 独立 client 用完归还（异常路径同样清理）
            await _sub_client.close()

    success = getattr(sub_agent, "status", None) == AgentStatus.COMPLETED
    summary = _extract_summary(sub_agent)
    usage = dict(sub_agent.accumulated_usage)  # 由 tool_executor 合并进父 Agent

    logger.info(
        f"[delegateagent_runner] 子Agent {agent_id} 完成: "
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

**机制**：主 Agent 在同一轮 LLM 响应中发出多个 `delegateagent` 工具调用（每个不同 `agent_id` 或不同 `task`）。现有 `tool_runner.execute_tools` 的并行分组调度（`asyncio.gather`）天然支持多工具调用并发。

**约束**：
- 单轮并行子 Agent 数 ≤ 6
- 子 Agent 内部**串行**（每个子 Agent 自身是单线程 ReAct 循环）
- 默认共享父 Agent 的 `llm_client`（连接池安全，非并发写）；`AgentConfig.model` 非 None 时用独立 client

**LLM 侧感知**：主 Agent 看到多个 `delegateagent` 的 observation 同时返回（各带摘要 + usage），自行整合。

```python
# tool_runner.execute_tools(agent, all_calls, ...) 的 B' 并行分组调度已用
# asyncio.gather(*tasks) 并发执行；delegateagent 作为普通 tool 参与，无需额外代码。
# 唯一新增：子 Agent 数量上限校验。
```

**上限校验落点**：必须在 `tool_runner.execute_tools` —— 它是唯一持有 `all_calls` 全量的一层。
`delegateagent()` 与 `tool_executor.execute_tool()` 都是单工具粒度，放在那里看不到同轮其它调用，校验无效。

```python
MAX_PARALLEL_SUB_AGENTS = 6  # tool_constants.py

# tool_runner.execute_tools 内、三分支调度之前：
delegate_calls = [c for c in all_calls if c.get("tool_name") == "delegateagent"]
if len(delegate_calls) > MAX_PARALLEL_SUB_AGENTS:
    # 超出部分回统一错误体（不静默丢弃），其余照常执行
    for c in delegate_calls[MAX_PARALLEL_SUB_AGENTS:]:
        ...
```

### 2.8 开放封闭原则（OCP）扩展点总表

架构的价值在于**对扩展开放、对修改封闭**。本设计的扩展点分布在配置层（不变代码即可扩展）与注入层（换实现不改调用方），逐项如下：

| 扩展点 | 默认行为 | 扩展方式（开放口） | 阶段 | 修改封闭性 |
|--------|----------|-------------------|------|-----------|
| 子 Agent 类型/能力 | 内置 3 个 | `AgentRegistry.register(AgentConfig)` / manifest 扫描 | P0 | 新增 Agent 不改运行器 |
| 工具集 | `AgentConfig.tool_categories` | 配置字段 + P1 `tool_names` | P0/P1 | 不加入参，避免权限交给 LLM |
| **LLM 模型** | 继承父 `llm_client` | `AgentConfig.model` → 新建独立 client | P0 | 不入工具参数；默认零开销 |
| system_prompt | 默认 PromptBuilder | `AgentConfig.system_prompt` + 实例覆盖 `_get_system_prompt` | P0 | 不改 UniversalAgent |
| max_steps / output_format | 8 / summary | `AgentConfig` 字段 | P0 | 配置驱动 |
| 名称/别名 | `delegateagent` 唯一 | `TOOL_NAME_ALIASES` 增条目 → `normalize_tool_name` | P0 | 不另注册工具、不改调用点 |
| 工具回调通道 | 入口层注入 | `ContextVar` set/reset（hooks/text_task/notice/question/generate/session_id/precheck/delegate） | P0 | 工具层零越层，新增回调不动工具代码 |
| 事件总线 | 私有纯内存 buffer | `_delegate_scope` 可换 sink（P2 `agent.event_sink` 注入） | P0/P2 | 不改 react_loop/runner |
| ReAct 引擎 | `react_loop.run_react_cycle` | 共用同一引擎，差异全在配置 | P0 | 子 Agent 零重写 |
| 并行上限 | 6 | `tool_constants.MAX_PARALLEL_SUB_AGENTS` | P0/P1 | 常量单点，校验落 tool_runner |
| 同步/异步 | `wait=True` 同步 | `wait` 参数切 P1 异步 + 完成通知通道 | P0/P1 | 不新增工具，参数复用 |
| 完成通知通道 | notice/Step | 经现有 notice 通道回灌，可换实现 | P1 | 不改 conversation_history 装配 |
| 插件/Skill | 内置注册 | `plugins/*/manifest.json` + `load_from_manifest` | P1 | 新增插件不放代码 |

**未列为扩展点（有意封闭，理由充分）**：工具集/模型/权限**不入工具参数**——这三类是"这个 agent 是谁"的配置属性，交给 LLM 入参会破坏递归防护与能力承诺（见 §2.2、§7.3）；ReAct 循环本身封闭——父子共用同一引擎，不允许子 Agent 定制循环逻辑，避免分叉出难以维护的多套实现。

**架构三性**：
- **灵活**：上表 13 个扩展口均为"配置字段 / 注册表条目 / ContextVar 回调 / 策略参数"，新增能力不改调用链主干。
- **可靠**：每个扩展位都有明确默认值（继承父、内存 buffer、同步 wait），缺配置即走零开销默认路径；异常路径有 finally 清理（client 归还、buffer 回收、token reset）。
- **高效**：默认路径不新建进程/线程/client/池（§7.1），扩展时才付额外成本，符合"按需付费"。

---

## 3 与现有代码的集成

### 3.1 工具注册（agent_register.py 扩展）

在 `_register_agent_tools()` 中增加 `delegateagent` 注册：

```python
# agent_register.py 扩展
from app.tools.agent.delegateagent import delegateagent
from app.tools.agent.delegateagent_schema import DelegateAgentInput

AGENT_TOOL_DESCRIPTIONS["delegateagent"] = (
    "委托子Agent执行独立任务。子Agent拥有独立上下文和工具子集，"
    "适用于：并行搜索不同来源、独立审查验证、工具专精任务、知识库多域对照分析。"
    "参数：agent_id(可用列表见下) + task(自包含任务描述) + context(可选附加信息) + wait(默认同步等待结果)。"
    "子Agent完成后回传摘要和token用量，父Agent整合结果继续。"
    "可用agent_id: researcher(搜索研究), reviewer(独立审查), kb_analyst(知识库分析)。"
)
AGENT_INPUT_MODELS["delegateagent"] = DelegateAgentInput
AGENT_TOOL_EXAMPLES["delegateagent"] = [
    {
        "agent_id": "researcher",
        "task": "搜索 2026年 Windows 桌面 Agent 框架的最新进展，重点关注上下文隔离和工具子集设计",
        "context": {"focus": "上下文隔离", "time_range": "2026"},
    }
]
# hide_from_steps 不加：delegateagent 是业务工具，前端步骤流可见
```

注意：`delegateagent` **不加入** `AGENT_HIDE_FROM_STEPS`（它是有业务产出的工具，前端步骤流应展示"正在委托 researcher 子Agent..."）。

### 3.2 工具子集注入

子 Agent 的工具注入复用 `ToolLoader.init_tools(initial_categories)`：

```python
# delegateagent_runner.py 中
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
if tool_name == "delegateagent" and is_success(result):
    sub_usage = result.get("data", {}).get("usage", {})
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        agent.accumulated_usage[key] += sub_usage.get(key, 0)
```

这样父 Agent 的 `FinalStep` 终态输出中已包含子 Agent 的 token 消耗。

### 3.4 SSE 隔离（P0 已实现）

子 Agent 的步骤**不透传**到父 Agent 的 SSE 流。父 Agent 步骤流中只看到：

```
Step N: delegateagent(researcher, "搜索...") → observation: 摘要
```

**隔离机制**：`_delegate_scope` 为子 Agent 创建 `sub_task_id` 对应的**纯内存 StreamBuffer**（`journal_sink=None`，无 `persist_sink`）。`stream_reader(buffer, task_id)` 的 buffer 是参数传入的——父 SSE 读的是父 buffer 对象，子事件写入子 buffer，天然不可见；同时不写 `chat_task_steps` / `chat_tasks`，不产生幽灵任务行。循环结束 `reclaim_memory_buffer(sub_task_id)` 回收。

子 Agent 内部步骤只在日志中记录（`logger.debug`），前端不可见。

P2 阶段可考虑（暂不实施）：
- 父 Agent 步骤中嵌套显示子 Agent 的步骤（折叠/展开）
- 显式把子 Agent 的 StepEmitter 事件经父级 SSE 转发（需改 `stream_orchestrator._SSE_FORWARD_TYPES` 白名单与嵌套渲染）

### 3.5 名称归一：其它生态名 → delegateagent

主名称唯一：`delegateagent`。其它生态的叫法不另注册工具，而是走工具名别名层归一——复用现成的 `tools_alias_mapper.TOOL_NAME_ALIASES` 与 `normalize_tool_name`，零重复定义、零歧义。

**文件位置**：`backend/app/tools/tools_alias_mapper.py`（扩展 `TOOL_NAME_ALIASES`）

```python
# tools_alias_mapper.py — TOOL_NAME_ALIASES 新增条目（大众生态名 → 本系统主名）
# 已有 normalize_tool_name() 在 registry.get_tool / resolve_registered_tool 内被调用，
# 别名自动生效，无需改任何调用点。
TOOL_NAME_ALIASES.update({
    "subagent":         "delegateagent",  # OpenCode 官方 tool 名
    "delegate_task":    "delegateagent",  # CrewAI/MetaGPT 概念名
    "delegate_to_agent":"delegateagent",  # 社区 Multi-Agent 教程常见名
    "call_agent":       "delegateagent",  # 通用动宾叫法
    "invoke_agent":     "delegateagent",  # 企业生态叫法
})
```

**归链**：LLM 生成任一别名 → `normalize_tool_name` 命中 → 返回 `delegateagent` → 查注册表得到唯一工具实现。工具列表只暴露 `delegateagent` 一个，不浪费 token；参数名不变（`agent_id`/`task`/`context`/`parallel`/`wait`），schema 校验天然兼容。

**可选参数别名（P1，仅当 LLM 按 OpenCode 习惯传参时）**：OpenCode 的 `subagent` 用 `prompt` 传任务描述，本系统用 `task`，可在 `PARAM_ALIASES["delegateagent"]` 加 `{"prompt": "task"}`；`description` 无对应字段则按 `PARAM_DROP` 丢弃，避免白废一轮。

**YAGNI 边界**：只收录真实存在的高频大众名，不自造别名；新增别名需有调用实证。

---

## 4 防递归与安全防护

### 4.1 递归防护

| 防护层 | 机制 |
|--------|------|
| **配置层** | `AgentConfig.allow_delegate=False`（默认），子 Agent 工具集剔除 AGENT 分类 |
| **实例层** | 子 Agent 的 `_tools_dict` 中不含 `delegateagent`，LLM 看不到该工具 |
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
| 连接池 | 默认共享父 Agent 的 `llm_client`（连接池天然并发安全）；`AgentConfig.model` 非 None 时新建独立 client，用完关闭 |
| 取消联动 | P0 入口检查父任务取消状态；运行中子 Agent 随父轮次结束自然收口，P1 做精确联动 |
| 事件总线 | 私有纯内存 buffer，用完 `reclaim_memory_buffer` 回收，不落库不进 SSE |
| 任务台账 | `BaseAgent.__init__` 仍为子 Agent 建 tracker 行并由 `_finalize_cycle` 收尾；不写 `chat_tasks`，用户不可见，P0 接受 |

---

## 5 实施文件清单

### 5.1 新增文件

| 文件 | 职责 | 预估行数 |
|------|------|----------|
| `backend/app/services/agent/agent_config.py` | AgentConfig 数据类 + AgentRegistry + 内置注册 | ~100 |
| `backend/app/services/agent/delegateagent_runner.py` | 子 Agent 创建/运行/私有事件总线/上下文克隆/摘要提取 | ~165 |
| `backend/app/tools/agent/delegateagent.py` | delegateagent 工具函数 | ~60 |
| `backend/app/tools/agent/delegateagent_schema.py` | DelegateAgentInput pydantic 模型 | ~30 |

### 5.2 修改文件

| 文件 | 改动 | 预估 |
|------|------|------|
| `backend/app/tools/agent/agent_register.py` | 注册 delegateagent | +10 行 |
| `backend/app/tools/context.py` | 新增 delegate_callback ContextVar（token/reset 模式） | +15 行 |
| `backend/app/services/agent/tool_executor.py` | 注入 delegate 回调（token 模式）+ usage 合并 | +15 行 |
| `backend/app/services/agent/tool_runner.py` | 并行分支加 delegate 数量上限校验（唯一持有 all_calls 的层） | +8 行 |
| `backend/app/tools/tool_constants.py` | 新增 MAX_PARALLEL_SUB_AGENTS 常量 | +1 行 |
| `backend/app/tools/tools_alias_mapper.py` | `TOOL_NAME_ALIASES` 新增 5 条大众名→`delegateagent` 映射（P1 可选 `PARAM_ALIASES["delegateagent"].prompt→task`） | +6 行 |

### 5.3 不改的文件

| 文件 | 原因 |
|------|------|
| `universal_agent.py` | 不改，子 Agent 复用现有构造；`system_prompt` 用实例覆盖 `_get_system_prompt` 注入 |
| `base_agent.py` | 不改，`run_react_cycle` 薄转发给父子共用，子 Agent 直接继承 |
| `react_loop.py` | 不改，父子共用同一 ReAct 引擎（零重写）；私有纯内存 buffer 满足其对 `get_stream_buffer` 的准入要求；全局清理由上下文副本隔离 |
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
  "model": null,
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
| `model` | 否 | 指定模型（null=继承父 Agent 的 LLM；非 null 时新建独立 client） |
| `max_steps` | 否 | 最大步数（默认 8） |
| `output_format` | 否 | summary/structured（默认 summary） |

### 6.3 加载时机

应用启动时扫描 `plugins/` 目录，逐目录读 `manifest.json`，调 `AgentRegistry.load_from_manifest()` 注册。`load_from_manifest` 对未知 `tool_categories` 值逐项 warning 跳过并回落 `["fundamental"]`；JSON 格式错/字段缺失由扫描器捕获仅 warning 跳过，不阻塞启动。

---

## 7 通信交互与数据流总览

### 7.1 主 Agent 的四条通信通道

主 Agent 同时与四个对象通信，各有独立载体，互不串扰：

| 通道 | 对象 | 载体 | 谁消费 |
|------|------|------|--------|
| ① LLM 回路 | LLM | `message_builder.conversation_history`（内存消息列表） | 仅 LLM |
| ② 工具层 | 各工具实现 | `ContextVar` 回调注入（hooks/text_task/notice/question/generate/session_id/precheck/delegate） | 工具实现 |
| ③ 前端 | 浏览器 SSE | `StreamBuffer.event_log`（`agent_streams[task_id]`） | `stream_reader` → SSE 帧 |
| ④ 子 Agent | 子会话 | `delegate_callback` + 返回字典 | 父 Agent 的 conversation_history |

- **① LLM 回路**：每轮 `react_step._process_single_step` → `call_llm_with_fallback` 把 `conversation_history` 发给模型；LLM 回 `action`(tool_calls) 或 `answer`。工具结果经 `build_observation` → `message_builder.add_tool_result(tool_call_id, content)` 以 `role=tool` 消息追加回历史，与 `add_assistant_tool_call` 按 `tool_call_id` 配对，下一轮 LLM 带上完整历史。
- **② 工具层**：`tool_executor.execute_tool` 调工具前把闭包注入 ContextVar，工具内部只消费、不 import services；finally 按 token reset。`delegateagent` 就走这条已验证通道。
- **③ 前端**：所有 Step 经 `StepEmitter` → `buffer.publish()` 写入 `event_log`；`stream_reader(buffer, task_id, after_seq)` 按 seq 读并转 SSE。该通道只给前端，也是断线重连回放源。
- **④ 子 Agent**：见 §7.2。

> 关键边界：**LLM 只看 conversation_history**，看不到 SSE、看不到前端、看不到子 Agent 内部步骤；**SSE 只给前端**，两条通道完全独立。

**执行模型定位（本设计的核心架构模式）**：子 Agent **不是子进程，也不是宿主的子线程**，而是同一 Python 进程、同一 OS 线程、同一 asyncio 事件循环上的一个协程任务（`asyncio.create_task`），靠 `copy_context()` 复制 ContextVar 做**逻辑隔离**。这是本设计的架构选择——用"不创建 OS 执行单元"换取零框架改动与轻量上下文隔离。

| 层次 | 执行单元 | 依据 |
|------|----------|------|
| 子 Agent 的 ReAct 循环 | 事件循环上的协程 Task | `asyncio.create_task(..., context=scope_ctx)`；`run_react_cycle` 全程 `async def` |
| LLM 调用 | 同一事件循环的异步 I/O | `httpx.AsyncClient` + 共享池（`_SharedClientPool`/`ConnectionScope`）+ `asyncio.Semaphore` 排队 |
| 同步工具实现 | 线程池（有界 WorkerPool / `asyncio.to_thread`） | `tool_retry_engine._execute_tool_once` |
| shell / 文件预演 | 真正的 OS 子进程（`subprocess.Popen` + Job Object） | `sandbox/backend.py`、`SandboxExecutor` |

即：**控制流全程是协程；只有工具执行才可能突破到线程/进程边界**。子 Agent 本身不另起进程或线程。

由此产生的架构边界（P0 接受，后续阶段按需升级）：

1. **无资源隔离**：父子共享进程内存、`llm_client`、事件循环；子 Agent 的 CPU 密集操作会阻塞父 Agent，不是"互不影响的子任务"。
2. **I/O 并发非 CPU 并行**：多个子 Agent 靠 `asyncio.gather` 交错执行，只在 I/O 等待时切换；token/连接池共享（信号量排队）。
3. **隔离唯一手段是 ContextVar 副本**：凡绕过 ContextVar 读写模块级全局状态（`agent_streams`、`_last_heal_attempt`）者，父子会串味——这是全局清理反噬问题（§4.2）的根源。

### 7.2 委托数据流

```
主 Agent LLM 回路（① conversation_history）
  │  LLM 决定调用 delegateagent(agent_id="researcher", task="...")
  ▼
tool_executor.execute_tool()
  │  注入 delegate_callback ContextVar（② 工具层通道）
  │  并行分支: asyncio.gather(多个 delegateagent 调用)
  ▼
tools/agent/delegateagent.py (工具函数)
  │  取 callback → await callback(agent_id, task, context, parallel, wait)
  ▼
delegateagent_runner.run_delegate(agent=父agent, agent_id, task, context, parallel, wait)
  │  1. 查 AgentRegistry.get(agent_id) → AgentConfig；父任务取消则跳过
  │  2. 递归防护: 剔除 AGENT 分类；system_prompt 覆盖 _get_system_prompt
  │  3. 创建 UniversalAgent(llm_client, sub_task_id, max_steps, initial_categories)
  │  4. 组装 sub_task 描述（task≤500字 / 单 context 值≤200字）
  │  5. _delegate_scope: 建 sub_task_id 纯内存 buffer + copy_context()
  │  6. asyncio.create_task(..., context=副本) 跑 run_react_cycle（有界 max_steps）
  │  7. 从 FinalStep.response 提取结果 + accumulated_usage；finally 回收 buffer
  ▼
返回 {"status", "summary", "usage", "steps"}（④ 子 Agent 通道）
  │  summary 来源：_extract_summary 取子 Agent 的 FinalStep.response（任务总结正文）；
  │               失败时回落 error_message / reasoning；无终态时降级取末步 get_content()
  ▼
工具层 build_success → llm_data={"summary", "action", "status": {"exec_code":"success"}}
  │
  ▼
observation_formatter._format_llm_data → observation 文本：
  │   "工具执行: 委托子Agent 调用工具-delegateagent - 执行结果: 成功\n观察: <summary>"
  ▼
message_builder.add_tool_result(tool_call_id, observation_text)  → 父 conversation_history（①）
  │
  ├─ tool_executor: usage 合并到 agent.accumulated_usage（③ 之外，仅供终态统计）
  └─ 父 Agent LLM 下一轮看到 observation（摘要+用量）→ 继续 ReAct 循环
```

子 Agent 内部步骤写入私有 buffer（§3.4），既不进父 SSE（③），也不进父 conversation_history（①）；只在日志中留痕。

### 7.3 通信交互对委托设计的三条约束

1. **结果回灌的唯一入口是 conversation_history**：父 LLM 只看①，看不到子 Agent 内部步骤。因此 `_extract_summary` 取出的 `FinalStep.response` 直接决定父 Agent 看到什么——摘要字段必须准确（见 §2.6 修复后的 `_extract_summary`）。

2. **SSE 与 LLM 上下文是两条独立通道**：子事件写私有 buffer，既不到父 SSE（前端不可见），也不到父 conversation_history（LLM 不可见），这是 §3.4 隔离目标的机制保证。

3. **P1 异步完成通知走③（notice/Step）而非直接改①**：父 Agent 此刻可能正等其它工具结果，直接写 conversation_history 会破坏 tool_call 的 assistant/tool 配对。应经 notice 事件回灌、由父 Agent 下一轮自主处理；通知携带 `delegate_id` 以区分并发异步委托（见 §2.2 `wait=False` 说明）。

---

## 8 优先级与里程碑

| 阶段 | 内容 | 预估工期 |
|------|------|----------|
| **P0** | AgentConfig + AgentRegistry + delegateagent_runner（含私有 buffer + 上下文克隆）+ delegateagent 工具（同步 `wait=True`）+ ContextVar + 注册 + 内置 3 个 Agent | 2-3 天 |
| **P0** | 工具子集注入验证（子 Agent 确实看不到 AGENT 分类工具） | 同 P0 |
| **P0** | SSE/DB 隔离验证（子步骤不进父 SSE、不写 chat_task_steps）+ 父授权不被清零 | 同 P0 |
| **P0** | usage 合并到父 Agent accumulated_usage | 同 P0 |
| **P0** | 别名归一：`TOOL_NAME_ALIASES` 增 5 条大众名→`delegateagent`（§3.5） | 0.5 天 |
| **P0** | `AgentConfig.model` 配置层扩展位（默认继承父 LLM，非 None 新建独立 client） | 含在首版 |
| **P1** | `wait=False` 异步模式：立即返回 `delegate_id` + 后台完成通知回灌（复用 shell background 范式） | 1-2 天 |
| **P1** | 并行上限校验落地 `tool_runner.execute_tools` | 0.5 天 |
| **P1** | 插件 manifest 加载 + `plugins/` 目录扫描 | 1 天 |
| **P1** | `tool_names` 名粒度过滤（构造 retry_engine 前筛 + `get_openai_tools` 接 tool_names）；可选 `PARAM_ALIASES["delegateagent"].prompt→task` | 1 天 |
| **P1** | `timeout` 字段、`allow_delegate=True` 精确多层委托（≤2层）、取消精确联动 | 1 天 |
| **P2** | SSE 子 Agent 步骤折叠透传（改 `_SSE_FORWARD_TYPES` + 嵌套渲染） | 暂缓 |
| **P2** | 事件 sink 注入（`react_loop._publish` 可注入 `agent.event_sink`），去掉私有 buffer 通行证 | 暂缓 |

---

## 9 设计决策记录

| 决策 | 理由 |
|------|------|
| 子 Agent 复用 `UniversalAgent` 而非新 Agent 子类 | KISS-DIRECT：现有类已支持 `initial_categories`，无需新抽象 |
| 不走 `agent_runner.run_agent_in_background` | 子 Agent 是同步子过程不是用户任务；完整 runner 的台账/取消/重连/统计属用户任务语义，套上去是类别错误 |
| 私有纯内存 buffer 而非改 runner 加开关 | 复用 `create_task_stream_buffer(..., journal_sink=None)` 现成纯内存模式；框架零改动、SSE/DB 天然隔离 |
| 上下文副本（`copy_context` + `create_task(context=)`） | `clear_temp_auth` / `reset_current_task_id` 是 ContextVar 作用域操作，副本天然隔离父子，优于手工保存恢复 |
| 子 Agent 用协程 Task 而非子进程/线程 | 同进程同事件循环、复用共享 LLM 连接池；零框架改动、零序列化开销；代价是无崩溃/CPU 隔离，P0 接受（见 §7.1） |
| `AgentConfig.model` 配置层扩展位，不入工具参数 | OCP：默认 None 继承父 LLM 零开销；扩展时配置指定即新建独立 client；模型身份构造期定死，无 per-request model 参数 |
| `delegateagent` 不 hide_from_steps | 业务产出工具，前端应展示 |
| usage 合并放在 tool_executor 侧 | 工具层不感知 Agent 内部字段，由执行框架统一收口（注意须按 `llm_data.status.exec_code` 契约判定成功） |
| 内置 3 个 Agent 而非动态生成 | P0 先固定，验证收益后再开放插件注册 |
| 子 Agent 不继承父对话历史 | 上下文隔离是核心价值，继承会失去隔离意义 |
| 子 Agent task 描述自包含（≤500字 / 单 context 值≤200字） | 防 LLM 把整个对话塞进 context 导致子 Agent 上下文膨胀 |
| P0 只做分类粒度工具集，名粒度推迟 P1 | 现成 `to_openai_tools(tool_names=)` 只控可见性不控执行，需与 `ToolRetryEngine` 构造前筛选联动 |
| 主名称定为 `delegateagent`，其它生态名走别名归一 | 名称唯一、零重复注册；复用 `TOOL_NAME_ALIASES`/`normalize_tool_name` 现成能力，注册表 `get_tool`/`resolve_registered_tool` 已内置归一调用，零改调用点 |
| `wait` 默认 True（P0 同步）/ False（P1 异步） | P0 先跑通同步直线路径；异步复用 shell background 完成通知范式，结果与父取消联动在 P1 补齐 |
