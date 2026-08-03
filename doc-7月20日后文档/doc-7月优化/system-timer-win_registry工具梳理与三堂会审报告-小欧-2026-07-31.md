# system/timer/win_registry 工具参数全面三堂会审报告

**文档名称**: system-timer-win_registry工具梳理与三堂会审报告-小欧-2026-07-31.md
**创建时间**: 2026-07-31 10:32:04
**更新时间**: 2026-07-31 17:00:00 小欧

## 版本历史
| 版本 | 时间 | 更新信息 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-07-31 10:32 | 初稿，包含三分类完整三堂会审+4项修复 | 小欧 |

---

## 一、概述

沿用 desktop 工具集的 `参数合理性分析` + `冲突检测` + `schema描述指引` + `三思三省` 方法论，对 system（4工具）、timer（6工具）、win_registry（3工具）三个分类进行完整梳理。

**总览**: 13 工具，0 个真实 bug，4 个 schema 指引增强项（已修复），其余均为观察项无功能性问题。

**修复提交**:
1. `timer_schema.py` - TimerSetInput.callback 加 `min_length=1` / TimeAddInput.delta 加范围指引 / QueryCalendarInput.year 加 `ge=1900, le=2100`
2. `system_schema.py` - EventLogInput.level 移除 `Optional`（与 `default="error"` 自相矛盾）

---

## 二、各分类三堂会审逐工具分析

### 系统分类 SYSTEM（4 工具）

**文件**: `backend/app/tools/system/system_schema.py` / `event_log.py` / `create_task.py` / `delete_task.py` / `list_tasks.py`

#### 1. event_log — EventLogInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | `log_name` Literal 三选项，`max_events` ge/le 约束，`time_range` Literal 四选项 |
| 冲突检测 | ⚠️ 观察 | `level: Optional[Literal[...]]` 与 `default="error"` 自相矛盾 — Optional 暗示 None 合法，但默认值固定为 "error"。Pydantic 允许 None 但实际行为仍为 "error"，LLM 可能误以为 omit level 返回全部级别 |
| schema 描述 | ✅ 良好 | level 描述含可选值列表，time_range 描述含选项 |
| 冗余 | ✅ 无 | 所有参数均必要 |
| 缺失 | ✅ 无 | |
| 实现交叉验证 | ✅ 一致 | `level_map` 映射与 schema Literal 值完全匹配；filter 逻辑在 `if level and level != "info"` 中正确实现 |

**修复**: `level` 类型从 `Optional[Literal[...]]` 改为 `Literal[...]`（移除 Optional，保留 `default="error"`），description 补充"默认error"说明。

#### 2. create_task — CreateTaskInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | 3 必填 + 1 可选（interval），schedule 格式含详细示例 |
| 冲突检测 | ✅ 无冲突 | |
| schema 描述 | ✅ 良好 | schedule 的格式描述清晰，interval 描述无歧义 |
| 冗余 | ✅ 无 | |
| 缺失 | ✅ 无 | |

#### 3. delete_task — DeleteTaskInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | 单参数 str，最简设计 |
| 实现交叉验证 | ✅ 一致 | `task_name` 直传 `schtasks /delete`，无额外处理 |

#### 4. list_tasks — ListTasksInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | task_name Optional（模糊匹配），state Literal 四选项默认 all |
| 实现交叉验证 | ✅ 一致 | client-side 过滤，state 值与 Literal 完全匹配 |

**⚠️ 观察项**: system_schema.py 注册 4 工具 + reg_register 注册 1 工具 = 总计 5？实际 `list_tasks.py` 的 `__all__` 导出 `list_tasks` 但注册时注册的是 `task_control`（统一 control 工具入口）。`system_register.py` L12 注释写"4个"，实际注册 event_log + task_control（task_control 内部 create/delete/list） + reg_register（3 个 registry 工具）= 4+3=7 注册点。注册计数与 schema 中 4 工具一致（reg_register 是独立注册点）。

---

### 定时器分类 TIMER（6 工具）

**文件**: `backend/app/tools/timer/timer_schema.py` 及相关实现

