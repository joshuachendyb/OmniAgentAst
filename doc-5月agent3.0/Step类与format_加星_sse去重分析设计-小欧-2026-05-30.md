# Step 类与 format_*_sse 去重分析设计

**创建时间**: 2026-05-30 21:03:22
**版本**: v0.1
**作者**: 小欧
**状态**: 初稿待确认

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v0.1 | 2026-05-30 21:03:22 | 小欧 | 初始版本，完整差异分析与去重方案 |

---

## 一、问题概述

**核心违规**：DRY（Don't Repeat Yourself），违法"10 大原则"。

当前系统存在 **两套独立的 dict 构建逻辑**：

```
第一套：Step 类体系（8 个 Step 类）
  └─ to_dict() — 将 Step 对象转为 dict，供保存 DB、前端渲染

第二套：format_*_sse 函数体系（8 个格式化函数）
  └─ 从 event dict 解构字段 → 重新拼装 → 传给 format_sse_event()
```

**问题本质**：同一份数据（type、content、timestamp、tool_name……）在两套逻辑中各拼一次。改一个必须同步改另一个，极易遗漏，已经出现过多处不一致。

**类比**：
> 就像一栋楼有两套图纸，每次改结构要同时改两套图纸——总有一天会忘了改另一套。

---

## 二、当前架构全景

### 2.1 数据流

```
agent.run_stream()
  → StepFactory.create_*_step(...)    ① 建 Step 对象
  → _emit_step(step)                  ② step.to_dict() → dict（第一遍拼装）
  → yield dict
↓
react_sse_wrapper.py / chat_stream_query.py / incident_handler.py
  → format_agent_sse(event_dict, ...) ③ 接收 dict
  → 解构 dict 字段                     ④ 拆开
  → 调用 format_*_sse(...)            ⑤ 重新拼装（第二遍拼装）
  → format_sse_event(type, step, data) → SSE 字符串
```

**重复点**：④→⑤ 与 ② 做的是同一件事——把同样的数据拼成 dict。

### 2.2 相关文件清单

| 文件 | 角色 | 行数 |
|------|------|------|
| `app/services/agent/steps/*.py` | 8 个 Step 类 + StepFactory | ~800 |
| `app/chat_stream/sse_formatter.py` | format_agent_sse + 8 个 format_*_sse | 403 |
| `app/services/react_sse_wrapper.py` | SSE 包装层（调用 format_agent_sse） | 627 |
| `app/services/chat_router.py` | 路由入口（直接调用 format_start_sse） | ~300 |
| `app/chat_stream/chat_stream_query.py` | 流式查询（直接调用 format_agent_sse） | ~420 |
| `app/chat_stream/incident_handler.py` | 事件处理（直接调用 format_agent_sse） | ~120 |
| `app/chat_stream/error_handler.py` | 错误处理（直接调用 format_error_sse） | ~60 |
| `app/chat_stream/chat_helpers.py` | 辅助函数（直接调用 format_final_sse） | ~50 |

---

## 三、逐类型差异分析

### 3.1 字段对照总表

| Step 类型 | Step.to_dict() 字段 | format_*_sse 字段 | 差异 |
|-----------|---------------------|-------------------|------|
| thought | content, thought, reasoning, tool_name, tool_params | 相同 | ✅ 精确匹配 |
| action_tool | tool_name, tool_params, execution_status, execution_result, execution_time_ms, action_retry_count, **summary, error_message** | tool_name, tool_params, execution_status, execution_result, execution_time_ms, action_retry_count | ⚠️ Step 多了 summary, error_message |
| observation | **tool_name, tool_params, observation, return_direct, execution_status, code, warning, attachment, next_actions, summary, error_message** | observation(JSON), code, timestamp | ❌ **形状完全不同** |
| chunk | content, is_reasoning | content, thought, reasoning, _thinking, is_reasoning, **model, provider**, timestamp | ❌ Step 缺 model, provider 等 |
| final | response, thought, model, provider | response, thought, model, provider, **is_finished, is_streaming, is_reasoning, display_name** | ⚠️ Step 缺 4 个字段 |
| error | error_type, error_message, recoverable, model, provider, reasoning, is_reasoning, context, retry_after | error_type, error_message, recoverable, retry_after, model, provider, **details, stack** | ⚠️ 部分重叠，各有独有字段 |
| incident | incident_value, message, content | 相同 | ✅ 精确匹配 |
| start | display_name, provider, model, task_id, user_message, security_check | 相同（去掉了 type, step） | ✅ 精确匹配 |

### 3.2 详细差异说明

#### 3.2.1 thought — 精确匹配

