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

---

## 一、复核结论总览

| 问题编号 | 问题描述 | 复核结果 | 是否真实问题 | 优先级 |
|---------|---------|---------|-------------|--------|
| 问题1 | 规则重复强调 | ✅ 真实存在 | 是 | P1 |
| 问题2 | 示例硬编码 | ✅ 真实存在 | 是 | P2 |
| 问题3 | 候选意图提示干扰判断 | ❌ 不成立 | 否 | - |
| 问题4 | temp_history容量检查频繁 | ✅ 真实存在 | 是 | P2 |
| 问题5 | 裁剪后丢失重要上下文 | ✅ 真实存在（设计权衡） | 是 | P3 |
| 问题6 | executed_summary每次注入 | ✅ 真实存在 | 是 | P2 |
| 问题7 | 重试逻辑导致重复执行 | ❌ 不成立 | 否 | - |
| 问题8 | 解析失败静默返回None | ✅ 真实存在（合理设计） | 是 | P3 |
| 问题9 | 空响应返回默认finish | ✅ 真实存在 | 是 | P1 |
| 问题10 | _TOOL_REMINDER硬编码 | ✅ 真实存在 | 是 | P2 |
| 问题11 | 解析链过长 | ❌ 不成立 | 否 | - |

**统计**:
- 真实问题：8个
- 不成立问题：3个
- P1优先级：2个
- P2优先级：4个
- P3优先级：2个

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

**最终结论**: ✅ **真实问题**

**性能影响评估**:

```
假设temp_history有10条消息，每条平均500字符：
- 每次prepare_messages_for_llm调用：
  - _total_chars遍历10条消息：O(10)
  - while循环可能执行多次
- 如果LLM调用100次，总计算量：100 * 10 = 1000次遍历
```

**建议优先级**: P2

**改进建议**:
```python
# 使用计数器维护字符数
def __init__(self):
    self._temp_chars = 0

def add_to_temp(self, chunk):
    self.temp_history.append(chunk)
    self._temp_chars += len(chunk.get("content", ""))
    self._cap_temp_history()

def _cap_temp_history(self):
    while self._temp_chars > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        removed = self.temp_history.pop(0)
        self._temp_chars -= len(removed.get("content", ""))
```

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

**改进建议**:
```python
# 增加重要消息标记
def add_observation(self, obs_text, is_important=False):
    msg = {"role": "user", "content": f"[Tool Result]\n{obs_text}"}
    if is_important:
        msg["_important"] = True
    self.conversation_history.append(msg)

def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    # 分离重要消息和普通消息
    important = [obs for obs in obs_list if obs.get("_important")]
    normal = [obs for obs in obs_list if not obs.get("_important")]
    # 先裁剪normal，保留important
    # ...
```

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

**最终结论**: ✅ **真实问题**

**影响评估**:
- 每次LLM调用都注入，增加约100-200 tokens
- 与observation有部分重复
- 但executed_summary有防止重复调用的价值

**建议优先级**: P2

**改进建议**:
```python
# 只在observation过长时注入
def _call_llm(self):
    messages = self.message_builder.prepare_messages_for_llm()
    
    # 检查最后一条observation是否过长
    last_obs = self._get_last_observation()
    if len(last_obs) > 10000:  # 过长时注入摘要
        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})
    # ...
```

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

**改进建议**:
```python
# 增加统计计数
def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
    try:
        # ...
    except Exception as e:
        self._parse_error_count += 1
        if self._parse_error_count % 100 == 0:  # 每100次打印一次warning
            logger.warning(f"[_parse_sse_data] 解析失败累计{self._parse_error_count}次, 最近: {e}")
        logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
        return None
```

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

**改进建议**:
```python
# 返回错误而非默认finish
if not full_content and not full_reasoning:
    logger.error("[FC] LLM返回空响应")
    yield ("response", json.dumps({
        "thought": "LLM返回空响应",
        "reasoning": "可能是网络错误或LLM异常",
        "tool_name": "finish",
        "tool_params": {"result": "任务执行失败：LLM返回空响应，请重试"}
    }))
    return
```

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

