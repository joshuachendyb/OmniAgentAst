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
| v1.10 | 2026-10-18 14:12:30 | 小欧 | **按 AGENTS.md 新增铁规「注释+编辑历史只能有技术术语和逻辑信息，严禁插入文档号章节号 bug号 评审\会审信息」清理全文 diff 注释**：扫描代码块内 `#` 注释与 docstring，**改写 17 处**（§6.1 类注释 3 / §6.2 docstring 与注释 4 / §6.3 docstring 与注释 2 / §6.5 注释 1 / §6.6 注释 2 / §6.14 注释 4 / §6.14 末注 1）。**清理内容**：删除 `文档[39]`、`文档本文`、`§一.1-7`、`§五.3`、`§五.4`、`§四.1`、`[39]原案§1.7`、`[39]原案§1.6第3步` 等文档号与章节号，以及引用裁定来源的措辞。**保留内容**：日期 + 署名 + 技术术语 + 逻辑因果（如"原 (severity == 'risk') 在 severity 删除后必崩, 且本就是 needs_confirm 的自证循环""恒等, 行为不变"），**信息零损失**。复扫结果：代码块内注释/docstring 违规残留 **0**。文档正文中的章节号引用与版本历史**不在本次清理范围**（属文档结构，非代码注释） |
| v1.11 | 2026-10-18 16:59:55 | 小欧 | **全量对齐本地已落码（老陈令：文档与代码不一致的修正文档，欠账的做完）**。三堂会审逐 diff 核查后确认 13 处文档与实际代码矛盾 + 4 项代码已改而文档无记载，逐项订正：①**字段层路径**：v1.0~v1.10 全篇按 `app/tools/tool_types.py` 描述，实际契约已回迁 `app/safety/safety_result.py`（§四.1/§6.1/§七 A 类/§八 批一 同步）；②**`trust_impact` 值域**：v1.5 定的 `high`/`low`（真值源 `temp_auth.resolve_grant_recursive`，即目录树 vs 单文件）已被老陈裁定推翻为 **`high`/`medium`/`low`**（真值源 `safety_level`，即删除类/写入类/其余）——原设计下"删一个文件"与"写一个文件"同为 `low`，删的不可撤销性完全没体现（§四.3/§五.3/§一.1-3/验收 #10/#11/§十 同步）；③**`safety_level` 取值**：v1.0 的 9 值表全部作废，实际为 `SafetyLevel` 枚举 **确认 13 + 硬拦 4**，无一与旧表重合（§四.4/§6.18/验收 #13 同步）；④**`_classify_safety_level`**：v1.5~v1.10 反复论证"必须保留作兜底"，实际**已整体删除**——各判定点直给后无任何调用点，且其扫描的关键词（"受保护区域"/"超出允许范围"）已随文案术语统一全部改写，函数自身亦成死代码（§一.1-6/§六.3/§6.9~6.14/验收 #8/§十一 同步）；⑤**§6.8 delete R4/R5**：v1.0 方案写 `if (inside_proj and recursive) or (not inside_proj)` 合并分支，实际已拆为 R4（根集内递归）/R5（根集外）两条 —— 合并写法会把允许根内**单文件**删除误判为需确认（该缺陷已实测复现并修复），且 R5 **必须补 `auth_path`**：缺它则 `safety_gate` 的 `grant_temp_auth` 被跳过，弹窗承诺"申请临时授权"而授权从未落地（实测确认后 `validate_delete` 仍拒绝，删线是死路）；⑥**放行不带标签**：v1.0 方案给放行结果也挂 `safety_level="path_auth"`，实际**一律留空** —— 无确认无拦截就无"分类"可言，且读线从不确认，原标签把放行与硬拦都叫成"需授权"；⑦**`sandbox_gate`**：`path_auth` 已不在枚举内，改 `SafetyLevel.BLOCK_COMMAND`（沙箱裁决属命令级预检，与路径授权无关）；⑧**§6.2 `resolve_grant_recursive`**：v1.8 立"两端共用"单一真源，实际随 `trust_impact` 改判已**仅 `grant_temp_auth` 自身调用**，共用前提不成立；⑨~⑬ 各产码点标签逐个订正为枚举成员。**新增四章记录文档无载的已落码事项**：`SafetyLevel` 枚举单源、`rename` 源判为写（含 `parse_move` 动词表拆分与沙箱宽表并入）、目录术语统一（允许根集 vs 白名单是两个不同集合）、三堂会审发现的既有安全缺口。**§八 实施顺序与 §九 验收标准按落码现状重排** |

---

**创建时间**：2026-10-18 12:12:51
**更新时间**：2026-10-18 16:59:55（小欧）
**编写人**：小欧

---

## 一、本文与 [39]原案 的关系

| 文档 | 定位 |
|------|------|
| [39]原案 | **原始方案**：问题诊断 + 候选落点评估 + 一步到位结论 |
| 本文（本文） | **实施方案**：完整采纳 [39]原案 全部核心设计 + 按代码现态修正 3 处缺陷 + 逐文件 diff |

[39]原案 的历史结论**不删除**。§四 逐条列出 [39]原案 核心设计及落位，§十一 给出 [39]原案 每一条到本文的完整对照。

### 一.1 核心结论（定案）

1. **`SafetyResult.severity` 整体删除**，不改名为 `trust_impact`。
2. **危险等级等价关系**（[39]原案 §1.7）为唯一表达：`blocked`（拦截）／`needs_confirm`（需确认）／两者皆 False（放行）。
3. **`trust_impact` 承载真授权影响面**，值域**英文标识** `high`/`medium`/`low`，真值源 = `safety_level`（删除类→`high`／写入类→`medium`／其余→`low`）；**与 `needs_confirm` 正交**，不互推。
   - ★ **v1.11 订正**：v1.0~v1.10 定为 `high`/`low`、真值源 `temp_auth.resolve_grant_recursive`（目录树 vs 单文件）。实测该口径下「删一个文件」与「写一个文件」同为 `low`，**删除的不可撤销性完全没体现**，用户无法据此判断该不该勾信任。老陈裁定改为**按操作性质分三档**。
4. **沙箱判定改读 `needs_confirm`**（[39]原案 §1.6 第3步）——**必采纳**，是删 `severity` 的硬依赖。
5. **字段缩短命名**：`requires_confirmation` → `needs_confirm`（14 文件，增量成本≈0）。★**该字段经 `tool_routes.asdict` 出到 `/tool/execute` API 响应，属对外契约变更**（v1.8 关联审查推翻 v1.7 的「纯后端内部」结论，详见 §四.1 与 §十三）。
6. **`safety_level` 产地归位**：决策点直给，**`_classify_safety_level` 整体删除**。
   - ★ **v1.11 订正**：v1.5~v1.10 反复论证「兜底不可删，理由：无 message 场景会失分类」。实际**已删**，理由三条：①各判定点直给后**无任何调用点**（`execute_sql`/`create_task` 等经 `_TOOL_CONFIRM_LEVEL` 已在产码点直给，不再留空）；②该函数扫描的关键词（`受保护区域`/`超出允许范围`）已随目录术语统一**全部改写**，命中集为空；③它正是「标签取决于文案怎么写」这个病根本身——文案一改分类就悄悄变。
7. **措辞补齐**：白名单外补时效、`non_system` 补"临时"二字。
   - ★ **v1.11 扩充**：目录术语全量统一为系统既有命名——**允许根集**（`get_allowed_roots`＝项目根+授权目录+会话工作区）与**白名单**（`get_default_allowed_paths`＝系统临时目录+项目根+授权目录+会话工作区）是**两个不同集合**，差一个「系统临时目录」，删线按前者、写线按后者，措辞不得混用（详见新增 §四.5）。
8. **前端补齐 13 个确认标签 + 三条独立说明行**（信任影响／临时授权时效／系统禁区不可授权）。
   - ★ **v1.11 订正**：v1.0 写「补齐 4 个缺失分类」（基于旧 9 值表）。实际改为 `SafetyLevel` 枚举后，确认命名空间 **13 个**、硬拦命名空间 **4 个**，前端 `SAFETY_LEVEL_CONFIG` 键集须与确认命名空间**完全相等**。

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
| 1 | `SafetyResult.severity` | `app/safety/safety_result.py`（★v1.11 订正，原写 `app/tools/tool_types.py`） | `safe`/`risk`/`dangerous` | **删除** |
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

### 四.1 `SafetyResult`（**`app/safety/safety_result.py`**）

> ★ **v1.11 订正**：v1.0~v1.10 全篇写 `app/tools/tool_types.py`。实际契约已**回迁安全层** `app/safety/safety_result.py` —— 生产者（三线判定、shell 通道、总闸）全在 `app/safety/` 内，契约随生产者走，落在安全层即免去用工具层模块迁就安全语义。`tool_types.py` 现仅保留 `ToolMetadata` 等工具层类型。

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

> ★ **v1.11 订正**：v1.5 定为 `high`/`low`，真值源 `temp_auth.resolve_grant_recursive`（目录树 vs 单文件）。老陈裁定改为**按操作性质分三档**，真值源改为 `safety_level`。原口径的缺陷：删一个文件与写一个文件同为 `low`，**删除的不可撤销性未被体现**。

| 值 | 中文显示 | 含义 | 判定（真值源 = `safety_level`） |
|----|---------|------|------|
| `high` | 授权影响：**大** | **删除类**：抹除不可撤销 | `delete_recursive` / `delete_out_of_scope` |
| `medium` | 授权影响：**中** | **写入类**：可覆写原内容 | `write_protected` / `write_out_of_scope` |
| `low` | 授权影响：**小** | 其余：命令级/任务级/注册表级/SQL 级确认 | 其余全部确认标签 |

