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
- ❌ 禁止使用 [TOOL_CALL] 格式(如:[TOOL_CALL]{{...}}[/TOOL_CALL])
- ❌ 禁止使用XML标签格式(如:<longcat_tool_call> <arg_key>等任何XML/HTML标签)
- ❌ 禁止在content中嵌入工具调用(工具调用必须通过tool_name+tool_params字段)
- ❌ 禁止使用任意自定义标签或特殊标记包裹工具名和参数

【示例】:
{"thought": "用户询问时间", "reasoning": "调用get_current_time", "tool_name": "get_current_time", "tool_params": {"format": "%Y-%m-%d"}}
{"thought": "已完成", "tool_name": "finish", "tool_params": {"result": "当前时间是2026-05-09"}}"""
```

**注**: 【SAFETY WARNING】已于2026-06-11（小健审查）合并到TOOL_CALL_RULES，消除SRP/DRY违反。

**分析**:
- ✅ 明确规定两种返回情况（调用工具/任务完成）
- ✅ 字段要求清晰（thought/reasoning/tool_name/tool_params）
- ✅ 禁止项详细（含具体格式示例供LLM参考）
- ⚠️ **问题**: 禁止项过多，可能导致LLM困惑

#### 2.1.2 TOOL_CALL_RULES（工具调用规则）

```python
TOOL_CALL_RULES = """【Tool Call Rules】:
- 确认用户意图后立即调用工具,不要在thought中反复讨论该用哪个工具
- reasoning简短说明选择理由即可(1-2句),不要写长篇分析
- ❌ 禁止:仅用文字回复而不调用工具 — 用户请求需要实际操作时,MUST调用工具
- ✅ 正确:确认意图→直接调用→根据结果决定下一步
- ⚠️ 任务完成时必须返回 tool_name="finish",否则会进入死循环
- 始终用中文回复用户
- 工具返回错误时向用户解释错误并建议替代方案

【IMPERATIVE: 必须使用工具执行操作】:
- 用户请求需要实际操作时,MUST调用对应的工具(非闲聊场景)
- 不得仅回复"好的,我将..."之类的文字确认而不调用工具
- 只有任务完成总结结果时,才能使用 tool_name="finish" 结束
- 如果不确定用什么工具,选择最合理的工具并调用,不要用文字回复代替"""
```

**注**: 原OUTPUT_FORMAT中的【SAFETY WARNING】已于2026-06-11合并至此（小健审查），消除SRP/DRY违反。原2条详细禁止项"禁止在thought中列举多个工具"和"禁止在thought中分析参数"已删除以减少重复；标题后缀"- 极其重要"已移除。

**分析**:
- ✅ 强调立即调用工具，不反复讨论
- ✅ 明确禁止仅文字回复
- ✅ 整合SAFETY WARNING消除冗余
- ⚠️ **问题**: 规则重复强调，可能与OUTPUT_FORMAT冲突

#### 2.1.3 AVOID_REPEAT_RULES（避免重复规则 — 类常量）

```python
AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行(结果不会变)
- 同一命令/URL失败3次后必须换工具或换URL,禁止再试同方式
- 已获取的信息直接使用,不需要重新获取
- 失败后优先尝试替代方法,而非反复重试同一方法"""
```

**注**: 2026-06-11（小沈）从 build_full_system_prompt() 硬编码提取为类常量，#1 fix。

#### 2.1.4 build_full_system_prompt()（唯一组装入口）

```python
def build_full_system_prompt(self, strategy: Optional[str] = None) -> str:
    """构建完整的系统 Prompt(唯一组装入口)
    
    组装顺序:
    ① get_system_prompt()       — 分类特有(角色+工具+示例)
    ② OUTPUT_FORMAT             — 公共:JSON输出格式(FC模式跳过,由API生成)
    ③ TOOL_CALL_RULES           — 公共:工具调用规则
    ④ get_safety_reminder()     — 分类特有:安全提醒
    ⑤ get_rollback_instructions()— 公共:回滚说明
    ⑥ AVOID_REPEAT_RULES        — 公共:避免重复操作
    
    Args:
        strategy: "tools"(FC模式,跳过OUTPUT_FORMAT), None(默认,包含OUTPUT_FORMAT)
    """
    parts = [self.get_system_prompt()]
    
    if strategy != "tools":
        parts.append(self.OUTPUT_FORMAT)
    parts.append(self.TOOL_CALL_RULES)
    
    safety = self.get_safety_reminder()
    if safety:
        parts.append(safety)
    
    rollback = self.get_rollback_instructions()
    if rollback:
        parts.append(rollback)
    
    parts.append(self.AVOID_REPEAT_RULES)
    
    return "\n\n".join(parts)
