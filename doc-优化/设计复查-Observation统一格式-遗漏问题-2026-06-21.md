# 设计复查：工具Observation统一格式设计遗漏问题

**创建时间**: 2026-06-21 00:19:41  
**编写人**: 小健  
**复查对象**: `doc-优化/工具Observation统一格式设计-融合方案-2026-06-20.md` v4.1  
**复查方法**: 对照代码现状逐条验证，5遍复核  
**状态**: 待修正

---

## 1 遗漏问题清单 【设计文档遗漏+解决方法】2026-06-21 00:19:41

### 1.1 P1：tool_retry_engine.py 未列入受影响文件

**问题**：5.9.8受影响文件表缺了 `tool_retry_engine.py`。该文件调用 `build_success/build_error`，且存在**二次包装**问题——工具函数返回新3字段result `{data, llm_data, other_data}` 后，retry_engine的L156-160会执行：

```python
return build_success(data=result, message="Tool execution succeeded", retry_count=engine.attempt_count)
```

新result没有顶层 `code` 字段，`result.get("code", "")` 返回空字符串，不以ERR_开头 → 走 `build_success(data=result)` → **3字段result被包进旧格式data里**，新builder产出的llm_data被埋在 `result.data.llm_data`，整条新管道断裂。

**影响范围**：
- L23: `from app.tools.tool_response import build_success, build_error` — 导入需改
- L66: `build_error(...)` — `_build_retry_error` 方法
- L91: `build_error(...)` — 工具未找到
- L101: `params.get("code") != "SUCCESS"` — 参数验证失败判断
- L153: `result.get("code", "").startswith("ERR_")` — 判断工具返回是否为错误
- L156-160: `build_success(data=result, ...)` — 成功时二次包装

**解决方法**：

retry_engine改为**透传工具返回的result**，不再二次包装：

1. 工具函数已返回 `build_result(...)` 产出的3字段result，retry_engine不应再包一层
2. 成功路径：直接 `return result`（工具已返回完整result）
3. 错误路径：retry_engine自身构建错误时，改用 `build_result("retry_engine", data=..., exec_code="error", ...)`
4. 判断是否需要重试：从 `result.llm_data.status.exec_code` 判断，替代 `result.get("code")`
5. retry_count：放入 `other_data`，不再作为顶层字段

**需在5.9.8受影响文件表中补充**：

| 文件 | 改动 |
|------|------|
| `tool_retry_engine.py` | 改为透传工具result；判断exec_code从 `llm_data.status.exec_code` 取；自身错误改用build_result；retry_count放入other_data |

---

### 1.2 P1：并行场景多result的observation合并规则缺失

**问题**：`action_handler.py:165-177` 只取 `results[0]` 的状态码/警告/附件，并行执行时其他工具的状态信息被丢弃。

```python
first_result = ctx.results[0] if ctx.results else {}
events.append(ToolStep(
    execution_status=first_result.get("code", ""),
    warning=first_result.get("warning"),
    attachment=first_result.get("attachment"),
    return_direct=first_result.get("return_direct", False),
))
```

**具体场景**：LLM同时调用 `read_text_file`（成功）和 `search_web`（warning），observation ToolStep只取read的结果，search的warning被丢弃。

Phase 2下Observation step只存一份 `llm_data` + 一份 `tool_result`，并行时两个工具各有一份，**合并规则完全未定义**。

**解决方法**：

并行场景下，Observation step的合并规则：

| 字段 | 合并规则 | 说明 |
|------|---------|------|
| `observation_text` | 多个obs_text用 `\n\n` 拼接 | 当前已有此逻辑（L163） |
| `llm_data` | 取exec_code最严重的那个（error > warning > success） | LLM需要知道最差状态 |
| `tool_result` | 合并为list：`[{"tool_name": "read_text_file", "data": ...}, {"tool_name": "search_web", "data": ...}]` | 前端按tool_name分tab展示 |
| `other_data.warning` | 收集所有非空warning，拼接 | 不丢失任何警告 |
| `other_data.attachment` | 收集所有非空attachment，合并为list | 不丢失任何附件 |
| `other_data.return_direct` | 任一为True则True | 任何一个工具要求直接返回就生效 |

**需在设计文档5.10节补充**：并行场景合并规则表。

---

### 1.3 P2：tool_executor.py 消费 llm_data.matches 路径断裂

**问题**：`tool_executor.py:26-27` 从旧result路径取matches：

```python
inner = result.get("data", {})
llm_matches = inner.get("llm_data", {}).get("matches", [])
```

新设计下result结构是 `{data, llm_data, other_data}`，tool_search的matches路径完全不同。5.9.8受影响文件表缺了 `tool_executor.py`。

**解决方法**：

1. tool_search的builder把matches放入 `data` 中：`data = {"matches": [...]}`
2. tool_executor改为从新路径取值：`result.get("data", {}).get("matches", [])`
3. matches不属于metrics（它是业务数据列表，不是关键数字指标），放data合理

**需在5.9.8受影响文件表中补充**：

| 文件 | 改动 |
|------|------|
| `tool_executor.py` | auto_inject_from_search 从 `result.data.matches` 取值，替代 `result.data.llm_data.matches` |

---

### 1.4 P2：5.9.6.2 format_llm_observation 实现与3.3/8.1格式定义不一致

**问题**：5.9.6.2节的实现代码（L1497-1518）与3.3节/8.1节的格式定义存在两处不一致：

**不一致1**：warning场景没有追加hint

5.9.6.2实现：
```python
elif exec_code == "warning":
    text = f"观察: {message} - {tool_zh}\n⚠ 警告: {status.get('detail', '')}"
    # ← 没有 hint
```

