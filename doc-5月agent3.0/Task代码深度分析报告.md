# Task 代码深度分析报告

**创建时间**: 2026-05-28 18:29:48
**版本**: v1.0
**分析人**: 小沈
**文档性质**: 深度代码分析

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-28 18:29:48 | 小沈 | 初始版本：10 个问题分析 + 修复方案 |
| v1.1 | 2026-05-28 18:40:55 | 小沈+北京老陈 | 新增 TASK-011~014（docstring说谎、GenericTaskTracker不继承基类、_deprecated_imports.py违反铁规、sequence_number旧名残留）；增强 TASK-001/+TASK-003；更新总计为14个问题 |

---

## 一、task 相关的架构全景图

```
react_agent_mixin.py ──→ get_task_tracker() ──→ TaskExecutionTracker
                                                        │
                                     ┌──────────────────┼──────────────────┐
                                     ▼                  ▼                  ▼
                           get_task_service()    GenericTaskTracker   其他意图
                           ────────────────       (内存dict)
                                 │
                     TaskOperationService
                     (TaskServiceBase + TaskStatsMixin)
                     ───────────────────────────────
                     │  SQLite operations_db
                     │  task_operations 表
                     │
                     ▼
           operation_history.py ←── get_task_service()
           file_tools.py ←── get_task_tracker() + get_task_service()
           file_safety.py ←── TaskRecord (model)
```

### 1.1 架构问题概要（北京老陈 2026-05-28）

| # | 问题 | 原则 | 影响 |
|---|------|------|------|
| 1 | `TaskStatsMixin` 死代码 — `__init__` 也未调用 | YAGNI | 虚占继承链 |
| 2 | `_init_db()` 空壳 | YAGNI | 误导维护者 |
| 3 | docstring 说大话 ("生成会话报告") | KISS | 信任损耗 |
| 4 | 连接管理 4 份重复 | DRY | 改一处漏四处 |
| 5 | `GenericTaskTracker` 不继承基类 | OCP/LSP | 多态失效 |
| 6 | `_deprecated_imports.py` 向后兼容 | 铁规 | 直接违规 |

---

### 1.2 分析范围

| 文件 | 行数 | 职责 |
|------|------|------|
| `backend/app/services/agent/task_base.py` | 171 | TaskServiceBase ABC + TaskStatsMixin |
| `backend/app/services/agent/task_service.py` | 193 | TaskOperationService (SQLite 实现) |
| `backend/app/services/agent/mixins/task_tracker.py` | 120 | TaskExecutionTracker (路由层) + GenericTaskTracker |
| `backend/app/services/agent/universal_react.py` | 177 | UniversalReactAgent (使用 _task_tracker) |
| `backend/app/api/v1/operation_history.py` | ~50 | API 路由 (含死代码 `_get_session`) |
| `backend/app/services/tools/file/file_tools.py` | - | 使用 get_task_tracker / get_task_service |
| `backend/app/services/safety/file/file_safety.py` | - | 使用 TaskRecord 模型 |
| `backend/app/db/operations_db.py` | - | 建表 |
| `backend/app/db/models/operation_models.py` | - | TaskRecord Pydantic 模型 |

**分析对照原则**: SRP / DRY / KISS / SLAP / YAGNI / 禁止向后兼容 / OCP / LSP / ISP

---

## 二、评估总览

| 原则 | 结论 | 违反问题数 |
|------|------|-----------|
| **SRP** — 单一职责 | ❌ 违反 | 1 |
| **DRY** — 不重复 | ❌ 违反 | 1 |
| **KISS** — 保持简单 | ❌ 违反 | 2（含 docstring 说谎） |
| **SLAP** — 同一抽象层 | ⚠️ 部分违反 | 1 |
| **YAGNI** — 不要过度设计 | ❌ 违反 | 3 |
| 禁止向后兼容 | ❌ 违反 | 1（铁规直达） |
| **OCP** — 开闭原则 | ❌ 违反 | 2 |
| **LSP** — 里氏替换 | ❌ 违反 | 1（不可替换） |
| **ISP** — 接口隔离 | ✅ 合规 | 0 |

**总计**: 14 个问题 (P1 x 6, P2 x 4, P3 x 4)

---

## 三、问题清单与修复方案

### 问题 TASK-001: TaskStatsMixin._stats_cache 废弃代码 <span style="color:red">(🔴 P1 — YAGNI/SRP)</span>

