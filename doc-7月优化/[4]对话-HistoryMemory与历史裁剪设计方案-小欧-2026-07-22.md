# 对话-HistoryMemory 与历史裁剪设计方案

> **编写人**: 小欧
> **创建时间**: 2026-07-22 18:30:00
> **更新时间**: 2026-07-22 17:35:08
> **版本**: v4.0
> 
> **核心定位**：History Memory（结构化记忆供给）是主，历史裁剪（T1/T3 压缩旧 tool 输出）是辅。先解决"LLM 每轮能看到决策链"，再解决"窗口不够用时腾空间"。

---

## 一、问题与需求

### 1.1 问题

#### 问题 1：单条 observation 体积巨大，撑爆窗口

我们的工具 formatter 虽然做了行×列收口，但上限仍然巨大：

| 工具 | 收口上限 | 单条最大体积 |
|------|---------|------------|
| readtext | 200行 × 1000字符/行 | 200K chars = 50K tokens |
| grep | 200行 × 150字符/行 | 30K chars = 7.5K tokens |
| shell | 200行 × 1000字符/行 | 200K chars = 50K tokens |
| fetchpage | 200行 × 500字符/行 | 100K chars = 25K tokens |

一条 readtext 就吃掉窗口的 25%（按 200K 窗口算）。Agent 跑 5 轮，其中 3 轮 readtext + 2 轮 shell，**光 observation 就 250K tokens，已经超出窗口**。LLM 窗口 900K 但我们的 `MAX_CONTEXT_TOKENS` 默认只有 200K（留余量防 LLM 注意力分散），实际更紧。

**为什么不能靠收口解决？** 收口是工具层的事，裁剪是对话层的事。收口改小（比如 50 行）会丢工具返回的信息完整性，裁剪是在保留完整信息的****前提下做二次压缩。

#### 问题 2：简单从最旧删，丢掉决策链

当前 `trim_history` 的裁剪逻辑是**从最新往最旧保留，超预算就丢弃**。效果是：

```
被保留的：最近几轮的 tool 原始输出（几百 K chars）
被丢弃的：早期 assistant 的 thought 和决策（为什么选这个工具、得出了什么结论）
```

**丢的是值钱的，留着的是笨重的。** 下一轮 LLM 看不到"之前已经做了什么、为什么这么做"，于是：
- 重复调已经调过的工具
- 偏离任务目标
- 重新分析已经分析过的文件

#### 问题 3：LLM 注意力被大量 tool 原始输出稀释

即使不超窗口，给 LLM 的 messages 列表里大部分是 tool 的 raw content：

```
一条 assistant 消息（几百字符）→ 一条 tool 消息（几万字符）
```

LLM 的注意力被稀释到几百 K 的工具输出细节中，**真正重要的推理链反而占比极小**。表现：
- LLM 忘了初始任务目标（task prompt 被埋在后面）
- LLM 在工具输出中"迷路"，抓不住重点
- 越往后轮次，LLM 决策质量越差

#### 问题 4：没有"只看概要"的能力

OpenCode 和 Hermes 都有 **LLM 摘要压缩**——把旧历史用 LLM 重新总结为结构化概要，体积小、信息密度高。但我们没有这个能力（引入 LLM 摘要 = 额外 LLM 调用 = 成本翻倍 + 延迟增加）。

所以我们的裁剪只能靠：**纯字符串替换（工具摘要）** 和 **直接删消息**。必须用更聪明的策略来弥补没有 LLM 摘要的短板。

### 1.2 需求（从问题推导）

| # | 需求 | 对应问题 | 为什么必须 |
|---|------|---------|-----------|
| R1 | **主动压缩 tool observation** | 问题 1 | 窗口有限，observation 最大，必须优先压缩。不压缩就直接删，信息全丢 |
| R2 | **保推理链不丢** | 问题 2 | 删消息时 assistant 的 thought/answer 不能丢，否则 LLM 不知道任务上下文 |
| R3 | **LLM 每轮都能看到决策全景** | 问题 2+3 | 不是"保一部分"，而是让 LLM 始终能看到"做了什么→为什么→当前到哪了"的完整链 |
| R4 | **零额外 LLM 调用** | 问题 4 | 我们没有 LLM 摘要压缩的能力，所有操作必须是纯规则、纯字符串 |
| R5 | **有最后安全网** | 问题 1 | 窗口快爆时（>95%）得有紧急手段，不能坐等 API 413 错误 |

### 1.3 核心思想

**删之前把值钱的东西搬出来。**

旧消息中真正有价值的是**推理链和结论**（assistant 的 thought/answer），而 tool 返回的原始内容后续轮次不需要——LLM 需要时可重新调工具获取最新数据。

因此策略是**三管齐下**：

```
T1 工具摘要（50% 触发）
  └── 对 observation 做一行摘要 → 腾出空间，消息数不变
  └── 解决 R1（主动压缩 tool obs）
  └── 解决 R4（纯字符串替换，零 LLM 成本）

History Memory（每轮追加）
  └── 把推理链提取为结构化记忆注入独立 user 消息
  └── 解决 R2（保推理链）+ R3（决策全景）
  └── 解决 R4（纯规则，零 LLM 成本）

T3 紧急裁剪（95% 触发）
  └── 加深 T1 + 参数截断 + 删除最早消息
  └── 解决 R5（最后安全网）
  └── History Memory 不受影响，R2 仍然满足
```

