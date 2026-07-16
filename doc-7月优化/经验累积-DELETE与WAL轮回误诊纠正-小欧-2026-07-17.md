# 经验累积：chat库 journal_mode DELETE↔WAL 轮回与误诊纠正

- **版本**：v1.0
- **编写时间**：2026-07-17 05:20:35
- **编写人**：小欧
- **主题**：同一配置（chat 库 journal_mode）因误诊改 DELETE、白做未回退、终在 DB 膨胀后暴露隐患，最终纠正回 WAL 的完整轮回；作为经验累积存档，禁止丢失历史因果。

---

## 一、事件时间线（实锤，附证据）

| 时间 | 事件 | 证据 |
|------|------|------|
| 2026-07-14（前） | chat_history.db 已膨胀至 **2.4GB** | 设计说明书实测记录 |
| 2026-07-14 | case05 遇 `Errno 22`，初诊为「SQLite WAL 模式 `-shm` 共享内存在 Windows 2GB+ 库并发读写下 `GetFileInformationByHandleEx` 不稳定」 | `后端step单步保存设计说明书-小欧_2026-07-14.md` 第一/三章 |
| 2026-07-14 | commit `f27cfd5b4`「chat库journal_mode改DELETE+新增chat_message_steps表及索引」将 chat 库改 DELETE（"方法二机制根治"） | git log 实锤 |
| 2026-07-14 21:10 | 设计说明书 v1.2 **自我更正**：Errno22 真实根因为 `time_utils.ensure_timestamp_milliseconds` 潜伏 bug（Python3.13 宽松 `fromisoformat` + 漏捕 OSError），**与 WAL 无关**；DELETE 改动属「误诊白做但无害」，当时未回退 | 同说明书第十章 v1.2 |
| 2026-07-17 | E2E 全量验证 P5-06 首次失败，`create_session` 10s 超时。实锤 chat_history.db **2.7GB**（`chat_message_steps` 表 **185 万行**）；DELETE 模式写 I/O 拥塞为主因（非 DB 锁竞争） | E2E 验证问题C 根因分析报告 |
| 2026-07-17 | 将 chat 库改回 **WAL**，三库统一；代码注释+编辑历史标注因果 | `app/db/database.py` 修改 |

---

## 二、当初为什么改 DELETE（误诊经过）

case05 的 `Errno 22` 调用链（当时判断）：
`agent_runner.finally` 一次性大写入（~1.4MB execution_steps JSON 进大库）→ 并发 `check_db`（e2e_helpers.py）发 `GET /messages` 读 → 当时判定 WAL 状态不稳 → `Errno 22`。

基于该判断，提出「方法二（机制根治）」：不改数据模型，仅改 PRAGMA，将 chat 库 `journal_mode` 由 WAL 降为 DELETE，消除 `-shm` 共享内存脆弱性（operations/task_tracker 小库保持 WAL）。即 commit `f27cfd5b4`。

---

## 三、为什么是误诊（文档已更正）

设计说明书 v1.2（2026-07-14 21:10）经实测 traceback 复核，明确：
- `Errno 22` 真实根因是 `time_utils.ensure_timestamp_milliseconds` 的潜伏 bug：Python 3.13 的 `fromisoformat` 变宽松，将 13 位 epoch 串误解析为约公元 1784 年的 datetime；`.timestamp()` 因年份早于 Windows `mktime` 下限(1970) 抛 **OSError 22**，未被 except 捕获 → 500 错误。
- 文档自承：`journal_mode=DELETE` 改动与 `VACUUM` 运维步骤**针对误诊根因**，属白做但无害；`VACUUM` 后重跑 case04 仍报 `Errno 22`，直至 `time_utils` 修复才消失。

**结论**：DELETE 模式当初就是误诊产物，与真实故障无关。

---

## 四、DELETE 埋下的隐患（本次暴露）

DELETE 模式机制缺陷（实锤于问题C 分析）：
- 写操作获取**排斥锁（EXCLUSIVE）**，且每次写需写 `-journal` 文件 + fsync，I/O 开销远大于 WAL。
- E2E 长跑使 `chat_message_steps` 累积 **185 万行 / 2.7GB**（后台清理循环只清过期 task，不清 chat_history.db → 只增不减）。
- 在 DELETE 模式下，长跑 case（如 P5-05 45 分钟）结束瞬间**磁盘 I/O 拥塞**，`create_session` 的同步写（`INSERT chat_sessions`）物理 I/O 被拖慢至 >10s → 客户端 10s 超时。
- 重启后端清空运行时 I/O 状态 → 恢复。

**为何不是「DB 锁积累」**：单事件循环串行，无并发写竞争；全代码应用库写均 `get_conn` 短连接；仅 2 处直接 `sqlite3.connect` 连用户外部库（已排除）。故否定锁竞争，锁定 I/O 拥塞。

---

## 五、纠正：改回 WAL（2026-07-17）

- `app/db/database.py`：删除 chat 库 DELETE 分支，**三库统一 `PRAGMA journal_mode=WAL`**（`busy_timeout=30000` 保留）。
- 编辑历史 + 行内注释标注完整因果：07-14 误诊 → 白做未回退 → 07-17 隐患暴露 → 回归 WAL。
- 本经验文档存档。

---

## 六、经验与教训（核心，累积）

1. **误诊驱动的配置改动即使"无害"也必须记录真实根因**，否则埋雷。本次 DELETE 因"白做无害不回退"遗留，终在系统演化（DB 膨胀）后变真隐患。
2. **单次"白做无害"会在系统演化后变成真问题**：配置改动的影响随数据量/场景变化而反转，不能因当下无害就搁置。
3. **改配置（尤其 DB journal_mode）须留可追溯注释**：为什么改、真实根因、是否误诊、何时纠正。
4. **大库是独立隐患，不能靠 journal_mode 掩盖**：`chat_message_steps` 185 万行/2.7GB 需轮转/清理/归档，这是治本项（建议补充）。
5. **分析要实锤、不凭印象**：P5-06 初判"DB 锁积累"是推断，经代码行号 + 实测数据（2.7GB、185 万行、单事件循环无锁竞争）实锤否定，锁定 I/O 拥塞。猜的结论必须标注"推断"并补实验。

---

## 七、结论

chat 库已回归 WAL、三库统一；DELETE 系 07-14 误诊产物，其隐患（写 I/O 拥塞）已于 07-17 E2E 暴露并纠正。历史因果已标注于 `database.py` 代码注释 + 编辑历史，并存档于本文档，作为经验累积，不得丢失。

---

**编写人**：小欧　**编写时间**：2026-07-17 05:20:35
