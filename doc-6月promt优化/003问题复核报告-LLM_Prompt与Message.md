# 问题复核报告 - LLM Prompt与Message全系统分析

**创建时间**: 2026-06-10 15:36:34  
**复核人**: 小沈  
**复核次数**: 3遍  
**原文档**: `doc/LLM_Prompt与Message_History全系统分析.md`

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-10 15:36:34 | 小沈 | 初始版本，11个问题逐一复核 |
| v2.0 | 2026-06-11 | 小健 | 10大原则复核:原方案5个违反YAGNI改为不修改,2个需优化,更新总览/总结/执行计划 |
| v2.1 | 2026-06-11 | 小健 | 代码验证复核:问题1/2已修复(非部分/待修复),问题8补充stream_parser warning,更新总结/执行计划 |

---

## 一、复核结论总览

| 问题编号 | 问题描述 | 复核结果 | 是否真实问题 | 优先级 | 10大原则符合性 | 最优方案方向 |
|---------|---------|---------|-------------|--------|---------------|------------|
| 问题1 | 规则重复强调 | ✅ 真实存在 | 是 | P1 | ✅ 已修复 | SAFETY WARNING合并到TOOL_CALL_RULES |
| 问题2 | 示例硬编码 | ✅ 真实存在 | 是 | P2 | ✅ 已修复 | system_prompts去掉indent=6(已修复) |
| 问题3 | 候选意图提示干扰判断 | ❌ 不成立 | 否 | - | - | - |
| 问题4 | temp_history容量检查频繁 | ✅ 真实存在 | 是 | P2 | ⚠️ YAGNI(改进方案过度) | 保持现状(复杂度不高) |
| 问题5 | 裁剪后丢失重要上下文 | ✅ 真实存在（设计权衡） | 是 | P3 | ⚠️ YAGNI(改进方案过度) | FC配对保护已足够 |
| 问题6 | executed_summary每次注入 | ✅ 真实存在 | 是 | P2 | ⚠️ YAGNI(条件注入过度) | 保持现状(设计意图正确) |
| 问题7 | 重试逻辑导致重复执行 | ❌ 不成立 | 否 | - | - | - |
| 问题8 | 解析失败静默返回None | ✅ 真实存在（合理设计） | 是 | P3 | ⚠️ YAGNI(计数改进过度) | 保持现状(合理设计,stream_parser已提warning) |
| 问题9 | 空响应返回默认finish | ✅ 真实存在 | 是 | P1 | ⚠️ 违反SRP(伪造finish) | 空字符串+上层捕获(已修复) |
| 问题10 | _TOOL_REMINDER硬编码 | ✅ 真实存在 | 是 | P2 | ⚠️ YAGNI(配置化过度) | 保持现状(硬编码足够) |
| 问题11 | 解析链过长 | ❌ 不成立 | 否 | - | - | - |

**统计**:
- 真实问题：8个
- 不成立问题：3个
- P1优先级：2个
- P2优先级：4个
- P3优先级：2个
- **原改进方案违反YAGNI**: 5个(问题4/5/6/8/10)
- **原改进方案违反SRP/DRY**: 2个(问题1/2) — 已修复
- **已修复**: 3个(问题1/2/9)
- **保持现状**: 5个(问题4/5/6/8/10)

---

## 二、逐个问题复核详情

### 问题1：规则重复强调

**原文档描述**:
- OUTPUT_FORMAT和TOOL_CALL_RULES都强调"必须调用工具"
- 禁止项过多（7条），可能导致LLM困惑
- avoid_repeat_rules硬编码在方法中，未提取为常量

**第一次复核**（代码验证）:

```python
# base_prompt_template.py

# OUTPUT_FORMAT 第87行
【SAFETY WARNING】:
⚠️ 任务完成时必须返回 tool_name="finish",否则会进入死循环。

# TOOL_CALL_RULES 第102-105行
【IMPERATIVE: 必须使用工具执行操作】:
- 当用户要求创建/写入/读取/修改文件时,你MUST调用对应的文件工具
- 不得仅回复"好的,我将..."之类的文字确认而不调用工具
- 只有在任务完成需要总结结果时,才能使用 tool_name="finish" 结束
```

**验证结果**: ✅ 确实存在重复强调

**第二次复核**（禁止项统计）:

```
OUTPUT_FORMAT禁止项（7条）:
1. ❌ 禁止同时返回多个tool_name
2. ❌ 禁止tool_name存在但tool_params缺失
3. ❌ 禁止使用 [TOOL_CALL] 格式
4. ❌ 禁止使用XML标签格式
5. ❌ 禁止在content中嵌入工具调用
6. ❌ 禁止使用任意自定义标签或特殊标记包裹工具名和参数
7. ⚠️ 任务完成时必须返回 tool_name="finish"
```

**验证结果**: ✅ 禁止项确实过多

**第三次复核**（硬编码验证）:

```python
# base_prompt_template.py 第202-208行
def build_full_system_prompt(self) -> str:
    # ...
    avoid_repeat_rules = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行(结果不会变)
- 同一命令/URL失败3次后必须换工具或换URL,禁止再试同方式
- 已获取的信息直接使用,不需要重新获取
- 失败后优先尝试替代方法,而非反复重试同一方法"""
    parts.append(avoid_repeat_rules)
```

**验证结果**: ✅ 确实硬编码在方法中

**最终结论**: ✅ **真实问题**

**影响评估**:
- Prompt过长，增加token消耗（约200 tokens）
- 规则重复可能导致LLM困惑
- 硬编码导致维护成本高

**建议优先级**: P1

**10大原则评估**:

**第1轮 — 原方案评估**（提取AVOID_REPEAT_RULES为常量+合并规则）:

