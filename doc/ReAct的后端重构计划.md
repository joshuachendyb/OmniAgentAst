# ReAct的后端重构计划

**创建时间**: 2026-03-09 22:04:41
**编写人**: 小沈
**存放位置**: D:\2bktest\MDview\OmniAgentAs-desk\

---

## 一、重构目标概述

本次后端代码重构的核心目标是：**实现真正的实时流式推送，遵守ReAct循环的三个独立阶段原则，消除硬编码和嵌套错误**。

---

## 二、需要重构的文件清单

| 序号 | 文件路径 | 作用 | 重构优先级 |
|------|---------|------|-----------|
| 1 | `backend/app/api/v1/chat/stream.py` | API入口，SSE流式响应 | 🔴 高 |
| 2 | `backend/app/services/file_operations/agent.py` | ReAct Agent核心逻辑 | 🔴 高 |
| 3 | `backend/app/services/file_operations/adapter.py` | 参数类型适配器 | 🟡 中 |
| 4 | `backend/app/services/file_operations/tools.py` | 文件操作工具集 | 🟡 中 |
| 5 | `backend/app/services/file_operations/safety.py` | 安全检查模块 | 🟡 中 |

---

## 三、当前问题诊断

### 3.1 chat.py 问题

| 问题编号 | 问题描述 | 位置 | 影响 |
|---------|---------|------|------|
| P8-001 | 第一个thought硬编码 | chat.py:697-702 | 违反ReAct原则，LLM推理被跳过 |
| P8-002 | 第一个action_tool硬编码 | chat.py:721-723 | 违反ReAct原则 |
| P8-003 | 推送时机错误（批量模式） | chat.py:780 | 等所有轮次执行完才推送，非实时 |
| P8-004 | observation嵌套thought/action_tool | chat.py:observation字段 | 数据结构混乱 |
| P8-005 | 错误响应字段不一致 | create_error_response函数 | error_type/error_message命名混乱 |

### 3.2 agent.py 问题

| 问题编号 | 问题描述 | 位置 | 影响 |
|---------|---------|------|------|
| P8-006 | Step类字段不完整 | agent.py:Step类 | 缺少reasoning、is_finished等字段 |
| P8-007 | 阻塞式执行 | agent.run()方法 | 没有实现异步流式输出 |
| P8-008 | 缺少安全检查集成 | agent.run() | 安全检查没有在Agent中体现 |
| P8-009 | action_tool命名不一致 | 多个位置 | 有时用action有时用tool_name |

### 3.3 tools.py 问题

| 问题编号 | 问题描述 | 影响 |
|---------|---------|------|
| P8-010 | 返回格式不统一 | 不同工具返回格式不一致 |
| P8-011 | 缺少execution_status字段 | 前端无法判断执行结果 |

---

## 四、修改计划详情

### Phase 1: tools.py 修改（底层工具层）

#### 1.1 统一工具返回格式

**目标**：所有工具方法返回时添加 `execution_status` 字段

| 工具函数 | 当前返回字段 | 修改后返回字段 | 修改类型 |
|---------|------------|--------------|---------|
| `read_file` | success, error, content | + execution_status | 修改 |
| `write_file` | success, error | + execution_status | 修改 |
| `list_directory` | success, error, entries | + execution_status + 分页 | 修改 |
| `delete_file` | success, error | + execution_status | 修改 |
| `move_file` | success, error | + execution_status | 修改 |
| `search_files` | success, error, results | + execution_status | 修改 |
| `generate_report` | success, error, report | + execution_status | 修改 |

**统一返回格式**：
```python
{
    "status": "success",  # success/error/warning
    "summary": "人类可读的结果描述",
    "data": {...},       # 原始数据
    "retry_count": 0
}
```

#### 1.2 新增分页支持

| 函数名 | 功能 | 新增类型 |
|--------|------|---------|
| `list_directory_with_pagination` | 支持分页的目录列表 | 新增 |
| `encode_page_token` | 编码页码令牌 | 新增 |
| `decode_page_token` | 解码页码令牌 | 新增 |
| `_generate_summary` | 生成人类可读的结果摘要 | 新增 |

---

### Phase 2: agent.py 修改（核心逻辑层）

#### 2.1 重新设计Step类

**拆分为3个独立的类**：

| 类名 | 字段 | 用途 |
|------|------|------|
| `ThoughtStep` | step_number, content, reasoning, action_tool, params | Thought阶段 |
| `ActionToolStep` | step_number, tool_name, tool_params, execution_status, summary, raw_data, action_retry_count | Action阶段 |
| `ObservationStep` | step_number, execution_status, summary, raw_data, content, reasoning, action_tool, params, is_finished | Observation阶段 |

#### 2.2 新增 run_stream 方法

```python
async def run_stream(self, user_input: str, max_steps: int = 10):
    """
    异步流式执行Agent，每轮循环完成后立即yield输出
    """
    while step_count < max_steps:
        # Thought阶段 → yield thought
        yield {"type": "thought", ...}
        
        # Action阶段 → yield action_tool
        yield {"type": "action_tool", ...}
        
        # Observation阶段 → yield observation
        yield {"type": "observation", ...}
        
        if is_finished:
            break
```

#### 2.3 修改现有方法

| 方法名 | 修改内容 |
|--------|---------|
| `ToolParser.parse_response` | 支持新字段名 action_tool, params |
| `ToolParser._extract_from_text` | 支持从新JSON格式提取 |
| `ToolExecutor.execute` | 返回格式添加 execution_status |
| `_execute_with_retry` | 配合新的错误分类 |
| `_format_observation` | 配合新observation格式 |

---

### Phase 3: adapter.py 修改（适配层）

#### 3.1 新增字段转换函数

