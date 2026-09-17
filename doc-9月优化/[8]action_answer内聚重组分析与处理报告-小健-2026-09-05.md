# [8]action/answer内聚重组分析与处理报告-小健-2026-09-05

**文档名称**：[8]action/answer内聚重组分析与处理报告-小健-2026-09-05
**编写人**：小健
**创建时间**：2026-09-05 11:01:46
**更新时间**：2026-09-05 11:49:30

| 版本 | 时间 | 更新人 | 更新要点 |
|------|------|--------|----------|
| v1.0 | 2026-09-05 11:01:46 | 小健 | 初版：内聚为纲分析 + 3项处理方案 - 小健-2026-09-05 |
| v1.1 | 2026-09-05 11:03:53 | 小健 | 新增第八章：可直接实施的代码diff（3项逐行改法，附调用点对照） - 小健-2026-09-05 |
| v1.2 | 2026-09-05 11:19:29 | 小健 | 新增第九章：check_safety_and_confirm 门禁职能与拆出方案（含 handle_action.py 改名成立条件） - 小健-2026-09-05 |
| v1.3 | 2026-09-05 11:26:02 | 小健 | 全文核查修正6处：4.3重号→4.4、guard入口名对齐8.3、5.1/5.2签名定案、L602→L603口径统一、8.1注澄清、response改名作废声明 - 小健-2026-09-05 |
| v1.4 | 2026-09-05 11:29:45 | 小健 | 新增第十章：承[7]第八章TDD体例，两代码各一完整阶段实施计划（含引用面实测与顺序依赖） - 小健-2026-09-05 |
| v1.5 | 2026-09-05 11:40:03 | 小健 | 误冻结一次（已撤销）：错将[8]服从[7]冻结实施章 - 小健-2026-09-05 |
| v1.6 | 2026-09-05 11:43:52 | 小健 | 以[8]为准：北京老陈亲删冻结声明与第十一章；10.6恢复执行，[7]v1.1同步改对齐 - 小健-2026-09-05 |
| v1.7 | 2026-09-05 11:49:30 | 小健 | 全文核查修正7处：4.3改调口径、response暂缓改作废、双保险set_completed归属、做/说终态表述、结论执行句、四个→五个用例、行尾注释保留 - 小健-2026-09-05 |

---

## 一、分析原则：内聚为纲

北京老陈裁定：方案不分最小/最大，只看架构是否合理；**功能类似相关的代码集中，同类集中、异类拆出**。本报告所有结论以此为唯一标尺，以 `file:line` 实证为据。—— 小健-2026-09-05

自我纠正：此前口头分析称"FinalStep两处各造"，经全仓 grep 核实为 **5文件12+处**，特此纠正，不谎报（见四.3证据表）。—— 小健-2026-09-05

---

## 二、现状盘点（实证）

| 模块 | 规模 | 函数 | 行号 |
|------|------|------|------|
| `handlers/action_handler.py` | 608行 | `check_safety_and_confirm` | L266-497 |
| | | `handle_action` | L499-608 |
| `handlers/answer_handler.py` | 235行 | `handle_answer` | L101-235 |
| | | `_dedup_repeat` | L65-98 |
| `react_dispatch.py` | 123行 | `_dispatch_handler` | L22-123 |

路由规则（`react_dispatch.py:47-57`）：`type=action→handle_action`，其余一切（answer/error/未知/None）→`handle_answer`。type 由 `llm_stream.py` 推断，不由 LLM 输出。

---

## 三、两者关系：做 vs 说

ReAct 循环一轮只有两条出路，分派器按此分叉：

- **做（handle_action）**：常规不设终态继续循环，唯 return_direct 直出终态。管线：解析→Thought→安全/HITL/沙箱三汇合→ActionStep→执行→观察→return_direct终态（L603-607，唯一终态出口；与 8.2⑤口径统一）。
- **说（handle_answer）**：终结或续命。5分支：error→failed（L118-135）/ unknown→failed（L138-156）/ 空→retrying（L163-174）/ reasoning-only→计数续循环或终止（L185-215）/ 正常answer→completed（L217-235）。