---

## 二、术语说明：T1 / T3

本方案包含两个裁剪级别，按触发阈值编号：

| 级别 | 全称 | 触发时机 | 做什么 | 通俗理解 |
|------|------|---------|--------|---------|
| **T1** | Tier 1 — 工具摘要 | total > 窗口 50% | tool 观察结果内容 → 一行摘要，**不删消息** | **轻量：把大段工具输出压缩成一句话** |
| **T3** | Tier 3 — 紧急裁剪 | total > 窗口 95% | 加深 T1 + 参数截断 + **删消息**（保尾 3 轮） | **重度：窗口快爆了，删旧消息腾空间** |

**为什么没有 T2？** 之前方案[2]有过 T2（冷区合并），因为不可控放弃了。现方案只有 T1（轻量压缩）+ T3（重度裁剪），中间 50%~95% 只做 T1，不够时才触发 T3。

T1 和 T3 的设计细节见第四章和第五章。

---

## 三、两处借鉴 + 一处创新

### 2.1 借鉴 OpenCode

| 机制 | 用在哪 | 原始实现 |
|------|--------|---------|
| **Prune** 替换旧 tool output 为占位符 | T1 工具摘要（替换 obs content） | `compaction.ts` Prune |
| **tail_turns** 轮次保尾 | T3 裁剪保尾 KEEP_TAIL_ROUNDS=3 | `compaction.ts select()` |
| **splitTurn** 部分保留一轮 | T3 如果整轮太大，只保尾部几条 | `compaction.ts` L162-185 |
| **溢出回退** 裁了还不够→继续缩小保尾 | T3 的 KEEP_TAIL_ROUNDS 递减回退 | `compaction.ts` overflow 模式 |
| **PRUNE_MINIMUM=20K** 节省太少不执行 | T3 防抖动 | `compaction.ts` L36 |

### 2.2 借鉴 Hermes

| 机制 | 用在哪 | 原始实现 |
|------|--------|---------|
| **Pass2 工具感知摘要** | T1 工具摘要模板 | `context_compressor.py` L880-892 |
| **Pass3 截断 tool_call 参数** | T3 加深压缩 | `context_compressor.py` L894-918 |
| **should_compress 防抖动** 连续2次节省<10%跳过 | T3 防抖动 | `context_compressor.py` L728-748 |
| **413/overflow 回退 + compress + retry** | T3 溢出重试 | `conversation_loop.py` L2817-3024 |

### 2.3 我们自己创造

| 创新 | 说明 |
|------|------|
| **History Memory** | 从 Step 体系提取推理链注入独立 user 消息；区别于被动"日志"，是主动给 LLM 提供的结构化记忆——LLM 每轮都能从中"回想"起决策链（做了什么→为什么→结论） |
| **提取源头提升到 Step 级别** | 跟方案E（从 assistant message 提取）的区别：FC 模式下 Step 始终有内容，assistant message 可能为空 |

---

## 四、系统架构

```
每轮 ReAct 循环:
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: LLM 调用前                                          │
│   trim_history() — 检查是否需要 T1/T3                         │
│   inject_history_mem() — 把 History Memory 注入 user 消息     │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: LLM 返回后                                          │
│   解析 Step(thought/tool/answer)                              │
│   append_history_mem(step) — 追加一行到 History Memory        │
│   消息追加到 conversation_history                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 History Memory — 概念升级：从"日志"到"记忆"

**Context Log（旧）** = 被动追加的"记录"，写进去就完了，LLM 自己从长文本里找有用信息。

**History Memory（新）** = 主动提供的结构化"记忆"，每轮从 Step 体系提取 thought→action→result→answer，拼成一条 LLM 可以直接"回想"的决策链。不是"把历史写下来"，而是"让 LLM 每次都能看到自己已经做了什么、为什么、结论是什么"。

同一个实现机制，但**思考层次不同**：
| | Context Log | History Memory |
|--|-----------|---------------|
| **本质** | 低层次的日志记录 | 高层次的记忆供给 |
| **视角** | "写"的角度：追加内容 | "读"的角度：LLM 需要什么信息来续写 |
| **关注** | 不丢数据 | LLM 能否快速定位决策链 |
| **信息量** | 全量 step 内容 | 提炼过的结构（结论+关键参数） |

### 3.2 History Memory — 维护在哪、怎么注入

**维护位置**：在 `MessageBuilder` 中以 `history_mem: List[str]` 属性存在

**注入方式**：每次 LLM 调用前，在 `prepare_messages_for_llm()` 中插入一条独立的 `user` 消息，紧挨 system 之后：

```
发给 LLM 的 messages 列表:
[0] system (原始系统指令)
[1] user (History Memory)         ← prepare_messages_for_llm() 浅拷贝时插入
     [History Memory]
     #1 thought: 需要查看 config.py 的 timeout 设置
     #2 tool: readtext(config.py) → 看到 timeout=30
     #3 action: edittext(config.py) → timeout=30→60
     #4 answer: timeout 已修复，pytest 全部通过
