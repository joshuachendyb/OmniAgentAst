# OmniAgent对话预处理及Agent的流程设计文档

**创建时间**: 2026-03-25 13:51:48
**更新时间**: 2026-03-25 19:00:00
**版本**: v2.10
**编写人**: 小沈

---

## 📚 参考文档

本设计文档参考以下文档：

| 参考文档 | 说明 |
|---------|------|
| `Agent分层重构设计方案-小沈-2026-03-25.md` | Agent分层架构设计原始方案，提供了BaseAgent与IntentReactAgent继承关系的详细设计 |
| `LLM调用prompt中间层设计方案-小沈-2026-03-24.md` | Prompt中间层设计，定义了Prompt构建和管理的架构 |
| `多意图系统与现有代码整合架构设计-2026-03-22.md` | 多意图系统与现有代码的整合架构 |
| `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` | 预处理与多意图代码目录结构说明 |

---

## 版本历史

| 版本 | 时间 | 更新内容 |
|------|------|---------|
| v1.0 | 2026-03-25 13:51:48 | 初始版本：对话预处理流程设计 |
| v1.1 | 2026-03-25 14:03:14 | 修正架构：预处理调用chat2，不是chat2调用预处理 |
| v1.2 | 2026-03-25 14:14:04 | Session管理并入chat2，职责更清晰 |
| v1.3 | 2026-03-25 14:18:02 | 补充文件引用、history处理、实际参数核对 |
| v1.4 | 2026-03-25 14:22:49 | 补充agent创建、意图判断逻辑、函数引入路径 |
| v1.5 | 2026-03-25 15:33:27 | 新增1.1.1问题发现过程，详细记录问题发现步骤 |
| v2.0 | 2026-03-25 16:00:00 | 合并对话预处理流程设计 + Agent分层重构设计方案，成为完整设计文档 |
| v2.1 | 2026-03-25 17:10:00 | 添加参考文档章节 |
| v2.2 | 2026-03-25 17:30:00 | 优化章节布局：整合Agent分层设计到第四章，合并文件位置与职责划分到第六章，统一待实现清单到第七章 |
| v2.3 | 2026-03-25 17:40:00 | 第一章1.3节添加说明，整合自参考文档Agent分层重构设计方案 |
| v2.4 | 2026-03-25 17:45:00 | 第二章2.1节添加Agent说明，特指IntentReactAgent |
| v2.5 | 2026-03-25 17:50:00 | 第二章2.3节添加chat2与Agent关系详细说明 |
| v2.6 | 2026-03-25 17:55:00 | 第四章标题改为Agent分层架构设计与实现说明，删除4.6实施步骤移到第七章 |
| v2.7 | 2026-03-25 18:00:00 | 确认7.4节已包含Agent分层重构待实现项 |
| v2.8 | 2026-03-25 18:40:00 | 新增7.1本次代码重组原则 |
| v2.9 | 2026-03-25 18:50:00 | 修正7.2/7.3/7.4，严格按照2.1架构：预处理是独立模块在路由层调用，禁止在chat2内部调用预处理 |
| v2.10 | 2026-03-25 19:00:00 | 修正7.5 Agent分层重构，整合4.5.2未完成项，不是清空重写 |

---

## 一、背景说明

### 1.1 问题描述

#### 1.1.1 问题发现过程

**时间**: 2026-03-25 13:00-15:30

| 步骤 | 发现内容 | 关键人物 |
|------|---------|---------|
| ① | 北京老陈要求深度代码检查，对比v0.7.92与v0.7.90差异 | 老陈 |
| ② | 发现主干流程（chat2 → ver1_run_stream → run_stream）缺失 preprocessor 和 intent_registry | 小沈 |
| ③ | 发现支流流程（chat_non_stream → run → _run_with_session）反而有完整的预处理功能 | 小沈 |
| ④ | 老陈点醒："chat-non-stream是废弃的支流，chat2才是主干，主干反而缺功能，跑到支杆上去了" | 老陈 |
| ⑤ | 小沈写错架构方向：以为是 chat2 调用预处理 | 小沈 |
| ⑥ | 老陈纠正："预处理调用chat2，职责不能混淆，chat2只做流式输出" | 老陈 |
| ⑦ | 老陈建议：Session管理并入chat2，预处理只做预处理+意图识别 | 老陈 |
| ⑧ | 小沈重新梳理调用关系、参数传递，完善文档 | 小沈 |
| ⑨ | 小健两轮代码审查，发现遗漏细节，小沈补充完善 | 小健/小沈 |