```

**组装顺序分析**:
```
① get_system_prompt()         [分类特有] → 角色+工具+示例
② OUTPUT_FORMAT               [公共]     → JSON格式规则(FC模式跳过)
③ TOOL_CALL_RULES             [公共]     → 工具调用规则
④ get_safety_reminder()       [分类特有] → 安全提醒
⑤ get_rollback_instructions() [公共]     → 回滚说明
⑥ AVOID_REPEAT_RULES          [公共]     → 避免重复规则
```

**分析**:
- ✅ 组装顺序合理：先角色定义，后规则约束
- ✅ 公共规则统一注入，避免重复
- ✅ strategy参数：FC模式跳过OUTPUT_FORMAT（由API Schema约束格式）
- ✅ AVOID_REPEAT_RULES提取为类常量（2026-06-11小沈修复）

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
    """构建完整system prompt — 含prompts守卫 + strategy参数"""
    if not hasattr(self, 'prompts') or not self.prompts:
        return "System: 通用助手"
    
    # 1. FC模式传递strategy="tools"(跳过OUTPUT_FORMAT,由API Schema约束)
    strategy = "tools" if self.tool_category is not None else None
    base_prompt = self.prompts.build_full_system_prompt(strategy=strategy)
    
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
② OUTPUT_FORMAT               [公共]     → JSON格式规则(FC模式跳过)
③ TOOL_CALL_RULES             [公共]     → 工具调用规则
④ get_safety_reminder()       [分类特有] → 安全提醒
⑤ get_rollback_instructions() [公共]     → 回滚说明
⑥ AVOID_REPEAT_RULES          [公共]     → 避免重复规则
⑦ _build_candidates_hint()    [运行时]   → 候选意图提示
⑧ _build_cross_tool_hint()    [运行时]   → 跨分类工具提示
```

**分析**:
- ✅ 运行时动态注入候选意图和跨分类工具提示
- ✅ 组装顺序合理（FC模式跳过②，由API Schema约束格式）
- ✅ prompts守卫防止未初始化时崩溃
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
    """去重+截断observation,优先保留FC配对obs(tool-role),非FC text-obs先裁剪"""
    obs_list = self._dedup_by_fingerprint(obs_list)
    # P4: 优先保留含tool_calls的assistant消息,保护FC配对完整性 — 小欧 2026-06-11
    tool_call_msgs = [m for m in assistant_msgs if m.get("tool_calls")]
    text_msgs = [m for m in assistant_msgs if not m.get("tool_calls")]
    tool_call_msgs = tool_call_msgs[-10:]
    text_msgs = text_msgs[-5:]
    assistant_msgs = text_msgs + tool_call_msgs
    obs_list = obs_list[-30:]
    # 分离tool-role(FC配对)和text-role(非FC),优先保留FC配对obs
    tool_obs = [o for o in obs_list if o.get("role") == "tool"]
    text_obs = [o for o in obs_list if o.get("role") != "tool"]
    # 先裁text-obs(非FC),保留最近15条tool-obs(FC配对)
    tool_obs = tool_obs[-15:]
    combined = text_obs + tool_obs
    while combined and self._total_chars(combined) > budget:
        combined.pop(0)
    return combined
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
- ✅ FC配对保护：assistant按tool_calls/text分离保留；observation按tool/text分离优先保留FC配对
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
    """调用LLM — FC优先,降级text流式 — 小沈 2026-06-11"""
    self.llm_call_count += 1
    self.message_builder.trim_history()
    
    messages = self.message_builder.prepare_messages_for_llm()
    
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})
    
    # 工具提醒惰性注入:不永久写入conversation_history — 小沈 2026-06-11
    if getattr(self, '_tool_reminder_needed', False):
        from app.services.prompts.base_prompt_template import BasePrompts
        messages.append({"role": "system", "content": BasePrompts.TOOL_REMINDER})
        self._tool_reminder_needed = False
    
    openai_tools = self._get_openai_tools()
    
    if not openai_tools:
        logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")
    
    # FC优先:所有场景都过FC流式,无工具也走(由API处理)
    async for item in self._call_llm_fc_stream(messages, openai_tools):
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
- ✅ FC优先：所有场景都过FC流式（2026-06-11小沈重构：无工具时由API处理）
- ✅ 工具提醒惰性注入：不永久写入conversation_history，通过标志位动态注入（2026-06-11小沈）
- ⚠️ **问题**: executed_summary在每次调用时都注入，可能增加上下文长度

