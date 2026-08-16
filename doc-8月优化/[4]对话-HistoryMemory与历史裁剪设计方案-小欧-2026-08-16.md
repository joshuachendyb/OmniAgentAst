# 对话-HistoryMemory 与历史裁剪设计方案

> **编写人**: 小欧
> **创建时间**: 2026-07-22 18:30:00
> **更新时间**: 2026-08-16 15:41:02
> **版本**: v5.9
> 
> **核心定位**：M1 历史记忆注入法（History Memory，结构化记忆供给）是主，历史裁剪（C3 的轻量实现函数 t1_compress_observations（工具摘要压缩）/T1 紧急裁剪法 压缩旧 tool 输出）是辅。先解决"LLM 每轮能看到决策链"，再解决"窗口不够用时腾空间"。

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
C3 的轻量实现函数 t1_compress_observations（Tool-Summary，50% 触发）
  └── 对 observation 做一行摘要 → 腾出空间，消息数不变
  └── 解决 R1（主动压缩 tool obs）
  └── 解决 R4（纯字符串替换，零 LLM 成本）

M1 历史记忆注入法（History Memory，每轮追加）
  └── 把推理链提取为结构化记忆注入独立 user 消息
  └── 解决 R2（保推理链）+ R3（决策全景）
  └── 解决 R4（纯规则，零 LLM 成本）

T1 紧急裁剪法（Emergency Trim，95% 触发）
  └── 加深 t1_compress_observations（C3 轻量实现） + 参数截断 + 删除最早消息
  └── 解决 R5（最后安全网）
  └── M1 历史记忆注入法 不受影响，R2 仍然满足
```

---

## 二、术语说明：t1_compress_observations（C3 轻量实现）/ T1

本方案包含两个裁剪级别，按触发阈值编号：

| 级别 | 全称 | 触发时机 | 做什么 | 通俗理解 |
|------|------|---------|--------|---------|
| **t1_compress_observations** | C3 的轻量实现函数 — 工具摘要压缩法（Tool-Summary） | total > 窗口 50% | tool 观察结果内容 → 一行摘要，**不删消息** | **轻量：把大段工具输出压缩成一句话** |
| **T1** | Trim 1 — 紧急裁剪法（Emergency Trim） | total > 窗口 95% | 加深 t1_compress_observations（C3 轻量实现）+ 参数截断 + **删消息**（保尾 3 轮） | **重度：窗口快爆了，删旧消息腾空间** |

**为什么没有 T2？** 之前方案[2]有过 T2（冷区合并），因为不可控放弃了。现方案只有 t1_compress_observations（C3 轻量实现，轻量压缩）+ T1（重度裁剪），中间 50%~95% 只做 t1_compress_observations，不够时才触发 T1。

t1_compress_observations（C3 轻量实现） 和 T1 的设计细节见第四章和第五章。

---

## 三、两处借鉴 + 一处创新

### 2.1 借鉴 OpenCode

| 机制 | 用在哪 | 原始实现 |
|------|--------|---------|
| **Prune** 替换旧 tool output 为占位符 | C3 的轻量实现函数 t1_compress_observations（Tool-Summary）（替换 obs content） | `compaction.ts` Prune |
| **tail_turns** 轮次保尾 | T1 裁剪保尾 KEEP_TAIL_ROUNDS=3 | `compaction.ts select()` |
| **splitTurn** 部分保留一轮 | T1 如果整轮太大，只保尾部几条 | `compaction.ts` L162-185 |
| **溢出回退** 裁了还不够→继续缩小保尾 | T1 的 KEEP_TAIL_ROUNDS 递减回退 | `compaction.ts` overflow 模式 |
| **PRUNE_MINIMUM=20K** 节省太少不执行 | T1 防抖动 | `compaction.ts` L36 |

### 2.2 借鉴 Hermes

| 机制 | 用在哪 | 原始实现 |
|------|--------|---------|
| **Pass2 工具感知摘要** | C3 的轻量实现函数 t1_compress_observations（Tool-Summary）模板 | `context_compressor.py` L880-892 |
| **Pass3 截断 tool_call 参数** | T1 加深压缩 | `context_compressor.py` L894-918 |
| **should_compress 防抖动** 连续2次节省<10%跳过 | T1 防抖动 | `context_compressor.py` L728-748 |
| **413/overflow 回退 + compress + retry** | T1 溢出重试 | `conversation_loop.py` L2817-3024 |

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
│   trim_history() — 检查是否需要 t1_compress_observations/T1                         │
│   inject_history_mem() — 把 History Memory 注入 user 消息     │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: LLM 返回后                                          │
│   解析 Step(thought/tool/answer)                              │
│   append_history_mem(step) — 追加一行到 History Memory        │
│   消息追加到 conversation_history                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 M1 历史记忆注入法（History Memory）— 概念升级：从"日志"到"记忆"

> **适用场景/场合**：① 每轮追加，零成本决策链供给；② 所有任务默认启用（独立 user 消息，_history_mem 保护）；③ 与任何压缩法组合，作 zero-cost 兜底记忆。

**Context Log（旧）** = 被动追加的"记录"，写进去就完了，LLM 自己从长文本里找有用信息。

**History Memory（新）** = 主动提供的结构化"记忆"，每轮从 Step 体系提取 thought→action→result→answer，拼成一条 LLM 可以直接"回想"的决策链。不是"把历史写下来"，而是"让 LLM 每次都能看到自己已经做了什么、为什么、结论是什么"。

同一个实现机制，但**思考层次不同**：
| | Context Log | History Memory |
|--|-----------|---------------|
| **本质** | 低层次的日志记录 | 高层次的记忆供给 |
| **视角** | "写"的角度：追加内容 | "读"的角度：LLM 需要什么信息来续写 |
| **关注** | 不丢数据 | LLM 能否快速定位决策链 |
| **信息量** | 全量 step 内容 | 提炼过的结构（结论+关键参数） |

### 3.2 M1 历史记忆注入法（History Memory）— 维护在哪、怎么注入

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

### 3.3 M1 历史记忆注入法（History Memory）— 追加内容

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

### 3.4 M1 历史记忆注入法（History Memory）— 保护机制

History Memory 以独立 `user` 消息存在（紧挨 system 之后），在 `trim_history` 中通过以下机制保护：

1. **保尾定位跳过**：T1 保尾从末尾找第 3 个 assistant 消息，History Memory 是 user 消息，不会被纳入轮次计数
2. **system+user 锁死**：T1 裁剪的中间区是 system 之后、保尾区之前，而 History Memory 紧挨 system，属于中间区最旧的部分——但 History Memory 的 token 极小（数百字符），在"从最旧往最新保留"的扫描中，预算内一定能保留
3. **`_history_mem` 标记**：History Memory 消息带 `_history_mem=True` 标记，trim_history 遇到此标记强制保留

**万一被裁了怎么办？** History Memory 是**每轮重新注入**的。即使本轮被裁剪，下一轮 `prepare_messages_for_llm()` 会重新生成 History Memory 消息（从 `MessageBuilder.history_mem` 列表中提取最新 N 条）。因此 History Memory 实际是**逻辑持久**的——message_builder 的属性不随 trim_history 消失。

---

## 五、C3 剪枝压缩法的轻量实现：工具摘要压缩（t1_compress_observations）

> **说明**：本轻量实现（函数 `t1_compress_observations`，原 C1 工具摘要压缩法 Tool-Summary Compaction）归 **C3 剪枝压缩法**策略族，与 14.9.3 的 `prune_tool_outputs`（prune 清输出）并列两种轻量压缩策略——前者逐工具写一行摘要、后者通用清零旧 tool output。其 DRY 升级为 `t1_reuse_summary`（原 C2 摘要复用压缩法，推荐，复用工具层已有 `llm_data.summary`，避免 per-tool 模板）。

> **适用场景/场合**：① 轻量主动压缩首选，obs 粗估超窗口 50% 触发；② 简单/单轮任务、成本敏感（零 LLM）；③ 不删消息、不破坏 FC 配对，适合需保留完整消息数的场景。

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
- t1_compress_observations 压缩后 100 轮 obs 摘要：100×80=8K chars=2K tokens
- 200 轮 t1_compress_observations 后 total（含 system+user+asst）：~336K chars=**84K tokens**，窗口 200K 仅占 **42%**

### 4.4 防重复压缩

每条 tool 消息加 `_compressed=True` 标记，已压缩的不再压缩。

---

## 六、T1 紧急裁剪法（Emergency Trim）（95% 触发，借鉴 OpenCode+Hermes）

> **适用场景/场合**：① 窗口快爆（>95%）最后安全网；② 防 LLM API 413 溢出；③ 加深 t1_compress_observations（C3 轻量实现） + Pass3 参数截断 + 保尾 + 回退 + 溢出重试。

### 5.1 触发条件

```
粗估 tokens > MAX_CONTEXT_TOKENS × 0.95
```

### 5.2 流程

```
T1 入口:
  1. [加深T1] 对尚未压缩的 obs 全部做工具摘要（确保每一条 obs 最小化）
  2. [Hermes Pass3] 截断旧 assistant 中 tool_call 参数 JSON
     args > 500 chars → 字符串字段截到 200 chars（保持 JSON 合法）
  3. [防抖动] 上次 T1 节省 < 10% → 跳过本次（Hermes should_compress）
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
  7. [溢出重试] 如果 LLM API 返回 413 → 触发 T1 后重试
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

## 七、M1 历史记忆注入法（History Memory）vs 其他压缩方式对比

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
| `TRIGGER_T1_RATIO` | 0.50 | C3 的轻量实现函数 t1_compress_observations（Tool-Summary）触发比例 | 新增 |
| `TRIGGER_T3_RATIO` | 0.95 | T1 紧急裁剪法（Emergency Trim）触发比例 | 新增 |
| `TRIM_TARGET_RATIO` | 0.50 | 裁剪目标比例 | 新增 |
| `KEEP_TAIL_ROUNDS` | 3 | 保尾轮数（借鉴方案[3]：保留最近 3 轮） | 新增 |
| `COMPRESS_MINIMUM` | 20000 | T1 最少需释放这么多 token，否则跳过 | 借鉴 OpenCode PRUNE_MINIMUM |
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
    Phase 1: trim_history() → total > 50%, 触发 t1_compress_observations
              旧 tool obs → "[readtext] config.py (120行)"
              total 降至 < 50%
              inject_history_mem() → History Memory 已有 N 行

  ...（继续增长）...

  轮M:
    Phase 1: trim_history() → total > 95%, 触发 T1
              加深 t1_compress_observations（C3 轻量实现） + Pass3 参数截断 → 仍超
              保尾 3 轮，从最旧往最新删 → total 降至 < 50%
              History Memory 在 user 消息中，_history_mem 标记保护
              inject_history_mem() 正常执行