#### 1.1.2 问题根因

**上一次 Agent 重构时**（2026-03-22~25），把预处理 + 意图识别 + Session管理全部放到了支流代码 `_run_with_session()` 方法中，而主干流程 `run_stream()`（base.py）直接用的原始版本，没有这些功能。

**结果**：
- 主干（chat2 → run_stream）：缺失预处理 ❌
- 支流（chat_non_stream → _run_with_session）：有完整预处理 ✅
- 支流是废弃代码，主干才是生产代码，**功能放反了**

### 1.2 现状对比

| 流程 | 代码路径 | preprocessor | intent_registry | Session管理 |
|------|----------|-------------|-----------------|-------------|
| **主干**（流式） | chat2 → ver1_run_stream → run_stream | ❌ 缺失 | ❌ 缺失 | ✅ 有 |
| **支流**（非流式） | chat_non_stream → run → _run_with_session | ✅ 有 | ✅ 有 | ✅ 有 |

### 1.3 Agent内部架构问题

> **📝 说明**：本节整合自参考文档 `Agent分层重构设计方案-小沈-2026-03-25.md` 第一章

#### 1.3.1 问题描述

```
BaseAgent (base.py) - 定义了一套循环逻辑
IntentAgent (agent.py) - 完全重写了另一套循环逻辑 ← 问题！
```

- agent.py 没有继承/调用 base.py 的核心逻辑
- 测试和生产代码不一致
- 维护困难

#### 1.3.2 正确设计

```
BaseAgent (base.py) 
    ↓ 定义核心逻辑（base = 基础）
IntentAgent (agent.py)
    ↓ 继承并调用 base 的方法
chat2.py
```

- base.py 是核心基准
- agent.py 继承 base.py，调用其方法
- 测试和生产用同样的核心逻辑

#### 1.3.3 当前问题总结

| 问题类型 | 具体问题 | 影响 |
|---------|---------|------|
| **外部流程问题** | 预处理功能放在废弃的支流代码中 | 主干流程缺失预处理功能 |
| **内部架构问题** | agent.py 重写循环逻辑，没有继承 base.py | 代码重复，维护困难 |
| **可扩展性问题** | base.py 的 run_stream 没有拆分成可扩展的子方法 | 子类无法针对特定阶段进行定制 |

---

## 二、整体架构设计

### 2.1 外部调用架构（预处理 → chat2 → Agent）

> **📝 说明**：本节提到的 **Agent** 特指 `IntentReactAgent`（agent.py），是文件操作/网络操作的智能代理，基于 ReAct 循环实现。

```
用户请求
    ↓
┌─────────────────────────────────────────┐
│          预处理模块 (preprocessing.py)   │
│  1. preprocessor.process()             │
│  2. intent_registry.get()              │
│  3. 完整预处理与意图识别              │
└─────────────────────────────────────────┘
    ↓
返回: intent_type + intent_def + 处理后的 task
    ↓
调用 chat2.handle_stream()
    ↓
┌─────────────────────────────────────────┐
│            chat2.py（入口+执行）         │
│  1. Session 创建/管理                   │
│  2. 根据 intent_type 决定分支           │
│  3. 流式输出具体工作                   │
└─────────────────────────────────────────┘
    ↓
    ├──────────────┴──────────────┐
    ↓                              ↓
 无动作                          有动作
 (普通对话)                     (文件操作/网络操作)
    ↓                              ↓
 chat_stream_query             IntentReactAgent
 (流式chunk发送)               (ReAct循环)
    ↓                              ↓
 流式yield                    流式yield事件
 chunk/final                 + _on_before_loop()
```

