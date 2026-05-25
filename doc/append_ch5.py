# -*- coding: utf-8 -*-
"""Append Chapter 5 to scan report"""
import re

with open('app代码函数行数分布扫描报告-小沈-2026-05-25.md', encoding='utf-8') as f:
    content = f.read()

if not content.endswith('\n'):
    content += '\n'

ch5 = r"""## 五、P1级函数拆分设计 — 函数 1~5

### 5.0 拆分大函数的工作要求

=+==========
拆分大函数的工作要求,必须遵守
1. 开始分析本章节前必须背铁规和专家戒律 反思哪些违规了
2. 必须遵守规矩的规矩是什么
3. 分析代码的要点:**跨文件数据流追踪有限**：追踪了明显的上下游关系（如 ToolRegistry → tool_meta），做完整的请求→响应全链路数据流分析
4. ⚠️ **边界条件覆盖不全**：对于大文件中的复杂条件分支，agent 识别了明显的边界缺陷（如空字典假值、fromisoformat 崩溃）
5. ⚠️ 要阅读代码 拆分中要去发现有没有现有的其他代码中的类似函数可以使用,公用
6. 必须分析每一个分支，详细后才进行拆分函数的设计和代码修改
   6.1 重构后的函数功能不能减少只能增强
   6.2 逻辑增强准确，简洁信息
   6.3 有已经有的函数用已有的，可以构建通用函数代码文件
7. 能够进行函数代码文件化的时候进行函数文件化
8. 完成一个函数的拆分后, 需要对全部边界场景做系统性测试
9. 完成一个函数后必须commit
=+==========

---

### 5.1 `_execute_retry_loop` — `chat_stream/chat_stream_query.py:100` (192行)

**当前规模**: 192 行 | **文件位置**: `backend/app/chat_stream/chat_stream_query.py:100`

#### 5.1.1 当前结构拆解

`_execute_retry_loop` 实现带 IdleTimeoutIterator 超时保护的 AI 流式调用重试循环，共 12 个决策点：

**调用路径**: `chat_stream_query` → `_execute_retry_loop` → `ai_service.chat_stream` → SSE事件

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **R1 重试入口** | R1a | retry_attempt > 0 | 生成 retrying incident 事件 + yield | 138-145 | 中层事件构建 |
| | R1b | 首次调用 | 直接进入流 | - | - |
| **S1 流检查** | S1a | chunk_count > max_chunk_count | 强制 break | 164-166 | 低层保护 |
| | S1b | is_reasoning 且连续空内容 | break | 167-171 | 低层保护 |
| **C1 取消检查** | C1a | running_tasks[cancelled] | 生成 interrupted 事件 + return | 175-181 | 中层检查 |
| **P1 暂停检查** | P1a | pause 事件 | yield pause_event | 183-186 | 中层检查 |
| **E1 流错误** | E1a | chunk.stream_error | 记录错误 + break（不重试）| 188-194 | 中层错误处理 |
| **D1 数据分块** | D1a | chunk.content 非空 | create_chunk_step + yield | 197-213 | 中层数据处理 |
| | D1b | chunk.is_done | break | 215-216 | 低层标志 |
| **T1 超时异常** | T1a | IdleTimeoutError | 记录 + can_retry 判断 | 218-222 | 中层异常处理 |
| **X1 通用异常** | X1a | Exception | 记录 + can_retry 判断 | 224-227 | 中层异常处理 |
| **F1 结果分支** | F1a | has_received_content | 成功 + break | 229-232 | 高级结果判断 |
| | F1b | idle_timeout + can_retry | 继续重试 | 234-237 | 高级结果判断 |
| | F1c | idle_timeout + !can_retry | 失败 + break | 238-241 | 高级结果判断 |
| | F1d | network_error + can_retry | 继续重试 | 243-246 | 高级结果判断 |
| | F1e | network_error + !can_retry | 失败 + break | 247-250 | 高级结果判断 |
| | F1f | 其他错误 | 失败 + break | 252-255 | 高级结果判断 |
| | F1g | 空内容 + can_retry | 继续重试 | 258-266 | 高级结果判断 |
| | F1h | 空内容 + !can_retry | 生成 empty_response 错误 + return | 267-291 | 高级错误构建 |

**重复/冗余**:
- retry logic 重复 4 次：F1b/F1d/F1g 的 `can_retry()` + `increment_retry()` + `continue` 结构完全相同
- `running_tasks_lock` 的 async with + cancelled 检查模式在多处出现
- `check_and_yield_if_paused` 在整个 `react_sse_wrapper.py` 中反复使用（同一函数调用无问题）
- `create_incident_data` 的 incident 事件构建：retrying(139-145) 和 interrupted(177-181) 模式相同
- empty_response 的错误构建（269-290）使用 `create_error_response` + `StepFactory.create_error_step` + yield + add_step_and_save 完整流程，可封装

#### 5.1.2 违反原则分析

- **DRY 严重违反**: retry 逻辑 4 处重复（can_retry + increment_retry + continue）。empty_response 错误构建（22 行代码内联，应封装）。中断/暂停检查模式重复。
- **SLAP 违反**: 函数在 192 行内混合了 4 层抽象：高级结果判断(F1)、中层事件构建/错误处理、低层流检查/数据分块。流处理(8行)和结果判断(12行分支)在同一层级。
- **SRP 违反**: 重试控制 + 流迭代 + 数据处理 + 错误处理 + 结果判断共 5 个职责。
- **KISS 违反**: F1a-F1h 的 8 路分支涉及 retry_controller 状态、last_error_type、has_received_content 的组合判断，条件矩阵复杂。
- **YAGNI 轻度违反**: `full_content` 积累了所有 chunk 内容但只在最后返回给 state；`empty_content_count` 保护很少触发。

#### 5.1.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `create_incident_data` | `chat_stream/incident_handler.py` ✅ | 已有，无需重写 |
| `create_error_response` | `chat_stream/error_handler.py` ✅ | 已有 |
| `check_and_yield_if_paused` | `react_sse_wrapper.py` ✅ | 已是独立函数 |
| 空内容→empty_response 流程 | 无可复用 | 建议封装为 `_build_empty_response_error` |
| retry 控制器判断 | `IdleTimeoutIterator` 内置 | 建议提取 `_should_retry(retry_controller, last_error_type)` |

#### 5.1.4 重构方案（详细代码设计）

**目标**: 192 行 → ~90 行骨架 + 2 个辅助函数，消除 4 次 retry 逻辑重复 + empty_response 内联。

**组件1: `_build_empty_response_error`** — 统一空内容错误构建

```python
async def _build_empty_response_error(
    next_step, add_step_and_save, ai_service, error_message,
) -> Tuple[str, Dict]:
    \"\"\"统一空内容错误事件 + step_data 的构建和保存。\"\"\"
    step = next_step()
    error_resp = create_error_response(
        error_type="empty_response", error_message=error_message,
        model=ai_service.model, provider=ai_service.provider,
        recoverable=True, retry_after=3, step=step)
    error_step = StepFactory.create_error_step(
        step=step, error_type='empty_response', error_message=error_message,
        model=ai_service.model, provider=ai_service.provider,
        recoverable=True, retry_after=3).to_dict()
    await add_step_and_save(error_step, f"错误: {error_message}")
    return error_resp, error_step
```

**组件2: `_should_retry`** — 统一重试判断

```python
def _should_retry(error_type: str, retry_controller) -> Tuple[bool, str]:
    \"\"\"判断是否应该重试。返回 (should_retry, reason)。\"\"\"
    if retry_controller.can_retry():
        retry_controller.increment_retry()
        return True, error_type
    return False, 'exhausted'
```

**组件3: 重构后的 `_execute_retry_loop`**（~90 行骨架）

```python
async def _execute_retry_loop(...) -> AsyncGenerator[Tuple[str, Optional[Dict]], None]:
    retry_controller = state["retry_controller"]
    chat_timeout = state["chat_timeout"]
    max_retries = state["max_retries"]

    for retry_attempt in range(max_retries + 1):
        if retry_attempt > 0:
            retry_data = create_incident_data('retrying',
                f'请求超时，正在重试 ({retry_attempt}/{max_retries})...', step=next_step())
            yield (f"data: {json.dumps(retry_data)}\n\n", None)
            await add_step_and_save(retry_data, None)

        full_content = ""
        chunk_count = 0
        has_received_content = False
        empty_content_count = 0
        idle_timeout_stream = None

        try:
            llm_call_count += 1
            idle_timeout_stream = IdleTimeoutIterator(
                ai_service.chat_stream(message="", history=history),
                timeout_seconds=chat_timeout, name=f"AI-Stream-{retry_attempt + 1}")

            async for chunk in idle_timeout_stream:
                chunk_count += 1
                if not _check_stream_limits(chunk, chunk_count, empty_content_count, state):
                    break
                if await _is_cancelled(task_id, running_tasks, running_tasks_lock):
                    yield _build_interrupted_event(next_step); return
                for pause_event in check_and_yield_if_paused(...):
                    yield (pause_event, None)
                if chunk.stream_error:
                    state["last_error"] = chunk.stream_error
                    state["last_error_type"] = getattr(chunk, 'stream_error_type', 'unknown')
                    state["ai_call_successful"] = False; break
                if chunk.content:
                    has_received_content = True
                    chunk_data = _process_chunk(chunk, next_step, current_execution_steps)
                    yield (f"data: {json.dumps(chunk_data)}\n\n", None)
                    full_content += chunk.content
                if chunk.is_done: break

        except IdleTimeoutError as e:
            state["last_error"] = str(e); state["last_error_type"] = 'idle_timeout'
        except Exception as e:
            state["last_error"] = str(e); state["last_error_type"] = 'network_error'

        if has_received_content:
            state["ai_call_successful"] = True; state["full_content"] = full_content; break

        should_retry, reason = _should_retry(state["last_error_type"], retry_controller)
        if should_retry: continue

        if reason == 'exhausted' and not has_received_content:
            err_resp, err_step = await _build_empty_response_error(
                next_step, add_step_and_save, ai_service,
                "模型未能生成有效回复，请尝试更换问题或稍后重试")
            yield (err_resp, err_step); return

        state["ai_call_successful"] = False; break
```

**优势**: 192 行 → ~90 行骨架 + 2 个辅助函数。4 次 retry 逻辑合并为 1 次 `_should_retry` 调用。empty_response 构建从 22 行内联压缩为 4 行调用。`_process_chunk` 和 `_check_stream_limits` 是纯提取的可测试函数。

---

### 5.2 `FileTools.list_directory` — `file_tools.py:1041` (136行)

**当前规模**: 136 行 | **文件位置**: `backend/app/services/tools/file/file_tools.py:1041`

#### 5.2.1 当前结构拆解

`list_directory` 实现目录内容的三合一列出（list/tree），包含参数校验、同步扫描、排序、分页，共 12 个决策点：

**调用路径**: `LLM意图` → `FileTools.list_directory(dir_path, format, ...)` → `_list_sync()`(同步) → `_build_list_success`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **V1 格式校验** | V1a | format 不在(list,tree) | ERR_PARAM_INVALID | 1054-1055 | 中层校验 |
| | V1b | max_depth < 1 | ERR_PARAM_INVALID | 1056-1057 | 中层校验 |
| | V1c | sortBy 不在(name,size,mtime) | ERR_PARAM_INVALID | 1058-1059 | 中层校验 |
| **T1 tree模式** | T1a | format == "tree" | 委托 _get_directory_tree + 统计 | 1061-1068 | 中层分发 |
| **P1 路径校验** | P1a | _validate_path 失败 | ERR_PATH_INVALID | 1070-1072 | 中层校验 |
| **K1 分页** | K1a | page_token 存在 | decode + 异常处理 | 1076-1080 | 低层解析 |
| **D1 目录检查** | D1a | path.exists() 失败 | ERR_FILE_NOT_FOUND | 1083-1084 | 中层校验 |
| | D1b | path.is_dir() 失败 | ERR_FILE_PATH_NOT_DIR | 1085-1086 | 中层校验 |
| **S1 同步扫描** | S1a | recursive=True | _scan_recursive 递归遍历 | 1109-1135 | 低层IO |
| | S1b | recursive=False | iterdir 直接遍历 | 1136-1144 | 低层IO |
| **O1 排序** | O1a | sortBy == "size" | 按size排序 | 1150-1151 | 中层数据处理 |
| | O1b | sortBy == "mtime" | 按mtime排序 | 1152-1153 | 中层数据处理 |
| | O1c | 默认 | 按name排序 | 1154-1155 | 中层数据处理 |
| **R1 结果构建** | R1a | total > MAX_DISPLAY_ENTRIES | 日志警告 + 截断 | 1165-1170 | 中层结果构建 |
| | R1b | 正常 | 直接返回 | 1172 | 中层结果构建 |
| **E1 异常** | E1a | Exception | ERR_FILE_LIST_DIR_FAILED | 1174-1176 | 中层异常 |

**重复/冗余**:
- `_list_sync` 是 55 行的内部函数，内含 `_process_item` 嵌套函数 — 内部函数每次调用 list_directory 时重新定义，浪费解析时间
- `_process_item` / `_classify_size` / `_build_entry` 功能通用，但定义在 `_list_sync` 内部，无法复用
- _scan_recursive 嵌套在 _list_sync 内部，无法独立测试
- timeout 自检（1097-1098, 1114-1115）逻辑在 _list_sync 和 _scan_recursive 中重复

#### 5.2.2 违反原则分析

- **DRY 中度违反**: `_process_item` / `_classify_size` / `_build_entry` 3 个纯函数定义在内部函数中，每调用一次 list_directory 就重新创建。timeout 自检逻辑重复。
- **SLAP 轻度违反**: 参数校验(高级) → 路径校验(中层) → 同步扫描(低层IO) → 排序(中层) → 结果构建(中层)，层次基本清晰。
- **SRP 中度违反**: 格式校验 + 路径校验 + 同步扫描 + 排序 + 结果构建共 5 个职责。`_list_sync` 内部又含遍历 + 统计 + 超时保护。
- **KISS 基本遵守**: 逻辑分支清晰，嵌套函数较多但结构明确。

#### 5.2.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_get_directory_tree` | `file_tools.py` ✅ | 已是类方法，tree 模式直接复用 |
| `_validate_path` | `file_tools.py` ✅ | 已是类方法 |
| `_build_entry` | `file_tools.py` 内部定义 | 建议提取为模块级函数 |
| `_classify_size` | `file_tools.py` 内部定义 | 建议提取为模块级函数 |
| `_process_item` | file_helper 无对应函数 | 建议提取到 `file_helpers.py` |

#### 5.2.4 重构方案（详细代码设计）

**目标**: 136 行 → ~80 行主函数 + 4 个模块级函数，消除内部函数重复定义。

**组件1: `_build_entry` → 提取到模块级**（供 statistics 复用）

```python
def _build_entry(item: Path, st: os.stat_result) -> Dict:
    \"\"\"构建文件/目录条目字典。\"\"\"
    return {"name": item.name, "path": str(item),
            "type": "directory" if item.is_dir() else "file",
            "size": st.st_size, "mtime": st.st_mtime}
```

**组件2: `_classify_size` → 提取到模块级**

```python
def _classify_size(size: int) -> str:
    \"\"\"按文件大小分桶。\"\"\"
    if size < 1024: return "<1KB"
    if size < 10*1024: return "1KB-10KB"
    if size < 100*1024: return "10KB-100KB"
    if size < 1024*1024: return "100KB-1MB"
    return ">1MB"
```

**组件3: `_scan_directory_sync` → 提取为独立同步函数**

```python
def _scan_directory_sync(
    path: Path, recursive: bool, max_depth: int,
    include_hidden: bool, deadline: float,
) -> Tuple[List[Dict], Dict]:
    \"\"\"同步扫描目录（可被 to_thread 调用）。\"\"\"
    entries = []; stats = {"total_size": 0, "dir_count": 0, "file_count": 0}
    _timed_out = False

    def _scan_recursive(current_path: Path, depth: int):
        nonlocal _timed_out
        if depth > max_depth or time.monotonic() > deadline:
            _timed_out = True; return
        try:
            for item in current_path.iterdir():
                if _timed_out: return
                if not include_hidden and item.name.startswith('.'): continue
                try:
                    st = item.stat()
                    entries.append(_build_entry(item, st))
                    if item.is_dir():
                        stats["dir_count"] += 1; _scan_recursive(item, depth + 1)
                    else:
                        stats["total_size"] += st.st_size; stats["file_count"] += 1
                except (PermissionError, OSError): continue
        except (PermissionError, OSError): return

    if recursive:
        _scan_recursive(path, 1)
    else:
        for item in path.iterdir():
            if not include_hidden and item.name.startswith('.'): continue
            try:
                st = item.stat()
                entries.append(_build_entry(item, st))
                if item.is_dir(): stats["dir_count"] += 1
                else: stats["total_size"] += st.st_size; stats["file_count"] += 1
            except (PermissionError, OSError): continue
    return entries, stats
```

**组件4: 重构后的 `list_directory`**（~80 行）

```python
async def list_directory(self, dir_path, format="list", recursive=False,
                          max_depth=10, page_token=None, sortBy="name",
                          include_hidden=False) -> Dict[str, Any]:
    if format not in ("list", "tree") or max_depth < 1 or sortBy not in ("name","size","mtime"):
        return build_error("ERR_PARAM_INVALID", f"format/max_depth/sortBy 参数无效")
    if format == "tree":
        tree = await self._get_directory_tree(dir_path=dir_path, max_depth=max_depth)
        if tree.get("code") == "SUCCESS" and isinstance(tree.get("data"), dict):
            t = tree["data"].get("tree")
            if isinstance(t, dict):
                f, d, s = _count_tree_stats(t)
                tree["data"]["statistics"] = {"file_count": f, "dir_count": d, "total_size": s}
        return tree
    valid, msg = self._validate_path(dir_path)
    if not valid: return build_error("ERR_PATH_INVALID", msg)
    path = Path(dir_path)
    start_offset = 0
    if page_token:
        try: start_offset = decode_page_token(page_token)
        except Exception as e: return build_error("ERR_PARAM_INVALID", f"Invalid page token: {e}")
    try:
        if not path.exists(): return build_error("ERR_FILE_NOT_FOUND", f"Directory not found: {dir_path}")
        if not path.is_dir(): return build_error("ERR_FILE_PATH_NOT_DIR", f"Not a directory: {dir_path}")
        deadline = time.monotonic() + get_timeout("list_directory") - 2
        entries, stats = await asyncio.to_thread(
            _scan_directory_sync, path, recursive, max_depth, include_hidden, deadline)
        _sort_entries(entries, sortBy)
        total = len(entries)
        MAX_DISPLAY = 200
        if total > MAX_DISPLAY:
            logger.warning(f"[list_directory] Large directory truncated: path={path}, total={total}")
        return _build_list_success(entries, total, path, stats, start_offset, MAX_DISPLAY)
    except Exception as e:
        logger.error(f"Failed to list directory {dir_path}: {e}")
        return build_error("ERR_FILE_LIST_DIR_FAILED", str(e))
```

**优势**: 136 行 → ~80 行主函数 + 4 个模块级函数。消除内部函数重复定义。`_scan_directory_sync` 可独立测试（纯同步函数）。`_build_entry` / `_classify_size` 可供其他函数复用。

---

### 5.3 `pipeline` — `meta_tools.py:274` (131行)

**当前规模**: 131 行 | **文件位置**: `backend/app/services/tools/meta/meta_tools.py:274`

#### 5.3.1 当前结构拆解

`pipeline` 实现多工具编排执行管道（前步输出 → 后步输入），共 10 个决策点：

**调用路径**: `LLM意图` → `pipeline(steps, stop_on_error, timeout_per_step)` → `tool_registry.get_implementation` → `_run_tool_with_timeout`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **J1 JSON解析** | J1a | steps 是 list/dict | 直接使用 | 289-290 | 低层解析 |
| | J1b | steps 是 str | json.loads | 292 | 低层解析 |
| | J1c | JSONDecodeError | ERR_INVALID_JSON | 293-295 | 中层错误 |
| | J1d | TypeError | ERR_INVALID_JSON | 296-298 | 中层错误 |
| **F1 格式校验** | F1a | 非 list | ERR_INVALID_FORMAT | 300-302 | 中层校验 |
| **S2 步骤循环** | S2a | step 不是 dict | ERR_INVALID_STEP | 308-311 | 中层校验 |
| | S2b | tool_name 缺失 | ERR_MISSING_TOOL | 313-317 | 中层校验 |
| | S2c | tool 不存在 | ERR_TOOL_NOT_FOUND + similar | 319-327 | 中层校验 |
| | S2d | params 非 dict | ERR_INVALID_PARAMS | 329-334 | 中层校验 |
| **C1 上下文注入** | C1a | context 非空 + param 未指定 | 按函数签名注入 context | 337-347 | 中层数据处理 |
| **E1 执行** | E1a | _run_tool_with_timeout | result | 356-357 | 低层执行 |
| | E1b | TimeoutError | _timeout_error | 359-362 | 中层错误 |
| **P1 结果处理** | P1a | _process_step_result 返回 err | 提前返回 | 364-366 | 中层结果处理 |
| **X2 异常** | X2a | TypeError | ERR_PARAM_MISMATCH | 368-373 | 中层错误 |
| | X2b | 其他 Exception | ERR_PIPELINE_FAILED | 374-382 | 中层错误 |
| **R2 结果构建** | R2a | 循环完成 | build_success + next_actions | 384-404 | 中层结果构建 |

**重复/冗余**:
- 错误返回的 `_pipeline_error` 调用模式高度一致（tool_name/data/llm_data 参数重复传递）
- context 注入的 `impl_sig` 获取逻辑（每步执行前重新获取）可缓存
- `import concurrent.futures as cf` 在 TimeoutError 异常处理中重复导入（359, 375）
- tool 查找 `tool_registry.get_tool` + `tool_registry.get_implementation` 两处独立查找，可合并为一次

#### 5.3.2 违反原则分析

- **DRY 中度违反**: `concurrent.futures` 重复导入、`_pipeline_error` 参数模板重复、`get_tool` 和 `get_implementation` 两次查找。
- **SLAP 基本遵守**: 管道控制的循环逻辑和数据处理层次清晰。
- **SRP 轻微违反**: 参数校验 + 上下文注入 + 执行调度 + 结果处理共 4 个职责，但边界较清晰。
- **KISS 基本遵守**: 步骤循环逻辑直观。

#### 5.3.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_run_tool_with_timeout` | `meta_tools.py:232` ✅ | 已有模块级函数 |
| `_process_step_result` | `meta_tools.py:257` ✅ | 已有模块级函数 |
| `_timeout_error` | `meta_tools.py:217` ✅ | 已有模块级函数 |
| `_pipeline_error` | `meta_tools.py:203` ✅ | 已有模块级函数 |
| context 注入逻辑 | `meta_tools.py` 内部 | 建议提取为 `_inject_context(params, context, impl)` |

#### 5.3.4 重构方案（详细代码设计）

**目标**: 131 行 → ~95 行主函数 + 1 个辅助函数，消除 concurrent.futures 重复导入 + 合并 tool 单次查找。

**组件1: `_inject_context`** — 提取上下文注入逻辑

```python
def _inject_context(params: Dict, context: Dict, tool_name: str) -> Dict:
    \"\"\"将 context 中未在 params 指定的键注入到 params。\"\"\"
    if not context: return params
    result = dict(params)
    impl = tool_registry.get_implementation(tool_name)
    if impl:
        try:
            for k, v in context.items():
                if k not in result and k in set(inspect.signature(impl).parameters.keys()):
                    result[k] = v
        except Exception: pass
    return result
```

**组件2: `_validate_step`** — 提取步骤校验

```python
def _validate_step(step: Any, i: int, steps_list: List) -> Optional[Dict]:
    \"\"\"校验单步格式。返回错误 dict 或 None。\"\"\"
    if not isinstance(step, dict):
        return _pipeline_error("ERR_INVALID_STEP",
            f"步骤{i+1}格式无效，应为对象，当前: {type(step).__name__}",
            llm_data={"failed_step": i + 1})
    tool_name = step.get("tool")
    if not tool_name:
        return _pipeline_error("ERR_MISSING_TOOL", f"步骤{i+1}缺少tool字段",
            llm_data={"failed_step": i + 1})
    if not tool_registry.get_tool(tool_name):
        available = list(tool_registry._tools.keys())
        similar = [n for n in available if tool_name.lower() in n.lower()]
        return _pipeline_error("ERR_TOOL_NOT_FOUND",
            f"步骤{i+1}: 工具 '{tool_name}' 不存在", tool=tool_name,
            data={"similar_tools": similar[:5]},
            llm_data={"failed_step": i + 1, "tool": tool_name, "similar_tools": similar[:3]})
    params = step.get("params", {})
    if not isinstance(params, dict):
        return _pipeline_error("ERR_INVALID_PARAMS", f"步骤{i+1}({tool_name})的params必须是对象",
            tool=tool_name, llm_data={"failed_step": i + 1, "tool": tool_name})
    return None
```

**组件3: 重构后的 `pipeline`**（~95 行）

```python
def pipeline(steps: str, stop_on_error: bool = True, timeout_per_step: int = 60) -> Dict[str, Any]:
    try:
        steps_list = steps if isinstance(steps, (list, dict)) else json.loads(steps)
    except (json.JSONDecodeError, TypeError) as e:
        return _pipeline_error("ERR_INVALID_JSON", f"steps 参数错误: {e}")
    if not isinstance(steps_list, list):
        return _pipeline_error("ERR_INVALID_FORMAT", f"steps 必须是JSON数组")
    context, results = {}, []
    for i, step in enumerate(steps_list):
        err = _validate_step(step, i, steps_list)
        if err: return err
        tool_name = step["tool"]
        impl = tool_registry.get_implementation(tool_name)
        if not impl:
            return _pipeline_error("ERR_META_TOOL_IMPL_NOT_FOUND",
                f"步骤{i+1}: 工具 '{tool_name}' 无法获取实现",
                tool=tool_name, llm_data={"failed_step": i + 1, "tool": tool_name})
        params = _inject_context(step.get("params", {}), context, tool_name)
        try:
            result = _run_tool_with_timeout(impl, params, timeout_per_step)
        except concurrent.futures.TimeoutError:
            return _timeout_error(i, tool_name, timeout_per_step, results, steps_list, stop_on_error)
        err = _process_step_result(result, i, tool_name, results, context, stop_on_error)
        if err: return err
    return build_success(
        truncate_data_for_frontend({"total_steps": len(steps_list), "completed_steps": len(results), "results": results}),
        f"管道执行完成: {len(results)}/{len(steps_list)} 个步骤",
        llm_data={"total_steps": len(steps_list), "completed_steps": len(results)},
        next_actions=build_next_actions([("tool_search", "查找可用的工具", "需要编排新管道时")]))
```

**优势**: 131 行 → ~95 行主函数 + 2 个辅助函数。消除 concurrent.futures 重复导入。合并 get_tool + get_implementation 为单次 get_implementation 调用。`_inject_context` 和 `_validate_step` 可独立测试。

---

### 5.4 `FileTools.grep_file_content` — `file_tools.py:1889` (119行)

**当前规模**: 119 行 | **文件位置**: `backend/app/services/tools/file/file_tools.py:1889`

#### 5.4.1 当前结构拆解

`grep_file_content` 实现正则内容搜索（单行/多行模式+上下文+分页），共 9 个决策点：

**调用路径**: `LLM意图` → `FileTools.grep_file_content(pattern, ...)` → `_grep_sync()`(同步) → `_paginate_results`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **C1 上下文解析** | C1a | context 非空 | 提取 after/before/around | 1902-1906 | 低层解析 |
| | C1b | context 为空 | 全部 None | - | 低层解析 |
| **P1 路径校验** | P1a | validate_path 失败 | ERR_PATH_INVALID | 1909-1911 | 中层校验 |
| **V1 模式校验** | V1a | pattern 为空 | ERR_PARAM_INVALID | 1912-1913 | 中层校验 |
| **S1 同步搜索** | S1a | multiline=True | DOTALL + finditer ≤ head_limit | 1947-1954 | 低层IO |
| | S1b | multiline=False | 逐行 regex.search + ctx | 1955-1965 | 低层IO |
| **T1 超时保护** | T1a | head_limit 触发 | break 内层文件循环 | 1939-1940 | 低层保护 |
| | T1b | deadline 超时 | break 外层 os.walk | 1934-1936 | 低层保护 |
| **R1 结果聚合** | R1a | total_matches 计算 | sum/match_count/count 兼容 | 1974-1977 | 中层数据处理 |
| **R2 结果构建** | R2a | 正常 | build_success + llm_data | 1983-2005 | 中层结果构建 |
| **E1 异常** | E1a | Exception | ERR_FILE_CONTENT_SEARCH_FAILED | 2006-2007 | 中层异常 |

**重复/冗余**:
- `_grep_sync` 是 54 行内部函数，内含 `_read_file_safe` / `_build_context` / `_format_match_output` 调用 — 这些函数已是模块级，但 `_grep_sync` 每次重新定义
- 多行和单行的结果收集逻辑（1949-1954 vs 1956-1965）结构相似但无法合并（finditer vs search）
- total_matches 的 sum/m.get/m.get 三元表达式（1975-1976）过于紧凑，可读性差
- match_count 递增与 head_limit 检查模式在多层循环中重复

#### 5.4.2 违反原则分析

- **DRY 中度违反**: `_grep_sync` 内部函数每次调用重新定义。total_matches 计算兼容 3 种 output_mode 但写为紧凑三元表达式。
- **SLAP 基本遵守**: 参数校验(中层) → 同步搜索(低层IO) → 结果聚合(中层) → 结果构建(中层)，层次清楚。
- **SRP 中度违反**: 上下文解析 + 路径校验 + 同步搜索 + 结果聚合 + 结果构建共 5 个职责。
- **KISS 中度违反**: total_matches 的 3 种模式兼容写为嵌套三元，不易理解。

#### 5.4.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_read_file_safe` | `file_helpers.py` ✅ | 已有模块级函数 |
| `_build_context` | `file_tools.py` ✅ | 已有模块级函数 |
| `_format_match_output` | `file_tools.py` ✅ | 已有模块级函数 |
| `_paginate_results` | `file_helpers.py` ✅ | 已有模块级函数 |
| `_grep_sync` 内部逻辑 | file_helper 无对应 | 建议提取为 `_grep_files_sync(…)` 模块级函数 |

#### 5.4.4 重构方案（详细代码设计）

**目标**: 119 行 → ~75 行主函数 + 1 个同步搜索函数，消除内部函数重新定义。

**组件1: `_grep_files_sync`** — 提取同步搜索逻辑

```python
def _grep_files_sync(search_path, pattern, file_glob, output_mode,
                      ignore_case, multiline, head_limit, context_lines,
                      after_lines, before_lines, deadline):
    \"\"\"同步文件内容搜索。返回 (results, match_count)。\"\"\"
    import fnmatch, re as re_mod
    flags = re_mod.IGNORECASE if ignore_case else 0
    if multiline: flags |= re_mod.DOTALL
    try: regex = re_mod.compile(pattern, flags)
    except re.error as e: raise ValueError(f"正则表达式错误: {e}")
    results = []; match_count = 0
    for root, dirs, files in os.walk(search_path):
        if time.monotonic() > deadline: break
        filtered = [f for f in files if not file_glob or fnmatch.fnmatch(f, file_glob)]
        for filename in filtered:
            if head_limit is not None and match_count >= head_limit: break
            file_lines = _read_file_safe(Path(root) / filename)
            if not file_lines: continue
            file_matches = _collect_file_matches(
                file_lines, regex, multiline, head_limit, match_count,
                context_lines, after_lines, before_lines)
            match_count += len(file_matches)
            entry = _format_match_output(file_matches, output_mode, str(Path(root) / filename))
            if entry: results.append(entry)
    return results, match_count


def _collect_file_matches(lines, regex, multiline, head_limit, match_count,
                          context_lines, after_lines, before_lines) -> List[Dict]:
    \"\"\"收集单个文件中的匹配行。\"\"\"
    file_matches = []
    if multiline:
        content = ''.join(lines)
        for m in regex.finditer(content):
            if head_limit and match_count + len(file_matches) >= head_limit: break
            file_matches.append({"line": content[:m.start()].count('\n') + 1, "content": m.group()})
    else:
        for line_no, line in enumerate(lines, 1):
            if head_limit and match_count + len(file_matches) >= head_limit: break
            m = regex.search(line)
            if m:
                entry = {"line": line_no, "content": line.rstrip('\n\r')}
                entry.update(_build_context(lines, line_no, context_lines, after_lines, before_lines))
                file_matches.append(entry)
    return file_matches
```

**组件2: 重构后的 `grep_file_content`**（~75 行）

```python
async def grep_file_content(self, pattern, search_dir=None, output_mode=None,
                             glob=None, context=None, ignore_case=True,
                             multiline=False, head_limit=None, page_token=None) -> Dict[str, Any]:
    after = before = around = None
    if context:
        after = context.get("after"); before = context.get("before"); around = context.get("around")
    try:
        search_path = Path(search_dir).resolve() if search_dir else Path.cwd().resolve()
        valid, msg = self._validate_path(str(search_path))
        if not valid: return build_error("ERR_PATH_INVALID", msg)
        if not pattern: return build_error("ERR_PARAM_INVALID", "搜索模式不能为空")
        deadline = time.monotonic() + get_timeout("grep_file_content") - 2
        matches, total_matches = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, output_mode,
            ignore_case, multiline, head_limit, around, after, before, deadline)
        total = len(matches)
        page_results, next_token = _paginate_results(matches, page_token, DEFAULT_PAGE_SIZE)
        return build_success(
            {"matches": page_results, "total_files": total, "total_matches": total_matches,
             "pattern": pattern, "search_dir": str(search_path),
             "output_mode": output_mode or "content",
             "has_more": next_token is not None, "next_page_token": next_token},
            f"搜索完成，匹配{total_matches}行，涉及{total}个文件",
            llm_data={"模式": pattern, "搜索目录": str(search_path),
                      "匹配文件数": total, "匹配行数": total_matches,
                      "预览": make_json_safe(page_results[:10], max_str_len=200)},
            next_actions=build_next_actions([
                ("read_file", "读取匹配行上下文", "需要查看完整内容时"),
                ("edit_file", "编辑匹配内容", "需要修改时")]))
    except Exception as e:
        return build_error("ERR_FILE_CONTENT_SEARCH_FAILED", str(e))
```

**优势**: 119 行 → ~75 行 + 2 个模块级函数。`_grep_files_sync` / `_collect_file_matches` 可独立测试。消除内部函数重新定义。total_matches 兼容逻辑移入 `_collect_file_matches` 返回值。

---

### 5.5 `http_request` — `network_tools.py:97` (113行)

**当前规模**: 113 行 | **文件位置**: `backend/app/services/tools/network/network_tools.py:97`

#### 5.5.1 当前结构拆解

`http_request` 实现 HTTP 请求工具（参数校验+重试+代理+响应解析），共 9 个决策点：

**调用路径**: `LLM意图` → `http_request(url, method, headers, ...)` → httpx.AsyncClient → response

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **V1 参数校验** | V1a | retry 不在 0-10 | ERR_NETWORK_INVALID_PARAM | 109-110 | 中层校验 |
| **U1 URL校验** | U1a | _validate_url 失败 | ERR_INVALID_URL | 115-117 | 中层校验 |
| **N1 网络检查** | N1a | _check_network 失败 | ERR_NETWORK_DOWN | 119-121 | 中层校验 |
| **Q1 查询参数** | Q1a | params 非空 | urlencode 拼入 URL | 123-126 | 低层数据处理 |
| **H1 请求头** | H1a | headers 非空 | update request_headers | 128-130 | 低层数据处理 |
| **P1 代理** | P1a | proxy 指定 | 使用指定代理 | 133-134 | 低层配置 |
| | P1b | 环境变量 | 使用 HTTP_PROXY/HTTPS_PROXY | 135-136 | 低层配置 |
| | P1c | 都无 | 无代理 | - | 低层配置 |
| **R1 重试循环** | R1a | POST/PUT/PATCH + json_body | 传 json 参数 | 154-156 | 低层请求 |
| | R1b | GET/DELETE/HEAD | 不传 json | - | 低层请求 |
| | R1c | 状态码 2xx | build_success | 162-171 | 中层成功 |
| | R1d | 非重试状态码(4xx) | 直接返回错误 + 不重试 | 174-186 | 中层错误 |
| | R1e | 重试状态码(5xx) + attempt<retry | 指数退避 sleep + continue | 187-190 | 中层重试 |
| | R1f | 重试耗完 | break | 191 | 中层重试 |
| **F1 最终错误** | F1a | TimeoutException | ERR_NETWORK_TIMEOUT | 193-194 | 中层错误 |
| | F1b | HTTPStatusError | ERR_NETWORK_HTTP_ERROR | 195-203 | 中层错误 |
| | F1c | 其他 | ERR_NETWORK_REQUEST_ERROR | 204-205 | 中层错误 |
| **X1 全局异常** | X1a | Exception | ERR_NET_UNKNOWN | 207-209 | 中层异常 |

**重复/冗余**:
- 代理配置（133-136）与 `fetch_webpage` 的代理配置逻辑重复（`network_tools.py:421`）— 4 行相同
- 重试循环（139-191）的模式与 `_execute_retry_loop` 的 retry 逻辑结构相似但实现不同
- 最终错误返回（193-205）3 个 isinstance 分支可用 dict 映射 + 循环简化

#### 5.5.2 违反原则分析

- **DRY 中度违反**: 代理配置与 `fetch_webpage` 重复。最终错误返回的 3 个 `isinstance` 分支可用 dict 映射简化。
- **SLAP 基本遵守**: 参数校验(中层) → 重试(中层) → 错误处理(中层)，层次较清晰。
- **SRP 中度违反**: 参数校验 + 代理配置 + 重试 + 响应解析 + 错误处理共 5 个职责。
- **KISS 基本遵守**: 重试循环逻辑直观。

#### 5.5.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_validate_url` | `network_tools.py:22` ✅ | 已有模块级函数 |
| `_check_network` | `network_tools.py:54` ✅ | 已有模块级函数 |
| `_parse_response_body` | `network_tools.py` ✅ | 已有模块级函数 |
| 代理配置 | 与 fetch_webpage 重复 | 建议提取为 `_resolve_proxy(proxy)` |
| 最终错误映射 | 无可复用 | 建议提取为 `_build_http_error(...)` |

#### 5.5.4 重构方案（详细代码设计）

**目标**: 113 行 → ~85 行主函数 + 2 个辅助函数，消除代理配置重复 + 最终错误映射简化。

**组件1: `_resolve_proxy`** — 提取代理配置（也为 fetch_webpage 复用）

```python
def _resolve_proxy(proxy: Optional[str] = None) -> Optional[str]:
    \"\"\"解析代理配置：优先参数，其次环境变量。\"\"\"
    return proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
```

**组件2: `_build_http_error`** — 统一最终错误构建

```python
def _build_http_error(last_exception, url: str, retry: int) -> Dict:
    \"\"\"构建HTTP请求最终错误响应。\"\"\"
    if isinstance(last_exception, httpx.TimeoutException):
        return build_error("ERR_NETWORK_TIMEOUT", f"请求超时：{url}")
    if isinstance(last_exception, httpx.HTTPStatusError):
        return build_error("ERR_NETWORK_HTTP_ERROR", f"HTTP请求失败（重试{retry}次后）：{url}",
            data={"status_code": last_exception.response.status_code,
                  "body": last_exception.response.text if hasattr(last_exception.response, 'text') else None})
    return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败（重试{retry}次后）：{str(last_exception)}")
```

**组件3: 重构后的 `http_request`**（~85 行）

```python
async def http_request(url, method="GET", headers=None, params=None,
                        json_body=None, timeout=30000, proxy=None, retry=3) -> dict:
    if retry < 0 or retry > 10:
        return build_error("ERR_NETWORK_INVALID_PARAM", f"重试次数必须在0-10之间，当前值：{retry}")
    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}")
        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用")
        if params:
            url = urlunparse(urlparse(url)._replace(query=urlencode(params, doseq=True)))
        proxy_config = _resolve_proxy(proxy)
        last_exception = None
        for attempt in range(retry + 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout/1000.0),
                    follow_redirects=True, verify=True, proxy=proxy_config) as client:
                    kwargs = {"url": url, "headers": headers or {}}
                    if method.upper() in ("POST","PUT","PATCH") and json_body is not None:
                        kwargs["json"] = json_body
                    response = await client.request(method.upper(), **kwargs)
                    response.raise_for_status()
                    parsed = _parse_response_body(response)
                    return build_success(parsed["body"], f"请求成功 (HTTP {response.status_code})",
                        llm_data={"状态码": response.status_code, "内容类型": parsed["content_type_short"],
                                  "响应体": parsed["llm_body"]},
                        next_actions=build_next_actions([("http_request", "继续发送请求", "")]))
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exception = e
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code not in RETRYABLE_HTTP_STATUS_CODES:
                    return build_error(...)
                if attempt < retry:
                    await asyncio.sleep(0.5 * (2 ** attempt)); continue
                break
        return _build_http_error(last_exception, url, retry)
    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"请求异常: {str(e)}")
```

**优势**: 113 行 → ~85 行 + 2 个辅助函数。`_resolve_proxy` 消除与 `fetch_webpage` 的跨函数重复。`_build_http_error` 封装最终错误构建。

---

"""

content += ch5

with open('app代码函数行数分布扫描报告-小沈-2026-05-25.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('Chapter 5 appended successfully')
