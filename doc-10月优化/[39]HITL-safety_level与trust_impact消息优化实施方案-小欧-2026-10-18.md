# [39] HITL safety_level 与 trust_impact 消息优化实施方案

## 版本历史

| 版本 | 时间 | 作者 | 修改简介 |
|------|------|------|--------|
| v1.0 | 2026-10-18 12:12:51 | 小欧 | 创建：基于 [39]原案 方案 + 代码现态核对，给出逐文件 diff 实施方案 |
| v1.1 | 2026-10-18 12:20:00 | 小欧 | 融合 [39]原案 核心设计：①`severity` 整体删除（不改名）；②blocked 分支不塞 severity；③补回措辞补齐；④补回系统禁区说明 |
| v1.2 | 2026-10-18 12:27:27 | 小欧 | **补漏与纠错**：①**采纳「沙箱判定改读 requires_confirmation」**——v1.1 漏此项，而它是删 `severity` 的**硬依赖**（`path_tool_safety_checker:195/231/235` 直接读 severity，删字段即 AttributeError/TypeError），实测确认 [39]原案 §1.7「自证循环」成立；②新增 §三「两个 severity 的关键区分」——`MetaStep.severity`（info/warn）是**另一个类的另一个字段**，**严禁一并改名**；③补齐 v1.1 漏掉的文件与构造点：`dual_path_check`(125/142)、`shell_path_check`(121/145)、`path_tool_safety_checker`(195/207/211/221/227/231/234/235/247)；④行号按实测校正；⑤新增 §七 影响面清单 A/B/C/D/E 五类 |
| v1.3 | 2026-10-18 12:39:02 | 小欧 | **新增「严禁保留空 severity 字段」硬约束**：明确彻底删除而非置空，并给出实测差异——删字段则 `:195` 抛 AttributeError（fail-fast）；留空则该行恒 False **不报错** → `sandbox_required` 永不置位 → `sandbox_gate:79` 短路 → **沙箱预检静默失效**。安全模块必须 fail-fast。落位 §五.1 硬约束块 + §六.13 行内注释 + 验收锚点 |
| v1.4 | 2026-10-18 12:42:20 | 小欧 | **新增 §6.0 涉及修改的代码清单（19 文件）**。核查出 v1.3 **漏 4 处**：`backupTypes.ts:21-31` 类型源 / `sseParser.ts:959-966` **对象字面量白名单** / `useAuthorization.ts:79-98` **对象字面量白名单** / `index.tsx:109-119` `AuthorizationRequest`。**白名单层漏改任一 → 字段静默丢弃，后端改得再对前端也不显示**。同时查明 `chatStreamTransport.ts:917` 是 spread 不丢字段；精确证实 [39]原案 §1.4「severity 前端不读」根因是**转换层从未映射**。补 §6.15~6.18 |
| v1.5 | 2026-10-18 12:48:38 | 小欧 | **两项裁定落地（老陈裁定）**：①**`trust_impact` 由「requires_confirmation 的 relabel」改为「真授权影响面」**——v1.0~v1.4 的 `trust_impact = "中" if requires_confirmation else "小"` 是 bool 的一对一映射、**零信息量**，正是 [39]原案 §1.7 骂 `severity` 的原罪（重复编码），等于改名重犯。改为承载真正独立语义：真值源 = `temp_auth` 实际生效的 `recursive`（目录根→`high` 整棵子树／单文件→`low` 仅精确路径），**与 needs_confirm 正交**；值域改**英文标识** `high`/`low`（与 `path_auth` 等英文契约一致，前端映射中文显示），并恢复 [39]原案 原义的方向性。新增 `temp_auth.resolve_grant_recursive()` 作**单一真源**，两端共用杜绝口径漂移。②**字段缩短命名 `requires_confirmation` → `needs_confirm`**（老陈令，实测 60 处/14 文件，增量成本≈0：这些文件本就需重写该构造行；该字段纯后端内部，不进 paused 帧/DB/前端，对外契约零影响）。全文 diff 与清单同步 |
| v1.6 | 2026-10-18 12:52:00 | 小欧 | **全文一致性核查（三堂会审·老陈令：读全文 10 遍 + 逐节互校）**，修 7 处不一致 + 补 4 处代码遗漏。**①影响面统计错误（最严重）**：v1.5 用 `Select-String -Path "app\**\*.py"`，PS 5.1 下 `**` 不递归只扫一层 → 实为 **60 处/14 文件**（非 49/10），漏 `safety_gate.py`(7，含关键读取点 :197/:200)、`tool_facade.py`(2，:171 读取点)、`execute_shell_command.py`(1，:1135 读取点)、`tool_routes.py`(1，注释)；已新增 §6.20/6.21/6.22 三个 diff 节 + §6.0 清单扩至 23 文件 + §七 G 类全量重做 + 立"禁用非递归 glob"铁律。**②§6.14 diff 结构错误**：bypass 两分支的 `requires_confirmation=` 未改（上下文行当原文），会与新增 `needs_confirm=` 并存 → `TypeError`；已重写为标准三行 `-`/`+` 对照。**③§6.6 残留**：修正后仍留 `requires_confirmation=True` 在 `-` 行但 `+` 行缺改名，已重排。**④验收 #3 不可执行**：原 `grep -rn` 会被 6 处历史注释命中（铁规禁删历史），改为"排除 `#` 开头注释行"的递归命令。**⑤§三 第2行悬空引用**「§五.5」→ 改 §五.3。**⑥§五.1/§五.2 为凑数空节**（仅写"见§六.0/§四.2"）违反 KISS → 删除，§五.2 改为有实质内容的落地规则。**⑦§6.3 diff 上下文行写成了改后内容**（`_readonly` 那段），已改为标准 `-+` 对照。 |
| v1.7 | 2026-10-18 12:58:57 | 小欧 | **因并发 shell 重构而做行号全量重校 + 补 7 处漏记读取点**（老陈令：马上改文档）。**背景**：工作区出现非本轮的 shell 重构改动（删 `shell_command_process.py`、新增 `shell_readonly.py` 等 5 文件、改 `shell_path_check.py`/`safety_gate.py`/`execute_shell_command.py`），本方案相关文件行号已漂移。**①行号漂移校正**：`shell_path_check.py` 6 处构造点 `62,77,93,121,131,145`→**`62,83,99,127,137,151`**（后 5 处 +6 行）；`write_path_check.py` `:121/:124`→**`:120/:123`**；`delete_path_check.py` 4 处 −1 行。**②★补 7 处漏记的属性读取点**（v1.6 仅记 5 处，实为 **12 处**）：`dual_path_check` `:122/:137/:149/:153`、`path_tool_safety_checker:279`、`shell_path_check` `:74/:88/:142` —— 同为 `AttributeError` 级，非可选。根因：前几版按"文件"归类，**未区分同文件内的构造 kwarg 与属性读取**。**③统计口径改三分**（§七 G 类重做）：属性读取 12 / 构造 kwarg 15 / 字段定义 1 / 历史注释 32，取代 v1.6 的"60 处/14 文件"混合口径，并给出三条可执行校验命令。**④§七 C 类重写**为 12 处属性读取明细表。**⑤§6.0 清单与 §六.9/6.10/6.14 diff 同步补读取点**。**⑥章节号断裂修正**：`## 十二、` → `## 十一、`（§十一 此前缺失，违铁规「章节序号必须连续有序」）。**⑦自查纠正一处不准确表述**：此前口头提示"文档引用了 `shell_command_process.py`"，经 grep 核实**文档内并无该文件引用**，实际问题为行号漂移与漏记读取点。 |
| v1.8 | 2026-10-18 13:40:12 | 小欧 | **逐 diff 三堂会审（老陈令：对照本地代码核查每一代码 diff）**，22 节逐节审查，**18 节一次通过 / 3 节修正后通过**，新增 §12 会审结论。**①★发现1（关联·高）**：`tool_routes.py:23/:64` 用 `asdict(_sf)` 把 `SafetyResult` 整体转 dict 作为 `/tool/execute` 响应 `safety` 字段返回 → 改名 `requires_confirmation`→`needs_confirm` **属对外 API 契约变更**，**v1.7「纯后端内部·对外契约零影响」结论作废**（已同步修正 §一.1 第5条、§七 G 类；前端实测零消费，第三方受影响；按禁止 backward 不做兼容但须记入发布说明）。**②★发现2（正确性·高）**：**PowerShell 行号统计在本项目不可信**——`path_tool_safety_checker.py` PowerShell 报 247 行而 Python 权威 294 行；`shell_path_check.py` 构造点应为 `64/85/101/129/139/154`、读取点 `74/88/142`，**v1.7 基于 PowerShell 的"校正"反而把对的改成错的，已全部按 Python 权威重校**，并立铁律「本项目行号统计禁用 PowerShell，一律用 Python」。**③★发现3（合规·中）**：`temp_auth` 的空/根路径判定（防 `Path("")` 扩域成整盘授权，安全关键）在 `grant_temp_auth:48` 与新函数间 **DRY 违反** → 上提私有原子 `_is_rejectable_root(root)` 两端共用，已证纯等价重构。**④★发现4（正确性·中）**：`requires_confirmation=` 构造 kwarg 实为 **13 处**（非 15）；`dual_path_check`/`shell_path_check` 的 SafetyResult 构造**不含该 kwarg**（只含 `severity=`），故只需删 severity + 加 safety_level、**无需 kwarg 改名**（现有 diff 本就正确，已加注）。另复核确认 §6.6~6.9、§6.11~6.14、§6.19~6.20 共 40 余处行号与 diff 内容**均与本地代码一致**。 |
| v1.9 | 2026-10-18 13:45:00 | 小欧 | **按老陈令删除第十二章「三堂会审结论」**（v1.8 新增的会审章节，含逐 diff 通过/修正表与四项实质发现的完整论证）。**删除前已确认无信息丢失**：v1.8 四项发现的**修正成果均已落在他章**，随章保留 —— ①API 契约变更 → §一.1 第 5 条 + §七 G 类；②禁用 PowerShell 统计行号（改用 Python）→ §6.10 前置说明；③temp_auth DRY 违反的修复（`_is_rejectable_root` 上提 + 等价性证明）→ §6.2 diff 与节末说明；④构造 kwarg 实为 13 处、dual/shell_path 构造不含该 kwarg → §6.9/§6.10 注。本版本历史条目保留 v1.8 记录（编辑型文档禁删历史版本信息），仅正文删除该章。 |

---

**创建时间**：2026-10-18 12:12:51
**更新时间**：2026-10-18 13:45:00（小欧）
**编写人**：小欧

---

## 一、本文与 [39]原案 的关系

| 文档 | 定位 |
|------|------|
| [39]原案 | **原始方案**：问题诊断 + 候选落点评估 + 一步到位结论 |
| 本文（本文） | **实施方案**：完整采纳 [39]原案 全部核心设计 + 按代码现态修正 3 处缺陷 + 逐文件 diff |

