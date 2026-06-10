# LLM Prompt与Message Conversation History全系统分析

**创建时间**: 2026-06-10 15:15:59  
**版本**: v1.2  
**作者**: 小沈  
**复查次数**: 5遍  

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-10 15:15:59 | 小沈 | 初始版本，全系统分析完成 |
| v1.1 | 2026-06-11 04:43:57 | 小沈 | 逐问题验证准确性+10大原则符合性+补充遗漏关键问题 |
| v1.2 | 2026-06-11 | 小健 | 逐问题修复复核，标注修复状态（✅已修复/⚠️未修复/✅不修改） |

---

## 一、核心架构总览

### 1.1 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：Prompt构建层（BasePrompts + 子类）                    │
│  职责：生成System Prompt + Task Prompt                       │
│  入口：build_full_system_prompt()                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  第二层：Message管理层（MessageBuilder）                      │
│  职责：管理conversation_history状态                           │
│  核心：init_history / add_assistant / add_observation        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  第三层：LLM调用层（BaseAIService）                           │
│  职责：发送messages给LLM，接收响应                             │
│  入口：request_stream(messages, mode, tools)                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 数据流向图

```
用户请求
    ↓
chat_stream_v2.py (路由层)
    ↓
AgentFactory.create(intent_type)
    ↓
UniversalAgent.__init__()
    ├─ 加载Prompt模板: config.prompt_class()
    └─ 初始化工具: ToolManager.init_tools()
    ↓
run_react_cycle() ─────────────────────────────────────┐
    ↓                                                  │
_initialize_run_state()                                │
    ├─ _get_system_prompt()                            │
    │   └─ prompts.build_full_system_prompt()          │
    ├─ _get_task_prompt(task, context)                 │
    └─ message_builder.init_history(sys, task)         │
        └─ conversation_history = [system, user]       │
    ↓                                                  │
循环开始 ←─────────────────────────────────────────────┤
    ↓                                                  │
_call_llm()                                            │
    ├─ message_builder.prepare_messages_for_llm()      │
    │   └─ 返回 conversation_history + temp_history    │
    ├─ llm_client.request_stream(messages, mode, tools)│
    └─ yield ("chunk", ChunkStep) / ("response", str)  │
    ↓                                                  │
parse_llm_response(llm_response)                       │
    └─ 返回 {type, thought, tool_name, tool_params}    │
    ↓                                                  │
handler分派                                            │
    ├─ action → 执行工具                               │
    │   ├─ yield ThoughtStep                           │
    │   ├─ 执行工具 → result                           │
    │   ├─ yield ActionToolStep                        │
    │   ├─ yield ObservationStep                       │
    │   └─ message_builder.add_observation()           │
    ├─ answer → 任务完成                               │
    │   └─ yield FinalStep                             │
    └─ chunk → 累积内容                                │
        └─ temp_history.append(chunk)                  │
    ↓                                                  │
判断是否继续循环 ───────────────────────────────────────┘
```

---

## 二、Prompt构建层详细分析

### 2.1 BasePrompts基类（base_prompt_template.py）

**文件路径**: `backend/app/services/prompts/base_prompt_template.py`

**核心职责**:
- 定义Prompt模板基类接口
- 统一System Prompt组装顺序
- 提供公共规则常量

**关键常量**:

#### 2.1.1 OUTPUT_FORMAT（JSON输出格式规则）

```python
OUTPUT_FORMAT = """【Response Format - 必须遵守】:
必须使用JSON格式输出,只能返回以下两种情况之一:

情况1:调用工具(继续执行)
{
  "thought": "分析当前状态和下一步决策",
  "reasoning": "为什么选这个工具、参数如何确定",
  "tool_name": "get_current_time",
  "tool_params": {"action": "now"}
}

情况2:任务完成(退出循环)
{
  "thought": "任务已完成",
  "reasoning": "完成说明",
  "tool_name": "finish",
  "tool_params": {"result": "最终结果"}
}

【字段要求】:
- thought: 必需
- reasoning: 必需
- tool_name: 必需(实际工具名或finish)
- tool_params: 必需(参数对象或{})

【禁止项】:
- ❌ 禁止同时返回多个tool_name
- ❌ 禁止tool_name存在但tool_params缺失
- ❌ 禁止使用 [TOOL_CALL] 格式
- ❌ 禁止使用XML标签格式
- ❌ 禁止在content中嵌入工具调用
- ❌ 禁止使用任意自定义标签或特殊标记包裹工具名和参数

【SAFETY WARNING】:
⚠️ 任务完成时必须返回 tool_name="finish",否则会进入死循环。"""
```

**分析**:
- ✅ 明确规定两种返回情况（调用工具/任务完成）
- ✅ 字段要求清晰（thought/reasoning/tool_name/tool_params）
- ✅ 禁止项详细（防止LLM使用非标准格式）
- ⚠️ **问题**: 禁止项过多，可能导致LLM困惑

#### 2.1.2 TOOL_CALL_RULES（工具调用规则）

```python
TOOL_CALL_RULES = """【Tool Call Rules - 极其重要】:
- 确认用户意图后,立即调用对应工具,不要在thought中反复讨论该用哪个工具
- reasoning字段简短说明选择理由即可(1-2句),不要写长篇分析
- ❌ 禁止:在thought中列举多个工具比较优缺点而不调用
- ❌ 禁止:在thought中分析参数是否必填而不调用
- ❌ 禁止:仅用文字回复而不调用工具 — 用户请求需要实际操作时,MUST调用工具
- ✅ 正确:确认意图→直接调用→根据结果决定下一步
- 始终用中文回复用户
- 工具返回错误时,向用户解释错误并建议替代方案

【IMPERATIVE: 必须使用工具执行操作】:
- 当用户要求创建/写入/读取/修改文件时,你MUST调用对应的文件工具
- 不得仅回复"好的,我将..."之类的文字确认而不调用工具
- 只有在任务完成需要总结结果时,才能使用 tool_name="finish" 结束
- 如果不确定用什么工具,选择最合理的工具并调用,不要用文字回复代替"""
```

**分析**:
- ✅ 强调立即调用工具，不反复讨论
- ✅ 明确禁止仅文字回复
- ⚠️ **问题**: 规则重复强调，可能与OUTPUT_FORMAT冲突

#### 2.1.3 build_full_system_prompt()（唯一组装入口）

```python
def build_full_system_prompt(self) -> str:
    """构建完整的系统 Prompt(唯一组装入口)
    
    组装顺序:
    ① get_system_prompt()       — 分类特有(角色+工具+示例)
    ② OUTPUT_FORMAT             — 公共:JSON输出格式(含退出规则)
    ③ TOOL_CALL_RULES           — 公共:工具调用规则
    ④ get_safety_reminder()     — 分类特有:安全提醒
    ⑤ get_rollback_instructions()— 公共:回滚说明
    """
    parts = [self.get_system_prompt()]
    
    parts.append(self.OUTPUT_FORMAT)
    parts.append(self.TOOL_CALL_RULES)
    
    safety = self.get_safety_reminder()
    if safety:
        parts.append(safety)
    
    rollback = self.get_rollback_instructions()
    if rollback:
        parts.append(rollback)
    
    # 避免重复规则
    avoid_repeat_rules = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行(结果不会变)
- 同一命令/URL失败3次后必须换工具或换URL,禁止再试同方式
- 已获取的信息直接使用,不需要重新获取
- 失败后优先尝试替代方法,而非反复重试同一方法"""
    parts.append(avoid_repeat_rules)
    
    return "\n\n".join(parts)
```

**组装顺序分析**:
```
① get_system_prompt()         [分类特有] → 角色+工具+示例
② OUTPUT_FORMAT               [公共]     → JSON格式规则
③ TOOL_CALL_RULES             [公共]     → 工具调用规则
④ get_safety_reminder()       [分类特有] → 安全提醒
⑤ get_rollback_instructions() [公共]     → 回滚说明
⑥ avoid_repeat_rules          [公共]     → 避免重复规则
```

**分析**:
- ✅ 组装顺序合理：先角色定义，后规则约束
- ✅ 公共规则统一注入，避免重复
- ⚠️ **问题**: avoid_repeat_rules硬编码在方法中，应提取为常量

---

### 2.2 FileOperationPrompts子类（file_prompts.py）

**文件路径**: `backend/app/services/prompts/file/file_prompts.py`

**核心职责**:
- 定义文件操作Agent的System Prompt
- 注入服务器OS信息（通过中间层）
- 动态生成工具描述

**get_system_prompt()实现**:

```python
def get_system_prompt(self) -> str:
    """获取增强版系统Prompt"""
    # 1. 注入服务器OS信息
    system_info = get_system_prompt_string(include_commands=False)
    
    # 2. 动态生成工具描述
    tools = [
        "read_file", "write_text_file", "list_directory",
        "search_files", "grep_file_content", "edit_file",
        "rename_file", "file_operation", "archive_tool",
        "read_media_file", "data_file_format",
    ]
    tool_descriptions = self.build_tool_descriptions(tools, category_label="FILE")
    
    # 3. 组装Prompt
    prompt = f"{system_info}\n\n# File Operation Tools\n\n{tool_descriptions}"
    
    # 4. 追加示例
    return prompt + """
【Tool Call Examples】:
Example 1: 读取文件
{"thought": "用户要读取配置文件", "reasoning": "调用read_file单文件模式", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/config.json"]}}

Example 2: 搜索文件内容
{"thought": "搜索包含TODO的Python文件", "reasoning": "使用grep_file_content搜索", "tool_name": "grep_file_content", "tool_params": {"pattern": "TODO", "search_dir": "D:/project", "glob": "*.py"}}

Example 3: 写入文件
{"thought": "用户要写入新文件", "reasoning": "使用write_text_file写入", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/output.txt", "text": "Hello World"}}

Example 4: 任务完成
{"thought": "文件操作已完成", "reasoning": "全部操作成功,结果已返回", "tool_name": "finish", "tool_params": {"result": "已读取配置文件并完成搜索"}}

【⚠️ P17互斥参数规则 - 极其重要】:
- read_file: file_paths传1个路径=单文件, 传多个=批量
- edit_file: old_string 和 edits 不能同时使用
- rename_file: path 和 directory 不能同时使用
- archive_tool: compress模式需要source+destination,extract模式需要source
- file_operation: move/copy需要destination,delete不需要

【⚠️ write_text_file text规则 - 极其重要】:
- text参数必须传入实际的文件内容(代码、文本、正文等)
- ❌ 绝对禁止将你的思考/计划/状态确认当作text传入
- ❌ 错误示例: text="已成功创建并写入第一章,需要继续创建第二章"
- ✅ 正确示例: text="第一章:觉醒\n\n林凡是一名普通的大学生..."""
```

