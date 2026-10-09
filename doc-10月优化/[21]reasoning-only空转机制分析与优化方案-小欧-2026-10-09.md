# reasoning-only 空转重试机制分析与优化方案

**编写人**: 小欧
**编写时间**: 2026-10-09 19:40:35
**版本**: v1.0

---

## 一、方案（北京老陈定稿）

### 1.1 需求原文（**v1.1 按实现修订：门槛由"2 次"改为"一旦检测到"**）

在检测到了 reason-only 的时候：

1. **不注入**
   ```
   {"role":"assistant", "content":"", "reasoning_content": RC, "_temp_reasoning":True}
   ```
   （content 必须空、键名不可动，只截值）

2. **而是注入**
   ```
   {"role":"user", "content":"原始user消息 + 警告信息"}
   ```

警告信息写：**"上一次你只是重复推理而没有采取行动, 下一次必须采取行动或者回答"**

### 1.2 落地的消息形态

**第 1 次起（计数 ≥ 1，即一检测到就注入）**：删掉 assistant 推理回灌，改为注入一条 user 消息 —

```json
{
  "role": "user",
  "content": "<原始user消息>\n<system-reminder>\n上一次你只是重复推理而没有采取行动, 下一次必须采取行动或者回答\n</system-reminder>"
}
```

| 项 | 决定 |
|---|---|
| 触发轮次 | **计数 ≥ 1（一检测到即注入）** |
| 原始 user 消息 | 取会话首条 `role=="user"`（即任务提示） |
| 警告文案 | 原文照用，不加追加 |
| 是否挂 `_temp_` 标记 | 不挂（按普通 user 消息常驻，反复提醒直到模型行动） |
| assistant 侧 | 只保留 `ThoughtStep` 事件供前端展示，不进 LLM 上下文 |
| 好/坏分支 | 作废，两分支行为相同（原先重复最严重那次反倒什么都不注入，已修） |
| 第 4 轮 | 计数 >3 → `emit_failed_final` 硬终止（兜底不变） |

---

## 二、现状分析

### 2.1 机制位置

代码中**不存在** `thought_only` 标识符，该机制正式名称是 **reasoning-only**，核心标识 `_consecutive_reasoning_only`。

| 要素 | 位置 | 值 |
|---|---|---|
| 阈值 | `agent/reasoning_guard.py:10` | `REASONING_ONLY_MAX_ROUNDS = 3` |
| 计数唯一写者 | `reasoning_guard.py` 的 `note_progress()` / `note_reasoning_only()` | — |
| 字段初始化 | `base_agent.py:79` | `= 0` |
| 唯一累加点 | `handle_answer.py:171` | — |
| 归零点 | `handle_action.py:338,435`；`handle_answer.py:103,130,149,197` | 共 6 处 |

阈值语义：连续容忍 3 轮，**第 4 轮终止**（判据 `> 3`）。硬编码，未进 `settings_registry`。

触发条件（`handle_answer.py:169`）：`if not content and reasoning` —— 既没给最终答案、也没调工具，只吐了推理。

### 2.2 现状问题一：回灌的推理模型永远拿不到两条对比

原实现在每轮把 LLM 自己的 reasoning 以 `_temp_reasoning` 标记的 assistant 消息回灌 context，
动机是"保留推理链供续写"。**该动机从未达成**：

- `message_builder.py:335-338` 的"发送即清"在**每次发送后**立即把 `_temp_*` 消息从源剔除
- 注入发生在响应处理阶段（`handle_answer.py`），发送在下一轮（`react_step.py:330`）
- 故注入的 A_n 在第 n+1 轮被拷入 messages、随即清除，**第 n+2 轮已不存在**

**结论：每轮视野里只有自己上一轮那一条推理，模型永远拿不到两条可对比。**
原设计指望的"让模型看到前后两次推理挨在一起从而察觉异常"**在时序上不可能发生**。

### 2.3 现状问题二：回灌代价是实的

- 单条 DeepSeek reasoning 可达 **20K 字符**（`message_builder.py:33` 注释）
- `_cap_temp_history` 上限仅 **50000 字符**（`message_builder.py:343`）—— 两条就可能吃满预算
- 模型看到自己上一轮的完整 CoT 原样奉还，最可能被强化的行为是**继续思考**，与打破空转**方向相反**

### 2.4 现状问题三：另有一条重复警告路径（B3）

排查发现 reason-only 实际触发**两条**警告注入，条件完全等价：