### 2.2 预处理模块职责

预处理模块（`preprocessing.py`）是**入口**，负责：

| 步骤 | 功能 | 输出 |
|------|------|------|
| 1 | preprocessor.process() | 意图类型、置信度、处理后的文本 |
| 2 | intent_registry.get() | 意图定义（name, description） |
| 3 | 返回决策数据 | intent_type + intent_def + task |

### 2.3 chat2.py 职责

> **📝 chat2.py 与 Agent 的关系说明**：
> - **chat2.py** 是**入口调度层**，负责接收预处理结果，根据 `intent_type` 决定走哪条分支
> - **IntentReactAgent** 是**执行层**，在需要文件操作/网络操作时调用，实现 ReAct 循环
> - chat2 调用 Agent，而不是包含 Agent，两者职责分离

chat2.py 是**入口+执行**，负责：

| 步骤 | 功能 |
|------|------|
| 1 | Session 创建/管理 |
| 2 | 根据 intent_type 决定分支 |
| 3 | 流式输出具体工作 |
| 4 | 有动作时：调用 IntentReactAgent.ver1_run_stream() |
| 5 | 无动作时：调用 chat_stream_query() |

### 2.4 文件引用关系

| 模块/函数 | 引用路径 |
|-----------|---------|
| PreprocessingPipeline | `from app.services.preprocessing import PreprocessingPipeline` |
| IntentRegistry | `from app.services.intent import IntentRegistry, Intent` |
| IntentReactAgent | `from app.services.agent import IntentAgent as FileOperationAgent` |
| AIServiceFactory | `from app.services import AIServiceFactory` |
| cache_display_name | `from app.utils.display_name_cache import cache_display_name` |
| check_command_safety | `from app.services.shell_security import check_command_safety` |

### 2.5 历史消息处理

| 消息类型 | 处理方式 |
|----------|---------|
| 最后一条用户消息 | 经过 preprocessor.process() 处理后传入 chat2 |
| 历史消息（messages[:-1]） | 直接传给 chat2，由 chat2 传给 chat_stream_query |

### 2.6 意图判断逻辑

预处理返回的 intent_type 可能有以下值：

| intent_type | 处理方式 |
|-------------|---------|
| file_operation | 有动作 → ReAct 循环 |
| network_operation | 有动作 → ReAct 循环 |
| chat / unknown / 其他 | 无动作 → 普通对话 |

### 2.7 函数调用关系

#### 2.7.1 preprocessing.py（入口）

```python
from app.services.preprocessing import PreprocessingPipeline
from app.services.intent import IntentRegistry, Intent

# 全局实例
_preprocessor = PreprocessingPipeline()
_intent_registry = IntentRegistry()

async def handle_request(request: ChatRequest):
    """
    预处理入口函数
    职责：预处理 → 意图识别 → 调用chat2
    """
    # 1. 预处理
    task = request.messages[-1].content
    intent_names = _intent_registry.get_all_names()
    preprocessed = _preprocessor.process(task, intent_names, session_id=None)
    
    # 2. 意图识别
    intent_type = preprocessed.get("intent", "unknown")
    intent_def = _intent_registry.get(intent_type)  # 获取意图定义
    
    # 3. 历史消息（不经过预处理）
    history = request.messages[:-1]
    
    # 4. 调用 chat2.py（传入预处理结果和意图定义）
    async for event in chat2.handle_stream(
        last_message=preprocessed["corrected"],
        intent_type=intent_type,
        intent_def=intent_def,  # 意图定义传给 chat2
        history=history,
        request=request,
    ):
        yield event
```

#### 2.7.2 chat2.py（入口+执行）