**现象**: `TaskStatsMixin` 维护一个内存 dict `_stats_cache`，并提供了 `get_task_stats()` 和 `update_task_stats()` 两个公有方法。但全项目 0 消费者 — 没有任何代码调用这两个方法，`_stats_cache` 也从未被外部读取。

**根因分析**: session→task 命名纠正前的遗留设计。老代码用内存 cache 保存统计信息，现在统计字段已全部存储在 SQLite `task_operations` 表中（`status`, `created_at`, `completed_at` 等）。Mixin 凭空维护了两套数据源，且内存那套根本没人用。

**额外发现（北京老陈 2026-05-28）**: `TaskOperationService.__init__`（`task_service.py:43`）只有 `pass`，完全没调用 `super().__init__()`。这意味着 `TaskStatsMixin.__init__` 根本不会执行，`self._stats_cache` dict 永远不会初始化。即使未来有人调用 `get_task_stats()`/`update_task_stats()`，也会因 `_stats_cache` 不存在而抛 AttributeError。这进一步证明 Mixin 是纯摆设。

**文件**: `backend/app/services/agent/task_base.py:120-165`

**修复方案**:
1. 删除 `TaskStatsMixin` 整个类（只含 `_stats_cache`、`get_task_stats`、`update_task_stats`）
2. 如果未来需要统计功能，直接从 SQLite `task_operations` 表查询
3. 删除 `task_base.py:168-171` 的 `__all__` 中 `TaskStatsMixin` 的导出（如果有引用则一并清理）

```python
# 删除前
class TaskStatsMixin:
    def __init__(self):
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
    def get_task_stats(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._stats_cache.get(task_id)
    def update_task_stats(self, task_id, total_operations=0, ...):
        self._stats_cache[task_id] = {...}

__all__ = ["TaskServiceBase", "TaskStatsMixin"]

# 删除后
__all__ = ["TaskServiceBase"]
```

**验证**: `grep -r "get_task_stats\|update_task_stats\|TaskStatsMixin"` 确认无引用后删除

---

### 问题 TASK-002: `_init_db()` 空壳方法 <span style="color:red">(🔴 P1 — YAGNI)</span>

**现象**: `TaskOperationService._init_db()` 方法体只有 `pass`，注释写"此处无需任何操作"。

**根因分析**: 是 2026-05-22 重构后的遗留。建表逻辑已由 `app.db.operations_db` 模块级 `init_database()` 统一处理，`_init_db` 方法未同步删除。

**文件**: `backend/app/services/agent/task_service.py:48-52`

**修复方案**:
```python
# 删除前
def _init_db(self):
    """初始化数据库（建表已由app.db.operations_db模块级处理）"""
    pass

# 删除后
# 整段删除
```

**注意**: 确认 `__init__` 方法和外部是否调用过 `self._init_db()`。从当前代码看 `__init__`（第43行）只有 `pass`，无调用。

---

### 问题 TASK-003: 连接管理重复 4 次 <span style="color:red">(🔴 P1 — DRY)</span>

**现象**: `create_task` / `complete_task` / `get_task` / `get_recent_tasks` 四个方法各自独立实现完全相同的连接管理模板：

```python
conn = None
try:
    conn = self._get_connection()
    cursor = conn.cursor()
    # ... 业务逻辑 ...
    conn.commit()           # 或 return
except Exception as e:
    logger.error(...)
    raise                   # 或 return None / []
finally:
    if conn:
        conn.close()
```

**根因分析**: 复制粘贴，未抽取公共方法。违反 DRY 原则。

**额外发现（北京老陈 2026-05-28）**: `_get_connection()` 已经存在（`task_service.py:54`），封装了 `get_operations_connection()` 调用，但各方法只把它当成一行转发调用，仍然在方法内部做完整的 try/except/finally 连接管理。应进一步封装为上下文管理器或装饰器，`_get_connection()` 本身不足以消除重复。

**文件**: `backend/app/services/agent/task_service.py:71-182`

**修复方案**: 抽取一个上下文管理器或装饰器

**方案 A — 装饰器**（推荐）:
```python
from functools import wraps

def with_task_db(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        conn = None
        try:
            conn = self._get_connection()
            return func(self, conn, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{func.__name__}] DB error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    return wrapper
```

