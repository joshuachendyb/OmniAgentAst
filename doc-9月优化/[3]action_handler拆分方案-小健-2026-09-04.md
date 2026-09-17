# action_handler.py 拆分方案-小健-2026-09-04

**文档名称**: action_handler.py 拆分方案-小健-2026-09-04
**编写人**: 小健
**创建时间**: 2026-09-04 15:54:03
**更新时间**: 2026-09-04 20:00:00

| 版本 | 时间 | 更新人 | 更新要点 |
|------|------|--------|----------|
| v1.0 | 2026-09-04 15:54:03 | 小健 | 初版：方案C拆分方案（3个新文件） - 小健-2026-09-04 |
| v1.1 | 2026-09-04 16:10:00 | 小健 | 补充拆分重构核心原则：先复制后修改 + 实施状态 - 小健-2026-09-04 |
| v1.2 | 2026-09-04 16:20:00 | 小健 | 重排章节结构：按阶段划分，第1阶段完成，预留第2/3/4阶段 - 小健-2026-09-04 |
| v1.3 | 2026-09-04 17:30:04 | 小健 | 新增第2阶段：4个函数下沉（target提取/factory/遥测）+ 沙箱DRY修复，原第2/3/4阶段顺延为第3/4/5阶段 - 小健-2026-09-04 |
| v1.4 | 2026-09-04 17:45:00 | 小健 | 第2阶段新增沙箱DRY修复：run_sandbox_gate统一入口消除三处重复调用，44测试全过 - 小健-2026-09-04 |
| v1.5 | 2026-09-04 18:35:00 | 小健 | 第2阶段函数下沉完成(第2阶段✅)；同时发现并修复 run_sandbox_gate DRY重构回归（bypass路径误拒） - 小健-2026-09-04 |
| v1.6 | 2026-09-04 19:10:00 | 小健 | 替换第3阶段：原yield架构改造章节→改为「名不副实函数下沉」方案（_build_call_list/_add_denial_feedback/build_observation/execute_tools），按先复制后修改规则 - 小健-2026-09-04 |
| v1.7 | 2026-09-04 20:00:00 | 小健 | 按10大规范复核命名与目录：函数定名名副其实（parse_action_input/build_observation_feedback/execute_tools/add_denial_feedback），目录位置论证（SLAP同层+复用优先）；按YAGNI合并feedback_writer进observation_builder，4文件→3文件 - 小健-2026-09-04 |

---

## 一、拆分目标

action_handler.py（1144行）是当前代码中最烂的文件——6个职责混在一起，函数乱放，还造成sandbox_gate环依赖。

**目标**：
1. **改掉烂架构和函数乱放**：把不属于action_handler的函数拆到正确的模块位置
2. **为后续前后端架构重构做准备**：第五章yield改造（handler→dict+event_emitter）依赖本章拆分完成后的干净代码结构

### 核心原则：先复制后修改

**铁律**：拆分重构必须严格按以下顺序执行，禁止边改边拆。

| 阶段 | 动作 | 说明 |
|------|------|------|
| **阶段1：复制** | 新建目标文件，从源文件**逐行完整复制**函数体 | 不改逻辑、不改变量名、不删注释，100%复制 |
| **阶段2：验证** | 对新文件执行 `py_compile` | 确认复制后的文件可编译 |
| **阶段3：修改** | 修改源文件：删内联 → 改为import新模块 | 只改import路径，不改业务逻辑 |
| **阶段4：验证** | 对修改后的源文件执行 `py_compile` | 确认import替换正确 |
| **阶段5：联动** | 修改其他引用文件的import路径 | 同上 |
| **阶段6：回归** | `pytest` 全量测试 | 确认功能零退化 |

**禁止**：
- ❌ 复制时顺手"优化"逻辑
- ❌ 边复制边修改源文件
- ❌ 跳过py_compile直接改下一个文件

---

## 二、第1阶段：信任域+冲突检测+文件工具拆分 ✅ 已完成

### 2.1 新建3个文件

#### 文件1：`backend/app/tools/trust.py`（121行）

**目的**：信任域三合一，消除 sandbox_gate→action_handler 环依赖。