```python
from app.services.agent import IntentAgent as FileOperationAgent
from app.services import AIServiceFactory

async def handle_stream(
    last_message: str,        # 预处理后的用户消息
    intent_type: str,         # 意图类型
    intent_def,               # 意图定义
    history: List[Message],   # 历史消息（不经过预处理）
    request: ChatRequest,     # 原始请求
):
    """
    chat2.py 入口+执行函数
    
    职责：
    1. Session 创建/管理
    2. 根据 intent_type 决定分支
    3. 流式输出具体工作
    """
    # ========== 1. 初始化（Session、AI服务、计数器） ==========
    session_id = request.session_id or create_session(...)
    ai_service = AIServiceFactory.get_service_for_model(request.provider, request.model)
    
    # 步骤计数器
    step_counter = 0
    def next_step():
        nonlocal step_counter
        step_counter += 1
        return step_counter
    
    # ========== 2. 根据 intent_type 决定分支 ==========
    if intent_type in ["file_operation", "network_operation"]:
        # 有动作 → 走 ReAct 循环
        
        # 创建 LLM 客户端适配器
        async def llm_client(message, history=None):
            response = await ai_service.chat(message, history)
            return type('obj', (object,), {'content': response.content})()
        
        # 创建 Agent 实例
        agent = FileOperationAgent(
            llm_client=llm_client,
            session_id=session_id
        )
        
        async for event in agent.ver1_run_stream(
            task=last_message,
            model=ai_service.model,
            provider=ai_service.provider,
            context={"session_id": session_id, "intent_def": intent_def},
            get_next_step=next_step,
        ):
            yield event
    else:
        # 无动作 → 走普通对话
        async for event in chat_stream_query(
            request=request,
            ai_service=ai_service,
            last_message=last_message,
            history=history,
            ...
        ):
            yield event
```

---

## 三、参数传递设计

### 3.1 预处理 → chat2

| 参数 | 说明 | 来源 |
|------|------|------|
| last_message | 预处理后的用户消息 | preprocessor.process() 返回的 corrected |
| intent_type | 意图类型 | preprocessor.process() 返回的 intent |
| intent_def | 意图定义 | intent_registry.get() 返回 |
| history | 历史消息（不含最后一条） | request.messages[:-1] |
| request | 原始请求对象 | API 传入 |

### 3.2 chat2 内部准备

| 参数 | 说明 | 准备方式 |
|------|------|---------|
| session_id | Session ID | request.session_id 或创建新 session |
| ai_service | AI 服务实例 | AIServiceFactory.get_service_for_model() |
| step_counter | 步骤计数器 | 局部变量 |
| next_step | 计数函数 | chat2 内定义的局部函数 |

### 3.3 chat2 → IntentReactAgent.ver1_run_stream()

**实际参数（已核对代码）**：

```python
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id
)

agent.ver1_run_stream(
    task=last_message,                    # 预处理后的用户消息
    model=ai_service.model,                # 模型名称
    provider=ai_service.provider,           # Provider 名称
    context={"session_id": session_id, "intent_def": intent_def},  # 上下文（含意图定义）
    system_prompt=None,                    # 可选自定义 prompt
    max_steps=100,                         # 最大迭代次数
    get_next_step=next_step,               # step 计数函数
)
```

### 3.4 chat2 → chat_stream_query()

**实际参数（已核对代码）**：

```python
chat_stream_query(
    request=request,                       # 原始请求
    ai_service=ai_service,                  # AI 服务实例
    task_id=task_id,                       # 任务 ID
    llm_call_count=llm_call_count,         # LLM 计数器
    current_execution_steps=[],            # 执行步骤列表
    current_content="",                    # 当前累积内容
    last_is_reasoning=None,                # 上一个 reasoning 状态
    last_message=last_message,              # 预处理后的用户消息
    running_tasks=running_tasks,            # 运行任务字典
    running_tasks_lock=running_tasks_lock, # 锁
    next_step=next_step,                   # step 计数函数
    display_name=display_name,             # 显示名称
    session_id=session_id,                 # Session ID
    save_execution_steps_to_db=save_fn,   # 保存函数
    add_step_and_save=add_step_fn,         # 添加步骤函数
)
```