[39]原案 的历史结论**不删除**。§四 逐条列出 [39]原案 核心设计及落位，§十二 给出 [39]原案 每一条到本文的完整对照。

### 一.1 核心结论（定案）

1. **`SafetyResult.severity` 整体删除**，不改名为 `trust_impact`。
2. **危险等级等价关系**（[39]原案 §1.7）为唯一表达：`blocked`（拦截）／`needs_confirm`（需确认）／两者皆 False（放行）。
3. **`trust_impact` 承载真授权影响面**，值域**英文标识** `high`/`low`，真值源 = `temp_auth` 实际生效的 `recursive`；**与 `needs_confirm` 正交**，不互推。
4. **沙箱判定改读 `needs_confirm`**（[39]原案 §1.6 第3步）——**必采纳**，是删 `severity` 的硬依赖。
5. **字段缩短命名**：`requires_confirmation` → `needs_confirm`（14 文件，增量成本≈0）。★**该字段经 `tool_routes.asdict` 出到 `/tool/execute` API 响应，属对外契约变更**（v1.8 关联审查推翻 v1.7 的「纯后端内部」结论，详见 §四.1 与 §十三）。
6. **`safety_level` 产地归位**：决策点直给，`_classify_safety_level` 降级为**兜底**（保留无 message 场景分类能力）。
7. **措辞补齐**：白名单外补时效、`non_system` 补"临时"二字。
8. **前端补齐 4 个缺失分类 + 三条独立说明行**（信任影响／临时授权时效／系统禁区不可授权）。

### 一.2 方案的意义

| # | 现状病根 | 治法 |
|---|---------|------|
| 1 | `safety_level` 由 `_classify_safety_level` **扫中文 message 文本**反推 → 文本**承重**，改措辞会悄悄改坏分类 | 决策点直给，文本降级为纯展示；分类不再依赖措辞 |
| 2 | `severity` 与 `blocked`/`needs_confirm` **完全重复编码**，唯一实用消费者（沙箱标记）还是自证循环 | 删字段，等价信号承载；沙箱直读 `needs_confirm` |
| 3 | 用户看不到"这是**临时**授权（任务级、结束自动失效）"，也分不清与"信任此操作"（会话级）是两套机制 | `path_auth` 挂独立说明行，讲清时效与两套机制差别 |
| 4 | `forbidden_zone`（系统禁区）**永不授权**，弹窗却只说"禁区"，用户仍以为点确认就能过 | `forbidden_zone` 挂"系统禁区不可授权"说明行 |
| 5 | 用户**看不到这次授权到底给了多大自由度**（一个文件 vs 整棵子树） | 新增真影响面 `trust_impact`，按实际生效 `recursive` 判定 |
完整携带链路
L2 call dict  ──┬─ tool_name / _normal_name ──→ _cn
 └─ tool_params ──────────────→ _cp
        ↓
ConfirmSpec (handlers/hitl_gateway.py:33-43)
   tool_name / params / path / content / safety_level / severity / auto_confirm
        ↓  hitl_confirm (hitl_gateway.py:108-113)
paused 帧 MetaStep (SSE + 落库)
        ↓
前端 AuthorizationRequest (index.tsx:109-119)
        ↓
AuthorizationModal 渲染
---
工具靠 tool_name，参数靠 params，范围靠 trust_path
后端 paused 帧字段（hitl_gateway.py:108-113）：

字段	携带什么	来源
tool_name	工具名（已归一规范名）	spec.tool_name = safety_gate 的 _cn
params	参数摘要（脱敏+截断后）	_desensitize(_summarize_params(...))
trust_path	授权/操作范围路径	spec.path or extract_trust_path(...)
content	原因句（即 SafetyResult.message）	spec.content
safety_level	问题来源分类	spec.safety_level
severity→trust_impact	影响面	[40] 改名
auto_confirm / confirm_timeout / backend_timeout / confirm_id	倒计时与自动确认	网关
前端 AuthorizationRequest（index.tsx:109-119）:

{
  confirmId: string;
  toolName: string;                 // ← 工具名
  params: Record<string, unknown>;  // ← 参数摘要
  content?: string;                 // ← 原因句（WebkitLineClamp:2 截断）
  safetyLevel: string;              // ← 查 SAFETY_LEVEL_CONFIG 出标签/颜色/图标
  trustPath?: string | null;        // ← 操作范围行
  autoConfirm?, confirmTimeout?, backendTimeout?
}
⚠️ 这里没有 severity 字段 —— 实测印证 [39] §1.4「severity 前端不读」。[40] 需在此补 trustImpact?: '中' | '小'。

三、params 的两重加工（hitl_gateway.py:46-74）
原始 params
  ↓ _summarize_params()   摘主键: extract_trust_path() 取 path 提到最前
  ↓                       去重: 跳过 key=="path"（已由 trust_path承载）
  ↓                       截断: 字符串 >140 → truncate_text 尾部切 + "...[截断N字符]"
  ↓                       单行化: re.sub(r"\s*\n\s*", " ") 把换行压成空格
  ↓ _desensitize()        剔除 SENSITIVE_FIELDS
