# Operation 数据模型最佳设计方案

版本: v1.0
创建时间: 2026-07-16 17:25:34
编写人: 小欧

---

## 一、背景与问题

北京老陈在排查系统"双轨/多套 ID"问题时，发现 operation 体系存在结构性混乱：三张 operation 相关表并存、同一文件操作被双写、其中一张表是僵尸表。本方案在全面读代码（探索 agent 全链路核实 + 人工 grep 复核）基础上，按代码 10 大原则（SRP/DRY/KISS-DIRECT/SLAP/YAGNI/禁止backward/OCP/LSP/ISP/复用优先）做最佳设计，根治而非修修补补。

编写人确认：本方案经"重新梳理、复核 3 遍"后落笔。3 遍复核结论——表结构边界清晰、改名范围精确到 8 处 SQL、DB 连接名 `operations` 不动、测试不直接碰表名、迁移幂等、外键索引随 RENAME 自动跟随、报告/回滚死代码保留为能力（禁止退化）。

---

## 二、现状实锤（四表总览，均带 file:line）

| 表 | DB 连接 | 定义位置 | 写入方 | 读取方 | 状态 |
|---|---|---|---|---|---|
| `tasks` | task_tracker | db_initializer.py:158 | task_db.create_task（base_agent.py:74）| API GET /tasks、GET /tasks/{id} | ✅ 活（任务主表）|
| `operations` | task_tracker | db_initializer.py:175 | task_db.add_operation | API GET /tasks/{id}/operations | ✅ 活 → **改名 `task_operations`** |
| `file_operations` | operations | db_initializer.py:98 | operation_recorder.record_operation | 报告/回滚模块（**全死代码无调用方**）| ✅ 活写 / 死读（文件安全维度）|
| `task_operations` | operations | db_initializer.py:122 | **0 处 INSERT** | **0 处 SELECT** | ❌ **僵尸表 → 删** |

关键实锤（非凭印象）：
1. `task_operations` 全仓**无任何 INSERT、无任何 SELECT**；唯一引用是 operation_rollback.py:102 一处 UPDATE，而 `rollback_session` 本身无任何调用方 → 铁定僵尸。
2. 一次 `delete_file` 被双写：工具内 `record_operation` 写 `file_operations`(op-A)，action_handler.py:390 `agent.record_operation` 写 `operations`(op-B)，**A≠B**（各自 `f"op-{uuid4().hex}"`）。
3. `file_operations` 唯一读取方是 `app/services/visualization/*_report.py`，但该模块全死代码（无调用方、未被任何 API 暴露）；前端不消费 operation 数据 → 当前只写不读。
4. 回滚链路 `rollback_operation`/`rollback_session`/`mark_rolled_back` 均**无调用方**（全死代码）。
5. 唯一活着的 operation 消费是 `GET /api/v1/tasks/{task_id}/operations`（读 `operations` 表，task_tracker.db）。

---

## 三、10 大原则诊断

| 问题 | 违反原则 | 处理 |
|---|---|---|
| 僵尸表 `task_operations`（operations.db）| KISS-DIRECT / YAGNI / DRY / SRP | **删** |
| 活表名 `operations` 语义含糊（与 `file_operations`/`task_operations` 混）| KISS-DIRECT | **改名 `task_operations`**（正名）|
| operation_id 两处 `f"op-{uuid4().hex}"` | DRY | **抽公共函数 `generate_operation_id()`** |
| 双写两表 operation_id 不可关联 | SRP（实为"两个维度"未成立）| **贯通 op_id，使两表同号**（见 5.3）|
| 回滚链路对僵尸表的引用 | KISS / SRP | **删引用，保留能力** |
| `file_operations` 安全能力 | 禁止退化 | **保留** |

---

## 四、核心准则（北京老陈认可，2026-07-16）