---

# 四、Agent分层架构设计与实现说明

> **📝 说明**：本节整合自参考文档 `Agent分层重构设计方案-小沈-2026-03-25.md`，以实际代码为参考标注实现状态。

### 4.1 设计原则

| 原则 | 说明 |
|------|------|
| **生产代码是基准** | 以 agent.py 的 run_stream 为准 |
| **base.py 向生产代码看齐** | 用正确的逻辑更新 base.py |
| **agent.py 继承 base.py** | 而不是重写 |

### 4.2 继承架构图

```
┌─────────────────────────────────────────┐
│     IntentReactAgent (agent.py) (扩展层) │
│  - 继承 BaseAgent                       │
│  - 添加扩展功能:                        │
│    • session 管理                        │
│    • prompt 日志                        │
│    • preprocessor                       │
│    • intent_registry                    │
│  - 调用父类核心方法                     │
└─────────────────────────────────────────┘
                    ↓ 继承
┌─────────────────────────────────────────┐
│     BaseAgent (base.py) (核心层)       │
│  - 定义 ReAct 循环核心逻辑               │
│  - 提供抽象方法供子类实现                │
│  - 不包含任何具体实现细节                │
└─────────────────────────────────────────┘
```

### 4.3 调用关系

```
chat2.ver1_run_stream()
    ↓ 调用
agent.ver1_run_stream() ← IntentReactAgent
    ↓ 调用
run_stream() ← 父类 BaseAgent
    ↓
    ├── _step_thought() ← 可扩展
    ├── _step_action() ← 可扩展  
    └── _step_observation() ← 核心逻辑在父类
            ↓
            内部调用:
            ├── _get_llm_response() ← 子类实现
            ├── _execute_tool() ← 子类实现
            └── _add_observation_to_history() ← 父类实现
```

### 4.4 BaseAgent 抽象方法定义（参考文档）

```python
class BaseAgent(ABC):
    """Agent 核心基类"""
    
    # ===== 抽象方法（子类必须实现）=====
    
    @abstractmethod
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        pass
    
    @abstractmethod
    async def _execute_tool(self, action: str, params: Dict) -> Dict:
        """执行工具"""
        pass
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        pass
    
    @abstractmethod
    def _get_task_prompt(self, task: str, context: Optional[Dict]) -> str:
        """获取任务 Prompt"""
        pass
    
    # ===== 核心方法（子类调用）=====
    
    async def run_stream(self, task: str, context: Optional[Dict] = None, max_steps: int = 100):
        """ReAct 核心循环"""
        self._init_session(task, context)
        step_count = 0
        while step_count < max_steps:
            step_count += 1
            yield await self._step_thought()
            yield await self._step_action()
            yield await self._step_observation()
    
    # ===== 可扩展方法（子类可覆盖）=====
    
    def _init_session(self, task: str, context: Optional[Dict]):
        pass
    
    async def _step_thought(self) -> Dict:
        pass
    
    async def _step_action(self) -> Dict:
        pass
    
    async def _step_observation(self) -> Dict:
        pass
```

### 4.5 当前实现状态

**检查时间**: 2026-03-25 15:30:20  
**检查人**: 小沈

#### 4.5.1 已完成项目 ✅

| 项目 | 说明 | 代码位置 |
|------|------|---------|
| agent.py 继承 BaseAgent | 继承关系已建立 | agent.py:41 `class IntentReactAgent(BaseAgent)` |
| 实现4个抽象方法 | 子类必须实现的方法 | agent.py:197/299/313/320 |
| ver1_run_stream 调用 run_stream | 调用父类核心方法 | agent.py:657 `async for event in self.run_stream(...)` |
| base.py 核心循环逻辑 | 完整的 ReAct 循环 | base.py:108-270 |
| observation 包含实际数据 | 2026-03-25 修复 | base.py:206-212 raw_data 传递给 LLM |