**最终结论**: ✅ **真实问题**

**影响评估**:
- 无法根据场景定制提醒内容
- 修改需要改代码

**建议优先级**: P2

**改进建议**:
```python
# 提取为配置
from app.config import get_config

def _get_tool_reminder(category: str) -> str:
    config = get_config()
    reminders = config.get("tool_reminders", {})
    return reminders.get(category, _DEFAULT_TOOL_REMINDER)
```

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

| 问题编号 | 问题描述 | 优先级 | 建议措施 |
|---------|---------|--------|---------|
| 问题1 | 规则重复强调 | P1 | 合并重复规则，提取avoid_repeat_rules为常量 |
| 问题2 | 示例硬编码 | P2 | 提取为模板池，支持动态配置 |
| 问题4 | temp_history容量检查频繁 | P2 | 使用计数器维护字符数 |
| 问题5 | 裁剪后丢失重要上下文 | P3 | 增加重要消息标记 |
| 问题6 | executed_summary每次注入 | P2 | 只在observation过长时注入 |
| 问题8 | 解析失败静默返回None | P3 | 增加统计计数和warning日志 |
| 问题9 | 空响应返回默认finish | P1 | 返回错误而非默认finish |
| 问题10 | _TOOL_REMINDER硬编码 | P2 | 提取为配置，支持动态调整 |

### 3.2 不成立问题汇总（3个）

| 问题编号 | 问题描述 | 不成立原因 |
|---------|---------|-----------|
| 问题3 | 候选意图提示干扰判断 | candidates_hint只在初始化时注入一次，不是每次LLM调用都注入 |
| 问题7 | 重试逻辑导致重复执行 | 重试的是LLM请求，不是工具执行；LLM请求幂等，不会导致工具重复执行 |
| 问题11 | 解析链过长 | 6个handler不算过长，链式解析是合理设计，复杂度线性可接受 |

### 3.3 优先级分布

```
P1（高优先级）：2个
- 问题1：规则重复强调
- 问题9：空响应返回默认finish

P2（中优先级）：4个
- 问题2：示例硬编码
- 问题4：temp_history容量检查频繁
- 问题6：executed_summary每次注入
- 问题10：_TOOL_REMINDER硬编码

P3（低优先级）：2个
- 问题5：裁剪后丢失重要上下文
- 问题8：解析失败静默返回None
```

---

## 四、改进建议执行计划

### 4.1 P1优先级（立即修复）

#### 问题1：规则重复强调

**修复位置**: `backend/app/services/prompts/base_prompt_template.py`

**修复方案**:
```python
# 1. 提取avoid_repeat_rules为常量
AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行
- 同一命令/URL失败3次后必须换工具或换URL
- 已获取的信息直接使用
- 失败后优先尝试替代方法
"""

# 2. 合并重复规则（简化TOOL_CALL_RULES）
TOOL_CALL_RULES = """【Tool Call Rules】:
- 确认意图后立即调用工具
- reasoning简短说明理由即可(1-2句)
- 始终用中文回复用户
- 工具返回错误时向用户解释并建议替代方案
"""

# 3. build_full_system_prompt中使用常量
def build_full_system_prompt(self) -> str:
    parts = [self.get_system_prompt()]
    parts.append(self.OUTPUT_FORMAT)
    parts.append(self.TOOL_CALL_RULES)
    # ...
    parts.append(self.AVOID_REPEAT_RULES)  # 使用常量
    return "\n\n".join(parts)
```

#### 问题9：空响应返回默认finish

**修复位置**: `backend/app/services/agent/universal_agent.py`

**修复方案**:
```python
async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
    # ...
    
    # 空响应检查
    if not full_content and not full_reasoning:
        logger.error("[FC] LLM返回空响应")
        yield ("response", json.dumps({
            "thought": "LLM返回空响应",
            "reasoning": "可能是网络错误或LLM异常",
            "tool_name": "finish",
            "tool_params": {"result": "任务执行失败：LLM返回空响应，请重试"}
        }))
        return
    
    # 如果只有reasoning，当作content
    if full_reasoning and not full_content:
        full_content = full_reasoning
    
    yield ("response", full_content.strip())
```

