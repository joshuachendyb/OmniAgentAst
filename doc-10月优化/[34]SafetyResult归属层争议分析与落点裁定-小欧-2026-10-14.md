# [34]SafetyResult 归属层争议分析与落点裁定

创建时间：2026-10-14 21:30:06

| 版本 | 时间 | 更新要点 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-10-14 21:30:06 | 新建：SafetyResult 归属层争议分析（老陈质疑"这该在系统层"）。含类义、实测血缘、27 构造点/消费方分布、承重墙拆解可行性、三方案对照、落点建议 | 小欧 |

> **关联文档**
> - `[32]安全信任三处结构归位可行性分析-小欧-2026-10-14.md`：已把 `execute_shell_command_safety.py:54/208` 列为"安全一分为二"的承重墙之一。**本文是其补充**——[32] 只指出"墙"，本文分析"墙能否拆"。
> - `[50]HITL弹框消息字段梳理-小欧-2026-09-18.md`：本类字段语义来源。
> - `[33]信任与授权权限现状问题与优化实施设计-小欧-2026-10-14.md` 4.11-D：本次实施依据（契约迁 `app/tools/tool_types.py`）。
> - 争议来源：2026-10-14 老陈审阅 P1 实施时质疑——"这好像是最近增加的，为什么在工具层，我觉得应该在系统层"。

---

## 一、结论先行

老陈的判断**对了一半**：该类确实是"为安全设计的契约"，但**它不是纯安全层的东西**——因为**工具层也在生产它**（实测 7 个构造点）。

**真问题不是"契约放哪层"，而是"谁该生产这个契约"。**

**当前建议**：维持 `app/tools/tool_types.py`（方案 A），把"收窄工具层依赖"（方案 C）列为独立议题，不在 P1 顺手带。

---

## 二、这个类是什么

纯 `dataclass`，**无任何逻辑**（只承载裁决结果），字段全部为"安全裁决"语义：

| 字段 | 含义 | 实际读取方（实测） |
|---|---|---|
| `blocked` | 硬拦死，不给确认机会 | 编排层 + bash 工具 `execute_shell_command.py:1125` |
| `requires_confirmation` | 需弹窗由用户裁决 | 编排层（`safety_gate`/`hitl_gateway`）；bash 工具**仅用于打日志** |
| `message` | 展示层文案（拼进安全事件与前端提示） | 展示层 + bash 工具 `:1127` |
| `severity` | 危险等级（与 SSE 输出对齐） | 编排层 |
| `auto_confirm` | 自动放行标记 | 编排层 |
| `auth_path` | 白名单外临时授权路径（`None`=普通确认） | `safety_gate:236` → `tool_facade` |
| `sandbox_required` | 是否触发沙箱预检（**沙箱预检触发唯一依据**） | `action_handler`/`executor`/`tool_facade` |

**消费方全部是编排层**（`safety_gate`/`hitl_gateway`/`tool_facade`/`handle_action`/`executor`）——本质是"安全层 → 编排层"的**传话对象**。

---

## 三、血缘（git 实测，非推断）

```
2026-08-12  4933452e4  refactor:A1安全模块迁移 path_safe_check+temp_auth+SafetyResult迁app.tools.security
```

- **诞生于系统层**：原定义在 `app/safety/tool_safety_checker.py`。
- **同日被迁到工具层**：迁入 `app/tools/security/safety_result.py`。
- 迁移理由（原文件 docstring 原文）：*"被 tools 层(Shell 风险检查)与 safety 层(checker)双向消费，定义在 tools/security 使 tools 层自包含"*。
- **即：老陈"它该在系统层"的直觉 = 它的出身；但当日搬走是刻意决定，不是随手放错。**

---

## 四、构造点与消费方实测分布

### 4.1 构造点（27 处）

| 构造方 | 所在层 | 处数 |
|---|---|---|
| `app/safety/tool_safety_checker.py` | 系统层 | 15 |
| `app/safety/delete_safety.py` | 系统层 | 5 |
| **`app/tools/fundamental/execute_shell_command_safety.py`** | **工具层** | **7** |

### 4.2 工具层那 7 个构造点的消费者（仅 2 处引用该模块）

| 引用方 | 位置 | 用途 |
|---|---|---|
| `app/safety/tool_safety_checker.py` | `:330` | `check_shell_command_risk_all_shells(_cmd)` —— 走完整 HITL 裁决（方向 safety→tools，合法） |
| `app/tools/fundamental/execute_shell_command.py` | `:240`/`:1122` | bash 工具**自身**内联预检 |

---

## 五、关键发现：承重墙可以拆，且比看上去薄