`ThoughtStep.to_dict()` 输出与 `format_thought_sse` 传参完全一致，可直接替换。

#### 3.2.2 action_tool — Step 多 2 个字段

`ActionToolStep.to_dict()` 包含 `summary` 和 `error_message`，这两个字段在设计上属于 observation 事件，不应该出现在 action_tool 的 SSE 中。

**处理**：to_dict() 输出后滤掉这两个字段，或直接接受（前端可能忽略多余字段）。

#### 3.2.3 observation — 形状完全不同

**当前 format_observation_sse** 的 output：
```json
{
  "type": "observation",
  "step": 3,
  "observation": { "summary": "xxx", "tool_name": "yyy", ... },
  "code": "SUCCESS"
}
```

**ObservationStep.to_dict()** 的 output：
```json
{
  "type": "observation",
  "step": 3,
  "tool_name": "yyy",
  "tool_params": {},
  "observation": "xxx",
  "return_direct": false,
  "execution_status": "success",
  "code": "SUCCESS",
  "summary": "xxx",
  ...
}
```

**差异根因**：format_observation_sse 把大部分字段**塞进 `observation` JSON 对象**里，只暴露 code 在外层；而 Step.to_dict() 是扁平展开。

**处理**：需要重映射——要么改 format_agent_sse 做扁平→嵌套转换，要么同步改前端解析。

#### 3.2.4 chunk — Step 缺 5 个字段

`ChunkStep` 只携带 `content` 和 `is_reasoning`，但 SSE 输出还需要 `thought, reasoning, _thinking, model, provider`。

**处理**：扩充 ChunkStep 字段以容纳完整信息，或在 format_agent_sse 中从其他来源补入。

#### 3.2.5 final — Step 缺 4 个字段

`FinalStep` 缺少 `is_finished, is_streaming, is_reasoning, display_name`。

**处理**：在 FinalStep 中增加这些字段，或由 format_agent_sse 补充。

#### 3.2.6 error — 各有独有字段

Step 有 `reasoning, is_reasoning, context`；SSE 有 `details, stack`。部分重叠但不完全对齐。

**处理**：统一字段集合——Step 补上 details/stack，SSE 补上 reasoning/is_reasoning/context，或接受差异。

#### 3.2.7 incident / start — 精确匹配

可直接替换，无副作用。

---

## 四、调用方分类

### 4.1 走 format_agent_sse 的（10 处）

| 位置 | 传入 type | 传入的额外字段 | 当前方式 |
|------|-----------|---------------|---------|
| `react_sse_wrapper.py:74` | interrupted | message | 改创建 IncidentStep |
| `react_sse_wrapper.py:107` | 各种（来自 Agent） | | Agent 直接 yield Step 对象 |
| `react_sse_wrapper.py:340` | interrupted | message | 改创建 IncidentStep |
| `chat_stream_query.py:217` | incident(retrying) | message, step | 改创建 IncidentStep |
| `chat_stream_query.py:254` | interrupted | message | 改创建 IncidentStep |
| `chat_stream_query.py:287` | chunk | content, step | Agent 已创建 ChunkStep |
| `chat_stream_query.py:415` | interrupted | message | 改创建 IncidentStep |
| `incident_handler.py:67` | interrupted | message | 改创建 IncidentStep |
| `incident_handler.py:101` | incident(resumed) | message | 改创建 IncidentStep |
| `incident_handler.py:111` | incident(paused) | message | 改创建 IncidentStep |

### 4.2 直接走 format_*_sse 的（3 处）

| 位置 | 函数 | 当前方式 | 改后方式 |
|------|------|---------|---------|
| `chat_router.py:266` | format_start_sse(start_data) | 传 start_data dict | 先用 StartStep 封装再走统一入口 |
| `error_handler.py:47` | format_error_sse(...) | 直接传参数 | 先用 ErrorStep 封装再走统一入口 |
| `chat_helpers.py:41` | format_final_sse(...) | 直接传参数 | 先用 FinalStep 封装再走统一入口 |

---

## 五、去重方案

### 5.1 总体目标

```
改前：
  两套 dict 构建 → 必须同步维护，容易遗漏

改后：
  唯一 dict 构建（Step.to_dict()）→ 改一处即可，消除重复
```

### 5.2 分阶段实施

#### 第一阶段：统一 format_agent_sse 接口（不删除旧函数）

**改动内容**：

1. 修改 `format_agent_sse` 签名，使其可以**同时接受 Step 对象或 dict**：
   ```python
   def format_agent_sse(
       event: Union[Dict[str, Any], ReasoningStep],
       step: Optional[int] = None,
       model: str = "",
       provider: str = ""
   ) -> str:
   ```
   - 如果 `event` 是 Step 对象：调用 `step.to_dict()` → 做字段映射 → `format_sse_event()`
   - 如果 `event` 是 dict：保持当前行为不变（兼容过渡期）