| 原则 | 符合性 | 分析 |
|------|--------|------|
| SRP | ⚠️ 部分违反 | OUTPUT_FORMAT混入"必须调用工具"强调(本应是格式定义) |
| DRY | ⚠️ 违反 | OUTPUT_FORMAT的SAFETY WARNING与TOOL_CALL_RULES重复强调"必须用工具" |
| KISS | ✅ | 提取常量是最简单的做法 |
| 禁止backward compatibility | ✅ | 修改Prompt文本，旧版不再兼容 |

**第2轮 — 代码当前状态验证**（检查已有修复）:

```python
# base_prompt_template.py 2026-06-10/11
# ✅ AVOID_REPEAT_RULES 已提取为类常量(第106行)
# ✅ build_full_system_prompt(strategy) FC模式跳过OUTPUT_FORMAT(第190行)
# ✅ SAFETY WARNING 已合并到 TOOL_CALL_RULES(第86行注释确认,第92行"必须返回finish")
# ✅ OUTPUT_FORMAT 不再包含 SAFETY WARNING 段落(SRP:只定义格式)
```

当前状态：✅ **已完全修复**。AVOID_REPEAT_RULES提取为常量，SAFETY WARNING合并到TOOL_CALL_RULES，OUTPUT_FORMAT只保留格式定义。DRY/SRP违反已消除。

**第3轮 — 最优方案**（基于10大原则的修正）:

✅ **已执行方案**：SAFETY WARNING从OUTPUT_FORMAT合并到TOOL_CALL_RULES（2026-06-11），消除SRP/DRY违反。

当前代码（已修复后）:
```python
# OUTPUT_FORMAT: 只定义JSON格式+字段要求+禁止项(无SAFETY WARNING)
OUTPUT_FORMAT = """【Response Format - 必须遵守】:
必须使用JSON格式输出,只能返回以下两种情况之一:
{JSON格式示例}
【字段要求】...
【禁止项】..."""

# TOOL_CALL_RULES: 合并了SAFETY WARNING(第86行注释确认)
TOOL_CALL_RULES = """【Tool Call Rules】:
- ⚠️ 任务完成时必须返回 tool_name="finish",否则会进入死循环
- ❌ 禁止:仅用文字回复而不调用工具
...
【IMPERATIVE: 必须使用工具执行操作】:
- 用户请求需要实际操作时,MUST调用对应的工具..."""
```

**10大原则结论**: ✅ 已完全修复。SAFETY WARNING归入TOOL_CALL_RULES(SRP),消除重复强调(DRY),仅做文本合并(KISS),不引入配置(YAGNI)。

---

### 问题2：示例硬编码

**原文档描述**:
- Tool Call Examples硬编码在字符串中
- 修改示例需要修改代码
- 不同分类示例格式不统一

**第一次复核**（file_prompts.py验证）:

```python
# file_prompts.py 第66-78行
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
```

**验证结果**: ✅ 确实硬编码

**第二次复核**（desktop_prompts.py验证）:

```python
# desktop_prompts.py 第91-103行
【Tool Call Examples】:
Example 1: 列出窗口
{"thought": "用户要查看所有打开的窗口", "reasoning": "使用window_info列出窗口", "tool_name": "window_info", "tool_params": {"action": "list"}}

Example 2: 最大化窗口
{"thought": "用户要最大化记事本", "reasoning": "使用window_control设置窗口状态", "tool_name": "window_control", "tool_params": {"window_title": "Notepad", "action": "maximize"}}
```

**验证结果**: ✅ 不同分类都硬编码

**第三次复核**（格式一致性检查）:

```
file_prompts格式: Example 1: 读取文件\n{"thought": "...", ...}
desktop_prompts格式: Example 1: 列出窗口\n{"thought": "...", ...}
system_prompts格式: 示例1:{"thought": "...", ...}  # 不同！
```

**验证结果**: ✅ 格式确实不统一

**最终结论**: ✅ **真实问题**

**影响评估**:
- 修改示例需要修改代码，维护成本高
- 格式不统一可能导致LLM学习不一致

**建议优先级**: P2

**10大原则评估**:

**第1轮 — 原方案评估**（提取为模板池）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| DRY | ⚠️ 格式不统一 | system_prompts.py用多行缩进JSON，file/desktop用单行JSON |
| KISS | ⚠️ 原方案过重 | 提取模板池引入新模块，示例很少变更 |
| YAGNI | ❌ 违反 | 示例极少变更(数月不变)，模板池过度设计 |
| 复用优先 | ⚠️ 部分符合 | 统一格式即可复用，不需模板池 |

**第2轮 — 代码当前状态验证**：

```python
# file_prompts.py: 单行JSON ✅ 简洁清晰
# desktop_prompts.py: 单行JSON ✅ 与file一致
# system_prompts.py: 单行JSON ✅ 已修复(2026-06-11,去掉indent=6)
```

格式不统一问题已修复。硬编码本身不是问题。

**第3轮 — 最优方案**（基于10大原则的修正）:

✅ **已执行方案**：`system_prompts.py:60` 已改为 `json.dumps(ex, ensure_ascii=False)`（去掉indent=6），与file/desktop格式统一。

**改动量**: 1个文件改1行（已完成）。

**10大原则结论**: ✅ 已修复。统一为单行JSON(DRY),改1行代码(KISS),不引入模板池(YAGNI)。

---

### 问题3：候选意图提示可能干扰判断

**原文档描述**:
- 候选意图提示在每次调用时都注入
- 可能干扰LLM对当前意图的判断
- 增加上下文长度

**第一次复核**（调用链追踪）:

```python
# initialize_run_state.py
def initialize_run_state(self, task, task_id, context):
    # ...
    sys_prompt = self._get_system_prompt()  # 只调用一次！
    task_prompt = self._get_task_prompt(task, context)
    # ...
    self.message_builder.init_history(sys_prompt, task_prompt)
```

**验证结果**: ⚠️ _get_system_prompt只在初始化时调用一次

**第二次复核**（_call_llm是否重新获取system prompt）:

```python
# universal_agent.py
async def _call_llm(self):
    self.llm_call_count += 1
    self.message_builder.trim_history()
    messages = self.message_builder.prepare_messages_for_llm()  # 从已有history获取
    # 没有重新调用_get_system_prompt！
```

**验证结果**: ✅ 每次LLM调用不会重新获取system prompt

**第三次复核**（conversation_history生命周期）:

```
初始化阶段:
  _get_system_prompt() → 包含candidates_hint
  init_history(sys_prompt, task_prompt)
  conversation_history = [system(含candidates_hint), user]

循环阶段:
  _call_llm():
    messages = prepare_messages_for_llm()  # 直接返回conversation_history
    # 不会重新构建system prompt
```

**验证结果**: ✅ candidates_hint只在初始化时注入一次

**最终结论**: ❌ **问题不成立**

**原因分析**:
- 原文档误认为每次LLM调用都会重新构建system prompt
- 实际上system prompt只在initialize_run_state时构建一次
- candidates_hint在conversation_history中持久存在，不是每次注入

**建议**: 无需修改

---

### 问题4：temp_history容量检查频繁

**原文档描述**:
- 每次调用都检查temp_history容量
- 可能影响性能

**第一次复核**（prepare_messages_for_llm验证）:

```python
# message_builder.py 第120-133行
def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
    messages = list(self.conversation_history)
    if self.temp_history:
        messages = messages + list(self.temp_history)
    # temp_history容量保护:总字符超50000时从最旧开始截断
    self._cap_temp_history()  # 每次都调用！
    return messages
```

**验证结果**: ✅ 确实每次都调用

**第二次复核**（_cap_temp_history实现）:

```python
# message_builder.py 第135-138行
def _cap_temp_history(self):
    """对temp_history加字符容量限制(最多50000字符),从最旧条目开始截断"""
    while self._total_chars(self.temp_history) > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        self.temp_history.pop(0)  # 从最旧开始移除
```

**验证结果**: ✅ while循环+每次计算_total_chars

**第三次复核**（_total_chars实现）:

```python
# message_builder.py 第289-301行
@staticmethod
def _total_chars(messages: List[Dict]) -> int:
    """计算消息列表总字符数"""
    total = 0
    for msg in messages:
        content = msg.get("content")
        total += len(content) if content is not None else 0
    return total
```

**验证结果**: ✅ 每次都遍历所有消息计算字符数

**最终结论**: ✅ **真实问题(但影响极低)**

**性能影响评估**:

```
假设temp_history有10条消息，每条平均500字符：
- 每次prepare_messages_for_llm调用：
  - _total_chars遍历10条消息：O(10)
  - while循环可能执行多次
- 如果LLM调用100次，总计算量：100 * 10 = 1000次遍历(微秒级)
```

**建议优先级**: P2

**10大原则评估**:

**第1轮 — 原方案评估**（使用计数器维护字符数）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| YAGNI | ❌ 违反 | temp_history通常<10条，O(n)遍历微秒级，计数器引入状态管理成本 |
| SRP | ✅ 计数器归_cap_temp_history管 |
| KISS | ⚠️ 计数器简单但没必要 | 10条数据的遍历不是性能瓶颈 |
| SLAP | ⚠️ 计数器分散到add_to_temp | 新增一个方法 |

**第2轮 — 代码当前状态验证**：

```python
# message_builder.py 第296-308行
@staticmethod
def _total_chars(messages: List[Dict]) -> int:
    total = 0
    for msg in messages:  # temp_history最多50000字符/约10-30条
        content = msg.get("content")
        total += len(content) if content is not None else 0
    return total

# 实际调用频率: 每次prepare_messages_for_llm调用一次
# prepare_messages_for_llm调用频率: 每次LLM调用(call_llm)一次
# 假设每次LLM调用耗时2-5秒, _total_chars耗时<0.001ms
```

性能影响不到总调用时间的0.0001%，是典型的**过早优化**。

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案引入`_temp_chars`计数器和`add_to_temp`方法，违反YAGNI。**保持现状**：
- temp_history通常小(10条内)，`_total_chars` O(n)遍历微秒级
- 引入计数器需同步维护append/pop/clear所有操作的计数一致，增加bug风险
- 真实性能瓶颈在LLM调用(秒级)，不在`_total_chars`(微秒级)

**10大原则结论**: ❌ 原方案违反YAGNI(KNUTH:过早优化是万恶之源)。**保持现状，不修改**。原"优先级P2"应降为**P4(无需处理)**。

---

### 问题5：裁剪后可能丢失重要上下文

**原文档描述**:
- 裁剪时只保留最新30条observation
- 可能丢失重要的早期上下文
- FC协议配对裁剪可能移除重要消息

**第一次复核**（_trim_to_budget验证）:

```python
# message_builder.py 第174-181行
def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    """去重+截断observation,保留最新assistant,直到满足预算"""
    obs_list = self._dedup_by_fingerprint(obs_list)
    assistant_msgs = assistant_msgs[-10:]  # 保留最新10条
    obs_list = obs_list[-30:]  # 保留最新30条
    while obs_list and self._total_chars(obs_list) > budget:
        obs_list.pop(0)
    return obs_list
```

**验证结果**: ✅ 确实只保留最新30条