终态推断双保险：handler 内先 `set_failed`（failed 路径，09-03 顺序），dispatch 外再按 `seen_types` 复核终态/重试/拒绝计数（`react_dispatch.py:71-112`，completed 由此层置）。

**结论：两个必须保留**。做/说语义对立，合并不仅复辟 1144 行烂文件，更把"有副作用需门禁"与"纯解释定终态"两种心智模型搅在一起。—— 小健-2026-09-05

---

## 四、问题诊断（有理有据）

### 4.1 handle_answer 的 5 分支是同类，不拆

5 分支判据同源（全读 `parsed` 内容）、出口同形（FinalStep / retrying / Thought 三选一），同属"解释 LLM 说话→定终态或继续"。按分支拆（三文件）是把同类打散，违反集中规矩。此前方案 B 作废。—— 小健-2026-09-05

### 4.2 异类一：`_dedup_repeat` 借住，应归文本工具层

- 证据：`_dedup_repeat(answer_handler.py:65-98)` 是纯文本句子频率处理，零 agent 依赖（仅用 `re/Counter/logger`）；同类函数 `format_tool_call_markup` 已在 `app/utils/text_utils.py:160`，且 `handle_answer` 本人就在 L159-160 调用它处理 content/reasoning。
- 判定：两处文本处理分居两文件，同类未集中。按复用优先，应并入 `text_utils.py`，`answer_handler` 改 import 调用，逻辑逐行复制零改。

### 4.3 异类二：终态分产 5 文件 12+ 处，应收口 step_emitter

- 证据（`FinalStep(` 全仓 grep）：
  - `answer_handler.py:130/150/191/230`（4 处：error/unknown/空转终止/正常）
  - `action_handler.py:603`（1 处：return_direct）
  - `react_loop.py:95/125/152/186/212`（5 处：循环级终态）
  - `react_step.py:392/443`（2 处）
  - `agent_runner.py:398/444`（2 处：任务级兜底）
- 判定：同类（终态声明）散落 5 文件。2026-09-03 badge 修复已证明 `set_failed` 与 `emit_final_with_stats` 顺序敏感（先设 FAILED 再 emit，否则 `final_status=executing` 卡 badge），顺序敏感逻辑散落多处必漏。应集中到 `step_emitter.py`（`emit_final_with_stats` 已在 L59）新增 `emit_completed_final / emit_failed_final` 两个工厂，各处改调入厂（细则见 8.2）。`react_loop/agent_runner` 的循环/任务级兜底与 handler 的轮级终态分层不同，首批只收 handler 侧 5 处（同层同类），循环/任务级不动（YAGNI）。

### 4.4 异类三：空转计数器跨文件直写 7 处，应单立 owner

- 证据（`_consecutive_reasoning_only` 全仓 grep）：定义 `base_agent.py:79`（初值 0）；直写 7 处——`action_handler.py:522/586`（只归零）+ `answer_handler.py:121/140/165/217`（归零）+ `answer_handler.py:187`（唯一 `+=1`）。
- 判定：跨模块共享可变状态无单一 owner。07-17 为它连打 3 补丁（计数修正 L5、去重升级 L6、不变量声明 L4/L121/L140/L165/L217 注释）即实证：谁都能写=谁都可能漏。应新建 `reasoning_guard.py` 收口 `note_progress / note_reasoning_only` 两个入口作为唯一写者，两 handler 只调入口不直写字段（入口签名以 8.3 为准）。`REASONING_ONLY_MAX_ROUNDS=3` 常量随迁（`answer_handler.py:62`）。

---

## 五、处理方案（先复制后修改，逻辑零改）

### 5.1 文本工具归位

| 步骤 | 动作 | 验证 |
|------|------|------|
| 1 | `_dedup_repeat` 逐行复制进 `app/utils/text_utils.py` | py_compile |
| 2 | `answer_handler.py` 删 L65-98，改 `from app.utils.text_utils import format_tool_call_markup, dedup_repeat`（去下划线转公有，定案见 8.1） | py_compile |
| 3 | 回归：answer 去重单测 + 全量 pytest | PASS |