各方法只关注业务逻辑：
```python
@with_task_db
def create_task(self, conn, agent_id, task_description):
    task_id = self._generate_task_id()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO ...', (...))
    conn.commit()
    return task_id

@with_task_db
def complete_task(self, conn, task_id, success=True):
    cursor = conn.cursor()
    cursor.execute('UPDATE ...', (...))
    conn.commit()
```

---

### 问题 TASK-004: `_get_session()` 死代码 <span style="color:red">(🔴 P1 — 死代码/旧名残留)</span>

**现象**: `operation_history.py:45` 定义了 `_get_session()` 函数，函数名残留旧名 "session"，而且全项目零引用，是死代码。

**文件**: `backend/app/api/v1/operation_history.py:45-48`

**修复方案**:
```python
# 删除前
def _get_session():
    """获取任务服务实例"""
    return get_task_service()

# 删除后 → 整段删除
```

**验证**: `grep -r "_get_session" backend/` 确认只有定义行。

---

### 问题 TASK-005: `universal_react.py` 中 `create_task` 调用不可达 <span style="color:red">(🔴 P1 — 死代码)</span>

**现象**: `universal_react.py:_run_with_task_tracking` 第 111-118 行有一整段 if 分支用于调用 `_task_tracker.create_task()`，但该分支永不执行。

**根因分析**: 
1. `UniversalReactAgent.__init__`（第36-37行）强制要求 `task_id` 为非空，否则抛 ValueError
2. 因此 `self.task_id` 一定为非空字符串
3. `_run_with_task_tracking` 第108行 `task_id = self.task_id or ""` 结果始终为 truthy
4. 第111行 `if not task_id:` 条件永远为 False

连带地，第168-177行的 `finally` 块中 `if session_created_by_this_run` 也同样是死代码（因为 `session_created_by_this_run` 只可能在 if 分支内变为 True）。

**文件**: `backend/app/services/agent/universal_react.py:108-177`

**修复方案**: 删除不可达的 if 分支和关联的 finally 清理逻辑

```python
async def _run_with_task_tracking(self, task, context=None, system_prompt=None):
    task_id = self.task_id
    
    result = None
    try:
        async for event in self.run_stream(task, context):
            # ... 处理事件 ...
        # ... 处理 result ...
        return result
    except Exception as e:
        # ... 错误处理 ...
        return result
    # finally 块中仅保留非 session 清理逻辑
```

---

### 问题 TASK-006: 4 层调用链过度曲折 <span style="color:orange">(🟡 P2 — KISS)</span>

**现象**: 从 Mixin 到实际数据库操作的调用链：

```
react_agent_mixin._run_with_task_tracking()
    → self._task_tracker.create_task(agent_id, task_description)
        → TaskExecutionTracker.get_tracker(agent_id)
            → TaskOperationService.create_task(agent_id, task_description)
                → SQLite INSERT
```

中间层 `TaskExecutionTracker.create_task` 除了转发调用外，只做了 `hasattr` 检查和 try/except 包裹，逻辑价值极低。

**文件**: `backend/app/services/agent/mixins/task_tracker.py:51-67`

**修复方案**: 
1. 将 `TaskOperationService` 直接注册到 agent 中，跳过 `TaskExecutionTracker` 路由层
2. 或合并 `TaskExecutionTracker` 和 `GenericTaskTracker` 为一个统一接口

```python
# 方案: 减少一层
# task_tracker 中直接提供 get_task_service() 返回的单例
# agent 直接调用 get_task_service().create_task()
```

---

### 问题 TASK-007: `create_task` 形参 `task_id` 未使用 <span style="color:orange">(🟡 P2 — KISS/YAGNI)</span>

**现象**: `TaskExecutionTracker.create_task(self, task_id, agent_id, task_description)` 中 `task_id` 参数从未在方法体内使用。方法内部的注释也解释了不应转发 `task_id`，但参数依然保留在签名中，造成 API 误解。

**文件**: `backend/app/services/agent/mixins/task_tracker.py:51`

**修复方案**: 从签名中删除 `task_id` 参数

```python
# 修改前
def create_task(self, task_id: str, agent_id: str, task_description: str):

# 修改后  
def create_task(self, agent_id: str, task_description: str):
```

---

### 问题 TASK-008: 8 个意图类型硬编码 <span style="color:orange">(🟡 P2 — OCP)</span>

**现象**: `_init_generic_tracker()` 硬编码了 8 个意图名称：