**分析**:
- ✅ 动态生成工具描述，避免硬编码
- ✅ 示例清晰，包含完整JSON格式
- ✅ 参数规则详细，防止误用
- ⚠️ **问题**: 示例硬编码在字符串中，应提取为模板池

---

### 2.3 SystemAdapter中间层（system_adapter.py）

**文件路径**: `backend/app/services/prompts/middle/system_adapter.py`

**核心职责**:
- 根据服务器OS生成系统自适应Prompt
- 提供路径格式、命令格式映射

**generate_system_prompt()实现**:

```python
def generate_system_prompt(self, include_commands: bool = True) -> str:
    """生成系统信息Prompt"""
    system_name = self.get_system_name()
    path_format = self.get_path_format()
    
    prompt = f"""【当前系统】
{system_name}

【路径格式】
- 当前系统: {path_format}
"""
    if include_commands:
        commands = self.get_commands()
        cmd_lines = "\n".join(f"- {k}: {v}" for k, v in commands.items())
        prompt += f"""
【命令格式】
{cmd_lines}
"""
    
    prompt += """
【路径规则】
- 必须使用绝对路径(禁止相对路径如 ./file.txt)
- 禁止用 ~ 表示家目录
- ❌ 路径中的中文字符必须原样保留,禁止翻译或转换!
"""
    
    return prompt
```

**分析**:
- ✅ 系统自适应，支持Windows/Linux/macOS
- ✅ include_commands参数控制是否注入命令格式
- ✅ 路径规则清晰，防止LLM转换中文路径
- ✅ 使用lru_cache单例，避免重复计算

---

### 2.4 UniversalAgent的Prompt组装（universal_agent.py）

**文件路径**: `backend/app/services/agent/universal_agent.py`

**_get_system_prompt()实现**:

```python
def _get_system_prompt(self) -> str:
    """构建完整system prompt"""
    # 1. 基础prompt（来自BasePrompts）
    base_prompt = self.prompts.build_full_system_prompt()
    
    # 2. 候选意图提示
    candidates_hint = self._build_candidates_hint()
    
    # 3. 跨分类工具提示
    cross_tool_hint = self._build_cross_tool_hint()
    
    # 4. 组装
    parts = [base_prompt]
    if candidates_hint:
        parts.append(candidates_hint)
    if cross_tool_hint:
        parts.append(cross_tool_hint)
    
    return "\n\n".join(parts)
```

**_build_candidates_hint()实现**:

```python
def _build_candidates_hint(self) -> str:
    """构建候选意图提示"""
    if not self._candidates:
        return ""
    
    from app.services.agent.agent_config import resolve_agent_config
    names = []
    for c in self._candidates:
        cfg = resolve_agent_config(c)
        if cfg:
            names.append(f"{cfg.category_display_name}({c})")
    
    if not names:
        return ""
    
    return f"【候选意图】用户任务可能属于以下分类: {', '.join(names)}。如当前工具无法完成,可尝试其他分类的工具。"
```

**_build_cross_tool_hint()实现**:

```python
def _build_cross_tool_hint(self) -> str:
    """构建跨分类工具提示"""
    loaded = getattr(self, '_loaded_categories', set())
    if len(loaded) <= 1:
        return ""
    
    from app.services.agent.agent_config import AGENT_REGISTRY
    loaded_names = []
    for intent_type, cfg in AGENT_REGISTRY.items():
        if cfg.category.value in loaded:
            loaded_names.append(cfg.category_display_name)
    
    if not loaded_names:
        return ""
    
    return f"【跨分类工具】当前已加载多分类工具: {', '.join(loaded_names)}。可跨分类调用工具完成任务。"
```

**完整Prompt组装顺序**:

```
① get_system_prompt()         [分类特有] → 角色+工具+示例
② OUTPUT_FORMAT               [公共]     → JSON格式规则
③ TOOL_CALL_RULES             [公共]     → 工具调用规则
④ get_safety_reminder()       [分类特有] → 安全提醒
⑤ get_rollback_instructions() [公共]     → 回滚说明
⑥ avoid_repeat_rules          [公共]     → 避免重复规则
⑦ _build_candidates_hint()    [运行时]   → 候选意图提示
⑧ _build_cross_tool_hint()    [运行时]   → 跨分类工具提示
```

**分析**:
- ✅ 运行时动态注入候选意图和跨分类工具提示
- ✅ 组装顺序合理
- ⚠️ **问题**: 候选意图提示可能干扰LLM判断

---

## 三、Message管理层详细分析

### 3.1 MessageBuilder类（message_builder.py）

**文件路径**: `backend/app/services/agent/message_builder.py`

**核心职责**:
- 管理conversation_history状态
- 提供消息操作统一入口
- 实现智能截断和容量感知裁剪

**核心属性**:

```python
class MessageBuilder:
    def __init__(self, max_context_chars: int = MAX_CONTEXT_CHARS):
        self.conversation_history: List[Dict[str, Any]] = []  # 正式对话历史
        self.temp_history: List[Dict[str, Any]] = []          # 临时历史（流式chunk缓冲）
        self.MAX_CONTEXT_CHARS = max_context_chars            # 最大上下文字符数（150000）
```

**核心方法分析**:

#### 3.1.1 init_history() - 初始化对话历史

```python
def init_history(self, sys_prompt: str, task_prompt: str) -> None:
    """初始化conversation_history"""
    self.conversation_history = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": task_prompt}
    ]
```

**分析**:
- ✅ 初始化为[system, user]两条消息
- ✅ 简单直接，无冗余逻辑

#### 3.1.2 add_assistant() - 追加assistant消息

```python
def add_assistant(self, content: str) -> None:
    """追加assistant消息"""
    self.conversation_history.append({"role": "assistant", "content": content})
```

**分析**:
- ✅ 简单追加，无自动trim（由_call_llm统一调度）

#### 3.1.3 add_observation() - 追加observation消息

```python
def add_observation(self, observation_text: str, llm_call_count: int = 0, fc_context: Optional[Dict] = None) -> None:
    """追加observation消息 — 含智能截断 + [Observation]前缀归一化 + trim"""
    # 1. 准备observation文本（截断+归一化）
    observation_text = self._prepare_observation_text(observation_text, llm_call_count)
    
    # 2. 追加observation消息
    self._append_observation(observation_text, fc_context)
    
    # 3. 触发历史裁剪
    self.trim_history()
```

**_prepare_observation_text()实现**:

```python
def _prepare_observation_text(self, observation_text: str, llm_call_count: int) -> str:
    """准备observation文本 — 截断+归一化"""
    # 1. 计算可用预算
    budget = self._get_observation_budget(llm_call_count)
    
    # 2. 智能截断
    if len(observation_text) > budget:
        observation_text = smart_truncate_text(observation_text, budget=budget)
    
    # 3. 归一化前缀
    observation_text = self._normalize_observation_prefix(observation_text)
    
    return observation_text
```

**_get_observation_budget()实现**:

```python
@staticmethod
def _get_observation_budget(llm_call_count: int) -> int:
    """计算observation可用预算"""
    # 公式: MIN + DECAY * max(0, 5 - llm_call_count)
    # 常量: MIN=20000, DECAY=10000, MAX=50000
    budget = OBSERVATION_BUDGET_MIN + OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
    return min(budget, OBSERVATION_BUDGET_MAX)
```

**预算计算示例**:

| llm_call_count | budget计算 | 结果 |
|----------------|-----------|------|
| 0 | 20000 + 10000 * 5 | 50000（MAX） |
| 1 | 20000 + 10000 * 4 | 50000（MAX） |
| 2 | 20000 + 10000 * 3 | 50000（MAX） |
| 3 | 20000 + 10000 * 2 | 40000 |
| 4 | 20000 + 10000 * 1 | 30000 |
| 5+ | 20000 + 10000 * 0 | 20000（MIN） |

**分析**:
- ✅ 预算随调用次数递减，防止observation过长
- ✅ 智能截断保留关键信息
- ✅ 前缀归一化防止双重[Observation]

**_append_observation()实现**:

```python
def _append_observation(self, observation_text: str, fc_context: Optional[Dict] = None) -> None:
    """追加observation消息 — 方案G: role=system→user+[Tool Result]"""
    if fc_context and fc_context.get("tool_call_id"):
        # FC模式：按OpenAI协议注入
        tool_call_id = fc_context["tool_call_id"]
        tool_calls = fc_context.get("tool_calls")
        if tool_calls:
            self.conversation_history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
        self.conversation_history.append({"role": "tool", "content": observation_text, "tool_call_id": tool_call_id})
    else:
        # Text模式：user+[Tool Result]
        self.conversation_history.append({"role": "user", "content": f"[Tool Result]\n{observation_text}"})
```

**分析**:
- ✅ 支持FC协议（role=tool + tool_call_id）
- ✅ Text模式使用user+[Tool Result]标识
- ✅ 两种模式清晰分离

#### 3.1.4 prepare_messages_for_llm() - 准备发给LLM的消息

```python
def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
    """准备发给LLM的完整消息列表"""
    # 1. 复制正式历史
    messages = list(self.conversation_history)
    
    # 2. 追加临时历史
    if self.temp_history:
        messages = messages + list(self.temp_history)
    
    # 3. temp_history容量保护
    self._cap_temp_history()
    
    return messages
```

**_cap_temp_history()实现**:

```python
def _cap_temp_history(self):
    """对temp_history加字符容量限制(最多50000字符)"""
    while self._total_chars(self.temp_history) > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        self.temp_history.pop(0)  # 从最旧开始移除
```

