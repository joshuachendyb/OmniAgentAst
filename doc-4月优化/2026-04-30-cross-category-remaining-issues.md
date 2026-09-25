# 跨分类工具访问重构 — 剩余问题与修复方案

**创建时间**: 2026-04-30
**作者**: 小沈
**状态**: 待修复清单
**关联文档**: [跨分类工具访问设计方案](./2026-04-30-cross-category-tool-access-design.md)

---

## 🔴 已修复（3个）

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| 1 | TimeReactAgent 死代码 | `react_sse_wrapper.py` | 已添加 time 意图分发 |
| 2 | 绕过 cross-category fallback | `file_react.py` | `_execute_tool` 已添加 executor fallback |
| 3 | 工具概要缓存不失效 | `file_react.py`, `time_react.py` | 已移除缓存，每轮实时生成 |

---

## 🟡 剩余中等缺陷（3个）

### 问题4：TimeReactAgent 未使用 LLMAdapter 自适应策略

**严重程度**: 中等

**当前行为**: `time_react.py:135-140` 调用时只使用 `TextStrategy`，不会根据 LLM 能力自动切换策略（response_format / tools / text）。

```python
# time_react.py - 当前代码
response = await self.text_strategy.call(
    llm_client=self.llm_client,
    message=last_message,
    history_dicts=history_dicts,
    conversation_history=self.conversation_history
)
```

**对比**: `file_react.py:186-229` 有完整的 `LLMAdapter` 策略选择：

```python
# file_react.py - 参考模式
if self.adapter:
    strategy = await self.adapter.ensure_capability()
    if strategy.method == "response_format":
        response = await self.response_format_strategy.call(...)
    elif strategy.method == "tools":
        ...
    else:
        response = await self.text_strategy.call(...)
```

**影响**: 当 LLM 支持 tools/function calling 模式时，TimeReactAgent 无法利用，只能用纯文本方式解析工具调用（可靠性较低）。

**修复步骤**:

1. **修改 `time_react.py` 的 `__init__`**：添加 adapter 和策略类初始化（在 `self.text_strategy = TextStrategy()` 之后）：

```python
# 在 __init__ 的 self.text_strategy = TextStrategy() 之后添加：

# 【修复】LLM 自适应策略
from app.services.agent.llm_adapter import LLMAdapter
from app.services.agent.llm_strategies import ResponseFormatStrategy, ToolsStrategy
self.adapter = LLMAdapter(
    llm_client=self.llm_client,
    model=getattr(self, 'model', 'unknown'),
    provider=getattr(self, 'provider', 'unknown')
)
self.tools_strategy = None
self.response_format_strategy = None
```

2. **修改 `time_react.py` 的 `_get_llm_response`**：用 adapter 策略替换直接调用（参考 `file_react.py:189-229`）：

```python
# 替换 _get_llm_response 中的：
response = await self.text_strategy.call(...)

# 改为：
if self.adapter:
    strategy = await self.adapter.ensure_capability()
    if strategy.method == "response_format" and self.response_format_strategy:
        response = await self.response_format_strategy.call(
            llm_client=self.llm_client,
            message=last_message,
            history_dicts=history_dicts,
            conversation_history=self.conversation_history
        )
    elif strategy.method == "tools" and self.tools_strategy:
        response = await self.tools_strategy.call(...)
    else:
        response = await self.text_strategy.call(...)
else:
    response = await self.text_strategy.call(...)
```

3. **确认 `agent_factory.py` 传递 `model` 参数**：

```python
# react_sse_wrapper.py 中创建 TimeReactAgent 时（约 line 548），
# 已经通过 **kwargs 传入了 api_base/api_key/model，这些参数会通过
# FileReactAgent/TimeReactAgent 的 __init__ 被 setattr 到 self 上。
# 确认 TimeReactAgent 的 super().__init__(..., **kwargs) 正确处理了 model 参数。
```

---

### 问题5：工具概要每轮注入到 Observation 末尾（语义奇异）

**严重程度**: 中等

**当前行为**: `file_react.py:170-177` 和 `time_react.py:129-133` 中，每轮把 ~2.5KB 的工具概要追加到 `conversation_history[-1]` 的内容末尾。从第二轮开始，`history[-1]` 是一条 Observation（如 `"Observation: success - 文件已创建"`），工具概要就变成了：

```
Observation: success - 文件已创建

---
当前可用工具列表:
=== 可用工具列表 ===
【文件操作工具】
  read_file(file_path): 读取文件内容
...
```

**分析**: 虽然设计文档 §11.1 指定"每轮在最后一条 user message 末尾追加"，但 Observation 的 role 也是 `user`，所以代码符合设计。但语义上不清晰：
- Observation 是工具执行结果，混杂工具列表让模型注意力分散
- 每轮重复 2.5KB 的工具列表，对话历史膨胀快

