# E2E 集成测试规范

**版本**: v1.0  
**编写人**: 小健  
**日期**: 2026-05-24  
**依据**: 多轮真实测试实践中总结的方法论

---

## 一、定义与命名

### 1.1 测试名称

**E2E 前端流程模拟集成测试**（End-to-End Frontend-Flow Simulation Integration Test）

简称 **E2E-FSI 测试**。

- **不叫**"API直接调用测试"——直接调chat接口不带session_id，不是真实用户路径
- **不叫**"Mock集成测试"——任何mock都是假的，不能发现真实问题
- **叫**"前端流程模拟"——因为测试程序必须**完整复刻前端的每一步操作**，从创建session到SSE对话，与真实用户操作完全一致

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| **零Mock** | 禁止任何mock/fake/stub。LLM必须调真实服务，HTTP必须发真实请求 |
| **前端流程完整复刻** | 测试程序必须按前端实际操作顺序执行：创建session→保存消息→SSE对话 |
| **错误不放过** | 收集app log、SSE事件、进程状态等多维度错误，不能只看HTTP 200就认为通过 |
| **问题必须修** | 发现Bug必须定位根因并修复，不能只记录不处理 |

---

## 二、前端真实流程（必须完整复刻）

前端从用户点击"发送"到收到AI回复，完整流程如下：

```
┌─────────────────────────────────────────────────────────┐
│  前端真实流程（5步）                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  步骤1: POST /api/v1/sessions                           │
│         → 创建会话，获取 session_id                      │
│         → 请求体: {"title": "用户消息前30字", "is_valid": true} │
│         → 返回: {"session_id": "xxx", ...}               │
│                                                         │
│  步骤2: POST /api/v1/sessions/{session_id}/messages      │
│         → 保存用户消息到DB                               │
│         → 请求体: {"role": "user", "content": "用户输入"} │
│         → 返回: {"message_id": 123}                      │
│                                                         │
│  步骤3: POST /api/v1/chat/stream/v2                     │
│         → SSE流式对话（必须带 session_id）                │
│         → 请求体: {                                      │
│              "messages": [{"role":"user","content":"..."}],│
│              "stream": true,                             │
│              "session_id": "步骤1获取的session_id"        │
│            }                                             │
│         → 逐行读取SSE: data: {type, step, ...}          │
│                                                         │
│  步骤4: 解析SSE事件流                                    │
│         → 收集所有事件: start, thought, action_tool,      │
│           observation, chunk, final, error               │
│         → 验证事件链完整性                               │
│                                                         │
│  步骤5: 深度断言（不能只看HTTP 200）                     │
│         → 必须有 start 事件                              │
│         → 必须有 final 或 error 结束事件                  │
│         → 工具调用测试: 必须有 thought→action_tool→observation 链 │
│         → 期望工具必须被调用                              │
│         → final内容不能含错误关键词（429/500/失败/exception）│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.1 为什么必须带 session_id

**不带的后果（已验证）**：
- 后端 `message_saver.py` 每个SSE事件都尝试 `save_execution_steps()`
- `sessions.py` 检查session存在性，不存在抛404
- **每个请求产生6条ERROR日志**：`[Save] 保存失败: 404: 会话不存在: xxx`
- 虽然不中断流式响应（catch了异常），但：
  - 污染日志，掩盖真实错误
  - 用户消息无法持久化，刷新后对话丢失
  - 不是真实用户场景，测试结果不可信

**带session_id后**：
- app log ERROR数从36条降为0条
- 消息正确持久化到SQLite
- 测试结果反映真实用户体验

---

## 三、测试程序结构规范

### 3.1 目录结构

```
backend/tests/e2e_real/
├── __init__.py
├── test_quick.py          # 精简版E2E-FSI测试（4-6个关键场景）
├── test_runner.py         # 完整版E2E-FSI测试（全工具类别覆盖）
├── error_collector.py     # 多维度错误收集器
├── bug_tracker.py         # Bug注册+验证+报告系统
└── reports/               # 测试报告输出（自动生成）
```

### 3.2 测试程序必须实现的函数

```python
# 1. 前端流程模拟（3个函数，缺一不可）

async def frontend_create_session(title) -> session_id
    """POST /api/v1/sessions → 创建会话"""