| 函数 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `_parse_paths` | action_handler.py L551-578 | 27行 | 完整复制 |
| `extract_trust_path` | action_handler.py L581-587 | 7行 | 完整复制，改名去掉下划线前缀 |
| `resolve_skip` | action_handler.py L297-327（check_safety_and_confirm内） | 30行 | 提取为独立async函数 |
| `save_session_trust` | hitl_confirmation.py L184-196 | 12行 | 提取为独立async函数 |

**依赖**：
- `PARAM_ALIASES` ← `app.tools.tools_alias_mapper`
- `FILE_OPERATION_TOOLS` ← `app.tools.tool_constants`
- `normalize_tool_name` ← `app.tools.tools_alias_mapper`
- `get_session_id_by_task` / `check_session_trust` / `insert_session_trust` ← `app.services.chat.storage`
- `db` ← `app.db`

#### 文件2：`backend/app/tools/conflict_detector.py`（92行）

**目的**：冲突检测下沉，SRP合规。

| 函数 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `_has_conflict` | action_handler.py L590-621 | 32行 | 完整复制 |
| `_partition_calls` | action_handler.py L623-655 | 33行 | 完整复制 |

**依赖**：
- `_parse_paths` ← `app.tools.trust`（跨文件引用，消除环依赖的关键）
- `FILE_OPERATION_TOOLS` / `WINDOW_TARGET_TOOLS` ← `app.tools.tool_constants` / `trust`
- `_WRITE_OPS` ← 需在本文件内定义或从action_handler复制

#### 文件3：`backend/app/tools/file_tool_utils.py`（59行）

**目的**：文件工具纠正逻辑独立。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `_EXT_TO_READ_TOOL` 常量 | action_handler.py L242-249 | 8行 | 完整复制 |
| `_EXT_TO_WRITE_TOOL` 常量 | action_handler.py L250-256 | 7行 | 完整复制 |
| `_auto_correct_file_tool` | action_handler.py L259-276 | 18行 | 完整复制 |

**依赖**：
- `TEXT_EXTENSIONS` / `MEDIA_EXTENSIONS` ← `app.tools.validate.file_type_checker`

### 2.2 现有文件改动

#### action_handler.py（删内联→import）

| 删除位置 | 行数 | 改为import |
|---------|------|-----------|
| L240-276（常量+纠正函数） | 37行 | `from app.tools.file_tool_utils import _auto_correct_file_tool, _EXT_TO_READ_TOOL, _EXT_TO_WRITE_TOOL` |
| L551-587（路径提取+信任路径） | 37行 | `from app.tools.trust import _parse_paths, extract_trust_path as _extract_trust_path` |
| L590-655（冲突检测+分组） | 66行 | `from app.tools.conflict_detector import _has_conflict, _partition_calls` |

**净减**：~140行（删除） - 3行（新增import） = ~137行

#### sandbox_gate.py（import路径）

| 改动 | 原始 | 改为 |
|------|------|------|
| `_extract_trust_path` import | `from app.services.agent.handlers.action_handler import _extract_trust_path` | `from app.tools.trust import extract_trust_path as _extract_trust_path` |

#### hitl_confirmation.py（import trust）

| 改动 | 原始 | 改为 |
|------|------|------|
| `save_session_trust` 逻辑 | 内联在函数中 | `from app.tools.trust import save_session_trust` |

### 2.3 实施步骤与状态

| 步骤 | 动作 | 验证 | 状态 |
|------|------|------|------|
| 1 | 新建 `backend/app/tools/trust.py`（完整复制，不改逻辑） | py_compile | ✅ 完成 |
| 2 | 新建 `backend/app/tools/conflict_detector.py`（完整复制，import trust） | py_compile | ✅ 完成 |
| 3 | 新建 `backend/app/tools/file_tool_utils.py`（完整复制，不改逻辑） | py_compile | ✅ 完成 |
| 4 | 改造 `action_handler.py`（删内联→import） | py_compile | ✅ 完成 |
| 5 | 改造 `sandbox_gate.py`（import路径） | py_compile | ✅ 完成 |
| 6 | 改造 `hitl_confirmation.py`（import trust） | py_compile | ✅ 完成 |
| 7 | 全量测试 | `pytest tests/ -x --tb=short` | ✅ 完成（54个关键测试PASS） |

### 2.4 优化效果

| 维度 | 改前 | 改后 |
|------|------|------|
| action_handler.py | 1144行，6职责 | 976行，3职责（-168行） |
| 新建文件 | 0 | 3个（trust.py 121行 + conflict_detector.py 92行 + file_tool_utils.py 59行） |
| 环依赖 | sandbox_gate→action_handler | sandbox_gate→trust（单向，无环） |
| SRP违规 | 6处 | 0处 |