**_call_llm_fc_stream()实现**:

```python
async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
    """FC模式流式调用 — 异常/纯文本降级text流式 — 小沈 2026-06-11"""
    from app.services.agent.steps import ChunkStep
    
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
        
        logger.info(f"[FC] 流式完成, content_len={len(full_content)}, reasoning_len={len(full_reasoning)}, chunks={chunk_step_count}")
    
    except Exception as e:
        logger.warning(f"[FC] request_stream异常,降级text流式: {e}")
        text_messages = self._convert_fc_messages_to_text(messages)
        async for item in self._call_llm_text_stream(text_messages):
            yield item
        return
    
    if stream_error:
        logger.error(f"[FC] 流式错误,降级text流式: {stream_error}")
        text_messages = self._convert_fc_messages_to_text(messages)
        async for item in self._call_llm_text_stream(text_messages):
            yield item
        return
    
    if full_content:
        parsed = parse_json(full_content)
        if parsed and "tool_name" in parsed:
            yield ("response", full_content)
            return
    
    if full_content.strip():
        logger.warning("[FC] LLM返回纯文本(无tool_name),降级text流式")
        text_messages = self._convert_fc_messages_to_text(messages)
        async for item in self._call_llm_text_stream(text_messages):
            yield item
        return
    
    if full_reasoning and not full_content:
        full_content = full_reasoning
    
    yield ("response", full_content.strip())
```

**分析**:
- ✅ 实时输出chunk给前端
- ✅ 支持reasoning分离
- ✅ 降级机制：FC失败→_convert_fc_messages_to_text()转换→_call_llm_text_stream()流式降级（2026-06-11小沈改为流式降级，非非流式）
- ✅ 纯文本兜底：FC模式下LLM返回纯文本(无tool_name)时同样降级text流式
- ✅ 无默认finish：空响应时返回空字符串（2026-06-11小欧P7修复）

#### _call_llm_text_stream()（Text模式流式 — 2026-06-09小沈新增）

```python
async def _call_llm_text_stream(self, messages: list):
    """Text模式流式调用 — 实时输出内容 - 小沈 2026-06-09"""
    from app.services.agent.steps import ChunkStep
    
    full_content = ""
    full_reasoning = ""
    chunk_step_count = 0
    
    try:
        async for chunk in self.llm_client.request_stream(
            messages=messages, mode="text",
        ):
            if chunk.stream_error:
                logger.error(f"[text] 流式错误: {chunk.stream_error}")
                break
            
            if chunk.content:
                chunk_step_count += 1
                if getattr(chunk, "is_reasoning", False):
                    full_reasoning += chunk.content
                    yield ("chunk", ChunkStep(
                        step=self.llm_call_count, content=chunk.content, is_reasoning=True,
                    ))
                else:
                    full_content += chunk.content
                    yield ("chunk", ChunkStep(
                        step=self.llm_call_count, content=chunk.content, is_reasoning=False,
                    ))
            
            if chunk.is_done:
                break
        
        logger.info(f"[text] 流式调用完成, content_len={len(full_content)}, reasoning_len={len(full_reasoning)}, chunks={chunk_step_count}")
    
    except Exception as e:
        logger.error(f"[text] request_stream失败,降级text: {e}")
        response = await self._call_llm_text_nostream(messages)
        yield ("response", response)
        return
    
    if not full_content and full_reasoning:
        full_content = full_reasoning
    
    yield ("response", full_content.strip())
```

**分析**:
- ✅ Text模式流式降级路径（与FC流式结构一致）
- ✅ 支持reasoning分离（思考模型）
- ✅ 异常降级到非流式 `_call_llm_text_nostream()`

#### _convert_fc_messages_to_text()（FC→Text消息转换 — 2026-06-11小欧P7修复）

```python
@staticmethod
def _convert_fc_messages_to_text(messages: list) -> list:
    """将FC配对(assistant+tool_calls, role:tool)转为Text格式"""
    result = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_calls = msg.get("tool_calls", [])
            tc_descs = []
            for tc in tool_calls:
                fn = tc.get("function", {}) if isinstance(tc.get("function"), dict) else {}
                tc_descs.append(fn.get("name", "unknown"))
            result.append({
                "role": "assistant",
                "content": f"[Tool calls: {', '.join(tc_descs)}]"
            })
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                tool_content = messages[i].get("content", "")
                if tool_content:
                    result.append({
                        "role": "user",
                        "content": f"[Tool Result]\n{tool_content}"
                    })
                i += 1
            continue
        else:
            result.append(msg)
            i += 1
    return result
```

