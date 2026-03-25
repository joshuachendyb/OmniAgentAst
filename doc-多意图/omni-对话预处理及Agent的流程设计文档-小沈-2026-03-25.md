# OmniAgent对话预处理及Agent的流程设计文档

**创建时间**: 2026-03-25 13:51:48
**更新时间**: 2026-03-25 22:28:07
**版本**: v2.28
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
| v2.11 | 2026-03-25 19:10:00 | 删除末尾重复Session内容，修正第四章标题层级，删除7.6回归验证移至附录 |
| v2.12 | 2026-03-25 19:15:00 | 修正2.7.1预处理代码示例：预处理不调用chat2，由路由层串联调用 |
| v2.13 | 2026-03-25 19:20:00 | 修正6.1文件位置（PreprocessingPipeline/IntentRegistry正确路径），修正6.2.1预处理职责（不调用chat2） |
| v2.14 | 2026-03-25 19:29:45 | 修正6.3 Session管理：补充两层Session管理（chat2.py任务管理 + session.py文件操作会话），删除不准确的Session生命周期描述，补充代码位置和实际状态值 |
| v2.15 | 2026-03-25 19:38:24 | 新增6.3.4节：添加6.3 Session管理与报告设计方案的逻辑关系图，说明两者是架构层与实现层的关系 |
| v2.16 | 2026-03-25 19:42:42 | 新增7.1.1核心教训：明确本次梳理的目的是"正确整合已有功能到主流程"，强调"单元重构完成≠重构目的达到" |
| v2.17 | 2026-03-25 19:46:12 | 新增7.3遗留问题修复：补充 `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` 7.7节的遗留问题（agent.py:452应用preprocessed['corrected']替代原始task） |
| v2.18 | 2026-03-25 19:59:02 | 修正7.4路由改造：引用整合架构设计，新增chat_router.py设计，强调chat2不能作为路由层，废除detect_file_operation_intent |
| v2.19 | 2026-03-25 20:09:30 | 整合两个文档的2.1节：合并整合架构设计的chat_router.py架构图，替换OMNI的2.1节，明确chat_router/预处理/IntentReactAgent职责分工 |
| v2.20 | 2026-03-25 20:15:07 | 新增Agent命名规范（7.5节）：IntentReactAgent统一改名为intent-file-ReactAgent，避免与BaseAgent混淆 |
| v2.21 | 2026-03-25 20:19:07 | 全面替换文档中所有IntentReactAgent为intent-file-ReactAgent（1.3/2.1/2.3/2.7/3.3/4.2/4.3/4.5/5.1/6.1/6.2节） |
| v2.22 | 2026-03-25 21:18:40 | 新增附录2：ReAct架构层次说明，明确base.py是底层ReAct、agent.py是上层Intent-*-React、chat2是混合体 |
| v2.23 | 2026-03-25 21:31:13 | 整理附录2.3为清晰的三层架构：底层ReAct(base.py)→上层Intent-*-React(agent.py)→路由层(chat_router.py待创建) |
| v2.24 | 2026-03-25 22:09:19 | 替换附录2.4为四层架构：路由层→意图特定React→chat2流式包装→base.py通用ReAct；明确agent.py约等于intent-file-ReactAgent |
| v2.25 | 2026-03-25 22:12:52 | 删除冗余的附录2.3（中间状态），保留完整的附录2.3（四层架构最终版） |
| v2.26 | 2026-03-25 22:17:08 | 修正章节编号：附录2.4改为附录2.3，各子章节同步更新 |
| v2.27 | 2026-03-25 22:20:36 | 新增附录2.4：base.py改名base-react.py，理由和同步更新说明 |
| v2.28 | 2026-03-25 22:28:07 | 完成base.py→base_react.py改名，同步更新所有导入，测试通过20个 |

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
intent-file-ReactAgent (agent.py) - 完全重写了另一套循环逻辑 ← 问题！
```

- agent.py 没有继承/调用 base.py 的核心逻辑
- 测试和生产代码不一致
- 维护困难

#### 1.3.2 正确设计

```
BaseAgent (base.py) 
    ↓ 定义核心逻辑（base = 基础）