最终 params
前端再 Object.entries(p).map(([k,v]) => \${k}=${truncateValue(v,80)}`) 逐行渲染（index.tsx:192-197`）。

四、前端渲染的对应关系
区域	用哪个字段	源码位置
标签「需授权/删除确认…」	safetyLevel → SAFETY_LEVEL_CONFIG	:131-149, :338
原因句（2行截断，title 存全文）	content	:311-344
操作范围行 操作范围: {目录}	trustPath + toolName	:347-379
参数列表	params	:192-197

## 二、两个 `severity` 的关键区分（★实施前必读，最大陷阱）

代码里存在**两个不同的 `severity` 字段**，属于**两个不同的类**，同名但语义完全不同：

| # | 字段 | 所属类 | 取值 | 本次 |
|---|------|--------|------|------|
| 1 | `SafetyResult.severity` | `app/tools/tool_types.py` | `safe`/`risk`/`dangerous` | **删除** |
| 2 | `MetaStep.severity` | `app/services/agent/steps/base.py` | `info`/`warn`/`error` | **严禁改动** |

**风险**：全局替换会把 `MetaStep` 的 SSE 分级一起改掉，破坏前端错误通道与提示样式。

**必须原样保留的 `MetaStep.severity` 站点（实测全量）**：

| 文件 | 行号 |
|------|------|
| `app/services/agent/handlers/hitl_gateway.py` | 129（`resumed` 帧 `severity="info"`）— **注意：只改同文件 111 行 paused 帧** |
| `app/services/agent/event_emitter.py` | 65, 91, 101, 111, 129 |
| `app/services/agent/react_step.py` | 370, 436, 503, 545, 571 |
| `app/services/agent/react_loop.py` | 292, 328 |
| `app/services/agent/react_inference.py` | 56 |
| `app/services/agent/handlers/handle_answer.py` | 156 |
| `app/services/agent/handlers/handle_action.py` | 200 |
| `app/services/chat/stream_orchestrator.py` | 289 |
| `app/monitoring/agent_telemetry.py` | 294, 430 |
| 前端 `types/execution.ts:162`、`services/error/handler.ts:174` 起全表 | （另一套体系） |

---

## 三、[39]原案 核心设计采纳清单

| # | [39]原案 出处 | 设计 | 落位 |
|---|---------|------|------|
| 1 | §1.3 事实1 / §1.6 第1步 | `safety_level` **产地归位** | §六.5~6.14；§六.3 字段优先+文本兜底 |
| 2 | §1.4 / §1.6 第2步 | `severity` 正名为 `trust_impact` | §五.3 真影响面（非改名 relabel） |
| 3 | §1.6 第3步 / §1.7 | **危险等级等价关系** | §五.2 |
| 4 | §1.6 第3步 | **沙箱判定改读 `needs_confirm`** | §五.4 + §六.14 |
| 5 | §1.6 第3步 | **blocked 分支不再塞 severity** | §六各处 |
| 6 | §1.6 第4步 | `trust_impact` 显示信任影响 | §六.17 |
| 7 | §1.6 第4步 | `path_auth` 挂临时授权时效说明 | §六.17 |
| 8 | §1.6 第4步 | **系统禁区不可授权**说明 | §六.17 |
| 9 | §1.6 第4步 | 说明渲染成**独立一行**（不追加进 `content`） | §六.17 |
| 10 | §1.6 第5步 | **措辞补齐** | §六.6 |
| 11 | §1.4 / §1.5 E | **不新增 `reason_code`** | 全文 |
| 12 | §1.3 事实2 | `content` 被 `WebkitLineClamp:2` 截断 | §六.17 独立行规避 |
| 13 | §1.3 事实3 | `temp_auth` 是**后端任务级不变式** | §六.6 说明行只描述不改语义 |
| 14 | §1.5 | 落点 E 最优 | 全文 |

---

## 四、字段契约

### 四.1 `SafetyResult`（`app/tools/tool_types.py`）

| 字段 | 类型 | 含义 | 本次 |
|------|------|------|------|
| `blocked` | bool | 是否拦截（**等价**旧 `dangerous`） | 不变 |
| `needs_confirm` | bool | 是否需确认（**等价**旧 `risk`） | **改名**（原 `requires_confirmation`） |
| `message` | str | 原因句（纯展示，不承载分类） | 不变 |
| `safety_level` | str | 问题来源分类 | **新增** |
| `auto_confirm` | bool | 是否自动确认 | 不变 |
| `auth_path` | Optional[str] | 临时授权路径 | 不变 |
| `sandbox_required` | bool | 是否需沙箱预检 | 不变（取值来源改，见 §五.4） |
| ~~`severity`~~ | — | — | **删除** |

> `trust_impact` **不进** `SafetyResult`（它由 `auth_path` 派生，存进去即重复编码）。

> ★★ **硬约束一：严禁把 `severity` 改成空值/占位保留，必须彻底删除字段定义。**
>
> | 方案 | `path_tool_safety_checker.py:195` `known_risk.severity == "risk"` | 后果 |
> |------|-----------------------------------------------------------|------|
> | **删除字段**（本方案） | 抛 `AttributeError` | ✅ **fail-fast**：立刻炸，当场暴露 |
> | **保留空字段**（禁止） | 恒为 `False`，**不抛异常** | ❌ **fail-slow 静默降级** |
>
> 保留空字段的致命后果链：`severity` 恒空 → `:195` 恒 `False` → `sandbox_required` 永不再置位
> → `sandbox_gate.py:79` `if not getattr(safety_result, "sandbox_required", False): return` 直接短路
> → **沙箱预检被静默跳过** → 越权写/注册表写/危险失败兜底**无沙箱直接执行**，**无异常、无日志、常规测试大概率仍绿**。
> 安全模块必须 fail-fast：崩溃暴露 ≫ 静默失效。
> 先例：`SafetyResult.is_safe` 即无人消费僵尸字段，2026-07-18 已删（见本类 docstring）；再留空 `severity` 属重蹈覆辙，违反 YAGNI。
> **验收锚点**：`SafetyResult` 类体内不得出现 `severity` 字段行。

> ★★ **硬约束二：`needs_confirm` 改名不得留旧名别名。**
> 严禁写 `requires_confirmation` 的 property/兼容别名 —— 违反「禁止 backward」铁律，且会留下两份真源。
> 改名须**一次性全量替换**（实测 60 处/14 文件），落地后 `grep -rn "requires_confirmation" backend/app` 应零匹配。

### 四.2 危险等级等价关系（[39]原案 §1.7）

| 旧 `severity` | 等价信号（唯一真源） | 语义 | 进 HITL？ |
|--------------|-------------------|------|----------|
| `dangerous` | `blocked=True` | 拦截 | 否 |
| `risk` | `needs_confirm=True` | 需确认 | 是 |
| `safe` | `blocked=False` 且 `needs_confirm=False` | 放行 | 否 |

### 四.3 `trust_impact` 值域（英文标识，前端映射中文）

| 值 | 中文显示 | 含义 | 判定 |
|----|---------|------|------|
| `high` | 信任影响：**大** | 授予**整棵子目录树**的操作权 | `resolve_grant_recursive(auth_path) == True`（目录根） |
| `low` | 信任影响：**小** | 仅授予**该精确路径** | `resolve_grant_recursive(auth_path) == False`（单文件／无 auth_path） |

### 四.4 `safety_level` 取值 ↔ 前端展示

| `safety_level` | 前端标签 | 颜色 | 附加说明行 |
|---------------|---------|------|-----------|
| `path_auth` | 需授权 | orange | 「临时授权仅本任务有效，任务结束自动失效」 |
| `shellparam` | 命令确认 | orange | — |
| `tool_write` | 写确认 | geekblue | — |
| `tool_delete` | 删除确认 | red | — |
| `tool_execute` | 执行确认 | volcano | — |
| `forbidden_zone` | 系统禁区 | red | 「系统禁区不可授权」 |
| `command_block` | 危险命令 | red | — |
| `data_guard` | 数据保护 | orange | （当前无产地，见 §六.14 注） |
| `unregistered` | 未注册 | volcano | — |

---

## 五、两处判定的实现细则

### 五.2 危险等级等价关系（[39]原案 §1.7）

见 §四.2。落地时只需遵守一条：**blocked 分支不塞任何"等级"字段**，`needs_confirm` 分支不塞 `severity`（已删）。

### 五.3 `trust_impact` 判定（**单一真源，两端共用**）

**真值源 = `temp_auth` 实际生效的 `recursive`**。实测依据 `temp_auth.py:52-56`：

```python
# 2026-09-03 小欧 修复: 文件路径(有后缀)强制 recursive False，仅目录保持 True，防 task 级目录越权
_recursive = recursive
if recursive and isinstance(root, str) and Path(root).suffix:
    _recursive = False
```

| 授权目标 | 实际 `recursive` | 授予的自由度 | `trust_impact` |
|---------|------------------|-------------|----------------|
| 目录 `D:\data` | `True` | 整棵子目录树 | `high` |
| 单文件 `D:\data\x.txt` | `False` | 仅该文件 | `low` |

**关键设计（老陈裁定：复用 temp_auth 规则，杜绝两套口径）**：把上述 suffix 规则从 `grant_temp_auth` 内联逻辑**上提为独立函数** `temp_auth.resolve_grant_recursive(root, requested)`，两端共用：

- `grant_temp_auth` 内部改调本函数（授权**写入**口径）
- `safety_gate._resolve_trust_impact` 调本函数（影响面**展示**口径）

若两处各自判 suffix，必然漂移：授权按目录给了整子树，影响面却按单文件显示「小」。

**与 `needs_confirm` 正交性**：不管弹不弹窗、是否需确认，只要存在 `auth_path` 即可定影响面；两者无推导关系。

**`sandbox_gate.py` 的特例**：该处是系统禁区裁决（`forbidden_zone`），**永不授权** → 无授权会被授予 → 无"授权影响面"可言 → **不传 `trust_impact`**（留空，前端 `request?.trustImpact &&` 判空不渲染），只显示「系统禁区不可授权」。

### 五.4 沙箱判定改读 `needs_confirm`（[39]原案 §1.6 第3步，**必做**）

**现状（实测）**：
```python
# path_tool_safety_checker.py:195
known_risk.sandbox_required = (known_risk.severity == "risk")
# path_tool_safety_checker.py:231-235
severity = "risk" if needs_confirm else "safe"
return SafetyResult(..., severity=severity, sandbox_required=(severity == "risk"))
```

**两个问题**：
1. **删字段即崩**：删 `severity` 后 `:195` 读 `known_risk.severity` 抛 `AttributeError`；`:234` 传 `severity=` 抛 `TypeError`。
2. **自证循环**（[39]原案 §1.7 判断成立）：`:231` 由 `needs_confirm` 推出 `severity`，`:235` 又由 `severity` 反推 `sandbox_required` —— 绕一圈等于 `needs_confirm`，中间那层编码纯属冗余。

**改法**：
```python
known_risk.sandbox_required = known_risk.needs_confirm     # :195
return SafetyResult(needs_confirm=needs_confirm, blocked=False,
                    message=_shell_msg or "", sandbox_required=needs_confirm)   # :233-235
```

**等价性证明**：`:195` 处 `known_risk` 已排除 `blocked`（`:186`），恒为 `needs_confirm=True` 的授权请求，故两式**恒等**；`:231-235` 处 `severity=="risk"` 与 `needs_confirm` **定义上恒等**。→ **纯等价收敛，行为不变，非缺陷修复**。

---

## 六、逐文件 diff（行号按 2026-10-18 实测）

### 6.0 涉及修改的代码清单（共 23 个文件）

> 分类：**后端字段层 1** / **后端产码点 10** / **后端编排层 3** / **后端下游消费 2** / **前端映射链 4** / **前端视图 1** / **核对不动 3**
>
> ★ 本表于 v1.6 经**全量递归 grep**（`Get-ChildItem -Recurse -Filter *.py`）校正：v1.5 曾用 `app\**\*.py`（PS5.1 下 `**` 不递归，只扫一层），导致 `safety_gate.py` / `tool_facade.py` / `execute_shell_command.py` / `tool_routes.py` 四个文件被漏统计。**教训：影响面统计禁用非递归 glob。**

| # | 文件 | 层 | 修改要点 | 漏改后果 |
|---|------|----|---------|---------|
| 1 | `app/tools/tool_types.py` | 字段层 | **删** `severity`；**新增** `safety_level: str = ""`；**改名** `requires_confirmation` → `needs_confirm`；`pass_result()` 同步 | 全部产码点 `severity=` 变 `TypeError`；旧名残留致新旧两套真源 |
| 2 | `app/safety/temp_auth.py` | 产码 | **新增** `resolve_grant_recursive(root, requested)`（suffix 规则上提为单一真源）；`grant_temp_auth` 内部改调它；`__all__` 补 | 影响面口径与授权口径漂移 |
| 3 | `app/safety/path_tool_safety_checker.py` | 总闸 | 7 处构造点补 `safety_level` + kwarg 改名；**`:195` 沙箱改读 `needs_confirm`**；`:231` 删 `severity` 中间变量；`:221` 不再把 check_fn 的 severity 灌入 | ★`:195` `AttributeError`；沙箱预检静默失效 |
| 4 | `app/services/agent/handlers/safety_gate.py` | 编排层 | `:197`/`:200` **读取点**改 `needs_confirm`；`:254` **字段优先+文本兜底**；新增 `_resolve_trust_impact()`；`:265` 改 `trust_impact=` | 读取点 `AttributeError`；分类退回扫文本 |
| 5 | `app/services/agent/handlers/hitl_gateway.py` | 编排层 | `ConfirmSpec.severity` → `trust_impact`；`:111` paused 帧改键。**`:129` `MetaStep.severity="info"` 严禁动** | paused 帧仍带旧键 |
| 6 | `app/services/agent/handlers/sandbox_gate.py` | 编排层 | `:150` 删 `severity="risk"`，`trust_impact` **不传**（禁区永不授权，见 §五.3） | 误导用户以为禁区可授权 |
| 7 | `app/safety/write_path_check.py` | 产码 | 4 处补 `safety_level` + kwarg 改名；**措辞补齐**（`:120` 加"临时"、`:123` 加时效） | 弹窗看不出是临时授权 |
| 8 | `app/safety/read_path_check.py` | 产码 | 2 处补 `safety_level="path_auth"` + kwarg 改名 | 弹窗无分类标签 |
| 9 | `app/safety/delete_path_check.py` | 产码 | 7 处补 `safety_level`（5×`tool_delete`+2×`forbidden_zone`）+ kwarg 改名 | 同上 |
| 10 | `app/safety/dual_path_check.py` | 产码 | 2 处补 `safety_level` + kwarg 改名 | 同上 |
| 11 | `app/safety/shell_path_check.py` | 产码 | 6 处补 `safety_level` + kwarg 改名 | 同上 |
| 12 | `app/safety/shell_danger_command.py` | 产码 | `:93` 补 `safety_level="command_block"` | 同上 |
| 13 | `app/safety/shell_command_risk.py` | 产码 | `:124` 补 `safety_level="shellparam"` | 同上 |
| 14 | `app/safety/path_legality_router.py` | 产码 | `:117` fail-closed 补 `safety_level="command_block"` | 同上 |
| 15 | **`app/services/tool/tool_facade.py`** | **下游消费** | **`:171` `if safety.requires_confirmation and not safety.auto_confirm:` → `needs_confirm`**（v1.5 **完全漏掉**） | ★`AttributeError`，直调 API 确认路径崩 |
| 16 | **`app/tools/fundamental/execute_shell_command.py`** | **下游消费** | **`:1135` `if safety.requires_confirmation:` → `needs_confirm`**（v1.5 **完全漏掉**） | ★shell 确认路径崩 |
| 17 | `frontend/src/features/chat/streams/backupTypes.ts` | 前端类型源 | `PendingAuthorizationPayload` 增 `trust_impact?: 'high' \| 'low'` | ★白名单类型缺字段 → TS 报错 |
| 18 | `frontend/src/features/chat/services/sseParser.ts` | 前端解析 | `onAuthorizationRequired({...})` 白名单补 `trust_impact: rawData.trust_impact` | ★**第 1 层丢字段 → 永不入 Store** |
| 19 | `frontend/src/features/chat/hooks/useAuthorization.ts` | 前端映射 | `newRequest` 补 `trustImpact: pendingAuthorization.trust_impact ?? 'low'` | ★**第 2 层丢 → 拿不到** |
| 20 | `frontend/src/components/AuthorizationModal/index.tsx` | 前端视图 | `SAFETY_LEVEL_CONFIG` 补 4 分类；`AuthorizationRequest` 增 `trustImpact?`；**渲染信任影响行 + 临时授权说明 + 系统禁区说明** | ★**无 UI + TS 报错** |
| 21 | `app/api/v1/tool_routes.py` | 注释订正 | `:45` 注释提及 `requires_confirmation` → 同步改名（**仅注释，无代码**） | 注释与代码不一致，误导后人 |
| 22 | `app/services/agent/steps/base.py` | 核对不动 | `:134`/`:148` **kwargs 透传** → `trust_impact` 自动进 `to_dict()`，无需加字段 | （防误改） |
| 23 | `frontend/src/features/chat/streams/chatStreamTransport.ts` | 核对不动 | `:917` `d.pendingAuthorization = { ...data }` spread 不丢字段 | （防误改，见反例警示） |

> `frontend/src/types/execution.ts:162` 的 `severity?: 'info'｜'warn'｜'error'` 属 `MetaStep` SSE 分级（见 §二 E 类），同样核对不动，未计入本表。

**★ 前端白名单三连坑**：后端 paused 帧的 `trust_impact` 要穿过
`sseParser.ts:959`（**对象字面量白名单**）→ `chatStreamTransport.ts:917`（spread，不丢）
→ `useAuthorization.ts:79`（**对象字面量白名单**）→ `AuthorizationRequest`。
**两个白名单层任一漏改 → 字段静默丢弃**，后端改得再对前端也不显示。

**★ 附带查明的历史事实**：这两层白名单里**从来就没有 `severity`** —— 后端 paused 帧一直白发 `severity`，前端压根没接。精确印证 [39]原案 §1.4「`severity` 前端不读」，根因更具体：**不是没人读，是转换层从未映射过**；且其值域 `safe/risk/dangerous` 与 `types/execution.ts:162` 声明的 `'info'｜'warn'｜'error'` **根本不匹配**，属跨层类型不一致缺陷。

### 6.1 `app/tools/tool_types.py` — 删 `severity`、增 `safety_level`、改名 `needs_confirm`

```diff
@@ -140,30 +140,31 @@
 @dataclass
 class SafetyResult:
     """安全检查结果 — 替代raw dict — 小欧 2026-06-25
     # 修复: 删 is_safe 死字段(无人消费) — 小欧 2026-07-18
     # ⑮2026-08-10: 新增 auth_path(白名单外临时授权路径, None=普通确认/无)
+    # 2026-10-18 小欧(文档本文):
+    #   ①删 severity —— 危险等级与 blocked/needs_confirm 重复编码([39]原案§1.7), 且沙箱判定是自证循环(见§五.4)。
+    #     ★严禁改成空值保留: :195 会恒 False 且不报错 → sandbox_required 永不置位 → 沙箱预检静默失效(§四.1硬约束一)。
+    #   ②增 safety_level —— 问题来源分类, 产地由"扫 message 文本"归位到"决策点直给"。
+    #   ③requires_confirmation 缩短命名 needs_confirm(纯内部字段, 不进 paused 帧/DB/前端, 对外契约零影响)。
+    #     ★严禁留旧名别名(property/兼容), 违反"禁止 backward"且会留两份真源(§四.1硬约束二)。
+    #   ★勿与 MetaStep.severity(info/warn/error, 另一个类的 SSE 分级) 混同 —— 见本文§二。
     逐字复制自 app/tools/security/safety_result.py:20, 字段/默认值零改动 ——
     下游均按 kwarg 构造, 丢一个字段即 TypeError。
     """
     blocked: bool = False
-    requires_confirmation: bool = False
+    needs_confirm: bool = False        # 原 requires_confirmation(2026-10-18 小欧 缩短命名)
     message: str = ""
-    severity: str = "safe"
+    safety_level: str = ""             # 问题来源分类: path_auth/shellparam/command_block/tool_delete/
+                                       #   tool_write/data_guard/unregistered/forbidden_zone/tool_execute
     auto_confirm: bool = False
     auth_path: Optional[str] = None
     # v1.25 M1: 沙箱预检触发标记 — 由 path_tool_safety_checker 四条置位路径点亮,
     #   action_handler(M3) 仅对 sandbox_required=True 的工具调用 SandboxExecutor.pre_execute;
     #   缺省 False 不改变既有安全流(非破坏性工具不进沙箱预检, 保性能)
     sandbox_required: bool = False
 
     @staticmethod
     def pass_result() -> "SafetyResult":
         """放行结果工厂(每次新建实例, 防共享单例被下游改写) — 小欧 2026-10-17(三线/通道统一放行)
 
         供 path_legality_router / dual_path_check / shell_path_check 复用, 免三份拷贝与循环导入。
         """
-        return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=False, needs_confirm=False, message="")
```

### 6.2 `app/safety/temp_auth.py` — **新增单一真源函数**（v1.8 按 DRY 修正）

> ★ **v1.8 DRY 合规修正**：v1.7 的 `resolve_grant_recursive` 内部重复了 `grant_temp_auth:48` 的
> 「空/根路径」判定。**该判定是安全关键分支**（防 `Path("")` resolve 成 cwd 而扩域成整盘授权），
> 两处并存必然产生"改一处漏一处"的分歧风险。故按铁规 **DRY + 复用优先**，上提为私有原子 `_is_rejectable_root`。

```diff
@@ -38,6 +38,33 @@

+def _is_rejectable_root(root) -> bool:
+    """空/根路径判定(授权拒绝线) — 单一真源 — 小欧 2026-10-18 文档[39]
+
+    判定为真表示**不可授权**: 空串 / None / Path("").resolve() 会落 cwd 扩域 /
+    "." / "/" 等根路径。上提原因: grant_temp_auth(拒绝+告警) 与 resolve_grant_recursive
+    (影响面判定) 共用同一口径, 防两处分歧。
+    """
+    return (not root) or (isinstance(root, str) and root.strip() in ("", ".", "/"))
+
+
+def resolve_grant_recursive(root: str, requested: bool = True) -> bool:
+    """给定授权根, 判定**实际生效**的 recursive —— 授予自由度真值源(单一真源) — 小欧 2026-10-18 文档[39]
+
+    规则(自 grant_temp_auth 内联逻辑上提, 与 2026-09-03 小欧修复同源):
+      文件路径(Path(root).suffix 非空) → False(仅精确路径)
+      目录路径(suffix 为空)           → True(整棵子目录树)
+
+    ★为何必须上提: 本函数是"授权写入"与"授权影响面判定(trust_impact)"的**唯一共用口径**。
+      两处若各自判 suffix 必然漂移 —— 授权按目录给了整子树, 影响面却按单文件显示"小", 误导用户。
+
+    Args:
+        root: 授权根路径
+        requested: 调用方请求的 recursive(grant_temp_auth 入口参数); False 时不授权递归
+    Returns:
+        bool: 实际生效的 recursive
+    """
+    if not requested or _is_rejectable_root(root):
+        return False
+    return not bool(Path(root).suffix)
+
+
 def grant_temp_auth(root: str, recursive: bool = True) -> None:
@@ -46,12 +73,12 @@
-    # 2026-09-03 小欧 修复: 空/根路径前置拒绝（Path("").resolve()得cwd扩域根治）
-    if not root or (isinstance(root, str) and root.strip() in ("", ".", "/")):
+    # 2026-09-03 小欧 修复: 空/根路径前置拒绝（Path("").resolve()得cwd扩域根治）
+    # 2026-10-18 小欧(文档[39]): 判定上提 _is_rejectable_root, 与 resolve_grant_recursive 共用同一口径(DRY)
+    if _is_rejectable_root(root):
         from app.logger import logger as _lg
         _lg.warning(f"[temp_auth] 空/根路径拒绝授权: {root!r}")
         return
-    # 2026-09-03 小欧 修复: 文件路径(有后缀)强制recursive False，仅目录保持True，防task级目录越权
-    _recursive = recursive
-    if recursive and isinstance(root, str) and Path(root).suffix:
-        _recursive = False
+    # 2026-10-18 小欧(文档[39]): suffix 规则上提 resolve_grant_recursive, 与 trust_impact 判定共用口径
+    _recursive = resolve_grant_recursive(root, recursive)
     _ensure_auth()[Path(root).resolve()] = _recursive
@@ -119,5 +146,5 @@
 __all__ = ["grant_temp_auth", "clear_temp_auth", "is_temp_authorized",
-           "get_authorized"]
+           "get_authorized", "resolve_grant_recursive"]
```

> ✅ **等价性保证**：`_is_rejectable_root` 是 `grant_temp_auth:48` 原条件的**逐字提取**（`not root or (isinstance(root,str) and root.strip() in ("", ".", "/"))`），
> 零逻辑变更；`resolve_grant_recursive` 在 `requested=False` 时返回 `False`（等同原 `_recursive = recursive = False`），
> 在 `requested=True` 且路径有后缀时返回 `False`（等同原 `_recursive = False`），
> 在 `requested=True` 且目录时返回 `True`（等同原 `_recursive = True`）。**行为完全不变，纯等价重构**。

### 6.3 `app/services/agent/handlers/safety_gate.py` — 字段优先 + 文本兜底 + trust_impact 真派生

```diff
@@ -88,6 +88,20 @@
 
+def _resolve_trust_impact(auth_path: Optional[str]) -> str:
+    """授权/信任影响面(英文标识 high/low; 前端映射中文显示) — 小欧 2026-10-18 文档本文
+
+    真值源 = temp_auth **实际生效** 的 recursive(本次授权到底给了 Agent 多大自由度):
+      high = 目录根授权 → 整个子目录树均可操作(影响面大)
+      low  = 单文件授权 → 仅该精确路径(影响面小)
+
+    ★与 needs_confirm 正交: 是否弹窗问用户, 与授权后有多大自由度, 是两回事, 互不推导。
+      (v1.0~v1.4 曾误写成 needs_confirm 的 relabel, 零信息量 = 重犯[39]原案§1.7 所批的重复编码, 已修正)
+    ★复用 temp_auth.resolve_grant_recursive 而非自判有无后缀 —— 保证与实际授权写入同一口径。
+    """
+    if not auth_path:
+        return "low"
+    from app.safety.temp_auth import resolve_grant_recursive   # 延迟import防环
+    return "high" if resolve_grant_recursive(auth_path) else "low"
+
+
 def _classify_safety_level(msg: str, tool_name: str) -> str:
@@ -195,8 +209,8 @@
             # 3.2/3.2.1 只读短路: shell 只读白名单(含新增五项)的 requires_confirmation 不进网关,
             #   恒与真机放行并行(仍落 site③ 走沙箱只读直通), 仅收敛"只读也弹窗"的过宽 — 小欧-2026-09-18
-            _readonly = (safety_result.requires_confirmation
+            _readonly = (safety_result.needs_confirm
                          and is_shell_tool(_cn)
                          and is_shell_readonly_whitelisted(str(_cp.get("command") or "")))
-            if safety_result.requires_confirmation and not _readonly:
+            if safety_result.needs_confirm and not _readonly:
                 # [5] 确认 — 信任预查移入本层(与"是否免确认"同层, SRP)。
+            if safety_result.needs_confirm and not _readonly:
@@ -251,7 +265,11 @@
                     _msg = getattr(safety_result, "message", "")
-                    _sl = _classify_safety_level(_msg, _cn)
+                    # 2026-10-18 小欧(文档本文): 产地归位但**不删本函数** ——
+                    #   有 safety_level 直读(治文本承重); 空则扫文本兜底。
+                    #   兜底不可删: execute_sql/create_task 等由 tool_meta.needs_confirmation 触发的确认,
+                    #   不经路径安全检查、无 SafetyResult.message 可扫, 删之则 safety_level 恒空。
+                    _sl = getattr(safety_result, "safety_level", "") or _classify_safety_level(_msg, _cn)
@@ -261,7 +279,9 @@
                     _verdict = await hitl_confirm(agent, ConfirmSpec(
                         auto_confirm=_bypass, tool_name=_cn, params=_cp,
                         content=_content,
-                        severity=getattr(safety_result, "severity", ""),
+                        # 2026-10-18 小欧(文档本文§五.3): 授权影响面按 auth_path 实际 recursive 判定, 非 needs_confirm 派生
+                        trust_impact=_resolve_trust_impact(getattr(safety_result, "auth_path", None)),
                         safety_level=_sl,
```

### 6.4 `app/services/agent/handlers/hitl_gateway.py` — ConfirmSpec 正名（**不动 MetaStep.severity**）

```diff
@@ -38,8 +38,9 @@
     path: Optional[str] = None
     content: str = ""
-    severity: str = ""           # 安全分级: safe / risk / dangerous
+    trust_impact: str = ""       # 授权/信任影响面: high(目录根授权, 整棵子树) / low(单文件授权, 仅精确路径);
+                                  #   真值源 temp_auth 实际生效的 recursive; 非危险等级(已由 blocked/needs_confirm 承载)
     safety_level: str = ""       # 问题来源分类: path_auth / shellparam / command_block / tool_delete / tool_execute / data_guard / unregistered / forbidden_zone
     auto_confirm: bool = False
 
@@ -108,7 +109,7 @@
     paused = agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="paused",
         content=spec.content, confirm_id=confirm_id, tool_name=spec.tool_name,
         params=_desensitize(_summarize_params(spec.tool_name, spec.params)),
-        severity=spec.severity,
+        trust_impact=spec.trust_impact,
         safety_level=spec.safety_level, trust_path=_path, auto_confirm=_auto,
         confirm_timeout=_ct, backend_timeout=_bt))
@@ -126,7 +127,7 @@
     if auth.get("confirmed") or (spec.auto_confirm and auth.get("expired")):
         resumed = agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="resumed",
-            content=f"已确认执行: {spec.tool_name}", severity="info", confirm_id=confirm_id))
+            content=f"已确认执行: {spec.tool_name}", severity="info", confirm_id=confirm_id))  # ★MetaStep.severity(info) 属 SSE 分级, 不动
```

### 6.5 `app/services/agent/handlers/sandbox_gate.py` — ConfirmSpec 正名（禁区不传影响面）

```diff
@@ -147,7 +147,7 @@
         return ConfirmSpec(
             auto_confirm=False, tool_name=tool_name, params=params,
             content=f"该路径在系统禁区，禁止访问: {path}",
-            severity="risk", safety_level="path_auth")
+            # 2026-10-18 小欧(文档本文§五.3): 系统禁区**永不授权** → 无授权被授予 → 无"授权影响面"可言
+            #   → 不传 trust_impact, 前端判空不渲染该行; 只显示"系统禁区不可授权", 免误导用户以为可授权。
+            safety_level="path_auth")
```

### 6.6 `app/safety/write_path_check.py` — **措辞补齐** + 置 `safety_level` + 改名

```diff
@@ -112,15 +112,18 @@
     _ok, _msg, _category = validate_write(path)
     if _ok:
-        return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=False, needs_confirm=False, message="", safety_level="path_auth")
     if _category == "system":
-        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
-                            severity="dangerous")
+        # blocked 分支不塞 trust_impact(等价关系: dangerous→blocked=True 已表达大影响, [39]原案§1.6第3步)
+        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
+                            safety_level="forbidden_zone")
     if _category == "non_system":
+        # 2026-10-18 小欧(文档本文§一.1-7): 措辞补齐 —— 原句缺"临时"二字, 用户看不出这是任务级临时授权
-        return SafetyResult(requires_confirmation=True, blocked=False,
-                            message=f"该路径在受保护区域，写入需申请授权: {path}",
-                            severity="risk", auth_path=path)
+        return SafetyResult(needs_confirm=True, blocked=False,
+                            message=f"该路径在受保护区域，写入需申请临时授权: {path}",
+                            auth_path=path, safety_level="path_auth")
+    # 2026-10-18 小欧(文档本文): 措辞补齐 —— 补时效, 让用户知道仅本任务有效、任务结束自动失效
-    return SafetyResult(requires_confirmation=True, blocked=False,
-                        message=f"该路径超出允许范围，需临时授权: {path}",
-                        severity="risk", auth_path=path)
+    return SafetyResult(needs_confirm=True, blocked=False,
+                        message=f"该路径超出允许范围，需临时授权（仅本任务有效，任务结束自动失效）: {path}",
+                        auth_path=path, safety_level="path_auth")
```

### 6.7 `app/safety/read_path_check.py`

```diff
@@ -98,6 +98,6 @@
     _ok, _msg, _category = validate_read(path)
     if not _ok:
-        return SafetyResult(blocked=True, message=_msg, severity="dangerous")
-    return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=True, message=_msg, safety_level="path_auth")
+    return SafetyResult(blocked=False, needs_confirm=False, message="", safety_level="path_auth")
```

### 6.8 `app/safety/delete_path_check.py` — 7 处

```diff
@@ -136,14 +136,14 @@
         logger.warning(f"[delete_path_check] 路径归一化失败, 按拒绝处理: {path!r} ({e})")
-        return SafetyResult(blocked=True, requires_confirmation=False,
-                            message=f"删除路径非法: {path}", severity="dangerous")
+        return SafetyResult(blocked=True, needs_confirm=False,
+                            message=f"删除路径非法: {path}", safety_level="tool_delete")
@@ -143,7 +143,7 @@
         logger.warning(f"[delete_path_check] 允许根读取失败, 按拒绝处理: {e}")
-        return SafetyResult(blocked=True, requires_confirmation=False,
-                            message=f"删除安全判定不可用(根集读取失败): {e}", severity="dangerous")
+        return SafetyResult(blocked=True, needs_confirm=False,
+                            message=f"删除安全判定不可用(根集读取失败): {e}", safety_level="tool_delete")
@@ -150,12 +150,12 @@
     if (not inside_proj) and recursive:
-        return SafetyResult(blocked=True, message=f"禁止删除工作区外目录: {path}", severity="dangerous")
+        return SafetyResult(blocked=True, message=f"禁止删除工作区外目录: {path}", safety_level="tool_delete")
     if (inside_proj and recursive) or (not inside_proj):
-        return SafetyResult(requires_confirmation=True, blocked=False,
-                            message=f"删除需确认: {path}", severity="risk")
+        return SafetyResult(needs_confirm=True, blocked=False,
+                            message=f"删除需确认: {path}", safety_level="tool_delete")
-    return SafetyResult(blocked=False, requires_confirmation=False,
-                        message="", severity="safe")
+    return SafetyResult(blocked=False, needs_confirm=False,
+                        message="", safety_level="tool_delete")
@@ -200,11 +200,11 @@
     _guard = guard_forbidden_delete(path)
     if _guard:
-        return SafetyResult(blocked=True, message=_guard, severity="dangerous")
+        return SafetyResult(blocked=True, message=_guard, safety_level="forbidden_zone")
@@ -206,3 +206,3 @@
     if not _ok and _category:
-        return SafetyResult(blocked=True, message=_msg, severity="dangerous")
+        return SafetyResult(blocked=True, message=_msg, safety_level="forbidden_zone")
```

### 6.9 `app/safety/dual_path_check.py` — **4 处属性读取 + 2 处构造**

```diff
@@ -120,7 +120,7 @@   # write 动作取严
             if result.blocked or result.blocked:
                 return result
@@ -122,1 +122,1 @@
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
                 return result
@@ -125,3 +125,3 @@   # dual 未带路径参数 → 硬拦
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="tool_delete",
                                 message=f"工具 {tool_name} 声明为 dual 但调用不带任何路径参数")
@@ -137,1 +137,1 @@   # read 动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
                 return result
@@ -142,1 +142,1 @@   # 系统源外泄拦截
-                return SafetyResult(blocked=True, severity="dangerous", message=msg)
+                return SafetyResult(blocked=True, safety_level="forbidden_zone", message=msg)
@@ -149,1 +149,1 @@   # delete 动作取严
-            if _perm.blocked or _perm.requires_confirmation:
+            if _perm.blocked or _perm.needs_confirm:
@@ -153,1 +153,1 @@   # move/其它动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
```

> ★ 4 处属性读取（`:122`/`:137`/`:149`/`:153`）v1.6 才补入，漏改则 `AttributeError`。

### 6.10 `app/safety/shell_path_check.py` — **3 处属性读取 + 6 处构造**（行号已按 Python 权威重校）

> ★★ **v1.7 行号错误已作废**：v1.7 曾用 PowerShell 把本文件行号"校正"为 `62,83,99,127,137,151`，**该组数据全错**。
> 根因：本项目 `.py` 为 **utf-8-sig + LF 换行**，`Select-String`/`Get-Content` 对该文件行数计算错误
> （实测 PowerShell 报 161 行内的行号时序错位；`path_tool_safety_checker.py` 更离谱：PowerShell 报 247 行，Python 权威 **294 行**）。
> **v1.8 起全部行号以 Python 读取为准**（铁律：本项目禁用 PowerShell 统计行号）。
>
> **Python 权威（总行 161）**：构造点 `64 / 85 / 101 / 129 / 139 / 154`；属性读取点 `74 / 88 / 142`。
> 本文件 6 处构造**均不含 `requires_confirmation` kwarg**（只含 `severity=`），故只需删 severity + 加 safety_level，**无需 kwarg 改名**。

```diff
@@ -64,1 +64,1 @@    # 动作判定非法路径(构造)
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="command_block",
@@ -74,1 +74,1 @@    # ★属性读取 cwd 写线
-            if perm.requires_confirmation:
+            if perm.needs_confirm:
@@ -85,1 +85,1 @@    # 构造
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="command_block",
@@ -88,1 +88,1 @@    # ★属性读取 动作取严
-            if not (result.blocked or result.requires_confirmation):
+            if not (result.blocked or result.needs_confirm):
@@ -101,1 +101,1 @@  # 构造
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="command_block",
@@ -129,1 +129,1 @@  # 构造 command 类型非法
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="command_block",
@@ -139,1 +139,1 @@  # 构造 cwd 含元字符
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level="command_block",
@@ -142,1 +142,1 @@  # ★属性读取 动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
@@ -154,1 +154,1 @@  # 构造 高危删除无法解析目标
-        return SafetyResult(blocked=True, severity="dangerous",
+        return SafetyResult(blocked=True, safety_level="command_block",
```

> ★ **本文件是本方案改动最密集的文件（9 处）**，且历史上被重构多次，行号务必落码时**现场复核**，勿照抄本文档数字。

### 6.11 `app/safety/shell_danger_command.py`

```diff
@@ -90,5 +90,5 @@
         return SafetyResult(
             blocked=True,
             message=f"高风险Shell操作: {desc}，已阻止执行",
-            severity="dangerous",
+            safety_level="command_block",
         )
```

### 6.12 `app/safety/shell_command_risk.py`

```diff
@@ -120,6 +120,6 @@
         return SafetyResult(
             blocked=False,
-            requires_confirmation=True,
+            needs_confirm=True,
             message=f"中风险Shell操作: {combined}，需确认后执行",
-            severity="risk",
+            safety_level="shellparam",
         )
```

### 6.13 `app/safety/path_legality_router.py`

```diff
@@ -115,5 +115,5 @@
-        return SafetyResult(blocked=True, severity="dangerous", message=f"路径安全检查异常: {e}")
+        return SafetyResult(blocked=True, safety_level="command_block", message=f"路径安全检查异常: {e}")
```

### 6.14 `app/safety/path_tool_safety_checker.py` — **沙箱判定改读 `needs_confirm`**（核心）

```diff
@@ -143,7 +143,7 @@
         if tool_meta is None:
-            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}", severity="dangerous")
+            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}", safety_level="unregistered")
@@ -193,7 +193,9 @@
-            known_risk.sandbox_required = (known_risk.severity == "risk")   # risk 级授权请求→沙箱预检
+            # 2026-10-18 小欧(文档本文§五.4): 沙箱判定改读 needs_confirm ——
+            #   原 (severity == "risk") 在 severity 删除后必崩, 且本就是 needs_confirm 的自证循环([39]原案§1.7)。
+            #   此处 known_risk 已排除 blocked(:186), 恒为需确认的授权请求 → 恒等, 行为不变。
+            # ★★ 本行是"严禁把 severity 留空字段"的决定性理由: 若 severity 留空, 本行不报错而恒 False
+            #   → sandbox_required 永不置位 → sandbox_gate:79 短路 → 沙箱预检静默失效(§四.1硬约束一)。
+            known_risk.sandbox_required = known_risk.needs_confirm
             return known_risk
@@ -205,7 +207,7 @@
                     -                    return SafetyResult(requires_confirmation=True, auto_confirm=True,
-                            blocked=False, message="",
-                            severity="risk", sandbox_required=True)   # v1.25 M2-A: bypass risk 确认→沙箱预检
+                    return SafetyResult(needs_confirm=True, auto_confirm=True,
+                            blocked=False, message="",
+                            safety_level="tool_execute", sandbox_required=True)   # v1.25 M2-A: bypass 需确认→沙箱预检
@@ -209,5 +211,4 @@
             -            return SafetyResult(requires_confirmation=False,
-                    blocked=False, message="安全开关已绕过",
-                    severity="safe")   # v1.25 M2-A: safe 级 bypass 不触发沙箱(与 G1 一致)
+            return SafetyResult(needs_confirm=False,
+                    blocked=False, message="安全开关已绕过")   # v1.25 M2-A: 无需确认的 bypass 不触发沙箱(与 G1 一致)
+                    blocked=False, message="安全开关已绕过")
@@ -216,13 +217,12 @@
                 if not custom_result.get("is_safe", True):
                     return SafetyResult(
                         blocked=True,
                         message=custom_result.get("message", "安全检查未通过"),
-                        severity=custom_result.get("severity", "dangerous"),
                     )
@@ -225,4 +225,3 @@
                 return SafetyResult(blocked=True,
-                        message=f"安全检查异常，已阻止执行: {e}",
-                        severity="dangerous")
+                        message=f"安全检查异常，已阻止执行: {e}")
@@ -229,10 +228,9 @@
         needs_confirm, _shell_msg = self._get_needs_confirmation(tool_meta, params or {})
-        severity = "risk" if needs_confirm else "safe"
-        # v1.25 M2-C: 仅 risk 级触发沙箱(与 G1 唯一触发依据一致); safe 级不进预检
-        return SafetyResult(requires_confirmation=needs_confirm,
-                blocked=False, message=_shell_msg or "", severity=severity,
-                sandbox_required=(severity == "risk"))
+        # v1.25 M2-C: 仅需确认级触发沙箱(与 G1 唯一触发依据一致); 免确认不进预检
+        # 2026-10-18 小欧(文档本文§五.4): 删 severity 中间变量(自证循环), 沙箱直读 needs_confirm
+        return SafetyResult(needs_confirm=needs_confirm,
+                blocked=False, message=_shell_msg or "",
+                sandbox_required=needs_confirm)
@@ -243,5 +242,9 @@
         if self_kill is not None:
-            return self_kill
+            return SafetyResult(blocked=True, message=self_kill.message, safety_level="command_block")
+@@ -279,1 +282,1 @@   # ★v1.6 补: _check_known_risks 汇总判定(属性读取)
+-        if risk.blocked or risk.requires_confirmation:
++        if risk.blocked or risk.needs_confirm:
 ```

> ⚠️ `:221` 的 `custom_result.get("severity", "dangerous")` 是**外部 `tool_meta.check_fn` 返回 dict 的键**，属第三方契约，**不动**；只是不再把它灌进 `SafetyResult`（`blocked=True` 已表达大影响）。
> **注**：`data_guard` 在当前生产代码已无产地（旧「写入大小保护」逻辑已随重构删除），前端配置保留仅为契约完整，见 §四.4。

### 6.15 `frontend/src/features/chat/streams/backupTypes.ts` — 前端类型源

```diff
@@ -21,11 +21,12 @@
 export interface PendingAuthorizationPayload {
   confirm_id: string;
   tool_name: string;
   params?: Record<string, unknown>;
   content?: string;
   safety_level?: string;
+  trust_impact?: 'high' | 'low';   // 授权/信任影响面(2026-10-18 小欧 文档本文); high=目录根授权整子树 / low=单文件授权
   trust_path?: string | null;
   auto_confirm?: boolean | string | number;
   confirm_timeout?: number | string;
   backend_timeout?: number | string;
 }
```

### 6.16 `frontend/src/features/chat/services/sseParser.ts` — 第 1 层白名单

```diff
@@ -958,12 +958,13 @@
           case 'paused':
             onPaused?.(rawData.confirm_id as string | undefined);
             if (rawData.confirm_id) {
               handlers.onAuthorizationRequired?.({
                 confirm_id: rawData.confirm_id,
                 tool_name: rawData.tool_name,
                 params: rawData.params,
                 content: rawData.content ?? '',
                 safety_level: rawData.safety_level,
+                // 2026-10-18 小欧(文档本文§6.0★白名单三连坑): 补 trust_impact ——
+                //   此处是**对象字面量白名单**, 不显式列出的字段直接丢弃。
+                //   漏本行 → 字段止步解析层, 永不入 Store, 前端拿不到。
+                trust_impact: rawData.trust_impact,
                 trust_path: rawData.trust_path ?? null,
```

### 6.17 `frontend/src/features/chat/hooks/useAuthorization.ts` — 第 2 层白名单

```diff
@@ -82,6 +82,9 @@
         content: pendingAuthorization.content ?? '',
         safetyLevel: pendingAuthorization.safety_level ?? 'unknown',
+        // 2026-10-18 小欧(文档本文§6.0★白名单三连坑): raw→camel 映射补 trustImpact ——
+        //   此处同样是**对象字面量白名单**; 漏本行则 AuthorizationRequest 拿不到, 弹窗无"信任影响"行。
+        //   缺省 'low': 系统禁区场景后端不传(见 §五.3), 判空不渲染该行。
+        trustImpact: pendingAuthorization.trust_impact ?? 'low',
         // 2026-09-03 小欧 D2-10: normalizeAutoConfirm四态归一(true/'true'/1/'1')
         autoConfirm:
```

### 6.18 `frontend/src/components/AuthorizationModal/index.tsx` — 视图（补 4 分类 + 类型 + 三行说明）

```diff
@@ -109,11 +109,12 @@
 export interface AuthorizationRequest {
   confirmId: string;
   toolName: string;
   params: Record<string, unknown>;
   content?: string;
   safetyLevel: string;
+  trustImpact?: 'high' | 'low';   // 授权/信任影响面(2026-10-18 小欧 文档本文)
   trustPath?: string | null;
@@ -131,6 +132,12 @@
 const SAFETY_LEVEL_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
   path_auth: { color: 'orange', label: '需授权', icon: <WarningOutlined /> },
   shellparam: { color: 'orange', label: '命令确认', icon: <ExclamationCircleOutlined /> },
   tool_write: { color: 'geekblue', label: '写确认', icon: <EditOutlined /> },
   tool_delete: { color: 'red', label: '删除确认', icon: <StopOutlined /> },
   tool_execute: { color: 'volcano', label: '执行确认', icon: <ExclamationCircleOutlined /> },
+  // 2026-10-18 小欧(文档本文): 补齐 4 个此前缺失的分类 ——
+  //   决策点直给 safety_level 后这 4 值必然出现, 原表查不到 → 弹窗无标签/样式退化
+  forbidden_zone: { color: 'red', label: '系统禁区', icon: <StopOutlined /> },
+  command_block: { color: 'red', label: '危险命令', icon: <StopOutlined /> },
+  data_guard: { color: 'orange', label: '数据保护', icon: <WarningOutlined /> },
+  unregistered: { color: 'volcano', label: '未注册', icon: <WarningOutlined /> },
 };
```

**三条独立说明行（挂在 `content` 之外，规避 `WebkitLineClamp:2` 截断）**：

```tsx
{/* ① 授权影响面: 英文标识映射中文显示(后端为主, 前端只呈现不做权限判断) */}
{request?.trustImpact && (
  <div style={{ marginTop: 4 }}>
    <Text type="secondary">
      信任影响：{request.trustImpact === 'high' ? '大（整个目录及其子目录）' : '小（仅此路径）'}
    </Text>
  </div>
)}

{/* ② 临时授权时效: temp_auth 是任务级 ContextVar, 任务结束自动失效 */}
{safetyLevel === 'path_auth' && (
  <div style={{ marginTop: 8, marginBottom: 4 }}>
    <Text type="secondary" style={{ fontSize: 12 }}>
      临时授权仅本任务有效，任务结束自动失效；与下方"信任此操作"（会话级）是两套机制
    </Text>
  </div>
)}

{/* ③ 系统禁区永不授权 —— [39]原案§1.6第4步 */}
{safetyLevel === 'forbidden_zone' && (
  <div style={{ marginTop: 8, marginBottom: 4 }}>
    <Text type="secondary" style={{ fontSize: 12 }}>
      系统禁区不可授权
    </Text>
  </div>
)}
```

### 6.19 `app/services/tool/tool_facade.py` — 下游消费点（v1.5 漏，v1.6 补）

```diff
@@ -171,7 +171,7 @@
     # 2026-10-15 小欧 - 文档[33] 5.21(P3缺口): 按 requires_confirmation 分支处理未注册(硬拒)与确认(走弹窗)两种形态,
-    if safety.requires_confirmation and not safety.auto_confirm:
+    if safety.needs_confirm and not safety.auto_confirm:
         ...
```

### 6.20 `app/tools/fundamental/execute_shell_command.py` — 下游消费点（v1.5 漏，v1.6 补）

```diff
@@ -1135,7 +1135,7 @@
-    if safety.requires_confirmation:
+    if safety.needs_confirm:
         ...
```

### 6.21 `app/api/v1/tool_routes.py` — 仅注释订正（无代码改动）

```diff
@@ -45,1 +45,1 @@
-    #   blocked/requires_confirmation/auth_path 属"拦截"/"待确认"两态, 不落库不污染对话框消息
+    #   blocked/needs_confirm/auth_path 属"拦截"/"待确认"两态, 不落库不污染对话框消息
```

### 6.22 核对不修改（防误改）

| 文件 | 行 | 理由 |
|------|----|------|
| `app/services/agent/steps/base.py` | 134, 148 | `MetaStep` 是 **kwargs 透传**（`self._kwargs = kwargs` / `_extra_fields()` 返回 `dict(self._kwargs)`）→ `trust_impact` 自动进 `to_dict()`，**无需加字段定义**。反例警示：若有人改成显式字段制，必须同步加，否则暂停帧静默丢字段 |
| `frontend/src/features/chat/streams/chatStreamTransport.ts` | 917 | `d.pendingAuthorization = { ...data }` spread 不丢字段。反例警示：若"顺手重构"成对象字面量白名单，必须同步补 `trust_impact` |
| `frontend/src/types/execution.ts` | 162 | `severity?: 'info'｜'warn'｜'error'` 属 `MetaStep` SSE 分级，与本次无关 |

---

## 七、影响面清单（实测全量，2026-10-18）

### A 类：`SafetyResult` 字段与工厂

| 文件 | 行 | 动作 |
|------|----|------|
| `app/tools/tool_types.py` | 152 | 删 `severity` 定义；`requires_confirmation` → `needs_confirm`；增 `safety_level` |
| `app/tools/tool_types.py` | 166 | `pass_result()` 同步三处 |

### B 类：`SafetyResult(...)` **构造点（24 处）** + 属性读取（12 处，见 C 类）

> v1.6 起本表**明确区分「构造 kwarg」与「属性读取」** —— 前者加 `safety_level`/改 kwarg 名，后者只改属性名，两类漏改后果同为 `AttributeError` 但改法不同。
> 构造点实测 **24** 处（此前误记 26，因 `dual_path_check` 的 4 处 `result.requires_confirmation` 是**读取**而非构造）。

| 文件 | 构造 | 读取 | 置 `safety_level` |
|------|------|------|----------------|
| `read_path_check.py` | 2 | 0 | `path_auth` |
| `write_path_check.py` | 4 | 0 | `path_auth`×3 / `forbidden_zone` |
| `delete_path_check.py` | 7 | 0 | `tool_delete`×5 / `forbidden_zone`×2 |
| `dual_path_check.py` | 2 | **4** | `tool_delete` / `forbidden_zone` |
| `shell_path_check.py` | 6 | **3** | `command_block` |
| `shell_danger_command.py` | 1 | 0 | `command_block` |
| `shell_command_risk.py` | 1 | 0 | `shellparam` |
| `path_legality_router.py` | 1 | 0 | `command_block` |
| `path_tool_safety_checker.py` | 7 | **2** | `unregistered` / `tool_execute`×2 / —×3 / `command_block` |
| `safety_gate.py` | 0 | **2** | （编排层，不产 SafetyResult） |
| `tool_facade.py` | 0 | **1** | （下游消费） |
| `execute_shell_command.py` | 0 | **1** | （下游消费） |
| **合计** | **24** | **12** | — |
| `path_legality_router.py` | 1 | `command_block` |
| `path_tool_safety_checker.py` | 7 | `unregistered` / `tool_execute`×2 / —×3 / `command_block` |

### C 类：`requires_confirmation` **属性读取点（12 处）** —— 改名后 `AttributeError`，★最高优先

> 正则 `\s*:` 会误匹 `if ...:` 的冒号，故此处**以 `\.requires_confirmation`（属性访问）为准**逐条实测。

| # | 文件 | 行 | 代码 | 所在分支 |
|---|------|----|------|---------|
| 1 | `dual_path_check.py` | **122** | `if result.blocked or result.requires_confirmation:` | write 动作 |
| 2 | `dual_path_check.py` | **137** | `if result.blocked or result.requires_confirmation:` | read 动作 |
| 3 | `dual_path_check.py` | **149** | `if _perm.blocked or _perm.requires_confirmation:` | delete 动作 |
| 4 | `dual_path_check.py` | **153** | `if result.blocked or result.requires_confirmation:` | move/其它动作 |
| 5 | `path_tool_safety_checker.py` | **195** | `known_risk.sandbox_required = (known_risk.severity == "risk")` | 授权请求（**另需改 severity，见本文档 §六.14**） |
| 6 | `path_tool_safety_checker.py` | **279** | `if risk.blocked or risk.requires_confirmation:` | `_check_known_risks` 汇总判定 |
| 7 | `shell_path_check.py` | **74** | `if perm.requires_confirmation:` | cwd 写线 |
| 8 | `shell_path_check.py` | **88** | `if not (result.blocked or result.requires_confirmation):` | 动作判定取严 |
| 9 | `shell_path_check.py` | **142** | `if result.blocked or result.requires_confirmation:` | 动作判定取严 |
| 10 | `safety_gate.py` | **197** | `_readonly = (safety_result.requires_confirmation` | 只读短路 |
| 11 | `safety_gate.py` | **200** | `if safety_result.requires_confirmation and not _readonly:` | 确认入口 |
| 12 | `tool_facade.py` / `execute_shell_command.py` | **171** / **1135** | `if safety.requires_confirmation ...` | API 直调 / shell 执行 |

> ★ **v1.6 漏记 7 处**：#1~#4（`dual_path_check`）、#6（`path_tool_safety_checker:279`）、#7~#9（`shell_path_check`）。
> 根因：前几版按"文件"归类统计，把这些文件归入"构造点"类，**未区分同文件内的属性读取**。
> **漏改后果**：这 7 处同样 `AttributeError`，与 #5/#10~#12 同等级，非可选项。
> **对应 diff**：#1~#4 见 §六.9；#6 见 §六.14；#7~#9 见 §六.10。

### D 类：`ConfirmSpec.severity`

| 文件 | 行 | 动作 |
|------|----|------|
| `hitl_gateway.py` | 41 | 字段改名 `trust_impact` |
| `hitl_gateway.py` | 111 | paused 帧改键 |
| `sandbox_gate.py` | 150 | 删 `severity="risk"`，不传 `trust_impact` |

### E 类：`MetaStep.severity`（**严禁改动**，见 §二）

`hitl_gateway.py:129`、`event_emitter.py:65/91/101/111/129`、`react_step.py:370/436/503/545/571`、`react_loop.py:292/328`、`react_inference.py:56`、`handle_answer.py:156`、`handle_action.py:200`、`stream_orchestrator.py:289`、`agent_telemetry.py:294/430`、前端 `types/execution.ts:162`、`error/handler.ts:174` 起全表。

### F 类：前端白名单映射链（**v1.3 漏项，v1.4 补**）

| # | 文件 | 行 | 形式 | 漏改后果 |
|---|------|----|-----------|---------|
| F1 | `streams/backupTypes.ts` | 21-31 | `interface` 逐字段 | TS 报缺字段 |
| F2 | `services/sseParser.ts` | 959-966 | **对象字面量白名单** | ★字段止步解析层 |
| F3 | `hooks/useAuthorization.ts` | 79-98 | **对象字面量白名单** | ★`AuthorizationRequest` 拿不到 |
| F4 | `components/AuthorizationModal/index.tsx` | 109-119 | `interface` | ★无 UI + TS 报错 |
| — | `streams/chatStreamTransport.ts` | 917 | `{ ...data }` spread（不丢） | 无需改 |

### G 类：`needs_confirm` 改名影响面（**按性质三分**，v1.7 实测重做）

> **v1.7 口径修正**：v1.6 只给"总处数/文件数"，掩盖了「构造 kwarg」与「属性读取」的**改法差异**。
> 本版按三类分列，落码时逐类对照。

| 类别 | 处数 | 改法 | 漏改后果 |
|------|------|------|---------|
| **① 属性读取** `X.requires_confirmation` | **12** | 直接改名 | `AttributeError` |
| **② 构造 kwarg** `requires_confirmation=` | **15** | 改名 **+** 加 `safety_level` | `TypeError`（未改名）/ 弹窗无标签（漏加） |
| **③ 字段定义** `requires_confirmation: bool` | **1** | 改名 | 不改则 ①②全部失效 |
| **④ 编辑历史注释** | 32 | 仅**功能注释**改名，历史注释保留 | 注释与代码不一致，误导后人 |

**① 属性读取 12 处**（明细见 §七 C 类）

| 文件 | 行号 |
|------|------|
| `dual_path_check.py` | 122, 137, 149, 153 |
| `path_tool_safety_checker.py` | 195(同时改 severity), 279 |
| `shell_path_check.py` | 74, 88, 142 |
| `safety_gate.py` | 197, 200 |
| `tool_facade.py` | 171 |
| `execute_shell_command.py` | 1135 |

**② 构造 kwarg 15 处**：分布 `shell_path_check`(6) / `delete_path_check`(7) / `write_path_check`(4) / `read_path_check`(2) / `dual_path_check`(2) / `shell_command_risk`(1) / `shell_danger_command`(1) / `path_legality_router`(1) / `path_tool_safety_checker`(7) 等，明细见 §六 各节 diff。

★★ **该字段并非「纯后端内部」—— v1.7 结论已作废（v1.8 关联审查推翻）**：
pp/api/v1/tool_routes.py:23 
rom dataclasses import asdict、:64 safety=asdict(_sf)，
说明 **SafetyResult 会被 sdict() 整体转 dict，作为 /tool/execute 的 API 响应字段 safety 返回**。
故改名 
equires_confirmation → 
eeds_confirm **确属对外 API 契约变更**。
- 本项目**前端零消费**（实测 
rontend/src 全量 grep 无命中），前端无感；
- 但**第三方调用方若读 safety.requires_confirmation 将失效**。
- 按铁规「禁止 backward」，**不做旧名兼容**，但必须在发布说明中记明该契约变更。
**增量成本≈0**：② 类所在文件本就需重写 `SafetyResult` 构造行，改 kwarg 名不增加 diff 体积。
⚠️ `path_tool_safety_checker.py:230` 已有**局部变量** `needs_confirm`，改名后同行成 `SafetyResult(needs_confirm=needs_confirm, ...)` —— 合法不冲突（kwarg 名 vs 变量名），但可读性下降，建议局部变量保持 `needs_confirm` 不动即可。

**★ 校验命令（v1.7 定版，替代 v1.6 的单条 grep）**：
```powershell
cd backend
# ① 属性读取（应 12 行，全部需改名）
Get-ChildItem app -Recurse -Filter *.py | Select-String '\.requires_confirmation' | Where-Object { $_.Line -notmatch '^\s*#' }
# ② 构造 kwarg（应 15 行）
Get-ChildItem app -Recurse -Filter *.py | Select-String 'requires_confirmation=' | Where-Object { $_.Line -notmatch '^\s*#' }
# ③ 字段定义（应 1 行）
Get-ChildItem app -Recurse -Filter *.py | Select-String 'requires_confirmation\s*:' | Where-Object { $_.Line -notmatch '^\s*#' -and $_.Line -notmatch 'if\s|or\s' }
```

> **v1.5 漏统计的 4 个文件**：`safety_gate.py`(7，含关键读取点 `:197`/`:200`)、`tool_facade.py`(2，`:171` 读取点)、
> `execute_shell_command.py`(1，`:1135` 读取点)、`tool_routes.py`(1，纯注释)。
> **根因**：v1.5 用 PowerShell `Select-String -Path "app\**\*.py"`，PS 5.1 下 `**` **不递归**，只扫了一层目录。
> **教训**：影响面统计**禁用非递归 glob**，必须用 `Get-ChildItem -Recurse` 或 `rg`。
>
> **其中真正的代码读取点共 4 处**（改字段后会 `AttributeError`）：
> `path_tool_safety_checker.py:195`、`safety_gate.py:197`、`safety_gate.py:200`、`tool_facade.py:171`、`execute_shell_command.py:1135`。
>
> 该字段**纯后端内部**：不进 paused 帧、不落 DB、不出前端 → **对外契约零影响**。
> 增量成本≈0：上述 14 文件中 10 个本就需重写 `SafetyResult` 构造行，改 kwarg 名不增加 diff 体积。
> ⚠️ `path_tool_safety_checker.py:230` 已有**局部变量** `needs_confirm`，改名后同行成 `SafetyResult(needs_confirm=needs_confirm, ...)` —— 合法不冲突（kwarg 名 vs 变量名），但可读性下降，建议局部变量保持 `needs_confirm` 不动即可。
>
> **历史注释例外**：编辑历史注释里另有 5 处提及 `requires_confirmation`
> （`safety_gate.py:11/31/195/299/358`、`tool_facade.py:19`、`tool_routes.py:45`）。
> 按铁规「编辑型内容禁止删除历史版本信息」，**这些注释保留原字样**，但**功能注释须改名**（见 §6.22）。

---

## 八、实施顺序

| 批次 | 内容 | 文件 | 依赖 |
|------|------|------|------|
| 批一 | `SafetyResult` 删 `severity` + 改名 `needs_confirm` + 增 `safety_level` | `tool_types.py` | 无 |
| 批二 | **C 类读取点 + 全部代码点 kwarg 改名**（含沙箱判定改读 `needs_confirm`） | `path_tool_safety_checker.py`, `safety_gate.py`, `tool_facade.py`, `execute_shell_command.py` | 批一（**必须同批，否则中间态崩**） |
| 批三 | B 类构造点补 `safety_level` + kwarg 改名 + 措辞补齐 | 8 个 safety 文件 | 批一 |
| 批四 | `temp_auth.resolve_grant_recursive` 上提 + `safety_gate._resolve_trust_impact` 新增 | `temp_auth.py`, `safety_gate.py` | 批二 |
| 批五 | D 类 `ConfirmSpec` 正名 | `hitl_gateway.py`, `sandbox_gate.py` | 批二 |
| 批六 | 注释订正（功能注释改名，历史注释保留） | `tool_routes.py` | 批二 |
| 批七 | **前端 F 类白名单链（F1→F2→F3，缺一即静默丢字段）** | `backupTypes.ts`, `sseParser.ts`, `useAuthorization.ts` | 批五 |
| 批八 | 前端视图：`SAFETY_LEVEL_CONFIG` 补 4 分类 + `AuthorizationRequest` 补 `trustImpact` + 渲染三行说明 | `index.tsx` | 批七 |
| 批九 | 端到端验证 + 全量 pytest + `npm run check:full` | — | 全部 |

---

## 九、验收标准

1. `SafetyResult` 类体内无 `severity` 字段行
2. `grep -rn "SafetyResult(.*severity=" backend/app` 零匹配
3. **`requires_confirmation` 在代码中零残留** —— 校验命令（**排除编辑历史注释**，注释按铁规保留原字样）：
   ```powershell
   Get-ChildItem -Path app -Recurse -Filter *.py | Select-String -Pattern "requires_confirmation" | Where-Object { $_.Line -notmatch '^\s*#' }
   ```
   期望：**零输出**。若输出非空，说明仍有代码点未改名（会 `AttributeError`）。
4. `grep -rn "\.severity == \"risk\"" backend/app` 零匹配
5. `grep -rn 'severity = "risk" if' backend/app` 零匹配
6. 沙箱判定改读 `needs_confirm`（`:195` 与 `:233-235`），行为等价不变
7. `blocked=True` 构造点均不带 `trust_impact`
8. `_classify_safety_level` **保留**且仅作兜底
9. `MetaStep.severity` 站点（E 类）**零改动**
10. `resolve_grant_recursive` 被 `grant_temp_auth` 与 `_resolve_trust_impact` **两处共用**（单一真源）
11. `trust_impact` 值域仅 `high`/`low`（英文标识），中文仅出现在前端显示层
12. `sandbox_gate.py:150` 不传 `trust_impact`
13. `SAFETY_LEVEL_CONFIG` 覆盖 9 个 `safety_level` 值
14. 弹窗显示「信任影响：大（整个目录及其子目录）」／「小（仅此路径）」
15. `path_auth` 显示「临时授权仅本任务有效…与信任此操作是两套机制」
16. `forbidden_zone` 显示「系统禁区不可授权」
17. 写线 `non_system` 文案含「临时」二字
18. 写线白名单外文案含「仅本任务有效」
19. 三条说明均为独立 DOM 行，未追加进 `content`
20. `pytest` 全量通过（含 HITL / safety / p1 / p2 / 路径守卫）
21. `npm run check:full` 通过（**含 `typecheck` 与 `typecheck:e2e`**——本方案改 TS 契约）
22. **端到端验证**：`trust_impact` 经 F1→F2→F3→F4 四层后，`request.trustImpact` 非空（白名单静默丢弃唯一定位手段，静态检查抓不到）
23. `grep -n "trust_impact\|trustImpact" frontend/src` 应命中 4 个文件，少一处即断链

---

## 十、风险与回滚

| 风险 | 影响 | 缓解 |
|------|------|------|
| 批一/批二不同批落地 | C 类读取点 `AttributeError`/`TypeError`，服务不可用 | 强制同批原子提交 |
| 全局替换误改 `MetaStep.severity` | SSE 分级丢失，前端错误通道与样式退化 | 按 §二/§七 E 类逐点排除，禁全局替换 |
| `needs_confirm` 改名留了兼容别名 | 新旧两套真源，违反禁止 backward | 验收 #3（排除注释后零输出） |
| **影响面统计用非递归 glob 漏文件** | **v1.5 实际发生**：漏 4 文件 / 11 处，含 3 个关键读取点 | 全量统计一律用 `Get-ChildItem -Recurse`；验收 #3 用递归命令 |
| `tool_facade`/`execute_shell_command` 读取点漏改 | 直调 API 与 shell 确认路径 `AttributeError` | 已补入批二 + §6.0 清单 #15/#16 |
| diff 内残留 `requires_confirmation=` kwarg | `TypeError: unexpected keyword argument` | 验收 #3；落码时逐 diff 对照 |
| 局部变量 `needs_confirm` 与 kwarg 同名致误读 | 可读性下降 | 局部变量保持不动；`path_tool_safety_checker:230` 同名合法 |
| `trust_impact` 判定口径漂移 | 授权给了整子树却显示"小" | `resolve_grant_recursive` 单一真源 + 验收 #10 |
| 前端白名单层漏改 | 后端正确但前端无显示 | 验收 #22 端到端 + #23 grep 计数 |
| 措辞改动打破既有断言 | 测试失败 | 措辞仅改 message，grep 受影响测试后同步 |
| `sandbox_gate` 误传 `trust_impact` | 禁区场景误导用户以为可授权 | 验收 #12 |

---

## 十一、[39]原案 逐条落位对照表

| [39]原案 章节 | [39]原案 结论 | 本文落位 | 状态 |
|---------|----------|---------|------|
| §1.3 事实1 | `safety_level` 产地错（扫文本） | §四.1 + §六.3 + §六.6~6.14 | ✅ 采纳 |
| §1.3 事实2 | `content` 被 `WebkitLineClamp:2` 截断 | §六.18 独立 DOM 行 | ✅ 采纳 |
| §1.3 事实3 | `temp_auth` 是后端任务级不变式 | §六.6/§六.18 只描述不改语义 | ✅ 采纳 |
| §1.3 事实4 | `sandbox_gate` 已直接置位（范式） | §六.5 | ✅ 采纳（订正：置的是 `ConfirmSpec` 非 `SafetyResult`） |
| §1.4 结论1 | `safety_level` 字段没问题，只是产地错 | §四.1 + §六.3 | ✅ 采纳 |
| §1.4 结论2 | `severity` 正名 `trust_impact` | §五.3 真影响面（非改名 relabel） | 🔄 **深化**（[39]原案 只说正名，未给判定真源；本文补 `recursive` 真值源） |
| §1.4 注 | 不新增 `reason_code` | 全文 | ✅ 采纳 |
| §1.5 E | 复用现有字段 + 前端合成 | 全文 | ✅ 采纳 |
| §1.6 第1步 | `SafetyResult` 增 `safety_level`；**删** `_classify_safety_level` | 增字段 ✅；删函数 ❌→**改兜底**（§六.3，理由：无 message 场景会失分类） | 🔄 修正 |
| §1.6 第2步 | `severity` → `trust_impact`，前端改读 | §五.3 + §六.3/6.4/6.5 + §6.15~6.18 | ✅ 采纳 |
| §1.6 第3步 | 沙箱判定改读 `requires_confirmation` | §五.4 + §六.14 | ✅ 采纳 |
| §1.6 第3步 | blocked 分支不再塞 severity | §七 B 类 + §六各处 | ✅ 采纳 |
| §1.6 第4步 | 前端显示信任影响 + 临时授权说明 + 系统禁区说明，独立一行 | §六.18 | ✅ 采纳 |
| §1.6 第5步 | 措辞补齐 | §六.6 | ✅ 采纳 |
| §1.7 | 危险等级等价关系（重复编码） | §四.2 | ✅ 采纳 |
| §1.7 | 「自证循环」判断 | §五.4 实测复核 `:231-235` **成立** | ✅ 采纳 |
**版面签名**：本文由小欧于 2026-10-18 13:45:00 修订至 **v1.9（按令删除第十二章）**。