#### 4.5.2 未完成项目 ❌

| 序号 | 未完成项 | 当前状态 |
|------|---------|---------|
| 1 | **_step_thought 可扩展方法** | base.py 未实现拆分 |
| 2 | **_step_action 可扩展方法** | base.py 未实现拆分 |
| 3 | **_step_observation 可扩展方法** | base.py 未实现拆分 |
| 4 | **_init_session Hook** | base.py 有 _on_session_init，但不是 _init_session |
| 5 | **_on_before_loop Hook** | base.py 有调用但没有实现 |

#### 4.5.3 差距分析

**文档设计**：base.py 应该有可扩展的 `_step_thought()`、`_step_action()`、`_step_observation()` 方法，run_stream 调用这些方法，子类可以覆盖。

**实际情况**：base.py 的 run_stream 是一个完整的函数，所有逻辑都在里面，没有拆分成可扩展的子方法。

**影响**：当前架构可扩展性不足，子类无法针对特定阶段进行定制。

---

## 五、事件类型定义

### 5.1 ReAct 循环事件（IntentReactAgent）

| 事件类型 | 说明 | 包含字段 |
|----------|------|---------|
| start | 会话开始 | task, session_id |
| thought | LLM 思考过程 | step, content, reasoning, action_tool, params |
| action_tool | 工具执行 | step, action_tool, params |
| observation | 执行结果 | step, result |
| final | 最终回复 | content |
| error | 错误信息 | code, message |

### 5.2 普通对话事件（chat_stream_query）

| 事件类型 | 说明 | 包含字段 |
|----------|------|---------|
| start | 会话开始 | task |
| chunk | 流式输出 | content |
| final | 完成信号 | content |

---

## 六、文件位置与职责划分

### 6.1 文件位置

| 文件 | 说明 |
|------|------|
| `backend/app/chat_stream/preprocessing.py` | 预处理入口模块（新建） |
| `backend/app/api/v1/chat2.py` | 改为被调用方，含Session管理 |
| `backend/app/api/v1/chat.py` 或新路由 | API 入口调用 preprocessing |
| `backend/app/services/agent/agent.py` | IntentReactAgent (ver1_run_stream) |
| `backend/app/services/agent/base.py` | BaseAgent 基类（需重构） |
| `backend/app/services/preprocessing.py` | PreprocessingPipeline（已存在） |
| `backend/app/services/intent.py` | IntentRegistry（已存在） |
| `backend/app/chat_stream/chat_stream_query.py` | 普通对话流式输出 |

### 6.2 职责划分原则

#### 6.2.1 外部流程职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **preprocessing.py** | 预处理+意图识别+history处理+调用chat2 | Session管理，流式输出 |
| **chat2.py** | Session管理+ai_service创建+根据intent_type分支+流式输出 | 预处理、意图识别 |

#### 6.2.2 Agent内部职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **BaseAgent (base.py)** | 定义ReAct循环核心逻辑，提供抽象方法，定义可扩展方法 | 包含具体实现细节 |
| **IntentReactAgent (agent.py)** | 继承BaseAgent，实现抽象方法，添加扩展功能（session、prompt等） | 重写循环逻辑 |

### 6.3 Session 管理

#### 6.3.1 Session 生命周期

```
预处理阶段（可选）创建 Session
    ↓
chat2 入口创建/复用 Session
    ↓
根据 intent_type 分支（保持 session_id 一致）
    ↓
对话结束显式关闭
```

#### 6.3.2 Session 状态

| 状态 | 说明 |
|------|------|
| creating | 创建中 |
| active | 活跃 |
| completed | 已完成 |
| interrupted | 已中断 |
| error | 错误 |

---

## 七、待实现清单

### 7.1 本次代码重组原则

> **📝 说明**：本次代码重组的核心指导思想，所有待实现任务都应遵循以下原则。