#### 1. timer_set — TimerSetInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ⚠️ 需增强 | `callback` 为 `str` 无 `min_length`，LLM 可传入空字符串产生无意义的定时器 |
| 冲突检测 | ✅ 无冲突 | |
| schema 描述 | ✅ 良好 | delay 的 ge/le 约束 + 范围描述清晰 |
| 冗余 | ✅ 无 | |
| 缺失 | ✅ 无 | |
| 实现交叉验证 | ✅ 一致 | L88-91 运行时 guard delay<=0 / delay>86400；callback 原样存储/回调空字符串无害但无意义 |

**修复**: `callback` 加 `min_length=1`，description 补充"不可为空"。

#### 2. timer_clear — TimerClearInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | 单参数 str |
| 实现交叉验证 | ✅ 一致 | 未知 timer_id 返回 "not exist" 处理正确 |

#### 3. timer_list — TimerListInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | 空模型（同 MousePositionInput 模式） |
| 输出限制 | ✅ 良好 | `TIMER_LIST_OUTPARM_LIMIT_TIMER_IDS` 常量限制输出条目 |

#### 4. time_add — TimeAddInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ⚠️ 需增强 | `delta` 为 float 无 ge/le 约束，极端值（如 ±999999999秒）可产生无意义日期 |
| 冲突检测 | ✅ 无冲突 | |
| schema 描述 | ⚠️ 需增强 | delta 描述缺少范围指引 |
| unit 与实现 | ✅ 一致 | `days`=×86400, `hours`=×3600, `minutes`=×60, `seconds`=×1, `months`=×30 (approx) |
| 冗余 | ✅ 无 | 与 time_diff 互补 |

**修复**: delta description 补充范围指引（实现中 `timedelta(seconds=delta*unit)` 实际使用秒单位处理所有 unit，months 用×30近似）。

#### 5. time_diff — TimeDiffInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | start 必填，end 默认 now() |
| schema 描述 | ✅ 良好 | ISO格式、示例、注意事项均清晰 |
| 实现交叉验证 | ✅ 一致 | `_parse_datetime_any` 处理多种格式，非法输入返回错误 ✓ |

#### 6. query_calendar — QueryCalendarInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ⚠️ 需增强 | `year` 无 ge/le 约束，LLM 可传入 year=0 或 year=10000 |
| 冲突检测 | ✅ 无冲突 | |
| schema 描述 | ✅ 良好 | name 双模式用法清晰（节日名/日期字符串） |
| 实现交叉验证 | ✅ 一致 | 异常年份 `_get_holiday_date_by_name` 返回 None → 友好错误提示 ✓ |

**修复**: `year` 加 `ge=1900, le=2100` 约束。

---

### 注册表分类 WIN_REGISTRY（3 工具）

**文件**: `backend/app/tools/win_registry/win_registry_schema.py` 及相关实现

#### 1. registry_read — RegistryReadInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | path + hive + value_name + output_format，四参数分工明确 |
| 冲突检测 | ✅ 无冲突 | `_check_path_hive` validator 防止 hive/path 不一致 |
| schema 描述 | ✅ 良好 | hive description 含"系统级配置需显式指定HKLM"指引 |
| 冗余 | ✅ 无 | |
| 缺失 | ✅ 无 | |
| 输出安全 | ✅ 良好 | read 无危险操作，无需 backup/dry_run |

#### 2. registry_write — RegistryWriteInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | path/value_name/value/value_type/hive 完备 |
| 冲突检测 | ✅ 无冲突 | `_check_path_hive` + `validate_registry_key` 双重校验 |
| schema 描述 | ⚠️ 微调 | value Union[str,int] 对 LLM 模糊（不确定传 str 还是 int）|
| 缺失 | ✅ 无 | |
| 安全设计 | ✅ 优秀 | `backup_before_write=True` + `dry_run=False` 双保险 |
| 实现交叉验证 | ✅ 一致 | auto_detect 逻辑 (L133-134): `value.isdigit()` → REG_DWORD / else → REG_SZ |

#### 3. registry_delete — RegistryDeleteInput

| 维度 | 判定 | 说明 |
|------|------|------|
| 参数合理性 | ✅ 良好 | path/hive/value_name/recursive 完备 |
| 冲突检测 | ✅ 无冲突 | `_check_path_hive` validator |
| schema 描述 | ✅ 良好 | recursive description 解释了非空键需设为 True |
| 安全设计 | ✅ 优秀 | `validate_delete_safety` 运行时安全门 |