### 5.2 终态工厂集中（handler 侧 5 处）

| 步骤 | 动作 | 验证 |
|------|------|------|
| 1 | `step_emitter.py` 新增 `emit_completed_final(step, response, reasoning="")` / `emit_failed_final(step, response, error_type="", error_message="", reasoning="")`（签名以 8.2 为准；仅 failed 工厂内封装 `set_failed` 先行，completed 沿用 dispatch 外层置状态） | py_compile |
| 2 | `answer_handler.py:130/150/191/230` + `action_handler.py:603` 改调入厂（①②删延迟 import + set_failed，③补 09-03 顺序，④⑤换 completed 工厂） | py_compile |
| 3 | 回归：终态单测（completed/failed/cancelled）+ badge E2E | PASS |

### 5.3 防御状态单立 owner

| 步骤 | 动作 | 验证 |
|------|------|------|
| 1 | 新建 `reasoning_guard.py`：迁计数读写 7 处语义（`+=1/>3终止/余者归零`不变量照搬注释 L4） | py_compile |
| 2 | 两 handler 7 处直写改调入口；`base_agent.py:79` 字段保留（guard 读写该字段，存量初始化不动，防外部测试直读断裂） | py_compile |
| 3 | 回归：reasoning-only 终止单测（第 4 轮终止）+ 全量 pytest | PASS |

前置：三项互无依赖，可并行；对外 import 路径保持兼容（`handlers/__init__.py` 重导出不动）。改名 `answer→response` 作废（见 9.3：单函数文件直用函数名更名副其实）。—— 小健-2026-09-05

---

## 六、验证标准

1. `py_compile` 逐文件通过（先复制后修改铁律）。
2. 第 3 阶段 467 用例集全过（11+33+336+83+4，2 基线既有失败除外）。
3. 行为零退化抽查：配额失败 badge=failed、空转第 4 轮终止、去重≥250字触发、三分支执行语义逐字保留。

---

## 七、结论

不动 handle_answer 分支结构；只做三件同类集中事：**文本工具归位（5.1）+ 终态工厂集中（5.2）+ 防御状态单立 owner（5.3）**。合计搬迁约 80 行，逻辑零改。以[8]为准执行（[7]v1.1 已对齐）。—— 小健-2026-09-05

---

## 八、实施代码 diff（可直接落地）—— 小健-2026-09-05

> 以下 diff 逐行对照当前本地代码（行号为 2026-09-05 11:03 实测），按"先复制后修改"顺序执行。新增代码一律带署名+日期注释。

### 8.1 文本工具归位：`_dedup_repeat` → `text_utils.py`

**依据**：`_dedup_repeat` 仅用 `re/Counter/logger`，零 agent 依赖；同类 `format_tool_call_markup` 已在 `app/utils/text_utils.py:160`。去下划线改公名，沿 `trust.py`（`extract_trust_path` 去下划线，见[3]2.1）既有惯例。

**步骤 1——复制**：`answer_handler.py:57-98`（3 常量 + `_dedup_repeat` 全文，逐字）追加到 `text_utils.py:206`（`format_tool_call_markup` 的 `return normalize_blank_lines(text)` 之后、`truncate_summary` 之前），并改两处：

```python
from collections import Counter  # 小健 2026-09-05：随 dedup_repeat 迁入（text_utils 原无此 import，见 L20-22）

REPEAT_CHECK_MIN_LEN = 250     # 小健 2026-09-05：从 answer_handler.py:58 迁移，逐字
SENTENCE_MIN_REPEAT = 3        # 小健 2026-09-05：从 answer_handler.py:59 迁移，逐字
DUP_RATIO = 0.5                # 小健 2026-09-05：从 answer_handler.py:60 迁移，逐字


def dedup_repeat(content: str) -> str:  # 小健 2026-09-05：原 answer_handler._dedup_repeat 去下划线转公有，函数体逐字复制（含 L97 logger.warning）
    ...函数体与 answer_handler.py:65-98 逐字一致...
```