**第二次复核**（这是设计权衡还是bug？）:

```
设计意图：
- conversation_history容量限制：150000字符
- 超过80%才触发裁剪
- 裁剪策略：保留system + 最新30条observation + 最新10条assistant

这是合理的设计权衡，不是bug：
- 防止上下文过长导致LLM性能下降
- 最新信息通常更重要
- 早期信息可能已过时
```

**验证结果**: ⚠️ 这是设计权衡，不是bug

**第三次复核**（FC协议配对裁剪）:

```python
# message_builder.py 第233-266行
def _trim_fc_pairs(messages: List[Dict]) -> List[Dict]:
    """FC协议配对裁剪:确保role:tool与role:assistant(tool_calls)严格配对"""
    # ...
    # 未配对的消息被移除
```

**验证结果**: ✅ 确实可能移除重要消息，但这是为了保证FC协议完整性

**最终结论**: ✅ **真实问题（但属于设计权衡）**

**影响评估**:
- 可能丢失早期重要信息
- 但这是容量限制的必然结果
- 需要在"保留完整上下文"和"控制上下文长度"间权衡

**建议优先级**: P3

**10大原则评估**:

**第1轮 — 原方案评估**（增加重要消息标记）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| YAGNI | ❌ 违反 | 当前无"重要消息"概念，引入标记需修改add_observation调用链 |
| SRP | ⚠️ 混合 | add_observation兼做"标记重要性"和"追加消息"两件事 |
| KISS | ❌ 违反 | 引入`_important`标记+分离逻辑，复杂度增30% |
| SLAP | ⚠️ 添加条件分支 | _trim_to_budget需判断_important属性 |

**第2轮 — 代码当前状态验证**：

```python
# 2026-06-11修复: _trim_to_budget已优先保留FC配对tool-obs(最近15条)
# 这是最重要的"重要上下文"——FC协议配对消息
# 非FC(text-role)消息中, 所有observation同等重要, 不存在"重要"vs"普通"
```

当前代码已通过FC配对保留机制解决了最重要的上下文保护问题。

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案引入`_important`标记机制，违反YAGNI+KISS+SRP。**保持现状**：
- FC配对保护已解决最关键的"重要上下文"问题(2026-06-11修复)
- text-role observation无"重要"vs"普通"区分,引入标记是伪需求
- 上下文长度裁剪是系统级约束,不可能保留所有历史

**10大原则结论**: ❌ 原方案违反YAGNI/KISS/SRP。**保持现状，不修改**。FC配对保护(2026-06-11修复)已充分缓解此问题。

---

### 问题6：executed_summary每次调用都注入

**原文档描述**:
- executed_summary在每次LLM调用时都注入
- 增加上下文长度
- 可能与observation重复

**第一次复核**（_call_llm验证）:

```python
# universal_agent.py 第126-144行
async def _call_llm(self):
    self.llm_call_count += 1
    self.message_builder.trim_history()
    
    messages = self.message_builder.prepare_messages_for_llm()
    
    executed_summary = self._build_executed_tool_summary()
    if executed_summary:
        messages.append({"role": "system", "content": executed_summary})  # 每次都注入！
    
    openai_tools = self._get_openai_tools()
    # ...
```

**验证结果**: ✅ 确实每次都注入

**第二次复核**（_build_executed_tool_summary内容）:

```python
# universal_agent.py 第331-345行
def _build_executed_tool_summary(self) -> str:
    if not hasattr(self, '_executed_tool_summary') or not self._executed_tool_summary:
        return ""
    
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

**验证结果**: ✅ 内容包含已执行工具摘要

**第三次复核**（是否与observation重复？）:

```
observation内容：
[Tool Result]
Observation: 文件读取成功
内容: {"name": "myapp", "version": "1.0"}

executed_summary内容：
【已执行工具(勿重复)】read_file→success({"name": "myapp", "version": "1.0"})
注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!

分析：
- observation包含完整结果
- executed_summary是摘要+提醒
- 有部分重复，但executed_summary更简洁
```

**验证结果**: ⚠️ 有部分重复，但executed_summary有独特价值（防止重复调用）

**最终结论**: ✅ **真实问题(但设计意图正确)**

**影响评估**:
- 每次LLM调用都注入，增加约100-200 tokens
- 与observation有部分重复
- 但executed_summary有防止重复调用的价值

**建议优先级**: P2

**10大原则评估**:

**第1轮 — 原方案评估**（只在observation过长时注入）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| YAGNI | ❌ 违反 | "observation过长"阈值10000是硬编码拍脑袋，从未真实出现 |
| SRP | ✅ 保持 | 执行摘要注入是_call_llm的合理职责 |
| KISS | ⚠️ 原方案简单 | 条件注入比每次都注复杂(需判断+额外方法_get_last_observation) |
| SLAP | ⚠️ 条件散布 | 需加_get_last_observation方法 |

**第2轮 — 代码当前状态验证**：

```python
# universal_agent.py 第342-356行
def _build_executed_tool_summary(self) -> str:
    done = [s for s in self._executed_tool_summary if '→success' in s]
    if not done:
        return ""  # 无已执行工具时返回空字符串
    # 保留最新8条
    for entry in done[-8:]:
        ...