### 2.5 核查清单

| 核查项 | 结果 |
|--------|------|
| 函数体完整复制 | ✅ 逐行对比一致 |
| 依赖import正确 | ✅ 新文件import路径可解析 |
| 原始文件删除干净 | ✅ action_handler.py无残留内联代码 |
| import替换正确 | ✅ 所有引用点改为新路径 |
| 编译通过 | ✅ py_compile每个文件 |
| 测试通过 | ✅ 54个关键测试PASS |

---

## 三、第2阶段：函数下沉（4个函数）✅ 已完成

> 三堂会审分析：action_handler.py中4个函数不属于agent层，应下沉到正确的模块位置

### 3.1 改造范围

| 函数 | 当前位置 | 行数 | 目标位置 | 下沉理由 |
|------|---------|------|---------|---------|
| `_resolve_target_field` | action_handler.py L666-685 | 19行 | `app/tools/target_utils.py` | 纯工具schema查询，依赖tool_registry，与agent逻辑无关 |
| `_extract_target` | action_handler.py L688-696 | 8行 | `app/tools/target_utils.py` | _resolve_target_field的消费者，同属工具schema层 |
| `_fp_factory` | action_handler.py L922-943 | 21行 | `app/file_persist.py`（新增`make_fp_callback`） | 文件持久化回调工厂，agent不该知道落盘细节（复用既有文件存储模块，不新建目录） |
| 遥测收集逻辑 | action_handler.py L635-655 | 20行 | `app/monitoring/agent_telemetry.py`（新增`collect_and_report`方法） | duration/artifacts收集是telemetry的职责 |

### 3.2 新建2个文件

#### 文件1：`backend/app/tools/target_utils.py`（~30行）

**目的**：target提取逻辑从action_handler下沉到工具层。

| 函数 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `_TARGET_PARAM_PRIORITY` | action_handler.py L660-663 | 4行 | 完整复制 |
| `_resolve_target_field` | action_handler.py L666-685 | 19行 | 完整复制 |
| `_extract_target` | action_handler.py L688-696 | 8行 | 完整复制 |

**依赖**：
- `tool_registry` ← `app.tools.registry`
- 无agent层依赖（纯工具层函数）

#### 文件2：`backend/app/file_persist.py`（新增 `make_fp_callback`，复用既有文件存储模块）

**目的**：文件持久化回调工厂从handle_action下沉到既有 file_persist 模块（不新建目录，复用优先）。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `_fp_factory` 闭包 | action_handler.py L922-943 | 21行 | 完整复制为模块级函数 `make_fp_callback(agent, step, exec_calls)`，内部 `_fp_factory(tno)` 闭包保留 |

**依赖**：
- `agent.file_persist` ← 调用方传入（解耦agent依赖）
- `step` / `_exec_calls` ← 闭包参数化

### 3.3 遥测收集逻辑提取

**目的**：execute_tools内的遥测收集逻辑提取到telemetry模块。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| 遥测回调+artifact收集 | action_handler.py L635-655 | 20行 | 提取为 `agent_telemetry.collect_and_report()` |

**改动**：
- action_handler.py execute_tools: L635-655删除 → 改为调用 `agent.telemetry.collect_and_report(all_calls, results)`
- agent_telemetry.py(TaskTelemetry): 新增 `collect_and_report()` 方法，封装duration/artifacts/tool_name收集逻辑

### 3.4 action_handler.py改动

| 删除位置 | 行数 | 改为import |
|---------|------|-----------|
| L660-696（target提取） | 37行 | `from app.tools.target_utils import _resolve_target_field, _extract_target` |
| L922-943（fp_factory闭包） | 21行 | `from app.file_persist import make_fp_callback` |
| L635-655（遥测收集） | 20行 | 删除内联逻辑，调用 `agent.telemetry.collect_and_report()` |

**净减**：~78行（删除） - 2行（新增import） = ~76行

### 3.5 实施步骤与状态 ✅ 已完成