```python
for intent in ['time', 'shell', 'network', 'desktop', 'database', 
               'system', 'document', 'code_execution']:
```

新增意图时必须修改此文件，违反 OCP（开闭原则）。

**文件**: `backend/app/services/agent/mixins/task_tracker.py:43-44`

**修复方案**: 从 `AgentConfig` 或 `ToolCategory` 枚举读取所有意图类型

```python
from app.services.tools.registry import ToolCategory

def _init_generic_tracker(self):
    self._generic_tracker = GenericTaskTracker()
    for cat in ToolCategory:
        if cat.value != 'file':  # file 已有专用 tracker
            self._trackers[cat.value] = self._generic_tracker
```

---

### 问题 TASK-009: 一行方法封装 <span style="color:blue">(🔵 P3 — YAGNI)</span>

**现象**: `task_base.py:101-117` 中有两个方法各自只封装了一行代码：

```python
def _generate_task_id(self) -> str:
    return f"task-{uuid4().hex}"

def _get_current_timestamp(self) -> datetime:
    return datetime.now()
```

8 行文档字符串 + 4 行空白 + 2 行实际代码 = 夸张的封装。直接增加阅读负担，无实际封装价值。

**文件**: `backend/app/services/agent/task_base.py:101-117`

**修复方案**: 
1. 删除这两个方法
2. 调用处直接写 `f"task-{uuid4().hex}"` 和 `datetime.now()`

---

### 问题 TASK-010: SQL 裸写在业务方法中 <span style="color:blue">(🔵 P3 — SLAP)</span>

**现象**: 4 个业务方法各自包含完整的 SQL 字符串 + 占位符参数 + cursor 操作，SQL 与 Python 业务逻辑混在一起：

```python
# task_service.py:76-83
cursor.execute('''
    INSERT INTO task_operations 
    (task_id, agent_id, task_description, status, created_at)
    VALUES (?, ?, ?, ?, ?)
''', (task_id, agent_id, task_description, 
      OperationStatus.PENDING.value, datetime.now()))
```

违反 SLAP（同一抽象层原则）— 高层业务编排（"创建任务"）与底层数据库细节（SQL）混在一起。

**文件**: `backend/app/services/agent/task_service.py:71-182`

**修复方案**: 抽取常量 SQL 模板或将 SQL 放入独立的方法/文件

```python
# 方案: 常量 + 命名参数
_SQL_CREATE_TASK = '''
    INSERT INTO task_operations 
    (task_id, agent_id, task_description, status, created_at)
    VALUES (:task_id, :agent_id, :description, :status, :now)
'''

_SQL_COMPLETE_TASK = '''
    UPDATE task_operations 
    SET status = :status, completed_at = :now
    WHERE task_id = :task_id
'''

_SQL_GET_TASK = 'SELECT * FROM task_operations WHERE task_id = ?'
_SQL_RECENT_TASKS = 'SELECT * FROM task_operations ORDER BY created_at DESC LIMIT ?'
```

---

### 问题 TASK-011: docstring 说谎 + 旧名残留 <span style="color:red">(🔴 P1 — KISS/旧名残留)</span>

**现象**: `TaskOperationService` 的类 docstring（`task_service.py:37-40`）声称：
```
功能：
1. 创建和管理会话
2. 更新会话状态和统计
3. 生成会话报告
```

但该类根本没有 `generate_report` 方法，也没有任何"更新会话状态和统计"的相关方法。而且 docstring 仍用"会话"（session）而非"任务"（task）。

**根因分析**: 类名已改为 `TaskOperationService`，但 docstring 从未同步更新。属于文档与代码不一致，降低了代码信任度。

**文件**: `backend/app/services/agent/task_service.py:37-41`

**修复方案**: 重写 docstring 反映实际能力

```python
class TaskOperationService(TaskServiceBase, TaskStatsMixin):
    """
    文件操作任务服务

    管理 file 意图的文件操作任务的创建、完成、查询。

    功能：
    1. 创建文件操作任务
    2. 完成任务并记录状态
    3. 查询单个/最近任务
    """
```

---

### 问题 TASK-012: GenericTaskTracker 不继承基类 <span style="color:red">(🔴 P1 — OCP/LSP)</span>

**现象**: 当前架构中有两个任务追踪实现：

