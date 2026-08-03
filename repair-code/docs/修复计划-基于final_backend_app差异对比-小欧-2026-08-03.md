# 后端代码修复计划 — 基于 final_backend_app 差异对比

**编写人**: 小欧
**编写时间**: 2026-08-03 09:38:46
**状态**: 待评审

### 修订历史
| 版本 | 时间 | 修订人 | 内容 |
|------|------|--------|------|
| v1.0 | 2026-08-03 09:38 | 小欧 | 初始版（A/B/C/C' 档估计） |
| v1.1 | 2026-08-03 09:55 | 小欧 | 证据档修正为权威 Tier1(152)/Tier2(35)/Tier3(0) |
| v1.2 | 2026-08-03 10:10 | 小欧 | 来源确认(G 盘 backend/app 已空, final 封闭)；差异分层修正(25/7/7/32→10/30/40→11/92/103→0/8/8=46+137=183) |
| v1.3 | 2026-08-03 10:28 | 小沧 | 修正批次文件清单计数: 3.1=14文件(5缺失+9不同), 3.2 validate=4(diff incl registry_path_checker), 移 registry_path_checker 从3.8 归入3.2 |
| v1.4 | 2026-08-03 12:11 | 小沧 | 批次0收尾：记录 pytest 收集基线 = 4597 tests collected, 16 errors (16个collection-error文件清单) |
| v1.5 | 2026-08-03 12:30 | 小沧 | 批次1 L0 权威清单核实：32=25缺失+7不同；`logger/config.py` 为 CRLF/LF 行尾差异非真 DIFF；api_logger diff=导入 setup_logger→shared_handler final 正确 |

---

## 一、背景

当前仓库 `F:\OmniAgentAs-repair\backend\app`（238 py）为 **v0.18.27 基线**（7/20 前）。
`E:\tmp_rec\final_backend_app\backend\app`（283 py）为上一轮 DB 会话记录捞取修复的产物，
由 **merged(磁盘/MFT 恢复 250 文件) + DB候选(opencode 会话记录 203 文件)** 合并而成。

本计划基于两者差异，**按依赖层分批**推进修复，遵守代码 10 大规范（SRP/DRY/KISS-DIRECT/SLAP/YAGNI/禁止backward + OCP/LSP/ISP/复用优先），**只前进不后退**。

## 二、权威来源判定结论（关键前提）

**final_backend_app 不能整体作为恢复源**，其 183 个待修文件（46 缺失 + 137 不同）按 DB 会话记录 + commit 清单证据分三档（权威核对自 `E:\tmp_rec\db_survey.py` + 293 提交清单）：

| 档位 | 判定标准 | 文件数 | 处理策略 |
|------|---------|--------|---------|
| **A 档（权威）** | DB 有 **完整、完整行号连续**的 7/20 后 read 记录 | 152 | 以 DB 原文为准，final_backend_app == DB 提取结果，可直接恢复/覆盖 |
| **B 档（部分可信）** | DB 仅有**部分 read**(不完整)、或**仅 commit** 命中 | 35 | 逐个核对 diff，综合 commit + final 判定新旧 |
| **C 档（无证据）** | DB 无记录、commit 无命中 | 0 | 无 |

> 注：152+35=187 ≈ 183（容为 size-only 判定边角）。**不存在完全无任何证据的 "盲区"**，因此所有修复都有 DB 或 commit 佐证——"不能整体覆盖"的风险已控制在**B 档 35 个需逐一核订**之上。