[2] user (task prompt)
[3] assistant (tool_calls)
[4] tool (observation)
...
```

**为什么选 user 而不是 system**（北京老陈 2026-07-22 裁定）：
- `system` 角色语义是"不可违抗的指令"，History Memory 是对话历史的一部分，放 `system` 语义不当
- `user` 角色在训练时被赋予"需要处理的信息"的含义，History Memory 恰好是"需要 LLM 参考的决策链信息"
- DeepSeek 对 role 的敏感度低于 OpenAI，内容本身 > role 标签
- 详见文档末尾《关于 role 选择的分析》

### 3.3 History Memory — 追加内容

在 `react_cycle.py` Phase 2 处理每个 Step 后调用：

```python
def append_history_mem(step):
    if step.type == "thought":
        text = step.content[:80].replace("\n", " ")
        agent.history_mem.append(f"thought: {text}")
    elif step.type == "action":
        tool = step.tool
        params = _brief_params(step.params)  # 只取 path/code/command 等关键字段
        agent.history_mem.append(f"action: {tool}({params})")
    elif step.type == "observation":
        brief = _brief_observation(step.content)  # 前 60 字符，结果状态
        agent.history_mem.append(f"result: {brief}")
    elif step.type == "answer":
        text = step.content[:100].replace("\n", " ")
        agent.history_mem.append(f"answer: {text}")
```

**限制**：最多 500 行，超了从最早两行开始合并。

### 3.4 History Memory — 保护机制

History Memory 以独立 `user` 消息存在（紧挨 system 之后），在 `trim_history` 中通过以下机制保护：

1. **保尾定位跳过**：T3 保尾从末尾找第 3 个 assistant 消息，History Memory 是 user 消息，不会被纳入轮次计数
2. **system+user 锁死**：T3 裁剪的中间区是 system 之后、保尾区之前，而 History Memory 紧挨 system，属于中间区最旧的部分——但 History Memory 的 token 极小（数百字符），在"从最旧往最新保留"的扫描中，预算内一定能保留
3. **`_history_mem` 标记**：History Memory 消息带 `_history_mem=True` 标记，trim_history 遇到此标记强制保留

**万一被裁了怎么办？** History Memory 是**每轮重新注入**的。即使本轮被裁剪，下一轮 `prepare_messages_for_llm()` 会重新生成 History Memory 消息（从 `MessageBuilder.history_mem` 列表中提取最新 N 条）。因此 History Memory 实际是**逻辑持久**的——message_builder 的属性不随 trim_history 消失。

---

## 五、T1 工具摘要（50% 触发，必须做）

### 4.1 触发条件

```
粗估 tokens > MAX_CONTEXT_TOKENS × 0.50
```

### 4.2 做法

扫描 Warm + Cold 区的 tool 消息，将 content 替换为工具感知一行摘要。

不删消息，不破坏 FC 配对。

### 4.3 工具摘要模板

基于工具注册名：

| 工具 | 模板 | 示例 |
|------|------|------|
| readtext | `[readtext] {path} ({line_count}行)` | `[readtext] src/config.py (120行)` |
| listdir | `[listdir] {path} ({file_count}项)` | `[listdir] backend/app/ (48项)` |
| grep | `[grep] '{pattern}' in {path} ({match_count}个)` | `[grep] 'timeout' in src/ (3个)` |
| shell | `[shell] {truncated_cmd} → exit={code}` | `[shell] pytest tests/ → exit=0` |
| edittext | `[edit] {path} ({operation})` | `[edit] config.py (timeout=30→60)` |
| fetchpage | `[fetch] {domain} ({chars}字符)` | `[fetch] example.com (4,200字符)` |

**收益估算**：
- 原始 100 轮 readtext obs（1000行×100字符）：100×100K=10M chars=2.5M tokens
- T1 压缩后 100 轮 obs 摘要：100×80=8K chars=2K tokens
- 200 轮 T1 后 total（含 system+user+asst）：~336K chars=**84K tokens**，窗口 200K 仅占 **42%**

### 4.4 防重复压缩

每条 tool 消息加 `_compressed=True` 标记，已压缩的不再压缩。

---

## 六、T3 紧急裁剪（95% 触发，借鉴 OpenCode+Hermes）

### 5.1 触发条件

```
粗估 tokens > MAX_CONTEXT_TOKENS × 0.95
```

### 5.2 流程

```
T3 入口:
  1. [加深T1] 对尚未压缩的 obs 全部做工具摘要（确保每一条 obs 最小化）
  2. [Hermes Pass3] 截断旧 assistant 中 tool_call 参数 JSON
     args > 500 chars → 字符串字段截到 200 chars（保持 JSON 合法）
  3. [防抖动] 上次 T3 节省 < 10% → 跳过本次（Hermes should_compress）
  4. [保尾] 保尾 KEEP_TAIL_ROUNDS=3 轮完整 FC 对不动
     └─ 定位方式（借鉴方案[3]简化设计）:
          从消息列表末尾往前找第 3 个 assistant 消息，该消息及之后的内容
          全部保留（含中间穿插的 tool/user 消息）。不足 3 轮则不裁剪。
  5. [裁剪] 确定预算 = MAX_CONTEXT_TOKENS × 0.50
           锁定 system(1条) + 保尾区(第4步) 占用量，
           **从最旧往最新**扫描中间区（system 之后、保尾区之前）的消息，
           在预算内尽量保留，超预算则丢弃。
  6. [回退] 如果保尾 3 轮 + system 已超预算 → KEEP_TAIL_ROUNDS -= 1
          递减到 2 轮、1 轮，直到 budget > 0
  7. [溢出重试] 如果 LLM API 返回 413 → 触发 T3 后重试
  8. _rebuild_and_validate → _trim_fc_pairs 清理孤儿 FC 对