2. 在 format_agent_sse 内部，为每个 type 做**字段映射**：
   - observation：将扁平 dict 转为 `{observation: {...}, code, timestamp}` 格式
   - chunk：补 thought/reasoning/_thinking/model/provider
   - final：补 is_finished/is_streaming/is_reasoning/display_name
   - action_tool：过滤 summary/error_message
   - error：统一字段集合
   - thought/incident/start：直接使用 to_dict() 结果

3. 删除 8 个 `format_*_sse` 函数本体（逻辑已内联进 format_agent_sse）

4. 修改 3 处直接调用 `format_*_sse` 的地方，改为走统一入口

#### 第二阶段：Agent 直接 yield Step 对象

**改动内容**：

1. `base_react.py:_emit_step()` → 改为返回 Step 对象而不是 dict
2. `agent.run_stream()` 返回类型从 `AsyncGenerator[Dict]` → `AsyncGenerator[ReasoningStep]`
3. `react_sse_wrapper.py` 接收 Step 对象 → 传给新的 format_agent_sse

#### 第三阶段（可选）：精简 Step 字段

- 统一 observation/action_tool 的字段设计
- 消除 format_agent_sse 内的字段映射逻辑，实现真正的一步到位

### 5.3 各类型字段映射规则

| 类型 | 输入（Step.to_dict 产出） | 输出（传给 format_sse_event） |
|------|--------------------------|-------------------------------|
| thought | 直接使用 | 不变 |
| action_tool | 过滤掉 summary, error_message | 不变 |
| observation | 重映射：`{observation: {...所有字段...}, code, timestamp}` | observation 嵌套结构 |
| chunk | 补 model, provider, thought, reasoning, _thinking | 扩充字段 |
| final | 补 is_finished, is_streaming, is_reasoning, display_name | 扩充字段 |
| error | 统一：取交集 + 补漏 | 标准 error 格式 |
| incident | 直接使用 | 不变 |
| start | 直接使用 | 不变 |

### 5.4 改动文件清单

| 阶段 | 文件 | 改动量 | 风险 |
|------|------|--------|------|
| 一 | `sse_formatter.py` | 重写 format_agent_sse，删除 8 个函数 | 中 |
| 一 | `chat_router.py` | 改 1 处 format_start_sse 调用 | 低 |
| 一 | `error_handler.py` | 改 1 处 format_error_sse 调用 | 低 |
| 一 | `chat_helpers.py` | 改 1 处 format_final_sse 调用 | 低 |
| 一 | `sse_formatter.py __all__` | 删除 8 个导出 | 低 |
| 二 | `base_react.py` | _emit_step 改返回 Step 对象 | 中 |
| 二 | `react_sse_wrapper.py` | 接收 Step 对象 | 中 |
| 二 | 各 Agent 子类 | 如有直接处理 dict 的需改 | 低 |
| 二 | `chat_stream_query.py` | 改为创建 Step 对象 | 中 |
| 二 | `incident_handler.py` | 改为创建 Step 对象 | 低 |

---

## 六、风险评估

### 6.1 兼容性影响

| 风险项 | 影响范围 | 概率 | 缓解措施 |
|--------|---------|------|---------|
| observation 格式变化 | 前端解析 observation SSE | 高 | 第一阶段保留映射，与前端同步 |
| chunk 字段变化 | 前端解析 chunk SSE | 中 | 加字段而非删字段，前端只读需要的 |
| Step 对象提前暴露 | 所有 yield 消费者 | 低 | 第一阶段兼容 dict，第二阶段再改 |
| 调用方遗漏 | 测试覆盖率不足时 | 中 | 完整回归测试 |

### 6.2 测试验证

每阶段完成后必须运行：

```bash
pytest -x --tb=short  # 单元测试全部通过
```

并手动验证流式对话（start → thought → action_tool → observation → chunk → final）完整链路。

---

## 七、决策建议

**建议分两阶段实施**：

> **第一阶段**（低风险，优先做）：format_agent_sse 统一接口，删除 8 个 format_*_sse，消除 DRY 违规。
>
> **第二阶段**（中风险）：Agent yield Step 对象，彻底简化数据流。

第一阶段改动集中在 sse_formatter.py + 3 个直接调用方，不涉 Agent 内部逻辑，测试回归风险可控。

---

**文档完成时间**: 2026-05-30 21:03:22
**作者**: 小欧