# _call_llm第135-137行: 仅在executed_summary非空时注入
```

关键发现：`_build_executed_tool_summary()` **仅在真正的工具执行后有内容**。首次LLM调用、多次对话等场景返回空字符串，不注入。因此"每次都注入"的说法**不准确**——实际是"每次有已执行工具时才注入"。

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案建议"条件注入"违反YAGNI且基于不准确的前提。**保持现状**：
- executed_summary仅在**真的执行了工具**后才注入(一般2-5条/100-200tokens)
- 防止LLM重复调用工具的核心价值远超token成本
- observation可能被trim_history裁剪，executed_summary是唯一保留的工具执行摘要
- 引入"observation过长"阈值增加复杂度且无真实收益

**10大原则结论**: ❌ 原方案评估不准确（实际非每次注入）且违反YAGNI。**保持现状，不修改**。executed_summary是防止重复调用的关键设计，其价值远超token成本。

---

### 问题7：重试逻辑可能导致重复执行

**原文档描述**:
- 重试时可能重复发送相同请求
- 没有幂等性保护
- 可能导致工具重复执行

**第一次复核**（request_stream重试逻辑）:

```python
# llm_core.py 第166-224行
while retry_count <= max_retries:
    try:
        async for data_str in self._llm_sdk.request_stream(...):
            # 处理SSE数据
        # ...
    except Exception as e:
        if self._should_retry(e) and retry_count < max_retries:
            retry_count += 1
            wait_time = 2 ** retry_count
            await asyncio.sleep(wait_time)
            continue  # 重试
        else:
            yield self._create_stream_error_chunk(e)
            return
```

**验证结果**: ✅ 确实会重试LLM请求

**第二次复核**（重试的是什么？）:

```
重试的是：LLM请求（发送messages给LLM）
不是：工具执行

流程：
1. _call_llm() → 发送messages给LLM
2. LLM返回响应
3. parse_llm_response() → 解析响应
4. handle_action() → 执行工具

重试发生在步骤1-2，不影响步骤4
```

**验证结果**: ✅ 重试的是LLM请求，不是工具执行

**第三次复核**（LLM请求是否幂等？）:

```
LLM请求幂等性：
- 发送相同messages给LLM
- LLM可能返回不同响应（温度>0时有随机性）
- 但不会导致工具重复执行

工具执行在handle_action中，不受LLM请求重试影响
```

**验证结果**: ✅ LLM请求幂等，不会导致工具重复执行

**最终结论**: ❌ **问题不成立**

**原因分析**:
- 原文档误认为重试会导致工具重复执行
- 实际上重试的是LLM请求，不是工具执行
- 工具执行在handle_action中，与LLM请求重试无关

**建议**: 无需修改

---

### 问题8：解析失败静默返回None

**原文档描述**:
- 解析失败时静默返回None
- 可能丢失重要信息

**第一次复核**（_parse_sse_data实现）:

```python
# llm_core.py 第277-304行
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
        logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
        return None  # 静默返回None
```

**验证结果**: ✅ 确实静默返回None

**第二次复核**（为什么返回None是合理的？）:

```
SSE流格式：
data: {"choices": [{"delta": {"content": "Hello"}}]}
data: {"choices": [{"delta": {"content": " World"}}]}
data: [DONE]

非数据行：
: comment
data: [DONE]

解析失败的情况：
1. 非JSON行（如": comment"）
2. 空数据行
3. 无content或reasoning_content的delta

这些情况下返回None是合理的，不应该报错
```

**验证结果**: ✅ 返回None是合理设计

**第三次复核**（是否有日志？）:

```python
except Exception as e:
    logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
    return None
```

**验证结果**: ✅ 有debug日志

**最终结论**: ✅ **真实问题（但属于合理设计）**

**原因分析**:
- 返回None是合理设计，因为SSE流中有非数据行
- 有debug日志记录，不是完全静默
- 但debug日志可能被忽略

**建议优先级**: P3

**10大原则评估**:

**第1轮 — 原方案评估**（增加统计计数）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| YAGNI | ❌ 违反 | 解析失败是SSE流正常现象(心跳行/注释行)，不是错误 |
| KISS | ✅ 原设计 | 返回None是最简单的处理方式 |
| SRP | ✅ _parse_sse_data | 只做解析，不做告警 |
| SLAP | ✅ | 统一在caller层处理None |

**第2轮 — 代码当前状态验证**：

```python
# llm_core.py 第291-293行: 仍为debug级别
except Exception as e:
    logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
    return None

# stream_parser.py 第80-82行: 已提升为warning级别(2026-06-11修复)
if data is None:
    logger.warning(f"[{log_tag}] JSON解析失败: {data_str[:100]}")
    continue

# 调用者(request_stream)正确过滤None:
# async for data_str in raw_stream:
#     chunk = self._parse_sse_data(data_str)
#     if chunk:
#         yield chunk
```

当前设计是正确的：
- SSE流包含`data: [DONE]`、`: heartbeat`等非数据行
- 返回None让调用者过滤，是最干净的KISS设计
- **stream_parser.py(新解析器)已将JSON解析失败日志提升为warning**，llm_core.py(旧解析器)仍为debug
- 计数`_parse_error_count`统计"正常行"无意义

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案引入`_parse_error_count`计数器违反YAGNI。**保持现状**：
- "解析失败"在SSE流中是正常现象（心跳/注释行），不是错误
- 调用者正确过滤None值
- DEBUG日志已足够，true error会由request_stream的其他异常路径处理（连接断开、超时等已有单独处理）
- 计数器统计"正常发生的行"无意义，且增加了不必要的状态

**10大原则结论**: ❌ 原方案违反YAGNI。"解析失败"在SSE流中是正常行，计数无意义。**保持现状，不修改**。

---

### 问题9：空响应返回默认finish

**原文档描述**:
- 空响应时返回默认finish
- 可能导致误判任务完成

**第一次复核**（_call_llm_fc_stream实现）:

```python
# universal_agent.py 第146-210行
async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
    full_content = ""
    full_reasoning = ""
    # ...
    
    # 如果只有reasoning，当作content
    if full_reasoning and not full_content:
        full_content = full_reasoning
    
    # 返回最终响应
    yield ("response", full_content.strip() or '{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}')