```

### 5.3 借鉴来源

| 步骤 | 借鉴自 | 原始机制 |
|------|--------|---------|
| 2. 参数截断 | Hermes Pass3 | `_truncate_tool_call_args_json()` args>500→200 |
| 3. 防抖动 | Hermes | `should_compress()` 连续 2 次 < 10% 跳过 |
| 6. 回退递减保尾 | OpenCode | `splitTurn()` 保不住→缩小范围 |
| 7. 溢出重试 | OpenCode+Hermes | overflow→compress→retry |
| 8. FC 配对修复 | Hermes | `_sanitize_tool_pairs()` |

### 5.4 防抖动细节

```python
if self._t3_savings_pct is not None and self._t3_savings_pct < 10:
    self._t3_ineffective_count += 1
else:
    self._t3_ineffective_count = 0

if self._t3_ineffective_count >= 2:
    logger.warning("[T3] 连续2次节省<10%, 跳过本次裁剪")
    return
```

`_t3_savings_pct = (裁剪前 token - 裁剪后 token) / 裁剪前 token × 100`

---

## 七、History Memory vs 其他压缩方式对比

| 对比 | OpenCode Process(LLM摘要) | Hermes _generate_summary(LLM) | 本方案 History Memory(纯自动) |
|------|--------------------------|------------------------------|-----------------------------|
| **成本** | 每次 1 次 LLM 调用 | 每次 1 次 LLM 调用 | **零** |
| **信息质量** | 高（NL 理解后的摘要） | 高（结构化摘要 + 迭代更新） | **中（结构化记忆，无 NL 理解）** |
| **维护复杂度** | 高 | 高 | **低（纯规则）** |
| **可回溯性** | 低（摘要无法还原细节） | 中（previous_summary 保留上下文） | **高（每轮工具调用链完整）** |
| **LLM 看得懂** | 最好 | 最好 | **足够（纯文本，加标记防歧义）** |
| **何时触发** | 每次 compaction | 每次 compression | **每轮追加，不受裁剪影响** |

**结论**：History Memory 的信息质量不如 LLM 摘要，但**零成本、零维护、独立 user 消息注入，trim_history 保护机制完善**。在当前的单次 Agent run 场景中，够用。

---

## 八、关键常量

| 常量 | 值 | 说明 | 来源 |
|------|-----|------|------|
| `MAX_CONTEXT_TOKENS` | 200000 | 上下文窗口上限（配置可覆盖） | 原 constants.py |
| `CHARS_PER_TOKEN` | 4 | chars→token 换算 | 原 constants.py |
| `TRIGGER_T1_RATIO` | 0.50 | T1 工具摘要触发比例 | 新增 |
| `TRIGGER_T3_RATIO` | 0.95 | T3 紧急裁剪触发比例 | 新增 |
| `TRIM_TARGET_RATIO` | 0.50 | 裁剪目标比例 | 新增 |
| `KEEP_TAIL_ROUNDS` | 3 | 保尾轮数（借鉴方案[3]：保留最近 3 轮） | 新增 |
| `COMPRESS_MINIMUM` | 20000 | T3 最少需释放这么多 token，否则跳过 | 借鉴 OpenCode PRUNE_MINIMUM |
| `PASS3_ARGS_THRESHOLD` | 500 | tool_call 参数超过此长度才截断 | 借鉴 Hermes Pass3 |
| `PASS3_ARG_MAX_CHARS` | 200 | 截断后字符串字段最大长度 | 借鉴 Hermes Pass3 |
| `HISTORY_MEM_MAX_LINES` | 500 | History Memory 最大行数 | 新增 |
| `HISTORY_MEM_LINE_MAX_CHARS` | 120 | 每行最大字符数 | 新增 |

---

## 九、完整数据流

```
用户请求 → Agent run 开始

  轮1:
    Phase 1: trim_history() → total < 50%, 跳过
              inject_history_mem() → History Memory 注入 user 消息
    LLM → thought + tool_call(readtext)
    Phase 2: append_history_mem(thought: "需要查看 config.py")
              append_history_mem(action: readtext(config.py))
              消息追加到 conversation_history

  轮2:
    Phase 1: trim_history() → total < 50%, 跳过
              inject_history_mem() → History Memory 已有一行
    LLM → action(edittext(config.py))
    Phase 2: append_history_mem(action: edittext(config.py timeout=30→60))

  ...（更多轮次，History Memory 持续增长）...

  轮N:
    Phase 1: trim_history() → total > 50%, 触发 T1
              旧 tool obs → "[readtext] config.py (120行)"
              total 降至 < 50%
              inject_history_mem() → History Memory 已有 N 行

  ...（继续增长）...

  轮M:
    Phase 1: trim_history() → total > 95%, 触发 T3
              加深 T1 + Pass3 参数截断 → 仍超
              保尾 3 轮，从最旧往最新删 → total 降至 < 50%
              History Memory 在 user 消息中，_history_mem 标记保护
              inject_history_mem() 正常执行