| 类 | 继承 | 存储 | 意图 |
|----|------|------|------|
| `TaskOperationService` | `TaskServiceBase, TaskStatsMixin` | SQLite `task_operations` 表 | file |
| `GenericTaskTracker` | **无基类** | 内存 dict | 其他 8 个意图 |

`GenericTaskTracker` 没有继承 `TaskServiceBase`，两者是两条平行的独立实现，没有统一接口契约。

**根因分析**: 开发初期 `GenericTaskTracker` 作为轻量方案快速实现，后期未对齐到 `TaskServiceBase`。这导致：
1. **OCP 违反**: 无法通过基类接口统一操作两种 tracker
2. **LSP 违反**: `GenericTaskTracker` 不能替换 `TaskOperationService` 的位置，反之亦然
3. 调用方（`TaskExecutionTracker`）必须用 `hasattr` 判断方法是否存在，而不是依赖接口契约

**文件**: `backend/app/services/agent/mixins/task_tracker.py:80-108` vs `backend/app/services/agent/task_base.py:6-99`

**修复方案**:

**方案 A（推荐）**: 让 `GenericTaskTracker` 继承 `TaskServiceBase`，补全接口方法
```python
class GenericTaskTracker(TaskServiceBase):
    """通用任务追踪器（非file意图使用）"""
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
    
    def create_task(self, agent_id: str, task_description: str) -> str:
        task_id = self._generate_task_id()
        ...
    
    def complete_task(self, task_id: str, success: bool = True):
        ...
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)
    
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        ...
```

**方案 B**: 将 `TaskServiceBase` 改为 Protocol（接口契约），两个类都实现它。

---

### 问题 TASK-013: `_deprecated_imports.py` 违反"绝不搞向后兼容"铁规 <span style="color:red">(🔴 P1 — 铁规直达)</span>

**现象**: `backend/app/services/agent/_deprecated_imports.py` 文件头部声明"绝不搞向后兼容，旧名必须彻底清除"（第3行），但其自身功能就是提供向后兼容的懒加载导入：

```python
# 当旧路径导入时，通过 __getattr__ 懒加载实际模块
def __getattr__(name: str):
    if name in ("FileOperationSafety", "FileSafetyConfig", "get_file_safety_service"):
        from app.services.safety.file.file_safety import ...
        return locals()[name]
    if name in ("FileTools", "get_file_tools"):
        from app.services.tools.file.file_tools import ...
        return locals()[name]
```

该文件被 `__init__.py`（第24行）引用：`from ._deprecated_imports import __getattr__`

所以 `from app.services.agent import FileTools` 这类旧导入路径依然有效。

**根因分析**: 2026-05-27 重构时将旧名兼容代码从 `__init__.py` 拆分到独立文件，但保留了向后兼容能力。与"绝不搞向后兼容"铁规直接冲突。

**文件**: `backend/app/services/agent/_deprecated_imports.py:1-40` + `backend/app/services/agent/__init__.py:24`

**修复方案**:
1. 删除 `_deprecated_imports.py` 文件
2. 搜索项目中所有使用旧导入路径的代码
3. 改为新路径导入：
   - `from app.services.agent import FileTools` → `from app.services.tools.file.file_tools import FileTools`
   - `from app.services.agent import FileOperationSafety` → `from app.services.safety.file.file_safety import FileOperationSafety`
4. 删除 `__init__.py` 中对 `_deprecated_imports` 的引用
5. 在 version.txt 记录此变更

**验证**: `grep -r "from app.services.agent import" backend/` 确认无旧路径残留

---

### 问题 TASK-014: `sequence_number` 描述残留"会话"旧名 <span style="color:blue">(🔵 P3 — 旧名残留)</span>

**现象**: `operation_models.py:56` 中 `sequence_number` 字段的 description 仍用旧名"会话"：
```python
sequence_number: int = Field(default=0, description="会话内操作顺序号")
```
应为"任务内操作顺序号"。

**文件**: `backend/app/db/models/operation_models.py:56`

**修复方案**: 更新 description 文本

```python
sequence_number: int = Field(default=0, description="任务内操作顺序号")
```

---

## 四、修复优先级