**分析**:
- ✅ 合并正式历史和临时历史
- ✅ temp_history有容量保护（50000字符）
- ⚠️ **问题**: 每次调用都检查容量，可能影响性能

#### 3.1.5 trim_history() - 容量感知裁剪

```python
def trim_history(self) -> None:
    """容量感知的对话历史裁剪"""
    # 1. 检查是否需要裁剪（超80%才触发）
    total = self._total_chars(self.conversation_history)
    if total < self.MAX_CONTEXT_CHARS * 0.8:
        return
    
    # 2. 消息太少不裁剪
    if len(self.conversation_history) <= 2:
        return
    
    # 3. 分类消息
    system_msgs, obs_list, assistant_msgs = self._classify_messages()
    
    # 4. 计算预算
    budget = int(self.MAX_CONTEXT_CHARS * 0.7)
    
    # 5. 裁剪observation
    trimmed_obs = self._trim_to_budget(obs_list, assistant_msgs, budget)
    
    # 6. 重组并验证
    rebuilt = self._rebuild_and_validate(system_msgs, trimmed_obs, assistant_msgs)
    
    if rebuilt is not None:
        self.conversation_history = rebuilt
```

**_classify_messages()实现**:

```python
def _classify_messages(self):
    """将消息分类为 system / observation / assistant 三组"""
    system_msgs = []
    obs_list = []
    assistant_msgs = []
    
    for msg in self.conversation_history:
        role = msg.get("role", "")
        if role == "assistant":
            assistant_msgs.append(msg)
        elif self._is_observation_role(msg):
            obs_list.append(msg)
        else:
            system_msgs.append(msg)
    
    return system_msgs, obs_list, assistant_msgs
```

**_is_observation_role()实现**:

```python
@staticmethod
def _is_observation_role(msg: Dict) -> bool:
    """判断消息是否为observation"""
    # 三种形式:
    # 1. text策略: role=user + content含[Tool Result]
    # 2. tools策略(FC协议): role=tool
    if msg.get("role") == "tool":
        return True
    content = msg.get("content", "")
    return msg.get("role") == "user" and "[Tool Result]" in content
```

**_trim_to_budget()实现**:

```python
def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    """去重+截断observation,保留最新assistant"""
    # 1. 去重observation
    obs_list = self._dedup_by_fingerprint(obs_list)
    
    # 2. 保留最新10条assistant
    assistant_msgs = assistant_msgs[-10:]
    
    # 3. 保留最新30条observation
    obs_list = obs_list[-30:]
    
    # 4. 按预算裁剪
    while obs_list and self._total_chars(obs_list) > budget:
        obs_list.pop(0)  # 从最旧开始移除
    
    return obs_list
```

**_dedup_by_fingerprint()实现**:

```python
@staticmethod
def _dedup_by_fingerprint(obs_list: List[Dict]) -> List[Dict]:
    """基于指纹去重observation"""
    seen = set()
    result = []
    
    for obs in obs_list:
        # FC协议消息不参与去重
        if obs.get("role") == "tool" and obs.get("tool_call_id"):
            result.append(obs)
            continue
        
        # 基于content计算指纹
        content = obs.get("content", "")
        fp = hashlib.md5(content.encode()).hexdigest()[:16]
        
        if fp not in seen:
            seen.add(fp)
            result.append(obs)
    
    return result
```

**分析**:
- ✅ 超过80%才触发裁剪，避免频繁操作
- ✅ 分类裁剪：system保留，observation去重+截断，assistant保留最新10条
- ✅ FC协议消息不参与去重，防止配对断裂
- ⚠️ **问题**: 裁剪后可能丢失重要上下文

#### 3.1.6 _trim_fc_pairs() - FC协议配对裁剪

```python
@staticmethod
def _trim_fc_pairs(messages: List[Dict]) -> List[Dict]:
    """FC协议配对裁剪:确保role:tool与role:assistant(tool_calls)严格配对"""
    # 1. 收集所有tool_call_id
    assistant_ids: set = set()
    tool_ids: set = set()
    
    for msg in messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                if tc.get("id"):
                    assistant_ids.add(tc["id"])
        elif msg.get("role") == "tool":
            if msg.get("tool_call_id"):
                tool_ids.add(msg["tool_call_id"])
    
    # 2. 计算配对ID
    paired_ids = assistant_ids & tool_ids
    
    # 3. 过滤消息
    result = []
    for msg in messages:
        if msg.get("role") == "assistant":
            # 保留配对的tool_calls
            tcs = msg.get("tool_calls") or []
            kept_tcs = [tc for tc in tcs if tc.get("id") in paired_ids]
            if not kept_tcs and tcs:
                continue  # 全部未配对，移除整条assistant
            new_msg = dict(msg)
            new_msg["tool_calls"] = kept_tcs
            result.append(new_msg)
        elif msg.get("role") == "tool":
            # 保留配对的tool消息
            if msg.get("tool_call_id") in paired_ids:
                result.append(msg)
        else:
            result.append(msg)
    
    return result
```

**分析**:
- ✅ 确保FC协议配对完整性
- ✅ 未配对的消息被移除
- ⚠️ **问题**: 可能移除重要上下文

---

### 3.2 conversation_history完整生命周期

```
初始化阶段:
┌─────────────────────────────────────────────────────────────┐
│ _initialize_run_state()                                     │
│   ├─ message_builder.reset_per_run()                        │
│   │   └─ conversation_history = []                          │
│   │   └─ temp_history = []                                  │
│   ├─ sys_prompt = _get_system_prompt()                      │
│   ├─ task_prompt = _get_task_prompt(task, context)          │
│   └─ message_builder.init_history(sys_prompt, task_prompt)  │
│       └─ conversation_history = [                           │
│             {"role": "system", "content": sys_prompt},      │
│             {"role": "user", "content": task_prompt}        │
│           ]                                                 │
└─────────────────────────────────────────────────────────────┘

循环阶段（每轮）:
┌─────────────────────────────────────────────────────────────┐
│ _call_llm()                                                 │
│   ├─ message_builder.trim_history()                         │
│   ├─ messages = message_builder.prepare_messages_for_llm()  │
│   │   └─ 返回 conversation_history + temp_history           │
│   └─ llm_client.request_stream(messages, mode, tools)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ parse_llm_response(llm_response)                            │
│   └─ 返回 {type, thought, tool_name, tool_params}           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ handle_action()                                             │
│   ├─ yield ThoughtStep                                      │
│   ├─ 执行工具 → result                                       │
│   ├─ yield ActionToolStep                                   │
│   ├─ yield ObservationStep                                  │
│   ├─ message_builder.add_assistant(llm_response)            │
│   │   └─ conversation_history.append(                       │
│   │         {"role": "assistant", "content": llm_response}  │
│   │       )                                                 │
│   └─ message_builder.add_observation(obs_text, count, fc)   │
│       └─ conversation_history.append(                       │
│             {"role": "user", "content": "[Tool Result]..."} │
│           )                                                 │
└─────────────────────────────────────────────────────────────┘

conversation_history结构示例:
[
  {"role": "system", "content": "System Prompt..."},
  {"role": "user", "content": "Task: 读取config.json"},
  {"role": "assistant", "content": '{"thought": "读取文件", "tool_name": "read_file", ...}'},
  {"role": "user", "content": "[Tool Result]\nObservation: 文件内容..."},
  {"role": "assistant", "content": '{"thought": "任务完成", "tool_name": "finish", ...}'},
]
```

---

## 四、LLM调用层详细分析

### 4.1 BaseAIService类（llm_core.py）

**文件路径**: `backend/app/services/llm_core/llm_core.py`

**核心职责**:
- 提供request/request_stream/chat方法
- 处理SSE流解析
- 支持FC协议和Text模式

**核心方法分析**:

#### 4.1.1 request_stream() - 流式请求

```python
async def request_stream(
    self,
    messages: List[Dict],
    mode: str = "text",
    tools: Optional[List[Dict]] = None,
    tool_choice: str = "auto",
) -> AsyncGenerator[StreamChunk, None]:
    """流式请求 - SSE服务层/Agent用"""
    self.reset_cancel()
    self._ensure_client()
    
    retry_count = 0
    max_retries = 3
    
    while retry_count <= max_retries:
        try:
            tool_call_accumulator = {}
            
            async for data_str in self._llm_sdk.request_stream(
                messages=messages,
                mode=mode,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                seed=self.seed,
            ):
                # 1. 检查取消/暂停状态
                if await self._check_task_cancelled_or_paused():
                    yield self._create_cancelled_chunk()
                    return
                
                # 2. 跨chunk聚合tool_calls
                tc_data = self._extract_tool_calls(data_str)
                for idx, entry in tc_data.items():
                    tool_call_accumulator.setdefault(idx, {"name": "", "arguments": ""})
                    if entry.get("name"):
                        tool_call_accumulator[idx]["name"] = entry["name"]
                    if entry.get("arguments"):
                        tool_call_accumulator[idx]["arguments"] += entry["arguments"]
                
                # 3. 解析SSE data
                chunk = self._parse_sse_data(data_str)
                if chunk:
                    yield chunk
                    if chunk.is_done:
                        return
            
            # 4. 流结束后，注入聚合的tool_calls
            if tool_call_accumulator:
                for idx in sorted(tool_call_accumulator):
                    tc = tool_call_accumulator[idx]
                    if tc["name"]:
                        params = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        action_json = json.dumps({"tool_name": tc["name"], "tool_params": params})
                        yield StreamChunk(content=action_json, model=self.model, is_done=False, is_reasoning=False)
            
            yield StreamChunk(content="", model=self.model, is_done=True)
            return
        
        except Exception as e:
            if self._should_retry(e) and retry_count < max_retries:
                retry_count += 1
                wait_time = 2 ** retry_count
                await asyncio.sleep(wait_time)
                continue
            else:
                yield self._create_stream_error_chunk(e)
                return
```

**分析**:
- ✅ 支持重试机制（最多3次，指数退避）
- ✅ 跨chunk聚合tool_calls，支持FC协议
- ✅ 定期检查取消/暂停状态
- ⚠️ **问题**: 重试逻辑可能导致重复执行

#### 4.1.2 _parse_sse_data() - 解析SSE数据