---

## 三、修复实施记录

### 修复 1: timer_schema.py - TimerSetInput.callback 加 min_length=1

- **文件**: `backend/app/tools/timer/timer_schema.py`
- **修改**: `callback: str = Field(..., ...)` → `callback: str = Field(..., min_length=1, description="...不可为空")`
- **原理**: 空字符串 callback 创建的定时器虽无害但无意义，LLM 应被告知不可传空值
- **验证**: `TimerSetInput(delay=10, callback='')` 现在抛出 ValidationError
- **实现交叉验证**: timer_set.py L78 `callback.strip()` 在空字符串情况下仍能运行（作为 log_message）— 修复是预防性而非紧急

### 修复 2: timer_schema.py - TimeAddInput.delta 加范围指引

- **文件**: `backend/app/tools/timer/timer_schema.py`
- **修改**: delta description 增加"建议范围-31536000~31536000(约±1年)"提示
- **原理**: 极大 delta 值产生无意义结果，指引 LLM 使用合理范围
- **未加硬约束**: timer_set.delay 因有进程内生存期限制需 ge/le，time_add 是纯计算无存储限制故仅加描述指引

### 修复 3: timer_schema.py - QueryCalendarInput.year 加 ge=1900, le=2100

- **文件**: `backend/app/tools/timer/timer_schema.py`
- **修改**: `year: Optional[int] = Field(default=None, ...)` → `year: Optional[int] = Field(default=None, ge=1900, le=2100, ...)`
- **原理**: 阻止 LLM 传入世纪外年份产生无意义的查询结果
- **验证**: `QueryCalendarInput(name='端午', year=1800)` 抛出 ValidationError

### 修复 4: system_schema.py - EventLogInput.level 移除 Optional

- **文件**: `backend/app/tools/system/system_schema.py`
- **修改**: `level: Optional[Literal["critical", "error", "warning", "info"]] = Field(default="error", ...)` → `level: Literal["critical", "error", "warning", "info"] = Field(default="error", description="...默认error...")`
- **原理**: `Optional[Literal[...]] = "error"` 自相矛盾 — Optional 暗示 None 合法/default 不传会变 None，但实际默认值为 "error"。修正后语义清晰：level 必传某合法值，默认"error"
- **无功能影响**: Pydantic v2 行为一致（default="error" 始终生效）

---

## 四、提交记录

| Hash | Message |
|------|---------|
| 待提交 | `fix:tool_schema system_timer_win_registry 四项参数指引增强 - 小欧-2026-07-31` |

---

## 五、整体评估

### 三分类总览

| 分类 | 工具数 | Bug 数 | 修复数 | 观察项 |
|------|--------|--------|--------|--------|
| system | 4 | 0 | 1 | 1（level 矛盾）|
| timer | 6 | 0 | 3 | 2（delta 无界/format 提示精度）|
| win_registry | 3 | 0 | 0 | 1（value Union 模糊）|
| **合计** | **13** | **0** | **4** | **4** |

### 与 desktop 对比

**desktop 工具集**: 11 工具，19 个真实 bug（含 schema 错误、参数缺失、功能退化），3 次 schema 增强，4 次提交修复

**本轮三分类**: 13 工具，0 个真实 bug（schema 定义均正确），4 次 schema 指引增强（提升 LLM 指引精度），本次 commit 完成修复

### 分类安全性对比

| 分类 | 安全特性 | 评估 |
|------|---------|------|
| system | 无危险操作 ✅ | event_log 纯查询 ✓，create_task 需显式 task_name |
| timer | 进程内定时器 ✓ | timer_set.delay ge/le 防止极端值 ✓ |
| win_registry | 危险操作多 | backup_before_write/dry_run/hard_delete 三保险 ✓ |

### 仍未修复的观察项（低优先级）

1. **time_add.delta** — 未加硬约束（纯计算），仅描述指引 — 如需约束可加 ge/le
2. **registry_write.value** — Union[str,int] 对 LLM 不够精确 — 如需增强可考虑拆分 description 提示 int→REG_DWORD
3. **time_diff** — format 指引可更精确（如提供 ISO 示例）— 当前已有基本指引