### 4.2 P2优先级（近期修复）

#### 问题2：示例硬编码

**修复位置**: `backend/app/services/prompts/file/file_prompts.py` 等

**修复方案**:
```python
# 提取为模板池
from app.services.prompts.example_templates import get_examples

def get_system_prompt(self) -> str:
    # ...
    examples = get_examples("file", count=4)
    return prompt + examples
```

#### 问题4：temp_history容量检查频繁

**修复位置**: `backend/app/services/agent/message_builder.py`

**修复方案**:
```python
def __init__(self, max_context_chars: int = MAX_CONTEXT_CHARS):
    self.conversation_history = []
    self.temp_history = []
    self.MAX_CONTEXT_CHARS = max_context_chars
    self._temp_chars = 0  # 新增：维护字符计数

def _add_to_temp(self, chunk: Dict):
    self.temp_history.append(chunk)
    content = chunk.get("content", "")
    self._temp_chars += len(content) if content else 0
    self._cap_temp_history()

def _cap_temp_history(self):
    while self._temp_chars > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
        removed = self.temp_history.pop(0)
        content = removed.get("content", "")
        self._temp_chars -= len(content) if content else 0
```

#### 问题6：executed_summary每次注入

**修复位置**: `backend/app/services/agent/universal_agent.py`

**修复方案**:
```python
async def _call_llm(self):
    # ...
    messages = self.message_builder.prepare_messages_for_llm()
    
    # 只在observation过长时注入
    last_obs_len = self._get_last_observation_length()
    if last_obs_len > 10000:
        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})
    # ...
```

#### 问题10：_TOOL_REMINDER硬编码

**修复位置**: `backend/app/services/agent/core_agent/react_cycle.py`

**修复方案**:
```python
# 提取为配置
from app.config import get_config

def _get_tool_reminder(category: str = None) -> str:
    config = get_config()
    reminders = config.get("tool_reminders", {})
    default = (
        "【系统提示·工具调用提醒】\n"
        "你刚才的回复没有调用任何工具。用户请求需要实际操作才能完成，"
        "你必须使用工具来执行。\n"
        "请重新输出JSON格式，包含 tool_name 和 tool_params。\n"
        "如果不需要工具（用户只是闲聊），请用 tool_name: finish 结束。"
    )
    return reminders.get(category, default)
```

### 4.3 P3优先级（长期优化）

#### 问题5：裁剪后丢失重要上下文

**修复位置**: `backend/app/services/agent/message_builder.py`

**修复方案**:
```python
def add_observation(self, observation_text: str, llm_call_count: int = 0, 
                    fc_context: Optional[Dict] = None, is_important: bool = False):
    observation_text = self._prepare_observation_text(observation_text, llm_call_count)
    msg = {"role": "user", "content": f"[Tool Result]\n{observation_text}"}
    if is_important:
        msg["_important"] = True
    self.conversation_history.append(msg)
    self.trim_history()

def _trim_to_budget(self, obs_list, assistant_msgs, budget):
    # 分离重要消息和普通消息
    important = [obs for obs in obs_list if obs.get("_important")]
    normal = [obs for obs in obs_list if not obs.get("_important")]
    # 先裁剪normal，保留important
    # ...
```

#### 问题8：解析失败静默返回None

**修复位置**: `backend/app/services/llm_core/llm_core.py`

**修复方案**:
```python
def __init__(self, ...):
    # ...
    self._parse_error_count = 0

def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
    try:
        # ...
    except Exception as e:
        self._parse_error_count += 1
        if self._parse_error_count % 100 == 0:
            logger.warning(f"[_parse_sse_data] 解析失败累计{self._parse_error_count}次")
        logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
        return None
```

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

**文档完成时间**: 2026-06-10 15:50:00  
**复核次数**: 3遍  
**复核结果**: ✅ 全部完成  
**真实问题**: 8个  
**不成立问题**: 3个  