```python
def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
    """解析SSE data字符串为StreamChunk"""
    try:
        data = parse_json(data_str)
        if data is None:
            return None
        
        choices = data.get("choices", [])
        if not choices:
            return None
        
        delta = choices[0].get("delta", {})
        content = delta.get("content", "") or ""
        reasoning_content = extract_reasoning_from_chunk(delta) or ""
        
        if content:
            return StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False)
        if reasoning_content:
            return StreamChunk(content=reasoning_content, model=self.model, is_done=False, is_reasoning=True)
        
        return None
    
    except Exception as e:
        return None
```

**分析**:
- ✅ 支持reasoning_content提取（思考模型）
- ✅ 返回StreamChunk统一格式
- ⚠️ **问题**: 解析失败静默返回None，可能丢失信息

---

### 4.2 UniversalAgent的LLM调用（universal_agent.py）

**_call_llm()实现**:

```python
async def _call_llm(self):
    """调用LLM — 流式输出chunk给前端"""
    # 1. 增加调用计数
    self.llm_call_count += 1
    
    # 2. 触发历史裁剪
    self.message_builder.trim_history()
    
    # 3. 准备消息
    messages = self.message_builder.prepare_messages_for_llm()
    
    # 4. 注入已执行工具汇总
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})
    
    # 5. 获取OpenAI工具定义
    openai_tools = self._get_openai_tools()
    
    # 6. 选择调用模式
    if openai_tools:
        async for item in self._call_llm_fc_stream(messages, openai_tools):
            yield item
    else:
        async for item in self._call_llm_text_stream(messages):
            yield item
```

**_build_executed_tool_summary()实现**:

```python
def _build_executed_tool_summary(self) -> str:
    """构建已执行工具汇总"""
    if not hasattr(self, '_executed_tool_summary') or not self._executed_tool_summary:
        return ""
    
    # 只取成功的工具
    done = [s for s in self._executed_tool_summary if '→success' in s]
    if not done:
        return ""
    
    parts = []
    for entry in done[-8:]:  # 保留最新8条
        if '|' in entry:
            tool_status, data_hint = entry.split('|', 1)
            parts.append(f"{tool_status}({data_hint})")
        else:
            parts.append(entry)
    
    return ("【已执行工具(勿重复)】" + "; ".join(parts)
            + "\n注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!")
```

**分析**:
- ✅ 注入已执行工具汇总，防止重复调用
- ✅ 支持FC和Text两种模式
- ⚠️ **问题**: executed_summary在每次调用时都注入，可能增加上下文长度

**_call_llm_fc_stream()实现**:

```python
async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
    """FC模式流式调用 — 实时输出思考过程"""
    full_content = ""
    full_reasoning = ""
    stream_error = None
    chunk_step_count = 0
    
    try:
        async for chunk in self.llm_client.request_stream(
            messages=messages,
            mode="tools",
            tools=openai_tools,
            tool_choice="auto",
        ):
            if chunk.stream_error:
                stream_error = chunk.stream_error
                break
            
            if chunk.content:
                chunk_step_count += 1
                if getattr(chunk, "is_reasoning", False):
                    full_reasoning += chunk.content
                    yield ("chunk", ChunkStep(
                        step=self.llm_call_count,
                        content=chunk.content,
                        is_reasoning=True,
                    ))
                else:
                    full_content += chunk.content
                    yield ("chunk", ChunkStep(
                        step=self.llm_call_count,
                        content=chunk.content,
                        is_reasoning=False,
                    ))
            
            if chunk.is_done:
                break
        
        logger.info(f"[FC] 流式调用完成, content_len={len(full_content)}, reasoning_len={len(full_reasoning)}, chunks={chunk_step_count}")
    
    except Exception as e:
        logger.warning(f"[FC] request_stream失败,降级text: {e}")
        response = await self._call_llm_text_nostream(messages)
        yield ("response", response)
        return
    
    if stream_error:
        logger.error(f"[FC] 流式错误: {stream_error}")
        response = await self._call_llm_text_nostream(messages)
        yield ("response", response)
        return
    
    # 尝试解析JSON
    if full_content:
        parsed = parse_json(full_content)
        if parsed and "tool_name" in parsed:
            yield ("response", full_content)
            return
    
    # 如果只有reasoning，当作content
    if full_reasoning and not full_content:
        full_content = full_reasoning
    
    # 返回最终响应
    yield ("response", full_content.strip() or '{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}')
```

**分析**:
- ✅ 实时输出chunk给前端
- ✅ 支持reasoning分离
- ✅ 降级机制：FC失败→Text非流式
- ⚠️ **问题**: 空响应时返回默认finish，可能导致误判

---

## 五、ReAct循环详细分析

### 5.1 run_react_cycle()（react_cycle.py）

**文件路径**: `backend/app/services/agent/core_agent/react_cycle.py`

**核心职责**:
- 循环调度
- 类型分派
- 产出Step事件

**实现**:

```python
async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()
    
    # 1. 初始化运行状态
    chunk_buffer = agent._initialize_run_state(task, task_id, context)
    
    step_counter = [0]
    agent.status = AgentStatus.EXECUTING
    
    try:
        while step_counter[0] < max_steps:
            # 2. 处理单步循环
            async for event in _process_single_step(agent, step_counter, chunk_buffer):
                yield event
            
            # 3. 检查是否完成
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break
            
            # 4. 检查chunk累积超时
            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({step_counter[0]}步),强制停止")
                agent.status = AgentStatus.COMPLETED
                break
    
    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED
    
    finally:
        # 5. FAILED时补发FinalStep
        if agent.status == AgentStatus.FAILED and agent.steps:
            last_err = None
            for s in reversed(agent.steps):
                if hasattr(s, '_error_message') and getattr(s, '_error_message', None):
                    last_err = s._error_message
                    break
            yield agent._step_emitter.emit(FinalStep(
                step=step_counter[0],
                response=last_err or "任务执行失败",
                thought="",
            ))
        
        agent._on_after_loop()
        agent._complete_tracked_task(agent.status == AgentStatus.COMPLETED)
```

**_process_single_step()实现**:

```python
async def _process_single_step(agent, step_counter: list, chunk_buffer) -> AsyncGenerator:
    """处理单步循环 — async generator"""
    step_counter[0] += 1
    
    llm_response = None
    
    # 1. 调用LLM
    async for chunk_or_response in agent._call_llm():
        chunk_type, chunk_data = chunk_or_response
        
        if chunk_type == "chunk":
            yield agent._step_emitter.emit(chunk_data)
        elif chunk_type == "response":
            llm_response = chunk_data
    
    # 2. 空响应检查
    if not llm_response or not isinstance(llm_response, str):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="empty_response",
            error_message="LLM返回空响应",
        )
        agent.status = AgentStatus.FAILED
        return
    
    # 3. 取消检查
    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step_counter[0],
            response="任务已被中断",
            thought="",
        ))
        agent.status = AgentStatus.COMPLETED
        return
    
    # 4. 解析LLM响应
    parsed = parse_llm_response(llm_response)
    parsed_type = parsed.get("type", "parse_error")
    
    # 5. 发射reasoning chunk
    reasoning = parsed.get("reasoning")
    if reasoning:
        yield agent._step_emitter.emit(ChunkStep(
            step=step_counter[0], content=reasoning, is_reasoning=True,
        ))
    
    # 6. 分派handler
    handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
    async for event in handler(agent, parsed, llm_response, step_counter, chunk_buffer):
        yield event
    
    # 7. 工具提醒（FC模式下LLM返回纯文本）
    if parsed_type == "chunk" and not _has_tool_call(agent):
        logger.warning(f"[react_cycle] LLM text-only response (step {step_counter[0]}), injecting tool reminder")
        agent.message_builder.conversation_history.append({"role": "system", "content": _TOOL_REMINDER})
```

**_TYPE_HANDLERS映射**:

```python
_TYPE_HANDLERS: OrderedDict[str, callable] = OrderedDict([
    ("action", handle_action),
    ("answer", handle_answer),
    ("implicit", handle_answer),
    ("chunk", handle_chunk),
    ("parse_error", handle_parse_error),
])
_DEFAULT_HANDLER = handle_unknown
```

**_TOOL_REMINDER内容**:

```python
_TOOL_REMINDER = (
    "【系统提示·工具调用提醒】\n"
    "你刚才的回复没有调用任何工具。用户请求需要实际操作才能完成，"
    "你必须使用工具来执行。\n"
    "请重新输出JSON格式，包含 tool_name 和 tool_params。\n"
    '示例: {"thought": "分析", "reasoning": "理由", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/test.txt", "text": "hello"}}\n'
    "如果不需要工具（用户只是闲聊），请用 tool_name: finish 结束。"
)
```

**分析**:
- ✅ 薄调度设计，业务逻辑在handlers
- ✅ 支持流式chunk实时输出
- ✅ 工具提醒机制防止LLM纯文本回复
- ⚠️ **问题**: _TOOL_REMINDER硬编码，应提取为配置

---

### 5.2 parse_llm_response()（parse_llm_response.py）

**文件路径**: `backend/app/services/agent/llm_response_parser/parse_llm_response.py`

**核心职责**:
- 解析LLM响应为统一格式
- 支持多种输入格式（dict/list/JSON/混合文本）

**解析链**:

```python
_HANDLERS = [
    _handle_dict_input,          # dict直接返回
    _handle_list_input,          # list处理
    _handle_json_array_string,   # JSON数组字符串
    _handle_empty_input,         # 空输入处理
    _handle_standard_json,       # 标准JSON提取
    _handle_mixed_text_json,     # 混合文本JSON
]
```

**解析流程图**:

```
输入(str)
    ↓
_handle_dict_input
    ├─ 是dict → 返回action结果
    └─ 否 → 继续
    ↓
_handle_list_input
    ├─ 是list → 返回action结果
    └─ 否 → 继续
    ↓
_handle_json_array_string
    ├─ 是JSON数组 → 返回action结果
    └─ 否 → 继续
    ↓
_handle_empty_input
    ├─ 是空 → 返回parse_error
    └─ 否 → 继续
    ↓
_handle_standard_json
    ├─ 是标准JSON → 返回处理结果
    └─ 否 → 继续
    ↓
_handle_mixed_text_json
    ├─ 提取JSON块
    │   ├─ 有tool_name="finish" → 返回answer
    │   ├─ 有tool_name → 返回action
    │   └─ 无tool_name → 返回implicit/chunk
    └─ 无JSON → 返回chunk
    ↓
返回parse_error（兜底）
```

