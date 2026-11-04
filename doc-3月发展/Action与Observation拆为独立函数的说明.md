# 重构 Action 与 Observation 设计与实现说明

**编写人**: 小沈
**编写时间**: 2026-03-19 17:30:00
**存放位置**: D:\OmniAgentAs-desk\doc-ReAct重构\

---

## 一、当前代码分析

### 1.1 action_tool 和 observation 在 chat_stream.py 中的位置

**当前代码位置**: `backend/app/api/v1/chat_stream.py`

| type | 代码位置 | 行号范围 |
|------|---------|---------|
| action_tool（文件操作入口） | thought之后 | 行884-999 |
| action_tool（Agent内部） | agent.run_stream循环内 | 行1040-1058 |
| observation | agent.run_stream循环内 | 行1060-1081 |

### 1.2 当前代码结构

**action_tool 代码片段1（文件操作入口，行884-999）**：

```python
# 文件操作：逐步推送执行步骤
action1_data = {
    'type': 'action_tool',
    'step': next_step(),
    'timestamp': create_timestamp(),
    'tool_name': 'notification',
    'tool_params': {'description': '检测到文件操作意图，开始执行...'},
    'execution_status': 'success',
    'summary': '检测到文件操作意图，开始执行...',
    'raw_data': None,
    'action_retry_count': 0
}
yield f"data: {json.dumps(action1_data)}\n\n"

# 保存数据库
current_execution_steps.append(action1_data)
await save_execution_steps_to_db(current_execution_steps, current_content)

await asyncio.sleep(0.3)

# 检查中断
async with running_tasks_lock:
    if running_tasks.get(task_id, {}).get("cancelled", False):
        interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
        yield f"data: {json.dumps(interrupted_data)}\n\n"
        return

# 安全检测
safety_result = check_command_safety(last_message)
is_safe = safety_result.get("is_safe", True)
risk = safety_result.get("risk", "")
if not is_safe:
    # yield error
    return

# observation1（安全检测结果）
observation1_data = {
    'type': 'observation',
    'step': next_step(),
    'timestamp': create_timestamp(),
    'obs_execution_status': 'success',
    'obs_summary': f'安全检测{"通过" if is_safe else "未通过"}',
    'obs_raw_data': {'is_safe': is_safe, 'risk': risk},
    'content': '',
    'obs_reasoning': '',
    'obs_action_tool': 'security_check',
    'obs_params': {},
    'is_finished': True
}
yield f"data: {json.dumps(observation1_data)}\n\n"

# 保存数据库
current_execution_steps.append(observation1_data)
await save_execution_steps_to_db(current_execution_steps, current_content)

# 创建Agent执行
session_id = str(uuid.uuid4())
ai_service = AIServiceFactory.get_service()

async def llm_client(message, history=None):
    response = await ai_service.chat(message, history)
    return type('obj', (object,), {'content': response.content})()

agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id
)

# action2（启动Agent）
action2_data = {
    'type': 'action_tool',
    'step': next_step(),
    'timestamp': create_timestamp(),
    'tool_name': 'notification',
    'tool_params': {'description': '执行文件操作...'},
    'execution_status': 'success',
    'summary': '执行文件操作...',
    'raw_data': None,
    'action_retry_count': 0
}
yield f"data: {json.dumps(action2_data)}\n\n"

current_execution_steps.append(action2_data)
await save_execution_steps_to_db(current_execution_steps, current_content)

# 流式执行（每步检查中断）
async for event in agent.run_stream(last_message, max_steps=max_steps):
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            break
    
    event_type = event.get('type')
    
    if event_type == 'thought':
        # ... thought处理
    elif event_type == 'action_tool':
        action_data = {
            'type': 'action_tool',
            'step': next_step(),
            'timestamp': create_timestamp(),
            'tool_name': event.get('tool_name', ''),
            'tool_params': event.get('tool_params', {}),
            'execution_status': event.get('execution_status', 'success'),
            'summary': event.get('summary', ''),
            'raw_data': event.get('raw_data'),
            'action_retry_count': event.get('action_retry_count', 0)
        }
        yield f"data: {json.dumps(action_data)}\n\n"
        current_execution_steps.append(action_data)
        await save_execution_steps_to_db(current_execution_steps, current_content)
    
    elif event_type == 'observation':
        observation_data = {
            'type': 'observation',
            'step': next_step(),
            'timestamp': create_timestamp(),
            'obs_execution_status': event.get('execution_status', 'success'),
            'obs_summary': event.get('summary', ''),
            'obs_raw_data': event.get('raw_data'),
            'content': event.get('content', ''),
            'obs_reasoning': event.get('reasoning', ''),
            'obs_action_tool': event.get('action_tool', ''),
            'obs_params': event.get('params', {}),
            'is_finished': event.get('is_finished', False)
        }
        yield f"data: {json.dumps(observation_data)}\n\n"
        current_execution_steps.append(observation_data)
        await save_execution_steps_to_db(current_execution_steps, current_content)
    
    elif event_type == 'final':
        # ... final处理
    elif event_type == 'error':
        # ... error处理
    
    await asyncio.sleep(0.05)
```