**优化方案**: 将工具概要注入到 System Prompt 末尾，而不是每轮追加到当前消息。

**修复步骤**:

1. **修改 `file_react.py` 和 `time_react.py` 的 `_get_system_prompt()`**：在 system prompt 末尾追加工具概要：

```python
# file_react.py _get_system_prompt() - 修改后
def _get_system_prompt(self) -> str:
    if hasattr(self, '_custom_system_prompt') and self._custom_system_prompt:
        return self._custom_system_prompt
    base = self.prompts.get_system_prompt()
    candidates_hint = ""
    if self._candidates:
        ...
    cross_tool_hint = (
        "\n\n【注意】除了文件操作工具，你还可以使用其他分类的工具。"
        "例如：创建脚本后可以用 execute_command 来运行它，"
        "需要时间信息时可以用 get_current_time 等。"
        "根据任务需要自由选择合适的工具，不受初始分类限制。"
    )
    # 【优化】工具概要注入到 system prompt 末尾（避免每轮重复+避免混入 Observation）
    tools_summary = self._get_tools_summary()
    return base + candidates_hint + cross_tool_hint + "\n\n" + tools_summary
```

2. **修改 `file_react.py` 和 `time_react.py` 的 `_get_llm_response()`**：移除工具概要注入逻辑：

```python
# 删除以下代码块（约 file_react.py:174-179）：
try:
    tools_summary = self._get_tools_summary()
    last_message = last_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
except Exception as e:
    logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
```

> **注意**: 这个修改将工具概要的注入点从 user message 改到 system prompt。优点是每轮不重复、不污染 Observation。缺点是 system prompt 会变长，如果 LLM 对 system prompt 的 attention 较弱，模型可能会忽略工具列表。部署后建议观察 LLM 是否还会调用跨分类工具。

**备选方案**（保持每轮更新但语义清晰）：不修改注入位置，而是将工具概要单独作为一条 system 角色消息插入到对话历史中：

```python
# 在 _get_llm_response 中，将 tool summary 作为独立的 system 消息
tools_summary = self._get_tools_summary()
summary_message = {"role": "system", "content": f"【当前可用工具列表】\n{tools_summary}"}
# 构建 history 时包含这条消息
history_dicts = self.conversation_history[:-1] + [summary_message]
# message 保持为原始 observation 内容，不加工具概要
response = await self.text_strategy.call(
    llm_client=self.llm_client,
    message=last_message,  # 原始内容，不追加工具概要
    history_dicts=history_dicts,
    conversation_history=self.conversation_history
)
```

---

### 问题6：PreprocessingPipeline.process() 残留废弃参数

**严重程度**: 中等

**当前行为**: `chat_router.py:478-483` 调用 `preprocessing.process()` 时传入了 `intent_labels=INTENT_LABELS`，但返回值从未被使用：

```python
# chat_router.py:478-483
intent_result = await self.preprocessing.process(
    user_input=user_input,
    intent_labels=INTENT_LABELS,  # 废弃参数
    session_id=session_id
)
# intent_result 在后续代码中从未引用
```

`pipeline.py:25` 的注释说明意图检测已移到 `route_with_fallback()`，但接口参数未清理。

**影响**: 代码混淆，`INTENT_LABELS` 定义在文件顶部（`chat_router.py:51`）但已无实际用途。后续维护者容易误以为预处理还做意图分类。

**修复步骤**:

1. **修改 `pipeline.py`**：移除 `intent_labels` 参数：

```python
# pipeline.py:15-20
class PreprocessingPipeline:
    """用户输入预处理流水线（纯文本处理）"""

    async def process(
        self,
        user_input: str,
        session_id: str = ""  # 移除 intent_labels 参数
    ) -> dict[str, Any]:
```

2. **修改 `chat_router.py`**：更新调用方和清理常量：

```python
# chat_router.py:478-483 — 修改后
intent_result = await self.preprocessing.process(
    user_input=user_input,
    session_id=session_id
)

# chat_router.py:49-51 — 移除 INTENT_LABELS（检查是否在其他地方被引用后删除）
# INTENT_LABELS = [c.value for c in ToolCategory] + ["chat"]  # 删除
```

3. **搜索 `INTENT_LABELS` 的引用**：确保没有其他地方使用：

```
grep -r "INTENT_LABELS" backend/ --include="*.py"
```

如果只有 `chat_router.py` 中使用，可安全删除。如果别处也引用，保留定义但清理调用。

---

## 🟢 剩余轻微缺陷（4个）

### 问题7：chat_router.py:493 冗余代码

**严重程度**: 轻微

**当前代码**:

```python
candidates_list = [c.value if c else "" for c in candidates_values if c]
```

`if c` 已过滤掉 None/空值，`c.value if c else ""` 中的 `else ""` 永远不会执行。

**修复步骤**:

```python
# 简化后
candidates_list = [c.value for c in candidates_values if c]
```

---