**与「授权范围大小」正交**：目录树 vs 单文件由 `trust_path` 单独展示，不在本字段编码——两个维度各自独立回答两个问题（后果多大 / 范围多大），合并即重复编码。

`blocked` 项永不进 HITL（实测 `blocked` 与 `needs_confirm` 无并存），故只有三值，无需第四档。

### 四.4 `safety_level` 取值（`SafetyLevel` 枚举，`app/safety/safety_result.py`）

> ★ **v1.11 全表替换**：v1.0 的 9 值表（`path_auth`/`shellparam`/`tool_write`/`tool_delete`/`tool_execute`/`forbidden_zone`/`command_block`/`data_guard`/`unregistered`）**全部作废**，实际无一重合。原表把「硬拦原因」与「确认原因」混在同一标签空间，而二者在 `safety_gate` 里是**互斥的两条分支**（`if safety_result.blocked:` 直接 rejected 并 `continue`，永不进 HITL；`if safety_result.needs_confirm:` 才进弹窗）。

**标签只回答「为什么」，不回答「怎么办」**——怎么办由 `blocked`/`needs_confirm` 两个布尔精确表达。故拆成两个互斥命名空间，前缀即区分：

**① 确认命名空间（`needs_confirm=True`，唯一有消费者的地方 —— 前端按标签渲染）**

| `safety_level` | 前端标签 | 产地 |
|---------------|---------|------|
| `delete_recursive` | 递归删除确认 | `delete_path_check` R4 |
| `delete_out_of_scope` | 范围外删除授权 | `delete_path_check` R5 |
| `write_protected` | 受保护路径写入授权 | `write_path_check` `non_system` |
| `write_out_of_scope` | 范围外写入授权 | `write_path_check` 白名单外 |
| `shell_medium_risk` | 命令确认（中风险） | `shell_command_risk` |
| `shell_delete_confirm` | 命令含删除动作 | `path_tool_safety_checker` 按命令动作取档 |
| `shell_write_confirm` | 命令含写入动作 | 同上 |
| `shell_read_confirm` | 命令含读取动作 | 同上 |
| `shell_command_confirm` | 命令无路径动作 | 同上 |
| `sql_execute_confirm` | SQL 执行确认 | 工具元数据确认策略 |
| `task_deal_confirm` | 任务处理确认 | 同上 |
| `registry_deal_confirm` | 注册表处置确认 | 同上 |
| `tool_confirm` | 工具级确认（兜底） | 同上 |

**② 硬拦命名空间（`blocked=True`，不进弹窗，标签仅作诊断留痕，前端不消费）**

| `safety_level` | 语义 | 产地 |
|---------------|------|------|
| `path_forbidden` | 路径硬拦：磁盘根／系统保护目录／系统禁区／代码目录／允许根集自身及上级（**R6 根集外递归删除亦归此**，同属路径策略硬拦） | `delete_path_check` / `write_path_check` / `dual_path_check` |
| `block_command` | 危险命令／命令层输入非法／非法 shell 元字符 | `shell_danger_command` / `shell_path_check` / `path_legality_router` / 总闸 check_fn |
| `block_path_invalid` | 路径非法：空值／`..`穿越／归一化失败／安全判定不可用（fail-closed） | `read_path_check` / `delete_path_check` / `dual_path_check` |
| `block_unregistered` | 工具未注册 | 总闸 |

**③ 放行结果一律不带标签（空串）**：无确认无拦截，无「分类」可言。
> v1.0 方案给放行结果也挂 `safety_level="path_auth"`，实际已去掉 —— 读线处处放行却标成「需授权」，是语义倒挂。

**枚举成员清单（`SafetyLevel`）与两个派生集合**：`CONFIRM_LEVELS`（13，前端 `SAFETY_LEVEL_CONFIG` 键集须与其**完全相等**）、`BLOCK_LEVELS`（4）。

### 四.5 目录术语统一（v1.11 新增）

**系统里有两个不同的允许范围集合，措辞不得混用**：

| 集合 | 定义（源码 docstring 原文） | 谁用它 |
|------|--------------------------|--------|
| **允许根集** | `get_allowed_roots` = 项目根 + 授权目录 + 会话工作区 | **删线** `check_delete_risk`（R3~R6） |
| **白名单** | `get_default_allowed_paths` = 系统临时目录 + 项目根 + 授权目录 + 会话工作区 | **写线** `validate_write` |

差一个「系统临时目录」——故同一路径 `Temp\a.txt` **写=放行、删=需确认**，这是设计使然而非缺陷，但**文案必须如实反映各自依据的那个集合**。

**禁用词**（系统无此分类，自造）：
- ~~工作区~~ —— 系统无「工作区」这一级分类（唯一合法用法是「会话工作区」这一具体来源名）
- ~~允许的操作范围~~ —— 无此命名，正确为「允许根集」或「白名单」
- ~~受保护区域~~ —— 无此分类，`non_system` 的真实口径是「代码目录自身及内部子级 + 允许根集自身及上级祖先」
- ~~授权根目录~~ —— 正确为「授权目录」
- ~~系统目录~~（用于 umbrella）—— 正确为「系统保护目录」／「系统禁区」

**系统既有术语表**（取自源码 docstring，非臆造）：磁盘根目录、系统禁区（敏感文件/敏感目录）、系统保护目录、代码目录、项目根、授权目录、会话工作区、允许根集、白名单。

---

## 五、两处判定的实现细则

### 五.2 危险等级等价关系（[39]原案 §1.7）

见 §四.2。落地时只需遵守一条：**blocked 分支不塞任何"等级"字段**，`needs_confirm` 分支不塞 `severity`（已删）。

### 五.3 `trust_impact` 判定（**真值源 = `safety_level`，按操作性质分三档**）

> ★ **v1.11 全面订正**：v1.5 原方案为「真值源 = `temp_auth` 实际生效的 `recursive`」，值域 `high`/`low`。老陈裁定改为按操作性质分档。真值源随之从 `auth_path` 解耦到 `safety_level`。

```python
def _resolve_trust_impact(safety_result) -> str:
    level = getattr(safety_result, "safety_level", "")
    if level in (SafetyLevel.DELETE_RECURSIVE, SafetyLevel.DELETE_OUT_OF_SCOPE):
        return "high"      # 删除类: 抹除不可撤销
    if level in (SafetyLevel.WRITE_PROTECTED, SafetyLevel.WRITE_OUT_OF_SCOPE):
        return "medium"    # 写入类: 可覆写原内容
    return "low"           # 其余: 命令级/任务级/注册表级/SQL 级
```

| 授权请求 | `safety_level` | 授予的自由度 | `trust_impact` |
|---------|---------------|-------------|----------------|
| 递归删除目录 / 删允许根集外路径 | `delete_recursive` / `delete_out_of_scope` | 整棵子树 / 该路径被抹除 | `high` |
| 写代码目录或允许根集自身 / 写白名单外 | `write_protected` / `write_out_of_scope` | 原内容可被覆写 | `medium` |
| 命令 / 任务 / 注册表 / SQL 级确认 | 其余确认标签 | 不直接改文件内容 | `low` |

**为什么不用 `resolve_grant_recursive`**：该口径只答「范围多大」（目录树 vs 单文件），答不了「后果多重」。实测原口径下 `delete_out_of_scope` 授权一个文件与 `write_out_of_scope` 授权一个文件**同为 `low`**，用户无从判断该不该勾信任。两个维度各自回答两个问题，**范围由 `trust_path` 单独展示**，影响面由 `trust_impact` 单独承载，合并即重复编码。

**`sandbox_gate.py` 的特例**：该处是**沙箱裁决**（预检未通过，是否强执行），并未授予任何路径访问权 → 无「授权影响面」可言 → **不传 `trust_impact`**（前端判空不渲染）。
> ★ **v1.11 订正**：v1.0 方案该处传 `safety_level="path_auth"` 且描述为「系统禁区裁决」。两处均已更正——①它是沙箱预检裁决**不是**禁区分类；②`path_auth` 已不在枚举内，现为 `SafetyLevel.BLOCK_COMMAND`。

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

### 6.0 涉及修改的代码清单（**v1.11 重做：26 个文件**）

> ★ **v1.11 变更**：①字段层文件由 `app/tools/tool_types.py` 改为 `app/safety/safety_result.py`；②新增 4 个文件（`shell_parse/parse_move.py`、`shell_parse/parse_shell_action.py`、`shell_sandbox_tables.py`、`path_classify_category.py`）；③新增 `SafetyLevel` 枚举与 `confirm_level_for` 出口。