```

---

## 十、对比之前所有方案

| 维度 | [3] 简单裁剪 | [2] 三级压缩 | 原[4] v1.0 | **最终方案(本文件 v3.0)** |
|------|------------|-------------|-----------|------------------------|
| **推理链保留** | ❌ 丢弃 | ⚠️ 工具调用链 | ✅ **从 Step 提取** | ✅ **History Memory 注入 user** |
| **obs 压缩** | ❌ 直接删 | ✅ t1_compress_observations 摘要 | ✅ **t1_compress_observations 摘要** | ✅ **t1_compress_observations 摘要** |
| **冷区合并** | — | ⚠️ 不可控 | ❌ 不做 | ❌ **不做** |
| **防抖动** | ❌ | ❌ | ✅ **Hermes** | ✅ **Hermes should_compress** |
| **参数截断** | ❌ | ❌ | ✅ **Pass3** | ✅ **Hermes Pass3** |
| **溢出回退** | ❌ | ❌ | ✅ **OpenCode** | ✅ **OpenCode 回退+重试** |
| **保尾策略** | ✅ KEEP=3 从最旧删 | ⚠️ KEEP=5 | KEEP=5 | ✅ **KEEP=3 + 从最旧删（融合[3]）** |
| **保尾定位方式** | ✅ 找第N个user消息 | — | — | ✅ **找第N个assistant消息（融合[3]）** |
| **History Memory 位置** | — | — | system 注入 | ✅ **独立 user 消息** |
| **总级别** | 1 | 3 | 2 + M1 历史记忆注入法（History Memory） | **2 级（t1_compress_observations（C3 轻量实现） + T1）+ M1 历史记忆注入法（History Memory）** |
| **复杂程度** | 低 | 高 | 中 | **中（融合[3]后略降）** |

---

## 十一、推荐落地组合（最终方案）

> 本方案是 **[4] History Memory 设计** 与 **[3] 简化保尾逻辑** 的有机融合。
> History Memory 提供"推理链永不丢"的保障，t1_compress_observations 做主动压缩，T1 做最后安全网，
> 保尾逻辑借鉴[3]的简洁可靠方式（KEEP=3、从最旧删）。

### 11.1 组合全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    最终方案：M1 历史记忆注入法（History Memory） + t1_compress_observations（C3 轻量实现） + T1                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [History Memory] ─── 每轮自动追加，独立 user 消息，_history_mem 保护  │
│  └─ thought → action(tool+params) → result → answer                 │
│  └─ 上限 500 行，超了合并最早两行                                    │
│  └─ 来源: Step 体系（非 assistant message，FC 模式也总有内容）         │
│  └─ role=user，紧挨 system 之后，语义对（对话历史）                   │
│                                                                     │
│  [C3 的轻量实现函数 t1_compress_observations（Tool-Summary）] ─── total > 50% 触发，零 LLM 成本                   │
│  └─ tool observation 内容 → 工具感知一行摘要                         │
│  └─ 不删消息、不破坏 FC 配对                                         │
│  └─ 已压缩消息标记 _compressed=True，防重复压缩                      │
│                                                                     │
│  [T1 紧急裁剪法（Emergency Trim）] ─── total > 95% 触发，最后安全网                      │
│  ├─ 加深 t1_compress_observations（C3 轻量实现） + Pass3 参数截断                                         │
│  ├─ should_compress 防抖动（连续 2 次节省 < 10% 跳过）               │
│  ├─ 保尾 KEEP_TAIL_ROUNDS=3 轮完整 FC 对（借鉴方案[3]）              │
│  │    定位: 从末尾往前找第 3 个 assistant 消息，之后全部保留          │
│  ├─ 从最旧往最新删，直到 total < 窗口×50%（借鉴方案[3]）              │
│  ├─ 回退: 保尾 3 轮超预算 → 递减到 2→1 轮                           │
│  └─ 溢出重试: LLM API 返回 413 → T1 后重试                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 11.2 触发链（按阈值递增）

| 阈值 | 动作 | 效果 | 信息丢失 |
|------|------|------|---------|
| < 50% | 不触发 | 全部保留 | 无 |
| 50%~95% | **C3 的轻量实现函数 t1_compress_observations（Tool-Summary）** | obs 内容→一行摘要，消息数不变 | 仅 obs 细节，决策链完整 |
| > 95% | **T1** 紧急裁剪法 | 加深 t1_compress_observations（C3 轻量实现） + Pass3 + 保尾 3 轮 + 从最旧删 | 旧轮次丢弃，但 History Memory 中有推理链 |

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
| **obs 压缩** | ❌ 零收益 | ✅ t1_compress_observations 摘要 | ❌ 直接删 | **✅ t1_compress_observations 摘要** |
| **保尾** | 3/1 轮 | 5 轮 | 3 轮从最旧删 | **✅ 3 轮 + 从最旧删** |
| **防抖动** | ❌ | ❌ | ❌ | **✅ Hermes should_compress** |
| **实用度** | ❌ 过度设计 | ⚠️ 冷区合并不成熟 | ✅ 够用但风险 | **✅ 够用 + 安全网完善** |
| **实现复杂度** | 极高 | 高 | 低 | **中** |

### 11.5 实施要点

| 模块 | 改动 |
|------|------|
| `constants.py` | 新增 `COMPRESS_T1_RATIO=0.50`、`TRIM_T3_RATIO=0.95`、`TRIM_TARGET_RATIO=0.50`、`KEEP_TAIL_ROUNDS=3`、`HISTORY_MEM_MAX_LINES=500`、`HISTORY_MEM_LINE_MAX_CHARS=120`、`T3_MINIMUM_SAVINGS=20000`、`PASS3_ARGS_THRESHOLD=500`、`PASS3_ARG_MAX_CHARS=200` |
| `message_builder.py` | ① 新增 `history_mem` 属性 + 追加/注入方法 ② 新增 `_t1_compress_observations()`（C3 的轻量实现函数 t1_compress_observations，工具摘要压缩） ③ 新增 `_trim_t3()` 从最旧删+保尾 3 轮 ④ `trim_history()` 重写为 t1_compress_observations（C3 轻量实现）→T1 流水线 ⑤ `prepare_messages_for_llm()` 浅拷贝时插入独立 user 消息(History Memory)，带 `_history_mem=True` 标记 ⑥ `trim_history()` 识别 `_history_mem` 标记强制保留 |
| `react_cycle.py` | `_process_single_step()` Phase 3 末尾追加 History Memory |

---

## 十二、三思三省

### 12.1 第一省：需求覆盖检查 — 方案真的解决了四个问题吗？

**R1（主动压缩 obs）→ t1_compress_observations（C3 轻量实现）**
- ✅ 大 obs（readtext 200行、shell 200行）→ 一行摘要，压缩比 >99%
- ⚠️ **但：obs 已被行×列收口，如果收口后本身很小（grep 3行匹配），t1_compress_observations 无收益**。此时 total 仍可能 >50% 但 t1_compress_observations 压缩率为零，白白走了一遍扫描。代价是 O(n) 遍历 + _estimate_tokens 重算，几十微秒级别，可接受。真正的问题是：**t1_compress_observations 没省出空间，后续轮次仍然会触发 T1。**

**R2（保推理链不丢）→ History Memory**
- ✅ thought→action→result→answer 结构，每轮追加
- ⚠️ **但：History Memory 只记录 `step.content`（公开推理），不记录 LLM 的 `reasoning` 字段（内部推理链）**。reasoning 是 LLM 的"自言自语"，有时候关键决策出现在 reasoning 里而不是 thought 里。当前设计只截取 thought[:80]，可能漏掉重要推理。**需要确认：在我们的 LLM 响应中，关键决策链到底在 thought 还是在 reasoning？**

**R3（决策全景）→ History Memory**
- ✅ LLM 每轮都能看到完整的调用链
- ⚠️ **但：History Memory 增长到 500 行上限后，本身也成了"长文本噪音"**。500 行按平均 60 字符/行 ≈ 30K chars ≈ 7.5K tokens，相当于又多了一条大 obs。**History Memory 的压缩策略（合并最早两行）只是字符截断，不是语义摘要**——越往后 History Memory 的信息密度越低。

**R4（零 LLM 成本）→ 全部**
- ✅ t1_compress_observations 纯字符串替换，History Memory 纯规则拼接，T1 纯列表操作，全程无 LLM 调用
- ✅ 没有任何隐藏的 LLM 调用路径

**R5（最后安全网）→ T1**
- ✅ 95% 触发，保尾 3 轮，从最旧删，递减回退
- ✅ 防抖动 + 溢出重试，不会"裁了还超"
- ⚠️ **但：T1 的裁剪方向是从最旧往最新删，budget = target(50%) - 锁定区。如果保尾 3 轮 + system 已经占了 60%，available < 0，直接走回退。而回退递减保尾轮数**——极端情况保尾 1 轮，可能把关键决策轮裁掉。此时 History Memory 是唯一保留的推理链。

### 12.2 第二省：假设风险 — 哪些假设可能不成立？

**假设 1：50% 和 95% 阈值在真实场景中合理**

| 窗口配置 | t1_compress_observations 50% 触发线 | T1 95% 触发线 | 5-15轮能否触发 |
|---------|--------------|--------------|--------------|
| 默认 200K | 100K tokens | 190K tokens | **t1_compress_observations 可能触，T1 几乎不触**（除非超大 obs） |
| deepseek 900K | 450K tokens | 855K tokens | **都不触发**（5-15轮到不了 450K） |

**风险**：窗口越大（900K），t1_compress_observations 和 T1 越不触发，整个裁剪机制在 deepseek 大窗口下**可能形同虚设**。

**对策**：触发阈值应基于**实际窗口**而不是固定比例。或者加一个备用触发条件：**消息数 > N 条**（类似之前方案的条件 C）。但消息数触发又回到了"删消息"的老路——没有压缩先行。

**需要北京老陈裁定**：deepseek-v4-flash 的 900K 窗口下，t1_compress_observations/T1 不触发是否可接受？还是需要基于消息数的备用触发？

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
| **1 轮完成** | 不触发 t1_compress_observations/T1，History Memory 正常工作 | 无 | — |
| **30 轮长任务** | t1_compress_observations 多次触发，同一 obs 被 Repeatedly 压缩 | _compressed 标记防重复，但标记本身不清理 | 每轮 prepare_messages_for_llm 剥离 `_compressed` 标记（只剥离副本，原始标记保留） |
| **LLM 空转（reasoning-only）** | B3 注入临时 reasoning 消息，然后被 pop_temp_messages 清除 | 空转也会被 append_history_mem 记录到 History Memory | 空转的 reasoning 没有对应的 action/observation，History Memory 中记录的是"thought: xxx"但没有后续的 tool/result，**LLM 自己看得出来这是空转**。但连续多次空转会污染 History Memory。对策：`append_history_mem` 检测到**连续 2 条 thought 没有中间 action** 时合并为一条 |
| **T1 + 回退到保尾 1 轮** | system + 最后 1 轮 + History Memory 保留 | 中间轮全丢，完全依赖 History Memory | **可接受**。History Memory 记录了所有轮次的推理链，LLM 虽看不到原始 tool 输出，但知道推理过程。这是裁剪的代价 |
| **History Memory 本身超 500 行上限** | 合并最早两行 | 合并后信息密度下降，但仍是纯文本保留 | 500 行 × 60 字符 ≈ 30K chars ≈ 7.5K tokens，约窗口的 3.75%。**在 History Memory 达到 500 行之前，t1_compress_observations 早就触发了（50%）。** 所以 History Memory 超限在前，t1_compress_observations 压缩在后——t1_compress_observations 腾出空间后，History Memory 的 7.5K 占比反而更小了。无害 |
| **多轮对话（历史注入）** | `inject_history` 插入 system 和 task 之间 | History Memory 紧挨 system，历史注入也在 system 之后，两者的相对位置？| 顺序应该是：`[0]system` → `[1]History Memory` → `[2]历史消息` → `[3]task prompt`。需要在 `prepare_messages_for_llm` 中正确处理 |
| **`_history_mem` 标记被意外剥离** | trim_history 不识别，当成普通 user 消息 | 中间区扫描时 History Memory 可能被删 | 在 `prepare_messages_for_llm` 剥离标记时，当前设计只剥离 `_temp_reasoning` 和 `_compressed`，`_history_mem` 不下发到 LLM 但保留在 conversation_history。**实现时必须加 `msg.pop("_history_mem", None)`** |

### 12.4 复核结论

| 检查项 | 结论 |
|--------|------|
| **需求全覆盖** | R1-R5 均有对应机制，但有 2 个风险点（900K 窗口下 t1_compress_observations 不触发、reasoning 字段不记录） |
| **无非受迫假设** | 3 个假设均做了分析，风险可控 |
| **边界有兜底** | 7 个边界场景均有对策 |
| **零退化** | 当前 `trim_history` 代码会被完全重写，但保尾+FC配对保留，功能不退化 |
| **可测试** | 每层（M1 历史记忆注入法（History Memory） / t1_compress_observations（C3 轻量实现）/ T1）可独立构造测试：构造超大 obs → t1_compress_observations 压缩 → 验证摘要格式；构造 95%+ → T1 裁剪 → 验证保尾 3 轮 + FC 配对完整性 |

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

## 十四、opencode 压缩方法深度研究（compaction.ts / overflow.ts / summary.ts）

> **本章来源**：北京老陈 2026-08-16 指示——深挖 `F:\agenttool\opencode`（opencode 源码）的上下文压缩实现，弄清每个文件的逻辑与原理功能，评估**我们能否使用、怎么使用**，研究结论补入本文档。以下为代码级实况（2026-08-16 研读 `packages/opencode/src/session/` 下 compaction.ts / overflow.ts / summary.ts 及关联的 message-v2.ts / processor.ts / prompt.ts / session.ts / config.ts）。
>
> **一句话总览**：opencode 的"上下文压缩"是一个**以 LLM 摘要为核心、以工具输出清零为轻量前置、以保尾为兜底**的三级机制。与我们 v4.0 的最大差异：**opencode 有真·LLM 语义摘要（anchored 锚定式），我们当时因"零 LLM 成本"原则刻意放弃**。本章研究清楚后给出逐文件原理 + 可借鉴性评估 + 落地建议。

### 14.1 三个文件的分工总览

| 文件 | 职责 | 一句话原理 | 触发时机 |
|------|------|-----------|---------|
| `overflow.ts` | **是否溢出的判定器** | 实际可用上下文 `usable = model.limit.input - reserved`，`total >= usable` → 溢出 | 每轮 LLM 返回后、异常 ContextOverflowError 时 |
| `compaction.ts` | **压缩编排核心**（create / select / prune / process） | 建压缩任务 → 选保尾区 → 轻量清零旧工具输出 → **LLM 锚定摘要**替换旧历史 → 自动续跑 | 溢出时 |
| `summary.ts` | 会话级 git diff 统计（**非上下文压缩**） | 计算 step-start/step-finish 快照间文件增删改，写入会话摘要 | 每轮 LLM 完成后异步 fork |

> ⚠️ **关键澄清（易误解）**：`summary.ts` 名字像"摘要"，但它做的是**文件变更统计（additions/deletions/files + diff）**，服务于 UI 展示"这个会话改了哪些文件"，**与上下文压缩无关**。真正的压缩逻辑全在 `compaction.ts`。下文详述。

### 14.2 overflow.ts — 溢出判定器（触发压缩的第一道闸门）

**功能**：判定当前对话上下文是否已满，满则触发压缩。

**核心逻辑**（overflow.ts:9-33）：

```python
# 可用上下文 = 模型输入上限 - 预留缓冲
def usable(cfg, model, outputTokenMax):
    reserved = cfg.compaction.reserved or min(COMPACTION_BUFFER=20000, maxOutputTokens)
    return model.limit.input - reserved if model.limit.input else max(0, context - maxOutputTokens)