```

---

## 十、对比之前所有方案

| 维度 | [3] 简单裁剪 | [2] 三级压缩 | 原[4] v1.0 | **最终方案(本文件 v3.0)** |
|------|------------|-------------|-----------|------------------------|
| **推理链保留** | ❌ 丢弃 | ⚠️ 工具调用链 | ✅ **从 Step 提取** | ✅ **History Memory 注入 user** |
| **obs 压缩** | ❌ 直接删 | ✅ T1 摘要 | ✅ **T1 摘要** | ✅ **T1 摘要** |
| **冷区合并** | — | ⚠️ 不可控 | ❌ 不做 | ❌ **不做** |
| **防抖动** | ❌ | ❌ | ✅ **Hermes** | ✅ **Hermes should_compress** |
| **参数截断** | ❌ | ❌ | ✅ **Pass3** | ✅ **Hermes Pass3** |
| **溢出回退** | ❌ | ❌ | ✅ **OpenCode** | ✅ **OpenCode 回退+重试** |
| **保尾策略** | ✅ KEEP=3 从最旧删 | ⚠️ KEEP=5 | KEEP=5 | ✅ **KEEP=3 + 从最旧删（融合[3]）** |
| **保尾定位方式** | ✅ 找第N个user消息 | — | — | ✅ **找第N个assistant消息（融合[3]）** |
| **History Memory 位置** | — | — | system 注入 | ✅ **独立 user 消息** |
| **总级别** | 1 | 3 | 2 + History Memory | **2 级（T1 + T3）+ History Memory** |
| **复杂程度** | 低 | 高 | 中 | **中（融合[3]后略降）** |

---

## 十一、推荐落地组合（最终方案）

> 本方案是 **[4] History Memory 设计** 与 **[3] 简化保尾逻辑** 的有机融合。
> History Memory 提供"推理链永不丢"的保障，T1 做主动压缩，T3 做最后安全网，
> 保尾逻辑借鉴[3]的简洁可靠方式（KEEP=3、从最旧删）。

### 11.1 组合全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    最终方案：History Memory + T1 + T3                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [History Memory] ─── 每轮自动追加，独立 user 消息，_history_mem 保护  │
│  └─ thought → action(tool+params) → result → answer                 │
│  └─ 上限 500 行，超了合并最早两行                                    │
│  └─ 来源: Step 体系（非 assistant message，FC 模式也总有内容）         │
│  └─ role=user，紧挨 system 之后，语义对（对话历史）                   │
│                                                                     │
│  [T1 工具摘要] ─── total > 50% 触发，零 LLM 成本                   │
│  └─ tool observation 内容 → 工具感知一行摘要                         │
│  └─ 不删消息、不破坏 FC 配对                                         │
│  └─ 已压缩消息标记 _compressed=True，防重复压缩                      │
│                                                                     │
│  [T3 紧急裁剪] ─── total > 95% 触发，最后安全网                      │
│  ├─ 加深 T1 + Pass3 参数截断                                         │
│  ├─ should_compress 防抖动（连续 2 次节省 < 10% 跳过）               │
│  ├─ 保尾 KEEP_TAIL_ROUNDS=3 轮完整 FC 对（借鉴方案[3]）              │
│  │    定位: 从末尾往前找第 3 个 assistant 消息，之后全部保留          │
│  ├─ 从最旧往最新删，直到 total < 窗口×50%（借鉴方案[3]）              │
│  ├─ 回退: 保尾 3 轮超预算 → 递减到 2→1 轮                           │
│  └─ 溢出重试: LLM API 返回 413 → T3 后重试                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 触发链（按阈值递增）

| 阈值 | 动作 | 效果 | 信息丢失 |
|------|------|------|---------|
| < 50% | 不触发 | 全部保留 | 无 |
| 50%~95% | **T1** 工具摘要 | obs 内容→一行摘要，消息数不变 | 仅 obs 细节，决策链完整 |
| > 95% | **T3** 紧急裁剪 | 加深 T1 + Pass3 + 保尾 3 轮 + 从最旧删 | 旧轮次丢弃，但 History Memory 中有推理链 |

### 11.3 保尾逻辑详解（融合方案[3]）

**为什么 KEEP_TAIL_ROUNDS=3？**
- 原设计 KEEP=5，但我们的单次 Agent run 典型 5~15 轮，5 轮保尾占比过高
- 方案[3]论证 KEEP=3 足够：保尾 3 轮保留最近完整决策链，从最旧删不会误伤关键信息
- 3 轮 ≈ 最近 6~9 条消息（assistant+tool），配合 History Memory 中的全量推理链，LLM 有足够上下文继续任务

**定位方式：**
```
从 conversation_history 末尾往前找第 3 个 assistant 消息，
该消息及之后的所有内容（含 tool/user 消息）划为保尾区。
不足 3 轮则不裁剪。
```

**裁剪方向（从最旧往最新删）：**
- 锁定 system 消息 + 保尾区，计算占用 token
- 预算 = `MAX_CONTEXT_TOKENS × 0.50` - 锁定占用量
- 从 system 之后、保尾区之前的消息，**从最旧往最新扫描**，预算内尽量保留
- 超预算则丢弃后续消息
- 最后 `_trim_fc_pairs` 清理孤儿 FC 对

### 11.4 与其他方案的关键区别

| 对比 | 方案[1] 4层触发 | 方案[2] 三级压缩 | 方案[3] 简化裁剪 | **最终方案** |
|------|---------------|----------------|----------------|------------|
| **设计哲学** | 理论上完美 | 优中选优+自创 | 只解决当下 | **方案[4]为主+方案[3]保尾** |
| **推理链保留** | ⚠️ 压缩不丢决策 | ⚠️ 冷区合并不可控 | ❌ 直接丢 | **✅ History Memory 始终在** |
| **obs 压缩** | ❌ 零收益 | ✅ T1 摘要 | ❌ 直接删 | **✅ T1 摘要** |
| **保尾** | 3/1 轮 | 5 轮 | 3 轮从最旧删 | **✅ 3 轮 + 从最旧删** |
| **防抖动** | ❌ | ❌ | ❌ | **✅ Hermes should_compress** |
| **实用度** | ❌ 过度设计 | ⚠️ 冷区合并不成熟 | ✅ 够用但风险 | **✅ 够用 + 安全网完善** |
| **实现复杂度** | 极高 | 高 | 低 | **中** |

### 11.5 实施要点

| 模块 | 改动 |
|------|------|
| `constants.py` | 新增 `COMPRESS_T1_RATIO=0.50`、`TRIM_T3_RATIO=0.95`、`TRIM_TARGET_RATIO=0.50`、`KEEP_TAIL_ROUNDS=3`、`HISTORY_MEM_MAX_LINES=500`、`HISTORY_MEM_LINE_MAX_CHARS=120`、`T3_MINIMUM_SAVINGS=20000`、`PASS3_ARGS_THRESHOLD=500`、`PASS3_ARG_MAX_CHARS=200` |
| `message_builder.py` | ① 新增 `history_mem` 属性 + 追加/注入方法 ② 新增 `_t1_compress_observations()` T1 工具摘要 ③ 新增 `_trim_t3()` 从最旧删+保尾 3 轮 ④ `trim_history()` 重写为 T1→T3 流水线 ⑤ `prepare_messages_for_llm()` 浅拷贝时插入独立 user 消息(History Memory)，带 `_history_mem=True` 标记 ⑥ `trim_history()` 识别 `_history_mem` 标记强制保留 |
| `react_cycle.py` | `_process_single_step()` Phase 3 末尾追加 History Memory |

---

## 十二、三思三省

### 12.1 第一省：需求覆盖检查 — 方案真的解决了四个问题吗？

**R1（主动压缩 obs）→ T1**
- ✅ 大 obs（readtext 200行、shell 200行）→ 一行摘要，压缩比 >99%
- ⚠️ **但：obs 已被行×列收口，如果收口后本身很小（grep 3行匹配），T1 无收益**。此时 total 仍可能 >50% 但 T1 压缩率为零，白白走了一遍扫描。代价是 O(n) 遍历 + _estimate_tokens 重算，几十微秒级别，可接受。真正的问题是：**T1 没省出空间，后续轮次仍然会触发 T3。**

**R2（保推理链不丢）→ History Memory**
- ✅ thought→action→result→answer 结构，每轮追加
- ⚠️ **但：History Memory 只记录 `step.content`（公开推理），不记录 LLM 的 `reasoning` 字段（内部推理链）**。reasoning 是 LLM 的"自言自语"，有时候关键决策出现在 reasoning 里而不是 thought 里。当前设计只截取 thought[:80]，可能漏掉重要推理。**需要确认：在我们的 LLM 响应中，关键决策链到底在 thought 还是在 reasoning？**

**R3（决策全景）→ History Memory**
- ✅ LLM 每轮都能看到完整的调用链
- ⚠️ **但：History Memory 增长到 500 行上限后，本身也成了"长文本噪音"**。500 行按平均 60 字符/行 ≈ 30K chars ≈ 7.5K tokens，相当于又多了一条大 obs。**History Memory 的压缩策略（合并最早两行）只是字符截断，不是语义摘要**——越往后 History Memory 的信息密度越低。

**R4（零 LLM 成本）→ 全部**
- ✅ T1 纯字符串替换，History Memory 纯规则拼接，T3 纯列表操作，全程无 LLM 调用
- ✅ 没有任何隐藏的 LLM 调用路径

**R5（最后安全网）→ T3**
- ✅ 95% 触发，保尾 3 轮，从最旧删，递减回退
- ✅ 防抖动 + 溢出重试，不会"裁了还超"
- ⚠️ **但：T3 的裁剪方向是从最旧往最新删，budget = target(50%) - 锁定区。如果保尾 3 轮 + system 已经占了 60%，available < 0，直接走回退。而回退递减保尾轮数**——极端情况保尾 1 轮，可能把关键决策轮裁掉。此时 History Memory 是唯一保留的推理链。

### 12.2 第二省：假设风险 — 哪些假设可能不成立？

**假设 1：50% 和 95% 阈值在真实场景中合理**

| 窗口配置 | T1 50% 触发线 | T3 95% 触发线 | 5-15轮能否触发 |
|---------|--------------|--------------|--------------|
| 默认 200K | 100K tokens | 190K tokens | **T1 可能触，T3 几乎不触**（除非超大 obs） |
| deepseek 900K | 450K tokens | 855K tokens | **都不触发**（5-15轮到不了 450K） |

**风险**：窗口越大（900K），T1 和 T3 越不触发，整个裁剪机制在 deepseek 大窗口下**可能形同虚设**。

**对策**：触发阈值应基于**实际窗口**而不是固定比例。或者加一个备用触发条件：**消息数 > N 条**（类似之前方案的条件 C）。但消息数触发又回到了"删消息"的老路——没有压缩先行。

**需要北京老陈裁定**：deepseek-v4-flash 的 900K 窗口下，T1/T3 不触发是否可接受？还是需要基于消息数的备用触发？

**假设 2：保尾 3 轮 + History Memory 足够 LLM 理解任务全局**

如果任务的**关键决策发生在第 4 轮之前**（比如第 1 轮做了项目全局分析、确定了方案），保尾 3 轮没保住第 1 轮：
- History Memory 保留了：`thought: 需要分析项目结构` → `tool: readtext(项目配置)` → `result: 发现 Python 项目`
- 保尾 3 轮保留了：最近的具体代码改了哪些文件
- LLM 看到的：知道"之前分析过项目结构是 Python"，但**看不到原始的分析细节**（目录树、文件列表、关键发现）

**风险**：LLM 信任 History Memory 的概要还是需要重新分析？取决于 History Memory 的信息密度是否足够让 LLM 做出正确的下一步决策。

**观察结论**：对于大多数 Agent 任务，"知道之前做过什么 + 结论"比"看到原始输出"更重要。History Memory 提供的正是"做过什么 + 结论"。但这个假设**需要 E2E 测试验证**。

**假设 3：History Memory 的 user 角色不会误导 LLM**

LLM 看到 messages 中有一条独立的 `user` 消息（History Memory），会不会以为"用户又发了新指令"？

**分析**：
- History Memory 紧挨 system 之后，早于 task prompt。LLM 阅读顺序是 system → History Memory → task → history。History Memory 的内容格式是 `#1 thought: xxx`，开头带 `[History Memory]` 前缀，明显不是用户指令而是记忆参考
- 训练数据中，user 消息也可以包含"参考信息"（OpenCode/Hermes 都把 tool result 放 user）。**关键在于内容前缀**，而不是 role 本身
- 风险极低