async def frontend_save_message(session_id, content) -> message_id
    """POST /api/v1/sessions/{id}/messages → 保存用户消息"""

async def frontend_chat_stream(msg, session_id) -> (events, status, dur, err)
    """POST /api/v1/chat/stream/v2 (带session_id) → SSE对话"""

# 2. 完整流程封装

async def frontend_full_flow(msg) -> (events, status, dur, err, session_id)
    """步骤1→2→3 串联，返回完整结果"""

# 3. 深度分析（不能只看HTTP 200）

def deep_analyze(events, expect_tool) -> analysis_dict
    """分析SSE事件链完整性，返回issues列表"""
```

### 3.3 深度断言清单

| 断言项 | 检查内容 | 严重级别 |
|--------|----------|----------|
| start事件存在 | SSE流第一个事件必须是type=start | CRITICAL |
| 结束事件存在 | 必须有type=final或type=error | CRITICAL |
| 中间步骤存在 | 工具调用场景必须有thought→action_tool→observation链 | HIGH |
| 期望工具被调用 | 如果指定expect_tool，必须在tools_called中出现 | HIGH |
| 空工具名检测 | action_tool事件的tool_name不能为空 | CRITICAL |
| final不含错误 | final内容不能含429/500/错误/失败/exception等关键词 | HIGH |
| final非工具JSON | final内容不能是未解析的tool_call JSON | MEDIUM |

---

## 四、错误收集规范

### 4.1 四维度收集

| 维度 | 收集器 | 收集内容 |
|------|--------|----------|
| **App Log** | AppLogCollector | backend/logs/app_*.log 中的 ERROR/WARNING |
| **SSE事件** | SSEEventCollector | SSE流中的error事件、工具执行失败、final含错误关键词 |
| **进程状态** | ProcessCollector | 后端/Ollama进程是否存活 |
| **Prompt日志** | PromptLogCollector | backend/logs/prompt-logs/ 中的异常记录 |

### 4.2 收集时机

- **测试开始前**：记录时间戳 `start_time`
- **每个测试后**：收集该测试产生的SSE事件错误
- **全部测试后**：收集 `start_time` 以来的 app log 错误

### 4.3 错误处置

1. ERROR/CRITICAL级别错误 → 自动注册为Bug
2. Bug必须定位根因并修复，不能只记录
3. 修复后必须重新测试验证

---

## 五、测试用例设计规范

### 5.1 用例必须覆盖的维度

| 维度 | 说明 | 示例 |
|------|------|------|
| **简单对话** | 验证LLM连通性+ReAct循环完整性 | "你好，请用一句话回复" |
| **工具调用** | 验证特定工具的完整调用链 | "读取 backend/pytest.ini 文件的内容" |
| **意图分类** | 验证CRSS+LLM两阶段路由正确性 | "获取当前系统时间" → system |
| **已知Bug验证** | 验证已修复Bug不再复现 | "hello" → 不应死循环 |

### 5.2 用例格式

```python
{
    "id": "T1",                    # 唯一标识
    "desc": "简单对话-LLM连通性",   # 人类可读描述
    "msg": "你好，请用一句话回复",   # 发给后端的用户消息
    "expect_tool": "",             # 期望调用的工具名（空=不期望特定工具）
    "timeout": 120,                # 超时秒数（根据模型推理速度调整）
}
```

### 5.3 超时设置参考

| 模型类型 | 建议超时 | 说明 |
|----------|----------|------|
| 云端API (qiniu/dmxapi等) | 60-120s | 网络延迟+推理时间 |
| 本地Ollama (1.5B CPU) | 300-600s | CPU推理极慢，首次约2-3分钟 |
| 本地Ollama (7B+ GPU) | 120-180s | GPU推理快但首次加载慢 |

---

## 六、测试执行流程

### 6.1 标准执行步骤

```
Phase 0: 环境预检
  ├── 检查后端服务是否运行 (GET /api/v1/health)
  ├── 读取当前config.yaml确认provider/model
  └── 确认LLM服务可达（Ollama/云端API）