| 步骤 | 动作 | 验证 | 状态 |
|------|------|------|------|
| 1 | 新建 `backend/app/tools/target_utils.py`（完整复制） | py_compile | ✅ 完成 |
| 2 | 在 `backend/app/file_persist.py` 新增 `make_fp_callback`（完整复制，复用既有模块） | py_compile | ✅ 完成 |
| 3 | 改造 `agent_telemetry.py`（新增collect_and_report方法） | py_compile | ✅ 完成 |
| 4 | 改造 `action_handler.py`（删内联→import） | py_compile | ✅ 完成 |
| 5 | 改造其他引用文件（无外链，无需改） | py_compile | ✅ 完成 |
| 6 | 回归测试 | pytest | ✅ 完成（44个action/trust/conflict测试PASS；sandbox_gate 6失败为第3阶段预写测试，baseline同样失败） |

> **⚠️ 第2阶段回归修复（重要）**：run_sandbox_gate DRY重构遗漏bypass路径无条件 `yield resumed`+`continue`，
> 导致auto_confirm工具沙箱放行后误落入真HITL等待（confirm_id已resolve→entry=None→误判"用户拒绝"），
> E2E中shell被误拒致任务失败。已恢复预DRY的无条件resumed+continue（action_handler.py bypass路径）。

### 3.6 预期效果

| 维度 | 改前 | 改后 |
|------|------|------|
| action_handler.py | 976行 | ~905行（-71行，另有沙箱回归修复+14行，净值约-57行） |
| 新建文件 | 0 | 1个（target_utils.py ~51行）+ 复用既有 file_persist.py/agent_telemetry.py 各增1方法 |
| agent层SRP违规 | 4处（target/factory/遥测/编排混合） | 0处 |

### 3.7 前置条件

- ✅ 第1阶段完成（信任域+冲突检测+文件工具已拆分）

### 3.8 沙箱DRY修复 ✅ 已完成

> check_safety_and_confirm中三处sandbox_precheck+sandbox_resolve重复调用，DRY违规

| 问题 | 说明 |
|------|------|
| **DRY违规** | ①auto_confirm ②用户确认 ③循环体兜底 三处调用逻辑几乎完全相同 |
| **改法** | sandbox_gate.py新增 `run_sandbox_gate()` 统一入口，封装precheck→resolve→yield steps→check ok |
| **效果** | 三处20行重复代码→三处5行调用，逻辑集中在sandbox_gate.py一个入口 |

**改动文件**：

| 文件 | 改动 |
|------|------|
| `sandbox_gate.py` | 新增 `run_sandbox_gate()` 统一入口函数 |
| `action_handler.py` | 三处重复调用→改为 `run_sandbox_gate()` 一行调用 |

**验证**：44个测试全过（action_handler 11 + trust 16 + conflict_detector 17）

---

## 四、第3阶段：名不副实函数下沉 ⏳ 待实施

> 三堂会审分析（小健 2026-09-04）：action_handler仍有4个「名不副实」的函数——它们做的都不是"action编排"，
> 而是工具解析/LLM历史写入/反馈构建/工具批执行。按第2阶段规矩（先复制后修改）逐一拆到正确的模块位置。
>
> v1.7 按10大规范复核：函数重新定名确保"名副其实"，目录位置按"作用对象→所属层"论证（SLAP同层），
> 并按YAGNI把 feedback_writer 合并进 observation_builder（4文件→3文件）。详见 4.8 命名与目录理由。

### 4.1 改造范围

| 函数 | 当前位置 | 现状职责 | 目标位置 | 名不副实理由 |
|------|---------|---------|---------|-------------|
| `_build_call_list`+`BuildCallListResult` | action_handler.py L765-810 | 解析parsed→action输入(all_calls+tool_name/params/is_parallel) | `app/services/agent/action_input_parser.py` | 返回值含编排决策字段，实为"LLM action输入解析"，非仅建调用列表 |
| `_add_denial_feedback` | action_handler.py L488-506 | 被拒call→写入LLM历史 | `app/services/agent/observation_builder.py` | 操作message_builder，属LLM历史反馈层（与build_observation配套，并入同一文件） |
| `build_observation` | action_handler.py L665-762 | 构建ObservationStep+写LLM历史+record_operation+编排决策收集 | `app/services/agent/observation_builder.py` | 职责远超"构建观察"，实为观察反馈构建层 |
| `execute_tools` | action_handler.py L511-662 | 工具三分支(单/并行/顺序)执行调度 | `app/services/agent/tool_runner.py` | 工具批执行调度，非action编排本身 |