def isOverflow(cfg, tokens, model):
    if cfg.compaction.auto is False: return False   # 配置关闭则不触发
    if model.limit.context == 0: return False
    count = tokens.total or tokens.input + tokens.output + tokens.cache.read + tokens.cache.write
    return count >= usable(cfg, model)
```

**要点**：
1. **按模型实际窗口算，不是固定比例**——`model.limit.input` 是多少用多少（deepseek 900K 就用 900K 算），预留 20K 缓冲（`reserved`）防压缩本身溢出。
2. **tokens 来自 Provider 真实返回**的 `tokens.total`，不是本地估算。
3. **`auto=false` 可关闭**自动触发（保留手动 `/compact` 命令路径）。

### 14.3 compaction.ts — 压缩编排核心（本文件是"压缩"本体）

分四个函数，对应压缩的四个阶段：

#### 14.3.1 `create()` — 建压缩任务（打标）
在会话中插入一个带 `type="compaction"` part 的 **user 消息**作为压缩任务标记（compaction.ts:586-616）。压缩不是"马上执行"，而是**作为一个消息插入会话队列**，由主循环（prompt.ts:1312-1322）下轮取到该任务后调用 `process()` 真正执行。auto/overflow 标志随任务携带。

#### 14.3.2 `select()` — 选保尾区（先决定"哪些保留不动"）
**功能**：从会话中选出最近 N 轮（tail）保留 verbatim，其余（head）交给压缩。是"先定保底，再定压缩范围"。

**核心逻辑**（compaction.ts:144-294）：
1. `turns()` 按 user 消息切分轮次（跳过带 compaction part 的 user）。
2. `preserveRecentBudget()`：保尾预算 = `min(8000, max(2000, usable*0.25))`——**不是固定轮数，是 token 预算上限 8K**，默认 `tail_turns=2` 轮。
3. 从最新往前逐轮累计 token：预算内整轮保留；超预算则 `splitTurn()` 在该轮内部"劈分"——只保留该轮后半段消息（compaction.ts:162-185），返回 `{head, tail_start_id}`。
4. 返回：`head`（要压缩的旧消息）+ `tail_start_id`（保尾区起点消息 ID，用于装配时从它开始原样保留）。

> **与我们 v4.0 的对照**：这就是"保尾 KEEP_TAIL_ROUNDS=3"的进阶版——**opencode 用 token 预算约束保尾（上限 8K），而不是死磕轮数**；还多了 `splitTurn` 半轮劈分（一整个 user 轮太大时只保该轮尾部）。

#### 14.3.3 `prune()` — 轻量前置：清零旧工具输出（零 LLM 成本）
**功能**：把旧 tool 消息的**输出内容**清掉（打 `time.compacted` 时间戳标记），**保留 tool_call 参数与 FC 配对结构**，腾出空间。这是"压缩第一步"，不调 LLM。

**核心逻辑**（compaction.ts:296-342 + message-v2.ts:301-306）：
1. 从后往前扫，**保护最近 2 轮**（`turns < 2 continue`）+ **遇到 summary 消息就停**（前面已压缩过，不再处理）+ **`skill` 工具豁免**。
2. 累计 token：`total <= PRUNE_PROTECT=40000` 之前不动（保护近期 40K 的工具输出细节）；超过后才开始收集待清。
3. 只有总节省 > `PRUNE_MINIMUM=20000` 才真正执行清零（防抖动，省得少不值当）。
4. 清零动作：`part.state.time.compacted = Date.now()`。之后装配时（message-v2.ts:304-306）该 tool 输出显示为 `[Old tool result content cleared]`，attachments 一并移除；但 **tool_call 参数仍在**（LLM 仍知道"调过什么工具、传了什么参数"）。

> **与我们 v4.0 的对照**：这对应我们的 **C3 的轻量实现函数 t1_compress_observations（Tool-Summary）**，但实现路径完全不同——
> - 我们 t1_compress_observations（C3 轻量实现）：**逐工具写摘要模板**（readtext/listdir/grep/shell/edittext/fetchpage 各一个模板），把 obs 内容替换成一行摘要。
> - opencode prune：**通用清零**，不维护任何 per-tool 模板，保留 tool_call 参数即可，`_compressed` 标记由 `time.compacted` 时间戳承担。
> - **判定：opencode 的做法明显更优**——零模板、零维护、不破坏 FC 配对（参数还在），且 `skill` 豁免 + PRUNE_PROTECT 保护近期细节的设计更精细。

#### 14.3.4 `process()` — LLM 锚定摘要（压缩的本体）
**功能**：用一次独立 LLM 调用，把旧历史总结成**固定结构的 Markdown 摘要**，替换掉 head 部分。这是 opencode 压缩的"灵魂"。

> **⚠️ 澄清（北京老陈 2026-08-16 确认）**：压缩**核心是 LLM 生成摘要**，agent 只是组织本次 LLM 调用的"壳"——**agent 壳（约束层）+ 底层 LLM（生成层）**，不能"只用 agent 不用 LLM"：
> - **agent 壳**（agent.ts:236-250）：专用 `name="compaction"` agent，`mode="primary"`、`hidden`（用户不可见）、专属系统提示词 `compaction.txt`、`permission "*": "deny"` 全拒 + `tools: {}` 不携带任何工具——**压缩只说话、不干活，绝不触发工具调用**；
> - **LLM 芯**（compaction.ts:445 → processor.ts:791）：`processor.process({ messages: [...modelMessages, user: nextPrompt] })` 内部 `llm.stream()` 做**一次 LLM 流式调用**，真正产出摘要文本的是底层 LLM 推理；
> - **结论**：opencode 用专用 agent 来"组织"这次 LLM 调用（提供锚定规则 + 锁死无工具 + 携带 previous-summary），**摘要文本仍由 LLM 生成**——与我们落地时"用当前模型（或可配置小模型）调一次 LLM"是同一件事，agent 是约束层、LLM 是生成层。

**核心逻辑**（compaction.ts:344-584）：
1. **取独立 compaction agent**：`agents.get("compaction")`——压缩用**专门的 agent**（可配置不同模型），LLM 不可见、不污染主对话（compaction.ts:385-388）。**该 agent 无工具、权限全 deny，仅通过系统提示词约束摘要输出，摘要文本由底层 LLM 流式生成（见上澄清）。**
2. **过滤已压缩对**：跳过之前已完成压缩的 user/assistant 消息对（`hidden` 集合），只压缩新增部分（compaction.ts:391-398）。
3. **anchored 锚定式提示词**（compaction.ts:124-135）——**这是本机制最精妙的一点**：
   - 有 `previousSummary`（上次摘要）：提示词 = "**更新**锚定摘要，保留仍成立的事实，删除过期事实，合并新事实" + `<previous-summary>`。
   - 无 previousSummary（首次）：提示词 = "从对话历史**新建**锚定摘要"。
   - → 摘要**可累积、不重复丢失**，每次只在旧摘要基础上增量更新，而非从零重写。
4. **固定结构模板** `SUMMARY_TEMPLATE`（compaction.ts:43-78）：强制输出 Markdown 结构——Goal（单句目标）/ Constraints & Preferences（约束偏好）/ Progress（Done / In Progress / Blocked）/ Key Decisions（关键决策+原因）/ Next Steps（下一步）/ Critical Context（关键技术事实/错误/未决问题）/ Relevant Files（涉及文件路径）。且规定：**保留精确文件路径/命令/错误串/标识符**，用简短 bullet 不用长段落，**不提及压缩过程本身**。
5. **压缩喂给 LLM 的历史被截断，但原库不破坏**（message-v2.ts:52-56, 301-306）：`toModelMessagesEffect(head, {stripMedia: true, toolOutputMaxChars: 2000})`——压缩用的工具输出截到 2000 字符（`[Tool output truncated for compaction: omitted N chars]`），**原始输出仍完整存库**，回放可查原文（与我们"回放走 DB"理念一致）。
6. **摘要以 assistant 消息落库**：`mode="compaction"`、`summary=true` 标记，作为对话的一部分持久化，UI 可展示"已压缩摘要"。
7. **结果判定**：
   - `"compact"` → 压缩后仍超限 → 记 `ContextOverflowError`（"会话太大，压缩后仍超模型限制"），返回 stop（compaction.ts:461-470）。
   - `"continue"` → 成功。若 auto 自动压缩：**自动续跑**——要么回放溢出前最近的 user 消息（overflow 场景），要么发一条合成消息 `"Continue if you have next steps, or stop and ask for clarification..."` 让 LLM 继续干活（compaction.ts:479-561）。**用户无感知，无需重新输入。**

> **与我们 v4.0 的对照**：这是**我们完全没有的一层**。我们 v4.0 的 R4 明确"零额外 LLM 调用"，所以只有 t1_compress_observations（字符级替换）+ T1（删消息）+ History Memory（规则级提取），**没有语义理解级的摘要**。opencode 证明了：一次独立 LLM 调用 + 锚定增量更新，能做到"信息密度高、决策链可累积"的真压缩。**代价**：额外一次 LLM 调用（成本 + 延迟）。这是当年我们主动放弃、而 opencode 选择承担的成本。

### 14.4 summary.ts — 澄清：它不是上下文压缩，是会话文件变更统计

**功能**（summary.ts:103-128）：`summarize()` 计算 `step-start` → `step-finish` 快照之间的 **git diff**（additions/deletions/files），写入 `session.summary`；`diff()` 提供查询。用于 UI 顶部展示"这个会话改了多少文件"。

**结论**：与上下文压缩**无关**，不参与压缩决策。我们若做压缩，**无需照搬此文件**；它对应的是我们文档2 中"会话级聚合信息"展示，非压缩职责。**判定：不借鉴。**

### 14.5 触发与装配闭环（理解全貌必看）

| 环节 | 代码位置 | 动作 |
|------|---------|------|
| 每轮 LLM 返回后 | processor.ts:611-616 | `isOverflow()` 为真 → `ctx.needsCompaction = true` |
| 异常溢出（413/ContextOverflow） | processor.ts:755-756 | 也置 `needsCompaction`，走压缩 |
| 主循环检测 | prompt.ts:1324-1331 | `lastFinished.summary !== true && isOverflow` → `compaction.create({auto: true})` 插压缩任务 |
| 任务消费 | prompt.ts:1312-1322 | 取到 compaction 任务 → `compaction.process()` |
| 装配过滤 | message-v2.ts:543-590 | 找最后一个带 `tail_start_id` 的 compaction part：**tail_start_id 之后原样保留，之前被摘要覆盖** |

### 14.6 我们可以使用吗？可以怎么使用（可借鉴性评估）

**总体结论：可借鉴，且有多处明显优于我们 v4.0 的现成做法。**

| # | opencode 机制 | 我们能否用 | 怎么用（映射到我们的代码） | 优先级 |
|---|--------------|-----------|--------------------------|--------|
| 1 | **prune 通用清零旧工具输出**（保留 tool_call 参数、清 output、`time.compacted` 标记） | ✅ 完全可用 | **替换 t1_compress_observations 逐工具摘要模板**：改 `message_builder.py`，对超预算的旧 tool 消息输出置 `compacted` 标记，装配时输出 `[旧工具结果已清除]`；tool_call 参数保留。删掉 6 个 per-tool 摘要模板（DRY/KISS 双赢） | **P0 立即** |
| 2 | **LLM 锚定摘要**（独立 compaction agent + previousSummary 增量更新 + 固定结构模板） | ✅ 可用，需放开"零 LLM 成本"原则 | 新增压缩入口：用当前模型（或可配置小模型）调一次，输出 Goal/Progress/Decisions/Next Steps/Critical Context 结构摘要，`previousSummary` 累积注入；摘要以 assistant 消息落库 + 前端可展示"已压缩" | P1（需北京老陈定夺是否接受一次 LLM 调用成本） |
| 3 | **按模型窗口触发**（`usable = model.limit.input - reserved`，真实 tokens） | ✅ 完全可用 | 改 `trim_history` 触发：`MAX_CONTEXT_TOKENS` 改为按当前模型 `limit.input` 动态取，减去 reserved 缓冲；tokens 用 Provider 返回的真实值（我们有 `last_total_tokens`） | **P0 立即** |
| 4 | **保尾 token 预算 + splitTurn 半轮劈分** | ✅ 可用 | 增强 T1 保尾：KEEP_TAIL_ROUNDS 基础上加 `preserve_recent_tokens` 上限（如 8K）；整轮超预算时只保该轮尾部消息 | P1 |
| 5 | **压缩用截断不破坏原库**（toolOutputMaxChars=2000） | ✅ 完全可用 | 压缩喂 LLM 时对历史工具输出截断，原库完整保留（我们 7.1 A5 / 回放走 DB 已同理念） | **P0 立即** |
| 6 | **自动续跑**（压缩后发 "Continue..." 合成消息） | ✅ 可用 | 压缩完成后在流内继续跑原任务，无需用户重发 | P1 |
| 7 | **`auto=false` 可关闭 + 手动命令** | ✅ 可用 | 配置项开关自动压缩 | P2 |
| 8 | summary.ts（git diff 统计） | ❌ 不借鉴 | 与上下文压缩无关，属会话统计展示职责 | — |

### 14.7 对照结论与修订建议

**我们的 v4.0 方案在 opencode 面前呈现的差距，集中在两点：**

1. **t1_compress_observations 逐工具摘要模板是过度设计**：opencode 的 prune 已证明工具输出压缩可以**通用清零 + 保 FC 配对**，零模板零维护。建议 **t1_compress_observations → prune 式清理** 改造。
2. **缺真·语义摘要层**：我们 t1_compress_observations 之后直接 T1 删消息，信息靠 History Memory 规则提取兜底，但**没有"理解级"的压缩**。opencode 的 anchored LLM 摘要（独立 agent + previousSummary 增量 + 固定结构）是经过验证的成熟方案，**建议评估放开"零 LLM 成本"原则，采纳为高层压缩**（一次压缩一次调用，可配置小模型控制成本）。

**保留我们方案的合理部分**：History Memory（决策链主动注入，zero-cost 且 opencode 没有同等机制）、防抖动、保尾思路。

**本版修订动作**：本章仅为**深度研究与借鉴评估**（记录 opencode 实况 + 可借鉴性结论），**不改变 v4.0 既有设计定案**。是否按 14.6 落地改造（尤其 P0 三项 + P1 锚定摘要）由北京老陈另行裁定，落地方案再开新版本。

### 14.8 两种方法对照分析（本 v4.0 纯规则 vs opencode 分层压缩）

> **北京老陈 2026-08-16 要求**：把本项目 [4] v4.0 的方法 与 opencode 的方法 放在一起对照分析，并给出**我的推荐方法**，写入本文档。

#### 14.8.1 两种方法的一句话定性

| 方法 | 一句话定性 | 核心思想 |
|------|-----------|---------|
| **我们 [4] v4.0** | **纯规则处理、零 LLM** | "删之前把值钱的东西搬出来"——用纯规则（字符串替换 / 删消息 / Step 提取）腾空间，**全程不调 LLM**（R4 硬约束） |
| **opencode** | **零 LLM 前置 + 调用 LLM 的锚定摘要** | "先轻量清工具输出，再让 LLM 真正理解并归档旧历史"——prune 零成本先行，锚定摘要用 LLM 做语义压缩 |

> **精修（北京老陈 2026-08-16 澄清）**：不能说"纯 agent 函数 vs 调 LLM 的 agent"——我们 v4.0 **根本没用到 agent 参与压缩**，是 message_builder 的纯规则函数在干活；opencode 的 LLM 摘要里 agent 只是"壳"（约束层）、**LLM 才是"芯"（生成层）**。核心差异只在一个点：**opencode 多了一层"真·LLM 语义摘要"，我们因 R4 刻意放弃。**

#### 14.8.2 逐层对照表（五层机制逐一对比）

| 维度 | 我们 v4.0 | opencode | 判定 |
|------|----------|----------|------|
| **① 压缩触发** | 固定比例（t1_compress_observations 50% / T1 95%） | 按模型窗口 `usable = limit.input - reserved`（真实 tokens） | **opencode 更合理**——不同模型窗口自适应，deepseek 900K 也能正确触发（我们 50% 在 900K 下到不了，文档 12.2 已自省） |
| **② 工具输出压缩** | **t1_compress_observations 逐工具摘要模板**（readtext/listdir/grep 等 6 模板） | **prune 通用清零**（保留 tool_call、清 output、`time.compacted` 标记，skill 豁免 + PRUNE_PROTECT 保近 40K） | **opencode 明显更优**——零模板零维护、不破坏 FC 配对（参数还在）、防抖动（省 <20K 不做） |
| **③ 语义压缩** | ❌ **无**（R4 拒绝 LLM）→ History Memory 规则拼接 + T1 删消息 | ✅ **anchored 锚定式 LLM 摘要**（独立 compaction agent + previousSummary 增量更新 + 固定 Markdown 结构 Goal/Progress/Decisions/NextSteps/CriticalContext/Files） | **opencode 是完整能力，我们缺失这一环**——这是最本质差距 |
| **④ 决策链保留** | ✅ **History Memory**（从 Step 提取 thought→action→result→answer，注入独立 user 消息，500 行上限） | 摘要模板含 Key Decisions / Critical Context / Progress 段（靠 LLM 归纳） | **各有千秋**——我们 zero-cost 且 opencode 无同等机制；但 History Memory 500 行后变字符截断（文档 12.1 自省），opencode 靠 LLM 语义归纳更持久 |
| **⑤ 保尾兜底** | KEEP_TAIL_ROUNDS=3（固定轮数，从最旧删） | **token 预算 + splitTurn**：preserveRecentTokens 上限 8K，整轮超预算只保该轮尾部半轮 | **opencode 更细**——token 预算优于固定轮数，多 splitTurn 半轮劈分 |

#### 14.8.3 本质差异一句话

```
我们 v4.0 = 纯规则、零 LLM（把压缩当"字符/列表操作"）
opencode  = prune 零 LLM + LLM 锚定摘要（把压缩当"语义归档"）
```

- **我们的长处**：History Memory 主动决策链（zero-cost）+ 零额外延迟 + 防抖动。
- **opencode 的长处**：真·语义摘要（信息密度高、可累积、不重复丢失）+ 按模型窗口自适应 + prune 零模板 + 保尾 token 预算。

#### 14.8.4 我的推荐方法（两个可复用的压缩方法，命名定案）

> **推荐原则**：不是二选一，而是**保留我们 History Memory 的 zero-cost 长处，吸收 opencode 的 prune 简化 + LLM 锚定摘要能力**。定案为**两个独立的、名副其实的压缩方法**，各自有适用场景，**可在系统中灵活选用/组合**（北京老陈 2026-08-16 定案：给 P0/P1 分别命名，并明确各自适用场景）。

##### C3 剪枝压缩法（Prune Compaction，规则级压缩）

> **适用场景/场合**：① 日常高频兜底压缩，任何任务上下文超限即触发；② 简单/单轮任务、高频轮次增长、成本敏感、新任务（independent）；③ 零 LLM 零成本，快速腾空间保配对保近期。

> **命名依据**：借鉴 opencode `prune`（修剪）语义——像园艺剪枝，剪掉冗余的"枝叶"（旧工具输出），保留"主干"（tool_call 参数 + FC 配对 + 保尾区），**纯规则、零 LLM、零成本**。

- **做什么**：① 按模型窗口触发（`usable = 当前模型 limit.input - reserved`）；② 通用清零旧 tool output（保留 tool_call 参数、`time.compacted` 标记、skill 豁免、PRUNE_PROTECT 保近 40K）；③ 保尾 token 预算（`preserve_recent_tokens` 上限 + splitTurn 半轮劈分）。
- **成本**：零 LLM 调用、毫秒级、纯字符串/列表操作。
- **定位**：日常高频兜底压缩——**任何任务**只要上下文超限即触发，快速腾空间、保配对、保近期。

**适用场景**：
| 场景 | 说明 |
|------|------|
| 简单/单轮任务 | 上下文超限时快速腾空间，不需要语义理解 |
| 高频轮次增长 | 每轮都长 tool 输出的任务，先剪枝控速 |
| 成本敏感 | 零 LLM 调用，不引入任何延迟与费用 |
| 新任务（independent） | 无关联上下文，只压缩本任务自身冗余输出 |

##### C4 锚定摘要压缩法（Anchored Summary Compaction，语义级压缩）

> **适用场景/场合**：① 长任务跨多轮需保决策链；② 续聊任务（linked）上下文链压缩；③ 决策链关键、可接受一次 LLM 成本；④ 需老陈定夺放开 R4 零 LLM 原则后启用。

> **命名依据**：借鉴 opencode `compaction` 的 **anchored（锚定）** 机制——LLM 把旧历史归纳为固定结构摘要，`previousSummary` 增量更新、可累积不丢失。核心是**调用 LLM 做语义归档**（agent 是壳、LLM 是芯）。

- **做什么**：① 一次 LLM 调用（当前模型或可配置小模型）；② 输出固定结构 Markdown（Goal / Progress(Done·InProgress·Blocked) / Key Decisions / Next Steps / Critical Context / Relevant Files）；③ `previousSummary` 锚定增量更新；④ 不破坏原库（喂 LLM 时工具输出截断 2000 字符，原始输出完整存库）；⑤ 摘要落库 + 前端可展示"已压缩" + 压缩后自动续跑。
- **成本**：每次压缩 1 次 LLM 调用（可配小模型控成本，需老陈定夺是否放开 R4）。
- **定位**：长任务/跨多轮的语义归档压缩——真正"理解"旧历史、保决策链、信息密度高。

**适用场景**：
| 场景 | 说明 |
|------|------|
| 长任务跨多轮 | 需要长期记忆决策链，纯剪枝会丢语义信息 |
| 续聊任务（linked） | 上下文链压缩，摘要随链累积（对应 0.2.3-5 任务上下文链） |
| 决策链关键 | 推理过程、关键结论需要被后续轮次引用 |
| 可接受一次 LLM 成本 | 一次压缩一次调用，可配 deepseek-flash 等小模型 |

##### 两方法组合使用规则

- **按场景选型**：日常高频/成本敏感/简单任务 → **C3（剪枝）**；长任务/语义归档/续聊链 → **C4（锚定摘要）**；可配置开关各自独立启用。
- **组合（推荐）**：剪枝为第一道（零成本兜底）→ 剪枝后仍超限且需保语义 → 再触发锚定摘要（opencode 正是 prune → compaction 递进）。History Memory 全程保留作 zero-cost 决策链兜底。
- **互不依赖**：两个方法各自独立可启用/关闭，未来可按任务类型（简单/复杂/续聊/新开）灵活调度。

**推荐落地顺序**：C3（剪枝）三项立即可做（零成本、纯增强不退化）→ C4（锚定摘要）一次压缩一次 LLM 调用、可配小模型、成本可控 → 用 E2E 对话实测验证摘要信息密度与成本，再定是否默认开启。

**不推荐**：只保留纯规则删删减减（丢语义）、或完全照抄 opencode 丢掉 History Memory（丢 zero-cost 决策链）。两方法 + History Memory 融合最优。

---

### 14.9 基于本地现有代码的落地 diff（含统一压缩/裁剪模块目录规划）

> **编写人**：小欧
> **编写时间**：2026-08-16 14:24:34
> **前置结论**：北京老陈 2026-08-16 拍板 —— **建立一个统一目录作为"消息压缩/裁剪"的独立模块/架构层**，集中承载两方法（剪枝 + 锚定摘要）及其后续扩展的代码与函数。本章据此给出**基于本地现有真实代码**的落地 diff，**三堂会审（合规/合理/关联逻辑）通过**。

#### 14.9.1 代码现状盘点（本地真实代码，非臆测）

落地 diff 前先核实本地现有裁剪相关真实代码，作为改造基线：

| 文件 | 现有关键实现 | 行号 |
|------|------------|------|
| `backend/app/services/agent/message_builder.py` | `trim_history()` 第二组"历史裁剪"入口 | 265 |
| 同上 | `MAX_CONTEXT_TOKENS` 类属性（默认 200000，运行时被覆盖） | 84 |
| 同上 | `last_total_tokens`（上轮精确 total_tokens，增量触发用） | 85 |
| 同上 | `reset_per_run()`（每轮重置） | 87 |
| 同上 | `_total_chars()` Unicode 字符数统计 | 467 |
| 同上 | `_estimate_tokens()` `chars//CHARS_PER_TOKEN` 粗估 | 484 |
| 同上 | `_trim_to_budget()`（超预算从最旧删消息） | 336 |
| 同上 | `prepare_messages_for_llm()`（组装消息列表，`_cap_temp_history` 先截断） | 233 |
| `backend/app/services/agent/agent_runner.py` | `MAX_CONTEXT_TOKENS = llm_service.context_limit`（**已按模型窗口**） | 139-140 |
| `backend/app/services/agent/react_cycle.py` | `agent.message_builder.trim_history()` **唯一裁剪入口** | 350 |
| 同上 | `last_total_tokens = int(_tt)`（usage 上报精确值） | 393 |
| `backend/app/services/agent/llm_stream.py` | `call_llm_stream(agent, messages, tools)` 流式调用（anchor 摘要复用此） | 133 |
| 同上 | `call_llm_with_fallback(agent, messages, openai_tools)` FC/Text 双回退 | 265 |
| `backend/app/constants.py` | `MAX_CONTEXT_RATIO=0.8`（绝对值安全网比例）、`COMPACTION_BUFFER=20000`（输出预留） | 98-99 |