Phase 1: 前端流程模拟测试
  ├── 对每个测试用例:
  │   ├── 步骤1: frontend_create_session()
  │   ├── 步骤2: frontend_save_message()
  │   ├── 步骤3: frontend_chat_stream()
  │   ├── deep_analyze() 深度断言
  │   └── 失败则注册Bug
  └── 请求间间隔2秒（避免限流）

Phase 2: 错误收集与分析
  ├── 收集app log (since start_time)
  ├── 收集进程状态
  ├── 按错误来源和级别统计
  └── ERROR级别自动注册Bug

Phase 3: 报告生成
  ├── Markdown报告 (人类阅读)
  ├── JSON报告 (机器解析)
  └── 输出Bug统计: 总数/确认/未修复
```

### 6.2 执行命令

```bash
# 精简版（4个关键场景，约5-10分钟）
cd backend/tests && python -m e2e_real.test_quick

# 完整版（全工具类别覆盖，约30-60分钟）
cd backend/tests && python -m e2e_real.test_runner
```

---

## 七、Bug追踪规范

### 7.1 Bug严重级别

| 级别 | 定义 | 示例 |
|------|------|------|
| CRITICAL | 系统崩溃/死循环/核心功能完全不可用 | 空工具名死循环、NoneType崩溃 |
| HIGH | 功能失败/数据丢失/错误信息暴露 | message_saver 404、意图分类错误 |
| MEDIUM | 功能降级/体验差 | LLM选错工具、final内容不理想 |
| LOW | 日志混乱/格式不规范 | 日志级别区分不当 |

### 7.2 Bug记录格式

```python
BugRecord:
    bug_id: "BUG-E2E-001"          # 自动编号
    title: "描述"                    # 一句话
    severity: Severity.HIGH         # 严重级别
    description: "详细描述"          # 包含根因分析
    verify_status: PENDING/CONFIRMED/FIXED
    discovered_by: "e2e_real"       # 发现来源
    evidence: [...]                 # 证据（日志片段、事件列表等）
    location: "file.py:123"         # 代码位置
    root_cause: "根因分析"           # 为什么发生
    fix_description: "修复说明"     # 怎么修的
```

---

## 八、反模式（禁止）

| 反模式 | 为什么禁止 | 正确做法 |
|--------|-----------|----------|
| **直接调chat/stream不带session_id** | 导致message_saver 404，不反映真实场景 | 先createSession再发SSE |
| **使用mock替换LLM** | mock无法发现LLM格式遵循、意图分类、FC兼容性等真实问题 | 调真实LLM服务 |
| **只断言HTTP 200** | 200但final内容可能是错误信息、工具未调用、步骤缺失 | 深度断言事件链完整性 |
| **不收集app log** | 隐藏的ERROR/WARNING不会暴露 | 每次测试后收集app log |
| **发现问题不修** | Bug会累积，后续测试结果不可信 | 发现即修，修后重测 |

---

## 九、本次实践中发现并修复的Bug清单

| # | Bug | 根因 | 修复 | 文件 |
|---|-----|------|------|------|
| 1 | TypeError: NoneType has no len() | msg.content为None时`get("content","")`返回None | `get("content") or ""` | react_agent_mixin.py:261, prompt_logger.py:215 |
| 2 | 空工具名死循环 | type=action但tool_name无效时仍执行 | 空工具名→parse_error+重试 | base_react.py:665 |
| 3 | FC格式JSON未解析 | `{"name":"xxx","arguments":{}}`格式未识别 | 新增`_build_action_from_fc_format()` | react_output_parser.py:147 |
| 4 | FC格式在llm_strategies中漏识别 | `_extract_json_block`只检查tool_name | 补充name+arguments识别 | llm_strategies.py:470 |
| 5 | greeting意图错走network | intent_type_value为None时默认走network | 闲聊类→system | chat_router.py:295 |
| 6 | raw_intent未传递 | route_with_fallback不返回LLM原始意图 | 增加raw_intent字段 | chat_router.py:137 |
| 7 | E2E测试不带session_id | 测试直接调chat接口不模拟前端 | 重写为完整前端流程模拟 | test_quick.py (全文重写) |
| 8 | FC探测请求不强制 | "Call test_tool"太简单，LLM可能不返回tool_calls | 增加system prompt强制 | llm_adapter.py:61 |

---

**更新时间**: 2026-05-24 v1.0  
**编写人**: 小健
