# E2E全链路测试 — 问题总结报告

**创建时间**: 2026-06-13 17:00:00  
**编写人**: 小沈  
**版本**: v1.0

---

## 一、发现并修复的Bug (6个)

### Bug 1: `max_consecutive_chunks` 属性缺失 (P0-01)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/agent/core_agent/initialize_run_state.py:44` |
| **现象** | Agent启动即抛 `AttributeError: 'UniversalAgent' object has no attribute 'max_consecutive_chunks'` |
| **根因** | 访问了不存在的实例属性`self.max_consecutive_chunks`，常量`MAX_CONSECUTIVE_CHUNKS=5`定义在`constants.py`但从未被引用 |
| **修复** | 导入常量 `MAX_CONSECUTIVE_CHUNKS` 替换不存在的实例属性 |
| **影响** | 所有E2E请求在`initialize_run_state`阶段崩溃，LLM调用数为0 |

### Bug 2: `conversation_history` 路径错误 (P0-01后续)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/agent/core_agent/handlers/answer_handler.py:42` |
| **现象** | answer handler访问 `agent.conversation_history`，但该属性不存在于agent实例上 |
| **根因** | `conversation_history`归属`message_builder`，正确路径是`agent.message_builder.conversation_history` |
| **修复** | 改为 `agent.message_builder.conversation_history.append(...)` |
| **影响** | 所有answer类型响应在保存到对话历史时崩溃 |

### Bug 3: `_update_message_builder` 函数未定义 (P0-02)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/agent/core_agent/handlers/action_handler.py:152` |
| **现象** | 每次工具执行后WARNING日志`_update_message_builder异常: name '_update_message_builder' is not defined` |
| **根因** | 引用了不存在的函数，从未被实现。日志为WARNING级别所以不中断流程，但observation持续丢失 |
| **修复** | 改为 `ctx.agent.message_builder.add_observation(...)` |
| **影响** | observation不能正确写入对话历史，LLM在后续轮次中看不到工具执行结果 → 死循环 |

### Bug 4: `_auto_inject_from_search` 读取层级错误 (P0-02)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/agent/universal_agent.py:89` |
| **现象** | tool_search返回`write_text_file`有匹配(`category: file`)，但工具注入失效，agent找不到文件工具 |
| **根因** | 工具执行引擎对结果做了一次包装（`create_tool_result(data=result)`），使得`llm_data`从`result["llm_data"]`变成了`result["data"]["llm_data"]`。`_auto_inject_from_search`直接读顶层，永远找不到 |
| **修复** | 改为 `inner = result.get("data", {}); inner.get("llm_data", {}).get("matches", [])` |
| **影响** | file/shell/network等分类的动态注入完全失效，agent只能使用基础工具 |

### Bug 5: `_INITIAL_CATEGORIES` 缺少 FILE 分类 (P0-02)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/agent/universal_agent.py:20` |
| **现象** | 可用工具列表只有 `['tool_search', 'time_now', ..., 'execute_code']`，无文件工具 |
| **根因** | 初始分类只有`FUND_RUNTIME`，FILE/SHELL/NET_PROCESS均不加载。Bug4又导致动态注入失效，双重打击 |
| **修复** | `_INITIAL_CATEGORIES` 加入 `ToolCategory.FILE` |
| **影响** | File类工具完全不可用，写文件/读文件/搜索文件全部失败 |

### Bug 6: 多轮对话历史未加载 (P0-05)

| 项目 | 内容 |
|------|------|
| **文件** | `backend/app/services/react_sse_wrapper/run_sse_stream.py` |
| **现象** | 第2轮后agent对话上下文丢失，无法回忆之前对话内容 |
| **根因** | `run_sse_stream`只传入最后一条消息，未从DB加载历史消息注入agent的`message_builder` |
| **修复** | 新增`_load_previous_messages()`函数从`chat_messages`表查询历史消息，通过`context["previous_messages"]`传递给`initialize_run_state`，在`init_history`后注入到`conversation_history` |
| **影响** | 多轮对话完全无上下文 |

---

## 二、根因模式总结

| 模式 | 出现次数 | 表现 |
|------|---------|------|
| **属性/函数未定义** | 3次 (Bug1/Bug2/Bug3) | 访问了不存在的属性或函数 |
| **数据层级不匹配** | 1次 (Bug4) | 函数返回格式与调用方预期不匹配 |
| **配置缺失** | 1次 (Bug5) | 初始配置遗漏了必需的工具分类 |
| **功能缺口** | 1次 (Bug6) | 多轮对话功能从未实现 |

**统计**: 6个Bug中，4个是"写了但写错了"（属性/路径/层级），1个是"没配齐"，1个是"没实现"。

---

## 三、已通过的测试

| 级别 | 测试 | 状态 |
|------|------|------|
| P0-01 | 核心链路验证 (hello) | ✅ |
| P0-02 | 文件写入能力 | ✅ |
| P0-03 | 网络搜索能力 | ✅ |
| P0-04 | Shell命令执行 | ✅ |
| P0-05 | 多轮对话 | ✅ |
| P1-01 | 对话内容完整性 (3项) | ✅✅✅ |
| P1-02 | DB操作记录验证 (2项) | ✅✅ |
| P1-03 | 用户授权交互 (2项) | ✅✅ |

**合计**: 11个测试，0失败

---

## 四、待推进的测试

| 级别 | 测试数 | 说明 |
|------|--------|------|
| P2 | 4 | 多语言、空输入、超长输入、特殊字符 |
| P3 | 5 | 超时恢复、连接断开、双开session、并发 |
| P4 | 10 | 各分类工具逐一验证 |
| P5 | 10 | SSRF/XSS/注入/路径穿越等安全测试 |
| P6 | 8 | 长对话(10轮+)、大文件等压力场景 |
| P7 | 8 | Shell命令组合、多文件操作等复杂场景 |
| P8 | 8 | DB恢复、进程死亡等容错场景 |
| P9 | 8 | SQLite并发、事件顺序等并发场景 |
| P10 | 8 | 内存/CPU泄漏、长时间稳定运行 |

---

**报告完成时间**: 2026-06-13 17:00:00