```

**验证结果**: ✅ 确实在空响应时返回默认finish

**第二次复核**（什么情况下会触发？）:

```
触发条件：
1. full_content为空
2. full_reasoning为空
3. LLM返回空响应

可能原因：
1. LLM网络错误
2. LLM返回空内容
3. 流式解析失败
```

**验证结果**: ✅ 多种情况可能触发

**第三次复核**（影响评估）:

```
影响：
1. 任务被误判为完成
2. 用户得不到预期结果
3. 可能丢失重要信息

严重程度：高
```

**验证结果**: ✅ 影响严重

**最终结论**: ✅ **真实问题**

**影响评估**:
- 可能导致任务提前结束
- 用户得不到预期结果
- 严重程度：高

**建议优先级**: P1

**10大原则评估**:

**第1轮 — 原方案评估**（返回错误信息而非默认finish）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| SRP | ⚠️ LLM层不应伪造业务响应 | "_call_llm_fc_stream返回response元组"是LLM层职责，伪造finish是越界处理 |
| KISS | ⚠️ 原方案 | 伪造finish字符串不如"空字符串让上层处理"简单 |
| SLAP | ⚠️ 混合抽象 | LLM层生成"任务执行失败"业务消息是错误抽象层 |

**第2轮 — 代码当前状态验证**（确认已修复）：

```python
# universal_agent.py 第206-221行 (2026-06-11 已修复)
if full_content:
    parsed = parse_json(full_content)
    if parsed and "tool_name" in parsed:
        yield ("response", full_content)
        return

if full_content.strip():
    logger.warning("[FC] LLM返回纯文本(无tool_name),降级text流式")
    async for item in self._call_llm_text_stream(messages):
        yield item
    return

if full_reasoning and not full_content:
    full_content = full_reasoning

yield ("response", full_content.strip())  # 空响应→空字符串→react_cycle捕获
```

**当前实现**：空响应返回`full_content.strip()`(空字符串) → 上层`react_cycle`捕获空响应 → 调用`exit_with_error`。
✅ 已在2026-06-11会话中修复（原#9 fix）。

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案建议"返回错误finish JSON"仍违反SRP（LLM层生成业务消息）。**当前已采用的方案**是更优的：

```python
# 已采用的方案(更符合10大原则):
# LLM层: yield ("response", "") — 返回空字符串(SRP:LLM层只传递,不解释)
# React层: catch空响应 → exit_with_error(SRP:业务决策在React层)
```

对比两个方案：

| 方案 | SRP | KISS | 可测试性 |
|------|-----|------|---------|
| ① 返回错误finish(原方案) | ❌ LLM层伪造业务响应 | ❌ 生成JSON字符串 | ❌ 需验证JSON内容 |
| ② 空字符串+上层捕获(已采用) | ✅ 职责分离 | ✅ 空字符串传递 | ✅ 只需检查空响应 |

**10大原则结论**: ✅ 已修复。采用方案②（空字符串→上层捕获）比原方案①（伪造finish）更符合SRP/KISS。**已修复，无需额外操作**。

---

### 问题10：_TOOL_REMINDER硬编码

**原文档描述**:
- _TOOL_REMINDER硬编码在文件中
- 无法动态调整

**第一次复核**（react_cycle.py验证）:

```python
# react_cycle.py 第36-43行
_TOOL_REMINDER = (
    "【系统提示·工具调用提醒】\n"
    "你刚才的回复没有调用任何工具。用户请求需要实际操作才能完成，"
    "你必须使用工具来执行。\n"
    "请重新输出JSON格式，包含 tool_name 和 tool_params。\n"
    '示例: {"thought": "分析", "reasoning": "理由", "tool_name": "write_text_file", "tool_params": {"file_path": "D:/test.txt", "text": "hello"}}\n'
    "如果不需要工具（用户只是闲聊），请用 tool_name: finish 结束。"
)
```

**验证结果**: ✅ 确实硬编码

**第二次复核**（使用场景）:

```python
# react_cycle.py 第100-102行
if parsed_type == "chunk" and not _has_tool_call(agent):
    logger.warning(f"[react_cycle] LLM text-only response (step {step_counter[0]}), injecting tool reminder")
    agent.message_builder.conversation_history.append({"role": "system", "content": _TOOL_REMINDER})
```

**验证结果**: ✅ 在LLM返回纯文本时注入

**第三次复核**（为什么需要动态调整？）:

```
不同场景可能需要不同的提醒：
1. 文件操作：强调文件工具
2. 桌面操作：强调桌面工具
3. 网络操作：强调网络工具

当前硬编码无法根据场景定制
```

**验证结果**: ✅ 确实无法动态调整

**最终结论**: ✅ **真实问题(但硬编码合理)**

**影响评估**:
- 无法根据场景定制提醒内容
- 修改需要改代码

**建议优先级**: P2

**10大原则评估**:

**第1轮 — 原方案评估**（提取为配置）：

| 原则 | 符合性 | 分析 |
|------|--------|------|
| YAGNI | ❌ 违反 | 工具提醒文本几乎不变化(上线至今只改过格式)，配置化过度 |
| KISS | ❌ 违反 | 从常量→配置需加config读取+YAML定义+category映射，复杂度倍增 |
| DRY | ✅ 居中 | _TOOL_REMINDER已在react_cycle.py一处定义 |
| 复用优先 | ⚠️ 无需复用 | 该文本仅在LLM未调用工具时用一次 |

**第2轮 — 代码当前状态验证**（确认已有优化）：

```python
# react_cycle.py 第36-43行: 模块级常量
_TOOL_REMINDER = ("""...""")