### 12.3 第三省：边界条件和失败模式

| 场景 | 预期行为 | 风险 | 对策 |
|------|---------|------|------|
| **1 轮完成** | 不触发 T1/T3，History Memory 正常工作 | 无 | — |
| **30 轮长任务** | T1 多次触发，同一 obs 被 Repeatedly 压缩 | _compressed 标记防重复，但标记本身不清理 | 每轮 prepare_messages_for_llm 剥离 `_compressed` 标记（只剥离副本，原始标记保留） |
| **LLM 空转（reasoning-only）** | B3 注入临时 reasoning 消息，然后被 pop_temp_messages 清除 | 空转也会被 append_history_mem 记录到 History Memory | 空转的 reasoning 没有对应的 action/observation，History Memory 中记录的是"thought: xxx"但没有后续的 tool/result，**LLM 自己看得出来这是空转**。但连续多次空转会污染 History Memory。对策：`append_history_mem` 检测到**连续 2 条 thought 没有中间 action** 时合并为一条 |
| **T3 + 回退到保尾 1 轮** | system + 最后 1 轮 + History Memory 保留 | 中间轮全丢，完全依赖 History Memory | **可接受**。History Memory 记录了所有轮次的推理链，LLM 虽看不到原始 tool 输出，但知道推理过程。这是裁剪的代价 |
| **History Memory 本身超 500 行上限** | 合并最早两行 | 合并后信息密度下降，但仍是纯文本保留 | 500 行 × 60 字符 ≈ 30K chars ≈ 7.5K tokens，约窗口的 3.75%。**在 History Memory 达到 500 行之前，T1 早就触发了（50%）。** 所以 History Memory 超限在前，T1 压缩在后——T1 腾出空间后，History Memory 的 7.5K 占比反而更小了。无害 |
| **多轮对话（历史注入）** | `inject_history` 插入 system 和 task 之间 | History Memory 紧挨 system，历史注入也在 system 之后，两者的相对位置？| 顺序应该是：`[0]system` → `[1]History Memory` → `[2]历史消息` → `[3]task prompt`。需要在 `prepare_messages_for_llm` 中正确处理 |
| **`_history_mem` 标记被意外剥离** | trim_history 不识别，当成普通 user 消息 | 中间区扫描时 History Memory 可能被删 | 在 `prepare_messages_for_llm` 剥离标记时，当前设计只剥离 `_temp_reasoning` 和 `_compressed`，`_history_mem` 不下发到 LLM 但保留在 conversation_history。**实现时必须加 `msg.pop("_history_mem", None)`** |