intent-file-ReactAgent (agent.py)
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

### 2.1 外部调用架构

> **📝 说明**：整合自 `多意图系统与现有代码整合架构设计-2026-03-22.md` 2.1节
>
> **核心原则**：
> - chat_router.py **独立作为路由入口**
> - 预处理模块**独立**，不在chat2内部
> - chat2.py **只负责流式loop**，不包含路由/预处理/意图识别
> - **Agent** 特指 `intent-file-ReactAgent`（agent.py），基于 ReAct 循环实现

```
前端请求
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  chat_router.py (新路由入口)                                      │
│                                                                 │
│  职责：                                                          │
│  1. 调用 PreprocessingPipeline 进行意图检测                       │
│  2. 根据 intent 类型分发到对应处理流程                            │
│                                                                 │
│  输出：intent, confidence, corrected_text                        │
└─────────────────────────────────────────────────────────────────┘
               │
         ┌─────┼─────┐
         │     │     │
         ▼     ▼     ▼
     intent= intent= intent=
     file   network query
          │     │     │
          ▼     ▼     ▼
      ┌─────────────┐ ┌─────────────────┐ ┌────────────┐
      │intent-file- │ │intent-network- │ │chat_       │
      │ReactAgent    │ │ReactAgent      │ │stream_     │
      │(ReAct)       │ │(ReAct)         │ │query.py    │
      │              │ │                │ │(简单对话)  │
      └─────────────┘ └─────────────────┘ └────────────┘
     
     ┌──────────────┐
     │error_handler │ ← 统一的错误处理
     │.py           │
     └──────────────┘
     ┌──────────────┐
     │incident_han- │ ← 统一的中断/暂停处理
     │dler.py       │
     └──────────────┘
```

**流程说明**：

| 阶段 | 文件 | 说明 |
|------|------|------|
| **入口** | chat_router.py | 意图检测 + 分发 |
| **预处理** | preprocessing/pipeline.py | 语句校对 + 意图识别 |
| **ReAct流程** | intent-*-ReactAgent (agent.py) | start → thought → action → observation → final |
| **简单对话** | chat_stream_query.py | start → chunk → final |
| **错误处理** | error_handler.py | 统一的错误响应 |
| **中断处理** | incident_handler.py | 统一的中断/暂停响应 |

**chat_router.py 与 chat2.py 的职责分工**：

| 文件 | 职责 | 不做 |
|------|------|------|
| **chat_router.py** | 路由入口、调用预处理、根据intent分发 | 流式loop、具体执行 |
| **chat2.py / intent-file-ReactAgent** | 流式loop（ReAct循环或普通对话） | 路由、预处理、意图识别 |

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
> - **intent-file-ReactAgent** 是**执行层**，在需要文件操作/网络操作时调用，实现 ReAct 循环
> - chat2 调用 Agent，而不是包含 Agent，两者职责分离

chat2.py 是**入口+执行**，负责：

| 步骤 | 功能 |
|------|------|
| 1 | Session 创建/管理 |
| 2 | 根据 intent_type 决定分支 |
| 3 | 流式输出具体工作 |
| 4 | 有动作时：调用 intent-file-ReactAgent.ver1_run_stream() |
| 5 | 无动作时：调用 chat_stream_query() |

### 2.4 文件引用关系

| 模块/函数 | 引用路径 |
|-----------|---------|
| PreprocessingPipeline | `from app.services.preprocessing import PreprocessingPipeline` |
| IntentRegistry | `from app.services.intent import IntentRegistry, Intent` |
| intent-file-ReactAgent | `from app.services.agent import intent_file_ReactAgent` |
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

#### 2.7.1 preprocessing.py（预处理入口）