| 序号 | 原则 | 说明 |
|------|------|------|
| 1 | **基础版本** | 改造的代码基础版本是 **v0.7.92** |
| 2 | **重构范围** | 本次重构的是系统**主流程**的不合理和错乱的部分代码 |
| 3 | **实现目标** | 通过部分代码的重构，和部分函数/代码文件的逻辑关系重组，实现**合理的OMNI系统运行逻辑**（流程图参考 2.1 节） |
| 4 | **改造对象** | 改造的函数、代码文件的**错乱功能** |
| 5 | **关联调用** | 重组把已经实现的功能正确的函数和代码，按照OMNI系统的流程进行**正确的关联和调用** |
| 6 | **复用原则** | 重组的代码要**尽可能使用基础版本已有功能**，可以将已有功能**函数化/文件化**，被引用 |
| 7 | **核心原则** | 引用基础版本的**各个小功能模块**的代码和功能，**不能丢失/破坏**已有的功能和小逻辑 |

#### 7.1.1 核心要点解读

**关于基础版本 v0.7.92**：
- 所有改造以 v0.7.92 为基准
- 不能脱离这个版本进行"全新设计"
- 只能在原有基础上进行调整和优化

**关于主流程重构**：
- 问题：预处理功能在废弃的支流代码中，主干流程缺失
- 目标：让主干流程具备完整的预处理功能
- 方法：参考 2.1 节的流程图，将预处理功能正确关联到主流程

**关于复用已有功能**：
- v0.7.92 中已有许多小功能模块（preprocessor, intent_registry, session管理等）
- 本次重组不是重新发明轮子
- 而是**正确地调用**这些已有模块

**关于不破坏已有功能**：
- 重组时不能影响那些已经正常工作的功能
- 只能修复错乱的部分
- 保持其他功能不受影响

### 7.2 预处理模块（独立入口）

> **📝 说明**：根据2.1架构要求，预处理是**独立模块**，在路由层调用，不是放在chat2内部
当前代码（v0.7.92）：
用户请求 → 路由 @router.post("/chat/stream") → chat2.chat_stream() → detect_file_operation_intent()

改造后：
用户请求 → 路由 @router.post("/chat/stream") → 预处理模块 → chat2.chat_stream() → Agent分支
**当前代码现状**：
- 路由层 `/chat/stream` → chat2.chat_stream() → detect_file_operation_intent()（简单函数）
- 缺少完整的预处理流程（preprocessor.process + intent_registry.get）

**2.1架构要求**（必须遵守）：
```
用户请求
    ↓
预处理模块 (preprocessing.py) ← 独立入口，在路由层调用
    ↓
返回: intent_type + intent_def + 处理后的 task
    ↓
chat2.handle_stream() ← 只接收预处理结果，不执行预处理
```

> **📝 路由层说明**：路由层 = API入口，即 `@router.post("/chat/stream")` 函数。预处理在此调用，不是chat2内部。

**改造方案**（根据2.1架构）：
- [ ] 创建/使用 `preprocessing.py` 作为预处理入口模块（参考2.1）
- [ ] 引入 PreprocessingPipeline (`from app.services.preprocessing import PreprocessingPipeline`)
- [ ] 引入 IntentRegistry (`from app.services.intent import IntentRegistry, Intent`)
- [ ] 实现预处理入口函数（如 `handle_preprocessing()`）
- [ ] 预处理入口在路由层调用，不是chat2内部
- [ ] 返回预处理结果：intent_type + intent_def + corrected_task + history

**关键约束**：
- **禁止在chat2内部调用预处理**（违反2.1架构）
- 预处理必须是独立模块，在路由层调用
- chat2只接收预处理结果，负责Session管理和分支

### 7.3 chat2.py 改造

> **📝 说明**：根据2.1架构，chat2**不执行预处理**，只负责Session管理和分支决策。

**chat2职责**（根据2.1）：
- 只接收预处理结果作为参数
- 负责Session创建/管理
- 根据intent_type决定分支（有动作/无动作）