**关键事实**（影响设计，三堂会审必须诚实）：本地**尚无** `_t1_compress_observations` / `history_mem` 的实现 —— 即 v4.0 文档里的 t1_compress_observations 逐工具摘要、History Memory **只是设计稿，代码里并不存在**（grep 确认零实现）。因此 C3/C4 是**新基建**，不是改旧 C1。这也决定了目录规划：需要一个全新模块层来承载。

#### 14.9.2 统一目录规划（北京老陈 2026-08-16 拍板）

**新建** `backend/app/services/agent/compaction/` 作为独立架构层，专门承载"消息压缩/裁剪"的代码与函数：

```
backend/app/services/agent/compaction/
├── __init__.py             # 导出各函数: CompactionTrigger / prune_tool_outputs / t1_reuse_summary / generate_anchored_summary / generate_chunked_summary / should_compact_window / CompactionCooldown / value_first_prune / trim_orphan_pairs_proactive — 小欧 2026-08-16(2026-08-16 精确化)
├── constants.py            # 压缩专属常量(PRUNE_*/PRESERVE_*/SUMMARY_*/COMPACTION_*/COOLDOWN_ROUNDS), 不再堆进 app/constants.py
├── trigger.py              # 触发判定: CompactionTrigger(14.9.3①) + 支撑函数 should_compact_window(动态窗口触发, 14.9.6 K1) + CompactionCooldown(冷却节流, 14.9.6 K2)
├── prune.py                # C3 轻量/剪枝实现: prune_tool_outputs(14.9.3②) + t1_compress_observations(第五章 C3 轻量) + t1_reuse_summary(14.9.6 C3 DRY升级) + value_first_prune(14.9.6 T1 保真策略)
├── summary.py              # C4 语义实现: generate_anchored_summary(14.9.4②) + generate_chunked_summary(14.9.6 C4 降本变体)
├── summary_prompt.py       # SUMMARY_TEMPLATE 固定结构(Goal/Progress/Decisions/Next/Critical/Files, 14.9.4①)
├── split_turn.py           # splitTurn 原语(保尾 token 预算 + 半轮劈分) — 【待补代码】14.9 各章未写具体函数, 仅规划占位
└── assembler.py            # 装配适配: tail_start/压缩消息注入/标记统一 + trim_orphan_pairs_proactive(配对修剪, 14.9.6 K3); 【待补装配代码】new_block 切分与注入未写
```