```python
from app.services.preprocessing import PreprocessingPipeline
from app.services.intent import IntentRegistry, Intent

# 全局实例
_preprocessor = PreprocessingPipeline()
_intent_registry = IntentRegistry()

async def execute_preprocessing(request: ChatRequest) -> dict:
    """
    预处理入口函数
    职责：预处理 → 意图识别 → 返回预处理结果
    注意：不调用chat2，由路由层决定后续调用
    """
    # 1. 预处理
    task = request.messages[-1].content
    intent_names = _intent_registry.get_all_names()
    preprocessed = _preprocessor.process(task, intent_names, session_id=None)
    
    # 2. 意图识别
    intent_type = preprocessed.get("intent", "unknown")
    intent_def = _intent_registry.get(intent_type)
    
    # 3. 历史消息（不经过预处理）
    history = request.messages[:-1]
    
    # 4. 返回预处理结果（由路由层决定后续调用）
    return {
        "corrected": preprocessed["corrected"],
        "intent_type": intent_type,
        "intent_def": intent_def,
        "history": history,
    }
```

> **📝 说明**：预处理模块只返回预处理结果，不直接调用chat2。由路由层（7.4节）负责串联调用。

#### 2.7.2 chat2.py（入口+执行）

```python
from app.services.agent import intent_file_ReactAgent  # 文件操作专用Agent
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

### 3.3 chat2 → intent-file-ReactAgent.ver1_run_stream()

**实际参数（已核对代码）**：

```python
agent = intent_file_ReactAgent(
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

## 四、Agent分层架构设计与实现说明

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
│     intent-file-ReactAgent (agent.py) (扩展层) │
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
agent.ver1_run_stream() ← intent-file-ReactAgent
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
| agent.py 继承 BaseAgent | 继承关系已建立 | agent.py:41 `class intent-file-ReactAgent(BaseAgent)` |
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

### 5.1 ReAct 循环事件（intent-file-ReactAgent）

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
| `backend/app/api/v1/chat2.py` | 路由层/chat2入口（含预处理调用） |
| `backend/app/services/agent/agent.py` | intent-file-ReactAgent (ver1_run_stream) |
| `backend/app/services/agent/base.py` | BaseAgent 基类（需补充可扩展方法） |
| `backend/app/services/preprocessing/pipeline.py` | PreprocessingPipeline（已存在） |
| `backend/app/services/intent/registry.py` | IntentRegistry（已存在） |
| `backend/app/chat_stream/chat_stream_query.py` | 普通对话流式输出 |

### 6.2 职责划分原则

#### 6.2.1 外部流程职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **预处理模块** | 预处理+意图识别，返回intent_type+intent_def+corrected_task+history | Session管理，调用chat2 |
| **chat2.py** | Session管理+ai_service创建+根据intent_type分支+流式输出 | 预处理、意图识别 |

> **📝 说明**：预处理不调用chat2，由路由层负责串联调用（见2.1架构）

#### 6.2.2 Agent内部职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **BaseAgent (base.py)** | 定义ReAct循环核心逻辑，提供抽象方法，定义可扩展方法 | 包含具体实现细节 |
| **intent-file-ReactAgent (agent.py)** | 继承BaseAgent，实现抽象方法，添加扩展功能（session、prompt等） | 重写循环逻辑 |

### 6.3 Session 管理

> **📝 说明**：代码中存在**两层Session管理**，职责不同：

#### 6.3.1 两层Session管理

| 层级 | 文件 | 职责 | Session ID |
|------|------|------|------------|
| **第一层** | chat2.py | task_id任务管理、中断/暂停控制 | task_id（路由参数） |
| **第二层** | session.py | 文件操作会话记录、统计 | session_id（业务参数） |

#### 6.3.2 chat2.py中的任务管理

**文件位置**：`backend/app/api/v1/chat2.py`

**数据结构**：
```python
# task_id → 任务信息
running_tasks: dict[str, dict] = {
    "task-uuid": {
        "status": "running",    # running/cancelled/paused
        "cancelled": False,
        "paused": False,
        "created_at": datetime,
        "ai_service": ai_service
    }
}

# session_id → 中断时间（防止5分钟内重连）
interrupted_sessions: dict[str, datetime] = {}
```

**Session生命周期**：
```
request.session_id 或生成新 session_id
    ↓
running_tasks[task_id] = {status: "running", ...}
    ↓
根据 intent_type 分支（有动作/无动作）
    ↓
finally: del running_tasks[task_id]
```

#### 6.3.3 FileOperationSessionService（文件操作会话）

**文件位置**：`backend/app/services/agent/session.py`

**数据库表**：`file_operation_sessions`

**状态**：`pending` / `active` / `completed` / `paused` / `failed`

**主要方法**：
- `create_session(agent_id, task_description)` → session_id
- `complete_session(session_id, success)`
- `get_session(session_id)` → SessionRecord

> **⚠️ 注意**：两层Session的ID可能不同：
> - chat2用的是task_id（路由级别）
> - session.py用的是session_id（业务级别）
> - 需要在Agent内部统一为session_id

#### 6.3.4 与报告设计方案的逻辑关系

> **📝 说明**：本节描述架构现状，报告设计方案（`LLM-文件操作历史过程报告设计方案V2版-小沈-20260325.md`）是基于本节架构的**具体实现方案**。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    6.3 Session管理（架构层）                              │
│                                                                         │
│  chat2.py                           session.py                          │
│  ┌─────────────────┐               ┌─────────────────┐                  │
│  │ task_id 任务管理 │               │ file_operation  │                  │
│  │ + session_id    │               │ _sessions 表    │                  │
│  └────────┬────────┘               └────────┬────────┘                  │
│           │                                 │                            │
│           │ 统一使用 request.session_id      │                            │
│           └───────────────┬─────────────────┘                            │
│                           ↓                                              │
│                  file_operations 表                                       │
│                  (session_id 关联操作记录)                                │
└─────────────────────────────────────────────────────────────────────────┘
                           │
                           ↓ 具体实现
┌─────────────────────────────────────────────────────────────────────────┐
│           报告设计方案（实现层）- 已实现 ✅                                │
│                                                                         │
│  chat2.py:456                                                           │
│  session_id = request.session_id or str(uuid.uuid4())  ← 统一session_id  │
│                           ↓                                              │
│  file_operations.session_id = request.session_id  ← 可被报告生成找到     │
│                           ↓                                              │
│  generate_report API (带 task_description 参数)  ← 报告正确生成        │
└─────────────────────────────────────────────────────────────────────────┘
```

**逻辑关系**：
1. **6.3 Session管理** = 描述架构现状（有哪些Session、职责是什么）
2. **报告设计方案** = 基于架构的具体实现方案（解决Session ID不统一导致报告找不到数据的问题）
3. **关系**：报告设计方案是6.3架构的**落地实现**

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

#### 7.1.1 核心教训（本次梳理的目的）

> **⚠️ 教训来源**：上次 Agent 重构时，preprocessor、intent_registry、Session管理等单元功能都实现了，单元测试通过，但整合到主流程时失败——功能放到了废弃的支流代码中，主干流程反而没有这些功能。

**核心问题**：
- 单元重构完成 ≠ 重构目的达到
- 功能实现 ≠ 功能被主流程调用
- 单元测试通过 ≠ 主流程能工作

**本次梳理的目的**：
- 不是重新实现功能
- 而是**正确地把已有功能整合到主流程**
- 确保：preprocessor、intent_registry 等 → 被 chat2.py 主流程调用

**每次修改必须思考**：
```
这个修改能不能整合到主流程？
如果不能，怎么改才能整合？
```

---

#### 7.1.2 关于基础版本 v0.7.92
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

**遗留问题修复**（来自 `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` 7.7节）：
> **问题**：agent.py:452 使用原始 `task` 而不是 `preprocessed['corrected']`
> 
> **当前代码**：
> ```python
> task_prompt = self.prompts.get_task_prompt(task, context)  # 用原始task ❌
> ```
> 
> **应改为**：
> ```python
> task_prompt = self.prompts.get_task_prompt(preprocessed['corrected'], context)  # 用修正后的 ✅
> ```
> 
> **改造要点**：
> - [ ] 修改 agent.py 第452行，使用 `preprocessed['corrected']` 替代原始 `task`

### 7.4 路由改造（创建 chat_router.py）

> **📝 设计依据**：`多意图系统与现有代码整合架构设计-2026-03-22.md` 3.1节
> 
> **核心原则**：chat2 **不能作为路由层**，chat2只负责流式loop

**问题**：当前 chat2.py 混合了路由和流式loop职责，职责不清

**目标**：创建独立的 chat_router.py 作为路由入口

**chat_router.py 职责**（参考整合架构设计3.1节）：
```
chat_router.py（新路由入口）
    ├── 调用 PreprocessingPipeline 进行意图检测
    ├── 根据 intent 类型分发到对应处理流程
    └── 输出：intent, confidence, corrected_text
```

**架构**（参考整合架构设计2.1节）：
```
chat_router.py
    ├── intent=file → chat2.py (ReAct流式loop)
    ├── intent=network → chat2.py (ReAct流式loop)
    └── intent=query → chat_stream_query.py (简单对话流式)
```

**改造要点**：
- [ ] 新建 `chat_router.py` 作为统一路由入口
- [ ] **废除** `detect_file_operation_intent`（预处理阶段已有意图识别）
- [ ] chat_router.py 调用 PreprocessingPipeline 获取意图
- [ ] chat_router.py 根据 intent 分发到对应流程
- [ ] chat2.py **只负责流式loop**，不包含任何预处理/意图识别

**chat_router.py 代码结构示例**：
```python
# chat_router.py
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    # 1. 调用预处理模块（包含意图识别）
    preprocessed = await execute_preprocessing(request)
    intent_type = preprocessed.get("intent")
    
    # 2. 根据 intent 分发
    if intent_type == "file":
        # ReAct 流式loop
        async for event in chat2.react_stream(...):
            yield event
    elif intent_type == "network":
        # ReAct 流式loop
        async for event in chat2.react_stream(...):
            yield event
    else:
        # 简单对话流式
        async for event in chat_stream_query(...):
            yield event

# 3. chat2.py 只负责流式loop（改造后）
# - 不包含预处理逻辑
# - 不包含意图识别
# - 只负责 ReAct 循环或普通对话流
```

### 7.5 Agent分层重构

> **📝 说明**：基于4.5.2的未完成项，补充base.py的可扩展方法。

**4.5.1已完成** ✅：继承关系、调用run_stream、核心循环逻辑

**4.5.2待实现** ❌：可扩展方法拆分

**Agent命名规范**（必须遵守）：
> **⚠️ 命名原则**：IntentReactAgent 是**文件操作专用**的Agent，应统一命名为 `intent-file-ReactAgent`
>
> | 当前命名 | 应改为 | 说明 |
> |---------|--------|------|
> | IntentReactAgent | intent-file-ReactAgent | 文件操作专用 |
> | IntentReactAgent (network) | intent-network-ReactAgent | 网络操作专用（未来） |
>
> **原因**：避免与 BaseAgent 混淆，明确每个Agent的职责范围

**改造要点**：
- [ ] 将 `IntentReactAgent` 重命名为 `intent-file-ReactAgent`
- [ ] base.py 拆分 `_step_thought()` 可扩展方法
- [ ] base.py 拆分 `_step_action()` 可扩展方法
- [ ] base.py 拆分 `_step_observation()` 可扩展方法
- [ ] base.py 实现 `_init_session()` Hook（替代 `_on_session_init`）
- [ ] base.py 实现 `_on_before_loop()` Hook
- [ ] 验证（生产功能正常 + 测试通过）

---

## 八、关键实现细节（代码示例）

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

## 附录2：ReAct架构层次说明

> **📝 说明**：整理ReAct架构的层次关系，明确各层职责
>
> **更新时间**: 2026-03-25 21:18:40
> **更新人**: 小沈

### 附录2.1 架构层次总览

```
┌─────────────────────────────────────────────────────────────────┐
│  底层 ReAct：base.py 的 run_stream()                              │
│                                                                 │
│  实现标准的 ReAct 循环：                                         │
│    Thought → Action → Observation → (循环直到 finish)              │
│                                                                 │
│  返回通用 dict 事件：                                           │
│    {"type": "thought", "content": ...}                          │
│    {"type": "action_tool", "tool_name": ...}                   │
│    {"type": "observation", "obs_summary": ...}                   │
│                                                                 │
│  ✅ 与意图无关，是通用的                                         │
└─────────────────────────────────────────────────────────────────┘
                           ↑
                           │ agent.py 调用
┌─────────────────────────────────────────────────────────────────┐
│  上层 Intent-*-React：agent.py 的 ver1_run_stream()             │
│                                                                 │
│  - 继承 BaseAgent                                               │
│  - 调用 self.run_stream()（底层）                               │
│  - 在底层事件基础上，格式化成 SSE 字符串                         │
│                                                                 │
│  根据意图不同调用不同的意图特定的react函数代码：                  │
│  ├── intent-file-ReactAgent  (file-react)                       │
│  │   └── 文件操作相关逻辑（工具/prompt/安全检查）                │
│  ├── intent-network-ReactAgent  (network-react)                │
│  │   └── 网络操作相关逻辑                                       │
│  ├── intent-desktop-ReactAgent  (desktop-react)                 │
│  │   └── 桌面操作相关逻辑                                       │
│  └── chat_stream_query()                                       │
│      └── 流式普通对话过程                                       │
│                                                                 │
│  ✅ 与具体意图相关（intent-file-react）                          │
└─────────────────────────────────────────────────────────────────┘
                            ↑
                            │ chat2.py 调用
┌─────────────────────────────────────────────────────────────────┐
│  chat2.py 是什么层？                                            │
│                                                                 │
│  ❌ 混合体：                                                   │
│    - 有路由判断（if is_file_op）—— 应该是 chat_router 的职责     │
│    - 调用 agent.ver1_run_stream() —— 上层 Intent-*-React        │
│    - 调用 chat_stream_query() —— 普通对话流式                    │
│                                                                 │
│  结论：chat2 不是任何一层，它是混合了多层的职责                   │
└─────────────────────────────────────────────────────────────────┘
```

### 附录2.2 各层职责说明

| 层次 | 文件 | 职责 | 特点 |
|------|------|------|------|
| **底层 ReAct** | base.py | 实现标准ReAct循环 | 与意图无关，通用 |
| **上层 Intent-*-React** | agent.py | 格式化SSE + 意图相关逻辑 | 与具体意图相关 |
| **路由层** | chat_router.py（待创建） | 意图检测 + 分发 | 路由职责 |
| **chat2（当前）** | chat2.py | 混合体 | ❌ 职责不清 |

### 附录2.3 四层架构与意图分发

> **整理时间**: 2026-03-25 21:50:00
> **整理人**: 小沈

#### 附录2.3.1 改造后的四层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  第一层：路由层 chat_router.py                                    │
│                                                                 │
│  ├── 调用 PreprocessingPipeline 进行意图检测                      │
│  ├── 判断 intent 类型                                            │
│  └── 分发到对应执行层：                                         │
│      ├── intent=file → intent-file-ReactAgent                   │
│      ├── intent=network → intent-network-ReactAgent              │
│      ├── intent=desktop → intent-desktop-ReactAgent              │
│      └── intent=query → chat_stream_query()                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  第二层：意图特定 React (intent-*-React)                         │
│                                                                 │
│  ├── intent-file-ReactAgent (file-react.py)                      │
│  │   └── 文件操作相关逻辑（工具/prompt/安全检查）                │
│  │                                                            │
│  ├── intent-network-ReactAgent (network-react.py)                 │
│  │   └── 网络操作相关逻辑                                       │
│  │                                                            │
│  └── intent-desktop-ReactAgent (desktop-react.py)                │
│      └── 桌面操作相关逻辑                                       │
│                                                                 │
│  【说明】这些层共同调用 chat2.py (改造后)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  第三层：chat2.py (改造后)                                       │
│                                                                 │
│  ├── 流式输出 SSE                                               │
│  ├── 中断/暂停处理                                              │
│  └── 不做路由判断                                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  第四层：底层 base.py                                            │
│                                                                 │
│  └── run_stream() - 通用 ReAct 循环                            │
│      与意图无关，通用                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### 附录2.3.2 改造前后对应关系

| 改造前 | 改造后 | 说明 |
|--------|---------|------|
| agent.py | intent-file-ReactAgent (file-react.py) | 当前 agent.py 约等于 intent-file-ReactAgent |
| agent.py (intent_type=network) | intent-network-ReactAgent (network-react.py) | 待实现 |
| agent.py (intent_type=desktop) | intent-desktop-ReactAgent (desktop-react.py) | 待实现 |
| chat2.py (混合体) | chat2.py (流式SSE输出包装) | 剥离路由职责 |
| 无 | chat_router.py (路由层) | 新增 |

#### 附录2.3.3 各层职责总结

| 层 | 文件 | 职责 | 特点 |
|---|------|------|------|
| **路由层** | chat_router.py | 意图检测 + 分发 | 新增 |
| **意图特定React** | intent-*-ReactAgent | 意图相关逻辑（工具/prompt/安全） | 拆分自 agent.py |
| **流式包装** | chat2.py | SSE输出 + 中断/暂停处理 | 剥离路由 |
| **通用ReAct** | base.py | 标准ReAct循环 | 与意图无关 |

#### 附录2.3.4 关键理解

1. **agent.py = intent-file-ReactAgent 的前身**
   - 当前 agent.py 有 intent_type 参数，但只完整实现了 file
   - 改造就是把 agent.py 拆分重命名

2. **意图特定 React 层共同调用 chat2.py**
   - intent-file-ReactAgent、intent-network-ReactAgent 等
   - 都调用同一个 chat2.py（流式输出器）
   - chat2.py 再调用 base.py

3. **不再需要现有的 agent.py 作为独立文件**
   - 其逻辑拆分到各 intent-*-ReactAgent
   - chat_router 负责路由分发

### 附录2.4 文件命名规范

> **整理时间**: 2026-03-25 22:20:00
> **整理人**: 小沈
>
> **更新时间**: 2026-03-25 22:25:00
> **更新说明**: 已完成改名，文件位置和实际命名为 base_react.py

#### 附录2.4.1 底层ReAct文件命名

| 原文件名 | 新文件名 | 文件位置 | 说明 |
|---------|---------|---------|------|
| base.py | **base_react.py** | `backend/app/services/agent/base_react.py` | 明确表示"底层ReAct"职责 |

**改名理由**：
- `base.py` 含义模糊
- `base_react.py` 明确表达是"底层ReAct循环"
- 与四层架构名称对齐

**注意**：Python模块名必须使用下划线，不能用连字符

#### 附录2.4.2 改名后同步更新 ✅ 已完成

| 文件 | 更新内容 |
|------|---------|
| `backend/app/services/agent/base_react.py` | 重命名文件 |
| `backend/app/services/agent/agent.py` | 更新导入：`from app.services.agent.base_react import BaseAgent` |
| `backend/app/services/agent/__init__.py` | 更新导入 |
| `backend/tests/test_agent.py` | 更新导入 |
| `backend/tests/test_multi_intent_architecture.py` | 更新导入 |

#### 附录2.4.3 改名影响范围

```
引用 base.py 的文件：
├── agent.py
├── test_agent.py
└── test_multi_intent_architecture.py

影响：较小，只需更新导入语句
```

---

## 附录：回归验证检查清单

> **📝 说明**：以下检查清单用于待实现任务完成后的验证，确保功能正常。

| 序号 | 验证项 | 验证方法 |
|------|--------|---------|
| 1 | 流式对话正常 | 触发 chat 意图，检查 chunk/final 事件正确 |
| 2 | 文件操作正常 | 触发文件操作，检查 ReAct 循环事件正确 |
| 3 | 网络操作正常 | 触发网络操作，检查 ReAct 循环事件正确 |
| 4 | Session 管理正常 | 检查创建/传递/关闭流程 |
| 5 | 预处理识别意图 | 检查 intent_type 正确识别 |
| 6 | 历史消息传递 | 检查 history 不经过预处理 |
| 7 | 中断/暂停功能 | 触发中断，检查状态正确 |
| 8 | 数据库保存 | 检查 execution_steps 正确保存 |

---

**文档结束**