**改造要点**：
- [ ] 修改chat2.chat_stream()接收预处理结果参数（last_message, intent_type, intent_def, history）
- [ ] **删除**chat2内部的预处理调用（detect_file_operation_intent等）
- [ ] Session 创建/管理（复用现有逻辑）
- [ ] ai_service 创建（AIServiceFactory）
- [ ] next_step 计数函数定义
- [ ] 根据 intent_type 决策分支
- [ ] 有动作：创建 FileOperationAgent + 调用 ver1_run_stream()
- [ ] 无动作：调用 chat_stream_query()
- [ ] 保留原有功能（中断检查、暂停检查、数据库保存）

### 7.4 路由改造

> **📝 说明**：根据2.1架构，路由层是整个流程的入口，负责调用预处理模块。

**路由层职责**（根据2.1）：
```
用户请求 → 路由层 → 预处理模块 → chat2 → Agent/chat_stream_query
```

**改造要点**：
- [ ] 修改 `/chat/stream` 路由入口
- [ ] 在路由层**先调用预处理模块**，获取intent_type + intent_def + corrected_task + history
- [ ] 再调用chat2.chat_stream()，传入预处理结果
- [ ] **注意**：不是直接调用chat2，是"预处理 → chat2"的串联调用

**代码结构示例**：
```python
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    # 1. 调用预处理模块
    preprocessed = await execute_preprocessing(request)
    
    # 2. 调用chat2，传入预处理结果
    async for event in chat2.chat_stream(
        last_message=preprocessed["corrected"],
        intent_type=preprocessed.get("intent"),  # preprocessor返回的key是"intent"
        intent_def=preprocessed["intent_def"],
        history=preprocessed["history"],
        request=request,
    ):
        yield event
```

### 7.5 Agent分层重构

> **📝 说明**：基于4.5.2的未完成项，补充base.py的可扩展方法。

**4.5.1已完成** ✅：继承关系、调用run_stream、核心循环逻辑

**4.5.2待实现** ❌：可扩展方法拆分

**改造要点**：
- [ ] base.py 拆分 `_step_thought()` 可扩展方法
- [ ] base.py 拆分 `_step_action()` 可扩展方法
- [ ] base.py 拆分 `_step_observation()` 可扩展方法
- [ ] base.py 实现 `_init_session()` Hook（替代 `_on_session_init`）
- [ ] base.py 实现 `_on_before_loop()` Hook
- [ ] 验证（生产功能正常 + 测试通过）

### 7.6 回归验证

- [ ] 流式对话正常（chat_stream_query 事件正确）
- [ ] 文件操作正常（ver1_run_stream 事件正确）
- [ ] 网络操作正常（ver1_run_stream 事件正确）
- [ ] Session 管理正常（创建/传递/关闭）
- [ ] 预处理正确识别意图（intent_type 正确）
- [ ] 历史消息正确传递（history 不经过预处理）
- [ ] 中断/暂停功能正常
- [ ] 数据库保存正常

---

## 八、关键实现细节

### 8.1 next_step 函数定义

```python
# 必须在使用前定义
step_counter = 0

def next_step():
    nonlocal step_counter
    step_counter += 1
    return step_counter
```

### 8.2 LLM 客户端适配器

```python
async def llm_client(message, history=None):
    response = await ai_service.chat(message, history)
    return type('obj', (object,), {'content': response.content})()
```

### 8.3 Agent 实例创建

```python
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id
)
```

---

**文档结束**

### 6.1 Session 生命周期

```
预处理阶段（可选）创建 Session
    ↓
chat2 入口创建/复用 Session
    ↓
根据 intent_type 分支（保持 session_id 一致）
    ↓
对话结束显式关闭
```

### 6.2 Session 状态

| 状态 | 说明 |
|------|------|
| creating | 创建中 |
| active | 活跃 |
| completed | 已完成 |
| interrupted | 已中断 |
| error | 错误 |

---

**文档结束**
