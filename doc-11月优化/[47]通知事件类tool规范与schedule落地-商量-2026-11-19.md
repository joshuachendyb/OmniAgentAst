# 通知事件类 tool 规范与 schedule 落地文档

> 文档号: [47] | 签名: 商量 | 时间: 2026-11-19 11:26:31
> 编写/更新人: 商量（签名）
> 存放: D:\NDOOmniAgent\doc-11月优化\[47]通知事件类tool规范与schedule落地-商量-2026-11-19.md
> 性质: **规范类文档** —— 定义「通知事件类 tool」的设计规范，schedule 为首个落地范例
> 前置: [37] question 与 schedule 工具设计（[37] 留作历史，本文是通知事件类 tool 的规范收敛版）
> 更新: 2026-11-19 商量 - 新增 plan_stage 必填参数(LLM 主动阶段决策 init/update/finish, 宽松核对反馈)与 summary 阶段前缀

## 目录

- [1. 规范定位](#1-规范定位)
- [2. 规范条款（通知事件类 tool 必须遵循）](#2-规范条款通知事件类-tool-必须遵循)
  - [2.1 三条通道严格分离](#21-三条通道严格分离)
  - [2.2 呈现标记机制（notice 可选字段）](#22-呈现标记机制notice-可选字段)
  - [2.3 工具行屏蔽的统一判据](#23-工具行屏蔽的统一判据)
  - [2.4 前端接收范式](#24-前端接收范式)
  - [2.5 错误二分（工具内校验范式）](#25-错误二分工具内校验范式)
- [3. schedule 落地（首个范例）](#3-schedule-落地首个范例)
  - [3.1 工具定义](#31-工具定义)
  - [3.2 参数结构](#32-参数结构)
  - [3.3 错误二分](#33-错误二分)
  - [3.4 三态行为](#34-三态行为)
  - [3.5 前端链路](#35-前端链路)
- [4. 关键代码位置](#4-关键代码位置)
- [5. 复用指引（下一个通知事件类 tool）](#5-复用指引下一个通知事件类-tool)
- [6. 验证](#6-验证)

---

## 1. 规范定位

本仓工具按「与用户交互方式」可分为两类：

| 类别 | 本质 | 代表 | 前端呈现 |
|---|---|---|---|
| 业务类 tool | 操作文件/网络/系统/数据，产出业务结果 | read/write/shell/query_sql | 结果随 observation 步进业务流水线 |
| **通知事件类 tool** | **不操作外部资源，产出的是「给用户看的一份状态/清单/进度」** | **schedule（首个）** | **走 notice 独立事件，不进业务流水线** |

通知事件类 tool 的特征：
1. 产出是「呈现给用户的信息」（计划清单、进度、状态），不是文件/数据操作结果。
2. 前端有专属呈现组件（schedule→taskinfo 计划卡片），而非通用 observation 工具行。
3. 需要跨会话/刷新保持（清单入会话快照）。
4. 三态（成功/警告/错误）都要能告诉用户，且呈现位置可能不同。

**本规范定义这类 tool 的统一设计范式**：schedule 是第一个落地者，后续同类 tool（进度看板、状态面板等）照此套用。

## 2. 规范条款（通知事件类 tool 必须遵循）

### 2.1 三条通道严格分离

| 通道 | 载体 | 内容 |
|---|---|---|
| 返回 LLM + 落库 | observation 步（`llm_data`/`data`） | 三态都有：成功/失败/警告 + 业务数据 |
| 前端步骤流（工具行） | ActionStep / ObservationStep | **无** —— 不画通用工具行 |
| 前端呈现 | notice 事件 | 三态都发，按呈现标记分派位置 |

关键点：notice 是 SSE-only、不落库、不进 LLM；业务数据靠 observation 步落库 + 喂 LLM。两条路互不干扰。

### 2.2 呈现标记机制（notice 可选字段）

notice 信封：`type=notice + kind + phase + content + items? + only_event?`
- `kind`：通知种类（工具名或事件名）
- `phase`：生命周期阶段（start/done/failed）
- `items`：结构化载荷（给专属呈现组件）
- `only_event`：呈现标记（默认 false）—— true=仅事件列表，不画卡片、不占位置2

`only_event` 是新引入的**通用呈现维度**：不绑死 phase，语义正向、默认维持现状、老帧缺字段按 false 处理零退化。后续任何"只需事件列表提示、不需卡片"的通知都可复用。

### 2.3 工具行屏蔽的统一判据

用工具属性 `hide_from_steps` 声明（注册时），框架层 `tool_registry.visible_in_steps(name)` 统一判据，在 SSE 转发出口（`format_agent_sse`）的**转发副本**上摘除工具行——**不改 event_log 原对象**（落库/喂 LLM/历史回放不受影响）。

工具自己不写屏蔽逻辑，业务调用点零改动；新工具想隐藏只需注册时声明 `hide_from_steps=True`（OCP 扩展点）。

### 2.4 前端接收范式

notice 事件 → `sseParser` 统一解析（push 事件列表 + 按 kind/呈现标记分派）→ 专属 store 字段（入快照，刷新恢复）→ 专属呈现组件。历史态（详情）不渲染专属卡片，避免两套事实混排。

### 2.5 错误二分（工具内校验范式）

- 完全错误（结构不符）→ `build_error`，拒绝，呈现为 `failed` notice
- 可容忍错误（值超标）→ 就地裁剪/归位 + `build_warning`，照常落地，呈现为 `done` notice

约束前置到参数 schema（enum/required/additionalProperties/maxLength/maxItems），工具体内校验为兜底双保险；常量单一真源，schema/描述/校验/失败 hint 全部引用，杜绝漂移。

## 3. schedule 落地（首个范例）

### 3.1 工具定义

schedule = 会话内任务/计划清单，一次提交完整清单（整体替换）。分类 AGENT，注册声明 `hide_from_steps=True`。

### 3.2 参数结构

两个参数均**必填**（schema `required=[items, plan_stage]`）：

1. `items`：完整清单，`[]` 即清空。每项仅两个字段：
   - `content`：一句话动作短语，非空，≤100 字
   - `status`：四选一必填 —— `pending`/`in_progress`/`completed`/`cancelled`
   上限 20 项。经 `json_schema_extra` 内联 item schema（enum/required/additionalProperties=false/maxLength/maxItems），保持 `List[Dict[str,Any]]` 扁平类型故无 `$ref/$defs`，严格 provider 兼容。

2. `plan_stage`：LLM 结合任务进展**主动声明**的计划阶段，enum 三选一 —— `init`（初建）/ `update`（更新进展）/ `finish`（结束清空）。语义提示非精密状态机：后端与 items 做**宽松核对**（如 finish 但清单非空 → 反馈提示，不硬拒绝），核对结论进 `llm_data.plan_stage_note`（LLM 下一轮可见）；`update` 阶段附"后续持续维护清单"引导。阶段中文含义前置到 summary（`任务计划:初建/更新/结束;`），notice content 随之可见。

### 3.3 错误二分

| 完全错误 → error | 可容忍 → warning |
|---|---|
| items 非数组 / 项非对象 / 含未知字段 / 缺 content / content 非字符串或空 / 缺 status / status 非字符串 | 条数>20 裁剪前 20 / content>100 字裁剪 / status 非法值归 pending |

体外 `_validate_params` 只做顶层（items 是不是 array、JSON coerce），与体内元素级校验无重叠。

### 3.4 三态行为

| 状态 | exec_code | LLM+落库 | step 工具行 | notice | 前端 |
|---|---|---|---|---|---|
| 成功 | success | ✔ | 无 | done + items | 事件列表 + 卡片 + 位置2 |
| 可容忍 | warning | ✔ | 无 | done + 处理后 items | 事件列表 + 卡片 + 位置2 |
| 完全错误 | error | ✔ | 无 | failed + only_event=true | 仅事件列表 |

LLM 文案：`message` 全仓规范（成功/完成但有警告/失败）；`summary` 计数式「收到N项: 已完成X, 未完成Y(进行中A/待开始B), 已取消Z」；错误 `✖错误`+参数说明 hint，警告 `⚠警告`+裁剪/归位项。

### 3.5 前端链路

```
notice(kind=schedule) → sseParser: push 事件列表 + (done && !only_event && items → onScheduleUpdate)
  → chatStreamStore.setScheduleList → 快照(刷新恢复) → ScheduleCard 读 store
useTaskInfo: only_event=true 跳过位置2；三态都 push 事件列表
```

清单类型 `ScheduleItem`/`ScheduleStatus` 定义在 `streams/chatStreamTypes.ts`（由 backupTypes.ts 改名）。`useScheduleList` 步骤流派生 hook 已删除。

## 4. 关键代码位置

| 层 | 文件 | 要点 |
|---|---|---|
| 常量 | `backend/app/tools/tool_constants.py` | SCHEDULE_* 单一真源 + SCHEDULE_ITEM_SCHEMA 内联约束 |
| 工具 | `backend/app/tools/agent/schedule.py` | 校验二分 + 三态 notice + build_* |
| schema/注册 | `agent_schema.py` / `agent_register.py` | 内联约束 / hide_from_steps + 路由描述 |
| 回调/发射 | `context.py` / `tool_executor.py` / `step_emitter.py` | notice 回调含 items/only_event 透传 MetaStep |
| SSE 过滤 | `backend/app/utils/sse_formatter.py` | hide_from_steps 转发副本摘工具行 |
| 解析/状态/渲染 | `sseParser.ts` / `chatStreamStore.ts` / `useTaskInfo.ts` / `ScheduleCard.tsx` | notice 分派 + 卡片 + 事件列表/位置2 |
| 类型 | `frontend/src/features/chat/streams/chatStreamTypes.ts` | ScheduleItem/ScheduleStatus |

## 5. 复用指引（下一个通知事件类 tool）

1. 注册时声明 `hide_from_steps=True`（工具行屏蔽自动生效）
2. notice 用 `kind=工具名`，按三态发 `phase=done/failed`
3. 只需事件列表的提示用 `only_event=true`（如错误摘要）
4. items 带结构化载荷给专属呈现组件，专属字段入会话快照
5. 常量与 schema/描述/校验同源，约束前置参数层
6. 前端按 §2.4 范式加专属 store 字段 + 呈现组件

## 6. 验证

- 参数 schema 无 `$ref/$defs`，enum/maxItems/maxLength/additionalProperties 完整（实测）
- 三态 notice + obs 文本实测；backend ruff 零错误、40 单测全过；frontend typecheck/eslint/prettier 全过、7 单测全过

---

**编写/更新人: 商量（签名）**
**时间: 2026-11-19 11:26:31**