### 5.1 bash 工具那次内联预检只做"硬拦"，不做裁决

`execute_shell_command.py:1122`：

```python
safety = check_shell_command_risk(processed_command, shell_type, protected_pids=shell_pool.get_all_pids())
if safety:
    if safety.blocked:                       # ← 只消费 blocked
        return build_error(...)
    if safety.requires_confirmation:         # ← 只用于打日志，明确不弹窗
        logger.warning("[Shell] 中风险命令本级放行(确认由上游安全门禁承担, 无弹窗非缺陷)")
```

**该调用只读 3 个字段**：`blocked`、`message`、`requires_confirmation`（且最后一个仅用于日志）。

**HITL 契约字段 `auth_path`/`sandbox_required`/`auto_confirm`/`severity` 工具层一个都没用。**

### 5.2 由此得出的结论

工具层对整份 HITL 契约的依赖**比表面弱得多**：它实质只需要"是否硬拦 + 原因文案"两个语义。

因此：
- 若把 bash 工具那次预检**收窄**（改用一个窄类型/直接复用 `shell_static_guard` 判定），工具层即不再生产本契约；
- 契约随之可**堂堂正正回到系统层**，且全链自洽；
- 这比"搬模块 + 改调用链"（方案 B）**改动面小得多**。

---

## 六、三方案对照

| 维度 | **A. 维持 `tool_types`**（现状/已实施） | **B. 契约+风险检查整体回系统层** | **C. 收窄工具层依赖后契约回系统层** |
|---|---|---|---|
| 依赖边 | `safety→tools`（合法） | 需先解耦 bash 工具 `:1122` | 同 B，但仅换掉那 3 个字段的用法 |
| 架构守护红项1（tools→safety） | **不复活** | 会复活，除非先解耦 | 不复活 |
| 改动面 | 已完成，0 | 大：搬模块 + 改 bash 工具调用链 + 硬拦路径回归 | 中：仅收窄一次调用的依赖面 |
| 语义纯度 | `tool_types` 是"工具类型/元数据单源"，放安全契约略有将就 | 最正 | 最正 |
| 回归风险 | 低（已跑通） | **高**：bash 硬拦是安全关键路径，须跑 E2E | 中 |
| 可逆性 | 好 | 差 | 中 |

---

## 七、落点建议（维持 A，另开 C 议题）

**建议：先 A，把 C 作为下一个独立议题。** 理由按分量排序：

1. **契约应跟着生产者走，不应单独搬。** 现在把契约搬去迁就一个"本该在系统层、却暂时在工具层"的生产者，属**倒着改**——等于用接口迁就错误实现。正确顺序是：先定生产者归属，再定契约归属。
2. **C 才是解法，且比 B 便宜。** 见 5.2：只需收窄一次调用的依赖面，不必搬模块、不必改整条调用链。
3. **A 现在零风险**：已完成、架构守护全绿、27 个构造点未动。此时挪回系统层属于"无收益 + 制造风险"。
4. **议题性质不同**：这是 **SA 架构口径**问题，与 `is_system_protected_path`（纯路径工具函数，已按老陈裁定下沉 `app/utils/`）不是一回事，不应在 P1 顺手带进来。

---

## 八、需要老陈裁定的一句话

> **bash 工具（`execute_shell_command.py:1122`）自己那次安全预检，应该留吗？**
>
> - **留** → 工具层依赖注定存在，契约就得待在工具层（方案 A）。
> - **删掉/统一走上游安全门禁** → 工具层不再生产契约，契约可回系统层（方案 C）。

---

## 九、本议题与已实施内容的关系

- 2026-10-14 P1 批次已按方案 A 实施：`SafetyResult` 迁入 `app/tools/tool_types.py`，旧模块 `app/tools/security/safety_result.py` 已删除（禁 backward 双份契约：双份 dataclass 会让 `isinstance` 判定失效——上层收 A 的实例、用 B 的类判，恒 False 且不报错）。
- 3 个消费方 import 已同步改：`app/safety/tool_safety_checker.py:128`、`app/safety/delete_safety.py:28`、`app/tools/fundamental/execute_shell_command_safety.py:54`。
- 测试侧 `tests/test_sandbox_executor.py`、`tests/test_s50_hitl_overwidth_tdd.py` 同步改（**本地改，按 AGENTS 铁律不 commit**）。
- 验收断言见 `backend/tests/test_p1_layer_ownership.py::test_tool_types_owns_safety_result` / `test_old_safety_result_module_removed` / `test_safety_result_constructor_contract` / `test_consumers_get_same_safety_result_object`。

—— 小欧 2026-10-14 21:30:06
