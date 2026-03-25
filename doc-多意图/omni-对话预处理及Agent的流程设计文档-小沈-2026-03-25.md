# OmniAgent对话预处理及Agent的流程设计文档

**创建时间**: 2026-03-25 13:51:48
**更新时间**: 2026-03-25 16:00:00
**版本**: v2.0
**编写人**: 小沈

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

chat2.py 是**入口+执行**，负责：

| 步骤 | 功能 |
|------|------|
| 1 | Session 创建/管理 |
| 2 | 根据 intent_type 决定分支 |
| 3 | 流式输出具体工作 |

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

### 2.8 Agent内部继承架构（BaseAgent → IntentReactAgent）

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

#### 2.8.1 设计原则

| 原则 | 说明 |
|------|------|
| **生产代码是基准** | 以 agent.py 的 run_stream 为准 |
| **base.py 向生产代码看齐** | 用正确的逻辑更新 base.py |
| **agent.py 继承 base.py** | 而不是重写 |

#### 2.8.2 调用关系

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

## 四、Agent分层架构设计

### 4.1 设计原则

| 原则 | 说明 |
|------|------|
| **生产代码是基准** | 以 agent.py 的 run_stream 为准 |
| **base.py 向生产代码看齐** | 用正确的逻辑更新 base.py |
| **agent.py 继承 base.py** | 而不是重写 |

### 4.2 BaseAgent 重构设计

