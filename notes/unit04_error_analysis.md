# Unit04 测试记录错误深度分析报告

## 基本信息
- **会话ID**: 2ef65734-1120-4566-b1e0-c8fd6c3ee2b0
- **AI消息ID**: 4285
- **开始时间**: 2026-07-04 14:24:56
- **结束时间**: 2026-07-04 15:04:31
- **持续时间**: 2375.62秒（约39分钟）
- **LLM调用次数**: 100次
- **最终状态**: FAILED

---

## 错误分类表

| 错误类型 | 出现位置 | 出现次数 | 根因分析 | 是堵截还是源头问题 | 建议修复方向 |
|---------|---------|---------|---------|-------------------|------------|
| **LLM循环死锁** | react_cycle.py | 100次调用 | LLM反复调用相同工具相同参数，系统无循环检测 | **源头问题** | 实现循环检测机制 |
| **上下文爆炸** | message_builder.py | 持续增长 | prompt从几千token增长到75386 token | **源头问题** | 优化上下文管理策略 |
| **RemoteProtocolError** | base_service.py | 1次 | 上下文过大导致API超时断开 | **连锁反应** | 限制单次prompt大小 |
| **循环结束无终态** | react_cycle.py:365 | 1次 | max_steps耗尽但未达到COMPLETED状态 | **堵截手段** | 改进终止条件判断 |
| **listdir结果截断** | list_directory.py:214 | 多次 | 目录内容过多（288项）被截断 | **预期行为** | 优化listdir分页机制 |
| **安全检查中风险** | execute_code.py/execute_shell_command_safety.py | 多次 | 代码中包含文件写入/删除操作 | **安全机制** | 正常工作 |

---

## 详细分析

### 1. LLM循环死锁（核心问题）

**现象**:
- 步骤6-9：反复读取 `hello.txt` 和 `capabilities.md`（完全相同的文件，相同内容）
- 步骤1-3：反复调用 `listdir(E:\test_dir)`（相同参数）
- 整个100次调用中，大量重复调用相同工具

**根因分析**:
```
用户任务："列出E:\test_dir下的所有文件 你自己 执行从file 网络 获取和网络测试 代码执行 系统管理 监控等都执行一系列操作"
```

任务描述过于宽泛，LLM无法确定何时完成。每次调用工具后，LLM认为任务还未完成，继续调用工具。由于上下文裁剪，LLM可能忘记了之前已经做过的操作，导致循环重复。

**代码层面问题**:
- `react_cycle.py` 没有任何循环检测逻辑
- 没有检测"连续N次相同tool+相同参数"的机制
- 没有检测"任务进展停滞"的机制

### 2. 上下文爆炸

**证据**:
- 第1次LLM调用：tokens=16360(prompt=16326+completion=34)
- 第100次LLM调用：tokens=75568(prompt=75386+completion=182)
- 增长了4.6倍

**根因分析**:
- 每次工具调用都会产生observation，这些observation会累积到上下文中
- trim_history在5746232字符时触发，但只裁剪到10条消息
- 裁剪策略是"从最新往最旧扫，按配对收集"，可能丢失了关键的历史信息

**代码问题**:
```python
# message_builder.py:200-203
if total > self.MAX_CONTEXT_CHARS * 0.8:
    always_keep_chars = self._total_chars(system_msgs) + self._total_chars(user_msgs)
    available_budget = max(0, int(self.MAX_CONTEXT_CHARS * 0.7) - always_keep_chars)
    trimmed = self._trim_to_budget(obs_list, assistant_msgs, available_budget)
```
- 裁剪后只保留70%的预算给工具调用历史
- 但没有考虑"去重"或"摘要"机制

### 3. RemoteProtocolError

**证据**:
```
2026-07-04 15:04:31,633 - INFO - llm_stream.py:154 - [FC] 解析结果: tool_calls(1)=['listdir'], tokens=75568(prompt=75386+completion=182), llm_dur=81.11s
20595-2026-07-04 15:03:10,526 - WARNING - base_service.py:261 - [Retry][L1] 重试 1/3, 等待2秒, 错误: [RemoteProtocolError] Server disconnected without sending a response.
```

**根因分析**:
- 第100次LLM调用耗时81.11秒（正常约8-20秒）
- prompt token达到75386，接近或超过模型上下文窗口限制
- 服务器因处理超大请求超时断开

### 4. 循环结束无终态

**证据**:
```python
# react_cycle.py:360-371
if agent.status not in (
    AgentStatus.COMPLETED,
    AgentStatus.FAILED,
    AgentStatus.CANCELLED,
):
    logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 设为FAILED")
    set_failed(agent, f"ReAct循环结束但无终态(status={agent.status})")
```

**问题**:
- 这是一个"堵截"手段，不是"源头"解决
- max_steps=100耗尽后，循环退出，但agent.status仍为THINKING
- 说明LLM从未返回"answer"类型的响应来结束任务

---

## 代码缺陷总结

### 缺陷1：无循环检测机制
**位置**: react_cycle.py
**问题**: 没有检测连续相同工具调用的机制
**影响**: LLM陷入死循环，浪费大量token和时间

### 缺陷2：上下文管理策略缺陷
**位置**: message_builder.py
**问题**: 裁剪后上下文不足以让LLM了解已完成的操作
**影响**: LLM忘记已做过的操作，重复调用

### 缺陷3：终止条件判断不完善
**位置**: react_cycle.py
**问题**: 只靠max_steps硬截断，没有语义级别的终止判断
**影响**: 任务可能在任何状态下被强制终止

### 缺陷4：无任务进展检测
**位置**: react_cycle.py
**问题**: 没有检测"连续N步无进展"的机制
**影响**: LLM在原地打转，系统无法干预

---

## 修复建议

### 短期修复（堵截层改进）
1. 在react_cycle.py中添加循环检测：连续3次相同tool+相同参数 → 注入warning并强制转向
2. 在message_builder.py中添加摘要机制：对重复的observation进行合并

### 中期修复（源头解决）
1. 实现任务状态追踪：记录已完成的操作，避免重复
2. 实现进展停滞检测：连续N步无新信息 → 强制进入总结阶段
3. 优化上下文裁剪策略：保留关键的"已完成操作"摘要

### 长期修复
1. 引入任务规划模块：在执行前明确任务边界和完成条件
2. 实现动态max_steps：根据任务复杂度动态调整

---

## 附录：关键日志证据

### 循环死锁证据
```
步骤6: readtext → E:\test_dir\hello.txt（18字节，"你好，世界！"）
步骤7: readtext → E:\test_dir\capabilities.md（555字节）
步骤8: readtext → E:\test_dir\capabilities.md（555字节，完全相同）
步骤9: readtext → E:\test_dir\capabilities.md（555字节，完全相同）
步骤10: listdir → E:\test_dir（288项，已截断）
步骤11: readtext → E:\test_dir\hello.txt（18字节，完全相同）
```

### 上下文增长证据
```
LLM调用#1: tokens=16360(prompt=16326+completion=34), llm_dur=27.61s
LLM调用#100: tokens=75568(prompt=75386+completion=182), llm_dur=81.11s
```

### RemoteProtocolError证据
```
[Retry][L1] 重试 1/3, 等待2秒, 错误: [RemoteProtocolError] Server disconnected without sending a response.
```

---

编写人：chendyg  
日期：2026-07-04