| 优先级 | 问题 | 原则 | 工作量 | 影响 |
|--------|------|------|--------|------|
| **P0** | TASK-005: 死代码分支 | YAGNI | 小 (1 文件) | 消除误导代码 |
| **P0** | TASK-004: `_get_session` 死代码 | 死代码 | 极小 | 清理旧名残留 |
| **P0** | TASK-013: `_deprecated_imports` 向后兼容 | 铁规直达 | 中 (搜索全项目) | 消除铁规违反 |
| **P1** | TASK-011: docstring 说谎 | KISS | 极小 | 信任修复 |
| **P1** | TASK-003: 连接重复 4 次 | DRY | 中 (1 文件) | 核心代码质量 |
| **P1** | TASK-001: _stats_cache 废弃 | YAGNI/SRP | 极小 | 消除无用状态 |
| **P1** | TASK-012: GenericTaskTracker 不继承基类 | OCP/LSP | 中 (1 文件) | 架构对齐 |
| **P2** | TASK-002: `_init_db` 空壳 | YAGNI | 极小 | 2 行清理 |
| **P2** | TASK-007: create_task 形参 | KISS | 极小 | API 清晰 |
| **P2** | TASK-008: 硬编码 8 意图 | OCP | 小 | 扩展友好 |
| **P3** | TASK-006: 4 层调用链 | KISS | 中 | 架构简化 |
| **P3** | TASK-009: 一行封装 | YAGNI | 极小 | 代码简洁 |
| **P3** | TASK-010: SQL 裸写 | SLAP | 小 | 抽象清晰 |
| **P3** | TASK-014: sequence_number 描述旧名 | 旧名残留 | 极小 | 命名一致性 |

---

## 五、修复策略建议

### 波次建议

| 波次 | 包含问题 | 说明 |
|------|---------|------|
| **Wave 1** | TASK-004, TASK-005, TASK-002, TASK-011, TASK-014 | 死代码+旧名清理，零风险，立即执行 |
| **Wave 2** | TASK-001, TASK-007, TASK-009, TASK-013 | 小改动+清理 backward compat |
| **Wave 3** | TASK-003, TASK-010 | 抽取公共模式，需回归测试 |
| **Wave 4** | TASK-008, TASK-006, TASK-012 | 架构调整，需全面测试 |

---

## 六、补充说明

### 6.1 关于 TASK-005 的特别说明

在分析中发现的 `universal_react.py` 的 create_task 调用不可达问题，根因是 `__init__` 强制执行了 `task_id` 非空校验（2026-05-22 的构造器变更），但关联的 `_run_with_task_tracking` 方法中的条件分支未同步删除。

虽然该路径不会导致运行时崩溃（因为不可达），但保留了:
1. 误导的代码（看起来能创建 session 但实际上不能）
2. 废弃的 finally 清理逻辑
3. 未来如果有人修改了构造器校验逻辑，可能意外激活一个有 bug 的代码路径

**建议**: 立即删除该不可达分支。

### 6.2 未纳入的问题

以下问题在分析中被识别但不属于本报告范围:

| 问题 | 原因 |
|------|------|
| Singleton 模式 (get_task_service) | 项目约定，非本模块问题 |
| 日志格式不统一 | 跨文件规范问题，需单独规范 |
| 缺少类型注解 | 已有类型注解，未发现缺失 |

---

**报告完成时间**: 2026-05-28 18:46:53
**分析人**: 小沈 + 北京老陈
task的 需求 
task_id 是 task-{uuid4().hex} 格式（如 task-a1b2c3d4e5f6...），自动生成。

task 关联的数据模型（两个 Pydantic 模型 + 一个 DB 表）：

TaskRecord（任务记录主体）
task_operations 表字段：

task_id, agent_id, task_description, status
统计：total_operations, success_count, failed_count, rolled_back_count
报告：report_generated, report_path
时间：created_at, completed_at
OperationRecord（操作记录明细）
file_operations 表字段：

operation_id, task_id（关联到任务）
operation_type, status
source_path, destination_path, backup_path
file_size, file_hash
sequence_number（回滚顺序）
状态枚举（OperationStatus）
状态	含义	适用
PENDING	待执行	刚创建
EXECUTING	执行中	正在处理
SUCCESS	成功完成	正常结束
FAILED	执行失败	出错了
ROLLBACK	已回滚	被撤销了
使用链路：task_id 是主键串联 — TaskRecord 记录一次文件操作任务的整体情况，OperationRecord 记录该任务内的每一次具体文件操作（移动/复制/删除等），通过 task_id 关联，sequence_number 决定回滚顺序。
