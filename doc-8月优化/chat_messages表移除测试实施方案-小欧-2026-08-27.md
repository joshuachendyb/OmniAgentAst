# chat_messages 表移除测试实施方案

**版本**: v1.0
**创建时间**: 2026-08-27 15:33:47
**创建人**: 小欧
**更新要点**: 初版 — 风险准确说明 + fail-safe 概念解释 + 精确到文件/行/代码块的严密实施步骤

---

## 一、背景与当前定位

`chat_messages` 自 **2026-08-22 铁律** + **2026-08-23 北京老陈裁定"写保留当空气"** 后，已被改造为**纯只写镜像表，系统零读取依赖**：

- 所有运行时**读**已迁移到结构化表：`chat_user_message`（用户/AI消息）、`chat_task_steps`（步骤）、`chat_tasks`（任务，含 `ai_message_id`）、`chat_sessions`、`token_usage`、`chat_session_trust`
- **外键已解除**（锚B解除，`backend/app/db/db_initializer.py:48-52`）：`chat_task_steps` 不再 `REFERENCES chat_messages(id)`，无级联依赖
- **id 分配锚已迁移**（锚A解除，`backend/app/services/chat/storage.py:70-73`、`backend/app/services/chat/message_service.py:155-156`）：不再取 `chat_messages.lastrowid`，改由 `chat_user_message` AUTOINCREMENT 分配
- 表仍由 `backend/app/db/db_initializer.py:90` 在启动时 `CREATE TABLE IF NOT EXISTS` 重建

---

## 二、终止 / 移除的风险与问题（准确说明）

### 2.1 依赖关系现状

| 维度 | 现状 | 删表是否受影响 |
|------|------|------|
| 读依赖 | 已全部迁移到 `chat_user_message`/`chat_task_steps`/`chat_tasks`/`chat_sessions`/`token_usage`/`chat_session_trust` | ❌ 不受影响 |
| 外键依赖 | `chat_task_steps` 的 FK 已解除 | ❌ 无级联破坏 |
| id 分配依赖 | 已迁移到 `chat_user_message` AUTOINCREMENT | ❌ 不受影响 |
| 写依赖 | 仍剩 W1–W7 共 7 处 INSERT/UPDATE 镜像写 + 启动清扫 W7 | ✅ **直接受影响→崩溃** |
| 表重建 | `db_initializer.py:90` 每次启动 `CREATE TABLE IF NOT EXISTS` | ⚠️ **即使手动 DROP，下次启动表又被重建并继续写入**（删表无意义，必须同时改代码） |

### 2.2 全部写点清单（W1–W7）

| 写点 | 位置 | SQL | 当前 fail-safe | 删表后后果 |
|------|------|-----|------|------|
| W1-user | `message_service.py:171` | INSERT 用户镜像 | ✅ try/except 仅告警 | 安全 |
| W1-assistant | `message_service.py:180` | INSERT legacy 助手直存 | ❌ 未包裹→500 | legacy 路径失败 |
| W2 | `storage.py:252` | INSERT assistant | ❌ 上层 except→500 | 步骤保存失败 |
| W3 | `storage.py:356` | INSERT assistant 空白行 | ✅ try/except 仅告警 | 安全 |
| W4 | `storage.py:279` | UPDATE content/status | ❌ 上层 except→500 | 步骤更新失败 |
| W5 | `storage.py:438` | UPDATE content/status/thought | ✅ agent_runner retry+except 仅记 error | 安全（终态不落镜像） |
| W6 | `stream_orchestrator.py:343` | UPDATE task_id | ❌ 在 `_setup_task_db` 内未单独包裹 | **任务创建失败** |
| W7 | `db_initializer.py:330` | UPDATE 启动清扫崩溃残留 | ❌ 初始化事务内 | **启动崩溃** |

> 迁移脚本 `migrate_steps.py:188/290/310/314/326` 及 `v2_chat_restructure.sql` 仍 SELECT/UPDATE `chat_messages`，均为**一次性数据迁移**，非运行时路径。

### 2.3 风险等级结论