| # | 文件 | 层 | 修改要点 | 漏改后果 |
|---|------|----|---------|---------|
| 1 | **`app/safety/safety_result.py`** | 字段层 | **删** `severity`；**新增** `safety_level`；**改名** `needs_confirm`；**新增 `SafetyLevel(StrEnum)` + `CONFIRM_LEVELS` + `BLOCK_LEVELS`**；`pass_result()` 同步 | 全部产码点 `severity=` 变 `TypeError`；无枚举则无任何约束 |
| 2 | `app/safety/temp_auth.py` | 产码 | `_is_rejectable_root` 上提；`grant_temp_auth` 改调；`__all__` 补 | 授权拒绝线两处分歧 |
| 3 | `app/safety/path_tool_safety_checker.py` | 总闸 | 构造点补枚举 + kwarg 改名；**沙箱改读 `needs_confirm`**；**新增 `confirm_level_for` / `shell_confirm_level` / `_TOOL_CONFIRM_LEVEL`** | 沙箱预检静默失效；标签全落兜底 |
| 4 | `app/services/agent/handlers/safety_gate.py` | 编排层 | 读取点改 `needs_confirm`；**直读 `safety_level`**；**删除 `_classify_safety_level`**；`_resolve_trust_impact` 改三档按标签取档；`_confirm_payload` 去掉 `tool_name` 形参 | 读取点 `AttributeError`；分类退回扫文本 |
| 5 | `app/services/agent/handlers/hitl_gateway.py` | 编排层 | `ConfirmSpec.trust_impact`（三档）+ paused 帧改键。**`MetaStep.severity="info"` 严禁动** | paused 帧仍带旧键 |
| 6 | `app/services/agent/handlers/sandbox_gate.py` | 编排层 | `trust_impact` **不传**；`safety_level` 改 `BLOCK_COMMAND`；**新增 `SafetyLevel` 导入** | 枚举外值泄漏 + 误导用户 |
| 7 | `app/safety/write_path_check.py` | 产码 | 4 处补枚举；**放行不带标签**；措辞按术语统一 | 弹窗看不出是临时授权 |
| 8 | `app/safety/read_path_check.py` | 产码 | 2 处：**硬拦 `BLOCK_PATH_INVALID` + 放行不带标签** | 读线标签说谎 |
| 9 | `app/safety/delete_path_check.py` | 产码 | **9 处**补枚举；**R4/R5 拆分**；**R5 补 `auth_path`**；文案术语统一 | 根内单文件删被误判确认；授权链断裂 |
| 10 | `app/safety/dual_path_check.py` | 产码 | 2 处补枚举 + 4 处读取改名 | 分类错误 |
| 11 | `app/safety/shell_path_check.py` | 产码 | 6 处补 `BLOCK_COMMAND` | 分类错误 |
| 12 | `app/safety/shell_danger_command.py` | 产码 | 补 `BLOCK_COMMAND` | 分类错误 |
| 13 | `app/safety/shell_command_risk.py` | 产码 | 补 `SHELL_MEDIUM_RISK` | 分类错误 |
| 14 | `app/safety/path_legality_router.py` | 产码 | fail-closed 补 `BLOCK_COMMAND` | 分类错误 |
| 15 | **`app/safety/path_classify_category.py`** | 产码 | 文案术语统一（「会话目录」→「会话工作区」、「允许根目录」→「允许根集」） | 文案与系统分类不符 |
| 16 | **`app/safety/shell_parse/parse_move.py`** | 解析层 | **动词表拆分 `MOVE_VERBS_*` / `RENAME_VERBS_*`**；源档位按动词二分 | shell 侧与工具侧语义不一致 |
| 17 | **`app/safety/shell_parse/parse_shell_action.py`** | 解析层 | 全局早退门补 `SHELL_RENAME_RE` + import | 改名命令绕过全部路径检查 |
| 18 | **`app/safety/shell_sandbox_tables.py`** | 解析层 | `_intent_verb_union()` **并入 `RENAME_VERBS_BY_SHELL`** | ★沙箱宽表丢改名动词 |
| 19 | `app/services/tool/tool_facade.py` | **下游消费** | `:171` 改 `needs_confirm` | ★`AttributeError`，直调 API 确认路径崩 |
| 20 | `app/tools/fundamental/execute_shell_command.py` | **下游消费** | `:1135` 改 `needs_confirm` | ★shell 确认路径崩 |
| 21 | `frontend/src/features/chat/streams/backupTypes.ts` | 前端类型源 | `PendingAuthorizationPayload` 增 `trust_impact?: 'high'\|'medium'\|'low'` | ★白名单类型缺字段 → TS 报错 |
| 22 | `frontend/src/features/chat/services/sseParser.ts` | 前端解析 | `onAuthorizationRequired({...})` 白名单补 `trust_impact` | ★**第 1 层丢字段 → 永不入 Store** |
| 23 | `frontend/src/features/chat/hooks/useAuthorization.ts` | 前端映射 | `newRequest` 补 `trustImpact` | ★**第 2 层丢 → 拿不到** |
| 24 | `frontend/src/components/AuthorizationModal/index.tsx` | 前端视图 | `SAFETY_LEVEL_CONFIG` **换为 13 键**；`AuthorizationRequest` 增 `trustImpact?`；**渲染三行说明** | ★**无 UI + TS 报错 + 走兜底显示英文串** |
| 25 | `app/api/v1/tool_routes.py` | 注释订正 | 注释提及 `requires_confirmation` → 同步改名（**仅注释，无代码**） | 注释与代码不一致 |
| 26 | `app/services/agent/steps/base.py` | 核对不动 | **kwargs 透传** → `trust_impact` 自动进 `to_dict()` | （防误改） |
| — | `frontend/src/features/chat/streams/chatStreamTransport.ts` | 核对不动 | `:917` spread 不丢字段 | （防误改） |
| — | `app/tools/tool_types.py` | 核对不动 | `SafetyResult` 已迁出，此处仅留 `ToolMetadata` 等 | （防误改） |

> `frontend/src/types/execution.ts:162` 的 `severity?: 'info'｜'warn'｜'error'` 属 `MetaStep` SSE 分级（见 §二 E 类），同样核对不动，未计入本表。

**★ 前端白名单三连坑**：后端 paused 帧的 `trust_impact` 要穿过
`sseParser.ts:959`（**对象字面量白名单**）→ `chatStreamTransport.ts:917`（spread，不丢）
→ `useAuthorization.ts:79`（**对象字面量白名单**）→ `AuthorizationRequest`。
**两个白名单层任一漏改 → 字段静默丢弃**，后端改得再对前端也不显示。

**★ 附带查明的历史事实**：这两层白名单里**从来就没有 `severity`** —— 后端 paused 帧一直白发 `severity`，前端压根没接。精确印证 [39]原案 §1.4「`severity` 前端不读」，根因更具体：**不是没人读，是转换层从未映射过**；且其值域 `safe/risk/dangerous` 与 `types/execution.ts:162` 声明的 `'info'｜'warn'｜'error'` **根本不匹配**，属跨层类型不一致缺陷。

### 6.1 `app/safety/safety_result.py` — 删 `severity`、增 `SafetyLevel` 枚举、改名 `needs_confirm`

> ★ **v1.11 订正**：文件路径由 `app/tools/tool_types.py` 改为 `app/safety/safety_result.py`（契约回迁安全层）。
> ★ **v1.11 新增**：`SafetyLevel(StrEnum)` 枚举 —— `safety_level` 由「9 个裸字符串」升级为**类型化闭合枚举**，杜绝再出现枚举外值。

```diff
+from enum import StrEnum
+
+class SafetyLevel(StrEnum):
+    """safety_level 取值单源
+
+    标签只回答"为什么", 不回答"怎么办" —— 怎么办由 blocked / needs_confirm 两个布尔精确表达。
+    据此拆成两个互斥命名空间, 前缀即区分, 两空间永不重叠。
+    """
+    # ── 确认命名空间(进 HITL 弹窗) ──
+    DELETE_RECURSIVE = "delete_recursive"
+    DELETE_OUT_OF_SCOPE = "delete_out_of_scope"
+    WRITE_PROTECTED = "write_protected"
+    WRITE_OUT_OF_SCOPE = "write_out_of_scope"
+    SHELL_MEDIUM_RISK = "shell_medium_risk"
+    SHELL_DELETE_CONFIRM = "shell_delete_confirm"
+    SHELL_WRITE_CONFIRM = "shell_write_confirm"
+    SHELL_READ_CONFIRM = "shell_read_confirm"
+    SHELL_COMMAND_CONFIRM = "shell_command_confirm"
+    SQL_EXECUTE_CONFIRM = "sql_execute_confirm"
+    TASK_DEAL_CONFIRM = "task_deal_confirm"
+    REGISTRY_DEAL_CONFIRM = "registry_deal_confirm"
+    TOOL_CONFIRM = "tool_confirm"       # 未细分域的工具级确认(诚实兜底: 不谎称是命令/写/删)
+    # ── 硬拦命名空间(不进弹窗) ──
+    PATH_FORBIDDEN = "path_forbidden"
+    BLOCK_COMMAND = "block_command"
+    BLOCK_PATH_INVALID = "block_path_invalid"
+    BLOCK_UNREGISTERED = "block_unregistered"
+
+
+CONFIRM_LEVELS = frozenset({...13 个...})   # 前端 SAFETY_LEVEL_CONFIG 键集须与其完全相等
+BLOCK_LEVELS = frozenset({...4 个...})
+
 @dataclass
 class SafetyResult:
     """安全检查结果 — 替代raw dict — 小欧 2026-06-25"""
     blocked: bool = False
-    requires_confirmation: bool = False
+    needs_confirm: bool = False        # 原 requires_confirmation 缩短命名
     message: str = ""
-    severity: str = "safe"
+    safety_level: str = ""             # 取值必须取自 SafetyLevel; 空串=放行(无确认无拦截, 无分类可言)
     auto_confirm: bool = False
     auth_path: Optional[str] = None
     sandbox_required: bool = False

     @staticmethod
     def pass_result() -> "SafetyResult":
         """放行结果工厂(每次新建实例, 防共享单例被下游改写)"""
-        return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=False, needs_confirm=False, message="")
```

> ★ **`safety_level` 类型收紧**：字段声明仍为 `str`（`StrEnum` 是 `str` 子类，JSON 序列化与 `asdict` 输出不变，对外契约零影响），但**所有产码点必须传枚举成员**，禁止裸字符串——枚举外的值等于分类失效。
> ★ 枚举外的值可通过一条断言锁死：`safety_level == "" or safety_level in CONFIRM_LEVELS | BLOCK_LEVELS`。

### 6.2 `app/safety/temp_auth.py` — `_is_rejectable_root` 上提（**共用前提已消失**）