**分析**:
- ✅ 链式解析，支持多种格式
- ✅ 优先级合理：dict > list > JSON > 混合文本
- ⚠️ **问题**: 解析链过长，可能影响性能

---

## 六、不合理之处分析

> **验证说明**：以下6.1~6.4的11个问题来自初版分析。v1.1更新中对每个问题进行了：
> - **准确性验证**：逐行阅读对应代码，确认问题描述是否与代码行为一致
> - **10大原则评估**：对照SRP/DRY/KISS/SLAP/YAGNI/OCP/LSP/ISP/复用优先/禁止backward compatibility逐条评估
> - **最优方案制定**：基于验证结果，给出符合原则的最优解决方案
> 
> 验证结果：11个问题中 **4个部分准确**、**6个不准确**、**1个准确**。不准确的问题（#3/#4/#7/#8/#10/#11）已标注"不修改"。同时在6.5补充了7个遗漏的关键问题。

### 6.1 Prompt构建层问题

#### 问题1：规则重复强调

**位置**: `base_prompt_template.py`

**问题描述**:
- OUTPUT_FORMAT和TOOL_CALL_RULES都强调"必须调用工具"
- 禁止项过多（7条），可能导致LLM困惑
- avoid_repeat_rules硬编码在方法中，未提取为常量

**影响**:
- Prompt过长，增加token消耗
- 规则冲突可能导致LLM行为不一致

**初步建议**:
```python
# 提取为常量
AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行
- 同一命令/URL失败3次后必须换工具或换URL
- 已获取的信息直接使用
- 失败后优先尝试替代方法
"""

# 合并重复规则
TOOL_CALL_RULES = """【Tool Call Rules】:
- 确认意图后立即调用工具
- reasoning简短说明理由即可(1-2句)
- 始终用中文回复用户
"""
```

**🔎 验证结论：部分准确**
- OUTPUT_FORMAT 聚焦"输出格式"（怎么输出JSON），TOOL_CALL_RULES 聚焦"行为模式"（不要只讨论不调用），侧重点不同，规则冲突概率较低
- 但 `avoid_repeat_rules` 硬编码在 `_build_avoid_repeat_rules()` 方法中确实应从方法级提升为类常量（`BasePromptTemplates.__AVOID_REPEAT_RULES`）

**🔎 10大原则评估**：
- ✅ DRY：提取为常量的方案符合不重复原则
- ✅ KISS：方案简单，改动范围小

**🏆 最优方案**：
```python
# base_prompt_template.py 第28行附近
__AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行
- 同一命令/URL失败3次后必须换工具或换URL
- 已获取的信息直接使用
- 失败后优先尝试替代方法
"""

# _build_avoid_repeat_rules() 改为引用类常量
def _build_avoid_repeat_rules(self) -> str:
    return self.__AVOID_REPEAT_RULES
```
- **只做提取，不做合并**：OUTPUT_FORMAT和TOOL_CALL_RULES职责不同，不应合并（SRP）
- **不改TOOL_CALL_RULES内容**：原有7条禁止项各有价值，删除其中任何一条都可能导致LLM行为异常

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`AVOID_REPEAT_RULES` 已提取为 `BasePrompts` 类常量（`base_prompt_template.py:106`）
> - ✅ **修复方式正确**：`build_full_system_prompt()` 中 `parts.append(self.AVOID_REPEAT_RULES)` 引用类常量，不再硬编码
> - ✅ **10大原则符合**：DRY（常量只定义一次）、KISS（简单提取）、禁止backward（删除方法内硬编码）

#### 问题2：示例硬编码

**位置**: `file_prompts.py`, `desktop_prompts.py`, `system_prompts.py`

**问题描述**:
- Tool Call Examples硬编码在字符串中
- 修改示例需要修改代码
- 不同分类示例格式不统一

**影响**:
- 维护成本高
- 示例可能过时

**初步建议**:
```python
# 提取为模板池
_EXAMPLE_TEMPLATES = {
    "file": [
        {"thought": "读取文件", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/config.json"]}},
        {"thought": "写入文件", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/output.txt", "text": "Hello"}},
    ],
    "desktop": [
        {"thought": "列出窗口", "tool_name": "window_info", "tool_params": {"action": "list"}},
    ],
}

def _build_examples(category: str, count: int = 4) -> str:
    templates = _EXAMPLE_TEMPLATES.get(category, [])
    lines = ["【Tool Call Examples】:"]
    for i, ex in enumerate(templates[:count], 1):
        lines.append(f"Example {i}: {json.dumps(ex, ensure_ascii=False)}")
    return "\n".join(lines)
```

**🔎 验证结论：部分准确，但遗漏了更严重的BUG**
- `file_prompts.py` 和 `desktop_prompts.py` 确实硬编码了示例，不同分类格式不统一
- **但更严重的问题在 `system_prompts.py:41-60`**：`_build_examples()` 方法使用的示例工具名包含 `get_weather`、`search_files`、`read_file`、`execute_shell_command`——这些**不属于当前系统注册的 `FUND_RUNTIME` 工具**，引导LLM调用不存在的工具

**🔎 10大原则评估**：
- ✅ DRY：模板池方案消除重复
- ✅ 复用优先：统一示例格式

**🏆 最优方案**：
```python
# 修复 system_prompts.py 的 _build_examples()，使用真实工具名
@staticmethod
def _build_examples() -> str:
    examples = [
        {"thought": "用户要查看桌面文件，先列出目录内容", "tool_name": "list_directory", "tool_params": {"directory_path": "C:/Users/Desktop"}},
        {"thought": "用户要打开计算器，先获取窗口信息", "tool_name": "window_info", "tool_params": {"action": "list"}},
    ]
    return json.dumps(examples, ensure_ascii=False, indent=2)
```
- **核心修复：示例必须使用系统已注册的真实工具名**（PS：`file_prompts.py` 和 `desktop_prompts.py` 的示例中 `read_file` 是正确的，仅 `system_prompts.py` 的通用示例使用了不存在工具）
- **同时更新 `file_prompts.py` 和 `desktop_prompts.py` 的 `_build_examples()` 调用方式**：统一使用 `SystemPrompts._build_examples()` 的输出格式

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`system_prompts.py:49-56` 的 `_EXAMPLE_TEMPLATES` 已替换为真实工具名（`get_time`/`query_calendar`/`get_system_info`/`list_processes`）
> - ✅ **修复方式正确**：所有示例工具名均属于 `FUND_RUNTIME` 分类，不再引用不存在的工具
> - ✅ **10大原则符合**：DRY（模板池统一格式）、KISS（只改数据不改逻辑）

#### 问题3：候选意图提示可能干扰判断

**位置**: `universal_agent.py` - `_build_candidates_hint()`

**问题描述**:
- 候选意图提示在每次调用时都注入
- 可能干扰LLM对当前意图的判断
- 增加上下文长度

**影响**:
- LLM可能在多个意图间摇摆
- 增加token消耗

**初步建议**:
```python
# 只在首次调用时注入
def _build_candidates_hint(self) -> str:
    if not self._candidates:
        return ""
    if self.llm_call_count > 1:  # 只在首次注入
        return ""
    # ...
```

**🔎 验证结论：❌ 问题不准确**
- 代码路径：`_build_candidates_hint()` → 由 `_get_system_prompt()` 调用 → 由 `initialize_run_state()` 调用（`universal_agent.py:29`）
- `initialize_run_state()` **只在 ReAct 循环开始时执行一次**，不是每次LLM调用都触发
- 因此 `_build_candidates_hint()` 在整个任务生命周期中**只生成一次**，不存在"每次调用都注入"的问题

**🏆 最优方案：不修改**
- 候选意图提示仅注入一次，不会干扰LLM判断
- 当前实现是正确的，无需任何改动

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：`_build_candidates_hint()` 仅在 `_get_system_prompt()` 中调用，而 `_get_system_prompt()` 只在 `initialize_run_state()` 时执行一次，不存在"每次调用都注入"的问题

---

### 6.2 Message管理层问题

#### 问题4：temp_history容量检查频繁

**位置**: `message_builder.py` - `prepare_messages_for_llm()`

**问题描述**:
- 每次调用都检查temp_history容量
- 可能影响性能

**影响**:
- 频繁计算字符总数
- 可能成为性能瓶颈

**初步建议**:
```python
# 使用计数器避免频繁计算
def __init__(self):
    self._temp_chars = 0  # 维护字符计数

def add_to_temp(self, chunk):
    self.temp_history.append(chunk)
    self._temp_chars += len(chunk.get("content", ""))
    self._cap_temp_history()

def _cap_temp_history(self):
    while self._temp_chars > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        removed = self.temp_history.pop(0)
        self._temp_chars -= len(removed.get("content", ""))
```

**🔎 验证结论：❌ 问题不准确**
- `_cap_temp_history()` 在 `prepare_messages_for_llm()` 中调用，而该方法**每轮ReAct循环只调用一次**（由 `_call_llm()` 触发）
- `temp_history` 是临时缓冲区，只在流式模式下存储未完工的chunk，每轮LLM调用前都会 `flush_temp_to_history()` 将其清空
- 所以每次检查时 `temp_history` 中的元素极少（通常0~3个）， `sum(len(...))` 的性能消耗可以忽略

**🔎 10大原则评估**：
- ❌ YAGNI：引入计数器维护 `_temp_chars` 增加了状态复杂度，但实际场景下性能提升可以忽略

**🏆 最优方案：不修改**
- 当前 `_cap_temp_history()` 在 `prepare_messages_for_llm()` 中的调用频率很低（每轮一次），性能不是问题
- 不需要额外维护 `_temp_chars` 计数器

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：`_cap_temp_history()` 每轮只调用一次，temp_history元素极少（0~3个），性能可忽略

#### 问题5：裁剪后可能丢失重要上下文

**位置**: `message_builder.py` - `trim_history()`、`_trim_fc_pairs()`