| 项 | handle_answer 路径 | B3 路径（`react_step.py:515-532`） |
|---|---|---|
| 触发条件 | `not content and reasoning` | `type=="answer"` 且 `not _content` 且 `reasoning` 非空 —— **等价** |
| 执行位置 | `react_dispatch.py:86` → handler | `react_step.py:517`，在 `_dispatch_handler`（`:629`）**之前** |
| 谁先 | 后 | **先** |
| 注入内容 | assistant，content 空，承载自身推理 | assistant，**content = `[Observation] 警告…`** |
| 角色语义 | 承载模型自己的推理，正确 | **把系统警告伪装成"模型自己说的话"，错误** |

B3 另有一处缺陷：其幂等检查（`:524` 查重后跳过）因"发送即清"跨轮恒不命中 —— 下一轮 history 已无它，
查重永远查不到自己 → 该守卫**从未真正生效**，与注释宣称的效果不符。

**必须一并删除**，否则一轮收到两条警告，本方案的"一条 user 警告"落空。

### 2.5 现状问题四：无任何主动信号

reason-only 路径**不发任何 user 消息**：

| 分支 | 注入 history 的消息 | user 消息 |
|---|---|---|
| 好分支无重复（`:179-191`） | 1 条 assistant（自身推理） | 无 |
| 坏分支有重复（`:192-194`） | 0 条，仅 `logger.warning` | 无 |

模型面对自己刚说的推理，**无从判断这是异常**，也无人告知这是第几次、还剩几次。

---

## 三、现状速查：消息时序

`RCₙ` = 第 n 轮推理正文内容（占位符，非键名）；`⟨HISTORY⟩` = system + user 原始提问 + 若干轮工具调用/结果。

| 轮次 | messages 列表构成 | 可见性 |
|---|---|---|
| 第 1 次空转 | `⟨HISTORY⟩` + `{assistant,"",reasoning_content:RC₁}` | RC₁ 注入 |
| 第 2 次空转 | `⟨HISTORY⟩` + `{assistant,"",reasoning_content:RC₂}` | **RC₁ 已被"发送即清"剔除** |
| 第 3 次空转 | `⟨HISTORY⟩` + `{assistant,"",reasoning_content:RC₃}` | RC₂ 已被剔除 |
| 第 4 次 | 计数 4 > 3 → 任务失败终止 | — |

**每轮只有一条推理，从无两条同框**（即 2.2 的直接证据）。

---

## 四、需要修改的代码

### 4.1 `backend/app/services/agent/reasoning_guard.py`

**性质**：计数单一写者，空转防御 single owner（2026-09-05 小健建立）。

**修改要点**：

1. **新增常量** `STAGNATION_WARNING` —— 警告文案（`<system-reminder>` 包裹，原文照用）
2. **新增 `logger`** —— 该模块原无 logger，需 `import logging` + `logging.getLogger(__name__)`
3. **新增函数** `notify_stagnation(agent)` —— **不设门槛**，一检测到即注入
   - 取会话首条 `role=="user"` 的 content（`init_history` 固定顺序为 system → task，故首条 user 即任务提示）
   - 组装 `f"{task}\n{STAGNATION_WARNING}"`，`task` 为空时只出警告段
   - **不挂 `_temp_` 标记**（常驻，反复提醒）
   - 打一条 warning 日志

**不变式**：本模块仍为**唯一**计数写者，不破坏 2026-09-05 建立的收口结构。

> 注：初稿曾设计 `WARN_FROM_ROUND = 2` 门槛（第 2 次起才警告），**最终定稿取消门槛** —— 一检测到即注入。

### 4.2 `backend/app/services/agent/handlers/handle_answer.py`

**性质**：reason-only 分支宿主，唯一的 `note_reasoning_only()` 调用点。

**修改要点**：

1. **删除 `:182-188` 整段 assistant 回灌**
   删掉整个 `conversation_history.append({... "reasoning": _deduped, "reasoning_content": _deduped, "_temp_reasoning": True})`。
   理由见 2.2 / 2.3。

2. **`:171` 之后插入 `notify_stagnation(agent)` 调用**
   位置：`if note_reasoning_only(agent):` 判定为 False（未超限）之后、进入去重分支之前。

3. **`:189` 的 `ThoughtStep` 补真实 reasoning**
   原为 `ThoughtStep(step=step, content=_deduped, reasoning="")` —— `thought_step.py:29` 的
   `_reasoning` 是独立字段，`_extra_fields` 会同时输出 `thought` 与 `reasoning`，
   故 `reasoning=""` 会让前端拿不到推理内容（弄虚作假）。
   改为 `ThoughtStep(step=step, content=_deduped, reasoning=_deduped)`。