> ★ **v1.11 订正**：v1.5~v1.10 立此节的前提是「`resolve_grant_recursive` 由 `grant_temp_auth` 与 `_resolve_trust_impact` **两端共用**」。`trust_impact` 改判后（§五.3），**`_resolve_trust_impact` 已不再调用它** —— 该函数现**仅被 `grant_temp_auth` 自身调用**，属授权写入侧的私有判定。
> `_is_rejectable_root` 的上提**仍然保留**：空/根路径判定是安全关键（防 `Path("")` resolve 成 cwd 而扩域成整盘授权），上提使「拒绝授权」与「判定 recursive」在同一文件内共用同一判据，是纯等价重构、零逻辑变更。

```diff
+def _is_rejectable_root(root) -> bool:
+    """空/根路径判定(授权拒绝线) — 单一判据 — 小欧 2026-10-18
+
+    判定为真表示**不可授权**: 空串 / None / Path("").resolve() 会落 cwd 扩域 /
+    "." / "/" 等根路径。上提原因: grant_temp_auth(拒绝+告警) 与 resolve_grant_recursive
+    (recursive 判定) 共用同一口径, 防两处分歧。
+    """
+    return (not root) or (isinstance(root, str) and root.strip() in ("", ".", "/"))
+
+
+def resolve_grant_recursive(root: str, requested: bool = True) -> bool:
+    """给定授权根, 判定**实际生效**的 recursive — 小欧 2026-10-18
+
+    规则(自 grant_temp_auth 内联逻辑上提, 与 2026-09-03 小欧修复同源):
+      文件路径(Path(root).suffix 非空) → False(仅精确路径)
+      目录路径(suffix 为空)           → True(整棵子目录树)
+    """
+    if not requested or _is_rejectable_root(root):
+        return False
+    return not bool(Path(root).suffix)
+
+
 def grant_temp_auth(root: str, recursive: bool = True) -> None:
-    if not root or (isinstance(root, str) and root.strip() in ("", ".", "/")):
+    if _is_rejectable_root(root):          # 判定上提, 与 resolve_grant_recursive 共用口径
         from app.logger import logger as _lg
         _lg.warning(f"[temp_auth] 空/根路径拒绝授权: {root!r}")
         return
-    _recursive = recursive
-    if recursive and isinstance(root, str) and Path(root).suffix:
-        _recursive = False
+    _recursive = resolve_grant_recursive(root, recursive)
     _ensure_auth()[Path(root).resolve()] = _recursive
```

> ✅ **等价性保证**：`_is_rejectable_root` 是原条件的**逐字提取**，零逻辑变更；`resolve_grant_recursive` 在 `requested=False` / 路径有后缀 / 目录三种情形分别等价于原 `_recursive` 的 `False` / `False` / `True`。**行为完全不变，纯等价重构**。

### 6.3 `app/services/agent/handlers/safety_gate.py` — 直读 `safety_level` + **删除**关键词兜底 + `trust_impact` 按标签归类

> ★ **v1.11 全面订正**：v1.3~v1.10 反复论证「`_classify_safety_level` **保留**作兜底，理由：无 message 场景会失分类」。实际**整体删除**，理由三条：
> ①**无调用点** —— `execute_sql`/`create_task`/`registry_*` 等无 message 的确认场景，已在 `path_tool_safety_checker.confirm_level_for()` 按工具名直给标签，不再留空等上层回填；
> ②**关键词已全部失效** —— 该函数扫 `受保护区域`/`超出允许范围`/`删除需确认` 等中文串，而这几处文案已随目录术语统一与 R4/R5 拆分**全部改写**，命中集为空；
> ③**它就是病根本身** —— 「标签取决于文案怎么写」，改一个字悄悄换一个分类。本次重构的全部目的就是消灭这条链。

```diff
+def _resolve_trust_impact(safety_result) -> str:
+    """授权/信任影响面(high/medium/low; 前端映射中文显示) — 小欧 2026-10-18
+
+    取档真值源是 safety_level: 删除类=high / 写入类=medium / 其余=low。
+    与 needs_confirm 正交: 弹不弹窗与同意后后果多大是两回事, 互不推导。
+    与授权范围大小(目录树/单文件)也正交: 范围由 trust_path 单独展示。
+    blocked 项永不进 HITL, 故只有三值。
+    """
+    level = getattr(safety_result, "safety_level", "")
+    if level in (SafetyLevel.DELETE_RECURSIVE, SafetyLevel.DELETE_OUT_OF_SCOPE):
+        return "high"
+    if level in (SafetyLevel.WRITE_PROTECTED, SafetyLevel.WRITE_OUT_OF_SCOPE):
+        return "medium"
+    return "low"
+
+
-def _classify_safety_level(msg: str, tool_name: str) -> str:
-    _sl = "tool_execute"                       # 默认
-    if "系统禁区" in msg:            _sl = "forbidden_zone"
-    elif "受保护区域" in msg or "超出允许范围" in msg: _sl = "path_auth"
-    elif "高风险Shell" in msg or "系统保护进程" in msg: _sl = "command_block"
-    elif "中风险Shell" in msg:       _sl = "shellparam"
-    elif "删除需确认" in msg or "禁止删除" in msg: _sl = "tool_delete"
-    elif "数据保护" in msg:          _sl = "data_guard"
-    elif "安全检查异常" in msg or "安全检查未通过" in msg: _sl = "command_block"
-    elif not msg: ...                            # 按工具名二次归属
-    return _sl

 def _confirm_payload(safety_result, group_size: int):
     """组装确认弹窗所需的原因句 / 分类 / 授权影响面"""
     msg = getattr(safety_result, "message", "")
-    _sl = getattr(safety_result, "safety_level", "") or _classify_safety_level(msg, tool_name)
+    level = getattr(safety_result, "safety_level", "")   # 直读, 不再兜底反查
     content = ...
-    return msg, _sl, _resolve_trust_impact(getattr(safety_result, "auth_path", None)), content
+    return msg, level, _resolve_trust_impact(safety_result), content
```

> ★ **`_confirm_payload` 的 `tool_name` 形参同步删除**（删除兜底后已无人使用，YAGNI），调用点由 `_confirm_payload(safety_result, _cn, _group_size)` 改为 `_confirm_payload(safety_result, _group_size)`。

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

### 6.5 `app/services/agent/handlers/sandbox_gate.py` — 沙箱裁决标签改 `block_command`

> ★ **v1.11 订正**：v1.0 方案此处传 `safety_level="path_auth"`，并把它描述成「系统禁区裁决」。两处均错——①它是**沙箱预检裁决**（问「预检未通过，是否强执行」），与禁区分类无关；②`path_auth` 已不在 `SafetyLevel` 枚举内，留着就是**枚举外值泄漏**。

```diff
     return ConfirmSpec(
         auto_confirm=_sb, tool_name=tool_name, params=params,
         content=f"预检未通过：{pre.blocked_reason.split(' | ', 1)[0] or '无法通过有效预检'}，是否允许直接执行{tool_name}？",
         # 沙箱裁决弹窗不传 trust_impact —— 此处问的是"预检未通过, 是否强执行",
         #   并未授予路径访问权(无授权路径可判影响面), 传值会误导用户以为确认即获得该路径权限。
-        safety_level="path_auth")
+        safety_level=SafetyLevel.BLOCK_COMMAND)   # 沙箱裁决属命令级预检未通过, 非路径授权
```

### 6.6 `app/safety/write_path_check.py` — 标签拆分 + **放行不带标签** + 术语统一

> ★ **v1.11 三处订正**：①放行结果**不带标签**（v1.0 挂 `path_auth`）；②`non_system`（代码目录/允许根集自身及上级）与白名单外是**两种不同成因**，标签必须拆开（v1.0 两者同为 `path_auth`）；③文案按 §四.5 术语统一。

```diff
     _ok, _msg, _category = validate_write(path)
     if _ok:
-        return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=False, needs_confirm=False, message="")   # 放行: 无确认无拦截, 无分类可言
     if _category == "system":
-        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
-                            severity="dangerous")
+        return SafetyResult(blocked=True, message=f"该路径在系统禁区，禁止访问: {path}",
+                            safety_level=SafetyLevel.PATH_FORBIDDEN)
     if _category == "non_system":
-        return SafetyResult(requires_confirmation=True, blocked=False,
-                            message=f"该路径在受保护区域，写入需申请授权: {path}",
-                            severity="risk", auth_path=path)
+        # non_system 真实口径 = 代码目录自身及内部子级 + 允许根集自身及上级祖先
+        return SafetyResult(needs_confirm=True, blocked=False, auth_path=path,
+                            message=f"该路径位于代码目录(含其内部子级)或允许根集内的根目录自身及其上级，"
+                                    f"写入需申请临时授权(仅本任务有效): {path}",
+                            safety_level=SafetyLevel.WRITE_PROTECTED)
-    return SafetyResult(requires_confirmation=True, blocked=False,
-                        message=f"该路径超出允许范围，需临时授权: {path}",
-                        severity="risk", auth_path=path)
+    # 此处判据集 = 白名单(系统临时目录 + 项目根 + 授权目录 + 会话工作区),
+    #   与上面 non_system 的"允许根集"不是同一集合, 差一个"系统临时目录" → 措辞必须写"白名单"
+    return SafetyResult(needs_confirm=True, blocked=False, auth_path=path,
+                        message=f"该路径不在白名单内(白名单=系统临时目录/项目根/授权目录/会话工作区)，"
+                                f"写入需申请临时授权(仅本任务有效，任务结束自动失效): {path}",
+                        safety_level=SafetyLevel.WRITE_OUT_OF_SCOPE)
```

### 6.7 `app/safety/read_path_check.py` — 读线从不确认，`path_auth` 是误标

> ★ **v1.11 订正**：v1.0 给读线两处都挂 `path_auth`。读线策略是「处处放行，仅空值/穿越/异常硬拦」，**从不产生确认**（无授权可给），`path_auth`（需授权）是纯误标 —— 把「放行」与「硬拦」都叫成「需授权」。