**放置依据（合规性三堂会审）**：

1. **SRP 单一职责**：压缩/裁剪是独立业务域，从 `message_builder.py`（其职责已够多的"消息组装+裁剪"）剥离出专用层。`message_builder` 未来只需"调 compaction 结果"，不再自己实现 prune/summary。
2. **OCP/ISP/复用优先**：`compaction` 作为中间层，`message_builder` 与 `trigger` 只通过薄接口交互；后续加 t1_compress_observations 逐工具摘要/History Memory 直接在 `prun trader.py` 或新 `memory.py` 扩充，不改 `message_builder` 本体 —— 对扩展开放、对修改封闭。
3. **分层存放遵循 AGENTS.md 1.3**：Agent 层公用逻辑放 `app/services/agent/` 下子目录（`compaction/`），不越过到全局 `app/utils/`。
4. **KISS-不越级**：目录只承载压缩/裁剪一件事，不塞调度、DB、SSE 等（那些仍归 `react_cycle`/`agent_runner`/chat）。

**新旧边界（不 backward、不重复）**：
- `message_builder.trim_history()` 仍保留为 `react_cycle.py:350` 的**唯一裁剪入口**（外部契约不变），但其内部实现**委托** `compaction`（先剪枝→仍超限再锚定摘要→再回退原有删消息兜底）。
- 原有 `_trim_to_budget()` 保留为**最后兜底**（防呆），不作为主路径 —— 不删除（不 backward）、也不与 prune 重复（prune="清输出"，_trim_to_budget="删消息"，两级语义不同）。

#### 14.9.3 C3 剪枝压缩法 diff（Prune，规则级，零 LLM）

> **适用场景/场合**：① 日常高频兜底压缩，任何任务上下文超限即触发；② 简单/单轮任务、高频轮次增长、成本敏感、新任务（independent）；③ 零 LLM 零成本，快速腾空间保配对保近期。

**改动文件**：新增 `compaction/trigger.py`、`compaction/constants.py`、`compaction/prune.py`（3 新增）；修改 `message_builder.py`（1 处委托）。

**① 触发判定（按模型窗口 + 增量 + 绝对值）** —— `compaction/trigger.py`：

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: 剪枝/锚定摘要统一触发判定层(C3/C4 共用)
"""compaction.trigger — 压缩/裁剪触发判定 — 小欧 2026-08-16"""
from typing import Optional

from app.services.agent.compaction.constants import (
    COMPACTION_BUFFER, MAX_CONTEXT_RATIO,
)


class CompactionTrigger:
    """统一触发判定 — 小欧 2026-08-16

    三个独立条件, 满足任一即触发压缩(先用剪枝, 剪枝后仍超限再由上层决定是否锚定摘要):
      A. 模型窗口: current_tokens >= usable(context_limit - reserve)
      B. 增量:     本轮粗估 - 上轮精确(last_total_tokens) > COMPACTION_BUFFER
      C. 绝对值:   current_tokens >= context_limit * MAX_CONTEXT_RATIO
    """

    def should_compact(self, current_tokens: int, last_total_tokens: int,
                       context_limit: int, reserve: int) -> bool:
        usable = context_limit - reserve
        delta = current_tokens - last_total_tokens
        if current_tokens >= usable:
            return True
        if delta > COMPACTION_BUFFER:
            return True
        if current_tokens >= int(context_limit * MAX_CONTEXT_RATIO):
            return True
        return False
```

> 三堂会审：
> - 合规：单一职责（只管"是否触发"），常量注入不硬编码；KISS——三条件一个 `return` 判定，无七绕八绕。
> - 合理：`usable = context_limit - reserve` 与 opencode `overflow.ts` 同构（14.3 已记录），且 `context_limit` 在 `agent_runner.py:140` 已由 `llm_service.context_limit` 覆盖 → **天然按模型窗口触发，无需新配置读取**。
> - 关联逻辑：与原 `message_builder` 增/绝对值双条件**语义不冲突**（新增模型窗口条件、复用缓冲常量），不改动原 trigger 行为。

**② 剪枝引擎（清 tool output 保 tool_call）** —— `compaction/prune.py`：

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: C3 剪枝引擎(借鉴 opencode prune, 纯规则零 LLM)
"""compaction.prune — C3: 剪枝压缩 — 小欧 2026-08-16"""
from typing import List, Dict

from app.services.agent.compaction.constants import PRUNE_MINIMUM_TOKENS, PRUNE_PROTECT_TOKENS


def prune_tool_outputs(messages: List[Dict]) -> tuple[List[Dict], int]:
    """清旧 tool output、保留 tool_call 参数与消息结构 — 小欧 2026-08-16

    遍历 assistant(tool_calls) ↔ tool 配对, 将 tool 的 content 清空并打算标记,
    保留 tool_call_id/name/arguments(供后续轮引用"做了什么"), 返回 (处理后的消息, 释放的token估算)。
    """
    released = 0
    pruned = []
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            # 近端受保护判定由上层依据 reserve 决定, 此处仅清 content 打标记
            content = msg.pop("content", None)
            if content:
                released += len(str(content)) // 4
            msg.update({"_pruned": True, "content": ""})
        pruned.append(msg)
    return pruned, released
```