- `task_operations`（task_tracker.db）= **任务步骤统一记录**（所有工具，活的，有 API `GET /tasks/{id}/operations`）
- `file_operations`（operations.db）= **文件操作安全维度**（backup_path / space_impact / file_hash / is_directory / rolled_back_at 等）
- 两表是**同一文件操作的两个维度，非冗余**
- `tasks`（task_tracker.db）= 任务主表，与 `task_operations` 是 1:N 主从关系（task_id 关联键）

---

## 五、最佳设计（完整）

### 5.1 命名治理（删僵尸 + 活表正名 + 迁移）

1. **删僵尸表**：`db_initializer.py:122-136` 整段 `CREATE TABLE task_operations (...)` 删除（该表在 operations.db，全仓 0 写入 0 读取）。
2. **活表正名**：`db_initializer.py:175` `CREATE TABLE IF NOT EXISTS operations (` → `CREATE TABLE IF NOT EXISTS task_operations (`（仍在 task_tracker.db）。
3. **task_db.py 表名引用改名（8 处）**：`:52`、`:81`、`:87`、`:88`、`:95`、`:130`、`:149`、`:200` 的 `operations` → `task_operations`（均为 task_tracker.db 的 SQL）。
4. **数据迁移（防残留、不退化）**：在 `init_task_tracker_db` 开头增加幂等迁移：
   ```python
   if conn.execute(
       "SELECT name FROM sqlite_master WHERE type='table' AND name='operations'"
   ).fetchone():
       conn.execute("ALTER TABLE operations RENAME TO task_operations")
   ```
   旧库（已有 `operations` 表）走 RENAME 保留历史；新库（无 `operations`）走 CREATE。外键 `task_id REFERENCES tasks`、索引 `idx_ops_task`/`idx_ops_seq` 随 RENAME 自动跟随，无需额外处理。

### 5.2 DRY 抽公共函数

- 新建 `backend/app/utils/id_utils.py`：
  ```python
  # -*- coding: utf-8 -*-
  """ID 生成公用函数 — 小欧 2026-07-16 抽自 task_db/operation_recorder 的 op-{hex} 生成（DRY）"""
  from uuid import uuid4


  def generate_operation_id() -> str:
      """生成统一格式 op-{hex}，全链路文件/任务操作 ID 同源 — 小欧 2026-07-16"""
      return f"op-{uuid4().hex}"
  ```
- `task_db.py:93`、`operation_recorder.py:51` 两处 `f"op-{uuid4().hex}"` 改调 `generate_operation_id()`。
- 登记进 `backend/FUNCTIONS.md`（复用优先原则要求）。

### 5.3 operation_id 贯通（两表同号，KISS 实现）

**裁决（基于 10 大原则，非凭印象）**：最佳方法 = **贯通 op_id**，使同一文件操作在 `task_operations` 与 `file_operations` 两表共享同一 operation_id。

- 理由：核心准则"两表是同一文件操作的两个维度，非冗余"——若两表 operation_id 不同，它们只是"碰巧同 task_id 的两条独立记录"，准则在数据模型上根本不成立（即北京老陈痛恨的双轨变种）。真正"两个维度" = 同一操作共享一个 operation_id 主键，可 `JOIN` 精确对应 → 符合 SRP（两维度共享主键）、KISS-DIRECT（数据直接表达"一操作两视角"）、SLAP。**不贯通是偷懒让准则落空（混蛋方法），违反设计自洽。**
- YAGNI 不违：贯通不是"加无用接口"，而是让已确认的"两个维度"准则内在成立，是设计自洽的必须，非额外负担。

**KISS 实现（零侵入调用链）**：经读代码确认，文件工具（如 delete_file.py:124）`record_operation()` 内部生成 op_id 并**返回**它（delete_file.py:143 `return {"operation_id": operation_id, ...}`），`execute_with_safety(operation_id, ...)` 用此 id 读写 file_operations；而 `action_handler.build_observation`（action_handler.py:390）在工具**返回后**写 task_operations，此时 result 已含文件工具的 operation_id。故：