```diff
     _ok, _msg, _category = validate_read(path)
     if not _ok:
-        return SafetyResult(blocked=True, message=_msg, severity="dangerous")
-    return SafetyResult(blocked=False, requires_confirmation=False, message="", severity="safe")
+        return SafetyResult(blocked=True, message=_msg, safety_level=SafetyLevel.BLOCK_PATH_INVALID)
+    return SafetyResult(blocked=False, needs_confirm=False, message="")   # 放行: 不带标签
```

### 6.8 `app/safety/delete_path_check.py` — **R4/R5 拆分 + 补 `auth_path` + 标签细分**

> ★★ **v1.11 三处订正，其中①②是缺陷修复**：
> ① **R4/R5 必须拆开**。v1.0 方案写 `if (inside_proj and recursive) or (not inside_proj):` 合并分支 —— 该写法会把**允许根内的单文件删除**（R3，免确认）一并判成需确认。实测已复现并修复。
> ② **R5 必须补 `auth_path`**。缺它则 `safety_gate` 确认后 `if _group_lead and getattr(safety_result, "auth_path", None):` 判假 → **`grant_temp_auth` 被整个跳过** → 弹窗承诺「申请临时授权」而授权从未落地 → `delete` 工具内 `validate_delete` 仍按白名单拒绝 → **删线是死路**。实测同一路径 `write` 线给了 `auth_path` 而 `delete` 线给 `None`，两条线文案却都写着「需申请临时授权」。
> ③ 标签按成因细分，`tool_delete` 一个标签不再覆盖 5 种语义。

```diff
     # --- R6 全部允许根外递归 → 拒 ---
     if (not inside_proj) and recursive:
-        return SafetyResult(blocked=True, message=f"禁止删除工作区外目录: {path}", severity="dangerous")
+        return SafetyResult(blocked=True, needs_confirm=False,
+            message=f"禁止递归删除允许根集之外的目录(允许根集=项目根/授权目录/会话工作区): {path}",
+            safety_level=SafetyLevel.PATH_FORBIDDEN)
-    if (inside_proj and recursive) or (not inside_proj):
-        return SafetyResult(requires_confirmation=True, blocked=False,
-                            message=f"删除需确认: {path}", severity="risk")
+    # --- R4 允许根内递归 → 确认 / R5 允许根外普通 → 确认 / R3 允许根内普通 → 放行 ---
+    #   R4 必须带 recursive 条件: 根内单文件删属 R3 免确认, 不可一并拦下。
+    if inside_proj and recursive:
+        return SafetyResult(needs_confirm=True, blocked=False,
+            message=f"递归删除目录，删除范围不可撤销，需确认: {path}",
+            safety_level=SafetyLevel.DELETE_RECURSIVE)
+    if not inside_proj:
+        # auth_path 必须随 needs_confirm 一并给出: 缺它则本分支是死路(见上文②)
+        return SafetyResult(needs_confirm=True, blocked=False, auth_path=path,
+            message=f"该路径不在允许根集内(允许根集=项目根/授权目录/会话工作区)，"
+                    f"删除需申请临时授权(仅本任务有效): {path}",
+            safety_level=SafetyLevel.DELETE_OUT_OF_SCOPE)
+    # --- R3 允许根内普通 → 放行(免确认), 恒非None ---
+    return SafetyResult(blocked=False, needs_confirm=False, message="")   # 放行: 不带标签
```

其余 4 处构造点：

| 位置 | 分支 | `safety_level` |
|------|------|---------------|
| 路径归一化失败 | fail-closed | `SafetyLevel.BLOCK_PATH_INVALID` |
| 允许根读取失败 | fail-closed | `SafetyLevel.BLOCK_PATH_INVALID` |
| `guard_forbidden_delete` 命中 | 禁区硬底线 | `SafetyLevel.PATH_FORBIDDEN` |
| `validate_delete` 返 category | 禁区硬底线 | `SafetyLevel.PATH_FORBIDDEN` |

> ★ `guard_forbidden_delete` 的 5 条文案同步按 §四.5 术语统一：「禁止删除系统目录」→「禁止删除**系统保护目录**」、「禁止删除项目根/授权根目录」→「禁止删除**允许根集内的根目录自身(项目根/授权目录/会话工作区)**」、「项目根/授权根上级目录」→「**允许根集的上级目录**」。

### 6.9 `app/safety/dual_path_check.py` — **4 处属性读取 + 2 处构造**

> ★ **v1.11 标签订正**：`tool_delete` → `SafetyLevel.BLOCK_PATH_INVALID`（不带任何路径参数属**调用形状**问题，不是删除问题）；`forbidden_zone` → `SafetyLevel.PATH_FORBIDDEN`（系统源外泄拦截确属禁区）。

```diff
@@ -122,1 +122,1 @@   # write 动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
@@ -125,3 +125,3 @@   # dual 未带路径参数 → 硬拦
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_PATH_INVALID,
                                 message=f"工具 {tool_name} 声明为 dual 但调用不带任何路径参数")
@@ -137,1 +137,1 @@   # read 动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
@@ -142,1 +142,1 @@   # 系统源外泄拦截
-                return SafetyResult(blocked=True, severity="dangerous", message=msg)
+                return SafetyResult(blocked=True, safety_level=SafetyLevel.PATH_FORBIDDEN, message=msg)
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
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
@@ -74,1 +74,1 @@    # ★属性读取 cwd 写线
-            if perm.requires_confirmation:
+            if perm.needs_confirm:
@@ -85,1 +85,1 @@    # 构造
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
@@ -88,1 +88,1 @@    # ★属性读取 动作取严
-            if not (result.blocked or result.requires_confirmation):
+            if not (result.blocked or result.needs_confirm):
@@ -101,1 +101,1 @@  # 构造
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
@@ -129,1 +129,1 @@  # 构造 command 类型非法
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
@@ -139,1 +139,1 @@  # 构造 cwd 含元字符
-            return SafetyResult(blocked=True, severity="dangerous",
+            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
@@ -142,1 +142,1 @@  # ★属性读取 动作取严
-            if result.blocked or result.requires_confirmation:
+            if result.blocked or result.needs_confirm:
@@ -154,1 +154,1 @@  # 构造 高危删除无法解析目标
-        return SafetyResult(blocked=True, severity="dangerous",
+        return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
```

> ★ **本文件是本方案改动最密集的文件（9 处）**，且历史上被重构多次，行号务必落码时**现场复核**，勿照抄本文档数字。

### 6.11 `app/safety/shell_danger_command.py`

```diff
@@ -90,5 +90,5 @@
         return SafetyResult(
             blocked=True,
             message=f"高风险Shell操作: {desc}，已阻止执行",
-            severity="dangerous",
+            safety_level=SafetyLevel.BLOCK_COMMAND,
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
+            safety_level=SafetyLevel.SHELL_MEDIUM_RISK,
         )
```

### 6.13 `app/safety/path_legality_router.py`

```diff
@@ -115,5 +115,5 @@
-        return SafetyResult(blocked=True, severity="dangerous", message=f"路径安全检查异常: {e}")
+        return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND, message=f"路径安全检查异常: {e}")
```

### 6.14 `app/safety/path_tool_safety_checker.py` — **沙箱判定改读 `needs_confirm`**（核心）

```diff
@@ -143,7 +143,7 @@
         if tool_meta is None:
-            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}", severity="dangerous")
+            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}", safety_level=SafetyLevel.BLOCK_UNREGISTERED)
@@ -193,7 +193,9 @@
-            known_risk.sandbox_required = (known_risk.severity == "risk")   # risk 级授权请求→沙箱预检
+            # 2026-10-18 小欧: 沙箱判定改读 needs_confirm ——
+            #   原 (severity == "risk") 在 severity 删除后必崩, 且本就是 needs_confirm 的自证循环。
+            #   此处 known_risk 已排除 blocked(:186), 恒为需确认的授权请求 → 恒等, 行为不变。
+            # ★★ 本行是"严禁把 severity 留空字段"的决定性理由: 若 severity 留空, 本行不报错而恒 False
+            #   → sandbox_required 永不置位 → 沙箱总闸短路 → 沙箱预检静默失效。
+            known_risk.sandbox_required = known_risk.needs_confirm
             return known_risk
@@ -205,7 +207,7 @@
                     return SafetyResult(needs_confirm=True, auto_confirm=True,
                             blocked=False, message="",
-                            safety_level="tool_execute", sandbox_required=True)   # v1.25 M2-A: bypass 需确认→沙箱预检
+                            safety_level=confirm_level_for(tool_name, params),
+                            sandbox_required=True)   # v1.25 M2-A: bypass 需确认→沙箱预检
@@ -209,5 +211,4 @@
-            return SafetyResult(needs_confirm=False,
-                    blocked=False, message="安全开关已绕过")   # v1.25 M2-A: 无需确认的 bypass 不触发沙箱(与 G1 一致)
+            return SafetyResult(needs_confirm=False,
+                    blocked=False, message="安全开关已绕过")   # v1.25 M2-A: 无需确认的 bypass 不触发沙箱(与 G1 一致)
@@ -216,13 +217,12 @@
                 if not custom_result.get("is_safe", True):
                     return SafetyResult(
                         blocked=True,
                         message=custom_result.get("message", "安全检查未通过"),
-                        severity=custom_result.get("severity", "dangerous"),
+                        safety_level=SafetyLevel.BLOCK_COMMAND,
                    )
@@ -225,4 +225,3 @@
                 return SafetyResult(blocked=True,
-                        message=f"安全检查异常，已阻止执行: {e}",
-                        severity="dangerous")
+                        message=f"安全检查异常，已阻止执行: {e}",
+                        safety_level=SafetyLevel.BLOCK_COMMAND)
@@ -229,10 +228,9 @@
         needs_confirm, _shell_msg = self._get_needs_confirmation(tool_meta, params or {})
-        severity = "risk" if needs_confirm else "safe"
-        # v1.25 M2-C: 仅 risk 级触发沙箱(与 G1 唯一触发依据一致); safe 级不进预检
-        return SafetyResult(requires_confirmation=needs_confirm,
-                blocked=False, message=_shell_msg or "", severity=severity,
-                sandbox_required=(severity == "risk"))
+        # 确认标签按工具名在本层直给(confirm_level_for), 不再留空等调用方按文案关键词反查 ——
+        #   那条兜底链会让"标签"取决于"文案怎么写", 改一个字就换一个分类, 正是标签与分支对不上的病根。
+        return SafetyResult(needs_confirm=needs_confirm,
+                blocked=False, message=_shell_msg or "",
+                safety_level=confirm_level_for(tool_name, params) if needs_confirm else "",
+                sandbox_required=needs_confirm)
@@ -243,5 +242,9 @@
         if self_kill is not None:
-            return self_kill
+            return SafetyResult(blocked=True, message=self_kill.message, safety_level=SafetyLevel.BLOCK_COMMAND)
+@@ -279,1 +282,1 @@   # ★v1.6 补: _check_known_risks 汇总判定(属性读取)
+-        if risk.blocked or risk.requires_confirmation:
++        if risk.blocked or risk.needs_confirm:
 ```