### 问题8：LLM 兜底超时未使用配置文件

**严重程度**: 轻微

**当前行为**: `intent_classifier.py:131` 硬编码 `timeout=30.0`，但配置文件 `config.yaml` 中设为 90s：

```python
# intent_classifier.py:131
async with httpx.AsyncClient(timeout=30.0) as client:
```

而 `_load_qiniu_config()` 已读取了配置中的 `timeout`（line 48）：

```python
"timeout": qiniu_config.get("timeout", 90)
```

但从未用于 HTTP 客户端创建。

**影响**: 慢速 API 下（如 LLM 推理时间长），30s 超时可能导致意图分类失败，fallback 到 chat。

**修复步骤**:

```python
# intent_classifier.py _classify_intent 函数内：
timeout = INTENT_CLASSIFIER_CONFIG.get("timeout", 90)
async with httpx.AsyncClient(timeout=timeout) as client:
```

---

### 问题9：PromptLogger 对非 file/time 意图使用错误 Prompt 模板

**严重程度**: 轻微

**当前行为**: `react_sse_wrapper.py:324-331` 对意图类型的判断不全：

```python
if intent_type == "time":
    from app.services.prompts.time import TimePrompts
    prompts_instance = TimePrompts()
else:
    # 非 time 全部 fallback 到 FileOperationPrompts
    from app.services.prompts.file import FileOperationPrompts
    prompts_instance = FileOperationPrompts()
```

当 `intent_type` 为 `shell` / `network` / `desktop` 时，日志记录会错误地标记为 `file_prompts.py`。

**影响**: 仅影响 prompt 日志的记录准确性，不影响业务逻辑。但在排查问题时可能误导。

**修复步骤**: 添加完整分类映射：

```python
# react_sse_wrapper.py:324-331 — 修改后
if intent_type == "time":
    from app.services.prompts.time import TimePrompts
    prompts_instance = TimePrompts()
    source_name = "time_prompts.py:get_system_prompt()"
elif intent_type == "file":
    from app.services.prompts.file import FileOperationPrompts
    prompts_instance = FileOperationPrompts()
    source_name = "file_prompts.py:get_system_prompt()"
elif intent_type == "shell":
    from app.services.prompts.shell import ShellPrompts
    prompts_instance = ShellPrompts()
    source_name = "shell_prompts.py:get_system_prompt()"
elif intent_type == "network":
    from app.services.prompts.network import NetworkPrompts
    prompts_instance = NetworkPrompts()
    source_name = "network_prompts.py:get_system_prompt()"
elif intent_type == "desktop":
    from app.services.prompts.desktop import DesktopPrompts
    prompts_instance = DesktopPrompts()
    source_name = "desktop_prompts.py:get_system_prompt()"
else:
    from app.services.prompts.file import FileOperationPrompts
    prompts_instance = FileOperationPrompts()
    source_name = "file_prompts.py:get_system_prompt()"
```

> **注意**: 需要确认 `app/services/prompts/` 下是否存在对应的 prompt 类（ShellPrompts / NetworkPrompts / DesktopPrompts）。如果不存在，需要先创建，或者在 `try/except ImportError` 中 fallback。

---

### 问题10：`route_with_fallback` 置信度阈值 0.3 是 magic number

**严重程度**: 轻微

**当前代码**: `chat_router.py:301`

```python
if primary is not None and confidence >= 0.3:
```

CRSS 评分经过 `1 - 2^(-raw)` 归一化到 `[0, 1)`，0.3 意味着原始分约 0.5。但没有注释说明这个阈值的依据。

**影响**: 不易调优。如果未来 CRSS 评分算法变化，不知道这个阈值是否还合适。

**修复步骤**:

```python
# 在文件顶部定义常量（或从配置读取）
CRSS_CONFIDENCE_THRESHOLD = 0.3  # CRSS 信任阈值：归一化评分 >= 0.3 认为可信

# line 301 — 修改后
if primary is not None and confidence >= CRSS_CONFIDENCE_THRESHOLD:
```

可选：将阈值移到配置文件中，允许运行时调整。

---

## 修复优先级建议

| 优先级 | # | 问题 | 预估工时 | 风险 |
|--------|---|------|---------|------|
| P1 | 6 | PreprocessingPipeline 残留参数 | 0.5h | 低（纯清理，无副作用） |
| P1 | 7 | 冗余代码 | 0.1h | 低 |
| P2 | 4 | TimeReactAgent 缺少 LLMAdapter | 1h | 中（需确认 adapter 兼容性） |
| P2 | 9 | PromptLogger 模板映射不全 | 0.5h | 低（仅影响日志） |
| P2 | 10 | 置信度阈值硬编码 | 0.3h | 低 |
| P3 | 8 | 兜底超时未用配置 | 0.2h | 低 |
| P3 | 5 | 工具概要注入位置优化 | 1h | 中（需观察 LLM 行为变化） |