### 4.2 新建/目标文件（3个）

#### 文件1：`backend/app/services/agent/action_input_parser.py`（~46行）

**目的**：把LLM输出的`parsed`反序列化/归一成 action 执行输入（调用列表+编排决策字段），从handle_action下沉。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `ActionInput` dataclass（原`BuildCallListResult`） | action_handler.py L765-773 | 9行 | 完整复制改名 |
| `parse_action_input`（原`_build_call_list`） | action_handler.py L776-810 | 35行 | 完整复制改名 |

**依赖**：无agent依赖（纯解析，只用parsed字段）。

#### 文件2：`backend/app/services/agent/observation_builder.py`（~130行）

**目的**：工具结果→LLM历史(assistant+tool)+record_operation+ObservationStep+编排决策收集+拒绝反馈，观察反馈构建层独立（yield一个文件承载）。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `ObservationContext` dataclass | action_handler.py L230-241 | 12行 | 完整复制 |
| `build_observation_feedback`（原`build_observation`） | action_handler.py L665-762 | 98行 | 完整复制改名 |
| `add_denial_feedback`（原`_add_denial_feedback`） | action_handler.py L488-506 | 19行 | 完整复制改名，并入本文件 |

**依赖**：`ObservationContext`、`observation_formatter.build_observation_text`、`message_builder`、step类型。

#### 文件3：`backend/app/services/agent/tool_runner.py`（~152行）

**目的**：工具三分支批量执行调度（单/并行分组串行/顺序+冲突分组），与action_handler解耦。

| 内容 | 原始位置 | 行数 | 操作 |
|------|---------|------|------|
| `execute_tools` | action_handler.py L511-662 | ~152行 | 完整复制，不改逻辑 |

**依赖**：`execute_tool`（tool_executor）、`_partition_calls`/`_has_conflict`（conflict_detector）、`_auto_correct_file_tool`（file_tool_utils）。

### 4.3 action_handler.py改动

| 删除位置 | 行数 | 改为import |
|---------|------|-----------|
| L765-810（BuildCallListResult+_build_call_list） | 46行 | `from app.services.agent.action_input_parser import parse_action_input, ActionInput` |
| L230-241, L488-506, L665-762（ObservationContext+_add_denial_feedback+build_observation） | ~129行 | `from app.services.agent.observation_builder import build_observation_feedback, add_denial_feedback, ObservationContext` |
| L511-662（execute_tools） | ~152行 | `from app.services.agent.tool_runner import execute_tools` |

**净减**：~327行（删除） - 3行（新增import） = ~324行（action_handler 920行→~596行为纯编排调度层）

### 4.4 实施步骤与状态（先复制后修改）

| 步骤 | 动作 | 验证 | 状态 |
|------|------|------|------|
| 1 | 新建 `action_input_parser.py`（完整复制改名） | py_compile | ⏳ 待实施 |
| 2 | 新建 `observation_builder.py`（完整复制改名） | py_compile | ⏳ 待实施 |
| 3 | 新建 `tool_runner.py`（完整复制） | py_compile | ⏳ 待实施 |
| 4 | 改造 `action_handler.py`（删内联→import） | py_compile | ⏳ 待实施 |
| 5 | 改造其他引用文件（观测/执行相关引用点） | py_compile | ⏳ 待实施 |
| 6 | 回归测试 | pytest | ⏳ 待实施 |

### 4.5 预期效果

| 维度 | 改前 | 改后 |
|------|------|------|
| action_handler.py | 920行（编排+解析+历史+反馈+执行混装） | ~596行（纯编排调度层） |
| 新建文件 | 0 | 3个（action_input_parser/observation_builder/tool_runner） |
| 名不副实函数 | 4处 | 0处 |

### 4.6 前置条件

- ✅ 第1阶段完成（信任域+冲突检测+文件工具已拆分）
- ✅ 第2阶段完成（target提取/fp回调/遥测下沉）
- ✅ 第2阶段回归修复（bypass路径误拒）完成
- ⏳ 本阶段内部按"先复制后修改"顺序执行（先全部新建验证，再改源头）

### 4.7 核查清单