`__all__`（`text_utils.py:223-231`）追加 `"dedup_repeat",` 一行。

**步骤 2——删源改调**（`answer_handler.py`）：

```diff
-import re
 import time
-from collections import Counter
 from typing import Dict
 ...
-from app.utils.text_utils import format_tool_call_markup
+from app.utils.text_utils import format_tool_call_markup, dedup_repeat  # 小健 2026-09-05：去重函数归位文本层
 ...
-# ── 重复检测(版本2026-07-17: 句子频率法替代固定chunk) ──
-REPEAT_CHECK_MIN_LEN = 250     #（L58-60 三常量删除；L62 REASONING_ONLY_MAX_ROUNDS 留给 8.3，见↓注）
 ...
-REASONING_ONLY_MAX_ROUNDS = 3   # ← 不删，此行随 8.3 迁 reasoning_guard，本节保留
 ...
-def _dedup_repeat(content: str) -> str:  # L65-98 整函数删除（已逐字迁入 text_utils.dedup_repeat）
 ...
-        _deduped = _dedup_repeat(reasoning)   # L186
+        _deduped = dedup_repeat(reasoning)     # 小健 2026-09-05
 ...
-            deduped = _dedup_repeat(content)  # L224
+            deduped = dedup_repeat(content)   # 小健 2026-09-05
```

（`import re / from collections import Counter` 在本文件仅 `_dedup_repeat` 使用——全函数 grep 确认，删后无残留引用；`REASONING_ONLY_MAX_ROUNDS` 留给 8.3。）

### 8.2 终态工厂集中：`step_emitter.py` 新增两工厂，handler 侧 5 处改调

**依据**：09-03 铁律——`set_failed` 必须先于 `emit_final_with_stats`，否则 `build_final_stats_step` 读到 `EXECUTING` 致 badge 卡 running。顺序敏感逻辑散 5 处必漏，收口一处。

**步骤 1——新增**（`step_emitter.py:65` 后，`_get_tracker` 之前）：

```python
    def emit_completed_final(self, step, response, reasoning=""):
        """终态工厂(completed) — 小健 2026-09-05：收口 handler 侧 2 处 completed 分产；
        状态沿用既有机制（dispatch 外层 seen_types→set_completed，本工厂不提前置状态），行为逐字节等价"""
        return self.emit_final_with_stats(FinalStep(
            step=step, response=response, outcome="completed", reasoning=reasoning,
        ))

    def emit_failed_final(self, step, response, error_type="", error_message="", reasoning=""):
        """终态工厂(failed) — 小健 2026-09-05：收口 handler 侧 3 处 failed 分产；
        09-03 顺序铁律内聚于此：set_failed 先行再 emit，使 build_final_stats_step 读到 FAILED"""
        from app.services.agent.status_table import set_failed  # 延迟 import，随 answer_handler.py:127 既有惯例，防循环依赖 — 小健 2026-09-05
        set_failed(self.agent, error_message or response)
        return self.emit_final_with_stats(FinalStep(
            step=step, response=response, outcome="failed",
            error_type=error_type, error_message=error_message, reasoning=reasoning,
        ))
```

（`FinalStep` 构造均为 kwargs，五个既有用例 `answer:130/150/191/230 + action:603` 参数全覆盖；`react_loop / react_step / agent_runner` 的循环·任务级兜底不动——分层不同，YAGNI。）

**步骤 2——5 处改调**：