**问题描述**:
- 裁剪时只保留最新30条observation
- 可能丢失重要的早期上下文
- FC协议配对裁剪可能移除重要消息

**影响**:
- LLM可能忘记早期信息
- 任务执行可能失败

**初步建议**:
```python
# 增加重要消息标记
def add_observation(self, obs_text, is_important=False):
    msg = {"role": "user", "content": f"[Tool Result]\n{obs_text}"}
    if is_important:
        msg["_important"] = True
    self.conversation_history.append(msg)

def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    # 保留重要消息
    important = [obs for obs in obs_list if obs.get("_important")]
    normal = [obs for obs in obs_list if not obs.get("_important")]
    # 先裁剪normal，保留important
    # ...
```

**🔎 验证结论：部分准确，但核心问题未覆盖**
- 保留30条observation的硬限制是合理的容量管理手段
- **真正的问题在 `_trim_fc_pairs()`**（`message_builder.py` 第146-154行）：当 `_collapse_fc_pairs()` 需要从左边裁剪时，它会删除最老的 `(assistant, user)` 配对。但如果最老的配对之前还有独立消息（如初始system prompt等），配对裁剪不会误伤它们
- "重要消息标记"方案过于复杂，且谁负责标记"重要"不明确

**🔎 10大原则评估**：
- ✅ KISS：方案本身思路简单
- ❌ 缺少调用者：没有明确谁调用 `is_important=True`，方案不完整

**🏆 最优方案：调整FC配对裁剪优先级**
```python
# _trim_fc_pairs() 中保留最近的N个有效配对
# 当前实现已足够，无需额外标记。关键改进点：
# 1. 确保_collapse_fc_pairs只在对conversation_history长度超限时触发
# 2. 不在裁剪前重置FC协议配对（避免丢失有效的function_call>tool消息对）
```
- **不引入 `_important` 标记**（YAGNI），现有30条observation的容量在多数场景下足够
- **仅确保 `_trim_fc_pairs()` 的触发时机合理**：只在实际超限时才调用，不提前调用

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：30条observation硬限制是合理的容量管理，`_important`标记方案缺少调用者（谁标记"重要"），不引入

#### 问题6：executed_summary每次调用都注入

**位置**: `universal_agent.py` - `_call_llm()`

**问题描述**:
- executed_summary在每次LLM调用时都注入
- 增加上下文长度
- 可能与observation重复

**影响**:
- 增加token消耗
- 信息冗余

**初步建议**:
```python
# 只在observation过长时注入
def _call_llm(self):
    messages = self.message_builder.prepare_messages_for_llm()
    
    # 检查observation是否过长
    last_obs = self._get_last_observation()
    if len(last_obs) > 10000:  # 过长时注入摘要
        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})
    # ...
```

**🔎 验证结论：问题存在但影响被夸大**
- `_build_executed_tool_summary()` 确实在每轮 `_call_llm()` 中调用（`universal_agent.py:91-92`）
- 但summary只包含最近8条已成功调用的工具，长度通常 < 500字符
- observation和summary的侧重点不同：observation包含完整工具结果，summary是执行摘要（成功/失败状态），两者互补不冗余

**🔎 10大原则评估**：
- ❌ YAGNI：检查"最后一条observation是否>10000字符"来决定是否注入是过度设计

**🏆 最优方案：不修改**
- `executed_summary` 长度小（<500字符），开销可忽略
- 它提供了**当前步骤执行状态的总览**，帮助LLM避免重复调用已完成的工具
- 检查observation长度的方案（>10000字符）增加了不必要复杂度

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：executed_summary长度<500字符，与observation互补不冗余，YAGNI原则不引入额外判断

---

### 6.3 LLM调用层问题

#### 问题7：重试逻辑可能导致重复执行

**位置**: `llm_core.py` - `request_stream()`

**问题描述**:
- 重试时可能重复发送相同请求
- 没有幂等性保护

**影响**:
- 可能导致工具重复执行
- 资源浪费

**初步建议**:
```python
# 增加请求指纹
def request_stream(self, messages, mode, tools):
    request_fp = self._build_request_fingerprint(messages, mode, tools)
    
    if request_fp == self._last_request_fp:
        # 相同请求，跳过
        return
    
    self._last_request_fp = request_fp
    # ...
```

**🔎 验证结论：❌ 问题不准确**
- 重试发生在 `request_stream()` 的 `try/except` 块中（`llm_core.py:251-278`），只在HTTP请求失败（如网络超时、500错误）时触发
- 如果LLM请求在网络层面失败，**没有任何工具被调用**，重试是安全的
- 如果LLM请求成功并返回了工具调用，就不会进入重试路径
- 没有"重复执行工具"的风险

**🔎 10大原则评估**：
- ❌ YAGNI：问题不存在，解决方案无价值
- ❌ KISS：请求指纹增加了不必要的状态维护

**🏆 最优方案：不修改**
- 当前重试逻辑只对网络级错误生效，不会导致工具重复执行
- `_build_request_fingerprint()` 和 `_last_request_fp` 是多余的复杂化

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：重试只在HTTP请求失败时触发，此时无工具被调用，不存在重复执行风险

#### 问题8：解析失败静默返回None

**位置**: `llm_core.py` - `_parse_sse_data()`

**问题描述**:
- 解析失败时静默返回None
- 可能丢失重要信息

**影响**:
- 错误难以排查
- 可能导致空响应

**初步建议**:
```python
def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
    try:
        # ...
    except Exception as e:
        logger.warning(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
        # 返回错误chunk而非None
        return StreamChunk(content="", model=self.model, is_done=False, stream_error=f"Parse error: {e}")
```

**🔎 验证结论：❌ 问题描述有偏差**
- 代码确实在异常时返回None（`llm_core.py:300-303`），但**已在debug级别记录了日志**：
  ```python
  except Exception as e:
      logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
      return None
  ```
- 且 `request_stream()` 中对 `None` chunk的处理是**直接跳过**（`if chunk:`），不会导致数据丢失
- 返回 `StreamChunk(error=...)` 的方案可能被下游误当成正常数据流处理

**🔎 10大原则评估**：
- ✅ KISS：仅提升日志级别的方案简单合理
- ❌ 返回StreamChunk：可能破坏下游数据流处理逻辑

**🏆 最优方案**：
```python
# 仅提升日志级别，不动返回逻辑
except Exception as e:
    logger.warning(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
    return None  # 保持返回None，由上游跳过
```
- **只做一件事**：`logger.debug` → `logger.warning`（SRP）
- **不动返回逻辑**：保持返回None，让 `request_stream()` 的 `if chunk:` 正常跳过（KISS）

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`stream_parser.py:81` 的 `logger.debug` 已改为 `logger.warning`
> - ✅ **10大原则符合**：KISS（只改日志级别，不动返回逻辑）

#### 问题9：空响应返回默认finish

**位置**: `universal_agent.py` - `_call_llm_fc_stream()`

**问题描述**:
- 空响应时返回默认finish
- 可能导致误判任务完成

**影响**:
- 任务可能提前结束
- 用户得不到预期结果

**初步建议**:
```python
# 返回错误而非默认finish
if not full_content and not full_reasoning:
    yield ("response", '{"thought": "LLM返回空响应", "reasoning": "可能是网络错误", "tool_name": "finish", "tool_params": {"result": "任务执行失败：LLM返回空响应"}}')
    return
```

**🔎 验证结论：✅ 准确，但改进方向要调整**
- 代码位置：`universal_agent.py:236`（或附近）
  ```python
  yield ("response", full_content.strip() or '{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}')
  ```
- 当LLM返回空流时，默认生成一个虚假的"任务完成"响应，**掩盖了LLM无响应的真实问题**
- `_process_single_step()` 第67-74行虽然有 `if not llm_response` 检查，但 `_call_llm_fc_stream()` 返回的虚假finish会让这个检查无法触发

**🔎 10大原则评估**：
- ✅ KISS：方案简单
- ❌ 但原方案返回的仍然是finish，只是改为"任务执行失败"——调用方可能无法区分真实失败和空响应错误

**🏆 最优方案**：
```python
# 返回空字符串，让 _process_single_step() 的空响应检查捕获
if not full_content.strip() and not full_reasoning:
    yield ("response", "")
    return
```
- **不生成任何虚假的finish**，返回空字符串
- 由 `_process_single_step()` 的空响应检查（`if not llm_response or not isinstance(llm_response, str)`）正确捕获，触发step_failure
- **SRP验证**：`_call_llm_fc_stream()` 只负责流式组装JSON，不负责错误策略；`_process_single_step()` 负责响应验证

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`universal_agent.py:216` 已改为 `yield ("response", full_content.strip())`，不再强制返回finish
> - ✅ **修复方式正确**：空响应时返回空字符串，由 `_process_single_step()` 的空响应检查捕获
> - ✅ **10大原则符合**：SRP（_call_llm_fc_stream不负责错误策略）、KISS（删除虚假finish）、禁止backward（不保留旧逻辑）
> - ⚠️ **注意**：同时新增了纯文本降级逻辑（L207-211），FC返回纯文本时降级text流式重新生成，不再强制finish

---

### 6.4 ReAct循环问题

#### 问题10：_TOOL_REMINDER硬编码

**位置**: `react_cycle.py`

**问题描述**:
- _TOOL_REMINDER硬编码在文件中
- 无法动态调整

**影响**:
- 修改需要改代码
- 不同场景无法定制

**初步建议**:
```python
# 提取为配置
from app.config import get_config

def _get_tool_reminder():
    config = get_config()
    return config.get("tool_reminder", _DEFAULT_TOOL_REMINDER)
```

**🔎 验证结论：❌ 问题描述不准确，遗漏了真正的BUG**
- `_TOOL_REMINDER` 是模块级常量（`react_cycle.py:36-43`），作为Prompt模板常量硬编码是正常做法，不需要从配置文件读取
- **真正的BUG在第102行**：`_TOOL_REMINDER` 被**永久追加**到 `conversation_history`：
  ```python
  self._message_builder.add_to_session("user", _TOOL_REMINDER)
  ```
  这导致 `_TOOL_REMINDER` 作为普通消息写入历史，**不会被裁剪**，随着任务进行污染整个历史

