# TaskMemory 设计方案

**创建时间**: 2026-06-16 13:08:20
**版本**: v1.0
**作者**: 小健

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-16 13:08:20 | 小健 | 初始版本，TaskMemory设计方案 |

---

## 1 问题背景

### 1.1 XC-10 暴露的核心问题

用户给出多步骤任务（如"搜索AI新闻 → 保存文件 → 查询时间 → 发送通知"），Agent 在执行过程中：

- trim_history 裁剪旧 observation → LLM 丢失早期上下文
- LLM 不记得已执行过哪些工具 → 重复调用（如 search_web 重复15次）
- 最终超时失败

### 1.2 现有机制的缺陷

| 机制 | 作用 | 缺陷 |
|------|------|------|
| observation | 工具返回结果给 LLM | 受 trim_history 裁剪，不可靠 |
| TaskTracker (task_tracker.py) | 持久化到 DB | 只写不读，LLM 看不到 |
| agent.steps | 记录执行步骤 | 未用于 LLM 上下文 |

**根本原因**：Agent 在无状态循环中执行有状态的任务。每次 LLM 调用都是独立的，但用户的任务有进度、有依赖、有完成状态。

---

## 2 设计目标

### 2.1 核心原则

**普遍意义**：设计不局限于某个具体问题，而是解决一类问题。

| 原则 | 说明 |
|------|------|
| 通用性 | 适用于任何多步骤任务，不绑定具体工具 |
| 最小化 | 不加新状态，从已有数据派生 |
| 存活性 | 不受 trim_history 影响 |
| 自然性 | 融入现有架构，不强行改造 |

### 2.2 抽象模型

**问题本质**：Agent 需要"工作记忆"——一个跨越 LLM 调用、不受上下文裁剪的任务状态。

**通用解法**：

```
用户任务 → Agent 执行（已有 steps）→ 派生摘要 → 注入 LLM 上下文
```

不额外记录，不读 DB，从已有的 agent.steps 派生。

---

## 3 方案设计

### 3.1 TaskMemory 类

```python
class TaskMemory:
    """Agent 工作记忆 — 从 agent.steps 派生任务进度
    
    通用性: 适用于任何多步骤任务
    最小化: 不加新状态，从已有数据派生
    存活性: 作为 system message 注入，不受 trim_history 影响
    """

    def __init__(self, agent):
        self.agent = agent  # 引用，不复制

    def to_context(self) -> str:
        """从 agent.steps 派生摘要"""
        completed = []
        for step in self.agent.steps:
            if hasattr(step, 'tool_name'):
                completed.append(f"{step.tool_name} ✓")
        if not completed:
            return ""
        recent = completed[-8:]
        lines = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(recent))
        return f"[Task Memory]\n{lines}"
```

### 3.2 数据流

```
用户任务
    ↓
Agent 开始执行
    ↓
每次 tool 执行 → 步骤记录到 agent.steps（已有机制，不改）
    ↓
每次 LLM 调用前 → TaskMemory.to_context() 从 agent.steps 派生摘要
    ↓
注入为 system message → LLM 看到完整的任务进度
```

### 3.3 LLM 看到的效果

```
[System Message]
[Task Memory]
  1. search_web(query=AI新闻) ✓
  2. write_text_file(path=ai_news.txt) ✓
  3. time_now() ✓
```

LLM 知道已完成3步，自然知道下一步该做什么。

---

## 4 集成点

### 4.1 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `base_agent.py` | 加 `self.task_memory = None` | 1行 |
| `initialize_run_state.py` | 创建 `TaskMemory(agent)` | 2行 |
| `message_builder.py` | `prepare_messages_for_llm()` 注入 `to_context()` | 5行 |

**总计**: ~8行代码，无新文件。

### 4.2 集成位置

**base_agent.py** — Agent 初始化：
```python
self.task_memory = None
```

**initialize_run_state.py** — 每次任务开始：
```python
from app.services.agent.task_memory import TaskMemory
agent.task_memory = TaskMemory(agent)
```

**message_builder.py** — 构建 LLM 消息：
```python
def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
    # ... 已有逻辑 ...
    
    # 注入 Task Memory
    if self.agent.task_memory:
        context = self.agent.task_memory.to_context()
        if context:
            messages.insert(-1, {"role": "system", "content": context})
    
    return messages
```

---

## 5 为什么是通用的

### 5.1 不绑定具体工具

```python
# 任何工具都能被记录
task_memory.record("search_web", {...}, True)   # 搜索
task_memory.record("write_text_file", {...}, True)  # 写文件
task_memory.record("http_request", {...}, True)  # API调用
task_memory.record("execute_sql", {...}, True)   # 数据库操作
```

### 5.2 不绑定具体任务类型

| 任务类型 | 适用性 |
|---------|--------|
| 信息检索（搜索、查询） | ✅ |
| 文件操作（读写、复制） | ✅ |
| 数据处理（转换、分析） | ✅ |
| 通知发送（邮件、消息） | ✅ |
| 任意组合 | ✅ |

### 5.3 不依赖 observation

- observation 受 trim_history 裁剪 → 不可靠
- TaskMemory 从 agent.steps 派生 → 独立于 observation
- 注入为 system message → 不被裁剪

---

## 6 与其他方案的对比

| 方案 | 数据源 | 改动量 | 通用性 | 存活性 |
|------|--------|--------|--------|--------|
| 在 observation 加进度 | observation | 中 | 低 | 低 |
| 读 DB 派生 | task_tracker.db | 大 | 中 | 高 |
| **从 agent.steps 派生** | **内存** | **小** | **高** | **高** |

---

## 7 总结

### 7.1 设计要点

1. **抽象**：不是解决"search_web 重复"，而是给 Agent 加通用工作记忆
2. **最小化**：不加新状态，从已有 agent.steps 派生
3. **存活性**：作为 system message 注入，不受 trim_history 影响
4. **通用性**：适用于任何多步骤任务，不绑定具体工具

### 7.2 核心思想

```
Agent 已经在记录执行步骤（agent.steps）
只是没有把这些步骤反馈给 LLM
TaskMemory 就是这座桥
```

---

**更新时间**: 2026-06-16 13:08:20
**版本**: v1.0
**编写人**: 小健