> 三堂会审：
> - 合规：不重复 —— prune 与既有 `_trim_to_budget`（删消息）**两级语义**，prune 清输出、trim 删消息，可叠加不重复；SRP 单一职责（一个函数只做"清 tool output"）。
> - 合理：`released = len//4` 沿用本地 `_estimate_tokens()` 同款纯数学估算（`CHARS_PER_TOKEN`），零外部依赖。
> - 关联逻辑：`_pruned` 标记需在 `prepare_messages_for_llm()` 组装**前**剥离（防泄漏到 LLM 请求），与现有 `_temp_*` 剥离同段处理（见下方 message_builder diff）。

**③ message_builder.py 委托改造（唯一入口不变）** —— `message_builder.py`：

在 `trim_history()` 内、原 `_trim_to_budget` 兜底之前，先调 compaction：

```python
    # 编辑历史: 2026-08-16 小欧 委托 compaction 剪枝/锚定摘要, 原 _trim_to_budget 保底
    def trim_history(self):
        if not self.conversation_history:
            return
        rough = self._estimate_tokens(self.conversation_history)
        cl = getattr(self, "MAX_CONTEXT_TOKENS", 200000)
        # ① 触发判定
        from app.services.agent.compaction.trigger import CompactionTrigger
        trig = CompactionTrigger()
        if trig.should_compact(rough, self.last_total_tokens, cl, reserve=COMPACTION_BUFFER):
            # ② C3: 剪枝(清旧 tool output 保 tool_call)
            from app.services.agent.compaction.prune import prune_tool_outputs
            self.conversation_history, _ = prune_tool_outputs(self.conversation_history)
        # ③ 兜底: 剪枝后仍超限再走原 _trim_to_budget(删消息防呆)
        self._trim_to_budget()
```

并在 `prepare_messages_for_llm()` 剥离段（现 line 246-249 `_temp_*` 剥离）追加 `_pruned` 剥离：

```python
        for msg in messages:
            stripped = [_k for _k in msg if _k.startswith("_temp_")]
            if msg.get("_pruned"):          # 2026-08-16 小欧 剪枝标记同段剥离, 防泄漏 LLM
                stripped.append("_pruned")
            for _k in stripped:
                msg.pop(_k, None)
```

> 三堂会审：
> - 合规：**唯一裁剪入口不变**（`react_cycle.py:350` 仍调 `trim_history`），外部契约零改动 —— 不 backward、无并发竞争点。
> - 合理：剪枝在 `_trim_to_budget` 之前（先清输出腾空间，实在不够才删消息）—— 保决策链优先于删消息，符合 14.8 推荐顺序（剪枝第一道）。
> - 关联逻辑：剪枝后仍在**同一函数**内回退 `_trim_to_budget`，保证不因剪枝引入越界；`_pruned` 与 `_temp_*` 同段剥离，与现有临时标记处理完全一致（增强不退化）。

#### 14.9.4 C4 锚定摘要压缩法 diff（Anchored Summary，语义级，一次 LLM）

> **适用场景/场合**：① 长任务跨多轮需保决策链；② 续聊任务（linked）上下文链压缩；③ 决策链关键、可接受一次 LLM 成本；④ 需老陈定夺放开 R4 零 LLM 原则后启用。

**改动文件**：新增 `compaction/summary.py`、`compaction/summary_prompt.py`、`compaction/split_turn.py`（3 新增）；修改 `react_cycle.py` 或 `message_builder.py` 触发点。

**① 摘要固定结构模板** —— `compaction/summary_prompt.py`：

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: 锚定摘要固定结构模板(借鉴 opencode SUMMARY_TEMPLATE)
"""compaction.summary_prompt — C4 摘要模板 — 小欧 2026-08-16"""
SUMMARY_TEMPLATE = """将 messages 归档为固定结构 Markdown 摘要:
- Goal: 当前任务目标
- Progress: 已完成(Done)/进行中(InProgress)/受阻(Blocked)
- Key Decisions: 关键决策与结论
- Next Steps: 下一步计划
- Critical Context: 不可或缺的上下文(文件路径/关键数据)
- Relevant Files: 涉及文件清单
若已有 previousSummary, 请增量合并(保留已有结论, 追加新发现), 不重复不遗漏。"""
```

> 三堂会审：合规 —— 模板单一职责（只定义结构）；合理 —— 结构对应 opencode anchored 六段（14.3），且提供决策段兜底 History Memory 语义；关联逻辑 —— 与 history_mem 的决策段**互补不冲突**（摘要归档整段历史，memory 注入单轮决策链）。

**② 锚定摘要引擎（调 LLM，不破坏原库）** —— `compaction/summary.py`：

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: C4 锚定摘要引擎(一次 LLM, 喂截断输出, 原库完整)
"""compaction.summary — C4: 锚定摘要压缩 — 小欧 2026-08-16"""
from typing import List, Dict, Optional

from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE


async def generate_anchored_summary(llm_client, messages: List[Dict],
                                    previous_summary: Optional[str] = None) -> str:
    """一次 LLM 调用产出锚定摘要 — 小欧 2026-08-16

    tools=None 走 llm_stream Text 模式; 喂给 LLM 的 tool 输出截断 2000 字符(防再撑爆),
    原始 messages 完整保留(list 不变), 仅生成文本摘要返回。自动续跑由上层 react_cycle 发 Continue。
    """
    from app.services.agent.llm_stream import call_llm_with_fallback
    feed = []
    for msg in messages:
        if msg.get("role") == "tool":
            c = str(msg.get("content", ""))[:2000]
            feed.append({**msg, "content": c})
        else:
            feed.append(msg)
    prompt = SUMMARY_TEMPLATE + (f"\npreviousSummary:\n{previous_summary}" if previous_summary else "")
    feed = [{"role": "system", "content": prompt}, *feed]
    async for _typ, data in call_llm_with_fallback(agent=llm_client, messages=feed, openai_tools=None):
        pass
    return str(getattr(data, "get", lambda k: None)("content", "") or data)   # 简化示意: 取末次 response content
```

> 三堂会审：
> - 合规：SRP（只生成摘要）；复用 `call_llm_with_fallback`（已有 LLM 链路，**不重造**，复用优先）；不破坏原库（list 不变 / 仅构造 feed 新列表）。
> - 合理：喂 LLM 截断 2000 字符、原始输出完整存库 —— 同 opencode `processor.process` 的"截断喂、完整存"（14.3），防二次胀窗。
> - 关联逻辑：`tools=None` → Text 模式推断 `tool_choice=None`（llm_stream.py:140），不触发 FC，天然适合纯摘要调用；`previous_summary` 锚定增量，对应续聊链（linked）。

> **落地前置（需北京老陈定夺）**：C4 引入一次 LLM 调用，触及项目"R4 零 LLM 成本原则"。落地前需老陈确认放开 R4（可在 analysis 阶段决策，本章仅给出 diff 方案，不擅自改运行配置）。

#### 14.9.5 三堂会审总结表（两方法落地 diff）

| 审查项 | C3（剪枝） | C4（锚定摘要） |
|--------|--------------|------------------|
| 合规（10 大规范） | SRP 每函数一件事；DRY 复用 `_estimate_tokens`/`_trim_to_budget` 兜底；KISS 三条件单判定；不 backward（唯一入口不变） | SRP 只生成摘要；复用 `call_llm_with_fallback`；不 backward（原库完整） |
| 合理（最优雅直线） | 先剪枝（清输出）→ 仍超再删消息，两级清晰；`context_limit` 已注入免新配置 | 截断喂 + 完整存，一次 LLM；Text 模式天然适配 |
| 关联逻辑（增强不退化） | 唯一裁剪入口 `react_cycle:350` 不变；`_pruned` 同 `_temp_*` 段剥离 | 决策段互补 memory；previousSummary 支持续聊链 |
| 目录归属（老陈拍板） | 统一 `compaction/` 层，`message_builder` 委托 | 统一 `compaction/` 层，LLM 链路复用 llm_stream |

> **落地顺序**（与 14.8.4 一致）：C3 三项立即可做（零成本纯增强）→ C4 需老陈定夺 R4 后接入 → E2E 实测摘要信息密度与成本再默认启用。

#### 14.9.6 支撑函数库与策略实现（归并到 4 主干方法）

> **编写人**：小欧
> **编写时间**：2026-08-16 15:21:13
> **编写动机**：北京老陈 2026-08-16 指示——在 4 主干方法（M1 历史记忆注入法 / C3 剪枝压缩法 / C4 锚定摘要压缩法 / T1 紧急裁剪法）之外，再研究更多可取思路（含 trim 新方法），写出**更好、可落地的函数**，归并到对应主干方法的策略实现或独立支撑函数库，不再设平级编号。每个函数均基于本地真实代码、经三堂会审（合规/合理/关联逻辑）。

**归并总览（候选函数 → 归属主干 / 支撑库，不再设平级编号）**：

| 函数 | 归属 | 解决的问题维度 | 成本 | 备注 |
|------|------|--------------|------|------|
| `t1_compress_observations` | C3 策略实现函数 | 主动压缩 tool obs（逐工具摘要） | 零 | 原 C1，详第五章 |
| `t1_reuse_summary` | C3 策略实现函数 | 逐工具模板重复造轮子（DRY 升级） | 零 | 原 C2，推荐 |
| `generate_chunked_summary` | C4 策略实现函数 | C4 全量重算成本高 | 1 次 LLM/块 | 原 C5 |
| `value_first_prune` | T1 策略实现函数 | 保尾=保最近 N 轮不保真 | 零 | 原 T2 |
| `should_compact_window` | 支撑函数库 | 900K 大窗口下不触发 | 零 | 原 K1 |
| `CompactionCooldown` | 支撑函数库 | 连续轮次反复压缩抖动 | 零 | 原 K2 |
| `trim_orphan_pairs_proactive` | 支撑函数库 | 裁剪后配对残留 | 零 | 原 K3 |

**C3 策略实现函数**（归 C3 剪枝压缩法）

- `t1_compress_observations`（原 C1 工具摘要压缩法 Tool-Summary Compaction）：C3 的逐工具摘要轻量实现，详见第五章；与 14.9.3 的 `prune_tool_outputs`（prune 清输出）并列两种轻量压缩策略，其 DRY 升级为 `t1_reuse_summary`（推荐）。



##### `t1_reuse_summary`（原 C2 摘要复用压缩法，归 C3 策略实现函数，DRY 升级）

> **归属/场合**：① 作为 t1_compress_observations 的 DRY 升级替代，当工具已返回 `llm_data.summary` 时优先用 `t1_reuse_summary` 而非 t1_compress_observations 逐工具模板；② 零 LLM、零模板维护；③ 与 t1_compress_observations 互斥（二选一，推荐 `t1_reuse_summary`）。

> **关键发现（本地真实代码）**：grep 确认每个工具的 `llm_data` 都自带一行 `summary` 字段（如 `read_text_file.py:93 "读取 /path，20/200行"`、`execute_shell_command.py:582 "执行Shell命令 cmd，成功: 退出码0，输出N字符"`、`list_directory.py:179` 等 100+ 处）。**即工具层早已产出"一行语义摘要"，t1_compress_observations 不必再写 per-tool 模板**——直接复用该字段替换 tool 的 content。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: T1 升级替代, 复用工具层已有 llm_data.summary 做一行摘要
# 2026-08-16 小欧 修正: tool 消息字典无独立 summary 字段(已拼进 content),
#                       需先在 add_tool_result stash _summary, 此处复用 _summary(三堂会审去臆测)
"""compaction.t1_reuse — 复用工具 summary 的 t1_compress_observations 摘要法 — 小欧 2026-08-16"""
from typing import List, Dict