| 函数名 | 功能 |
|--------|------|
| `observation_to_llm_input` | 将observation格式化为LLM输入：Observation: {execution_status} - {summary} |
| `thought_to_message` | 将thought转换为对话消息格式 |

---

### Phase 4: chat.py 修改（入口层）

#### 4.1 移除硬编码

| 位置 | 当前问题 | 修改方案 |
|------|---------|---------|
| 第697-702行 | 硬编码第一个thought | 调用LLM获取真正的thought |
| 第721-723行 | 硬编码第一个action_tool | 调用LLM获取真正的action_tool |

#### 4.2 实现实时流式推送

| 位置 | 当前问题 | 修改方案 |
|------|---------|---------|
| 第748行 | `result = await agent.run()` 阻塞等待 | 改为 `async for event in agent.run_stream()` |

#### 4.3 统一错误响应格式

```python
def create_error_response(
    error_type: str,
    message: str,
    code: str = "INTERNAL_ERROR",
    details: Optional[str] = None,
    stack: Optional[str] = None
) -> str:
    """
    统一的错误响应格式
    """
    response = {
        'type': 'error',
        'code': code,
        'message': message,
        'error_type': error_type
    }
    if details:
        response['details'] = details
    if stack:
        response['stack'] = stack
    return f"data: {json.dumps(response)}\n\n"
```

#### 4.4 修改辅助函数

| 函数名 | 修改内容 |
|--------|---------|
| `check_and_yield_if_interrupted` | 使用新status格式：type=status, status_value=interrupted |
| `check_and_yield_if_paused` | 使用新status格式：type=status, status_value=paused |
| `simplify_observation` | 配合新observation格式 |
| `detect_file_operation_intent` | 更新返回格式 |
| `cancel_stream_task` | 发送status类型 |
| `pause_stream_task` | 发送status类型 |
| `resume_stream_task` | 发送status类型 |
| `handle_file_operation` | 添加execution_status |

---

### Phase 5: safety.py 修改（安全层）

#### 5.1 增强安全检查结果格式

```python
async def check_command_safety(command: str) -> Dict[str, Any]:
    """
    检查命令安全性
    
    Returns:
        {
            "is_safe": bool,
            "risk_level": str | null,   # low/medium/high/critical
            "risk": str | null,
            "blocked": bool,
            "rule_matched": str | null
        }
    """
```

---

## 五、修改顺序（重要）

```
tools.py (底层)
    ↓
agent.py (核心)
    ↓
adapter.py (适配)
    ↓
chat.py (入口)
    ↓
safety.py (安全)
```

**原因**：
1. tools.py 是最底层，被 agent.py 依赖
2. agent.py 是核心逻辑，被 chat.py 调用
3. adapter.py 是适配层
4. chat.py 是最上层入口
5. safety.py 被各层调用

---

## 六、新type数据结构设计

### 6.1 整合后的type列表（8个）

| type | 说明 | 阶段 |
|------|------|------|
| start | 任务开始 | 初始化 |
| thought | 思考 | ReAct第1阶段 |
| action_tool | 执行动作 | ReAct第2阶段 |
| observation | 执行结果 | ReAct第3阶段 |
| final | 最终回复 | 结束 |
| chunk | 流式内容片段 | 辅助 |
| error | 错误 | 状态 |
| status | Agent执行状态 | 状态 |

### 6.2 各type字段设计

#### type=thought

```json
{
  "type": "thought",
  "step": 1,
  "content": "用户想要查看桌面文件夹...",
  "reasoning": "...",
  "action_tool": "list_directory",
  "params": {"path": "Desktop"}
}
```

#### type=action_tool

```json
{
  "type": "action_tool",
  "step": 1,
  "tool_name": "list_directory",
  "tool_params": {"path": "Desktop"},
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {"entries": [...]},
  "action_retry_count": 0
}
```

#### type=observation

```json
{
  "type": "observation",
  "step": 1,
  "execution_status": "success",
  "summary": "成功读取目录",
  "raw_data": {...},
  "content": "已获取目录内容，现在整理成列表回复用户",
  "reasoning": "...",
  "action_tool": "finish",
  "params": {},
  "is_finished": true
}
```

#### type=error

```json
{
  "type": "error",
  "code": "TIMEOUT",
  "message": "请求超时",
  "error_type": "network",
  "details": "...",
  "stack": "...",
  "retryable": true,
  "retry_after": 5
}
```

#### type=status

```json
{
  "type": "status",
  "status_value": "interrupted",  // interrupted/paused/resumed/retrying
  "message": "任务已被中断"
}
```

---

## 七、执行检查清单

### 7.1 修改前检查

- [ ] 备份当前代码版本
- [ ] 确保有完整的测试用例
- [ ] 理解当前代码逻辑

### 7.2 修改中检查

- [ ] 按照修改顺序执行
- [ ] 每修改一个函数，进行单元测试
- [ ] 确保不破坏现有功能

### 7.3 修改后检查

- [ ] 运行所有单元测试
- [ ] 进行集成测试
- [ ] 验证SSE流式输出是否正常
- [ ] 验证ReAct循环是否正确

---

## 八、预期效果

### 8.1 功能改进

- ✅ 真正的实时流式推送，每轮循环完成后立即输出
- ✅ 遵守ReAct三个独立阶段原则
- ✅ 移除所有硬编码，使用真正的LLM推理
的数据结构和- ✅ 统一错误格式

### 8.2 用户体验

- ✅ 前端实时显示每一步操作
- ✅ 错误信息更清晰明确
- ✅ 支持任务暂停/恢复/中断

### 8.3 代码质量

- ✅ 代码结构更清晰
- ✅ 职责划分更明确
- ✅ 易于维护和扩展

---

**更新时间**: 2026-03-09 22:04:41
**版本**: v1.0