**分析**:
- ✅ FC降级前将FC协议(assistant+tool_calls + role:tool)转为Text格式(assistant+[Tool Result])
- ✅ 解决Text模式LLM无法理解FC协议消息的问题
- ✅ 在 `_call_llm_fc_stream` 的3个降级点（异常/stream_error/纯文本）前调用

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
    
    # 7. 工具提醒: 设标志位,由_call_llm()动态注入(不永久写入conversation_history) — 小沈 2026-06-11
    if parsed_type == "chunk" and not _has_tool_call(agent):
        logger.warning(f"[react_cycle] LLM text-only response (step {step_counter[0]}), set tool_reminder flag")
        agent._tool_reminder_needed = True
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

**_TOOL_REMINDER来源**（2026-06-11 小欧M1修复：从react_cycle.py移入base_prompt_template.py）：

```python
# react_cycle.py 引用：
from app.services.prompts.base_prompt_template import BasePrompts
_TOOL_REMINDER = BasePrompts.TOOL_REMINDER

# base_prompt_template.py 定义：
TOOL_REMINDER = (
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
- ✅ 工具提醒采用惰性注入（设标志位→_call_llm()动态注入），不永久写入conversation_history
- ✅ TOOL_REMINDER与OUTPUT_FORMAT/TOOL_CALL_RULES同级（base_prompt_template.py），消除硬编码
- ⚠️ **问题**: TOOL_REMINDER与OUTPUT_FORMAT规则部分重复

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
self._on_session_init(task, context)          # 会话初始化回调
sys_prompt = self._get_system_prompt()
# 组装顺序(FC模式跳过OUTPUT_FORMAT):
# ① system_info (服务器OS信息)
# ② tool_descriptions (FILE工具描述)
# ③ Tool Call Examples
# ④ OUTPUT_FORMAT(FC模式跳过)
# ⑤ TOOL_CALL_RULES
# ⑥ safety_reminder
# ⑦ rollback_instructions
# ⑧ AVOID_REPEAT_RULES
# ⑨ _build_candidates_hint()(动态)
# ⑩ _build_cross_tool_hint()(动态)

task_prompt = self._get_task_prompt("读取C:/config.json文件内容")
# Task: 读取C:/config.json文件内容
# Current time: 2026-06-10 15:15:59
# 请完成此文件管理任务,按以下步骤:
# 1. 分析需要做什么操作
# 2. 使用合适的工具完成任务
# 3. 用中文总结结果

self._on_before_loop(sys_prompt, task_prompt, context)  # loop前回调
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

### 第六遍复查（2026-06-11 系统同步校验 — 小欧）

**复查内容（逐节核对当前代码，修复17处差异）**:
- ✅ OUTPUT_FORMAT移除SAFETY_WARNING、添加【示例】
- ✅ TOOL_CALL_RULES合并SAFETY_WARNING、精简规则
- ✅ build_full_system_prompt增加strategy参数 + AVOID_REPEAT_RULES类常量
- ✅ _get_system_prompt增加prompts守卫 + strategy参数
- ✅ _trim_to_budget增加FC配对保护分离逻辑
- ✅ _call_llm增加tool_reminder标志机制、FC-only分支
- ✅ _call_llm_fc_stream降级改为流式 + _convert_fc_messages_to_text
- ✅ 新增_call_llm_text_stream()和_convert_fc_messages_to_text()文档
- ✅ _TOOL_REMINDER移至base_prompt_template.py引用
- ✅ 工具提醒改为标志位惰性注入（非直接append）
- ✅ 初始化run_state补充_on_session_init和_on_before_loop回调
- ✅ 降级描述修正为非流式→流式

---

## 九、总结

### 9.1 架构优点

1. **分层清晰**: Prompt构建、Message管理、LLM调用三层分离
2. **统一入口**: build_full_system_prompt()唯一组装入口
3. **状态管理**: MessageBuilder集中管理conversation_history
4. **智能裁剪**: 容量感知、去重、FC配对保护
5. **流式支持**: 实时输出chunk给前端
6. **降级机制**: FC失败→ _convert_fc_messages_to_text()消息转换→ _call_llm_text_stream()流式降级（2026-06-11小沈优化为流式降级）

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