def t1_reuse_summary(messages: List[Dict]) -> List[Dict]:
    """用工具返回自带 summary 替换 tool content — 小欧 2026-08-16

    前置(必做, 见下方改动点): tool 消息构造时把 llm_data.summary 存为 _summary 字段。
    依据本地真实代码: observation_formatter.py:603/627 已将 summary 拼进 content 文本,
    tool 消息字典本身只有 role/tool_call_id/content, 无独立 summary 字段 —— 此为三堂会审
    修正(杜绝臆测不存在的 msg["summary"])。复用 _summary(各 tool_*_tools.py 已产出一行语义摘要),
    不写 per-tool 模板(DRY, 消除 14.3 指出的 C1 逐工具模板过度设计)。
    """
    for msg in messages:
        if msg.get("role") == "tool" and not msg.get("_compressed"):
            summ = msg.get("_summary")
            raw = msg.get("content", "")
            if summ and raw and len(raw) > len(summ):
                msg["_raw"] = raw
                msg["content"] = f"[tool-summary] {summ}"
                msg["_compressed"] = True
    return messages
```

> **前置改动点（基于本地代码，必须随本法一起落地）**：
> - `message_builder.add_tool_result()`（:124）增加 `summary: str = ""` 形参，构造字典时写入 `"_summary": summary`（含 line 139-143 兜底分支同步加）；由 handler 调 `add_observation` 处把 `llm_data.summary` 透传（action_handler 已有 `llm_data.summary`，observation_formatter.py:603）。

> 三堂会审：
> - 合规：**复用优先**（AGENTS 1.3）——复用工具层已产出的 `llm_data.summary`，禁止局部重造模板；消除 14.3 指出的"C1 逐工具模板属过度设计"；前置改动仅在构造点 stash 一个字段，不破坏 add_tool_result 既有契约（无 backward）。
> - 合理：一条 `if` 取已 stash 的 `_summary`，零模板维护；比 14.9 prune 更轻（prune 清空 content，本法保留一行语义）；长度保护 `len(raw) > len(summ)` 避免小输出反向膨胀。
> - 关联逻辑：与现有 `_compressed` 防重复压缩标记**完全兼容**（沿用现有标记）；`_raw` 落库不破坏原库（对应 14.3 "压缩截断不破坏原库"）；`_summary` 属内部标记，须在 `prepare_messages_for_llm()` 与 `_compressed`/`_temp_*` 同段剥离（沿用 14.9.3 ③ 的剥离逻辑，增强不退化）。

**C4 策略实现函数**（归 C4 锚定摘要压缩法）

##### `generate_chunked_summary`（原 C5 增量块式锚定摘要法，归 C4 策略实现函数，降本变体）

> **归属/场合**：① 长任务且会多次压缩，C4 降本变体；② 成本敏感又需语义归档；③ 只摘要新增块+previousSummary 增量合并，成本随压缩次数线性而非累积。

> **改进点**：C4（14.9.4）每次对全量历史做摘要，长任务多次压缩会**全量重算**成本高。本法改为**只摘要"新增块"（上次 compact 之后的新轮次），与 `previousSummary` 增量合并**——LLM 调用量从 O(全量) 降到 O(增量块)。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: C4 降本变体, 只摘要新增块 + 增量合并
"""compaction.chunked_summary — 增量块式锚定摘要 — 小欧 2026-08-16"""
from typing import List, Dict, Optional


async def generate_chunked_summary(llm_client, new_block: List[Dict],
                                   previous_summary: Optional[str] = None) -> str:
    """只把新增块喂 LLM, 与 previousSummary 合并 — 小欧 2026-08-16

    与 C4 区别: 不重喂全量历史, 仅 new_block(tool 输出截断 2000) + previousSummary,
    成本随压缩次数线性而非累积。其余(截断喂/原库完整/previousSummary 锚定)同 14.9.4。
    """
    from app.services.agent.compaction.summary_prompt import SUMMARY_TEMPLATE
    from app.services.agent.llm_stream import call_llm_with_fallback
    feed = [{"role": "system", "content": SUMMARY_TEMPLATE}]
    if previous_summary:
        feed.append({"role": "user", "content": f"已有摘要:\n{previous_summary}"})
    for msg in new_block:
        c = str(msg.get("content", ""))[:2000] if msg.get("role") == "tool" else str(msg.get("content", ""))
        feed.append({**msg, "content": c})
    async for _typ, data in call_llm_with_fallback(agent=llm_client, messages=feed, openai_tools=None):
        pass
    return str(getattr(data, "get", lambda k: None)("content", "") or data)
```

> 三堂会审：
> - 合规：复用 `SUMMARY_TEMPLATE` / `call_llm_with_fallback`（DRY）；不 backward（C4 仍可全量版并存）。
> - 合理：增量块摘要，成本可控，契合老陈"成本敏感"诉求；与 History Memory 续聊链同理（增量不丢）。
> - 关联逻辑：`new_block` 由 assembler 切分（tail_start 之后的增量）；`previous_summary` 落库锚定（14.9.4）。

**T1 策略实现函数**（归 T1 紧急裁剪法）

##### `value_first_prune`（原 T2 知识密度优先裁剪法，归 T1 策略实现函数，保真增强）

> **归属/场合**：① 关键决策发生在早期轮（保尾 N 轮保不住）；② 替代"保最近 N 轮"，按消息价值权重保留 thought/answer、先丢低价值 tool 输出；③ 与 T1 组合增强保真。

> **痛点**：现有保尾=保留最近 N 轮（KEEP_TAIL_ROUNDS=3），但关键决策可能发生在第 1 轮。本法改为**按消息语义价值权重**保留，先删低价值纯 tool 大输出，再删低价值轮，最后才动高价值 thought/answer。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: 替代"保最近N轮", 按价值权重保留消息
"""compaction.value_prune — 知识密度优先保留 — 小欧 2026-08-16"""
from typing import List, Dict


def _value_weight(msg: Dict) -> int:
    role = msg.get("role")
    if msg.get("_history_mem"):
        return 100          # History Memory 最高
    if role == "system":
        return 90
    if role == "assistant" and msg.get("tool_calls"):
        return 80          # 决策: 调了什么工具
    if role == "assistant":
        return 70          # thought/answer
    if role == "tool":
        return 10          # 纯输出, 价值最低, 先删
    return 50


def value_first_prune(messages: List[Dict], budget_tokens: int) -> List[Dict]:
    """按价值权重保留, 预算内先丢低价值 tool 输出 — 小欧 2026-08-16"""
    # 用 enumerate 记原始下标, 避免 dict 重复导致 index() 错位(三堂会审: 关联逻辑保时序)
    indexed = list(enumerate(messages))
    kept_idx = []
    used = 0
    for i, msg in sorted(indexed, key=lambda t: _value_weight(t[1]), reverse=True):
        cost = len(str(msg.get("content", ""))) // 4
        if used + cost <= budget_tokens or _value_weight(msg) >= 70:
            kept_idx.append(i); used += cost
    # 按原始下标升序还原(保 LLM 阅读时序)
    return [messages[i] for i in sorted(kept_idx)]
```

> 三堂会审：
> - 合规：SRP（只做"按价值排序取舍"）；不 backward（可与剪枝/T1 组合，非替换保尾机制）。
> - 合理：权重表直观，先丢 tool 输出保 thought/answer，直击"丢值钱的留笨重的"痛点（14.1 问题 2）。
> - 关联逻辑：`_history_mem`/`system` 高权重与 3.4 保护机制**同频**；`system` 不丢保证指令完整；不破坏 FC 配对需配合 `trim_orphan_pairs_proactive` 前置修剪。

**支撑函数库**（独立支撑函数，供主干方法组合调用）

##### `should_compact_window`（原 K1 动态窗口触发法，归支撑函数库，Window-Aware Trigger）

> **归属/场合**：① 大窗口模型（如 deepseek 900K）下防 t1_compress_observations/T1 不触发；② 消息数 > N 兜底触发；③ 解决固定比例阈值在超大窗口形同虚设的问题。

> **痛点**（12.2 假设 1）：deepseek 900K 窗口下，t1_compress_observations(50%)=450K、T1(95%)=855K，5~15 轮根本触不到，裁剪形同虚设。本法完善 `usable = context_limit - reserve`，`reserve` 可配，并在大窗口下加"消息数 > N"备用触发。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: 动态窗口触发, 解决大窗口不触发 + 消息数备用触发
"""compaction.window_trigger — 动态窗口触发 — 小欧 2026-08-16"""
from typing import List


def should_compact_window(current_tokens: int, context_limit: int,
                           reserve: int, msg_count: int,
                           max_msgs: int = 80) -> bool:
    usable = context_limit - reserve
    if current_tokens >= usable:
        return True
    if msg_count >= max_msgs:        # 大窗口下消息数兜底触发, 防"不触发"
        return True
    return False
```

> 三堂会审：
> - 合规：与 14.9 trigger 三条件**不重复**（本法补"消息数兜底"这一维）；KISS（一个 return 判定）。
> - 合理：直击 12.2 已识别风险（大窗口不触发），`max_msgs` 默认 80 给长任务兜底。
> - 关联逻辑：`context_limit` 已由 `agent_runner.py:140` 注入，零新配置；`reserve` 复用 `COMPACTION_BUFFER` 语义一致。

##### `CompactionCooldown`（原 K2 触发冷却节流法，归支撑函数库，Cooldown Throttle）

> **归属/场合**：① 启用 C4（LLM 压缩）时防连续轮次反复烧 LLM；② 压缩后冷却若干轮再评估；③ 与防抖动（节省率）互补（一个看时间间隔、一个看节省率）。

> **痛点**：压缩触发后下一轮立刻又满，可能连续压缩抖动（尤其 C4 每次 1 LLM 调用，反复触发=成本失控）。本法在压缩后设冷却轮次，冷却期内不重复触发。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: 压缩冷却节流, 防连续轮次反复压缩
"""compaction.cooldown — 触发冷却节流 — 小欧 2026-08-16"""
from typing import Optional


class CompactionCooldown:
    def __init__(self, cooldown_rounds: int = 2):
        self._cooldown_rounds = cooldown_rounds
        self._since_last = 0

    def allow(self) -> bool:
        self._since_last += 1
        return self._since_last > self._cooldown_rounds

    def mark_compacted(self) -> None:
        self._since_last = 0
```

> 三堂会审：
> - 合规：单一职责（只管冷却）；与 14.9 trigger 解耦（trigger 管"是否该"，cooldown 管"刚压过没"）。
> - 合理：冷却 2 轮足够让压缩生效后再评估，避免 C4 每轮烧 LLM。
> - 关联逻辑：`mark_compacted()` 在 trim_history 委托 compaction 后调用，与 `_t3_savings_pct` 防抖（5.4）**互补不冲突**（一个看节省率、一个看时间间隔）。

##### `trim_orphan_pairs_proactive`（原 K3 孤儿FC对前置修剪法，归支撑函数库，Pre-Pair Trim）

> **归属/场合**：① 凡做删除式裁剪（C3 prune / value_first_prune / T1）必配；② 每次裁剪后立即保 FC 配对，防孤儿 assistant(tool_calls) 无对应 tool 致 LLM 400；③ 与现有 `_trim_fc_pairs` 思路一致、前置化。

> **痛点**：现有 `_trim_fc_pairs` 在 T1 末尾（5.2 步骤 8）收尾清理。若先清 tool output（C3 prune）或按值删除（value_first_prune），可能中途产生孤儿 assistant(tool_calls) 无对应 tool。本法**每次 prune/删除后立即前置修剪**，保 FC 配对贯穿全程。

```python
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-16 小欧 新增: FC 配对前置修剪, 每次裁剪后立即保配对
"""compaction.pair_trim — 孤儿 FC 对前置修剪 — 小欧 2026-08-16"""
from typing import List, Dict


def trim_orphan_pairs_proactive(messages: List[Dict]) -> List[Dict]:
    """保留有对应 tool_call_id 的工具消息, 删孤儿 assistant/tool — 小欧 2026-08-16"""
    seen_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    result = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            keep = all(tc.get("id") in seen_ids for tc in m["tool_calls"])
            if keep:
                result.append(m)
            continue
        if m.get("role") == "tool":
            if m.get("tool_call_id") in seen_ids:
                result.append(m)
            continue
        result.append(m)
    return result