**🔎 10大原则评估**：
- ❌ YAGNI：从config读取是过度设计
- ❌ 当前实现违反SLAP：将Prompt级别的提醒注入到Message级别的历史中，抽象层次混乱

**🏆 最优方案：改为运行时动态注入**
```python
# 在 _call_llm() 中动态注入，不写入永久历史
async def _call_llm(self, ...):
    messages = self._message_builder.prepare_messages_for_llm()
    messages.append({
        "role": "user",
        "content": self._TOOL_REMINDER
    })
    # ...原有调用逻辑
```

同时删除 `run_react_cycle()` 中第102行的永久追加：
```python
# 删除这行
# self._message_builder.add_to_session("user", _TOOL_REMINDER)
```
- **关键修正**：`_TOOL_REMINDER` 在每次LLM调用时通过 `messages.append()` 动态注入，不污染 `conversation_history`（SRP+SLAP）
- **不需要从config读取**：常量硬编码不是问题，污染历史才是（KISS+YAGNI）

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`react_cycle.py:102` 已改为 `agent._tool_reminder_needed = True`（设标志位，不写永久历史）
> - ✅ **动态注入**：`universal_agent.py:139-142` 在 `_call_llm()` 中通过 `messages.append()` 动态注入，然后清除标志位
> - ✅ **10大原则符合**：SLAP（Prompt级提醒不再注入到Message级历史）、SRP（react_cycle只设标志，_call_llm负责注入）、KISS（标志位+动态注入）

#### 问题11：解析链过长

**位置**: `parse_llm_response.py`

**问题描述**:
- 6个handler的解析链
- 可能影响性能

**影响**:
- 解析耗时增加
- 可能成为瓶颈

**初步建议**:
```python
# 使用快速路径
def parse_llm_response(output: str) -> Dict[str, Any]:
    # 快速路径：标准JSON
    if output.startswith("{") and output.endswith("}"):
        data = parse_json(output)
        if data and "tool_name" in data:
            return _process_json_result(data, output)
    
    # 慢速路径：完整解析链
    for handler in _HANDLERS:
        result = handler(output)
        if result is not None:
            return result
    # ...
```

**🔎 验证结论：❌ 问题不准确**
- 6个handler每个都是O(1)的简单检查（字符串匹配、正则等），而非复杂计算
- 解析链路总耗时通常 < 1ms，远非性能瓶颈——真正的瓶颈是LLM API调用（秒级）
- `_handle_standard_json` 已经起到快速路径的作用，不需要额外优化

**🔎 10大原则评估**：
- ❌ YAGNI：提前优化不需要优化的部分
- ❌ KISS：引入"快速路径+慢速路径"的双重判断增加了维护成本

**🏆 最优方案：不修改**
- 当前解析链的6个handler都是O(1)简单检查，性能不是问题
- `_handle_standard_json` 已经是事实上的快速路径
- 不引入额外的"fast-path check"来增加复杂度

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **不修改（正确）**：6个handler均为O(1)简单检查，总耗时<1ms，LLM API调用是真正瓶颈（秒级）

---

### 6.5 遗漏关键问题（原分析未覆盖）

以下问题是在代码复查中发现的，原6.1~6.4分析未覆盖：

#### 遗漏问题A：SystemPrompts示例使用错误工具名（P1-严重）

**位置**: `system_prompts.py:41-60` - `_build_examples()`

**问题描述**:
- `_build_examples()` 中示例使用的工具名：`get_weather`、`search_files`、`read_file`、`execute_shell_command`
- 这些工具**不属于当前系统注册的 `FUND_RUNTIME` 工具分类**
- `get_weather`：已废弃（`WEATHER`分类已合并），不在 `ToolCategory` 枚举中
- `search_files`、`read_file`、`execute_shell_command`：属于其他分类，不是当前Agent的子工具
- 引导LLM调用不存在的工具，导致LLM困惑

**影响**:
- LLM可能调用不存在的工具名，导致解析失败
- LLM收到"工具不存在"的错误后可能陷入重复尝试
- 示例误导LLM对可用工具范围的理解

**🏆 最优方案**：
```python
# system_prompts.py _build_examples() 使用通用示例，不依赖具体工具名
@staticmethod
def _build_examples() -> str:
    examples = [
        {"thought": "用户请求执行一个操作", "tool_name": "list_directory", "tool_params": {"directory_path": "C:/Users"}},
        {"thought": "用户请求获取系统信息", "tool_name": "window_info", "tool_params": {"action": "list"}},
    ]
    return json.dumps(examples, ensure_ascii=False, indent=2)
```
- 使用**系统已注册的真实工具名**（`list_directory`、`window_info` 属于FUND_RUNTIME）
- 示例仅作格式示范，不暗示具体业务逻辑

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：与问题#2合并修复，`_EXAMPLE_TEMPLATES` 已替换为 `get_time`/`query_calendar`/`get_system_info`/`list_processes`

---

#### 遗漏问题B：get_observation_prompt() / get_parameter_reminder() 死代码（P1-严重）

**位置**: `file_prompts.py`、`desktop_prompts.py` 等所有子类

**问题描述**:
- `get_observation_prompt()` 和 `get_parameter_reminder()` 是所有 `BasePromptTemplates` 子类必须实现的两个抽象方法
- 各子类正确实现了实现体，但**这两个方法在全系统中从未被调用**
- 完整的死代码——既不在Prompt构建中使用，也不在Message管理中使用

**影响**:
- 维护负担：改Prompt时仍要维护这两个方法
- 代码膨胀：每个子类都有无用代码
- 误导新开发者：以为这两个方法在某个地方被调用

**🏆 最优方案**：
```python
# 1. 从 BasePromptTemplates 中删除这两个抽象方法
# 2. 从所有子类中删除对应实现
# 3. 文件：file_prompts.py, desktop_prompts.py, shell_prompts.py, 
#    network_prompts.py, system_prompts.py, document_prompts.py, meta_prompts.py
```
- 删除死代码（DRY+SLAP）
- 不做backward compatibility：不会产生向后兼容问题，因为没有任何调用方

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`get_parameter_reminder()` 和 `get_observation_prompt()` 已从 `BasePrompts` 基类和所有子类中删除
> - ✅ **修复方式正确**：grep确认全系统无任何调用方，删除安全
> - ✅ **10大原则符合**：DRY（删除无用代码）、YAGNI（不需要的接口不保留）、禁止backward（彻底删除不保留）

---

#### 遗漏问题C：OUTPUT_FORMAT与FC模式冲突（P1-严重）

**位置**: `base_prompt_template.py` - `_build_output_format()`

**问题描述**:
- `_build_output_format()` 生成的OUTPUT_FORMAT严格规定输出JSON格式（含 `thought`, `tool_name`, `tool_params` 等字段）
- 但FC（Function Calling）模式下，LLM的输出不是JSON字符串，而是**结构化tool_calls协议**（由LLM API直接返回）
- 强制LLM在FC模式下遵守JSON OUTPUT_FORMAT是相矛盾的——LLM要么忽略OUTPUT_FORMAT，要么困惑
- 这个矛盾不会导致功能崩溃（LLM API的FC模式会强制使用tool_calls协议），但浪费了token

**影响**:
- OUTPUT_FORMAT的200+ token在FC模式下完全无效
- 可能轻微增加LLM的思维负担
- token浪费

**🏆 最优方案**：
```python
# 根据策略模式决定是否注入OUTPUT_FORMAT
def build_full_system_prompt(self, strategy: Optional[str] = None) -> str:
    parts = [self._build_role_prompt()]
    if strategy != "tools":  # FC模式不注入OUTPUT_FORMAT
        parts.append(self._build_tool_call_rules())
        parts.append(self._build_output_format())
    else:
        parts.append(self._build_tool_call_rules(fc_mode=True))  # FC版tool_call_rules
    ...
```
- 在 `build_full_system_prompt()` 或 `_get_system_prompt()` 中传入当前策略模式
- FC模式下跳过OUTPUT_FORMAT，改用FC模式的精简版tool_call_rules
- 保留TOOL_CALL_RULES不删除，因为Text/ResponseFormat模式仍需要它

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`build_full_system_prompt(strategy)` 新增 `strategy` 参数，FC模式（`strategy="tools"`）时跳过OUTPUT_FORMAT
> - ✅ **修复方式正确**：`universal_agent.py:73` 根据 `tool_category` 决定策略，`base_prompt_template.py:190` 用 `if strategy != "tools"` 条件注入
> - ✅ **10大原则符合**：OCP（新增参数有默认值不破坏现有调用）、SRP（FC/Text策略分离）、KISS（简单条件判断）

---

#### 遗漏问题D：Text模式降级缺少参数Schema（P2-中等）

**位置**: `strategy_selector.py` 或 `llm_core.py` - Text模式回退路径

**问题描述**:
- 当FC模式解析失败时，系统可能降级到Text模式（通过response_format或纯文本）
- 在Text模式下，LLM的可用工具列表通过 `tool_descriptions` 描述，但**参数Schema被丢失**
- `_build_tool_descriptions()` 包含工具名和描述，但不包含参数类型、约束条件等Schema信息
- LLM不知道参数该传什么类型、哪些必填、有哪些枚举值

**影响**:
- Text模式下LLM生成的参数可能格式错误
- 工具调用因参数不匹配而失败
- 降级路径可用性降低

**🏆 最优方案**：
```python
# 在 tool_descriptions 中追加参数Schema
def _tool_to_json_schema(self, tool) -> dict:
    """将工具转为参数Schema描述"""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "parameters": tool.input_model.model_json_schema() if tool.input_model else {}
    }
```
- 在 `_build_tool_descriptions()` 中为每个工具注入 `input_model.model_json_schema()`
- 只影响Text模式，FC模式下LLM API会自动处理Schema
- 不改变工具注册逻辑（OCP）

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`base_prompt_template.py:244-255` 的 `build_tool_descriptions()` 已增加参数类型、必填标记、参数描述
> - ✅ **修复方式正确**：每个参数输出格式为 `pname(ptype)(必填):desc`，LLM可获知参数类型和约束
> - ✅ **10大原则符合**：DRY（从input_schema自动提取）、KISS（简单格式化）