| 操作 | 风险 | 说明 |
|------|------|------|
| 直接 `DROP TABLE chat_messages` | 🔴 致命 | W7 在初始化事务内执行 → 启动崩溃；W6 在任务创建热路径 → 新任务全失败 |
| 只停写不删表 | 🟢 安全 | 表空着无读者，无功能影响（过渡态） |
| **代码移除写点 + 停建表 + 删表** | 🟢 安全 | 系统对该表零依赖，删后无副作用 |

**核心风险只有两点**：① 启动崩溃（W7）；② 新任务无法创建（W6）。二者均为"镜像写无读者"代码，移除即用。

---

## 三、fail-safe 包裹 概念说明（过渡安全垫）

**fail-safe（故障安全）** = 把每一处对 `chat_messages` 的写 SQL 用 `try/except` 包起来，**捕获所有异常（特别是表不存在时的 `OperationalError`），只打一条警告日志，不抛出、不中断主流程**。

**"不动表结构"** = 不改 `CREATE TABLE`/`DROP`/`_ensure_column` 等任何 DDL：表继续存在、继续被建，只动写 SQL 的包裹方式。

**作用**：测试删表前的安全垫。先把代码对"表不存在"免疫，再手动 DROP 做实验，系统不崩溃；观察无问题再走正式移除。此步做完**表仍存在**（没动建表），是可逆安全过渡态。

---

## 四、严密实施步骤（精确到文件 / 行 / 代码块）

> 纪律：每改完一处立即跑启动验证（阶段1）或 pytest（阶段2-3），一处绿了再动下一处。严禁 PowerShell 脚本批量改代码。

### 阶段 0：基线备份与记录

**步骤 0.1** 备份数据库（Windows 命令）
```
copy %USERPROFILE%\.omniagent\chat_history.db chat_history.db.bak_20260827
```

**步骤 0.2** 记录当前行数（SQLite 客户端或后端日志）
```sql
SELECT COUNT(*) FROM chat_messages;          -- 记 baseline 行数
SELECT COUNT(*) FROM chat_user_message;      -- 对照权威表
SELECT COUNT(*) FROM chat_task_steps;
```

**步骤 0.3** 确认测试环境
- 后端可启动：`uvicorn app.main:app --reload`（端口 8000）
- pytest 可跑：`pytest -x --tb=short`
- E2E 环境可用（真实 LLM + 真实 SQLite）

---

### 阶段 1：fail-safe 包裹（5 处，不动表结构）

> 目标：让代码对"表不存在"免疫。改完任一处即重启后端确认 `/health` 返回 200、日志无 OperationalError。

#### 步骤 1.1 — W1-assistant（`backend/app/services/chat/message_service.py:180`）

**当前代码**（行 180-184）：
```python
            cursor.execute(
                "INSERT INTO chat_messages(session_id, role, content, timestamp, display_name, client_os, browser, device, network) VALUES(?,?,?,?,?,?,?,?,?)",
                (session_id, message.role, message.content, local_time, display_name_to_save,
                 message.client_os, message.browser, message.device, message.network))
            message_id = cursor.lastrowid
```

**改为**（包 try/except，失败降级不抛）：
```python
            try:
                cursor.execute(
                    "INSERT INTO chat_messages(session_id, role, content, timestamp, display_name, client_os, browser, device, network) VALUES(?,?,?,?,?,?,?,?,?)",
                    (session_id, message.role, message.content, local_time, display_name_to_save,
                     message.client_os, message.browser, message.device, message.network))
                message_id = cursor.lastrowid
            except Exception as _mir_e:
                logger.warning(f"[save_message] 镜像写chat_messages失败(session={session_id}): {_mir_e}")
                message_id = None
```

**验证**：legacy 助手直存路径触发时，表不存在仅告警，接口不 500。

#### 步骤 1.2 — W2（`backend/app/services/chat/storage.py:251` 的 `insert_assistant_message`）

**当前代码**（行 251-256）：
```python
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name, user_message_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ai_message_id, session_id, "assistant", initial_content, local_time, display_name, reply_to),
    )
```

**改为**（函数体内整体包 try/except）：
```python
    try:
        cursor.execute(
            """INSERT INTO chat_messages
               (id, session_id, role, content, timestamp, display_name, user_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ai_message_id, session_id, "assistant", initial_content, local_time, display_name, reply_to),
        )
    except Exception as _mir_e:
        logger.warning(f"[insert_assistant_message] 镜像写chat_messages失败(id={ai_message_id}): {_mir_e}")
```