> ⚠️ **v1.11 订正**：`:221` 原 `custom_result.get("severity", ...)` 是**外部 `tool_meta.check_fn` 返回 dict 的键**，属第三方契约，**读取端不动**；只是不再把它灌进 `SafetyResult`。现直接给 `SafetyLevel.BLOCK_COMMAND` —— check_fn 不通过与危险命令拦截同类，且已硬拦无授权可给。
> **注**：`data_guard` 在旧 9 值表中已随枚举化**整体消失**（无产地 + 与 `block_command` 语义重叠）。

**★ `confirm_level_for()` —— 工具级确认标签的唯一出口（v1.11 新增）**

v1.0 方案在此处留空、由上层按文案关键词回填，导致 `execute_sql`/`create_task`/`bash` 全落 `tool_execute` 一个标签。现改为**按工具名/命令动作直给**：

```python
_TOOL_CONFIRM_LEVEL = {
    "execute_sql":    SafetyLevel.SQL_EXECUTE_CONFIRM,
    "create_task":    SafetyLevel.TASK_DEAL_CONFIRM,
    "delete_task":    SafetyLevel.TASK_DEAL_CONFIRM,
    "registry_write": SafetyLevel.REGISTRY_DEAL_CONFIRM,
    "registry_delete":SafetyLevel.REGISTRY_DEAL_CONFIRM,
}
TOOL_CONFIRM_DEFAULT = SafetyLevel.TOOL_CONFIRM      # ★ 不可兜底成 shell_command_confirm
_SHELL_TOOLS = frozenset({"bash", "execute_shell_command", "execute_command"})
# 命令动作 → 标签, 取 shell_parse.action.ACTION_KINDS 的全部 3 种(闭合枚举)
_SHELL_KIND_LEVEL = {"delete": SHELL_DELETE_CONFIRM, "write": SHELL_WRITE_CONFIRM, "read": SHELL_READ_CONFIRM}


def confirm_level_for(tool_name: str, params: Optional[dict]) -> str:
    """bypass 分支与主 return 两处共用, 避免同一表达式写两遍(DRY)导致两处漂移"""
    _p = params or {}
    if tool_name in _SHELL_TOOLS:
        return shell_confirm_level(_p.get("command"), _p.get("shell_type"), _p.get("cwd"))
    return _TOOL_CONFIRM_LEVEL.get(tool_name, TOOL_CONFIRM_DEFAULT)
```

> ★ **`TOOL_CONFIRM_DEFAULT` 必须是 `TOOL_CONFIRM`（诚实的「工具级确认」兜底），不可兜底成 `SHELL_COMMAND_CONFIRM`** —— 否则一个写类工具弹窗会显示「命令确认」，标签与事实不符，正是本次重构要消灭的病。
> ★ **多动作并存取最严档**（删 > 写 > 读），与 `shell_path_check._judge_actions` 的判定优先级同序。
> ★ **⚠️ 已知现状（三堂会审发现）**：`shell_delete_confirm` / `shell_write_confirm` / `shell_read_confirm` / `shell_command_confirm` 四值当前**无产地**——`_get_needs_confirmation` 对 `bash`/`execute_command` **硬返回 `False`**（无 MEDIUM 命中即不确认），故 bash 的确认只有两个来源：中风险命令（`SHELL_MEDIUM_RISK`）与路径越权（三线标签）。四值待「bash 是否应对路径合规的命令也确认」这一**行为决策**落地后才有消费者，在此之前属预留枚举，非死代码亦非已生效。

### 6.15 `frontend/src/features/chat/streams/backupTypes.ts` — 前端类型源

```diff
@@ -21,11 +21,12 @@
 export interface PendingAuthorizationPayload {
   confirm_id: string;
   tool_name: string;
   params?: Record<string, unknown>;
   content?: string;
   safety_level?: string;
+  trust_impact?: 'high' | 'medium' | 'low';   // 授权影响面: high=删除类 / medium=写入类 / low=其余
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
+                  trustImpact: pendingAuthorization.trust_impact ?? 'low',
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
 +  trustImpact?: 'high' | 'medium' | 'low';   // 授权影响面
   trustPath?: string | null;
@@ -131,6 +132,21 @@
 const SAFETY_LEVEL_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
-  path_auth: { color: 'orange', label: '需授权', icon: <WarningOutlined /> },
-  shellparam: { color: 'orange', label: '命令确认', icon: <ExclamationCircleOutlined /> },
-  tool_write: { color: 'geekblue', label: '写确认', icon: <EditOutlined /> },
-  tool_delete: { color: 'red', label: '删除确认', icon: <StopOutlined /> },
-  tool_execute: { color: 'volcano', label: '执行确认', icon: <ExclamationCircleOutlined /> },
+  // ★ 键集必须与后端 SafetyLevel.CONFIRM_LEVELS 完全相等(硬拦命名空间不进弹窗, 不配)
+  delete_recursive:     { color: 'red',     label: '递归删除确认', icon: <StopOutlined /> },
+  delete_out_of_scope:  { color: 'red',     label: '范围外删除授权', icon: <WarningOutlined /> },
+  write_protected:      { color: 'orange',  label: '受保护路径写入授权', icon: <WarningOutlined /> },
+  write_out_of_scope:   { color: 'orange',  label: '范围外写入授权', icon: <WarningOutlined /> },
+  shell_medium_risk:    { color: 'orange',  label: '命令确认', icon: <ExclamationCircleOutlined /> },
+  shell_delete_confirm: { color: 'red',     label: '命令含删除动作', icon: <StopOutlined /> },
+  shell_write_confirm:  { color: 'orange',  label: '命令含写入动作', icon: <EditOutlined /> },
+  shell_read_confirm:   { color: 'blue',    label: '命令含读取动作', icon: <FileSearchOutlined /> },
+  shell_command_confirm:{ color: 'orange',  label: '命令确认', icon: <ExclamationCircleOutlined /> },
+  sql_execute_confirm:  { color: 'volcano', label: 'SQL 执行确认', icon: <ExclamationCircleOutlined /> },
+  task_deal_confirm:    { color: 'geekblue',label: '任务处理确认', icon: <EditOutlined /> },
+  registry_deal_confirm:{ color: 'volcano', label: '注册表处置确认', icon: <ExclamationCircleOutlined /> },
+  tool_confirm:         { color: 'volcano', label: '工具级确认', icon: <WarningOutlined /> },
 };
```

> ★ **v1.11 全表替换**：旧 5 键（`path_auth`/`shellparam`/`tool_write`/`tool_delete`/`tool_execute`）与新枚举**无一重合**，全部作废。`tool_write` 是死条目（后端 0 产地）。
> ★ **兜底仍必须保留**（`SAFETY_LEVEL_CONFIG[request.safetyLevel] || {label: request.safetyLevel}`）作为防御，但**不应被命中** —— 应由一条前后端一致性测试锁死（见 §九）。

**三条独立说明行（挂在 `content` 之外，规避 `WebkitLineClamp:2` 截断）**：

```tsx
{/* ① 授权影响面: 英文标识映射中文显示(后端为准, 前端只呈现不做权限判断) */}
{request?.trustImpact && (
  <div style={{ marginTop: 4 }}>
    <Text type="secondary">
      授权影响：
      {request.trustImpact === 'high'
        ? '大（删除类，抹除不可撤销）'
        : request.trustImpact === 'medium'
          ? '中（写入类，可覆写原内容）'
          : '小（命令级确认，不直接改文件内容）'}
    </Text>
  </div>
)}

{/* ② 临时授权时效: temp_auth 是任务级 ContextVar, 任务结束自动失效 */}
{(safetyLevel === 'write_protected' || safetyLevel === 'write_out_of_scope' ||
  safetyLevel === 'delete_out_of_scope') && (
  <div style={{ marginTop: 8, marginBottom: 4 }}>
    <Text type="secondary" style={{ fontSize: 12 }}>
      临时授权仅本任务有效，任务结束自动失效；与下方"信任此操作"（会话级）是两套机制
    </Text>
  </div>
)}

{/* ③ 系统禁区不可授权 */}
{safetyLevel === 'delete_recursive' && (
  <div style={{ marginTop: 8, marginBottom: 4 }}>
    <Text type="secondary" style={{ fontSize: 12 }}>
      该路径在允许根集内，但递归删除不可撤销，仅可确认单文件删除
    </Text>
  </div>
)}
```