3.3节/8.1节定义：
```
观察: {status.message} - {action.tool_zh}
⚠ 警告: {status.detail}
结果: {summary}
详情: {format_data_detail(data)}
建议: {status.hint}          ← 有 hint
```

**不一致2**：error场景hint缺少"建议:"前缀

5.9.6.2实现：
```python
if exec_code == "error":
    hint = status.get("hint", "")
    if hint:
        text += f"\n{hint}"     # ← 缺少"建议:"前缀
```

3.3节/7.3节定义：
```
建议: {status.hint}            ← 有"建议:"前缀
```

**解决方法**：

5.9.6.2实现代码修正为：

```python
# warning场景追加hint
if exec_code == "warning":
    text = f"观察: {message} - {tool_zh}\n⚠ 警告: {status.get('detail', '')}"
    if summary:
        text += f"\n结果: {summary}"
    if data is not None and data != {}:
        detail = format_data_detail(data)
        if detail:
            text += f"\n详情:\n{detail}"
    hint = status.get("hint", "")
    if hint:
        text += f"\n建议: {hint}"    # ← 补上

# error场景hint加前缀
if exec_code == "error":
    hint = status.get("hint", "")
    if hint:
        text += f"\n建议: {hint}"    # ← 加"建议:"前缀
```

---

### 1.5 P2：5.9.7示例data含摘要数字，与4.2.1零重复原则矛盾——builder数据来源未解决

**问题**：5.9.7示例中，data包含 `file_path` 和 `line_count`：

```python
data={"content": content, "file_path": file_path, "line_count": len(content.splitlines())}
```

但4.2.1规范说data只放纯业务数据：`data = {"content": str}`。零重复原则要求line_count只在llm_data.metrics中出现。

**结构性矛盾**：
- builder需要从data中提取 `line_count`/`file_size` 放入metrics
- 但4.2.1说data中不应有这些字段
- `tool_params` 只有LLM调用参数，不含执行结果（line_count是执行后才知道的）
- builder不应重复执行业务逻辑（如再算一遍行数）
- builder只读data不修改data（5.9.2.3原则）

**解决方法**：

采用**"data先全量，builder提取后，build_result剥离"**策略：

1. 工具函数返回data时，**可以临时包含摘要数字**（如line_count、file_size）
2. builder从data中读取这些数字，放入llm_data.metrics
3. `build_result` 在调用builder后，**自动剥离data中与llm_data重复的字段**

具体实现：在 `build_result` 中增加一步去重：

```python
def build_result(tool_name, data=None, exec_code="success", ...):
    builder = _BUILDERS.get(tool_name, _default_builder)
    llm_data = builder(tool_name, data, exec_code, duration_ms, tool_params)
    
    # 去重：从data中移除已在llm_data.metrics中出现的字段
    if isinstance(data, dict) and llm_data.get("metrics"):
        metric_keys = set(llm_data["metrics"].keys())
        data = {k: v for k, v in data.items() if k not in metric_keys}
    
    result = {"data": data, "llm_data": llm_data, "other_data": other_data or {}}
    ...
```

**优势**：
- 工具函数写法自然（执行完把所有数据都放data里）
- builder从data读取数字放入metrics（不重复计算）
- build_result自动剥离重复字段（保证零重复输出）
- builder只读data不修改data（由build_result统一剥离）

**需在设计文档5.9.3.1的build_result实现中补充去重逻辑**。

---

### 1.6 P3：duration_ms重试场景含义未定义

**问题**：设计文档5.9.7说"工具函数内部加 `time.perf_counter()` 测duration_ms"，但重试场景下：
- 工具每次执行都测一次perf_counter，只有最后一次的duration_ms被保留
- retry_engine的重试间隔（指数退避sleep）是否计入？
- 总耗时（含所有重试）vs 最后一次执行耗时，哪个是duration_ms？

**解决方法**：

定义duration_ms为**最后一次工具执行的纯耗时**（不含重试间隔、不含重试次数）。理由：
- LLM需要知道"这次操作本身花了多久"，判断是否超时
- 重试是框架行为，不应混入工具执行耗时
- 总耗时信息可通过ToolStep的step级时间戳推算

如需总耗时，在other_data中加 `total_duration_ms` 字段，与 `duration_ms`（纯执行耗时）并存。

---

## 2 受影响文件补充表

原5.9.8受影响文件表需补充以下两行：

| 文件 | 改动 |
|------|------|
| `tool_retry_engine.py` | 透传工具result；判断exec_code从llm_data.status.exec_code取；自身错误改用build_result；retry_count放入other_data；删除build_success/build_error导入 |
| `tool_executor.py` | auto_inject_from_search从 `result.data.matches` 取值；删除旧路径 `result.data.llm_data.matches` |

---

## 3 设计文档修正清单

| 位置 | 修正内容 |
|------|---------|
| 5.9.8 受影响文件表 | 补充 `tool_retry_engine.py` 和 `tool_executor.py` |
| 5.9.6.2 format_llm_observation实现 | warning场景补hint；error场景hint加"建议:"前缀 |
| 5.9.3.1 build_result实现 | 补充data去重逻辑（剥离已在metrics中出现的字段） |
| 5.9.7 duration_ms规范 | 补充重试场景定义：duration_ms=最后一次纯执行耗时 |
| 5.10 Phase 2 | 补充并行场景合并规则表 |
| 5.4.9 基础工具 → tool_search | 补充tool_search的data格式：`data = {"matches": [...]}` |

---

**更新时间**: 2026-06-21 00:19:41  
**编写人**: 小健