```diff
# ① answer_handler.py:127-134（error 分支：删延迟 import + set_failed，入厂）
-        from app.services.agent.status_table import set_failed
-        set_failed(agent, content)
         yield agent._step_emitter.emit(ThoughtStartStep(step=step))
-        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
-            step=step, response="任务执行失败",
-            outcome="failed", error_type=err_type, error_message=content,
-        )):
+        for _s in agent._step_emitter.emit_failed_final(
+            step=step, response="任务执行失败", error_type=err_type, error_message=content,
+        ):  # 小健 2026-09-05
             yield _s

# ② answer_handler.py:147-155（unknown 分支：同上形状）
-        from app.services.agent.status_table import set_failed
-        set_failed(agent, f"LLM返回未知响应类型: {parsed_type}")
         yield agent._step_emitter.emit(ThoughtStartStep(step=step))
-        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
-            step=step, response="任务执行失败",
-            outcome="failed", error_type="unknown_response",
-            error_message=f"LLM返回未知响应类型: {parsed_type}",
-        )):
+        for _s in agent._step_emitter.emit_failed_final(
+            step=step, response="任务执行失败", error_type="unknown_response",
+            error_message=f"LLM返回未知响应类型: {parsed_type}",
+        ):  # 小健 2026-09-05
             yield _s

# ③ answer_handler.py:191-197（空转终止分支：原无 set_failed，入厂后顺带补齐 09-03 顺序——同根 badge 隐患的增强，
#    非退化：dispatch 外层原就会按 outcome=failed 置 FAILED，终态不变；仅 emit 时刻 final_status 由失真变准确，E2E 验证 badge）
-            for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
-                step=step,
-                response="模型反复思考未产出有效结果，任务已终止（疑似陷入无效循环）",
-                reasoning=_deduped,
-                outcome="failed",
-            )):
+            for _s in agent._step_emitter.emit_failed_final(
+                step=step,
+                response="模型反复思考未产出有效结果，任务已终止（疑似陷入无效循环）",
+                reasoning=_deduped,
+            ):  # 小健 2026-09-05：error_type/message 缺省空串，set_failed 取 response 兜底
                 yield _s

# ④ answer_handler.py:230-234（正常 answer）
-    for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
-        step=step, response=content,
-        outcome="completed", reasoning=reasoning,
-    )):
+    for _s in agent._step_emitter.emit_completed_final(
+        step=step, response=content, reasoning=reasoning,
+    ):  # 小健 2026-09-05
         yield _s

# ⑤ action_handler.py:603-607（return_direct）
-        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
-            step=step, response=orchestration.get("return_direct_message", ""),
-            outcome="completed", reasoning="",
-        )):
+        for _s in agent._step_emitter.emit_completed_final(
+            step=step, response=orchestration.get("return_direct_message", ""), reasoning="",
+        ):  # 小健 2026-09-05
             yield _s
```

### 8.3 防御状态单立 owner：新建 `reasoning_guard.py`

**依据**：`_consecutive_reasoning_only` 定义 1 处（`base_agent.py:79`）+ 直写 7 处（action 2 处只归零：L522/L586；answer 5 处：L121/L140/L165/L217 归零 + L187 唯一 `+=1`）。07-17 三补丁即"人人可写=人人可漏"实证。

**步骤 1——新建** `backend/app/services/agent/reasoning_guard.py`（目录论证沿[3]4.8：与 `message_builder` 等 LLM 交互层同层平铺，不进 `handlers/`）：

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建：空转防御单一 owner，收口 action/answer 两文件 7 处 _consecutive_reasoning_only 直写（不变量照搬 answer_handler 注释：仅 reasoning-only 累加、余者归零）
"""reasoning_guard — reasoning-only 空转防御（计数单一写者）

作用对象是跨轮空转计数，与 message_builder 同属 LLM 交互层，平铺于 app/services/agent/。
base_agent.py:79 字段初始化保留（外部测试可能直读），本模块为唯一写者。 — 小健 2026-09-05
"""

REASONING_ONLY_MAX_ROUNDS = 3  # 小健 2026-09-05：从 answer_handler.py:62 迁移，逐字（连续容忍 3 轮，第 4 轮终止）


def note_progress(agent):
    """非 reasoning-only 进展：归零空转计数 — 小健 2026-09-05（收口 6 处归零直写）"""
    agent._consecutive_reasoning_only = 0


def note_reasoning_only(agent):
    """reasoning-only 一轮：累加；超限返回 True（调用方走终止分支） — 小健 2026-09-05（收口唯一 +=1）"""
    agent._consecutive_reasoning_only += 1
    return agent._consecutive_reasoning_only > REASONING_ONLY_MAX_ROUNDS