> ★ **v1.11 三处订正**：①`trustImpact` 映射由二档改**三档**；②触发条件由 `path_auth` 改为**实际带临时授权的三个标签**（`path_auth` 已不存在）；③第三条由「`forbidden_zone` 系统禁区不可授权」改为 `delete_recursive` —— `forbidden_zone` 是**硬拦命名空间**、永不进弹窗，该说明行永不可能触发。`delete_recursive` 是**弹窗内**唯一需要额外解释的删除类（它不授予路径授权，只确认这一次不可撤销的操作）。

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

### A 类：`SafetyResult` 字段与工厂（**v1.11 订正路径**）

| 文件 | 动作 |
|------|------|
| `app/safety/safety_result.py` | 删 `severity` 定义；`requires_confirmation` → `needs_confirm`；增 `safety_level`；**新增 `SafetyLevel(StrEnum)` + `CONFIRM_LEVELS` + `BLOCK_LEVELS`** |
| `app/safety/safety_result.py` | `pass_result()` 同步 |

### B 类：`SafetyResult(...)` **构造点（31 处）** + 属性读取（12 处，见 C 类）

> v1.6 起本表**明确区分「构造 kwarg」与「属性读取」** —— 前者加 `safety_level`/改 kwarg 名，后者只改属性名。
> ★ **v1.11 重做**：枚举化后新增 `SafetyLevel` 成员引用（而非裸串），且 `delete_path_check` 因 R4/R5 拆分增至 9 处、`path_tool_safety_checker` 因 `confirm_level_for` 收敛为 2 个出口。

| 文件 | 构造 | 读取 | `safety_level`（v1.11 实际值） |
|------|------|------|----------------|
| `read_path_check.py` | 2 | 0 | `BLOCK_PATH_INVALID` ×1 / 放行**不带标签** |
| `write_path_check.py` | 4 | 0 | `WRITE_PROTECTED` / `WRITE_OUT_OF_SCOPE` / `PATH_FORBIDDEN` / 放行不带标签 |
| `delete_path_check.py` | **9** | 0 | `DELETE_RECURSIVE` / `DELETE_OUT_OF_SCOPE` / `PATH_FORBIDDEN` ×3 / `BLOCK_PATH_INVALID` ×2 / 放行不带标签 |
| `dual_path_check.py` | 2 | **4** | `BLOCK_PATH_INVALID` / `PATH_FORBIDDEN` |
| `shell_path_check.py` | 6 | **3** | `BLOCK_COMMAND` ×6 |
| `shell_danger_command.py` | 1 | 0 | `BLOCK_COMMAND` |
| `shell_command_risk.py` | 1 | 0 | `SHELL_MEDIUM_RISK` |
| `path_legality_router.py` | 1 | 0 | `BLOCK_COMMAND` |
| `path_tool_safety_checker.py` | 3 | **2** | `BLOCK_UNREGISTERED` / `BLOCK_COMMAND` ×2 |
| `safety_gate.py` | 0 | **2** | （编排层，不产 SafetyResult） |
| `sandbox_gate.py` | 0 | 0 | （产 `ConfirmSpec`，`BLOCK_COMMAND`） |
| `tool_facade.py` | 0 | **1** | （下游消费） |
| `execute_shell_command.py` | 0 | **1** | （下游消费） |
| **合计** | **29** | **13** | — |

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

### D 类：`ConfirmSpec.trust_impact`

| 文件 | 动作 |
|------|------|
| `hitl_gateway.py` | 字段改名 `trust_impact`（取值 `high`/`medium`/`low`）；paused 帧改键 |
| `sandbox_gate.py` | 不传 `trust_impact`（沙箱裁决未授予路径访问权）；`safety_level` 改 `BLOCK_COMMAND` |

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

## 八、实施顺序（**v1.11 按落码现状重排**）

> ★ 批一~批六**已落码**（2026-10-18）。批七/批八（前端 F 类链）**本次补做**。下表标注各批状态。

| 批次 | 内容 | 文件 | 依赖 | 状态 |
|------|------|------|------|------|
| 批一 | 字段层：删 `severity` + 改名 `needs_confirm` + 增 `safety_level` + **`SafetyLevel` 枚举** | `app/safety/safety_result.py` | 无 | ✅ |
| 批二 | C 类读取点 + 全部代码点 kwarg 改名（**含沙箱判定改读 `needs_confirm`**） | `path_tool_safety_checker` / `safety_gate` / `tool_facade` / `execute_shell_command` | 批一（**必须同批，否则中间态崩**） | ✅ |
| 批三 | B 类构造点补 `safety_level` + 措辞补齐 + **R4/R5 拆分 + R5 补 `auth_path`** | 8 个 safety 文件 | 批一 | ✅ |
| 批四 | `temp_auth._is_rejectable_root` 上提 | `temp_auth.py` | 批二 | ✅ |
| 批五 | D 类 `ConfirmSpec` 正名 + **`trust_impact` 改三档按 `safety_level` 取档** | `hitl_gateway.py`, `safety_gate.py`, `sandbox_gate.py` | 批二 | ✅ |
| 批六 | 注释订正（功能注释改名，历史注释保留） | `tool_routes.py` | 批二 | ⬜ 本次补做 |
| 批七 | **前端 F 类白名单链（F1→F2→F3，缺一即静默丢字段）** | `backupTypes.ts`, `sseParser.ts`, `useAuthorization.ts` | 批五 | ⬜ 本次补做 |
| 批八 | 前端视图：`SAFETY_LEVEL_CONFIG` **13 键** + `AuthorizationRequest.trustImpact` + 渲染三行说明 | `index.tsx` | 批七 | ⬜ 本次补做 |
| 批九 | 端到端验证 + 全量 pytest + `npm run check:full` | — | 全部 | ⬜ |

**v1.11 新增批次（已落码，记录备查）**：

| 批次 | 内容 | 文件 |
|------|------|------|
| 批十 | **`rename` 源判为「写」**，shell 侧同步（动词表拆分 + 沙箱宽表并入） | `tool_constants.DUAL_ACTION_PARAMS`（核对不动）/ `shell_parse/parse_move.py` / `shell_parse/parse_shell_action.py` / `shell_sandbox_tables.py` |
| 批十一 | **删除 `_classify_safety_level`**（关键词反查链，各判定点直给后成死代码） | `safety_gate.py` |
| 批十二 | 目录术语统一（允许根集／白名单／代码目录／会话工作区） | `path_classify_category.py` / `delete_path_check.py` / `write_path_check.py` |

---

## 九、验收标准（**v1.11 按落码现状重写**）

### 已落码部分的验收（应全过）

1. `SafetyResult` 类体内无 `severity` 字段行
2. `grep -rn "SafetyResult(.*severity=" backend/app` 零匹配
3. **`requires_confirmation` 在代码中零残留**（排除编辑历史注释）：
   ```powershell
   Get-ChildItem -Path app -Recurse -Filter *.py | Select-String -Pattern "requires_confirmation" | Where-Object { $_.Line -notmatch '^\s*#' }
   ```
   期望：**零输出**。
4. `grep -rn "\.severity == \"risk\"" backend/app` 零匹配
5. **★ 枚举外值零泄漏**（v1.11 新增，最强约束）：
   ```python
   from app.safety.safety_result import SafetyLevel, CONFIRM_LEVELS, BLOCK_LEVELS
   VALID = {str(v) for v in SafetyLevel}
   # 静态: 扫 safety_level="..." 字面量, 必须全在 VALID 内
   # 运行时: 遍历各工具各分支, 产出的 safety_level 必须是 VALID 成员或空串
   ```
6. **`_classify_safety_level` 已删除**（v1.11 订正原验收 #8「保留」）
7. `MetaStep.severity` 站点（E 类）**零改动**
8. **★ 前后端标签集一致**（v1.11 新增，替代原验收 #13）：
   `set(SAFETY_LEVEL_CONFIG.keys()) == set(str(v) for v in CONFIRM_LEVELS)`
9. `sandbox_gate.py` 不传 `trust_impact`；其 `safety_level` 为 `BLOCK_COMMAND`
10. `trust_impact` 值域仅 `high`/`medium`/`low`，且**按 `safety_level` 取档**（非 `auth_path`、非 `recursive`）
11. **放行结果一律不带 `safety_level`**（空串）
12. **`needs_confirm=True` 且文案承诺授权的分支，必须带 `auth_path`**（R5 已补）
13. `blocked=True` 与 `needs_confirm=True` 互斥（实测全分支零同现）
14. **★ `rename` 工具与 bash `Rename-Item` 判定一致**（v1.11 新增）：四组语义（改名/搬移/复制/删除）逐组比对，工具与 shell 必须同结论
15. **★ 沙箱宽表含改名动词**（v1.11 新增）：`SHELL_WRITE_INTENT_RE.search("Rename-Item")` 必须为 True
16. 沙箱判定改读 `needs_confirm`（`known_risk.sandbox_required` 与主 return 两处），行为等价不变

### 前端部分（本次补做后验收）

17. `SAFETY_LEVEL_CONFIG` 覆盖 `CONFIRM_LEVELS` 全部 13 个值
18. 弹窗显示「授权影响：大（删除类，抹除不可撤销）」／「中（写入类，可覆写原内容）」／「小（命令级确认…）」
19. 三个带临时授权的标签（`write_protected`/`write_out_of_scope`/`delete_out_of_scope`）显示「临时授权仅本任务有效…与信任此操作是两套机制」
20. `delete_recursive` 显示「递归删除不可撤销，仅可确认单文件删除」
21. `grep -n "trust_impact\|trustImpact" frontend/src` 应命中 4 个文件，少一处即断链
22. **端到端验证**：`trust_impact` 经 F1→F2→F3→F4 四层后，`request.trustImpact` 非空（白名单静默丢弃唯一定位手段，静态检查抓不到）
23. `npm run check:full` 通过（**含 `typecheck` 与 `typecheck:e2e`**）
24. 全量 `pytest` 通过（不含需真实后端服务的 `test_api_comprehensive.py`）