1. `record_operation`（operation_recorder.py）与 `add_operation`（task_db.py）均增加**可选** `operation_id` 参数（不传则内部调 `generate_operation_id()`，保持其他潜在调用方兼容）。
2. `action_handler.build_observation`（action_handler.py:390 附近）改为统一：
   ```python
   op_id = (result.get("operation_id") if isinstance(result, dict) else None) or generate_operation_id()
   ctx.agent.record_operation(
       op_id, call.get("tool_name", "?"),
       status=OperationStatus.FAILED.value if _is_failed else OperationStatus.SUCCESS.value,
       error=str(result) if _is_failed else None,
   )
   ```
3. 文件类工具（delete/copy/move/edit_text/compress/write_text）**确保 result 返回 `operation_id`**（delete_file 已返回，其余核对补齐），供 action_handler 复用 → `file_operations.operation_id == task_operations.operation_id`，两表同号可精确关联。
4. 非文件工具 result 无 `operation_id` → 走 `generate_operation_id()` 自生成（正常，无 file_operations 对应）。

**此实现不改动** `execute_tool` / `ToolRetryEngine` / 工具函数签名，仅调整"取 id 的源头"，符合 KISS-DIRECT。

### 5.4 分层职责固化（写进本方案即设计契约）

- `task_operations`（task_tracker.db）：operation_id PK、task_id FK、intent、operation_type、status、source/dest_path、file_size、file_hash、sequence_number、details、error
- `file_operations`（operations.db）：operation_id UNIQUE、task_id、operation_type、status、source/dest_path、backup_path、backup_expires_at、file_size、file_hash、is_directory、file_extension、duration_ms、space_impact_bytes、metadata、error_message、rolled_back_at、sequence_number
- 关联：经 `operation_id` 精确关联（5.3 贯通后）+ `task_id` 聚合；operation_id 同源（公共函数）

### 5.5 回滚链路清理（保留能力）

- **operation_rollback.py:102** `UPDATE task_operations SET rolled_back_count=? WHERE task_id=?` 删除——该句连 `operations.db`（operation_rollback.py:82 `get_conn("operations")`），改名的 `task_operations` 在 task_tracker.db（无 `rolled_back_count` 字段），且 operations.db 的僵尸 `task_operations` 已被删 → 此句必报错。
- 任务回滚统计已由 `task_db.mark_rolled_back`（task_db.py:147-151 更新 `tasks` 表 `rolled_back_count`）负责；`rollback_operation`/`rollback_session` 保留为产品能力（虽当前无调用方，删除=功能退化，违反铁规）。

### 5.6 报告模块处理

- `app/services/visualization/*_report.py` 是 `file_operations` 唯一读取方，但全死代码（无调用方、未暴露 API）→ **保留**（产品能力），不删（禁止退化）。标记为潜在清理项：若未来确认不接线，应整体删除避免废弃代码累积。

---

## 六、不做的（边界，防越界 / 退化）

- ❌ 不删 `file_operations` 安全能力（禁止退化）
- ❌ 不删报告模块（保留能力，标潜在清理项）
- ❌ 不强行复活回滚 API 入口（本次仅清僵尸表引用）
- ❌ 不改 `GET /tasks/{id}/operations` 现有字段/行为（禁止 backward）
- ❌ 不动 DB 连接名 `operations`（operations.db 及其内 file_operations/timers 表不受影响；10+ 处 `get_conn("operations")` 全部有效）

---

## 七、实施文件清单（精确 file:line）

| 文件 | 改动 |
|---|---|
| `backend/app/db/db_initializer.py` | 删 :122-136 僵尸表定义；:175 `operations`→`task_operations`；`init_task_tracker_db` 开头加 RENAME 迁移 |
| `backend/app/services/task/task_db.py` | 8 处表名 `operations`→`task_operations`（:52/:81/:87/:88/:95/:130/:149/:200）；:93 改调 `generate_operation_id`；`add_operation` 增可选 `operation_id` 参数 |
| `backend/app/services/safety/operation_recorder.py` | :51 改调 `generate_operation_id`；`record_operation` 增可选 `operation_id` 参数 |
| `backend/app/services/safety/operation_rollback.py` | 删 :102 僵尸 `task_operations` UPDATE |
| `backend/app/services/agent/handlers/action_handler.py` | :390 附近 `build_observation` 改 `op_id = result.get("operation_id") or generate_operation_id()`，传入 `agent.record_operation` |
| `backend/app/tools/file/{delete,copy,move,edit_text,compress,write_text}_file.py` | 确保 result 返回 `operation_id`（delete_file 已返回，其余核对补齐）|
| `backend/app/utils/id_utils.py` | 新建 `generate_operation_id()` |
| `backend/FUNCTIONS.md` | 登记 `generate_operation_id` |