**验证**：`save_execution_steps` 调用路径不再抛 500（失败仅告警）。

#### 步骤 1.3 — W4（`backend/app/services/chat/storage.py:278` 的 `update_message_fields`）

**当前代码**（行 278-281）：
```python
        cursor.execute(
            f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
            values,
        )
```

**改为**：
```python
        try:
            cursor.execute(
                f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
                values,
            )
        except Exception as _mir_e:
            logger.warning(f"[update_message_fields] 镜像写chat_messages失败(id={values[-1]}): {_mir_e}")
```

**验证**：步骤 content/status 更新路径不再抛 500。

#### 步骤 1.4 — W6（`backend/app/services/chat/stream_orchestrator.py:342` 的 `_setup_task_db` 内）

**当前代码**（行 342-345）：
```python
                    conn.execute(
                        "UPDATE chat_messages SET task_id=? WHERE id=?",
                        (task_id, _user_msg_id),
                    )
```

**改为**：
```python
                    try:
                        conn.execute(
                            "UPDATE chat_messages SET task_id=? WHERE id=?",
                            (task_id, _user_msg_id),
                        )
                    except Exception as _mir_e:
                        logger.warning(f"[setup_task] 镜像写chat_messages失败(task={task_id}): {_mir_e}")
```

**验证**：新任务创建事务不再因镜像写失败而整体失败（任务照常创建）。

#### 步骤 1.5 — W7（`backend/app/db/db_initializer.py:330` 启动清扫）

**当前代码**（行 330-333）：
```python
        conn.execute(
            "UPDATE chat_messages SET status='failed', "
            "content=CASE WHEN content='' THEN '(任务中断，未产生输出)' ELSE content END "
            "WHERE role='assistant' AND status IS NULL")
```

**改为**：
```python
        try:
            conn.execute(
                "UPDATE chat_messages SET status='failed', "
                "content=CASE WHEN content='' THEN '(任务中断，未产生输出)' ELSE content END "
                "WHERE role='assistant' AND status IS NULL")
        except Exception as _mir_e:
            logger.warning(f"[init] 启动清扫chat_messages失败(表可能已移除): {_mir_e}")
```

**验证**：**后端可正常启动**（`/health` 200），日志仅 warning 不崩溃。

> ✅ 阶段 1 完成判据：手动 `DROP TABLE chat_messages;` 后重启后端，启动成功、新任务可创建、各接口不 500。此时表处于"被删但代码免疫"的可观测状态。

---

### 阶段 2：移除全部镜像写代码（按既有 TODO 注释逐点删除）

> 每删一处，删其整段 INSERT/UPDATE 及上方 `TODO 删除` 注释块；保留周围主流程代码（如 `message_count` UPDATE、`allocate` 返回值）。

#### 步骤 2.1 — W1（`message_service.py`）
- 删除行 168-176（W1-user 整段 `try/except` INSERT）
- 删除行 178-184（W1-assistant 整段 INSERT）
- 保留行 154-167（权威源 `insert_user_message`）与行 186+（`message_count` UPDATE）

#### 步骤 2.2 — W2/W3/W4/W5（`storage.py`）
- 删除 `insert_assistant_message` 函数体（行 240-257）中 INSERT（或整函数，若仅此一处用途）
- 删除 `allocate_and_insert_message` 内 W3 的 `try/except` INSERT 块（行 355-362），保留下方 `UPDATE chat_sessions message_count` (行 363-366)
- 删除 `update_message_fields` 内 W4 的 `cursor.execute`（行 278-281），保留函数签名与 fields 组装（或整函数，若无其他调用）
- 删除 `finalize_message` 内 W5 的 `conn.execute`（行 438-441）

#### 步骤 2.3 — W6（`stream_orchestrator.py`）
- 删除行 340-345（W6 `try/except` UPDATE 块及上方 `TODO 删除` 注释）

#### 步骤 2.4 — W7（`db_initializer.py`）
- 删除行 328-333（W7 注释块 + `conn.execute` UPDATE）