# 使用方式(2026-06-11已优化为标志位动态注入):
# react_cycle设标志→_call_llm动态注入→不持久化写入conversation_history
```

✅ 已修复的7.4(标志位动态注入)解决了**何时注入**的问题，但未解决**内容定制**的问题。

**第3轮 — 最优方案**（基于10大原则的修正）：

原方案建议"提取为配置"违反YAGNI+KISS。**保持现状（硬编码）**：

```
需要定制工具提醒内容的假设场景与实际情况：

假设场景1: 不同域需要不同提醒
实际情况: 所有域的提醒内容一样（提醒LLM调用工具），工具提示不区分域

假设场景2: 提醒文本需要经常修改
实际情况: 上线至今未改过，未来也不会常改

假设场景3: 用户需要自定义提醒
实际情况: 无此需求
```

三个假设场景均不成立，配置化是过度设计。

**10大原则结论**: ❌ 原方案违反YAGNI/KISS。工具提醒文本极少变更且所有域通用，硬编码是最简单正确的做法。**保持现状，不修改**。7.4修复(标志位动态注入)已解决运行时问题。

---

### 问题11：解析链过长

**原文档描述**:
- 6个handler的解析链
- 可能影响性能

**第一次复核**（parse_llm_response实现）:

```python
# parse_llm_response.py 第184-191行
_HANDLERS = [
    _handle_dict_input,          # 1
    _handle_list_input,          # 2
    _handle_json_array_string,   # 3
    _handle_empty_input,         # 4
    _handle_standard_json,       # 5
    _handle_mixed_text_json,     # 6
]
```

**验证结果**: ✅ 确实有6个handler

**第二次复核**（性能分析）:

```
每个handler的复杂度：
1. _handle_dict_input: O(1) - 类型检查
2. _handle_list_input: O(1) - 类型检查
3. _handle_json_array_string: O(n) - JSON解析
4. _handle_empty_input: O(1) - 空值检查
5. _handle_standard_json: O(n) - JSON解析
6. _handle_mixed_text_json: O(n) - JSON提取+解析

最坏情况：遍历所有6个handler
总复杂度：O(6n) = O(n)
```

**验证结果**: ✅ 线性复杂度，不算过长

**第三次复核**（这是合理设计吗？）:

```
链式解析是常见设计模式：
- 责任链模式（Chain of Responsibility）
- 每个handler处理一种格式
- 优先级清晰：dict > list > JSON > 混合文本

优点：
- 易于扩展（新增handler）
- 单一职责（每个handler只处理一种格式）
- 易于测试（每个handler独立测试）

缺点：
- 可能遍历多个handler
- 但复杂度是线性的，可接受
```

**验证结果**: ✅ 链式解析是合理设计

**最终结论**: ❌ **问题不成立**

**原因分析**:
- 6个handler不算过长
- 链式解析是常见设计模式
- 复杂度是线性的，性能可接受

**建议**: 无需修改

---

## 三、复核总结

### 3.1 真实问题汇总（8个）

| 问题编号 | 问题描述 | 优先级 | 原建议措施 | 10大原则评估 | 最优方案 | 当前状态 |
|---------|---------|--------|-----------|-------------|---------|---------|
| 问题1 | 规则重复强调 | P1 | 合并重复规则，提取常量 | ✅ 已修复 | SAFETY WARNING合并到TOOL_CALL_RULES | **已修复**(2026-06-11) |
| 问题2 | 示例硬编码 | P2 | 提取为模板池 | ✅ 已修复 | system_prompts去掉indent=6 | **已修复**(2026-06-11) |
| 问题4 | temp_history容量检查频繁 | P2→**P4** | 使用计数器维护字符数 | ❌ 违反YAGNI | **保持现状** | **无需修改** |
| 问题5 | 裁剪后丢失重要上下文 | P3→**P4** | 增加重要消息标记 | ❌ 违反YAGNI/KISS | FC配对保护已足够 | **已缓解**(2026-06-11 FC保护) |
| 问题6 | executed_summary每次注入 | P2→**P4** | 条件注入 | ❌ 违反YAGNI(前提不准确) | **保持现状** | **无需修改** |
| 问题8 | 解析失败静默返回None | P3→**P4** | 增加统计计数 | ❌ 违反YAGNI | **保持现状** | **无需修改** |
| 问题9 | 空响应返回默认finish | P1 | 返回错误finish | ⚠️ 方案可优化 | 空字符串+上层捕获 | **已修复**(2026-06-11) |
| 问题10 | _TOOL_REMINDER硬编码 | P2→**P4** | 提取为配置 | ❌ 违反YAGNI/KISS | **保持现状** | **无需修改**(7.4已修复) |

### 3.2 不成立问题汇总（3个）

| 问题编号 | 问题描述 | 不成立原因 |
|---------|---------|-----------|
| 问题3 | 候选意图提示干扰判断 | candidates_hint只在初始化时注入一次，不是每次LLM调用都注入 |
| 问题7 | 重试逻辑导致重复执行 | 重试的是LLM请求，不是工具执行；LLM请求幂等，不会导致工具重复执行 |
| 问题11 | 解析链过长 | 6个handler不算过长，链式解析是合理设计，复杂度线性可接受 |

### 3.3 10大原则复核结论

```
原方案符合10大原则: 0个(全部建议方案均有违反)
原方案违反YAGNI:   5个(问题4/5/6/8/10) — 过度设计，保持现状
原方案违反SRP/DRY: 2个(问题1/2) — 已修复(合并/统一格式)
已修复:            3个(问题1/2/9) — 全部已修复
保持现状:          5个(问题4/5/6/8/10) — YAGNI/合理设计
```

### 3.4 修正后优先级分布

```
P1（高优先级）：0个（全部已修复）
  - 问题1：已修复(SAFETY WARNING合并到TOOL_CALL_RULES)
  - 问题9：已修复(空响应上层捕获)