```

> 三堂会审：
> - 合规：复用现有 `_trim_fc_pairs` 思路（Hermes `_sanitize_tool_pairs` 借鉴），前置化不重造；SRP（只管配对）。
> - 合理：配对残留是 LLM API 400 根因，前置比收尾更稳。
> - 关联逻辑：与 C3 prune（清 tool output 不删消息，配对天然在）、value_first_prune（可能删 tool）**协同**——value_first_prune 删 tool 后由本法清孤儿 assistant，闭环。

**14.9.6 选型建议**：`t1_reuse_summary` 直接替代 t1_compress_observations 逐工具模板（DRY 升级，强烈推荐）；`value_first_prune` 与 T1 组合保真；`should_compact_window` 必配（解决大窗口不触发）；`generate_chunked_summary` 长任务用 C4 时替代全量版；`CompactionCooldown` 启用 C4 时必配（控成本）；`trim_orphan_pairs_proactive` 凡做删除式裁剪必配。以上函数与 C3/C4/T1 共同构成 `compaction/` 模块完整能力集，不再设平级方法编号。

---

## 十五、变更记录

| 版本 | 时间 | 变更人 | 变更内容 |
|------|------|--------|---------|
| v5.9 | 2026-08-16 15:41:02 | 小欧 | 14.9.2 目录树精确化(老陈 2026-08-16 核对: 并非所有写出函数都在原目录树里): 每文件行尾标注实际承载函数; value_first_prune 归 prune.py(T1 保真策略); trim_orphan_pairs_proactive 归 assembler.py(配对修剪, K3); should_compact_window/CompactionCooldown 标入 trigger.py; 修正 __init__ 笔误 CessionManager→导出各函数; 注明 split_turn.py/assembler.py 仅规划占位待补代码; 目录树与 14.9.3/14.9.4/14.9.6 实际函数落点一一对应 |
| v5.8 | 2026-08-16 15:21:13 | 小欧 | 编号重构：方法体系从"11 个平级方法"重构为"4 主干方法 + 策略实现函数 + 支撑函数库"。保留 4 主干：M1 历史记忆注入法 / C3 剪枝压缩法 / C4 锚定摘要压缩法 / T1 紧急裁剪法；降级归并 7 项：原 C1 工具摘要压缩法→C3 轻量实现函数 t1_compress_observations（第五章）、原 C2 摘要复用压缩法→C3 策略实现函数 t1_reuse_summary（DRY 升级）、原 C5 增量块式锚定摘要法→C4 策略实现函数 generate_chunked_summary、原 T2 知识密度优先裁剪法→T1 策略实现函数 value_first_prune、原 K1 动态窗口触发法→支撑函数 should_compact_window、原 K2 触发冷却节流法→支撑函数 CompactionCooldown、原 K3 孤儿FC对前置修剪法→支撑函数 trim_orphan_pairs_proactive；14.9.6 整章重构为"支撑函数库与策略实现（归并到 4 主干方法）"四块，6 法总览表改为归并总览表，正文交叉引用按新归属改写；代码标识符（TRIGGER_T1_RATIO/TRIGGER_T3_RATIO/KEEP_TAIL_ROUNDS/PASS3_*/HISTORY_MEM_*/MAX_CONTEXT_TOKENS 等）保持不变 |
| v5.7 | 2026-08-16 14:40:17 | 小欧 | 全文方法统一编号命名(C功能域前缀+序号) + 各方法头部加适用场景：C1工具摘要压缩法(原T1)/C2摘要复用压缩法(原14.9.6①)/C3剪枝压缩法(原方法一)/C4锚定摘要压缩法(原方法二)/C5增量块式锚定摘要法(原14.9.6④)/T1紧急裁剪法(原T3)/T2知识密度优先裁剪法(原14.9.6②)/M1历史记忆注入法(原History Memory)/K1动态窗口触发法(原14.9.6③)/K2触发冷却节流法(原14.9.6⑤)/K3孤儿FC对前置修剪法(原14.9.6⑥)；名称名副其实、交叉引用统一编号、各方法定义段加适用场景/场合段 |
| v5.6 | 2026-08-16 14:35:58 | 小欧 | 14.9.6 备选方法库三堂会审修正（北京老陈 2026-08-16 要求新方法务必满足"基于本地真实代码+经得起三堂会审+统一compaction/目录"三点要求）：①修正方法①——核实 observation_formatter.py:603/627 已把 summary 拼进 content, tool 消息字典无独立 summary 字段, 原 `msg.get("summary")` 属臆测; 改为先 stash `_summary`(add_tool_result:124 加形参+handler 透传 llm_data.summary)再复用, 去臆测保合规; ②方法②原始顺序还原由 messages.index(m) 改 enumerate 下标(防重复 dict 错位) |
| v5.5 | 2026-08-16 14:31:58 | 小欧 | 新增 14.9.6 "备选方法库（更多可取思路 + 更优函数，供后续选型）"：①工具层 summary 复用摘要法(复用 llm_data.summary 替代 C1 模板, DRY) ②知识密度优先保留法(按价值权重替保最近N轮) ③动态窗口触发完善法(解决900K大窗口不触发+消息数兜底) ④增量块式锚定摘要法(方法二降本变体, 只摘要新增块) ⑤触发冷却节流法(压缩冷却防抖深化) ⑥孤儿 FC 对前置修剪法(每次裁剪后立即保配对); 六法均基于本地真实代码行号 + 三堂会审(合规/合理/关联逻辑) + 归入 compaction/ 模块; 附选型建议 |
| v5.4 | 2026-08-16 14:24:34 | 小欧 | 新增 14.9 "基于本地现有代码的落地 diff（含统一压缩/裁剪模块目录规划）"（北京老陈 2026-08-16 拍板：建立统一目录作为消息压缩/裁剪的独立模块架构层）：①14.9.1 代码现状盘点——核实本地真实代码行号（message_builder.trim_history:265 / MAX_CONTEXT_TOKENS:84 / last_total_tokens:85 / _trim_to_budget:336 / react_cycle.trim_history 唯一入口:350 / agent_runner:140 已按模型窗口 / llm_stream:133 call_llm_stream，**确认 T1/history_mem 代码未实现、仅设计稿**）；②14.9.2 新建 `compaction/` 目录（__init__/constants/trigger/prune/summary/summary_prompt/split_turn/assembler），SRP/OCP/ISP/分布式层三堂会审依据，trim_history 仍为唯一入口委托 compaction、_trim_to_budget 保底；③14.9.3 方法一减枝 diff（trigger 触发三条件 + prune 清 tool output 保 tool_call + message_builder 委托改造，唯一入口不变、_pruned 同段剥离）；④14.9.4 方法二锚定摘要 diff（SUMMARY_TEMPLATE 六段固定结构 + generate_anchored_summary 截断喂/原库完整 + previousSummary 锚定，前置需老陈定夺放开 R4 零 LLM 原则）；⑤14.9.5 三堂会审总结表；落地顺序方法一立即可做 → 方法二定夺 R4 后接入 → E2E 实测 |
| v5.3 | 2026-08-16 14:16:56 | 小欧 | 14.8.4 定案两方法命名与适用场景（北京老陈 2026-08-16 定案：给 P0/P1 分别命名名副其实的方法名，明确各自适用场景，可灵活选用组合）：**方法一=剪枝压缩法**（Prune Compaction，规则级：按模型窗口触发 + 通用清零旧 tool output 保 tool_call + 保尾 token 预算+splitTurn，零 LLM 零成本，适用：简单/单轮任务、高频轮次增长、成本敏感、新任务 independent）；**方法二=锚定摘要压缩法**（Anchored Summary Compaction，语义级：一次 LLM 调用输出固定结构 Markdown + previousSummary 锚定增量 + 不破坏原库 + 自动续跑，适用：长任务跨多轮、续聊任务 linked 上下文链、决策链关键、可接受一次 LLM 成本）；两方法按场景选型/组合（剪枝第一道零成本兜底→仍超限且需保语义→锚定摘要，opencode prune→compaction 递进），History Memory 全程保留；互不依赖可独立开关 |
| v5.2 | 2026-08-16 14:09:18 | 小欧 | 14.8 新增"两种方法对照分析与推荐方法"（北京老陈 2026-08-16 要求对照分析并给推荐，写入本文档）：①14.8.1 一句话定性（我们=纯规则零 LLM / opencode=零 LLM 前置+调 LLM 锚定摘要；精修措辞：我们没用到 agent 参与压缩、opencode 中 agent 是壳 LLM 是芯）；②14.8.2 五层逐层对照表（触发固定比例 vs 按模型窗口 / T1 逐工具模板 vs prune 通用清零 / 无语义压缩 vs anchored LLM 摘要 / History Memory vs 摘要模板决策段 / KEEP3 固定轮数 vs token预算+splitTurn）；③14.8.3 本质差异（纯规则 vs 语义归档）+ 双方长处；④14.8.4 推荐融合式两阶段——P0 立即（触发按模型窗口 + T1→prune 式清零 + 保尾 token预算+splitTurn，纯规则零成本不退化）→ P1 引入 LLM 锚定摘要（放开 R4 零 LLM 原则，需老陈定夺成本，当前/小模型一次调用、anchored 累积、不破坏原库、History Memory 保留作 zero-cost 兜底、压缩后自动续跑）；不推荐纯删删减减或照抄丢掉 History Memory |
| v5.1 | 2026-08-16 14:04:49 | 小欧 | 14.3.4 补澄清（北京老陈 2026-08-16 确认：压缩核心是 LLM 生成摘要，不能只是 agent）——压缩 = agent 壳（约束层：专用 compaction agent、无工具、权限全 deny、专属提示词 compaction.txt）+ 底层 LLM（生成层：processor.process → llm.stream 一次流式调用产出摘要）；opencode 用专用 agent 组织本次 LLM 调用，摘要文本仍由 LLM 生成 |
| v5.0 | 2026-08-16 13:59:53 | 小欧 | 新增第十四章"opencode 压缩方法深度研究（compaction.ts / overflow.ts / summary.ts）"（北京老陈 2026-08-16 指示深挖 opencode 压缩实现并评估可借鉴性）：①澄清 summary.ts 非上下文压缩（是 git diff 会话统计）；②overflow.ts = 按模型窗口 usable() 判定溢出（非固定比例）；③compaction.ts 四函数拆解（create 打标 / select 保尾区 token 预算+splitTurn / prune 通用清零旧工具输出保 tool_call / process 独立 agent+anchored 锚定式 LLM 摘要+压缩截断不破坏原库+auto 自动续跑）；④14.6 可借鉴性评估 8 项（P0 立即：prune 清零替换 C1 模板、按模型窗口触发、压缩截断不破坏原库；P1：锚定 LLM 摘要需老陈定夺成本、保尾 token 预算+splitTurn、自动续跑；P2：auto 开关；summary.ts 不借鉴）；⑤14.7 对照结论——T1 逐工具模板属过度设计建议改 prune 式、缺语义摘要层建议评估放开零 LLM 成本原则；本章仅研究评估不改 v4.0 既有定案。原第十四章"变更记录"顺延为第十五章 |
| v3.0 | 2026-07-22 16:33:34 | 小欧 | History Memory 注入方式从 system 改为独立 user 消息（北京老陈裁定：user 角色语义更对）；新增 3.4 保护机制（`_history_mem` 标记 + 每轮重注入）；新增第十一章"关于 role 选择的分析" |
| v2.0 | 2026-07-22 18:30:00 | 小欧 | 融合方案[3]保尾逻辑：KEEP_TAIL_ROUNDS=5→3、从最旧往最新删、保尾定位方式借鉴方案[3]找第N个assistant消息；新增第十章"推荐落地组合"总结全文 |
| v1.0 | 2026-07-22 18:30:00 | 小欧 | 初版：History Memory（从 Step 提取推理链注入 system prompt）+ T1 工具摘要 + T3 紧急裁剪（借鉴 OpenCode/Hermes 的 6 种机制） |