#### 步骤 2.5 — 清理失效 import / 变量
- 删除因移除产生的未使用 import、未使用变量（如 `reply_to`、`_mir_e` 若成孤儿），跑 `pytest` + 类型检查确认无冗余。

---

### 阶段 3：停止建表 + 删表

#### 步骤 3.1 — 删除建表 DDL（`db_initializer.py`）
- 删除行 86-97（`chat_messages` 表注释块 + `CREATE TABLE IF NOT EXISTS chat_messages (...)`）
- 删除行 280（`CREATE INDEX idx_messages_session`）
- 删除行 291（`CREATE INDEX idx_msg_task`）
- 删除行 292（`CREATE INDEX idx_msg_timestamp`）
- 删除行 183-196 内所有 `_ensure_column(conn, "chat_messages", ...)` 调用

#### 步骤 3.2 — 执行删表（SQLite 客户端或一次性迁移脚本）
```sql
DROP TABLE IF EXISTS chat_messages;
```
> 注：阶段 3.1 已停止建表，重启后端不会再重建，故删表一次即永久移除。

#### 步骤 3.3 — 确认 `migrate_steps.py` 不并入日常
- 确认 `migrate_steps.py` 为独立迁移工具，仅手动按需运行，不挂启动链路。

---

### 阶段 4：回归测试验证（逐条过，全绿才算通过）

| 编号 | 验证项 | 方法 | 通过标准 |
|------|------|------|------|
| V1 | 启动 | 重启后端，`GET /api/v1/health` | 返回 200，日志无 OperationalError / 无 chat_messages 引用异常 |
| V2 | 新任务 | E2E 新建会话→发起真实任务→终态 | 任务创建成功，无 500，无告警 |
| V3 | 历史回放 | 前端打开既有历史会话 | 消息/步骤来自 `chat_user_message`+`chat_task_steps`，内容正确 |
| V4 | 多轮上下文 | 同一会话续聊（带上下文） | `_load_previous_messages` 正确重建"用户+AI"有序对 |
| V5 | 终态落库 | 查 `chat_tasks`/`chat_task_steps` | status/content/usage/artifacts 正确 |
| V6 | 存量库兼容 | 用含旧 `chat_messages` 的库启动 | 不读不崩，旧数据静置无碍 |
| V7 | 单元/集成 | `pytest` 存储层相关用例 | 全绿 |
| V8 | 代码整洁 | `grep -rn "chat_messages" backend/app` | 运行状态仅剩注释/历史说明，无实际 SQL 引用 |

> E2E 严禁 Mock，必须真实后端 + 真实 LLM + 真实 SQLite（`~/.omniagent/chat_history.db`）。

---

### 阶段 5：回滚预案

| 场景 | 回滚动作 |
|------|------|
| 阶段 1 后发现问题 | 代码 git revert 阶段 1 改动；表仍在，重启即恢复 |
| 阶段 2-3 后发现问题 | git revert 全部改动；`chat_history.db.bak_20260827` 还原（含 chat_messages）；重启即恢复 |
| 数据级回滚 | `copy chat_history.db.bak_20260827 %USERPROFILE%\.omniagent\chat_history.db` |

> 因阶段 1 已 fail-safe，过渡期任何时刻删表都不会崩溃，回滚窗口宽松。

---

## 五、执行纪律

1. **一次一处**：每改一个写点即跑一次启动 / pytest 验证，绿了再动下一处（铁律）
2. **禁 PowerShell 改码**：严禁用 PowerShell 脚本批量替换代码（防编码损坏），逐文件手工 edit
3. **分提交**：阶段 1（fail-safe）与阶段 2-3（真正移除）分两次 commit，互不阻塞
4. **提交格式**：`refactor:chat_messages镜像写点W1-W7改fail-safe - 小欧-2026-08-27` / `refactor:移除chat_messages镜像写点W1-W7及建表 - 小欧-2026-08-27`
5. **打 tag**：全部通过后 `git tag v0.19.33`（或下一序号），version.txt 头部插入变更汇总
6. **不动表结构原则**：阶段 1 严格只加 try/except，不碰任何 DDL

---

**编写人**: 小欧
**编写时间**: 2026-08-27 15:33:47
**签名**: 小欧