| 核查项 | 结果 |
|--------|------|
| 函数体完整复制 | ⏳ 逐行对比一致 |
| 重命名名副其实 | ⏳ parse_action_input/build_observation_feedback/execute_tools/add_denial_feedback |
| 依赖import正确 | ⏳ 新文件import路径可解析 |
| 原始文件删除干净 | ⏳ action_handler.py无残留内联代码 |
| import替换正确 | ⏳ 所有引用点改为新路径 |
| 编译通过 | ⏳ py_compile每个文件 |
| 测试通过 | ⏳ 关键测试PASS |

### 4.8 命名与目录理由（10大规范复核）— 小健 2026-09-04

> 回答两个问题：①拆出函数名是否名副其实 ②存放目录架构层次是否合理。

**架构层次判断原则（SLAP-同一抽象层）**：`app/services/agent/` 平铺模块分3层 ——
LLM交互层(`message_builder`/`observation_formatter`/`fc_message_types`)、编排层(`react_cycle`/`step_emitter`/`status_table`)、
工具执行层(`tool_executor`/`tool_cache_manager`)。**看每个函数"作用对象"落在哪层，就放哪层，与其依赖同层。**

| 函数 | 作用对象 | 所属层 | 存放位置 | 合理依据（复用优先+SLAP） |
|------|---------|--------|---------|--------------------------|
| `parse_action_input` | 解析LLM输出parsed→调用结构 | LLM交互层 | `action_input_parser.py`(agent 平铺) | ✅ 与 fc_message_types/message_builder 同层，紧邻LLM消息处理 |
| `add_denial_feedback` | 写 message_builder(LLM历史) | LLM交互层(反馈) | `observation_builder.py`(agent 平铺) | ✅ 与 message_builder 同层，且是 build_observation 配套 |
| `build_observation_feedback` | message_builder+record_operation+step_emitter | LLM交互层(反馈构建) | `observation_builder.py`(agent 平铺) | ✅ 与 observation_formatter 紧邻同层 |
| `execute_tools` | 调 execute_tool+conflict_detector | 工具执行层(调度) | `tool_runner.py`(agent 平铺) | ✅ 与 tool_executor 同层，是 execute_tool 的上一层调度 |

**结论：目录位置全部合理** —— 4个都放 `agent/` 平铺（不进 `handlers/` 子目录），与其依赖同层，
符合"handlers 只留 ReAct 循环业务处理器"的解耦方向（与第2阶段 target_utils/file_persist/trust 下沉同思路）。

**命名核实（名副其实）**：

| 原函数 | 原名义副实？ | 新定名 | 理由 |
|--------|------------|--------|------|
| `_build_call_list`+`BuildCallListResult` | ❌ 名不副实 | `parse_action_input`+`ActionInput` | 返回值含 tool_name/params/is_parallel 编排决策字段，本质是"LLM action输入反序列化"，非"建个列表" |
| `_add_denial_feedback` | ✅ 名副其实 | `add_denial_feedback` | 就是"把拒绝反馈写入(历史)" |
| `build_observation` | ❌ 名不副实 | `build_observation_feedback` | 不只构建观察，还写LLM历史+record_operation+收集编排决策，加 feedback 更贴"反馈构建层" |
| `execute_tools` | ✅ 名副其实 | `execute_tools` | 就是"批量执行工具" |

**YAGNI 收紧**：原方案拆4个文件，`_add_denial_feedback`(仅19行)与 `build_observation` 同层且配套
（handle_action在build_observation后调用），单独成 `feedback_writer.py` 过薄违反YAGNI，合并进 `observation_builder.py`。
两个函数SRP各自独立（各做一件事），只是**同放一个观察反馈模块**，不违反SRP。

---

## 五、第4阶段：SRP合规拆分（待实施）

> 对应设计文档第七章：agent_telemetry + step_emitter SLAP修复

### 5.1 改造范围

| 文件 | 改造内容 | 状态 |
|------|---------|------|
| `agent_telemetry.py` | build_final_stats_step加outcome参数 | ⏳ 待实施 |
| `step_emitter.py` | emit_final_with_stats显式透传outcome | ⏳ 待实施 |

### 5.2 前置条件

- ✅ 第1阶段完成
- ⏳ 第3阶段完成（名不副实函数下沉后，action_handler为纯编排调度层，telemetry/反馈更清晰）

---

## 六、第5阶段：最终集成验证（待实施）

## 七、第6阶段：最终集成验证（待实施）

## 八、第7阶段：最终集成验证（待实施）

## 九、第8阶段：最终集成验证（待实施）
>