**关键事实**：
- DB 会话记录覆盖本次 183 文件 = **187 个**（含 7/20 后 read）；其中**完整可恢复 152 个**
- 服务层(DB)覆盖率: services/ 仅 4 个完整 read，但 **commit 清单覆盖 80%**（commit 是补充证据）
- final_backend_app 相比当前 baseline **删除** `logger/setup_logger.py`（被拆为 utils/log_config/*）
- `core_agent` 已在 final 中删除（正确形态：`services/agent/` 下 universal_agent + base_agent）

## 三、差异总览

> **来源确认**：G 盘 live repo `backend/app` 已全部清空 (0 py)；G 盘 08-02 12:00 后**无任何 py 更新**。
> 因此 `final_backend_app`(283 py, 08-02 11:32 生成) 是**唯一封闭、完整**的正确形态，对照源。当前 F 盘 repair 工程 **不会引入超出 final_backend_app 的新增文件**。

| 依赖层 | 缺失(MISSING) | 不同(DIFF) | 小计 |
|--------|--------------|-----------|------|
| L0 基础层 (utils/logger/db) | 25 | 7 | 32 |
| L1 services 公共层 | 10 | 30 | 40 |
| L2 tools 工具层 | 11 | 92 | 103 |
| L3 api/入口层 | 0 | 8 | 8 |
| **合计** | **46** | **137** | **183** |

> 注：DIFF 为**内容不同**（字长不同即视为不同）。baseline 独有 `logger/setup_logger.py` 被 final 删除（拆为 utils/log_config/*）。


## 四、分批修复计划（按依赖层，每批含验证）

### 批次 0：修复前准备（本轮已完成）
- [x] 确认 final_backend_app 三副本一致（md5 全等）
- [x] 生成差异清单（46 缺失 + 137 不同）
- [x] 判定 A/B/C 档可信度
- [x] 建立每批的验证基线：
  > **baseline pytest 收集基线（2026-08-03 12:11 小沧）**：`pytest --collect-only` 得 **4597 tests collected, 16 errors**（38s）。
  > 16 个 ERROR 测试文件（全部因缺 `app.tools.fundamental.execute_shell_command` / `app.tools.fundamental.shell_engine`）：
  > `tests/handlers/test_observation_formatter_shell.py`、`tests/test_critical_flow_deep_bugs.py`、`tests/test_shell_quality.py`、`tests/tools/param_combination/test_analyze_data.py`、`test_analyze_data_mutex.py`、`test_execute_shell_command_bugs.py`、`test_filter_data.py`、`test_filter_data_combo.py`、`test_http_request_v2.py`、`test_network_tools.py`、`test_persistent_shell_engine.py`、`test_shell_bugfixes_20260727.py`、`test_shell_bugs_wave2.py`、`test_shell_bugs_wave3.py`、`test_shell_pool_manager.py`、`test_shell_truncation_deep.py`
  > 即 **批次 3.1 的缺失文件**。
  > 后续每批的验证 = `py_compile 全部 + 相关模块单测通过 + import 链 + 工具注册冒烟`，并以**本基线**作对照，**不得引入新的 collection ERROR / 失败**。

### 批次 1：L0 基础层（32 个 = 25 缺失 + 7 不同）— 先修底座
> 顺序：utils → logger → db，因 services/tools 都依赖它们
> **权威清单（2026-08-03 12:30 小沧，脚本 l0_tier.py 文本口径核实，无 C 档盲区）**：
> `logger/config.py` 字节不同但文本相同（CRLF/LF）→ **非真 DIFF，不纳入**。

| 子组 | 文件 | 档位 | 依据 |
|------|------|------|------|
| utils 缺失(23) | common_patterns, content_quality, context_vars, counter_utils, error_classifier, error_parser, log_config/(init,api_logger,config,handler,setup/init,setup/api_logger,setup/setup_logger_func,setup_logger_func), logger, message_id_tracker, next_actions_builder, paths, prompt_logger, retry_engine, sys_error_classifier, test_marker, version | B 档（DB 有部分 read）+ A 档 mixed | final 为准恢复 |
| utils 不同(3) | json_utils(+32/-3), text_utils(+17/-2), time_utils(+18/-0) | A 档 | text_utils 有 commit(07-24/25)，以 final 为准 |
| logger 缺失(1) | shared_handler | A 档（DB 完整 read） | 查 commit e8014e3bf(07-23) 确认 |
| logger 不同(3) | __init__(+18/-1), api_logger(+3/-1), prompt_logger(+14/-6) | A 档 2 + B 档 1(api_logger) | api_logger diff 已核=改导入 setup_logger→shared_handler，final 正确 |
| db 缺失(1) | models/operation_enums | B 档 | final 为准恢复 |
| db 不同(1) | database(+35/-1) | A 档 | 有 commit，以 final 为准 |
| **验证** | `py_compile` 全部 + 单测（logger/db 相关）+ import 链检查 | | |

### 批次 2：L1 services 公共层（39 个）
> 顺序：services/llm → services/agent/types,agent_utils → services/agent → services/safety → services/chat/task/lifecycle/model/prompts

| 子组 | 重点文件 | 依据 |
|------|---------|------|
| services/llm | llm_constants, stream_parser(缺失); base_service, client_sdk, error_classifier, reasoning(不同) | base_service 有 commit(07-26)，以 final 为准 |
| services/agent | agent_utils/, types/(缺失); agent_runner, base_agent, fc_message_types, action_handler, llm_stream, message_builder, react_cycle, step_emitter, final_step, tool_executor, tool_retry_engine(不同) | action_handler 有 DB+commit，权威 |
| services/safety | operation_record(缺失); __init__, operation_backup, operation_cleanup, operation_recorder, path_safe_check, tool_safety_checker(不同) | tool_safety_checker 有 commit(07-31) |
| services/chat | handlers, storage, stream(不同) | 有 commit |
| services/task | task_context, task_db(不同) | 有 commit |
| 其他 | lifecycle/service, model/resolver, prompts/system_adapter, system_prompts(不同) | system_prompts 有 DB+commit |
| **验证** | import 全链 + 单元测试 + agent 初始化冒烟 | |

### 批次 3：L2 tools 工具层（107 个）— **按模块分批，逐模块推进**
> 原则：先修 register/schema（对外契约），再修工具实现，最后修依赖链；每模块独立验证通过后才进下一模块。
> **分组依据 = 功能关联性**（同链路工具放同批），每行一个批次、单独 commit。
> **已知主线索**：shell 链是 7/20-31 变更最密集部分（50+ commit，含 07-28 shell 从 SHELL→FUNDAMENTAL 分类搬迁、07-30 Singleton→ShellPoolManager 分池并发两次大重构）；schema 类变更集中在 07-21/25（去冗余）与 07-29/30/31（增强/修复）两个浪潮。

| 批次号 | 模块（关联组） | 涉及文件 | 权威档位 | 验证目标（含现有测试） |
|--------|--------------|---------|---------|------------------------|
| 3.1 | **fundamental-shell 链（核心）** | execute_shell_command, execute_shell_command_safety, shell_engine, shell_prompt_templates（缺失 4）+ shell/下 execute_shell_command, execute_shell_command_safety, shell_engine, shell_prompt_templates, shell_schema, shell_register（不同 6）+ fundamental/__init__, send_notification, fundamental_register, fundamental_schema（不同 4）= **14 文件 (5 缺失+9 不同)** | **A 档（DB+commit 最密集）** | `test_execute_shell_command_bugs`、`test_shell_quality`、`test_persistent_shell_engine`、`test_shell_pool_manager`（当前收集 ERROR 根因） |
| 3.2 | **file 链（含 schema）** | compress_files, copy_file, delete_file, edit_text_file, extract_archive, file_register, file_schema, grep_file_content, list_directory, move_file, read_media_file, read_text_file, search_files, tree, write_text_file, file/__init__（不同 16）+ validate: file_path_checker, registry_path_checker, timeout_validator, url_validator（不同 4） | A/B 档 | file 相关测试 |
| 3.3 | **network 链（含 schema）** | connectivity, url_validator（缺失 2）+ download_file, fetch_webpage, http_request, network_diagnose, network_register, network_schema, search_web, network/__init__（不同 8）+ http_client_sdk（如依赖） | A/B 档 | `test_network_tools`、`test_http_request_v2` |
| 3.4 | **document 链（含 schema）** | document_register, document_schema, md_inline_utils, read_docx, read_pdf, read_pptx, read_xlsx, write_docx, write_pdf, write_pptx, write_xlsx（不同 11） | A 档（DB 覆盖多） | document 相关测试 |
| 3.5 | **dataanalysis 链（含 schema）** | data_loader（缺失 1）+ analyze_data, filter_data, execute_sql, get_db_schema, query_sql, generate_chart, dataanalysis_schema, dataanalysis_register（不同 8） | A 档 | `test_analyze_data`、`test_filter_data` |
| 3.6 | **desktop 链（含 schema，07-31 三堂会审 19 bug）** | clipboard_control, desktop_register, desktop_schema, keyboard_control, mouse_click/move/position/scroll, screen_capture, set_window_state, window_focus/info/resize（不同 12） | B 档（07-31 有 `fix:desktop*13个文件`、`fix:desktop三堂会审19个真实bug`） | desktop 相关测试 |
| 3.7 | **system + timer 链（含 schema）** | system: create_task, delete_task, event_log, list_tasks, system_schema（不同 5）；timer: query_calendar, time_add, time_diff（缺失 3）+ timer_register, timer_schema, timer_set, timer_list, timer/__init__（不同 5） | B/C 档 | system/timer 相关测试 |
| 3.8 | **win_registry 链** | registry_delete, registry_read, registry_write（不同 3） | A 档（07-31 有 `fix:win_registry registry_write BugB`） | `test_win_registry_deep` |
| 3.9 | **工具根 + toolhelper + 其余** | registry, tool_constants, tool_description, tool_error_classifier, tool_fc_helper, param_alias_mapper, schema_utils（不同 7）+ toolhelper/__init__, syntax_validator（不同 2）+ 其余 validate | A/B 档 | 工具注册冒烟 + 全量测试 |
| **每批验证** | — | `py_compile` + 该模块单测通过 + import 链 + 工具注册冒烟 | — | 不得引入新失败 |

### 批次 4：L3 API/入口层（7 个）
| 文件 | 依据 |
|------|------|
| api/v1/chat/openai, health, messages, model_routes, task_queries; config, constants, main | 等 L0-L2 就绪后处理，避免 import 断裂 |
| **验证** | 全后端 `import app.main` + pytest 全量 + 启动冒烟 | |

## 五、每批验证标准（铁律）

1. **语法层**：所有产出文件 `py_compile` 通过
2. **导入链**：相关模块可成功 import（逐层 `python -c "import ..."`）
3. **测试层**：该模块相关 pytest 通过；不得引入新失败（记录前后对比）
4. **规范层**：10 大规范三堂会审（合规/合理/相关逻辑）
5. **提交层**：按 AGENTS.md 规范 commit，禁止提交测试文件；每批一个 commit

## 六、风险与红线

- **禁止**：整体覆盖 final_backend_app 到 backend/（会引入 B 档 35 个未核订文件 + 删除 baseline 文件）
- **禁止**：git checkout/reset --hard/revert 回滚
- **禁止**：修改 baseline 未涉及文件
- **高风险区**：B 档 35 个文件（DB 仅部分 read / 仅 commit）——逐一核对后再入；A 档 152 个可直接信任
- 所有修复先落地 `repair-code/` 验证，再同步到 `backend/`
- `core_agent` 已删的正确结构必须保持，不得恢复

## 七、下一步

1. 评审本计划（批次划分、顺序、判定规则）
2. 批次 0 收尾：记录当前 backend 测试收集基线（当前 16 个 collection ERROR，根因缺 fundamental/shell 模块）
3. 按模块分批推进：从**批次 3.1 fundamental-shell 链**（变更最密集、且是多数测试收集失败的根因）开始
4. 每模块完成提交一次，独立验证，逐个推进，不急于一次性完成