P2（中优先级）：0个（全部已修复）
  - 问题2：已修复(system_prompts去掉indent=6)

P4（无需处理）：5个
  - 问题4：保持现状(YAGNI:过早优化)
  - 问题5：FC配对保护已足够
  - 问题6：保持现状(设计意图正确)
  - 问题8：保持现状(合理设计,stream_parser已提warning)
  - 问题10：保持现状(YAGNI:硬编码足够)
```

---

## 四、改进建议执行计划（基于10大原则修正版）

> 原计划中的5个方案（问题4/5/6/8/10）违反YAGNI，已标记为**不修改**。
> 3个需修改问题（问题1/2/9）**已全部修复**。

### 4.1 已修复：问题9 — 空响应返回默认finish

**修复状态**: ✅ **已修复**（2026-06-11会话，原#9）

**修复位置**: `backend/app/services/agent/universal_agent.py:218-221`

**已采用的方案**（更符合10大原则）:
```python
# LLM层: 空响应→返回空字符串
yield ("response", full_content.strip())  # 当full_content为空时→""

# React层: 捕获空响应→exit_with_error
# react_cycle.py _handle_chunk: 空response触发""检查→exit_with_error
```

**符合什么原则**:
- ✅ **SRP**: LLM层只传递原始内容不解释；业务决策在React层
- ✅ **KISS**: 空字符串是最简单的哨兵值
- ✅ **YAGNI**: 不引入自定义错误格式

---

### 4.2 已修复：问题1 — 规则重复强调

**修复状态**: ✅ **已修复**（2026-06-11，SAFETY WARNING合并到TOOL_CALL_RULES）

**当前状态**:
```python
# ✅ AVOID_REPEAT_RULES 已提取为类常量(第106行)
# ✅ build_full_system_prompt(strategy) FC模式跳过OUTPUT_FORMAT(第190行)
# ✅ SAFETY WARNING 已合并到 TOOL_CALL_RULES(第86行注释确认)
# ✅ OUTPUT_FORMAT 只定义格式(SRP纯净)
```

**已采用的方案**（符合10大原则）:
- ✅ **SRP**: OUTPUT_FORMAT只定义格式，TOOL_CALL_RULES定义规则
- ✅ **DRY**: 消除"必须调用工具"的重复强调
- ✅ **KISS**: 仅做文本合并，不改框架/不拆文件/不引入配置
- ✅ **YAGNI**: 不提取为配置（规则极少变更）

---

### 4.3 已修复：问题2 — 示例硬编码

**修复状态**: ✅ **已修复**（2026-06-11，system_prompts.py去掉indent=6）

**已采用的方案**: `system_prompts.py:60` 改为 `json.dumps(ex, ensure_ascii=False)`（去掉indent参数），与file/desktop格式统一。

**符合什么原则**:
- ✅ **KISS**: 改1行代码，不新建文件
- ✅ **YAGNI**: 不引入模板池/配置化（示例极少变更）
- ✅ **DRY**: 保持所有域示例格式一致

---

### 4.4 不修改（原方案违反YAGNI）

| 问题 | 原方案 | YAGNI违反原因 | 最优方案 |
|------|--------|--------------|---------|
| 问题4 | 计数器中维护temp_chars | 10条数据O(n)遍历微秒级 | **保持现状** |
| 问题5 | _important标记 | 无真实"重要"vs"普通"区分需求 | **FC配对保护已足够** |
| 问题6 | 条件注入executed_summary | 前提不准确(非每次都注入) | **保持现状** |
| 问题8 | _parse_error_count计数器 | SSE流非数据行正常现象 | **保持现状** |
| 问题10 | 提取为配置 | 提醒文本极少变更 | **保持现状**(硬编码足够) |

---

### 4.5 修正后执行计划

| 问题 | 动作 | 工作量 | 优先级 | 依赖 |
|------|------|--------|--------|------|
| 问题9(空响应) | ✅ 已修复 | - | - | - |
| 问题1(规则重复) | ✅ 已修复(SAFETY WARNING合并) | - | - | - |
| 问题2(示例格式) | ✅ 已修复(去掉indent=6) | - | - | - |
| 问题4/5/6/8/10 | **不修改** | - | P4 | - |

---

## 五、复查记录

### 第一次复查（2026-06-10 15:40:00）

**复查内容**:
- 逐一验证11个问题的代码位置
- 确认问题描述是否准确
- 发现问题3、7、11不成立

**复查结果**: ✅ 完成

### 第二次复查（2026-06-10 15:45:00）

**复查内容**:
- 验证不成立问题的原因
- 确认真实问题的影响评估
- 检查改进建议的可行性

**复查结果**: ✅ 完成

### 第三次复查（2026-06-10 15:50:00）

**复查内容**:
- 检查优先级分配是否合理
- 验证改进建议是否完整
- 确认执行计划是否可行

**复查结果**: ✅ 完成

---

**文档完成时间**: 2026-06-11  
**文档版本**: v2.1  
**复核次数**: 3遍（原复核）+ 10大原则复核3遍 + 代码验证复核1遍  
**复核结果**: ✅ 全部完成  
**真实问题**: 8个（原确认）+ 10大原则分析 + 代码验证  
**不成立问题**: 3个  
**10大原则关键结论**: 原方案5个违反YAGNI改为不修改，3个已修复(问题1/2/9)，5个保持现状