---

## 八、验证方案

1. 单元测试：`pytest backend/tests`（重点回归 task_db / operation_recorder / action_handler / 文件工具）
2. E2E 选 `P6-03`（network_fail）/ `P6-04`（sql_error）验证文件操作双表写入、`GET /tasks/{id}/operations` API 行为不变
3. 迁移验证：用已有 `~/.omniagent/task_tracker.db`（含旧 `operations` 表）启动，确认 RENAME 后 `task_operations` 可读、旧历史不丢
4. 贯通验证：执行一次文件删除，查 `file_operations` 与 `task_operations` 两表 `operation_id` 一致

---

## 九、迁移与兼容性（禁止 backward）

- 仅 schema 内部改名 + 删僵尸表，**不改变任何对外 API 字段/行为**（禁止 backward）。
- 迁移为幂等（RENAME 判断存在、CREATE IF NOT EXISTS 兜底），老库新库均安全。
- 删除僵尸表 `task_operations`（operations.db）属清理废弃结构，不影响任何活功能（其唯一 UPDATE 来自无调用方死代码）。

---

## 十、风险与缓解

| 风险 | 缓解 |
|---|---|
| 改名遗漏某处 `operations` 表名引用 | 已 grep 全仓确认仅 task_db.py 8 处 + operation_rollback.py:102；其余 `operations` 均为 DB 连接名，不动 |
| 测试直接引用旧表名导致挂 | 已 grep `tests/` 确认无任何 `SELECT/INSERT INTO operations` 或 `task_operations` 表名 SQL（多数命中是 `analyze_data(operations=[...])` 参数名），改名安全 |
| RENAME 破坏外键/索引 | SQLite RENAME 自动跟随外键与索引；task_tracker.db 内 operations→tasks 引用方向不变 |
| 文件工具未返回 operation_id 致贯通不全 | 实施时逐文件核对（delete_file 已返回，其余补齐），验证阶段查两表 id 一致 |

---

## 十一、B 功能激活设计（回滚 + 报告，从系统+人角度）

北京老陈指示：B 与 A 同做，功能须从"系统+人"双角度设计，可用、不奇怪、符合 10 大规范。以下为详细功能 / 逻辑 / 流程。

### 11.1 文件操作回滚功能

**人的角度（真实场景）**
- 用户让 Agent 删/改了一批文件，发现删错或改坏，想要"撤销本次对话产生的文件改动"
- 核心诉求：按任务一次性回滚本次任务产生的所有文件变更；且回滚前**必须确认**（破坏性操作，从"人"角度不能静默执行）

**系统角度（逻辑，复用既有能力）**
- 已有 `operation_rollback.rollback_session(task_id)`：遍历 `file_operations` 中该 task 且 status=SUCCESS 的文件操作，逐条 `rollback_operation(op_id)`（删→恢复备份、移→移回原位、建→删除）
- 已有 `rollback_operation(operation_id)`：单条回滚
- 缺失项仅为**触发入口 + 结果反馈 + 统计串联**

**API 设计（符合 10 大规范）**
- `POST /api/v1/tasks/{task_id}/rollback`
- 流程：
  1. 前置 HITL 确认：复用现有 `confirm_id` 机制（hitl_confirmation.py），因回滚破坏性，必须用户确认
  2. 确认通过后调 `rollback_session(task_id)` → 返回 `{total, success, failed, operations:[{operation_id, type, success, reason}]}`
  3. 回滚统计串联 `task_db.mark_rolled_back`（已在 task_db.py:118，更新 `tasks` 表 `rolled_back_count`/status）—— 消除"回滚统计无人管"死链