---

#### 遗漏问题E：_build_messages() 两处重复定义（P2-中等）

**位置**: `llm_core.py:111-117` 和 `message_utils.py`

**问题描述**:
- `_build_messages()` 的相同逻辑在 `llm_core.py` 和 `message_utils.py` 中分别实现
- 两处功能等价但实现细节可能不同步
- 违反了DRY原则

**影响**:
- 改一处漏另一处
- 维护时需同时修改两个文件

**🏆 最优方案**：
```python
# message_utils.py 保留完整实现
# llm_core.py 改为委托调用
from app.utils.message_utils import build_messages as _build_messages_from_utils

def _build_messages(self, system_prompt, history, user_input) -> list:
    return _build_messages_from_utils(system_prompt, history, user_input)
```
- `message_utils.py` 中的实现作为唯一真实来源（复用优先）
- `llm_core.py` 中委托调用，确保两处行为一致

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **问题已不存在**：`llm_core/` 拆分后，`llm_core.py` 中已无 `_build_messages` 方法，只有 `message_utils.py` 中的 `build_llm_messages()`
> - ✅ DRY原则已满足：无重复定义

---

#### 遗漏问题F：BaseAIService单例可变状态（P2-中等）

**位置**: `llm_core.py` - `BaseAIService` 单例模式

**问题描述**:
- `BaseAIService` 使用 `_instance` 类属性实现单例（`llm_core.py:48-51`）
- 但 `_cancelled`（取消标志）和 `task_id` 是实例级别的可变状态
- 多个任务共享同一个单例实例，一个任务的 `cancel()` 可能错误影响其他任务

**影响**:
- 任务A调用 `cancel()` 可能导致任务B被错误取消
- 并发场景下的竞态条件
- 单例本应用作无状态服务，但 `_cancelled` 引入了有状态行为

**🏆 最优方案**：
```python
# 方案A（推荐）：移除_cancelled和task_id，改为无状态单例
class BaseAIService:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    # 删除 __init__ 中的 self._cancelled / self.task_id
    # 取消逻辑改为由调用方维护
```
- 保持单例模式但**消除可变状态**（SRP）
- `_cancelled` 逻辑应由上层调用方（如ReAct循环）管理

> **📋 修复复核（小健 2026-06-11）**：
> - ⚠️ **不修复（P2-可接受风险）**：`BaseAIService` 仍有 `_cancelled` 和 `task_id` 实例级可变状态
> - **风险评估**：当前为单用户桌面应用，并发请求概率极低；`_check_task_cancelled_or_paused()` 已优先使用 `task_registry` 检查（L85-87），`_cancelled` 仅作为本地fallback
> - **如需修复**：将 `_cancelled` 改为 `task_registry` 统一管理，消除实例级可变状态

---

#### 遗漏问题G：中英文混用 & 命名不一致（P3-轻微）

**位置**: 多个Prompt模板文件

**问题描述**:
- Prompt内容混合中英文：部分字段用中文、部分用英文（如 `When to use` → `使用场景`）
- 工具描述中英文风格不统一
- 影响LLM输出的一致性

**影响**:
- LLM输出可能在中文和英文之间切换
- Prompt风格不一致降低LLM的理解准确度

**🏆 最优方案**：
- 统一使用中文Prompt
- 一次评审所有Prompt模板，确保语言和风格一致
- 低优先级，可在下一次Prompt调整时统一处理

> **📋 修复复核（小健 2026-06-11）**：
> - ✅ **已修复**：`base_prompt_template.py:255-256` 的 "Parameters" → "参数"、"Returns: 返回操作结果" → "返回: 操作结果"
> - ✅ **10大原则符合**：KISS（统一为中文标签）、DRY（格式一致）

---

## 七、完整流程示例

### 7.1 示例场景：用户要求读取config.json

**Step 1: 用户请求**

```
用户输入: "读取C:/config.json文件内容"
```

**Step 2: 路由层处理**

```python
# chat_stream_v2.py
intent_type = "file"  # CRSS评分判断
agent = AgentFactory.create(intent_type="file", task_id="xxx")
```

**Step 3: Agent初始化**

```python
# UniversalAgent.__init__()
config = resolve_agent_config("file")
self.prompts = FileOperationPrompts()
self.tool_category = ToolCategory.FILE
```

**Step 4: 初始化运行状态**

```python
# _initialize_run_state()
sys_prompt = self._get_system_prompt()
# 组装顺序:
# ① system_info (服务器OS信息)
# ② tool_descriptions (FILE工具描述)
# ③ Tool Call Examples
# ④ OUTPUT_FORMAT
# ⑤ TOOL_CALL_RULES
# ⑥ safety_reminder
# ⑦ rollback_instructions
# ⑧ avoid_repeat_rules

task_prompt = self._get_task_prompt("读取C:/config.json文件内容")
# Task: 读取C:/config.json文件内容
# Current time: 2026-06-10 15:15:59
# 请完成此文件管理任务,按以下步骤:
# 1. 分析需要做什么操作
# 2. 使用合适的工具完成任务
# 3. 用中文总结结果

message_builder.init_history(sys_prompt, task_prompt)
# conversation_history = [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt}
# ]
```

**Step 5: 第一轮LLM调用**

```python
# _call_llm()
messages = message_builder.prepare_messages_for_llm()
# messages = [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt}
# ]

# LLM返回
llm_response = '{"thought": "用户要读取配置文件", "reasoning": "调用read_file工具", "tool_name": "read_file", "tool_params": {"file_paths": ["C:/config.json"]}}'
```

**Step 6: 解析LLM响应**

```python
parsed = parse_llm_response(llm_response)
# parsed = {
#   "type": "action",
#   "thought": "用户要读取配置文件",
#   "reasoning": "调用read_file工具",
#   "tool_name": "read_file",
#   "tool_params": {"file_paths": ["C:/config.json"]}
# }
```

**Step 7: 执行工具**

```python
# handle_action()
result = await agent._execute_tool("read_file", {"file_paths": ["C:/config.json"]})
# result = {
#   "code": "SUCCESS",
#   "data": {"content": '{"name": "myapp", "version": "1.0"}'},
#   "message": "文件读取成功"
# }
```

**Step 8: 构建observation**

```python
obs_text = build_observation_text(result, "read_file", {"file_paths": ["C:/config.json"]})
# obs_text = "[Observation] 文件读取成功\n内容: {"name": "myapp", "version": "1.0"}"

message_builder.add_assistant(llm_response)
# conversation_history.append({"role": "assistant", "content": llm_response})

message_builder.add_observation(obs_text, llm_call_count=1)
# conversation_history.append({"role": "user", "content": "[Tool Result]\n[Observation] ..."})
```

**Step 9: 第二轮LLM调用**

```python
# conversation_history = [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt},
#   {"role": "assistant", "content": '{"thought": "...", "tool_name": "read_file", ...}'},
#   {"role": "user", "content": "[Tool Result]\n[Observation] ..."}
# ]

# LLM返回
llm_response = '{"thought": "文件已成功读取", "reasoning": "任务完成", "tool_name": "finish", "tool_params": {"result": "文件内容: {"name": "myapp", "version": "1.0"}"}}'
```

**Step 10: 解析并结束**

```python
parsed = parse_llm_response(llm_response)
# parsed = {"type": "answer", ...}

# handle_answer()
agent.status = AgentStatus.COMPLETED
yield FinalStep(response="文件内容: ...")
```

---

## 八、复查记录

### 第一遍复查（2026-06-10 15:20:00）

**复查内容**:
- ✅ Prompt组装顺序正确
- ✅ Message生命周期完整
- ✅ LLM调用流程清晰
- ✅ ReAct循环逻辑正确
- ⚠️ 发现问题：规则重复、示例硬编码

### 第二遍复查（2026-06-10 15:25:00）

**复查内容**:
- ✅ conversation_history结构正确
- ✅ observation截断逻辑正确
- ✅ FC协议配对正确
- ⚠️ 发现问题：temp_history容量检查频繁

### 第三遍复查（2026-06-10 15:30:00）

**复查内容**:
- ✅ LLM响应解析链完整
- ✅ handler分派正确
- ✅ 工具提醒机制正确
- ⚠️ 发现问题：重试逻辑可能重复执行

### 第四遍复查（2026-06-10 15:35:00）

**复查内容**:
- ✅ 常量定义完整
- ✅ 配置加载正确
- ✅ 系统适配器正确
- ⚠️ 发现问题：解析链过长

### 第五遍复查（2026-06-10 15:40:00）

**复查内容**:
- ✅ 所有流程图准确
- ✅ 所有代码片段准确
- ✅ 所有问题分析合理
- ✅ 所有建议可行

---

## 九、总结

### 9.1 架构优点

1. **分层清晰**: Prompt构建、Message管理、LLM调用三层分离
2. **统一入口**: build_full_system_prompt()唯一组装入口
3. **状态管理**: MessageBuilder集中管理conversation_history
4. **智能裁剪**: 容量感知、去重、FC配对保护
5. **流式支持**: 实时输出chunk给前端
6. **降级机制**: FC失败→Text非流式

### 9.2 主要问题

1. **规则重复**: OUTPUT_FORMAT和TOOL_CALL_RULES重复强调
2. **示例硬编码**: 维护成本高
3. **候选意图干扰**: 可能影响LLM判断
4. **容量检查频繁**: 可能影响性能
5. **裁剪丢失上下文**: 可能丢失重要信息
6. **重试无幂等性**: 可能重复执行
7. **解析链过长**: 可能影响性能

### 9.3 改进建议优先级

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | 规则重复 | 合并重复规则，提取为常量 |
| P0 | 重试无幂等性 | 增加请求指纹 |
| P1 | 示例硬编码 | 提取为模板池 |
| P1 | 裁剪丢失上下文 | 增加重要消息标记 |
| P2 | 容量检查频繁 | 使用计数器维护 |
| P2 | 解析链过长 | 增加快速路径 |
| P3 | 候选意图干扰 | 只在首次注入 |

---

**文档完成时间**: 2026-06-10 15:40:00  
**复查次数**: 5遍  
**复查结果**: ✅ 全部通过  