### 措辞验收

25. 文案不含禁用词（工作区／允许的操作范围／受保护区域／授权根目录）——「会话工作区」是合法来源名，不算
26. 文案提到的目录集合名，必须与该分支**实际使用的那个集合**一致（删线→允许根集；写线→白名单）
27. 文案承诺的行为必须在分支里真实发生（如「需申请临时授权」必须有 `auth_path`）

---

## 十、风险与回滚（**v1.11 增补**）

| 风险 | 影响 | 缓解 |
|------|------|------|
| 批一/批二不同批落地 | C 类读取点 `AttributeError`/`TypeError`，服务不可用 | 强制同批原子提交 |
| 全局替换误改 `MetaStep.severity` | SSE 分级丢失，前端错误通道与样式退化 | 按 §二/§七 E 类逐点排除，禁全局替换 |
| `needs_confirm` 改名留了兼容别名 | 新旧两套真源，违反禁止 backward | 验收 #3（排除注释后零输出） |
| 影响面统计用非递归 glob 漏文件 | v1.5 实际发生：漏 4 文件 / 11 处 | 全量统计用 `Get-ChildItem -Recurse`；**行号统计禁用 PowerShell，一律用 Python** |
| `tool_facade`/`execute_shell_command` 读取点漏改 | 直调 API 与 shell 确认路径 `AttributeError` | 批二 + §6.0 清单 #15/#16 |
| **★ 枚举外值泄漏**（v1.11 新增） | 前端查不到配置 → 走兜底**直接显示原始英文串**；且分类信息全丢 | 验收 #5（静态 + 运行时双查）+ #8（前后端集一致） |
| **★ 删兜底函数前未确认无调用点**（v1.11 实际险招） | 若仍有路径 level 为空 → 分类恒空 | 删前先确认所有产码点直给；验收 #6 |
| **★ R5 缺 `auth_path`**（v1.11 实际缺陷） | 弹窗承诺授权而授权未落地 → 确认后仍被拒，删线死路 | 验收 #12 |
| **★ 动词表拆分漏并宽表**（v1.11 实际退化） | 改名命令不进沙箱写意图判定 | 验收 #15 |
| **★ `TOOL_CONFIRM_DEFAULT` 兜底成命令标签**（v1.11 已避免） | 写类工具弹窗显示「命令确认」，标签说谎 | 兜底必须是 `TOOL_CONFIRM` |
| 前端白名单层漏改 | 后端正确但前端无显示 | 验收 #22 端到端 + #21 grep 计数 |
| 措辞改动打破既有断言 | 测试失败 | 措辞仅改 message，grep 受影响测试后同步 |
| `sandbox_gate` 误传 `trust_impact` | 沙箱裁决场景误导用户以为获得路径权限 | 验收 #9 |

---

## 十一、[39]原案 逐条落位对照表

| [39]原案 章节 | [39]原案 结论 | 本文落位 | 状态 |
|---------|----------|---------|------|
| §1.3 事实1 | `safety_level` 产地错（扫文本） | §四.1 + §六.3 + §六.6~6.14 | ✅ 采纳 |
| §1.3 事实2 | `content` 被 `WebkitLineClamp:2` 截断 | §六.18 独立 DOM 行 | ✅ 采纳 |
| §1.3 事实3 | `temp_auth` 是后端任务级不变式 | §六.6/§六.18 只描述不改语义 | ✅ 采纳 |
| §1.3 事实4 | `sandbox_gate` 已直接置位（范式） | §六.5 | ✅ 采纳（订正：置的是 `ConfirmSpec` 非 `SafetyResult`） |
| §1.4 结论1 | `safety_level` 字段没问题，只是产地错 | §四.1 + §六.3 | ✅ 采纳 |
| §1.4 结论2 | `severity` 正名 `trust_impact` | §五.3（**v1.11 改判**：`high`/`medium`/`low`，真值源 `safety_level`） | 🔄 **两次深化**（原案只说正名；v1.5 补 `recursive` 真值源；v1.11 按老陈裁定改为按操作性质三档） |
| §1.4 注 | 不新增 `reason_code` | 全文 | ✅ 采纳 |
| §1.5 E | 复用现有字段 + 前端合成 | 全文 | ✅ 采纳 |
| §1.6 第1步 | `SafetyResult` 增 `safety_level`；**删** `_classify_safety_level` | 增字段 ✅ + **`SafetyLevel` 枚举**（v1.11 扩充）；**删函数 ✅（v1.11 已删）** | ✅ **完全采纳**（v1.5 曾改为"保留兜底"，v1.11 回归原案并说明理由：保留兜底的反面理由——"无 message 场景会失分类"已不成立，因该场景已在产码点直给） |
| §1.6 第2步 | `severity` → `trust_impact`，前端改读 | §五.3 + §六.3/6.4/6.5 + §6.15~6.18 | ✅ 采纳 |
| §1.6 第3步 | 沙箱判定改读 `requires_confirmation` | §五.4 + §六.14 | ✅ 采纳 |
| §1.6 第3步 | blocked 分支不再塞 severity | §七 B 类 + §六各处 | ✅ 采纳 |
| §1.6 第4步 | 前端显示信任影响 + 临时授权说明 + 系统禁区说明，独立一行 | §六.18 | 🔄 **订正触发条件**（`path_auth` 已不存在；「系统禁区不可授权」原挂在 `forbidden_zone`，而该值属硬拦命名空间永不进弹窗，该行永不可能触发 → 改挂 `delete_recursive`） |
| §1.6 第5步 | 措辞补齐 | §六.6 + **§四.5 术语统一** | 🔄 **深化**（补的不只是"临时"二字，还有目录术语全量统一：允许根集 vs 白名单是两个不同集合） |
| §1.7 | 危险等级等价关系（重复编码） | §四.2 | ✅ 采纳 |
| §1.7 | 「自证循环」判断 | §五.4 实测复核 `:231-235` **成立** | ✅ 采纳 |

---

## 十二、`rename` 源判为「写」（v1.11 新增）

**问题**：改名前原路径消失，形式上像删除。但**改名不销毁数据、可回退**，与删除的「抹除不可撤销」性质不同。若按删线处理，则代码目录内的改名被硬拦，而同名文件的新建/改写只弹确认——对同一目录的两种操作给出宽严不一的判定。

**裁定（老陈 2026-10-18）**：`rename` 工具的源判为**写**。

**同步要求（必须与工具侧一致）**：shell 通道的改名动词原与搬移动词合表（`Rename-Item`/`ren`/`rnm`/`rename` 均在 `MOVE_VERBS_*`），改后须拆出独立动词表并按动词二分源档位：

```python
MOVE_VERBS_PS   = ("Move-Item", "mi", "mv")            # 搬移: 源被搬走 → 源=delete
RENAME_VERBS_PS = ("Rename-Item", "ren", "rnm")        # 改名: 只换名   → 源=write
```

三处连带改动（缺一即退化）：

| # | 位置 | 改动 | 漏改后果 |
|---|------|------|---------|
| 1 | `shell_parse/parse_move.py` | 动词表拆分 + `parse_move_action` 按动词二分源档位 | 语义与工具不一致 |
| 2 | `shell_parse/parse_shell_action.py` | 全局早退门补 `SHELL_RENAME_RE` | 改名命令被早退门跳过全部路径检查 |
| 3 | **`shell_sandbox_tables.py`** | `_intent_verb_union()` 并入 `RENAME_VERBS_BY_SHELL` | ★**沙箱宽表丢改名动词** —— 宽表是沙箱侧独立依据、不经早退门，漏并等于改名命令不进沙箱写意图判定（实测 `SHELL_WRITE_INTENT_RE.search("Rename-Item")` 为 `False` 即此退化） |

**验证**：四组语义（改名／搬移／复制／删除）逐组比对工具与 shell(PS) 判定，必须同结论。

---

## 十三、`safety_level` 枚举化（v1.11 新增）

**问题**：9 个裸字符串在 13 个文件里手写，同一成因多处各写一遍、新成因随手加字符串，无任何约束；且「硬拦原因」与「确认原因」混在同一空间，导致 `path_auth` 一个标签同时表示放行／硬拦／任务级授权／临时授权／沙箱裁决五种语义。

**治法**：
1. `SafetyLevel(StrEnum)` **单源定义**，两空间前缀隔离；
2. 派生 `CONFIRM_LEVELS`（13）与 `BLOCK_LEVELS`（4），前者是前端配置的**唯一对齐基准**；
3. 确认标签在**产码点直给**（`path_tool_safety_checker.confirm_level_for` 统一出口），彻底删除按文案关键词反查的 `_classify_safety_level`；
4. 放行结果不带标签。

**附带的既有安全缺口（三堂会审发现，非本次引入，尚未修）**：

| # | 现象 | 实测 | 性质 |
|---|------|------|------|
| 1 | 相对源 + 绝对目标的复制命令，**目标被判成源** | `Copy-Item a.txt C:\Windows\b.txt` → 解析为 `[('read','C:\\Windows\\b.txt','copy-src')]` → 读线放行系统目录 → **往系统目录写文件不拦** | 安全漏洞 |
| 2 | shell 通道**缺「系统源外泄拦截」** | `copy C:\Windows\a.txt out.txt` → `blocked=False`；而 `dual_path_check.py:141-144` 有该拦截，`shell_path_check` 读循环没有 → **系统文件可搬出** | 安全漏洞（两通道不一致） |

两者均在 `lexer.split_source_target` 与 `shell_path_check` 读循环，修复会改判定行为，需单独立项。

---

**版面签名**：本文由小欧于 2026-10-18 16:59:55 修订至 **v1.11（全量对齐本地已落码 + 补记 v1.0~v1.10 无载的已落码事项）**。