### 12.4 复核结论

| 检查项 | 结论 |
|--------|------|
| **需求全覆盖** | R1-R5 均有对应机制，但有 2 个风险点（900K 窗口下 T1 不触发、reasoning 字段不记录） |
| **无非受迫假设** | 3 个假设均做了分析，风险可控 |
| **边界有兜底** | 7 个边界场景均有对策 |
| **零退化** | 当前 `trim_history` 代码会被完全重写，但保尾+FC配对保留，功能不退化 |
| **可测试** | 每层（History Memory / T1 / T3）可独立构造测试：构造超大 obs → T1 压缩 → 验证摘要格式；构造 95%+ → T3 裁剪 → 验证保尾 3 轮 + FC 配对完整性 |

---

## 十三、关于 role 选择的分析

### 13.1 各 LLM Provider 支持的 role

| Provider | 支持的 role | 备注 |
|----------|------------|------|
| **OpenAI** | `system` `developer` `user` `assistant` `tool` `platform` | `developer` 是 o1 起替代 `system` 的；`platform` 是 OpenAI 内部用 |
| **DeepSeek（我们用的）** | `system` `user` `assistant` `tool` | **只认这 4 个**，自定义 role 直接 400 |
| **Anthropic** | `user` `assistant`（system 是顶层字段） | 消息数组里只有 2 个 role |
| **NVIDIA NIM** | `system` `user` `assistant` `tool` | 跟 OpenAI 兼容 |