- 人因反馈：返回每条操作回滚结果（成功/失败+原因），前端可展示"已恢复 X 个文件，Y 个失败"

**10 大规范核查**
- SRP：API handler 编排、rollback_session 执行、mark_rolled_back 统计，各管一摊
- KISS-DIRECT：直接复用既有回滚逻辑，不重写
- YAGNI：先做"按任务全回滚"，不做花哨的选择性回滚 UI
- 安全：HITL 确认（复用现有 confirm 机制），禁止静默破坏性操作
- 禁止 backward：新增端点，不改既有端点

### 11.2 文件操作报告功能

**人的角度（真实场景）**
- 用户想看"这次任务 Agent 对我的文件做了什么"：删/建/改了哪些文件、占了多少空间、是否已回滚
- 诉求：清晰可读的列表 / 总结，而非花哨图形

**系统角度（复用既有能力）**
- 已有 `query_file_operations(task_id)`（operation_queries.py:80）结构化取数
- 已有 `text_report` / `html_report`（visualization）生成可读报告
- 缺失项仅为 **API 入口**

**API 设计（克制，从"人能用"角度，YAGNI）**
- `GET /api/v1/tasks/{task_id}/file-operations` → 结构化 JSON 列表（operation_type / source_path / destination_path / status / space_impact_bytes / backup_path / rolled_back_at），供前端列表
- `GET /api/v1/tasks/{task_id}/file-operations/report?format=text|html` → 可读报告（text_report / html_report）
- **YAGNI 克制**：不暴露 sankey / mermaid / animation / tree 等花哨可视化（属"奇奇怪怪"），仅结构化列表 + 文本 / HTML 两种人读格式

**流程**
1. 用户查看任务详情 → 点"文件操作"
2. 前端 `GET /tasks/{task_id}/file-operations`
3. 后端 `query_file_operations` → 结构化返回
4. 前端列表展示（类型 / 路径 / 状态 / 空间 / 是否已回滚）；可选"查看报告"→ text / html

**10 大规范核查**
- SRP：API 取数、visualization 生成，分离
- KISS-DIRECT：直接 query_file_operations，不过度包装
- YAGNI：不堆 6 种格式，只结构化 + text / html
- 复用优先：复用 query_file_operations / *_report 既有函数

### 11.3 落地范围（B 部分新增文件）
| 文件 | 改动 |
|---|---|
| backend/app/api/v1/task_queries.py | 加 `POST /tasks/{id}/rollback`（含 HITL 确认）、`GET /tasks/{id}/file-operations`、`GET /tasks/{id}/file-operations/report` |
| backend/app/services/safety/operation_rollback.py | rollback_session 回滚后串联 `task_db.mark_rolled_back` 更新 tasks 统计（消除死链）|
| frontend（不在本次后端范围）| 前端调用留前端专项，不在本次 |

---

## 版本历史

| 版本 | 时间 | 编写人 | 说明 |
|---|---|---|---|
| v1.0 | 2026-07-16 17:25:34 | 小欧 | 创建。Operation 数据模型最佳设计方案：命名治理（删僵尸 task_operations + 活表 operations→task_operations 正名 + 迁移）、DRY 抽 generate_operation_id、operation_id 贯通使两表同号（KISS 实现）、回滚僵尸引用清理、分层职责固化。基于 10 大原则裁决，经复核 3 遍。 |
| v1.1 | 2026-07-16 17:40:00 | 小欧 | 增补 B 功能激活设计（第十一章）：从系统+人角度设计文件操作回滚（POST /tasks/{id}/rollback，HITL 确认 + 复用 rollback_session + 串联 mark_rolled_back 统计）与文件操作报告（GET /tasks/{id}/file-operations 结构化列表 + report?format=text|html，YAGNI 克制不堆花哨格式），均附 10 大规范核查。A+B 同做。 |