#### 4.2.1 核心方法定义

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
    
    async def run_stream(
        self,
        task: str,
        context: Optional[Dict] = None,
        max_steps: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        ReAct 核心循环（生产环境正确逻辑）
        
        特点：
        - 每次循环包含 3 个阶段: thought → action_tool → observation
        - observation 包含实际执行数据（2026-03-25 修复）
        - LLM 根据 observation 更新 thought
        """
        # 初始化
        self._init_session(task, context)
        
        while step_count < max_steps:
            # ==== Thought 阶段 ====
            yield await self._step_thought()
            
            # ==== Action 阶段 ====
            yield await self._step_action()
            
            # ==== Observation 阶段 ====
            yield await self._step_observation()
    
    # ===== 可扩展方法（子类可覆盖）=====
    
    def _init_session(self, task: str, context: Optional[Dict]):
        """初始化 session（可选覆盖）"""
        pass
    
    async def _step_thought(self) -> Dict:
        """执行 thought 阶段（可扩展）"""
        pass
    
    async def _step_action(self) -> Dict:
        """执行 action 阶段（可扩展）"""
        pass
    
    async def _step_observation(self) -> Dict:
        """执行 observation 阶段（可扩展）"""
        pass
```

#### 4.2.2 核心循环逻辑（直接复用 agent.py）

```python
async def _step_observation(self) -> Dict:
    """Observation 阶段 - 核心逻辑"""
    
    # 1. 构建 observation_text（包含实际数据）
    raw_data = execution_result.get('data')
    if raw_data:
        observation_text = f"Observation: {status} - {summary}\n实际数据: {raw_data}"
    else:
        observation_text = f"Observation: {status} - {summary}"
    
    # 2. 添加到历史
    self._add_observation_to_history(observation_text)
    
    # 3. 再次调用 LLM 获取下一个决策
    llm_response = await self._get_llm_response()
    
    # 4. 解析响应
    try:
        parsed_obs = self.parser.parse_response(llm_response)
    except ValueError as e:
        parsed_obs = {"content": "无法解析LLM响应", "action_tool": "finish", "params": {}}
    
    # 5. 返回 observation
    return {
        "type": "observation",
        "content": parsed_obs.get("content", ""),
        "obs_action_tool": parsed_obs.get("action_tool", "finish"),
        "is_finished": parsed_obs.get("action_tool") == "finish",
        ...
    }
```

### 4.3 IntentReactAgent 重构设计

#### 4.3.1 继承结构

```python
class IntentAgent(BaseAgent):
    """文件操作 Agent"""
    
    def __init__(self, ...):
        # 调用父类初始化
        super().__init__(max_steps=max_steps)
        
        # 添加扩展功能
        self.session_service = ...
        self.preprocessor = ...
        self.intent_registry = ...
        self.prompts = ...
        self.executor = ...
    
    # ===== 实现抽象方法 =====
    
    def _get_system_prompt(self) -> str:
        return self.prompts.get_system_prompt()
    
    def _get_task_prompt(self, task: str, context: Optional[Dict]) -> str:
        return self.prompts.get_task_prompt(task, context)
    
    async def _execute_tool(self, action: str, params: Dict) -> Dict:
        return await self.executor.execute(action, params)
    
    # ===== 覆盖扩展方法 =====
    
    def _init_session(self, task: str, context: Optional[Dict]):
        """扩展：session 管理"""
        # 确保 session 存在
        if not self.session_id:
            self.session_id = self.session_service.create_session(...)
    
    # ===== 调用父类核心方法 =====
    
    async def ver1_run_stream(self, ...):
        """入口方法"""
        # 使用父类的 run_stream
        async for event in self.run_stream(task, context, max_steps):
            # 转换为 SSE 格式
            yield self._to_sse(event)
```

#### 4.3.2 调用关系

```
ver1_run_stream()
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

### 4.4 实施步骤

#### 4.4.1 第一步：清空 base.py

**操作**：删除 base.py 内部所有实现代码，只保留：
- 导入语句
- 类型定义
- 抽象方法声明
- 核心方法实现

#### 4.4.2 第二步：重写 base.py

**操作**：用 agent.py 的正确逻辑重写 base.py：
- 核心循环逻辑
- 抽象方法定义
- 可扩展方法定义

#### 4.4.3 第三步：重构 agent.py

**操作**：让 agent.py 继承 base.py：
- 删除重写的循环逻辑
- 调用父类方法
- 只保留扩展功能

#### 4.4.4 第四步：验证

**操作**：运行测试，确保：
- 生产功能正常
- 测试通过

### 4.5 完成情况检查

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

| 序号 | 未完成项 | 文档位置 | 当前状态 |
|------|---------|---------|---------|
| 1 | **_step_thought 可扩展方法** | 4.2.1 | ❌ base.py 未实现 |
| 2 | **_step_action 可扩展方法** | 4.2.1 | ❌ base.py 未实现 |
| 3 | **_step_observation 可扩展方法** | 4.2.1 | ❌ base.py 未实现 |
| 4 | **_init_session Hook** | 4.2.1 | ❌ base.py 有 _on_session_init，但不是 _init_session |
| 5 | **_on_before_loop Hook** | 4.2.1 | ⚠️ base.py 有调用但没有实现 |

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

## 六、Session 管理

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

## 七、待实现清单

### 7.1 预处理模块

- [ ] 创建 `preprocessing.py`
- [ ] 引入 PreprocessingPipeline (`from app.services.preprocessing import PreprocessingPipeline`)
- [ ] 引入 IntentRegistry (`from app.services.intent import IntentRegistry, Intent`)
- [ ] 实现 `handle_request()` 入口函数
- [ ] 整合 preprocessor.process() + intent_registry.get()
- [ ] 处理 history（历史消息不经过预处理）
- [ ] 调用 chat2.handle_stream() 传入预处理结果和意图定义

### 7.2 chat2.py 改造

- [ ] 接收预处理结果作为参数（last_message, intent_type, intent_def, history）
- [ ] Session 创建/管理（复用现有逻辑）
- [ ] ai_service 创建（AIServiceFactory）
- [ ] next_step 计数函数定义
- [ ] 根据 intent_type 决策分支
- [ ] 有动作：创建 FileOperationAgent + 调用 ver1_run_stream()
- [ ] 无动作：调用 chat_stream_query()
- [ ] 保留原有功能（中断检查、暂停检查、数据库保存）

### 7.3 路由改造

- [ ] 修改 API 路由入口（`/api/v1/chat` 或 `/api/v1/chat2`）
- [ ] 从直接调用 chat2 改为调用 preprocessing.handle_request()

### 7.4 回归验证

- [ ] 流式对话正常（chat_stream_query 事件正确）
- [ ] 文件操作正常（ver1_run_stream 事件正确）
- [ ] 网络操作正常（ver1_run_stream 事件正确）
- [ ] Session 管理正常（创建/传递/关闭）
- [ ] 预处理正确识别意图（intent_type 正确）
- [ ] 历史消息正确传递（history 不经过预处理）
- [ ] 中断/暂停功能正常
- [ ] 数据库保存正常

### 7.5 Agent分层重构实施步骤

#### 7.5.1 第一步：清空 base.py

**操作**：删除 base.py 内部所有实现代码，只保留：
- 导入语句
- 类型定义
- 抽象方法声明
- 核心方法实现

#### 7.5.2 第二步：重写 base.py

**操作**：用 agent.py 的正确逻辑重写 base.py：
- 核心循环逻辑
- 抽象方法定义
- 可扩展方法定义

#### 7.5.3 第三步：重构 agent.py

**操作**：让 agent.py 继承 base.py：
- 删除重写的循环逻辑
- 调用父类方法
- 只保留扩展功能

#### 7.5.4 第四步：验证

**操作**：运行测试，确保：
- 生产功能正常
- 测试通过

---

## 八、文件位置

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

---

## 九、职责划分原则

### 9.1 外部流程职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **preprocessing.py** | 预处理+意图识别+history处理+调用chat2 | Session管理、流式输出 |
| **chat2.py** | Session管理+ai_service创建+根据intent_type分支+流式输出 | 预处理、意图识别 |

### 9.2 Agent内部职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **BaseAgent (base.py)** | 定义ReAct循环核心逻辑，提供抽象方法，定义可扩展方法 | 包含具体实现细节 |
| **IntentReactAgent (agent.py)** | 继承BaseAgent，实现抽象方法，添加扩展功能（session、prompt等） | 重写循环逻辑 |

---

## 十、关键实现细节

### 10.1 next_step 函数定义

```python
# 必须在使用前定义
step_counter = 0

def next_step():
    nonlocal step_counter
    step_counter += 1
    return step_counter
```

### 10.2 LLM 客户端适配器

```python
async def llm_client(message, history=None):
    response = await ai_service.chat(message, history)
    return type('obj', (object,), {'content': response.content})()
```

### 10.3 Agent 实例创建

```python
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id
)
```

---

**文档结束**