### 1.3 需要拆分的部分

| 序号 | 函数名 | 功能 | 代码位置 |
|------|--------|------|---------|
| 1 | process_action_file_op | 文件操作入口（action1 + 安全检测 + observation1 + action2 + Agent执行） | 行881-1157 |
| 2 | handle_action_event | Agent内部 action_tool 事件处理 | 行1040-1058 |
| 3 | handle_observation_event | Agent内部 observation 事件处理 | 行1060-1081 |

---

## 二、拆分设计

### 2.1 拆分原则

1. **action_tool 和 observation 不拆成独立文件**，因为它们：
   - 依赖于 chat_stream.py 的上下文（running_tasks、save_execution_steps_to_db 等）
   - 有循环调用逻辑（Agent 内部事件处理）
   - 代码量中等（100-200行）

2. **拆成独立函数，放在 types/process_action.py**，由 chat_stream.py 调用

3. **文件操作入口（行881-1157）**拆成 `process_file_operation` 函数

### 2.2 文件结构

```
backend/app/api/v1/types/
├── __init__.py
├── process_start.py      ✅ 已完成
├── process_thought.py    ✅ 已完成
├── process_action.py     ⏳ 待实现（本次）
└── ...
```

---

## 三、process_action.py 设计

### 3.1 函数清单

| 函数名 | 功能 | 行号 |
|--------|------|------|
| `build_action_notification` | 构建 notification 类型的 action_data | 待定 |
| `build_observation_security` | 构建安全检测结果的 observation_data | 待定 |
| `handle_action_event` | 处理 Agent 返回的 action_tool 事件 | 待定 |
| `handle_observation_event` | 处理 Agent 返回的 observation 事件 | 待定 |
| `process_file_operation` | 文件操作入口主函数 | 待定 |

### 3.2 process_file_operation 函数设计

```python
async def process_file_operation(
    last_message: str,                    # 用户消息
    ai_service: AIService,                # AI服务
    task_id: str,                        # 任务ID
    current_execution_steps: Any,        # 执行步骤列表（引用）
    current_content: Any,                # 当前内容（引用）
    save_execution_steps_to_db: Any,     # 保存数据库函数
    add_step_and_save: Any,               # 添加步骤函数
    running_tasks: Any,                   # 运行任务
    running_tasks_lock: Any,              # 运行任务锁
    next_step: Any                       # next_step()函数
) -> AsyncGenerator[dict, None]:
    """
    处理文件操作入口
    
    流程：
    1. yield action1（notification，开始执行）
    2. 保存数据库
    3. 检查中断
    4. 安全检测
    5. yield observation1（安全检测结果）
    6. 保存数据库
    7. yield action2（启动Agent）
    8. 保存数据库
    9. 执行 Agent.run_stream()
    10. 返回 Agent 内部事件供调用方处理
    
    Yields:
        dict: action_data / observation_data
        第三次yield: {'_file_operation_complete': True, 'final_content': xxx}
    """
    # 1. yield action1（notification）
    # 2. 保存数据库
    # 3. 检查中断
    # 4. 安全检测
    # 5. yield observation1（安全检测结果）
    # 6. 保存数据库
    # 7. yield action2（启动Agent）
    # 8. 保存数据库
    # 9. 执行 Agent.run_stream()
    # 10. yield Agent 内部事件
    
    yield {
        '_file_operation_complete': True,
        'final_content': full_content
    }
```

---

## 四、待确认问题

### 4.1 action_tool 和 observation 需要拆成独立文件吗？

**当前方案**：拆成独立文件 `process_action.py`，放在 `types/` 目录下。

**理由**：
- 与 process_start.py、process_thought.py 保持一致
- 统一按 type 分文件架构

### 4.2 是否需要新建 observation.py？

**当前方案**：不需要，observation 和 action_tool 都放在 `process_action.py` 中。

**理由**：
- observation 通常跟在 action_tool 后面
- 代码量不大（各50行左右）
- 拆分增加复杂度

---

## 五、实现计划

### 5.1 实现步骤

1. 创建 `backend/app/api/v1/types/process_action.py`
2. 实现 `build_action_notification` 函数
3. 实现 `build_observation_security` 函数
4. 实现 `handle_action_event` 函数
5. 实现 `handle_observation_event` 函数
6. 实现 `process_file_operation` 主函数
7. 更新 chat_stream.py 调用
8. 编译检查
9. 代码审查

### 5.2 预计工作量

| 步骤 | 工作量 | 说明 |
|------|--------|------|
| 创建文件 | 1个 | process_action.py |
| 实现函数 | 5个 | 见函数清单 |
| 更新调用 | 1处 | chat_stream.py |
| 编译检查 | 1次 | python -m py_compile |
| 代码审查 | 1次 | 小健检查 |

---

**文档状态**: 待实现
**待办**: 按本设计创建 types/process_action.py 文件