4. **好/坏分支合并**
   原 `if _deduped == reasoning:` / `else:` 两分支作废 —— 两分支改后行为完全相同。
   顺带修掉一处反直觉缺陷：原先重复最严重那次（最需要警告）反倒什么都不注入。

5. **补充导入**
   `from ...reasoning_guard import notify_stagnation`，与 `:77` 现有导入同行，保持单一 import 点。

### 4.3 `backend/app/services/agent/react_step.py`

**性质**：单步处理；`:515-532` 是另一条空转警告注入。

**修改要点**：

删除 `:515-532` 整个注入块（`obs_text` 拼装 + `_temp_reasoning` 的 assistant append），**保留 `logger.warning`**。

理由见 2.4（三条：一条警告发两遍、角色语义错误、幂等守卫从未生效）。

**注意**：`else` 分支（`:533` 起处理 content 非空的情形）**不动**。

### 4.4 不改动的文件

| 文件 | 原因 |
|---|---|
| `utils/text_utils.py` | `dedup_repeat` 五重防误伤边界是验证过的资产，本方案不涉及其逻辑 |
| `settings/settings_registry.py` | 阈值配置化不在本次定稿范围内 |
| `config.py` | 同上 |

---

## 五、测试

改动落在既有文件 `backend/tests/test_react_cycle_split_regression.py`（非新建）：

| 用例 | 断言点 | 状态 |
|---|---|---|
| `test_single_step_reasoning_only_injects_user_warning` | 恰好注入 1 条含 `<system-reminder>` 的 user 警告；history 中无 `_temp_reasoning` 的 assistant 消息；任务仍 EXECUTING | 已实施 |
| `test_single_step_reasoning_only_warning_per_round` | 连续两轮各注入 1 条；警告消息不挂 `_temp_`（常驻） | 已实施 |
| `test_single_step_b3_reasoning_warning_idempotent` | **已删除** —— 断言的正是被删的 B3 注入块 | 已移除 |

**重要约定**：测试**不断言警告文案原文**。文案属可改内容，断言它会把测试绑死在措辞上；
测试只断言行为（注入 user 警告、角色正确、恰好一条、不回灌 assistant）。

**回归状态**：`test_react_cycle_split_regression.py` 35 passed；
更大范围回归（`-k "answer or react or reason or agent or guard or wire or b3 or cycle"`）
**未跑完即被中断**，故不能声称全量绿。

**注意**：`backend/tests/` 被 gitignore，测试改动不会入库。

---

## 六、方案有效性边界

本方案能**提高**模型主动结束的概率，但**不保证**必然终止 —— 最终仍有硬上限兜底（连续 3 轮即终止）。

三种可能结果：
1. **最优**：模型看到警告后直接给答案/调工具
2. **部分**：模型调整了但仍在推理 → 一两轮后触发硬终止（比现状略好，至少获得了明确信号）
3. **无效**：模型无视警告继续空转 → 与现状相同，硬终止兜底

**不应承诺**"加了警告就不会空转了"。真正收益是给模型一个此前完全没有的**显式信号与出路**。

### 已知的副作用（须知晓）

1. **上下文累积**：警告不挂 `_temp_`，故常驻。连续空转 3 轮会在上下文里累积 3 条「重发任务 + 警告」。
   若需只保留最新一条，须改为每轮替换而非追加 —— **当前实现为追加**。
2. **删回灌后模型看不到自己上一轮推理**：符合定稿意图（避免回灌强化空转），
   但确实丢掉了推理连贯性。该取舍未经真实 LLM 验证。
3. **`fix_thinking_messages` 是死代码**（`llm/reasoning.py:100` 定义并导出，但全仓无调用点）。
   本方案不依赖它；但"thinking 模型必须带 reasoning_content"这道保险目前**未接线**，
   现靠 `message_builder.py:330-332` 的出站收口恰好产出标准字段名。

---

**变更历史**:
- v1.0 (2026-10-09 19:40:35 小欧) 初版：按北京老陈定稿重写。此前 v1.0~v1.3 全部作废重写 —— 旧版把方案理解成"assistant 推理截断 500 字 + user 警告两条并行"，与定稿"直接不注入 assistant、只注一条 user 消息"不符。
- v1.1 (2026-10-09 20:30 小欧) 同步实现：①门槛由"第2次起"改为"一检测到即注入"（定稿后续明确）；②`ThoughtStep` 的 `reasoning` 由 `""` 补为真实推理（原值使前端拿不到推理，属弄虚作假）；③测试一节改为实际的既有文件改动，并明确"不断言文案原文"；④补记三条已知副作用。