### 13.2 各 role 对 LLM 的实际影响

role 不是 API 硬编码的规则，而是**训练时通过数据分布暗示的权重**：

| role | 训练时学到的含义 | 权威性 | 影响 |
|------|----------------|--------|------|
| **`system`** | "不可违抗的指令" | 最高 | LLM 把它当**底线规则**，即使后面 user 冲突也优先听 system |
| **`user`** | "需要回答的输入" | 中等 | LLM 把它当**当前任务**，驱动对话方向 |
| **`assistant`** | "自己以前说过的话" | 低但有自洽偏置 | LLM 倾向于跟自己以前说的话保持一致 |
| **`tool`** | "外部工具返回的事实" | 最低 | LLM 把它当**待处理的原材料**，可质疑、可摘要 |

这是 OpenAI 提出的 **Chain of Command（指挥链）** 设计：
```
platform（OpenAI 内置规则，用户改不了）
  → system/developer（开发者设定的规则）
    → user（用户输入）
      → assistant / tool（无权威，纯数据）
```

**但 DeepSeek 不一定严格遵循这套等级体系。** 它只是消息格式兼容 OpenAI，内部训练数据分布和权重分配可能完全不同。

### 13.3 为什么最终选择 user

| 候选 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **`system`** 注入 | trim_history 天然不碰，实现最简单 | 语义不对——History Memory 不是"指令"，是"记忆参考" | ❌ 放弃 |
| **`user`** 独立消息 | 语义最对，对话历史的一部分；DeepSeek 对 role 不敏感 | 需要 trim_history 加保护标记 | **✅ 选定** |
| **`assistant`** 消息 | 推理链放 assistant 语义上也合理 | FC 配对逻辑复杂，且 trim_history 可能误删 | ❌ 放弃 |
| 自定义 role | DeepSeek 不支持，400 错误 | — | ❌ 不可行 |

**最终裁定**（北京老陈 2026-07-22）：History Memory 用 `user` 角色，独立消息紧挨 system 之后，带 `_history_mem=True` 标记由 trim_history 保护。

---

## 十四、变更记录

| 版本 | 时间 | 变更人 | 变更内容 |
|------|------|--------|---------|
| v4.0 | 2026-07-22 17:35:08 | 小欧 | 概念升级：Context Log → History Memory（从"日志记录"提升为"结构化记忆供给"）；新增 3.1 概念升级说明；全篇 s/Context Log/History Memory/、s/context_log/history_mem/、s/_context_log/_history_mem/、s/CONTEXT_LOG_/HISTORY_MEM_/ |
| v3.0 | 2026-07-22 16:33:34 | 小欧 | History Memory 注入方式从 system 改为独立 user 消息（北京老陈裁定：user 角色语义更对）；新增 3.4 保护机制（`_history_mem` 标记 + 每轮重注入）；新增第十一章"关于 role 选择的分析" |
| v2.0 | 2026-07-22 18:30:00 | 小欧 | 融合方案[3]保尾逻辑：KEEP_TAIL_ROUNDS=5→3、从最旧往最新删、保尾定位方式借鉴方案[3]找第N个assistant消息；新增第十章"推荐落地组合"总结全文 |
| v1.0 | 2026-07-22 18:30:00 | 小欧 | 初版：History Memory（从 Step 提取推理链注入 system prompt）+ T1 工具摘要 + T3 紧急裁剪（借鉴 OpenCode/Hermes 的 6 种机制） |