```

**步骤 2——7 处改调**：

```diff
# action_handler.py 两处（L522 空名异常 / L586 工具执行后）+ answer_handler.py 四处（L121 error / L140 unknown / L165 真空 / L217 正常answer）：
-        agent._consecutive_reasoning_only = 0  # 各处原注释保留
+        note_progress(agent)  # 小健 2026-09-05：空转计数唯一写者收口（各处原行尾注释如L522归零防残留缀回行尾，语义不变）
# 各文件头加：from app.services.agent.reasoning_guard import note_progress, note_reasoning_only  # 小健 2026-09-05

# answer_handler.py:187-188（唯一累加处）：
-        agent._consecutive_reasoning_only += 1
-        if agent._consecutive_reasoning_only > REASONING_ONLY_MAX_ROUNDS:
+        if note_reasoning_only(agent):  # 小健 2026-09-05
# L189/L201 两处 logger f-string 内对该字段的只读引用保留（读不破坏单一写者）。
# answer_handler.py:62 常量行删除（已迁 guard）；8.1 的 REPEAT_* 三常量删除（已迁 text_utils）。
```

**步骤 3——联动**：`FUNCTIONS.md` 登记 `dedup_repeat / emit_completed_final / emit_failed_final / note_progress / note_reasoning_only`（先查后建：grep 确认无重名公用函数——`dedup_repeat` 全仓仅 answer 两处调用，`note_*` 无撞名）。回归跑六.2 的 467 用例集 + E2E（配额 badge / 空转第 4 轮终止 / 去重触发）。—— 小健-2026-09-05

---

## 九、check_safety_and_confirm 门禁职能与拆出方案—— 小健-2026-09-05

### 9.1 它是干嘛的：执行前门禁（L266-497，约 230 行）

`check_safety_and_confirm(agent, all_calls, step, fc_context, _out, _denied_out)` 是 async generator，逐个 call 过三道闸，产出两份名单：

| 闸口 | 逻辑（action_handler.py 行号） | 出口 |
|------|-------------------------------|------|
| ①信任预查 | `resolve_skip`（L291，会话信任豁免）→ `check_before_execute`（L293） | 信任命中则跳确认 |
| ②安全分级 | `blocked`（L298-305）→ yield error + 入 `_denied`，`continue` 不终止整批 | 拦截转 LLM 历史换方案 |
| ③确认三汇合 | bypass-S1 等待（L348-409）/ 真 HITL 等用户（L411-467）/ safe 直通（L469-485），每路汇合 `run_sandbox_gate`（L396/L460/L481） | 通过进 `_out`，拒绝/超时进 `_denied` |

协议：事件 `async for` 透传给调用方 yield；结果经 `_out`（放行）/ `_denied_out`（拦截三元组）回传。拒绝≠失败，不设终态（见 L268-272 注释）。—— 小健-2026-09-05

### 9.2 与 handle_action 的关系：唯一前后脚

全仓 grep `check_safety_and_confirm` 22 命中中，真实调用点仅 1 处：`handle_action` L545（`async for event in check_safety_and_confirm(...)`）。其余为注释、`sandbox_gate.py` 的 DRY 来源说明、`tool_facade.py:128` 的"同源"注释（未直调）。即：**门禁只为编排打工，编排只调这一次门禁**。—— 小健-2026-09-05

### 9.3 拆出方案：整搬 `safety_gate.py`

- 可拆：已是模块级函数、无闭包捕获（08-25 沙箱闭包已拆 `sandbox_gate.py`），整搬 L266-497 逐字 + 随迁 import（trust/safety/hitl/sandbox/status/steps/constants），`action_handler.py` 改 1 行 import。`fc_context` 形参虽当前未用（透传位），照搬不删（YAGNI，不顺手精简）。
- 改名成立条件：搬完后 `action_handler.py` 只剩 `handle_action` 一个函数，方配改名 `handle_action.py`；`answer` 侧待 8.1 迁出 `dedup_repeat` 后只剩 `handle_answer`，方配改名 `handle_answer.py`。两改名附带全仓 import 联动（`handlers/__init__.py` + `react_dispatch.py:17-19` + 测试直引），与真拆同批做，不单独做 cosmetic 改名。
- 备选名如不用 `safety_gate.py`，`hitl_gate.py` 亦可（门禁=安全+HITL+沙箱三合一，`safety_` 覆盖面更全，推荐前者）。
- 取代说明：本节"单函数文件直用函数名"取代五.前置中的 `response_handler` 改名动议——`handle_answer.py` 比 `response_handler.py` 更名副其实，后者作废。—— 小健-2026-09-05

---

## 十、TDD实施计划（承[7]第八章体例，一代码一完整阶段）—— 小健-2026-09-05

> 体例沿 [7]8.2-8.3：**一个代码一个阶段、走完五步独立 commit 才进下一个，禁止混杂**；TDD 测试仅验证用不进 commit（AGENTS.md 铁律）；备份落 `backup/`；改名用 `git mv`（blame 不断）；删模块不留垫片。
> 五步模板即 [7]8.3（TEST红→BACKUP→CODE→TEST绿→COMMIT），本章不复述，只列每阶段的红灯断言与搬迁清单。

### 10.1 一代码一阶段总表

| 阶段 | 代码（拆分对象） | 内容 | 来源 |
|------|----------------|------|------|
| 第一阶段（10.3） | `answer_handler.py`（235行） | 三件集中（8.1/8.2/8.3）+ 余部改名 `handle_answer.py` | 本报告八章 |
| 第二阶段（10.4） | `action_handler.py`（608行） | 门禁拆出 `safety_gate.py` + 余部改名 `handle_action.py` | 本报告九章 |

### 10.2 引用面实测（2026-09-05 11:29，红灯与联动依据）

| 引用方 | action 侧 | answer 侧 |
|--------|-----------|-----------|
| 生产代码 | 仅包导入 2 处（`handlers/__init__.py:9` + `react_dispatch.py:17` 经包转引，模块直引 0 处） | 同左（`__init__.py:10` 同包） |
| 测试代码 | 约 120 处直引 `handlers.action_handler`（test_flow4/test_critical_flow_deep_bugs/test_target_derivation/test_reality_bugs/test_d2_*/test_flow_deep_bugs 等；含 `patch("...action_handler.execute_tools")` 旧路径，靠第 3 阶段兼容 import 存活） | 约 10 处直引 `handlers.answer_handler`（test_answer_handler_edge_cases/test_reasoning_only_defense 等；另 test_s2_s4_review_bugs 用 `inspect.getsource(check_safety…)` 锁门禁位置——注意这是 action 门禁的测试锚点） |

**兼容铁律**（由上表得出，两阶段共用）：新模块建成后，老模块保留同名 import 重导出（沿第 3 阶段"调用点零改动"家法），`patch(旧路径)` 才能继续工作；测试 import 改指新路径只在改名步（`git mv` 同提交）一次到位。

### 10.3 第一阶段：answer 三件集中 + 余部改名（完整流程）

**目标**：`answer_handler.py`（235行）→ 迁出文本/终态调用/计数三异类，余部只剩 `handle_answer` 即 `git mv → handle_answer.py`，老名消亡不留垫片。
**来源**：`_dedup_repeat`（L65-98）+ 5 处终态调用（L130/150/191/230）+ 计数直写 5 处（L121/140/165/187/217）+ 常量（REPEAT_* / REASONING_ONLY_MAX_ROUNDS）。

1. **TEST（红）**：新 import 断言三组——`from app.utils.text_utils import dedup_repeat` / `agent._step_emitter.emit_failed_final` 存在 / `from app.services.agent.reasoning_guard import note_progress`——模块方法均不存在→必失败（证明测试锁定新地址）。
2. **BACKUP（备份）**：`answer_handler.py` + `step_emitter.py` + `text_utils.py` 整份→`backup/20260905-answer_focus/` + `md5.txt`。
3. **CODE（搬）**（一阶段内按序，三搬互不依赖但同文件串行）：
   - 搬一：8.1（dedup→text_utils，改 2 处调用点 L186/L224）；
   - 搬二：8.2 的 answer 侧 4 处（①②④入厂 + ③补顺序，L127-134/L147-155/L191-197/L230-234）；
   - 搬三：8.3 的 answer 侧 5 处直写改调 + 删两常量块；
   - 改名：余部只剩 `handle_answer` 时 `git mv answer_handler.py handle_answer.py`，改 `handlers/__init__.py:10` + `react_dispatch.py:17-19` 转引，测试直引（test_answer_handler_edge_cases/test_reasoning_only_defense）改指新路径同提交。
4. **TEST（绿）**：行数账（迁出≈70行 = 三新址增量 ± import）；`pytest test_answer_handler_edge_cases.py test_reasoning_only_defense.py test_react_cycle_split_regression.py` + 六.2 基线子集全绿；diff 逐块对照备份。
5. **COMMIT**：`refactor:answer_handler.py三件集中并改名handle_answer.py - 小健-2026-09-05`（仅生产文件，测试文件禁入）。

### 10.4 第二阶段：action 门禁拆出 + 余部改名（完整流程）

**目标**：`action_handler.py`（608行）→ 门禁整搬 `safety_gate.py`，余部只剩 `handle_action` 即 `git mv → handle_action.py`，老名消亡不留垫片。
**来源**：`check_safety_and_confirm`（L266-497）整函数 + 随迁 import（trust/safety/hitl/sandbox/status/steps/constants）；`fc_context` 透传形参照搬不删。

1. **TEST（红）**：新 import 断言——`from app.services.agent.handlers.safety_gate import check_safety_and_confirm` 不存在→必失败；另锁 `test_s2_s4_review_bugs.py:242`（`inspect.getsource(check_safety…)`）改指新模块后跑仍失败（缺模块）。
2. **BACKUP（备份）**：`action_handler.py` 整份→`backup/20260905-safety_gate/` + `md5.txt`。
3. **CODE（搬）**：
   - 提一：新建 `handlers/safety_gate.py` 放 `check_safety_and_confirm`（逐字复制，`sandbox_gate` 同族目录）；
   - 瘦身：`action_handler.py` 删 L266-497 改 1 行 import；`handle_action` 内 L545 调用改调新路径；8.2⑤ return_direct（L603-607）换 `emit_completed_final`（第一阶段已建，一步到位）；8.3 的 action 侧 2 处（L522/L586）改 `note_progress`；
   - 改名：余部只剩 `handle_action` 时 `git mv action_handler.py handle_action.py`，改 `handlers/__init__.py:9` + `react_dispatch.py:17-19` 转引；测试直引与 `patch("...action_handler.execute_tools")` 等旧路径改指新路径同提交（量最大，约 120 处，见 10.2）；
   - 兼容：`safety_gate` 建成后老模块留 1 行重导出至改名提交（改名即删，不留垫片）。
4. **TEST（绿）**：行数账（迁出 232 行 = safety_gate 增量 ± import）；`pytest test_flow4.py test_critical_flow_deep_bugs.py test_d2_same_name_tool_fix.py test_s2_s4_review_bugs.py test_target_derivation.py` + 六.2 基线子集全绿 + bypass/HITL E2E 各一（门禁是高危区，9-04 DRY 曾致 bypass 乱序回归）；diff 逐块对照备份。
5. **COMMIT**：`refactor:action_handler.py门禁拆出safety_gate并改名handle_action - 小健-2026-09-05`（仅生产文件，测试文件禁入）。

### 10.5 顺序与依赖

第一阶段（answer）→ 第二阶段（action），硬依赖一条：10.4 的 return_direct 与计数两改调消费 10.3 新建的工厂与 guard，先建后用一步到位；其余无交叉。两阶段各独立 commit 即天然回滚位，坏即 `revert` 单段。

### 10.6 与[7]关系（以[8]为准）

[7]v1.1 已同步修改对齐（2.3 两 verdict 改执行、4.6 改门禁先行），本章两阶段即执行案，无冻结。—— 小健-2026-09-05


