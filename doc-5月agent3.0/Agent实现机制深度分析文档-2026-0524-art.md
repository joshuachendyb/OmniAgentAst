# OmniAgentAs-desk Agent 实现机制深度分析文档

> 基于代码 v0.13.11 | 生成日期: 2026-05-24 | 分析者: CodeArts | 更新日期: 2026-05-24 (修正映射不一致)

---

## 目录

- [一、系统总体架构概览](#一系统总体架构概览)
- [二、请求完整流程分析](#二请求完整流程分析)
- [三、意图识别与路由机制](#三意图识别与路由机制)
- [四、Agent 核心架构](#四agent-核心架构)
- [五、ReAct 循环详解](#五react-循环详解)
- [六、LLM 调用策略体系](#六llm-调用策略体系)
- [七、输出解析器链](#七输出解析器链)
- [八、工具注册与加载机制](#八工具注册与加载机制)
- [九、工具执行器](#九工具执行器)
- [十、Message 组装与历史管理](#十message-组装与历史管理)
- [十一、Prompt 模板体系](#十一prompt-模板体系)
- [十二、SSE 流式输出机制](#十二sse-流式输出机制)
- [十三、安全与回滚机制](#十三安全与回滚机制)
- [十四、辅助支撑模块](#十四辅助支撑模块)

---

## 一、系统总体架构概览

### 1.1 概要总结

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 模式的 AI Agent 桌面应用。用户输入自然语言指令后，系统通过 **两阶段意图识别** 路由到对应 Agent，Agent 在 **Thought→Action→Observation** 循环中反复调用 LLM 推理和工具执行，直到任务完成，全过程通过 **SSE** 流式输出给前端。

### 1.2 四层架构

```
┌─────────────────────────────────────────────────────────┐
│  第一层：chat_router.py — 路由入口                        │
│  职责：预处理 → 意图路由 → 安全检查 → 启动SSE流            │
├─────────────────────────────────────────────────────────┤
│  第二层：react_sse_wrapper.py — SSE包装层                 │
│  职责：Agent实例创建 → SSE格式化 → 中断控制 → DB持久化     │
├─────────────────────────────────────────────────────────┤
│  第三层：Agent子类 — 配置驱动的智能体                       │
│  职责：Prompt组装 → 工具选择 → 任务追踪 → 回滚管理         │
│  (UniversalReactAgent / DesktopReactAgent)               │
├─────────────────────────────────────────────────────────┤
│  第四层：base_react.py — ReAct循环引擎                    │
│  职责：循环控制 → LLM调用 → 解析 → 工具执行 → 步骤生成     │
└─────────────────────────────────────────────────────────┘
```

### 1.3 核心模块依赖关系图

```
用户请求
  ↓
chat_router.py ──→ preprocessing/pipeline.py (文本预处理)
  │                → intents/crss_scorer.py (CRSS评分)
  │                → preprocessing/intent_classifier.py (LLM分类)
  │                → safety/ (安全检查)
  ↓
react_sse_wrapper.py
  │──→ agent_factory.py ──→ agent_config.py (声明式配置)
  │       └──→ UniversalReactAgent / DesktopReactAgent
  │              ├──→ base_react.py (ReAct循环)
  │              │      ├──→ llm_strategies.py (TextStrategy/ToolsStrategy)
  │              │      │       └──→ llm_core.py (BaseAIService)
  │              │      ├──→ react_output_parser.py (9级解析链)
  │              │      ├──→ message_builder.py (消息组装/历史裁剪)
  │              │      ├──→ tool_executor.py (工具执行/重试)
  │              │      │       └──→ tools/registry.py (ToolRegistry)
  │              │      └──→ reasoning_steps.py (Step封装)
  │              ├──→ mixins/react_agent_mixin.py (公用逻辑)
  │              ├──→ mixins/rollback_mixin.py (回滚能力)
  │              └──→ prompts/ (Prompt模板)
  └──→ SSE格式化 → 前端
```

---

## 二、请求完整流程分析

### 2.1 概要总结

一次完整的用户请求经过 **6个阶段**：文本预处理 → 两阶段意图路由 → 安全检查 → Agent实例创建 → ReAct循环 → SSE流式输出。整个流程是 **全异步** 的，支持中断/暂停/恢复。

### 2.2 详细流程

```
用户输入: "帮我读取C盘下的config.yaml文件"
  │
  ▼ [阶段1] 文本预处理
  preprocessing/pipeline.py — PreprocessingPipeline.process()
  - strip() 去除首尾空白
  - （不再做意图检测，意图检测已统一由route_with_fallback处理）
  │
  ▼ [阶段2] 两阶段意图路由
  route_with_fallback(user_input)
  │
  ├─→ [阶段2a] CRSS快速匹配 (crss_scorer.py)
  │    - "读取" → 命中read动作 (+1.0)
  │    - "文件/config.yaml" → 命中FILE类型 (+2.0)
  │    - 双维度合成: FILE类型分 × (1 + read兼容系数 × 0.3)
  │    - 归一化: adjusted = 1.0 - 2^(-raw)
  │    - confidence = 0.85 >= 0.3 阈值 ✓
  │    - 返回: {intent: "file", confidence: 0.85, source: "crss"}
  │
  │  （如果CRSS置信度 < 0.3，进入阶段2b）
  ├─→ [阶段2b] LLM语义分类 (intent_classifier.py)
  │    - 使用 gemma3:4b 模型
  │    - 构建包含7+5个意图定义的prompt
  │    - 调用 ollama cloud API (temperature=0.1)
  │    - 解析返回JSON → resolve_category() → ToolCategory
  │
  ▼ [阶段3] 初始化
  - 生成 task_id (UUID)
  - 创建 ai_service (BaseAIService实例)
  - 初始化 next_step / current_execution_steps
  │
  ▼ [阶段4] 安全检查
  check_command_safety(user_input)
  - 黑名单检测 (command_security.py)
  - 危险命令: rm -rf /, format, del /s 等 → 拦截
  │
  ▼ [阶段5] SSE流式生成
  generate_sse_stream(intent_type, ...)
  - 注册任务到 running_tasks 字典
  - AgentFactory.create(intent_type) → Agent实例
  - ensure_tools_registered() → 全量注册7个分类工具
  │
  ▼ [阶段6] ReAct循环 (BaseAgent.run_stream)
  - 获取system_prompt + task_prompt
  - 初始化conversation_history
  - 进入while True循环:
      → LLM推理 → 解析响应 → 工具执行 → 观察结果 → yield Step
      → 循环直到finish/错误/最大步数
  - 每个Step通过SSE实时推送前端
```

### 2.3 关键设计决策

| 决策 | 原因 |
|------|------|
| 两阶段意图路由 | CRSS快(毫秒级)但覆盖有限，LLM慢(1.5s)但语义理解强 |
| 全量工具注册 | 避免按需注册的复杂性，7分类48工具注册开销可接受 |
| SSE流式输出 | 用户体验：实时看到思考和执行过程 |
| 全异步架构 | 支持并发请求和长时间工具执行 |

---

## 三、意图识别与路由机制

### 3.1 概要总结

意图识别采用 **CRSS（分类规则评分系统）+ LLM兜底** 的两阶段架构。阶段1通过 **双维度关键词匹配**（类型维度+动作维度）+ 兼容矩阵调制实现毫秒级快速路由；阶段2在阶段1置信度不足时调用 **gemma3:4b** 小模型进行语义分类。

### 3.2 阶段1：CRSS 评分器详解

**文件**: `backend/app/services/intents/crss_scorer.py`

#### 3.2.1 双维度评分模型

```
         类型维度                    动作维度
    ┌──────────────┐          ┌──────────────┐
    │ FILE: 文件/目录│          │ read: 读取/查看│
    │ SHELL: 命令/执行│         │ create: 创建/写入│
    │ TIME: 时间/日期│          │ delete: 删除/移除│
    │ NETWORK: 网络/URL│        │ execute: 执行/运行│
    │ DESKTOP: 窗口/截图│       │ query: 查询/搜索│
    │ ENV: 环境变量  │          │ navigate: 导航/打开│
    │ SYSTEM: 系统/进程│        │ configure: 配置/设置│
    │ DATABASE: 数据库│         │ capture: 截图/捕获│
    │ DOCUMENT: 文档 │          └──────────────┘
    │ CODE_EXECUTION:代码│
    └──────────────┘
```

#### 3.2.2 评分算法流程

```python
def _compute_intent_scores(user_input: str) -> Dict[str, float]:
    scores = {}
    
    # Step 1: 危险命令检测
    if is_dangerous_command(user_input):
        scores["SYSTEM"] += 3.0  # 直接高分路由到system
    
    # Step 2: 类型关键词匹配
    for intent_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in user_input:
                # 中文关键词 +2.0, 英文 +1.0
                # 否定词检测: "不/没/别/勿/无/未/非" + 关键词 → 减分
                if not _is_negated(user_input, kw):
                    scores[intent_type] += weight
    
    # Step 3: 动作关键词匹配
    matched_actions = []
    for action_name, action_def in ACTION_DEFINITIONS.items():
        if any(kw in user_input for kw in action_def["keywords"]):
            matched_actions.append(action_def)
    
    # Step 4: 双维度合成
    for intent_type, type_score in scores.items():
        for action in matched_actions:
            compatibility = action["compatibility"].get(intent_type, 0)
            # 合成公式: 类型分 × (1 + 兼容系数 × 0.3)
            final_score = type_score * (1 + compatibility * 0.3)
            scores[intent_type] = max(scores[intent_type], final_score)
    
    # Step 5: 无类型分时用动作反推
    if not scores and matched_actions:
        for action in matched_actions:
            for intent, compat in action["compatibility"].items():
                if compat > 0:
                    scores[intent] = compat
    
    # Step 6: 归一化 (映射到 [0, 1))
    for k in scores:
        scores[k] = 1.0 - 2 ** (-scores[k])
    
    return scores
```

#### 3.2.3 兼容矩阵示例

```python
ACTION_DEFINITIONS = {
    "read": {
        "keywords": ["读取", "查看", "打开", "read", "cat", ...],
        "compatibility": {
            ToolCategory.FILE: 1.5,      # 读取+文件 → 高兼容
            ToolCategory.DOCUMENT: 1.2,  # 读取+文档 → 较高兼容
            ToolCategory.SYSTEM: 0.8,    # 读取+系统 → 中兼容
            ToolCategory.NETWORK: 0.5,   # 读取+网络 → 低兼容
            ...
        }
    },
    "delete": {
        "keywords": ["删除", "移除", "delete", "rm", ...],
        "compatibility": {
            ToolCategory.FILE: 1.5,      # 删除+文件 → 高兼容
            ToolCategory.DOCUMENT: 1.2,  # 删除+文档 → 较高兼容
            ToolCategory.DESKTOP: 0.5,   # 删除+桌面 → 低兼容
        }
    },
    ...
}
```

#### 3.2.4 类型到ToolCategory映射

```
原始11种类型         精简5种有效ToolCategory     注册归属
─────────────    →    ──────────────           ────────
FILE             →    FILE                    FILE分类
SHELL            →    SYSTEM                  注册到SYSTEM (ToolCategory.SHELL枚举保留但无工具)
TIME             →    SYSTEM                  注册到SYSTEM (ToolCategory.META枚举保留但无工具)
NETWORK          →    NETWORK                 NETWORK分类
DESKTOP          →    DESKTOP                 DESKTOP分类
ENV              →    SYSTEM                  注册到SYSTEM
SYSTEM           →    SYSTEM                  注册到SYSTEM
DATABASE         →    DOCUMENT                注册到DOCUMENT
DOCUMENT         →    DOCUMENT                注册到DOCUMENT
CODE_EXECUTION   →    SYSTEM                  注册到SYSTEM
DATA_FORMAT      →    FILE                    注册到FILE

> **重要说明**: ToolCategory枚举保留SHELL和META值(兼容性), 但所有shell工具和meta/time工具
> 实际注册到ToolCategory.SYSTEM。INTENT_TO_CATEGORY和CRSS TYPE_CATEGORY_MAP均已统一映射为SYSTEM。
```

### 3.3 阶段2：LLM 意图分类器详解

**文件**: `backend/app/services/preprocessing/intent_classifier.py`

#### 3.3.1 核心设计

- **模型**: gemma3:4b (ollama cloud) — 选择原因: 1.5s响应，比deepseek-v3快37倍
- **温度**: temperature=0.1 — 低温度保证分类稳定性
- **任务**: 文本矫正 + 意图分类（双任务合一）

#### 3.3.2 Prompt结构

```
你是一个意图分类器。根据用户输入，判断其意图类型。

可用意图:
1. file - 文件和目录操作 (读取/写入/编辑/搜索/移动/复制/删除/压缩/解压)
2. system - 系统信息查询和进程管理 (CPU/内存/进程/服务/环境变量)
3. shell - Shell命令执行和代码运行 (命令行/Python/JavaScript)
4. network - 网络通信和请求 (HTTP请求/下载/搜索/网页获取)
5. desktop - 桌面和窗口操作 (截图/鼠标/键盘/窗口管理/OCR)
6. document - 文档读写和数据处理 (PDF/Word/Excel/数据库)
7. meta - 元工具和时间操作 (工具帮助/管道/时间/定时器)

(含5个已合并分类的别名提示: time→meta, environment→system, database→document, ...)

用户输入: {user_input}

请返回JSON: {"corrected": "矫正后文本", "intent": "意图类型", "confidence": 0.0-1.0}
```

#### 3.3.3 解析策略

- 使用 `_extract_json_balanced()` 平衡花括号算法从返回文本中提取JSON
- `resolve_category()` 将LLM返回的intent字符串映射到ToolCategory枚举
- LLM失败时保持CRSS结果（优雅降级）

### 3.4 路由分发规则

| 意图 | Agent类 | 工具分类(注册) | CRSS→ToolCategory | 回滚支持 |
|------|---------|---------------|-------------------|---------|
| file | UniversalReactAgent | FILE | FILE | ✓ (RollbackMixin) |
| system | UniversalReactAgent | SYSTEM | SYSTEM | ✗ |
| shell (别名) | UniversalReactAgent | SYSTEM (shell_register注册到SYSTEM) | SYSTEM | ✗ |
| network | UniversalReactAgent | NETWORK | NETWORK | ✗ |
| desktop | DesktopReactAgent | DESKTOP | DESKTOP | ✗ |
| document | UniversalReactAgent | DOCUMENT | DOCUMENT | ✗ |
| meta (别名) | UniversalReactAgent | SYSTEM (meta_register注册到SYSTEM) | SYSTEM | ✗ |
| time (别名) | UniversalReactAgent | SYSTEM (meta_register注册到SYSTEM) | SYSTEM | ✗ |
| environment (别名) | UniversalReactAgent | SYSTEM | SYSTEM | ✗ |
| database (别名) | UniversalReactAgent | DOCUMENT | DOCUMENT | ✗ |
| code_execution (别名) | UniversalReactAgent | SYSTEM (shell_register注册到SYSTEM) | SYSTEM | ✗ |
| 未注册意图 | _GenericAgent | 无工具 | - | ✗ |

---

## 四、Agent 核心架构

### 4.1 概要总结

Agent 系统采用 **声明式配置驱动** + **Mixin组合** 的架构。`BaseAgent` 定义 ReAct 循环骨架和抽象接口，`ReactAgentMixin` 提供工具加载/LLM策略/任务追踪等公用逻辑，`RollbackMixin` 插入回滚能力，`AgentFactory` 根据 `AgentConfig` 声明式配置创建具体Agent实例。

### 4.2 类继承体系

```
                    ┌─────────────────┐
                    │   BaseAgent     │  (ABC - ReAct循环骨架)
                    │  base_react.py  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────┴──────┐  ┌───┴────┐  ┌──────┴─────────┐
    │ ToolLoaderMixin │  │        │  │  RollbackMixin  │
    │ tools/mixin.py  │  │        │  │ mixins/         │
    └────────┬───────┘  │        │  │ rollback_mixin  │
             │          │        │  └──────┬──────────┘
             │          │        │         │
    ┌────────┴───────┐  │  ┌─────┴─────────┐
    │ ReactAgentMixin │  │  │               │
    │ mixins/         │  │  │               │
    │ react_agent_    │  │  │               │
    │ mixin.py        │  │  │               │
    └────────┬───────┘  │  │               │
             │          │  │               │
    ┌────────┴──────────┴──┴───────────────┐
    │      UniversalReactAgent              │  (配置驱动通用Agent)
    │      universal_react.py               │
    └───────────────────────────────────────┘

    ┌───────────────────────────────────────┐
    │      DesktopReactAgent                │  (桌面专用Agent)
    │      desktop_react.py                 │
    │  (ReactAgentMixin + BaseAgent, 无回滚) │
    └───────────────────────────────────────┘
```

### 4.3 BaseAgent 抽象接口

```python
class BaseAgent(ABC):
    # === 抽象方法（子类必须实现）===
    @abstractmethod
    async def _get_llm_response(self) -> str:       # 获取LLM响应
        ...
    
    @abstractmethod
    async def _execute_tool(self, action, params) -> dict:  # 执行工具
        ...
    
    @abstractmethod
    def _get_system_prompt(self) -> str:             # 获取系统Prompt
        ...
    
    @abstractmethod
    def _get_task_prompt(self, task, context) -> str: # 获取任务Prompt
        ...
    
    # === Hook方法（子类可覆盖）===
    def _on_session_init(self, task, context): ...   # Session初始化
    def _on_before_loop(self, ...): ...              # 循环开始前
    def _on_after_loop(self): ...                    # 循环结束后
```

### 4.4 声明式配置注册表

**文件**: `backend/app/services/agent/agent_config.py`

```python
@dataclass
class AgentConfig:
    intent_type: str              # 意图类型标识
    category: ToolCategory        # 对应工具分类
    prompt_module: str            # Prompt模块路径 (懒加载)
    prompt_class_name: str        # Prompt类名
    category_display_name: str    # 中文显示名 (用于Prompt)
    rollback_enabled: bool        # 是否启用回滚
    max_steps: int = 100          # 最大循环步数
    aliases: List[str]            # 意图别名列表
```

注册表内容:

| intent_type | category | prompt_class | 显示名 | rollback | aliases |
|-------------|----------|-------------|--------|----------|---------|
| file | FILE | FileOperationPrompts | 文件操作 | True | [] |
| system | SYSTEM | SystemPrompts | 系统操作 | False | [shell,meta,time,...] |
| network | NETWORK | NetworkPrompts | 网络通信 | False | [] |
| document | DOCUMENT | DocumentPrompts | 文档读写 | False | [database] |
| desktop | DESKTOP | DesktopPrompts | 桌面操作 | False | [] |

### 4.5 AgentFactory 创建流程

```python
class AgentFactory:
    @classmethod
    def create(cls, intent_type, llm_client, task_id, 
               tool_category, max_steps, candidates, **kwargs) -> BaseAgent:
        
        # Step 1: 解析声明式配置
        config = resolve_agent_config(intent_type)
        # → 查AGENT_REGISTRY → 匹配intent_type或aliases
        
        # Step 2: 特殊处理desktop
        if intent_type == "desktop":
            return DesktopReactAgent(llm_client, task_id, ...)
        
        # Step 3: 通用Agent（配置驱动）
        return UniversalReactAgent(
            llm_client=llm_client,
            task_id=task_id,
            config=config,       # AgentConfig驱动
            **kwargs
        )
```

### 4.6 UniversalReactAgent 初始化详解

```python
class UniversalReactAgent(ReactAgentMixin, RollbackMixin, BaseAgent):
    def __init__(self, llm_client, task_id, config: AgentConfig, **kwargs):
        # Step 1: 调用BaseAgent.__init__
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=config.category,
            max_steps=config.max_steps,
            **kwargs
        )
        
        # Step 2: 保存配置
        self.config = config
        
        # Step 3: ReactAgentMixin — 工具+执行器+策略+追踪
        self._init_tools_and_executor(config.category)  # 加载工具,创建ToolExecutor
        self._init_llm_strategies()                      # 创建TextStrategy/ToolsStrategy
        self._init_task_tracking(config.rollback_enabled) # 初始化任务追踪
        self._init_candidates(candidates)                 # 初始化候选意图
        
        # Step 4: RollbackMixin — 按配置决定是否启用回滚
        if not config.rollback_enabled:
            self.rollback = lambda *a, **kw: False
        
        # Step 5: 加载Prompt类 (懒加载)
        self.prompts = config.prompt_class  # @property 懒加载
```

### 4.7 ReactAgentMixin 公用逻辑

```python
class ReactAgentMixin(ToolLoaderMixin):
    
    # === 工具与执行器 ===
    def _init_tools_and_executor(self, tool_category):
        ensure_tools_registered()           # 全量注册7分类工具
        self.load_tools_by_category(tool_category)  # 加载指定分类
        self.executor = ToolExecutor(tools=self._tools_dict)  # 创建执行器
    
    # === LLM策略 ===
    def _init_llm_strategies(self):
        self.text_strategy = TextStrategy(self.llm_client, self._tools_dict)
        self.tools_strategy = ToolsStrategy(self.llm_client, self._tools_dict)
        self.llm_adapter = LLMAdapter(api_base, api_key, model)
        self._strategy_determined = False  # 首次调用时懒探测
    
    def _call_llm(self):
        if not self._strategy_determined:
            strategy = await self.llm_adapter.detect_strategy()
            # → 发一个带tools的请求，看LLM是否支持FC
            # → 有tool_calls → "tools", 无 → "text"
            self._strategy_determined = True
        
        if strategy == "tools":
            return await self.tools_strategy.call(messages, ...)
        else:
            return await self.text_strategy.call(messages, ...)
    
    # === 任务追踪 ===
    def _init_task_tracking(self, enable):
        if enable:
            tracker = get_task_tracker()
            tracker.create_task(task_id, agent_id, task)
    
    # === System Prompt构建 ===
    def _build_system_prompt(self, category_name):
        parts = [
            self.prompts.get_system_prompt(),     # 分类特有Prompt
            self._build_cross_tool_hint(...),     # 跨分类工具提示
            self._build_candidates_hint(...),     # 候选意图提示
        ]
        return "\n".join(parts)
```

---

## 五、ReAct 循环详解

### 5.1 概要总结

ReAct 循环是整个 Agent 系统的核心引擎，实现在 `BaseAgent.run_stream()` 中。它遵循 **Thought→Action→Observation** 模式，每轮：调用LLM获取思考→解析响应→如果是工具调用则执行→观察结果→继续循环。支持中断、暂停、最大步数限制、空响应重试、解析错误重试、动态工具加载等机制。

### 5.2 循环状态机

```
                    ┌─────────────┐
                    │   IDLE      │
                    └──────┬──────┘
                           │ run_stream()
                           ▼
                    ┌─────────────┐
                    │  THINKING   │ ←── LLM推理中
                    └──────┬──────┘
                           │
                    解析响应类型
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────┐
    │   action     │ │  answer  │ │  chunk   │
    │  (工具调用)   │ │ (最终答案) │ │ (流式片段) │
    └──────┬───────┘ └────┬─────┘ └────┬─────┘
           │              │            │
           ▼              │            ▼
    ┌──────────────┐      │    ┌──────────────┐
    │  EXECUTING   │      │    │  连续chunk   │
    │  (工具执行)   │      │    │  达阈值?     │
    └──────┬───────┘      │    └──────┬───────┘
           │              │           │
           ▼              │     ┌────┴────┐
    ┌──────────────┐      │     │是       │否
    │  OBSERVING   │      │     ▼         ▼
    │  (观察结果)   │      │  implicit   continue
    └──────┬───────┘      │  (提升为完成)
           │              │
           ▼              ▼
    ┌──────────────┐ ┌──────────┐
    │  COMPLETED   │ │ COMPLETED│
    │  (继续循环)   │ │ (退出)   │
    └──────────────┘ └──────────┘
```

### 5.3 详细流程代码分析

```python
async def run_stream(self, task, context=None, max_steps=100, 
                     task_id=None, running_tasks=None):
    # ==========================================
    # 初始化阶段
    # ==========================================
    self.steps = []                              # 清空步骤历史
    self.message_builder = MessageBuilder()      # 新建消息组装器
    self.status = AgentStatus.THINKING           # 设置状态
    
    sys_prompt = self._get_system_prompt()       # 获取系统Prompt
    task_prompt = self._get_task_prompt(task, context)  # 获取任务Prompt
    
    self._on_session_init(task, context)         # Hook: Session初始化
    self._on_before_loop(sys_prompt, task_prompt, context)  # Hook: 循环前
    
    self.message_builder.init_history(sys_prompt, task_prompt)  # 初始化历史
    
    step_count = 0
    chunk_buffer = ""
    
    # ==========================================
    # 主循环
    # ==========================================
    while True:
        step_count += 1
        
        # --- [检查1] 最大步数 ---
        if step_count >= max_steps:
            yield StepFactory.create_error_step("达到最大步数限制")
            return
        
        # --- [检查2] 中断标志 ---
        if running_tasks and running_tasks[task_id]["cancelled"]:
            yield StepFactory.create_error_step("任务已取消")
            return
        
        # --- [步骤A] 调用LLM ---
        try:
            response = await self._get_llm_response()
        except Exception as e:
            # LLM调用异常 → ErrorStep → return
        
        # --- [检查3] LLM返回后中断 ---
        if running_tasks and running_tasks[task_id]["cancelled"]:
            return  # 静默退出，不yield
        
        # --- [步骤B] 空响应处理 ---
        if not response:
            self.empty_response_retry_count += 1
            if self.empty_response_retry_count > self.max_empty_response_retries:
                # 截断历史后重试
                self.message_builder.trim_history()
            continue
        
        # --- [步骤C] 解析响应 ---
        parsed = parse_react_response(response)
        # 返回: {type, content, tool_name, tool_params, ...}
        
        # ==========================================
        # 分支处理（按parsed.type）
        # ==========================================
        
        # --- [分支1] chunk (流式文本片段) ---
        if parsed["type"] == "chunk":
            chunk_buffer += parsed["content"]
            self.message_builder.temp_history.append(...)  # 临时缓冲
            yield ChunkStep(content=parsed["content"])
            
            if not self._tools_dict:  # 无工具Agent
                # 第一个chunk直接作为最终回答
                yield FinalStep(content=chunk_buffer)
                return
            else:
                # 连续chunk达阈值(5次) → 提升为implicit退出循环
                if consecutive_chunks >= MAX_CONSECUTIVE_CHUNKS:
                    parsed = {"type": "implicit", "content": chunk_buffer}
                else:
                    continue  # 继续接收chunk
        
        # --- [分支2] answer / implicit (最终答案) ---
        if parsed["type"] in ("answer", "implicit"):
            self.message_builder.flush_temp_to_history(chunk_buffer)
            yield FinalStep(content=parsed["content"])
            return
        
        # --- [分支3] thought_only (纯思考) ---
        if parsed["type"] == "thought_only":
            thought_step = ThoughtStep(content=parsed["content"])
            yield thought_step
            self.message_builder.add_assistant(response)
            self.message_builder.trim_history()
            continue
        
        # --- [分支4] parse_error (解析失败) ---
        if parsed["type"] == "parse_error":
            self.parse_retry_count += 1
            if self.parse_retry_count <= self.max_parse_retries:
                if is_network_error:
                    # 网络错误: 不注入history, 429限流指数退避
                    await asyncio.sleep(backoff)
                else:
                    # 格式错误: 注入Parse Error提示
                    self.message_builder.add_parse_error(error_msg)
                continue
            else:
                yield ErrorStep("解析重试次数耗尽")
                return
        
        # --- [分支5] action (正常工具调用) ---
        if parsed["type"] == "action":
            tool_name = parsed["tool_name"]
            tool_params = parsed["tool_params"]
            
            # 1. 创建并yield思考步骤
            thought_step = ThoughtStep(
                content=parsed.get("thought", ""),
                tool_name=tool_name,
                tool_params=tool_params
            )
            yield thought_step
            
            # 2. 工具执行前中断检查
            if running_tasks[task_id]["cancelled"]:
                return
            
            # 3. 执行工具
            start_time = time.time()
            try:
                result = await self._execute_tool(tool_name, tool_params)
            except Exception as e:
                result = {"code": -1, "message": str(e)}
            execution_time = time.time() - start_time
            
            # 4. 工具执行后中断检查
            if running_tasks[task_id]["cancelled"]:
                return
            
            # 5. 创建并yield工具执行步骤
            action_step = ActionToolStep(
                tool_name=tool_name,
                tool_params=tool_params,
                execution_status="success" if result["code"] == 0 else "error",
                summary=result.get("message", ""),
                raw_data=result.get("data"),
                execution_time=execution_time
            )
            yield action_step
            
            # 6. 添加assistant消息到历史
            self.message_builder.add_assistant(response)
            
            # 7. 构建observation文本
            observation_text = MessageBuilder.build_observation_text(result)
            
            # 8. 添加observation到历史
            fc_context = ...  # FC协议上下文 (ToolsStrategy时)
            self.message_builder.add_observation(observation_text, fc_context)
            
            # 9. 创建并yield观察步骤
            observation_step = ObservationStep(
                content=observation_text,
                tool_name=tool_name,
                is_finished=result.get("return_direct", False)
            )
            yield observation_step
            
            # 10. 检查是否直接完成 (return_direct)
            if observation_step.is_done():
                yield FinalStep(content=result.get("message"))
                return
            
            # 11. 检查动态加载工具
            if "load_tools" in result:
                self.load_tools_by_intent(result["load_tools"])
            
            # 12. 历史裁剪
            self.message_builder.trim_history()
            
            # 13. 执行并行工具调用 (_pending_calls)
            while self._pending_calls:
                pending = self._pending_calls.pop(0)
                result = await self._execute_tool(pending.name, pending.params)
                # ... 同样yield ActionToolStep + ObservationStep
```

### 5.4 关键机制汇总

| 机制 | 阈值/参数 | 说明 |
|------|----------|------|
| 最大步数 | `max_steps=100` | 防止无限循环 |
| 空响应重试 | `max_empty_response_retries=2` | LLM返回空时截断历史重试 |
| 解析错误重试 | `max_parse_retries=3` | 解析失败时区分网络/格式错误 |
| chunk提升 | `MAX_CONSECUTIVE_CHUNKS=5` | 连续5个chunk提升为implicit完成 |
| 中断检查 | 每步3处 | LLM前、LLM后、工具执行前后 |
| 动态工具加载 | 工具返回`load_tools` | 运行时按需加载其他分类工具 |
| 并行工具调用 | `_pending_calls`队列 | FC多工具调用时依次执行 |
| return_direct | 工具返回`return_direct=True` | 跳过后续推理直接完成 |

---

## 六、LLM 调用策略体系

### 6.1 概要总结

LLM 调用采用 **策略模式**，支持 Text（文本模式）和 Tools（Function Calling模式）两种策略。通过 `LLMAdapter` 在首次调用时 **探测** LLM 是否支持 FC，确定策略后缓存。`TextStrategy` 使用多层解析架构处理 LLM 的自由文本输出，`ToolsStrategy` 使用标准 FC 协议。

### 6.2 策略探测

```python
class LLMAdapter:
    async def detect_strategy(self) -> str:
        """首次调用时探测，后续缓存"""
        if self._strategy:
            return self._strategy
        
        # 发一个带tools参数的简单请求
        result = await self._probe_tools(client)
        
        if result.get("tool_calls"):
            self._strategy = "tools"   # LLM支持FC
        else:
            self._strategy = "text"    # LLM不支持FC，用文本模式
        
        return self._strategy
```

### 6.3 TextStrategy — 三层解析架构

```
LLM返回自由文本
  │
  ▼ [第一层] parse_react_response() — 9级解析器链
  │   ├── JSON格式 → action/answer/implicit
  │   ├── 混合文本 → 提取JSON块
  │   ├── 正则兜底 → 提取工具调用
  │   └── 关键词匹配 → 判断意图类型
  │
  │  解析结果:
  │   ├── answer → 直接finish ✓
  │   ├── chunk → 返回chunk数据 ✓
  │   ├── implicit → 直接finish ✓
  │   ├── action (有tool_name+tool_params) → 直接返回 ✓
  │   ├── thought_only / parse_error → 继续下一层 ↓
  │   └── action (缺tool_name/params) → 继续下一层 ↓
  │
  ▼ [第二层] _extract_by_known_tools() — 工具名保底匹配
  │   - 在原始文本中正则搜索已知工具名
  │   - 尝试提取常见参数 (path/text/file_name/search_query)
  │   - 支持Windows路径 (C:\) 和 Unix路径 (/)
  │
  ▼ [第三层] 兜底返回 parse_error
```

### 6.4 ToolsStrategy — FC协议

```
LLM接收tools参数
  │
  ▼ chat_with_tools(messages, tools=tools_schema)
  │
  ├── 返回tool_calls → 格式化为统一JSON
  │   ├── 单个工具调用 → {tool_name, tool_params}
  │   └── 多个工具调用 → 第一个立即执行，其余入_pending_calls
  │
  ├── 空tool_calls → 转为finish
  │
  ├── JSON解析失败 → _extract_json_block() 兜底
  │
  └── 无chat_with_tools方法 → fallback到TextStrategy
```

### 6.5 BaseAIService 核心能力

```python
class BaseAIService:
    # --- 非流式调用 ---
    async def chat(messages, ...) → ChatResponse
    
    # --- 流式调用 ---
    async def chat_stream(messages, ...) → AsyncGenerator[StreamChunk]
    # - SSE行解析: data: 前缀, [DONE] 结束
    # - 每秒检查取消标志 (wait_for timeout=1.0)
    # - 支持 reasoning_content (thinking模型)
    
    # --- FC调用 ---
    async def chat_with_tools(messages, tools, ...) → ChatResponse
    # - 后台任务 + 心跳检查
    # - XML工具调用转换 (_convert_xml_tool_call_to_json)
    
    # --- 429重试 ---
    # _StreamRetryContext: 指数退避, 最多3次, 基础延迟2秒
```

---

## 七、输出解析器链

### 7.1 概要总结

`parse_react_response()` 是 ReAct 系统的关键组件，使用 **责任链模式** 排列9个解析handler，按优先级依次尝试解析LLM输出。支持JSON/非标准JSON/混合文本/正则兜底/关键词匹配等多种格式，确保对各种LLM输出的最大兼容性。

### 7.2 九级解析器链

```
输入: LLM原始输出 (str / dict / list)
  │
  ▼ Handler 1: _handle_dict_input
  │   输入类型为dict → 直接提取tool_name/tool_params → action
  │   或含finish/answer字段 → implicit
  │
  ▼ Handler 2: _handle_list_input
  │   输入类型为list → 取第一个元素 → action
  │
  ▼ Handler 3: _handle_json_array_string
  │   以"["开头且"]"结尾 → json.loads → 按list处理
  │
  ▼ Handler 4: _handle_empty_input
  │   None/空字符串/非字符串 → parse_error
  │
  ▼ Handler 5: _handle_standard_json
  │   json.loads成功 → _process_json_result()
  │   ├── tool_name + tool_params → action
  │   ├── action + action_input → action (旧格式兼容)
  │   ├── finish/answer字段 → answer
  │   └── thought字段 → thought_only
  │
  ▼ Handler 6: _handle_non_standard_json
  │   单引号JSON → 替换单引号为双引号 → json.loads → 同上
  │
  ▼ Handler 7: _handle_mixed_text_json
  │   混合文本 → _extract_json_block() (平衡括号算法)
  │   ├── 提取成功 → 解析JSON
  │   └── 不完整JSON → 尝试补全 → 解析
  │
  ▼ Handler 8: _handle_regex_fallback
  │   正则匹配:
  │   ├── "Action: XXX\nAction Input: {...}" 模式
  │   ├── ```json\n{...}\n``` 代码块
  │   └── 自定义工具调用格式
  │
  ▼ Handler 9: _handle_keyword_match
  │   _determine_parse_type():
  │   ├── `` 包裹的文本 → 关键词 (可能是工具名)
  │   ├── 自然语言关键词匹配
  │   └── 文本长度 < 5 → parse_error
  │       文本长度 >= 5 → implicit (当作回答)
```

### 7.3 参数处理管道

当解析出 action 类型后，工具参数经过 **三步统一处理管道**:

```
原始tool_params
  │
  ▼ [Step 1] _normalize_tool_params_content()
  │   - content字段: 若为dict/list → JSON序列化为str
  │   - result字段: 同上
  │
  ▼ [Step 2] _filter_tool_params()
  │   - 对比input_schema的properties
  │   - 移除非标准参数 (如LLM幻觉添加的字段)
  │
  ▼ [Step 3] _supplement_missing_params()
  │   - 从原始输出中提取缺失的必需参数
  │   - 常见参数: path/file_path, text/content, query/keyword
  │
  ▼ 规范化后的tool_params
```

---

## 八、工具注册与加载机制

### 8.1 概要总结

工具系统采用 **单例Registry + 分类注册 + 按需加载** 模式。`ToolRegistry` 维护全局工具注册表，7个分类各有独立的注册/工具/Schema文件。启动时通过 `ensure_tools_registered()` 全量注册，Agent初始化时按分类加载所需工具到本地 `_tools_dict`。

### 8.2 ToolRegistry 核心数据结构

```python
class ToolRegistry:
    _tools: Dict[str, ToolMetadata]           # 工具名 → 元数据
    _categories: Dict[ToolCategory, List[str]] # 分类 → 工具名列表
    _implementations: Dict[str, Callable]      # 工具名 → 实现函数

@dataclass
class ToolMetadata:
    name: str                    # 工具名
    description: str             # 描述
    category: ToolCategory       # 所属分类
    input_schema: Dict           # OpenAI兼容的参数Schema
    output_schema: Dict          # 输出Schema
    expose_to_llm: bool = True   # 是否暴露给LLM
    examples: List[Dict]         # 使用示例
    next_actions: Dict           # 推荐后续操作
    ...
```

### 8.3 注册流程

```python
# ensure_tools_registered() 全量注册流程

_CATEGORY_MODULES = {
    "file":    ("app.services.tools.file",    "_register_file_tools"),
    "shell":   ("app.services.tools.shell",   "_register_shell_tools"),
    "network": ("app.services.tools.network", "_register_network_tools"),
    "system":  ("app.services.tools.system",  "_register_system_tools"),
    "desktop": ("app.services.tools.desktop", "_register_desktop_tools"),
    "document":("app.services.tools.document","_register_document_tools"),
    "meta":    ("app.services.tools.meta",    "_register_meta_tools"),
}

def ensure_tools_registered():
    for cat_name, (module_path, register_func) in _CATEGORY_MODULES.items():
        # 动态import模块
        module = importlib.import_module(module_path)
        # 调用注册函数
        getattr(module, register_func)()
        # 标记已注册
        _registered_categories.add(cat_name)
```

### 8.4 各分类工具清单

| 分类 | 工具数 | 工具列表 | 注册到Category |
|------|--------|---------|---------------|
| FILE | 11 | read_file, write_text_file, read_media_file, edit_file, list_directory, search_files, grep_file_content, rename_file, archive_tool, file_operation, data_file_format | FILE |
| SHELL | 4 | execute_shell_command, find_command, execute_code, shell_session | **SYSTEM** (特殊) |
| NETWORK | 5 | http_request, download_file, fetch_webpage, search_web, network_diagnose | NETWORK |
| SYSTEM | 10 | get_system_info, net_connections, event_log, list_processes, kill_process, service_control, task_control, get_env, set_env, registry_control | SYSTEM |
| DESKTOP | 9 | window_info, window_control, mouse_control, keyboard_control, screen_capture, clipboard_control, screen_record, ocr, send_notification | DESKTOP |
| DOCUMENT | 9 | read_document, write_document, convert_document, analyze_data, filter_data, generate_chart, query_sql, execute_sql, get_db_schema | DOCUMENT |
| META | 10 | tool_help, tool_search, pipeline, batch_process, get_time, time_add, time_diff, query_calendar, timezone_convert, timer | **SYSTEM** (特殊: meta_register.py注册到SYSTEM) |

> **特殊设计**: SHELL 和 META 工具分别通过 shell_register.py 和 meta_register.py 注册到 SYSTEM 分类。ToolCategory.SHELL 和 ToolCategory.META 枚举值保留用于兼容性，但实际无任何工具注册到它们下面。INTENT_TO_CATEGORY 和 CRSS TYPE_CATEGORY_MAP 均已统一将 shell/meta/time/code_execution 映射为 ToolCategory.SYSTEM。

### 8.5 工具Schema生成

```python
def register(name, description, category, input_model=None, ...):
    # Pydantic模型 → OpenAI兼容Schema
    if input_model:
        input_schema = input_model.model_json_schema()
    
    # 修复Pydantic V2兼容问题
    _fix_schema_types(input_schema)
    # - anyOf/oneOf中只有一个非null类型 → 直接设置type
    # - 多类型保留anyOf结构 (OpenAI API兼容)
    
    # 生成OpenAI tools格式
    tool_def = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": input_schema
        }
    }
```

### 8.6 动态工具加载

```python
# Agent运行时可动态加载其他分类工具
def load_tools_by_intent(self, intent_type, reason):
    # 1. 检查是否已加载
    if intent_type in self._loaded_categories:
        return
    
    # 2. 解析意图到ToolCategory
    category = resolve_category(intent_type)
    
    # 3. 从registry获取该分类所有工具
    tools = tool_registry.list_tools(category=category)
    
    # 4. 更新本地_tools_dict
    for tool in tools:
        self._tools_dict[tool.name] = tool_registry.get_implementation(tool.name)
    
    # 5. 刷新FC通道的tools定义
    if self.tools_strategy:
        self.tools_strategy.tools = tool_registry.to_openai_tools(
            categories=self._loaded_categories
        )
    
    # 6. 清除message_builder缓存
    self.message_builder.invalidate_cache()
```

---

## 九、工具执行器

### 9.1 概要总结

`ToolExecutor` 是工具执行的统一入口，封装了 **别名转换 → 废弃检查 → 参数规范化 → 必需参数验证 → 执行(含重试) → 错误分类** 的完整管道。支持 async/sync 工具的统一调度，同步工具通过 `to_thread` 委托到线程池。

### 9.2 执行管道

```
execute(action, action_input)
  │
  ▼ [Step 1] 废弃检查
  │   is_deprecated_tool(action) → ERR_TOOL_DEPRECATED
  │
  ▼ [Step 2] 别名转换
  │   action = get_tool_name_alias(action)
  │   例: "read_text_file" → "read_file"
  │
  ▼ [Step 3] finish短路
  │   action == "finish" → 直接返回成功
  │
  ▼ [Step 4] 工具查找
  │   本地tools_dict → 全局tool_registry → ERR_TOOL_NOT_FOUND
  │
  ▼ _execute_with_retry(action, action_input)
  │
  ▼ [Step 5] 参数规范化
  │   _normalize_params(): 基于input_schema移除非法参数
  │
  ▼ [Step 6] 必需参数验证
  │   inspect.signature() 检查, 缺失 → ERR_MISSING_PARAM
  │
  ▼ [Step 7] 执行工具
  │   ├── 纯async函数: await asyncio.wait_for(tool(**params), timeout)
  │   ├── lambda包装async: to_thread → coroutine → await
  │   └── 纯同步函数: asyncio.to_thread(tool, **params) → wait_for
  │
  ▼ [Step 8] 错误处理
  │   ErrorClassifier.classify(exception) → ErrorType
  │   ├── TIMEOUT → 可重试, 指数退避
  │   ├── PERMISSION_DENIED → 不可重试
  │   ├── FILE_NOT_FOUND → 不可重试
  │   └── UNKNOWN → 不可重试
```

### 9.3 重试策略

```python
class RetryPolicy:
    max_retries: int = 3           # 最大重试次数
    backoff_factor: float = 2.0    # 退避因子
    retryable_errors: List[str] = ["timeout"]  # 可重试错误类型
    
    def get_wait_time(self, attempt):
        return self.backoff_factor ** attempt  # 1s, 2s, 4s, ...
```

---

## 十、Message 组装与历史管理

### 10.1 概要总结

`MessageBuilder` 是 Agent 会话历史的唯一写入入口，管理 system/user/assistant/observation 消息的组装、注入、裁剪。核心设计：**容量感知延迟裁剪**（超过80%阈值才触发，裁剪到70%）、**observation智能截断**（头60%+尾40%）、**FC协议配对裁剪**、**MD5指纹去重**。

### 10.2 七组方法

```
┌─────────────────────────────────────────────────┐
│ 第1组: conversation_history 写操作                │
│  - init_history(sys_prompt, task_prompt)         │
│  - add_assistant(content)                        │
│  - add_observation(observation_text, fc_context) │
│  - add_parse_error(error_msg)                    │
│  - flush_temp_to_history(chunk_buffer)           │
├─────────────────────────────────────────────────┤
│ 第2组: observation_text 构建 (静态方法)           │
│  - build_observation_text(execution_result)      │
├─────────────────────────────────────────────────┤
│ 第3组: LLM调用消息组装                           │
│  - prepare_messages_for_llm()                    │
│  - inject_tools_info()                           │
│  - inject_schema_text()                          │
├─────────────────────────────────────────────────┤
│ 第4组: 历史裁剪 (延迟裁剪)                       │
│  - trim_history() — 容量感知, 80%阈值触发        │
├─────────────────────────────────────────────────┤
│ 第5组: 缓存管理                                  │
│  - invalidate_cache()                            │
├─────────────────────────────────────────────────┤
│ 第6组: observation截断辅助                       │
│  - _get_observation_budget(llm_call_count)       │
│  - _smart_truncate(content, budget, head_ratio)  │
├─────────────────────────────────────────────────┤
│ 第7组: Schema文本生成                            │
│  - build_schema_text(openai_tools)               │
└─────────────────────────────────────────────────┘
```

### 10.3 历史裁剪算法详解

```python
def trim_history(self):
    total = _total_chars(self.conversation_history)
    
    # 仅当超过80%阈值时触发
    if total < MAX_CONTEXT_CHARS * 0.8:  # 150000 * 0.8 = 120000
        return
    
    # 分类消息
    system_msgs = [msg for msg in history if msg["role"] == "system"]
    obs_list = [msg for msg in history if _is_observation_role(msg)]
    assistant_msgs = [msg for msg in history if msg["role"] == "assistant"]
    
    # MD5指纹去重 (FC消息跳过)
    obs_list = _dedup_by_fingerprint(obs_list)
    
    # 保留最新10条assistant + 30条observation
    # 从最旧开始移除observation直到满足预算 (150000 * 0.7 = 105000)
    while _total_chars(history) > target_budget and obs_list:
        oldest_obs = obs_list.pop(0)
        history.remove(oldest_obs)
    
    # FC协议配对裁剪
    history = _trim_fc_pairs(history)
    
    # 保证至少有system + user两条消息
    assert len(history) >= 2
```

### 10.4 Observation预算公式

```python
def _get_observation_budget(self, llm_call_count):
    # 随LLM调用次数递减，上限50000
    budget = OBSERVATION_BUDGET_MIN + OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
    # llm_call_count=0 → 20000 + 10000*5 = 70000 → cap 50000
    # llm_call_count=1 → 20000 + 10000*4 = 60000 → cap 50000
    # llm_call_count=5 → 20000 + 10000*0 = 20000
    # llm_call_count=10 → 20000 + 10000*0 = 20000
    return min(budget, 50000)
```

---

## 十一、Prompt 模板体系

### 11.1 概要总结

Prompt 系统采用 **基类框架 + 子类特化 + OS适配** 三层结构。`BasePromptTemplate` 定义6段组装架构（分类Prompt → 输出格式 → 工具调用规则 → 安全提醒 → 回滚说明 → 去重规则），子类只需实现 `get_system_prompt()` 即可。`SystemAdapter` 根据运行OS注入平台特定的路径和命令格式。

### 11.2 六段组装架构

```
build_full_system_prompt()
  │
  ├── ① get_system_prompt()          — 分类特有: 角色定义 + 工具详情 + 示例
  │     (子类实现，如FileOperationPrompts, NetworkPrompts等)
  │
  ├── ② OUTPUT_FORMAT                — 公共: JSON输出格式规范
  │     - 两种返回: {"tool_name":..., "tool_params":...} 或 {"action":"finish", ...}
  │     - 含thought/reasoning字段要求
  │     - 禁止项: 多tool_name, [TOOL_CALL]格式, XML标签
  │
  ├── ③ TOOL_CALL_RULES              — 公共: 工具调用行为规则
  │     - 确认意图后立即调用
  │     - reasoning简短
  │     - 中文回复
  │     - 错误时建议替代方案
  │
  ├── ④ get_safety_reminder()        — 分类特有: 安全提醒 (默认空)
  │
  ├── ⑤ get_rollback_instructions()  — 公共: 回滚操作说明
  │
  └── ⑥ 避免重复规则                 — 公共: 同一命令不重复执行
```

### 11.3 OS适配器

```python
class SystemAdapter:
    # 根据服务器OS生成自适应内容
    # Windows: 路径 C:\, 命令 dir/copy/del/type/findstr
    # Linux:   路径 /home/, 命令 ls/cp/rm/cat/grep
    # macOS:   路径 /Users/, 命令 ls/cp/rm/cat/grep
    
    def get_system_prompt(include_commands=False):
        # include_commands=True: ShellAgent注入命令格式
        # include_commands=False: 其他Agent不注入(防止LLM幻觉调用execute_shell_command)
```

### 11.4 各意图Prompt特点

| 意图 | 工具数 | 特色规则 |
|------|--------|---------|
| file | 11 | 互斥参数规则、write_text_file的text规则、TaskTemplates预定义 |
| network | 5 | URL必须含scheme、json_body而非data/params |
| shell | 4 | 注入命令格式(include_commands=True) |
| desktop | 9 | 26→10工具精简重构后的窗口/鼠标键盘/截图/OCR/通知 |
| system | 24 | 最大工具集(10 system + 4 shell + 10 meta) |
| document | 9 | 文档读写+数据分析+数据库，8合2路由重构 |
| meta | 3 | tool_help/tool_search/pipeline元工具 |

---

## 十二、SSE 流式输出机制

### 12.1 概要总结

SSE 层由 `react_sse_wrapper.py` 实现，负责将 Agent 的 `run_stream()` 生成器产出的 Step 对象格式化为 SSE 事件推送给前端。支持8种事件类型，附带 DB 持久化、中断控制、任务超时清理。

### 12.2 SSE事件类型

| 事件类型 | 对应Step | 前端含义 |
|---------|----------|---------|
| `thought` | ThoughtStep | Agent思考过程 |
| `action_tool` | ActionToolStep | 工具执行中 |
| `observation` | ObservationStep | 工具执行结果 |
| `final` | FinalStep | 最终回答 |
| `chunk` | ChunkStep | 流式文本片段 |
| `error` | ErrorStep | 错误 |
| `incident` | - | 安全事件 |
| `interrupted` | - | 中断 |

### 12.3 SSE流生成流程

```python
async def generate_sse_stream(intent_type, ...):
    # 1. 注册任务
    running_tasks[task_id] = {"cancelled": False, "paused": False, ...}
    
    try:
        # 2. 尝试Agent SSE流
        async for event_dict in _run_agent_sse_stream(intent_type, ...):
            # 每个event前检查中断
            if running_tasks[task_id]["cancelled"]:
                break
            
            # 3. 格式化为SSE字符串
            sse_str = _format_sse_event(event_dict)
            yield sse_str
            
            # 4. DB持久化
            save_execution_steps_to_db(event_dict)
            
            # 5. 节流
            await asyncio.sleep(0.05)  # 50ms
            
    except ValueError:
        # intent_type未注册 → fallback到通用SSE流
        async for event in _run_generic_sse_stream(...):
            yield _format_sse_event(event)
    
    except asyncio.CancelledError:
        yield _format_sse_event(create_error_response("客户端断开"))
    
    finally:
        # 清理任务
        cleanup_task(task_id)
```

### 12.4 中断机制

```python
async def cancel_task(task_id):
    # 三重中断:
    # 1. 设置cancelled标志 (ReAct循环检查)
    running_tasks[task_id]["cancelled"] = True
    # 2. asyncio.Task.cancel() (取消正在进行的LLM调用)
    if task in asyncio.all_tasks():
        task.cancel()
    # 3. 强制关闭HTTP连接 (释放资源)
    if ai_service:
        ai_service.cancel()
```

---

## 十三、安全与回滚机制

### 13.1 概要总结

安全机制分为两层：**路由层** 的黑名单检测（`command_security.py`）和 **工具层** 的文件操作安全服务（`FileOperationSafety`）。回滚机制仅对 file 意图启用，通过 `RollbackMixin` + `FileOperationSessionService` 实现，支持单个操作回滚和整会话批量回滚。

### 13.2 路由层安全检查

```python
# chat_router.py
def check_command_safety(user_input):
    # 黑名单检测
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",     # rm -rf /
        r"format\s+[A-Z]:",  # format C:
        r"del\s+/[sfq]",     # del /s /f /q
        r"shutdown",         # 关机
        r"reg\s+delete",     # 注册表删除
        ...
    ]
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            return {"safe": False, "reason": "危险命令"}
    return {"safe": True}
```

### 13.3 文件操作安全服务

```python
class FileOperationSafety:
    # 核心能力:
    
    # 1. 操作历史记录 (SQLite: operations.db)
    record_operation(task_id, operation_type, source_path, ...)
    
    # 2. 回收站机制
    #    删除的文件 → 备份到 ~/.omniagent/recycle_bin/
    #    30天后自动清理
    
    # 3. 安全执行
    execute_with_safety(operation_id, operation_func, ...):
        # 更新状态: PENDING → EXECUTING
        # 删除操作: 先备份到回收站
        # 执行operation_func()
        # 收集文件信息 (大小/SHA-256/扩展名)
        # 计算空间影响和耗时
        # 更新状态: EXECUTING → SUCCESS/FAILED
    
    # 4. 回滚
    rollback_operation(operation_id):
        # DELETE: 从回收站恢复
        # MOVE:   移回源位置
        # CREATE: 删除创建的文件
    
    rollback_session(task_id):
        # 按逆序回滚整个会话的所有操作
```

### 13.4 RollbackMixin

```python
class RollbackMixin:
    async def rollback(self, step_number=None):
        if step_number is None:
            # 回滚所有步骤
            await self.executor.execute('rollback_session', ...)
        else:
            # 回滚指定步骤之后的操作
            await self.executor.execute('rollback_operation', ...)
```

---

## 十四、辅助支撑模块

### 14.1 ReasoningSteps — Step封装类体系

```
ReasoningStep (ABC)
  ├── ChunkStep      — 流式文本片段
  ├── ThoughtStep    — 思考步骤 (含ToolMixin: tool_name/tool_params)
  ├── ActionToolStep — 工具执行步骤 (含ToolMixin)
  ├── ObservationStep— 观察步骤 (含ToolMixin, 含is_finished)
  ├── FinalStep      — 最终回答
  └── ErrorStep      — 错误

StepFactory:
  - 统一构建入口，隐藏具体类
  - create_thought_step(), create_action_step(), ...
```

### 14.2 TaskTracker — 任务执行追踪

```python
class TaskExecutionTracker:
    # file意图 → FileOperationSessionService (SQLite持久化)
    # 其他意图 → GenericTaskTracker (内存dict)

class GenericTaskTracker:
    # 轻量追踪，内存存储
    # 只做基本统计: start_time, end_time, success, step_count
```

### 14.3 RetryPolicy + CircuitBreaker

```python
class CircuitBreaker:
    # 三态: CLOSED → OPEN → HALF_OPEN
    # failure_threshold=5, recovery_timeout=60s
    # OPEN状态: 直接拒绝调用
    # HALF_OPEN: 允许一个探测调用

class RetryPolicy:
    # 含熔断器的增强版重试策略
    # max_retries=3, backoff_factor=2.0
    # 每次重试前检查熔断器状态
```

### 14.4 ToolAliases — 别名管理

```python
# 优先级: 分类别名 > 全局别名
resolve_tool_alias("read_text_file")  → "read_file"
resolve_tool_alias("check_command")   → "find_command"
resolve_tool_alias("query_calendar")  → "query_calendar" (已改名, 无旧别名)
```

### 14.5 ToolConfig — 工具配置管理

```python
class ToolConfig:
    # 从 config/tools.yaml 加载
    # 支持超时设置、参数别名、重试配置
    # 热重载 (原子性替换)
    # 环境变量替换
```

### 14.6 ToolResultFormatter — 双输出路径

```python
# 给LLM看的observation (截断+格式化)
_format_llm_observation(result) → str

# 给前端SSE事件的dict (1M上限截断)
_format_frontend_event(result) → dict
```

### 14.7 统一工具返回结构

```python
# 所有工具必须返回此结构
{
    "code": 0,           # 0=成功, -1=错误, 1=警告
    "data": {...},       # 结构化数据
    "message": "...",    # 人类可读消息
    "warning": "...",    # 可选: 警告信息
    "llm_data": {...},   # 可选: 给LLM的精简数据
    "next_actions": {},  # 可选: 推荐后续操作
    "return_direct": F,  # 可选: 是否跳过后续推理
    "attachment": {}     # 可选: 附件(如图片Base64)
}
```

---

## 附录：完整数据流图

```
┌──────────────────────────────────────────────────────────────────────┐
│                        用户输入                                       │
│                    "帮我读取config.yaml"                               │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ chat_router.py                                                       │
│  1. PreprocessingPipeline.process() → strip                          │
│  2. route_with_fallback()                                            │
│     ├─ CRSS: "读取"→read(动作), "config.yaml"→FILE(类型)             │
│     │  双维度合成 → confidence=0.85 → 返回 FILE                       │
│     └─ (CRSS足够, 跳过LLM)                                           │
│  3. task_id = UUID()                                                 │
│  4. check_command_safety() → safe                                    │
│  5. send_start_step() → SSE: {type: "start"}                        │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ react_sse_wrapper.py → generate_sse_stream()                         │
│  1. AgentFactory.create("file") → UniversalReactAgent                │
│     ├─ ensure_tools_registered() → 注册7分类48工具                    │
│     ├─ load_tools_by_category(FILE) → 加载11个FILE工具               │
│     ├─ _init_llm_strategies() → TextStrategy + ToolsStrategy         │
│     └─ LLMAdapter.detect_strategy() → "text" 或 "tools"             │
│  2. agent.run_stream(task) → AsyncGenerator[Step]                   │
└─────────────────────────────┬────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│ BaseAgent.run_stream() — ReAct循环                                   │
│                                                                      │
│  Step 1: LLM推理 (TextStrategy/ToolsStrategy)                        │
│    → response: '{"tool_name":"read_file","tool_params":{"path":...}}'│
│                                                                      │
│  Step 2: parse_react_response(response)                              │
│    → Handler 5 (标准JSON) → type="action", tool_name="read_file"     │
│                                                                      │
│  Step 3: yield ThoughtStep → SSE: {type: "thought", ...}            │
│                                                                      │
│  Step 4: ToolExecutor.execute("read_file", {"path": "config.yaml"})  │
│    → 别名转换 → 参数规范化 → await read_file(path="config.yaml")      │
│    → result: {code: 0, data: {content: "..."}, message: "读取成功"}   │
│                                                                      │
│  Step 5: yield ActionToolStep → SSE: {type: "action_tool", ...}     │
│                                                                      │
│  Step 6: observation = build_observation_text(result)                │
│    → add_observation(observation) → 智能截断(如需要)                  │
│                                                                      │
│  Step 7: yield ObservationStep → SSE: {type: "observation", ...}    │
│                                                                      │
│  Step 8: LLM推理 (基于observation决定下一步)                          │
│    → response: '{"action":"finish","result":"文件内容如下:..."}'      │
│                                                                      │
│  Step 9: parse → type="answer"                                       │
│                                                                      │
│  Step 10: yield FinalStep → SSE: {type: "final", ...}               │
│                                                                      │
│  完成!                                                                │
└──────────────────────────────────────────────────────────────────────┘
```

---

> 文档结束 | 全文基于代码 v0.13.11 实际实现分析 | 如有疑问请对照源码验证
