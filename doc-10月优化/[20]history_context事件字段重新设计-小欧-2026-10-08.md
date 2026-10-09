# history_context 事件字段重新设计

**创建时间**: 2026-10-08 23:30:38
**编写人**: 小欧
**版本**: v3.0
**性质**: 设计方案（编辑型文档）
**所属主线**: compaction / 上下文可观测性
**设计人裁定**: 北京老陈（字段结构与场景语义）

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|---|---|---|---|
| v1.0 | 2026-10-08 23:30:38 | 小欧 | 首版：按北京老陈裁定的字段结构重写 history_context 事件契约。核心变更：①扁平 8 字段改为 `conv_context` / `inject_context` 双分组嵌套；②`compressed` 由 bool 改文字信息；③`summary` 收窄为只存压缩摘要；④新增 `content` 承载处理模式；⑤废弃 `compress_saved_pct` 与 `last_user_text`（死字段）|
| v2.0 | 2026-10-09 07:24:08 | 小欧 | 按 §3.1 + §3.1.1 全量对齐。核心变更：①新增 §3.1.1「首帧分工制」装配逻辑（首帧非 link → conv 实填/inject 全空；首帧 link → 反之；第 2 帧起 conv 实填/inject 保持首帧值）；②`compressed` 改为 `第[N]个link任务, <情况文字>` 固定格式；③`content` 三态改 `独立任务,无历史上下文注入` / `连续任务,注入历史上下文` / `第[N]轮的对话历史上下文信息`；④补 §3.1.1 八 UI 双标签（历史上下文读 inject_context、对话上下文读 conv_context）与 九 DB 落点；⑤§五后端重写为 18 小节（删 `build_context_overview`、新增 4 个装配 helper + 空组工厂 + 压缩率反解 + 链内序号取数）；⑥§六前端重写为 10 小节（拆双标签、去三层套娃）；⑦§四场景表、§3.3、§3.4、§八实施顺序、§九遗留问题同步对齐 |
| v3.0 | 2026-10-09 08:33:46 | 小欧 | 三堂会审 52 条全改 + KISS 收敛（21 处→13 处）。核心变更：①`_is_link_task` 判据改 `context_link_mode`（旧判据误判独立任务）；②删 `_parse_compress_pct`+`import re`+两空组工厂（快照直接算数字，编排内联）；③telemetry 收为一帧一函数 `_build_history_context_frame`；④初始化上移 `initialize_run_state`（删 `start_step:296` 重复清零）；⑤前端单卡双段（保 metricLine/占窗率链路）+ 压缩时间线事件（判据用 compressed 情况文字）；⑥`_compact_attempted`+`_start_summary` 每轮初始化；⑦后端逻辑副本 18 断言 + 单函数版 13 断言全过，前端 tsc 零类型错 |

---

## 一、设计目标与范围

### 1.1 目标

重构 `history_context` 事件的字段契约，**抛弃现有扁平字段结构**，改为分组嵌套结构。三个改造点：

| # | 改造 | 动机 |
|---|---|---|
| 1 | 字段**分组**（conv / inject 两个命名空间）| 现状 8 个平铺字段语义混杂：`message_count`（conv）与 `injected_message_count`（inject）名字相近易混，前端极易取错 |
| 2 | `compressed` 由 **bool → 文字** | 现状前端要自己把 `compress_saved_pct` 拼成"已压缩 X%"，文案散落前端；改为后端直接给成品文字 |
| 3 | `content` 独立承载**处理模式** | 现状 `content` 字段被塞进 `summary`（承担"摘要"与"状态文案"两职），语义重载 |

### 1.2 不在范围

| 不做 | 理由 |
|---|---|
| 不改 compaction 压缩算法本身 | 本次只改"怎么报告"，不改"怎么压" |
| 不改 `chat_task_steps` 表结构 | 与本事件无关 |
| 不动 conv 注入链路的执行流程 | 仅新增 `_compact_attempted` 尝试标记用于区分"未超窗"与"压缩失败"（见 §5.3 初始化与 §5.4 置位） |

---

## 二、现状与字段处置

### 2.1 主干时序：history_context 帧怎么发出来的

```
react_loop.run_react_cycle()
│
├─ L155  _start_step = await _assemble_start_step(agent, context)
│        │
│        └─ start_step.py  ── 此刻决定「有没有压缩、压成什么」
│             ├─ L296   agent._start_summary = ""            ← 清零
│             ├─        agent._needs_compact 判定（注入历史是否超窗）
│             ├─ L301   if _needs_compact:
│             │             _start_summary = await _compact_injected_history(agent)
│             │             └─内部 3 处把 _needs_compact 复位 False（所以事后读不到）
│             ├─        agent._injected_history_msgs = 未压缩时的原始注入历史
│             └─ L304   telemetry.set_injected_context({
│                          message_count, estimated_tokens, last_user_text
│                      })   ← 注入基线快照，固定不随后续裁剪变
│
├─ L158  message_builder.init_history(system_prompt, task)     ← conv 起盘
│
├─ L159  if _start_summary:                                     ← conv 装入内容二选一
│   L161 inject_history([{assistant:摘要}])               有压缩 → 只装摘要
│   L163 else inject_history(_injected_history_msgs)          无压缩 → 装原历史
│
├─ L164★ 首帧：telemetry.build_history_context_step(step=0)
│   L166      → _publish(_hc.to_dict())                        ← SSE 推第1 帧
│
└─ L170  emit start 帧 → _publish                              ← start 在 history_context 之后
```

### 2.2 逐轮刷新（第 2 帧起）

```
react_step（每次 LLM 响应后，Phase 2 收尾）
│
├─ L480  build_stats_step() → emit → publish                    ← stats 帧
│
└─ L484★ _llm_n = agent.llm_call_count
        L485  if _trimmed_this_round  or  _llm_n % 5 == 0:      ← 只在这两种轮次发
        L486      build_history_context_step(step=_llm_n)
        L487      → emit → _emit_publish(to_dict())             ← SSE 推水位更新帧
```

### 2.3 帧的字段从哪来（现状：单一出口 `build_history_context_step`）

```
build_history_context_step(step)                      agent_telemetry.py:338
│
├─ L350  _ov = self.build_context_overview()          ← 唯一的字段组装处（扁平 8 键）
│        │
│        ├─ message_builder.conversation_history ──┐│        ├─ message_builder._estimate_tokens()     │
│        ├─ message_builder._trimmed_this_round   ├──→ {message_count, estimated_tokens,
│        │ │      truncated}
│        ├─ telemetry._injected_context ───────────┤   {injected_message_count,
│        │   (set_injected_context 写入的基线快照)   │    injected_estimated_tokens}
│        └─ agent._start_summary ──────────────────┘   compressed = bool(摘要非空)
│                                                      compress_saved_pct = (1-装入/注入)×100
│                                                      summary = 摘要 或 last_user_text
│
├─ L352  MetaStep(step, type="history_context",
│                  content=_ov["summary"], <8 个平铺字段>, severity="info")
│           ↓  _extra_fields() = dict(self._kwargs)   ← 嵌套也能原样透传
└─ 返回 MetaStep → 调用方 .to_dict() → publish → SSE
```

### 2.4 `build_context_overview()` 的两个消费点（这是问题的根源）

```
              ┌──────────────────────────────┐
              │ build_context_overview()   │现状：扁平整包              │      返回 8 个平铺键         │
              └───────┬──────────────┬───────┘
                      │              │
        ┌─────────────▼──────┐  ┌────▼─────────────────────┐
        │ 消费点1：SSE 帧     │  │ 消费点2：build_task_snapshot│
        │ L350 → MetaStep     │  │ L392 →落库               │
        │ 想要「嵌套分组」     │  │ L418-426 → 扁平定长 DB 列  │
        │ 前端要分组渲染       │  │ context_compressed  int0/1 │
        │                    │  │ context_compress_saved_pct │
        │                    │  │          float              │
        └────────────────────┘  └────────────────────────────┘
                      ▲形状需求互斥：一个出口喂两个形状，必然一边迁就```
```
现状是**两边都在将就**：SSE 帧喂平铺字段（前端自己拼 `conv_context` 那套语义），DB 列喂 `1 if compressed else 0`。

### 2.5 字段实际来源对照（现状 8 键）

| 帧字段 | 来源 | 备注 |
|---|---|---|
| `message_count` | `len(message_builder.conversation_history)` | conv 侧 |
| `estimated_tokens` | `MessageBuilder._estimate_tokens(conv)` | 粗估，非 LLM 实测 |
| `truncated` | `message_builder._trimmed_this_round` | **末轮瞬时标志**，早于末轮的裁剪会漏报 |
| `injected_message_count` | `_injected_context["message_count"]` | 注入侧基线 |
| `injected_estimated_tokens` | `_injected_context["estimated_tokens"]` | 注入侧基线 |
| `compressed` (bool) | `bool(agent._start_summary)` | 有摘要=压过 |
| `compress_saved_pct` | `(1 - 装入/注入) × 100` | 前端自己拼成「已压缩 X%」 |
| `summary` | 摘要 **或** `last_user_text` | 一字段两职 |
| `content` | `MetaStep(content=_ov["summary"])` | 与 `summary` 同源，重复 |

### 2.6 三个可实证的缺陷

1. **`summary` 一字段两职** —— 同一个表达式同时产出「压缩摘要」和「上一轮历史提问」（`last_user_text` 取的是 `previous_messages` 末条 user，实测任务 `00f3e93b9` 帧里显示的是前一任务 `5bd5fc403` 的提问原文）。
2. **压缩失败静默** —— `_compact_injected_history` 失败 `return ""`，只 `logger.warning`。因为 `compressed = bool(摘要)`，失败与「压根没超窗」在帧上完全同形，且 `_needs_compact` 事后恒 `False`，连判定依据都没了。
3. **`truncated` 漏报** —— 读的是末轮瞬时标志，中途裁剪后若末轮未裁，帧报 `false`。

---
## 三、新设计的 context-history字段设计及装配逻辑构

### 3.1 目标帧结构

```json[信息样例模式说明,具体填写说明以 3.1.1的说明为准]
{
  "timestamp": "2026-10-08T22:14:33",
  "step": 0,
  "conv_context": {
    "message_count": 116,
    "estimated_tokens": 122000,
    "truncated": false
  },
  "inject_context": {
    "injected_message_count": 104,
    "injected_estimated_tokens": 117261,
    "compressed": "本次注入历史信息压缩率= 34%",
    "summary": "<压缩摘要全文>"
  },
  "content": "注入有压缩"
}
```

### 3.1.1 装配逻辑（首帧分工制 · UI和落库情况）

> **编制**：小欧　**时间**：2026-10-08　**依据**：北京老陈口述裁定

#### 3.1.1.1 总原则

首帧按**任务性质分工**装配，两个分组**互斥填充实**：非 link 任务只报 conv 侧，link 任务只报 inject 侧。这样每个字段都在它成立的那个场景里有值，不存在"该空却非空"的噪声。

| 帧类型 | `content` | `conv_context`（3 字段）| `inject_context`（4 字段）|
|---|---|---|---|
| **首帧 · 非 link 任务** | 独立任务,无历史上下文注入 | **实填** | **全部置空** |
| **首帧 · link 任务** | 连续任务,注入历史上下文 | **全部置空** | **实填** |
| **第 2 帧及以后** | `第<N>轮的对话历史上下文信息` | **实填** | **不处理，保持首帧值不变** |

#### 3.1.1.2 情况 1：非 link 任务（无历史注入动作）

```json
{
  "content": "独立任务,无历史上下文注入",
  "conv_context": {
    "message_count": <实填>,
    "estimated_tokens": <实填>,
    "truncated": <实填>
  },
  "inject_context": {
    "injected_message_count": "",
    "injected_estimated_tokens": "",
    "compressed": "",
    "summary": ""
  }
}
```

| 字段 | 取值 |
|---|---|
| `content` | `独立任务,无历史上下文注入` |
| `conv_context.*` | 三个字段全部实填（`len(conversation_history)` / `_estimate_tokens(conv)` / `_trimmed_this_round`）|
| `inject_context.*` | 四个字段**全部置空字符串** |

#### 3.1.1.3 情况 2：link 任务（有历史注入动作）

```json
{
  "content": "连续任务,注入历史上下文",
  "conv_context": {
    "message_count": "",
    "estimated_tokens": "",
    "truncated": ""
  },
  "inject_context": {
    "injected_message_count": <实填>,
    "injected_estimated_tokens": <实填>,
    "summary": "<有压缩时的摘要文本，否则空>",
    "compressed": "第<N>个link任务, <四种情况之一>"
  }
}
```

| 字段 | 取值 |
|---|---|
| `content` | `连续任务,注入历史上下文` |
| `conv_context.*` | 三个字段**全部置空字符串** |
| `inject_context.injected_message_count` | 实填（`_injected_context["message_count"]`）|
| `inject_context.injected_estimated_tokens` | 实填（`_injected_context["estimated_tokens"]`）|
| `inject_context.summary` | **仅压缩成功时**填摘要文本；其余情况空字符串 |
| `inject_context.compressed` | `第<N>个link任务, ` + 下表四种情况之一 |

#### 3.1.1.4 `compressed` 四种情况（填写模型）

格式固定：`第[N]个link任务, <情况文字>`

| 情况 | `<情况文字>` | `summary` |
|---|---|---|
| 无历史上下文注入 | `无历史上下文注入` | `""` |
| 注入但未触发压缩（未超窗）| `""` | `""` |
| 压缩成功 | `本次注入历史信息压缩率= {pct}%` | 摘要文本 |
| 压缩失败 | `本次注入历史信息压缩失败` | `""` |

**示例**：

| 帧 | `compressed` 完整值 |
|---|---|
| 第 1 个 link 任务 | `第1个link任务, 无历史上下文注入` |
| 第 2 个 link 任务，未超窗 | `第2个link任务, ` |
| 第 3 个 link 任务，压缩成功 | `第3个link任务, 本次注入历史信息压缩率= 34%` |
| 第 4 个 link 任务，压缩失败 | `第4个link任务, 本次注入历史信息压缩失败` |

#### 3.1.1.5 填写注意

| # | 注意 |
|---|---|
| 1 | **第 1 个 link 任务**填 `第1个link任务, 无历史上下文注入` —— 链根任务自身无前序历史可注入 |
| 2 | **第 2 个及以后的 link 任务**全部有历史上下文注入，走后三种情况 |
| 3 | 序号 `N` 与"有无历史注入"是两个独立维度：序号靠链内位置，"无历史上下文注入"靠有无历史，两者不能互推 |
| 4 | 第 2 帧及以后 `inject_context` **一律不处理**，必须原样保持首帧的值，不得重算、不得清空 |

#### 3.1.1.6 第 2 帧及以后

```json
{
  "content": "第<N>轮的对话历史上下文信息",
  "conv_context": {
    "message_count": <实填>,
    "estimated_tokens": <实填>,
    "truncated": <实填>
  },
  "inject_context": "<保持首帧原值，一个字节都不动>"
}
```

| 字段 | 取值 |
|---|---|
| `content` | `第<N>轮的对话历史上下文信息` |
| `conv_context.*` | 三个字段全部实填（每轮真实水位）|
| `inject_context.*` | **不处理，保持不对** —— 严禁重算、严禁清空、严禁覆盖 |

| `N` 取值 | 来源 |
|---|---|
| 轮次序号 | `build_history_context_step(step=...)` 的 `step` 入参，即 `react_step.py:484` 的 `_llm_n = agent.llm_call_count` |

**示例**：`第5轮的对话历史上下文信息`、`第10轮的对话历史上下文信息`

#### 3.1.1.7 代码缺口（实施前必须解决）

| 缺口 | 现状 | 需要的动作 |
|---|---|---|
| **`N`（link 序号）无数据源** | 全仓无 `link_index` / `link_seq` / `chain_index` 类字段；`chat_tasks` 只有 `context_root_task_id`（`db_initializer.py:138`）、`context_link_mode` | 新增：按 `context_root_task_id` 聚合已有任务数 + 1 得 `N` |
| **link 模式判定入口** | `agent._start_meta["context_link_mode"]` / `["context_root_task_id"]`（`start_step.py:265-266`）已就位 | 直接读，无需新增 |

#### 3.1.1.8 前端 UI 显示逻辑

> 2026-10-09 小欧三堂会审修正：卡片保持**单个 `FloatingEntry`**（`TaskInfoBar:421` 单点调用、
> `ContextOverviewCard:138` 早退、`metric` 锚点均不动），卡片**内容内拆两段**各读一组。
> 严禁改成两个 `FloatingEntry` —— 那会破坏组件契约（致命 #49）。

| 任务类型 | 历史上下文段 | 对话上下文段 |
|---|---|---|
| **实时任务** | 显示（读 `inject_context`）| 显示（读 `conv_context`）|
| **历史任务** | L138 早退，只显行内 `metric`，卡片不渲染 | — |

| 段 | 对应分组 | 显示字段 |
|---|---|---|
| **历史上下文** | `inject_context` | `injected_message_count`、`injected_estimated_tokens`、`compressed`、`summary` |
| **对话上下文** | `conv_context` | `message_count`、`estimated_tokens`、`usedPct` 占窗率 |

**现状与目标的差距（代码实证）**

| 项 | 现状 | 证据 | 差距 |
|---|---|---|---|
| 段数量 | 只有 **1 个**「历史上下文」标题 | `ContextOverviewCard.tsx:146` `ariaLabel="历史上下文"`、`:163` 卡片标题 | **卡片内新增「对话上下文」段** |
| 分组渲染 | `metricLine` 混装 conv 侧 + inject 侧 | `:165` `{metricLine ?? ctx.text}` 一行出全部 | **拆 `injectPart` / `convPart`，两段各读一组** |
| 保留项 | `formatTokenK`、`usedPct` 占窗率、`ctx.tooltip` 警示行、行内 `metric` | `:80-84`、`:112-121`、`:194-196`、`:127-136` | **一律保留，丢任何一项即功能退化（致命 #48）** |

**两段的数据源严格隔离**：历史上下文段只读 `inject_context`，对话上下文段只读 `conv_context`，严禁交叉读（交叉读即 §2.6 缺陷1 复发）。

#### 3.1.1.9 context-history 信息 DB 保持逻辑

**落点一：`monitoring.db` 的 `task_metrics`（汇总，只剩末帧）**

| 项 | 实证 |
|---|---|
| 建表 | `storage.py:38-56`，7 个 context 列在 `:51-54` |
| 写入 | `persist_task_metrics()` 用 `INSERT OR REPLACE`（`storage.py:128`），`task_id TEXT UNIQUE`（`:40`）|
| 结论 | 一任务一行、每次全量覆盖 → **只留最后一帧，首帧没存** |
| 时机 | `build_task_snapshot()`，任务 finalize 时调一次 |

**落点二：`chat_history.db` 的 `chat_task_steps.step_json`（逐帧，全存）**

| 项 | 实证 |
|---|---|
| 路由 | `agent_runner._route_step_to_db()`（`agent_runner.py:480`），排除集只有 `SSE_ONLY_TYPES` 9 类（`agent_telemetry.py:82-85`），**不含 `history_context`** |
| 归类 | `PERSISTED_NON_BIZ_TYPES`（`agent_telemetry.py:86-88`）=落库需回放、不计业务步 |
| 结论 | 首帧 `step=0` 与之后每帧**逐帧落库** |

**结论**：context 信息已全量落库，**不需要新增任何表或列**。历史任务要显示「历史上下文」时，详情接口直给首帧（`get_task_detail` 附带 `history_context_first`，`storage.get_history_context_first()` 只取 `step=0` 那帧）。

> 2026-10-10 小欧[20]实施注：原方案"前端从 `chat_task_steps` 取 `step=0` 帧"改为"后端详情接口直给" ——
> 实证发现 `TaskInfoBar` 传的是实时 steps 数组（历史任务时为空），前端根本拿不到历史 steps；
> 跨组件传历史 steps 改动大，不如详情接口多带一个字段（一处改，后端为主）。

### 3.2 两个分组职责

| 分组 | 语义 | 字段 |
|---|---|---|
| `conv_context` | **conv 侧实况** = 本轮实际装入 LLM 的上下文 | `message_count`（conv 全量条数，含本轮 system/提问/工具调用）、`estimated_tokens`（估算）、`truncated`（本轮是否发生裁剪）|
| `inject_context` | **注入侧** = 跨任务注入的历史及其压缩处理 | `injected_message_count`、`injected_estimated_tokens`、`compressed`（**文字**）、`summary`（**只**存压缩摘要）|

### 3.3 `content` 的职责

> 北京老陈裁定：**`content` 就是 context，各种状态信息都可以记录到这里。**

`content` 承载帧的种类标识：首帧按任务性质（独立 / 连续），第 2 帧起带轮次号。

| 场景 | `content` |
|---|---|
| 首帧 · 非 link 任务 | `独立任务,无历史上下文注入` |
| 首帧 · link 任务 | `连续任务,注入历史上下文` |
| 第 2 帧及以后 | `第<N>轮的对话历史上下文信息` |

禁再出现 `无历史注入` / `注入无压缩` / `注入有压缩` 等旧值。

### 3.4 `compressed` 的职责

格式固定：`第[N]个link任务, <情况文字>`（§3.1.1 四）。承载压缩的一切信息。

| 情况 | `<情况文字>` | `summary` |
|---|---|---|
| 无历史上下文注入 | `无历史上下文注入` | `""` |
| 注入但未触发压缩（未超窗）| `""` | `""` |
| 压缩成功 | `本次注入历史信息压缩率= {pct}%` | 摘要文本 |
| 压缩失败 | `本次注入历史信息压缩失败` | `""` |

`""` 只出现在「注入但未触发压缩」这一种；其余三种都有确定文字。前端直接显示，不拼装。

### 3.5 `summary` 的硬约束

> 北京老陈裁定：**`summary` 只能存压缩摘要，不能放其他任何信息。**

非压缩场景该字段必须是**空字符串**，不得填状态文案、不得填历史提问。

### 3.6 压缩率算式（沿用现状，不改）

`agent_telemetry.py:323-325` 现状算式保留：

```
pct = max(0.0, round((1 - 装入tokens / 注入tokens) × 100, 1))
```

| 项 | 说明 |
|---|---|
| 分母 | `injected_estimated_tokens`（注入的原始历史，tool 输出完整）|
| 分子 | `estimated_tokens`（conv 侧实际装入量）|
| 夹逼 | `max(0.0, ...)`，负数防御 |
| 精度 | 1 位小数 |

该口径天然包含"摘要前清零降本"与"摘要信息损失"两部分贡献（因 conv 侧只装摘要不装原历史，见 `react_loop.py:160-161`），故不再单独上报降本数字。

---

## 四、场景完整映射

| 场景 | `content` | `conv_context` | `inject_context.compressed` | `inject_context.summary` |
|---|---|---|---|---|
| 首帧 · 独立任务 | `独立任务,无历史上下文注入` | **实填** | **全空** | `""` |
| 首帧 · link 任务 · 第1个（无历史可注入）| `连续任务,注入历史上下文` | **全空** | `第1个link任务, 无历史上下文注入` | `""` |
| 首帧 · link 任务 · 未超窗 | `连续任务,注入历史上下文` | **全空** | `第N个link任务, ` | `""` |
| 首帧 · link 任务 · 压缩成功 | `连续任务,注入历史上下文` | **全空** | `第N个link任务, 本次注入历史信息压缩率= 34%` | 摘要全文 |
| 首帧 · link 任务 · 压缩失败 | `连续任务,注入历史上下文` | **全空** | `第N个link任务, 本次注入历史信息压缩失败` | `""` |
| 第 2 帧及以后 | `第<N>轮的对话历史上下文信息` | **实填** | **保持首帧值** | **保持首帧值** |

**首帧为什么两组互斥**：独立任务没有注入动作，报注入侧是噪声；link 任务首帧报的是"注入了什么"，conv 侧水位要到第 2 帧起才逐帧刷新。故一组实填、一组留空（§3.1.1 一）。

**压缩失败怎么区分**：靠 `_compact_attempted`（§5.4 改动 2）判定，`compressed` 文字直接给失败原因；`content` 不参与区分。

**压缩失败的现状问题**：`_compact_injected_history`（`start_step.py:226/233`）失败或取消时 `return ""`，仅 `logger.warning`，用户侧完全无感知。本设计通过 `compressed` 文字如实上报。

---

## 五、后端代码改动（一个代码文件一小节 · 每处代码一个 unified diff）

### 5.0 改动总览（5 个代码文件 · 14 处）

| 代码文件 | 改动处数 | 改动点 | 对应 §3.1 要求 |
|---|---|---|---|
| `backend/app/services/agent/initialize_run_state.py` | 1 处 | ① `_start_summary` / `_compact_attempted` 每轮初始化 | 初始化（替代 `start_step.py:296` 重复清零）|
| `backend/app/services/agent/start_step.py` | 3 处 | ② 删 L296 重复清零 ③ `_compact_attempted = True` 压缩分支内置位 ④ 删 `last_user_text` 计算 | §5.15 失败判据；§2.6缺陷2 |
| `backend/app/services/chat/storage.py` | 2 处 | ⑤ 新增 `count_chain_siblings()` ⑥ `get_task_detail` 附带首帧 + `get_history_context_first()` | §3.1.1.4 前缀数据源；历史任务回显 |
| `backend/app/services/chat/stream_orchestrator.py` | 2 处 | ⑥ 取 `_chain_sibling_count` ⑦ `_start_meta` 注入 `context_link_index` | §3.1.1.4 序号 |
| `backend/app/monitoring/agent_telemetry.py` | 9 处 | ⑧ `_inject_frame` 快照槽 ⑨ `set_injected_context()` 删 `last_user_text` ⑩ **删 `build_context_overview()`** ⑪ `build_history_context_step()` 改编排（判据与空组内联） ⑫ `_build_frame_content()` ⑬ `_build_conv_frame()` ⑭ `_build_inject_frame(meta)` ⑮ `build_task_snapshot()` 删 `_overview` 调用并自取数字 ⑯ `build_task_snapshot()` 落库 7 列改自取 | §3.1.1 首帧分工制；§3.3；§3.5；§2.4；§九 零迁移 |

**落地顺序**：`initialize_run_state.py` → `start_step.py`（无依赖）→ `storage.py` → `stream_orchestrator.py` → `agent_telemetry.py` → §六 前端。

---

### 5.1 `storage.py`（2 处）

**文件**：`backend/app/services/chat/storage.py`

**改动 1/1** — 新增链内序号查询（新增于 `query_chain_accumulation` 之前，L534）

```diff
--- a/backend/app/services/chat/storage.py
+++ b/backend/app/services/chat/storage.py
@@ -531,6 +531,20 @@
 
 
+def count_chain_siblings(conn: Connection, *, context_root_task_id: str, current_task_id: str) -> int:
+    """统计同链内除当前任务外的任务数 —— link 序号 N 的数据源(北京老陈 2026-10-08 裁定)
+
+    2026-10-08 小欧: 新增。history_context 首帧 compressed 需要"第N个link任务"前缀,
+      而全仓无 link 序号字段(§3.1.1 七 代码缺口)。N = 本函数返回值 + 1。
+    口径与 query_chain_accumulation(storage.py:534) 同源: 按 context_root_task_id 归链,
+      排除当前任务(独立任务 context_root_task_id=自身, 故结果恒 0 → N=1)。
+    """
+    return conn.execute(
+        "SELECT COUNT(*) FROM chat_tasks WHERE context_root_task_id = ? AND task_id != ?",
+        (context_root_task_id, current_task_id),
+    ).fetchone()[0]
+
+
 def query_chain_accumulation(conn: Connection, *, context_root_task_id: str, current_task_id: str) -> dict:
```


**改动 2/2** — `get_task_detail` 附带首帧 + 新增 `get_history_context_first()`（L916-935）

```diff
--- a/backend/app/services/chat/storage.py
+++ b/backend/app/services/chat/storage.py
@@ -916,6 +916,22 @@
     _r["model"] = _sm.model if _sm else None
     _r["provider"] = _sm.provider if _sm else None
+    # 2026-10-10 小欧[20]: 历史任务回显历史上下文 —— 首帧定稿后不变, 取 step=0 那帧即可
+    _r["history_context_first"] = get_history_context_first(conn, task_id)
     return _r


+def get_history_context_first(conn: Connection, task_id: str) -> Optional[dict]:
+    """取首帧 history_context 的 content/inject_context(历史任务回显用) — 小欧 2026-10-10

+    2026-10-10 小欧[20]: inject 首帧定稿后不变, 故只取 step=0 那帧, 不扫全表;
+      老任务帧是扁平结构(无 inject_context), 原样返回, 前端如实显示, 不做迁移。
+    """
+    rows = conn.execute(
+        "SELECT step_json FROM chat_task_steps WHERE task_id=?", (task_id,)).fetchall()
+    for r in rows:
+        d = parse_json(r["step_json"], label="step_json")
+        if isinstance(d, dict) and d.get("type") == "history_context" and d.get("step") == 0:
+            return {"content": d.get("content", ""),
+                    "inject_context": d.get("inject_context")}
+    return None
```
---

### 5.2 `stream_orchestrator.py`（2 处）

**文件**：`backend/app/services/chat/stream_orchestrator.py`

**改动 1/2** — 取链内序号（L616 之后、`_start_meta` 之前）

```diff
--- a/backend/app/services/chat/stream_orchestrator.py
+++ b/backend/app/services/chat/stream_orchestrator.py
@@ -616,6 +616,9 @@
         )
+        # 2026-10-08 北京老陈裁定: 取链内序号(第几个 link 任务)供 _start_meta 注入(§5.2 改动 2)。
+        #   口径与 L502 get_previous_task_chain 同源: 独立任务 _context_root_task_id=自身, 故结果恒 0 → N=1。
+        #   用闭包不用 partial —— 与 L494/L502 同款形态(DRY); partial 需新增 import, YAGNI 不做
+        _chain_sibling_count = await db.atxn(
+            "chat", lambda conn: count_chain_siblings(
+                conn, context_root_task_id=_context_root_task_id, current_task_id=task_id))
         # ── 编排⑧注入 start 运行元数据(_start_meta, start_step 装配用) ———————— 小健 2026-08-17
```

**改动 2/2** — `_start_meta` 注入 link 序号（L626-630）

```diff
--- a/backend/app/services/chat/stream_orchestrator.py
+++ b/backend/app/services/chat/stream_orchestrator.py
@@ -626,6 +626,7 @@
             "context_link_mode": _context_link_mode,
             "context_root_task_id": _context_root_task_id,
             "warning": _model_warning,
+            # 2026-10-08 北京老陈裁定: link 序号 N(第几个 link 任务), telemetry 直接读不算(单一写点)
+            "context_link_index": _chain_sibling_count + 1,
         }
```

---

### 5.3 `initialize_run_state.py`（1 处）

**文件**：`backend/app/services/agent/initialize_run_state.py`

**改动 1/1** — 每轮重置区初始化 `_start_summary` / `_compact_attempted`（L65-66 之后）

```diff
--- a/backend/app/services/agent/initialize_run_state.py
+++ b/backend/app/services/agent/initialize_run_state.py
@@ -65,3 +65,7 @@
     agent._last_error = None  # 2026-08-18 - 小欧 - error全仅SSE: 每轮重置, step_emitter.emit统一出口记录, 守卫读此填充final
     agent._usage_events = []  # 2026-08-18 - 小欧 - usage剔step_json: 每轮重置, react_cycle usage emit时append, agent_runner终态insert_token读
+    # 2026-10-09 北京老陈裁定: 摘要与压缩尝试标记在此统一初始化 ——
+    #   原 start_step.py:296 首行清零不是初始化, 296 之前抛异常即残留上次任务值; 此处是每轮入口, 一处管全部(DRY)
+    agent._start_summary = ""
+    agent._compact_attempted = False
```

---

### 5.4 `start_step.py`（3 处）

**文件**：`backend/app/services/agent/start_step.py`

**改动 1/3** — 删 L296 首行清零（初始化已上移 §5.3，此处重复）

```diff
--- a/backend/app/services/agent/start_step.py
+++ b/backend/app/services/agent/start_step.py
@@ -296,2 +296,0 @@
-    agent._start_summary = ""    # 首行清零, 防后续步骤抛异常时残留上次任务的值
```

**改动 2/3** — `_compact_attempted = True` 压缩分支内置位（L301-303）

```diff
--- a/backend/app/services/agent/start_step.py
+++ b/backend/app/services/agent/start_step.py
@@ -301,6 +301,8 @@
     # ③ 锚定摘要生成(超窗时; 结果挂 agent._start_summary 供调用方装配)
     if getattr(agent, "_needs_compact", False):
+        # 2026-10-08 北京老陈裁定: 语义=确实调用了摘要生成(非"判定超窗"), 故置在执行分支内
+        agent._compact_attempted = True
         agent._start_summary = await _compact_injected_history(agent)
```

**改动 3/3** — 删 `last_user_text` 计算（L304-318）

```diff
--- a/backend/app/services/agent/start_step.py
+++ b/backend/app/services/agent/start_step.py
@@ -304,18 +304,12 @@
     # 11.3-A 跨任务注入基线快照（独立模块 TaskTelemetry 存储，固定不漂移）— 小欧 2026-08-20
     _tele = getattr(agent, "telemetry", None)
     if _tele is not None:
         _prev = context.get("previous_messages") if isinstance(context, dict) else None
         _prev = _prev or []
         from app.services.agent.message_builder import MessageBuilder
+        # 2026-10-08 北京老陈裁定: 删 last_user_text(死字段, 串味实证见 §2.6)
         _tele.set_injected_context({
             "message_count": len(_prev),
             "estimated_tokens": MessageBuilder._estimate_tokens(_prev),
-            # 2026-10-08 小欧 传最近一条历史提问: telemetry 原从 conv 末条取, 首帧时那正是本轮提问,
-            #   标签叫"最近"等于回显用户自己的话。改由注入源取, 语义才成立。
-            "last_user_text": next(
-                (str(m.get("content") or "") for m in reversed(_prev)
-                 if m.get("role") == "user" and (m.get("content") or "").strip()), ""),
         })
```

---

### 5.5 `agent_telemetry.py`（6 处）

**文件**：`backend/app/monitoring/agent_telemetry.py`

**改动 1/6** — `__init__` 新增 `_inject_frame` 快照槽（L141 之后）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -141,1 +141,4 @@
         self._injected_context: Optional[Dict[str, Any]] = None  # 跨任务注入基线（固定快照）
+        # 2026-10-08 北京老陈裁定: 首帧 inject_context 定稿后存此槽, 第2帧及以后原样复用
+        #   (§3.1.1.6: 第2帧起 inject_context 保持首帧值, 严禁重算/清空/覆盖)
+        self._inject_frame: Optional[Dict[str, Any]] = None
```

**改动 2/6** — `set_injected_context()` 删 `last_user_text`（L150-160）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -150,13 +150,8 @@
     def set_injected_context(self, snapshot: Dict[str, Any]) -> None:
-        """跨任务注入上下文基线快照（start_step 注入后一次性写入，固定不随裁剪变）
+        """跨任务注入上下文基线快照(start_step 注入后一次性写入, 固定不随裁剪变)

-        2026-10-08 小欧 增 last_user_text: 原 summary 取 conv 最后一条 user/assistant, 首帧时那正是
-        用户刚发的本轮提问, 标签却叫"最近" → 用户看到自己的提问被回显, 属误导。改由注入源提供。
+        2026-10-08 北京老陈裁定: 删 last_user_text(死字段, 串味实证见 §2.6)
         """
         self._injected_context = {
             "message_count": int(snapshot.get("message_count", 0) or 0),
             "estimated_tokens": int(snapshot.get("estimated_tokens", 0) or 0),
-            "last_user_text": str(snapshot.get("last_user_text", "") or ""),
         }
```

**改动 3/6** — **删 `build_context_overview()`**（L302-336，整函数删除）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -302,36 +302,0 @@
-    def build_context_overview(self) -> Dict[str, Any]:
-        """产出 history_context 帧的数据字典(11.3-A) — 小欧 2026-10-08 重写压缩语义
-
-        ①删 injected_ratio(注入量/装入量): >1 才代表压缩生效但标签叫"压缩比"方向相反, 且未压缩时
-          因装入含 system+本轮提问而不等于 1.0。改 compressed + compress_saved_pct(详见文件头编辑历史)。
-        ②summary 按场景给真内容: 压缩给真正注入 conv 的那段摘要, 未压缩给注入源最后一条 user。
-        """
-        from app.services.agent.message_builder import MessageBuilder
-        _mb = self.agent.message_builder
-        _history = _mb.conversation_history
-        _message_count = len(_history)
-        _estimated = MessageBuilder._estimate_tokens(_history)
-        _truncated = bool(getattr(_mb, "_trimmed_this_round", False))
-        _inj = self._injected_context or {}
-        _inj_tokens = int(_inj.get("estimated_tokens", 0) or 0)
-        # 摘要取一次复用(DRY): 是否压缩与摘要正文同源, 不重复读 agent 属性
-        _start_summary = str(getattr(self.agent, "_start_summary", "") or "").strip()
-        _compressed = bool(_start_summary)
-        # 省了多少%: 未压缩显式 0, 不让 system+本轮提问的固定开销冒充"压缩收益"。
-        #   口径近似: 分母=注入的原始历史, 分子=装入全部消息(含摘要+system+本轮提问), 实测占比 <1%。
-        #   夹逼 ≥0: 摘要仅在原文 > 窗口一半(实测 121868 tok)时生成, 负数实际不可达, 仍夹逼为防御。
-        _saved_pct = 0.0
-        if _compressed and _inj_tokens > 0:
-            _saved_pct = max(0.0, round((1 - _estimated / _inj_tokens) * 100, 1))
-        # summary 按场景给真内容(北京老陈 2026-10-08 裁定 B: 卡片全展开不折叠, 故须给全文)
-        return {
-            "message_count": _message_count,
-            "estimated_tokens": _estimated,
-            "truncated": _truncated,
-            "injected_message_count": int(_inj.get("message_count", 0) or 0),
-            "injected_estimated_tokens": _inj_tokens,
-            "compressed": _compressed,
-            "compress_saved_pct": _saved_pct,
-            "summary": _start_summary if _compressed else str(_inj.get("last_user_text", "") or ""),
-        }
-
```

**改动 4/6** — `build_history_context_step()` 只编排不组装（L338-360）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -338,20 +338,19 @@
     def build_history_context_step(self, step: int = 0):
         """构造 history_context MetaStep(单一出口, react_loop 首帧与 react_step 逐轮共用) — 北京老陈 2026-10-07
 
         适用场景: ① react_loop 装配完 conv 后、emit start 之前发首帧(压缩与不压缩都发);
                   ② react_step 裁剪轮/每5轮发水位更新。
         使用方法: 取本方法返回值交给 agent._step_emitter.emit(...).to_dict() 再 publish。
         输出: MetaStep(type="history_context"); telemetry 未挂载时返回 None(调用方跳过)。
+
+        2026-10-08 北京老陈裁定: 首帧分工制(§3.1.1) —— 两个分组互斥填充实;
+          第2帧及以后 conv侧实填、inject 侧原样复用首帧槽。
+        2026-10-09 小欧: 本函数只编排(取数+调帧函数+emit), 组装全在 _build_history_context_frame ——
+          一个文件内不拆四个 helper 传来传去(KISS-DIRECT: 一帧一函数)。
         """
         _emitter = getattr(self.agent, "_step_emitter", None)
         if _emitter is None:
             return None
         from app.services.agent.steps import MetaStep
-        _ov = self.build_context_overview()
+        # 2026-10-09 小欧: _start_meta 只读一次(DRY); link 判据内联不单抽函数(只用一次, 单抽即透传函数)
+        #   严禁取 context_root_task_id 非空 —— 独立任务该字段=自身 task_id(非空),
+        #   取它会把独立任务误判成 link, 首帧两组全填错(stream_orchestrator.py:383 实证)
+        _meta = getattr(self.agent, "_start_meta", None) or {}
+        _linked = _meta.get("context_link_mode") == "linked"
+        _frame = self._build_history_context_frame(step, _meta, _linked)
         return _emitter.emit(MetaStep(
-            step=step, type="history_context", content=_ov.get("summary", ""),
-            message_count=_ov["message_count"], estimated_tokens=_ov["estimated_tokens"],
-            truncated=_ov["truncated"],
-            injected_message_count=_ov["injected_message_count"],
-            injected_estimated_tokens=_ov["injected_estimated_tokens"],
-            compressed=_ov["compressed"],
-            compress_saved_pct=_ov["compress_saved_pct"],
+            step=step, type="history_context", severity="info", **_frame,
         ))
```

**改动 5/6** — 新增 `_build_history_context_frame()`（整帧唯一组装点，紧随 `build_history_context_step` 之后）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -360,6 +360,64 @@
         ))
 
+    def _build_history_context_frame(self, step: int, meta: Dict[str, Any], linked: bool) -> Dict[str, Any]:
+        """组装 history_context 整帧 —— content/conv/inject 一次成型(§3.1.1)
+
+        2026-10-09 小欧: 三组装配收归一处, 不拆 helper(KISS-DIRECT: 一帧一函数, 一个文件内不分层)。
+          conv 实数只取一次, 复用于帧字段与压缩率分子(DRY); 空组内联字面量(各用一次, 不单抽工厂)。
+          inject 首帧定稿存槽、第2帧起复用(§3.1.1.6); summary 只在压缩成功时非空(§3.5)。
+        """
+        from app.services.agent.message_builder import MessageBuilder
+        _mb = self.agent.message_builder
+        _conv_count = len(_mb.conversation_history)
+        _conv_tokens = MessageBuilder._estimate_tokens(_mb.conversation_history)
+        _conv_truncated = bool(getattr(_mb, "_trimmed_this_round", False))
+
+        if step > 0:
+            _content = f"第{step}轮的对话历史上下文信息"
+            _conv = {"message_count": _conv_count, "estimated_tokens": _conv_tokens, "truncated": _conv_truncated}
+        elif linked:
+            _content = "连续任务,注入历史上下文"
+            _conv = {"message_count": "", "estimated_tokens": "", "truncated": ""}
+        else:
+            _content = "独立任务,无历史上下文注入"
+            _conv = {"message_count": _conv_count, "estimated_tokens": _conv_tokens, "truncated": _conv_truncated}
+
+        if step == 0:
+            if linked:
+                # 前缀格式固定「第N个link任务, <情况文字>」(§3.1.1.4), 四种情况互斥
+                _prefix = f"第{int(meta.get('context_link_index') or 1)}个link任务, "
+                _inj = self._injected_context or {}
+                _inj_count = int(_inj.get("message_count", 0) or 0)
+                _inj_tokens = int(_inj.get("estimated_tokens", 0) or 0)
+                _summary = str(getattr(self.agent, "_start_summary", "") or "").strip()
+                if not _inj_count:
+                    _compressed = "无历史上下文注入"
+                elif _summary:
+                    # 压缩率沿用现状口径 (1 - 装入/注入)×100, 夹逼 ≥0, 1位小数(§3.6)
+                    _pct = max(0.0, round((1 - _conv_tokens / _inj_tokens) * 100, 1)) if _inj_tokens else 0.0
+                    _compressed = f"本次注入历史信息压缩率= {_pct}%"
+                elif getattr(self.agent, "_compact_attempted", False):
+                    # 尝试压缩却无摘要 = 失败/取消(start_step.py:226/233), 如实上报; 未触发则空串
+                    _compressed = "本次注入历史信息压缩失败"
+                else:
+                    _compressed = ""
+                self._inject_frame = {
+                    "injected_message_count": _inj_count,
+                    "injected_estimated_tokens": _inj_tokens,
+                    "compressed": _prefix + _compressed,
+                    "summary": _summary,
+                }
+            else:
+                self._inject_frame = {
+                    "injected_message_count": "", "injected_estimated_tokens": "",
+                    "compressed": "", "summary": "",
+                }
+        return {
+            "content": _content,
+            "conv_context": _conv,
+            # 浅拷贝出槽 —— MetaStep 存引用, 直接给槽会被调用方改写污染后续帧
+            "inject_context": dict(self._inject_frame),
+        }
+
```

**改动 6/6** — `build_task_snapshot()` 删 `_overview` 调用并自取数字（L392、L418-426）

```diff
--- a/backend/app/monitoring/agent_telemetry.py
+++ b/backend/app/monitoring/agent_telemetry.py
@@ -392,1 +392,9 @@
-        _overview = self.build_context_overview()
+        # 2026-10-08 北京老陈裁定: build_context_overview 已删, 快照落库自取数字(§2.4 两消费点形状互斥);
+        # 2026-10-09 小欧: 直接取数不调帧函数 —— 落库只要 4 个数字, 不要文案(SRP: 快照与帧各走各的, 不拼文字再扔)
+        from app.services.agent.message_builder import MessageBuilder
+        _mb = self.agent.message_builder
+        _snap_count = len(_mb.conversation_history)
+        _snap_tokens = MessageBuilder._estimate_tokens(_mb.conversation_history)
+        _inj = self._injected_context or {}
+        _inj_count = int(_inj.get("message_count", 0) or 0)
+        _inj_tokens = int(_inj.get("estimated_tokens", 0) or 0)
+        _snap_summary = str(getattr(self.agent, "_start_summary", "") or "").strip()
@@ -418,9 +426,11 @@
-            "context_message_count": _overview["message_count"],
-            "context_estimated_tokens": _overview["estimated_tokens"],
+            "context_message_count": _snap_count,
+            "context_estimated_tokens": _snap_tokens,
             "context_truncated": ...,
-            "context_injected_message_count": _overview["injected_message_count"],
-            "context_injected_estimated_tokens": _overview["injected_estimated_tokens"],
+            "context_injected_message_count": _inj_count,
+            "context_injected_estimated_tokens": _inj_tokens,
             ...
-            "context_compressed": 1 if _overview["compressed"] else 0,
-            "context_compress_saved_pct": _overview["compress_saved_pct"],
+            # DB 列语义未变(int 0/1 + float), 表结构零改动(§九); 压缩率与帧内同口径(§3.6), 直接算不反解文字
+            "context_compressed": 1 if _snap_summary else 0,
+            "context_compress_saved_pct": (
+                max(0.0, round((1 - _snap_tokens / _inj_tokens) * 100, 1))
+                if (_snap_summary and _inj_tokens) else 0.0),
```
## 六、前端代码改动（一个代码文件一小节 · 每处代码一个 unified diff）

### 6.0 改动总览（7 个代码文件 · 24 处）

| 代码文件 | 改动处数 | 改动点 | 对应 §3.1 要求 |
|---|---|---|---|
| `frontend/src/types/sse.ts` | 3 处 | ① `ContextOverviewFrame` 重写 ② 新增 `ConvContextFrame` ③ 新增 `InjectContextFrame` | §3.1 双分组嵌套；§3.4 `compressed` 带前缀 |
| `frontend/src/types/execution.ts` | 2 处 | ④ 类型 import（复用 sse.ts，无循环依赖） ⑤ `ExecutionStep` 的 history_context 字段同步 | §3.1 双分组嵌套 |
| `frontend/src/features/chat/services/sseParser.ts` | 1 处 | ⑤ `history_context` 白名单改整体透传 | §3.1.1 两组必须透传 |
| `frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx` | 7 处改动 + 1 锚点 | ⑥ 取值路径改嵌套 ⑦ `count` 改读嵌套 ⑧ `injected` 改读嵌套 + 新增 `compressedText`/`injectFailed` ⑨ 注入行读成品文字 ⑩ `metricLine` 拆 `injectPart`/`convPart` ⑪ 卡片内拆两段标题 ⑫ 摘要区条件+标题 ⑬ 警示行保留（回归锚点）| §3.1.1.8 两段各读一组；§3.3；§3.5 |
| `frontend/src/features/chat/components/taskinfo/infoMaps.tsx` | 4 处 | ⑭ `EVENT_ICON_MAP` 新增图标 ⑮ 类型 import（复用 sse.ts） ⑯ `ContextSource` 改复用帧类型 ⑰ `mapStatus` 判据改 `content` | 压缩事件图标；§3.3 `content` 三态 |
| `frontend/src/features/chat/hooks/useTaskInfo.ts` | 3 处 | ⑯ kind 并入 `context_compressed` ⑰ `_compressedSeen` 守卫 ⑱ 分支加压缩事件 | 北京老陈令：有压缩加时间线事件 |
| `frontend/src/tests/unit/sse-context-overview-frame-contract.test.ts` | 1 处 | ⑲ 真帧换新结构 | §3.1 双分组嵌套 |

**落地顺序**：`types/sse.ts` → `types/execution.ts` → `sseParser.ts` → `ContextOverviewCard.tsx` → `infoMaps.tsx` → `useTaskInfo.ts` → 契约测试。

---

### 6.1 `types/sse.ts`（3 处）

**文件**：`frontend/src/types/sse.ts`

**改动 1/3** — `ContextOverviewFrame` 重写（L56-67）

```diff
--- a/frontend/src/types/sse.ts
+++ b/frontend/src/types/sse.ts
@@ -56,14 +56,11 @@
 export interface ContextOverviewFrame {
-  summary: string;
-  message_count?: number;
-  estimated_tokens?: number;
-  truncated: boolean;
-  // 2026-10-08 小欧 - 删 injected_ratio(注入量/装入量, >1 才代表压缩生效但标签叫"压缩比"方向相反,
-  //   且未压缩时因装入含 system+本轮提问而不等于 1.0, 两语义混淆)。改为下面两个语义明确的字段。
-  compressed?: boolean;
-  compress_saved_pct?: number;
-  injected_message_count?: number | null;
-  injected_estimated_tokens?: number | null;
+  // 2026-10-08 北京老陈裁定: 扁平 8 字段改双分组嵌套(§3.1)。两组互斥填充实, 空位给空字符串
+  conv_context?: ConvContextFrame;
+  inject_context?: InjectContextFrame;
+  content?: string;   // 首帧: 独立任务,无历史上下文注入 | 连续任务,注入历史上下文
+                      // 第2帧起: 第<N>轮的对话历史上下文信息
 }
```

**改动 2/3** — 新增 `ConvContextFrame`（紧随 `ContextOverviewFrame` 之后）

```diff
--- a/frontend/src/types/sse.ts
+++ b/frontend/src/types/sse.ts
@@ -67,2 +67,9 @@
 }
 
+// 2026-10-08 小欧: conv 侧独立成 interface(ISP) —— 「对话上下文」标签只读这一个, 不越界读 inject
+export interface ConvContextFrame {
+  message_count?: number | '';
+  estimated_tokens?: number | '';
+  truncated?: boolean | '';
+}
+
```

**改动 3/3** — 新增 `InjectContextFrame`（紧随 `ConvContextFrame` 之后）

```diff
--- a/frontend/src/types/sse.ts
+++ b/frontend/src/types/sse.ts
@@ -74,2 +74,11 @@
 }
 
+// 2026-10-08 小欧: inject 侧独立成 interface(ISP) —— 「历史上下文」标签只读这一个
+export interface InjectContextFrame {
+  injected_message_count?: number | '';
+  injected_estimated_tokens?: number | '';
+  // 2026-10-08 小欧: 文字带「第N个link任务, 」前缀(§3.1.1 四), 前端直接显示不再拼装
+  compressed?: string;
+  summary?: string;
+}
+
```

---

### 6.2 `types/execution.ts`（2 处：类型 import + 字段同步）

**文件**：`frontend/src/types/execution.ts`

**改动 1/2** — `execution.ts` 顶部加类型 import（L24 之后）

```diff
--- a/frontend/src/types/execution.ts
+++ b/frontend/src/types/execution.ts
@@ -22,2 +22,4 @@
 // 编辑历史: 2026-10-08 小欧 - history_context 字段块: 删 injected_ratio, 改 compressed + compress_saved_pct
 //   (同 sse.ts 的 ContextOverviewFrame, 后端 build_context_overview 为唯一真源, 两处声明须同步)
+// 2026-10-09 小欧: 引 ConvContextFrame/InjectContextFrame(DRY, 不在两处各写一套)。
+//   无循环依赖 —— sse.ts 零 import(2026-08-27 断环后), import type 编译期擦除
+import type { ConvContextFrame, InjectContextFrame } from './sse';
 
 export interface ExecutionStep {
```

**改动 2/2** — `ExecutionStep` 的 history_context 字段同步（L191-202，`ExecutionStep` 接口内）

```diff
--- a/frontend/src/types/execution.ts
+++ b/frontend/src/types/execution.ts
@@ -191,14 +191,14 @@
   // 2026-09-12 小欧: 删 final_status 死字段(useTaskInfo 读 frames.finalStats.final_status, 不读 step; outcome(L88)为终态单一权威) — 小欧-2026-09-12
-  // history_context
-  message_count?: number;
-  estimated_tokens?: number;
-  // 2026-10-08 小欧 - 删 injected_ratio(误导源), 与 sse.ts 的 ContextOverviewFrame 同步改语义明确的两个字段
-  compressed?: boolean;
-  compress_saved_pct?: number;
-  // 2026-10-04 小欧 - 与 sse.ts 的 ContextOverviewFrame 对齐
-  injected_message_count?: number | null;
-  injected_estimated_tokens?: number | null;
-  // 2026-10-04 小欧 - 裁剪标志随帧入 steps, 供 useTaskInfo 生成"历史对话已裁剪"事件(帧级字段, 与 metaFrames 同源不重复发)
-  truncated?: boolean;
+  // 2026-10-08 北京老陈裁定: 与 sse.ts 的 ContextOverviewFrame 同步(两处声明长期分裂, 本次一并改)
+  conv_context?: ConvContextFrame;
+  inject_context?: InjectContextFrame;
+  // 2026-10-08 小欧: truncated 保留顶层 —— 它是"该帧因裁剪而入 steps"的门控标记
+  //   (sseParser.ts pushAndFlush 时写), 与帧内 conv_context.truncated 语义不同
+  truncated?: boolean;
 }
```

---

### 6.3 `services/sseParser.ts`（1 处：白名单透传 + 入 steps 帧带分组同一块）

**文件**：`frontend/src/features/chat/services/sseParser.ts`

**改动 1/2** — `history_context` 白名单改整体透传 + 入 steps 帧带分组（L529-557）

```diff
--- a/frontend/src/features/chat/services/sseParser.ts
+++ b/frontend/src/features/chat/services/sseParser.ts
@@ -529,30 +529,32 @@
       case 'history_context': {
         logTypeArrival('history_context'); // 2026-09-14 小欧 debug 各 type 统一打点 — 小欧-2026-09-14
-        const content =
-          typeof rawData.content === 'string' ? rawData.content : '';
-        const trimmed = rawData.truncated === true;
+        // 2026-10-08 北京老陈裁定: 双分组嵌套整体透传。本 parser 是逐字段白名单,
+        //   必须显式列全两个键, 否则嵌套字段被静默丢弃(2026-10-04 曾出过该事故)
+        const content =
+          typeof rawData.content === 'string' ? rawData.content : '';
+        const trimmed = rawData.conv_context?.truncated === true;
         handlers.setMetaFrames?.((prev) => ({
           ...prev,
           contextOverview: {
-            summary: content,
-            message_count: rawData.message_count,
-            estimated_tokens: rawData.estimated_tokens,
-            truncated: trimmed,
-            compressed: rawData.compressed === true,
-            compress_saved_pct: rawData.compress_saved_pct ?? 0,
-            injected_message_count: rawData.injected_message_count ?? null,
-            injected_estimated_tokens:
-              rawData.injected_estimated_tokens ?? null,
+            content,
+            conv_context: rawData.conv_context,
+            inject_context: rawData.inject_context,
           },
         }));
+        // 2026-10-09 小欧: 入 steps 帧必须带两组字段 —— useTaskInfo 的裁剪/压缩事件从 steps 扫描派生,
+        //   不带则两事件永不触发(实证: 原 push 只有 content/step/timestamp/truncated 四键, 下方旧块整体替换)
         // 2026-10-04 小欧: 仅裁剪轮入 steps(北京老陈令: truncated=1 要在行尾事件列表留一条); 事件派生与现有 9 类同源(走 steps 扫描),
+        //   取帧内真实 timestamp; 非裁剪帧不入, 免每5轮里程碑灌入无用帧影响步骤数比较; 该类型已在 META_STEP_TYPES 不进业务流水线
+        if (trimmed) {
+          pushAndFlush(handlers, {
+            type: 'history_context',
+            content,
+            step: toStepNumber(rawData.step),
+            timestamp: timestampValue,
+            truncated: true,
+            conv_context: rawData.conv_context,
+            inject_context: rawData.inject_context,
+          });
+        }
-        // 2026-10-04 小欧: 仅裁剪轮入 steps(北京老陈令: truncated=1 要在行尾事件列表留一条); 事件派生与现有 9 类同源(走 steps 扫描),
-        //   取帧内真实 timestamp; 非裁剪帧不入, 免每5轮里程碑灌入无用帧影响步骤数比较; 该类型已在 META_STEP_TYPES 不进业务流水线
-        if (trimmed) {
-          pushAndFlush(handlers, {
-            type: 'history_context',
-            content,
-            step: toStepNumber(rawData.step),
-            timestamp: timestampValue,
-            truncated: true,
-          });
-        }
         break;
       }
```

---

### 6.4 `ContextOverviewCard.tsx`（9 处改动 + 1 回归锚点）

**文件**：`frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx`

**改动 1/8** — 取值路径改双分组嵌套（L56-59）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -56,4 +56,7 @@
   const ctx = CONTEXT_STATE_MAP[ctxState];
-  const tokens =
-    typeof overview === 'object' && overview ? overview.estimated_tokens : null;
-  const summary =
-    typeof overview === 'object' && overview ? (overview.summary ?? '') : '';
+  // 2026-10-08 北京老陈裁定: 读路径改双分组嵌套(§3.1)。typeof 守卫保留 ——
+  //   Props 声明 overview: string | ContextOverviewFrame | null, string 无 conv_context 键
+  const convCtx = typeof overview === 'object' && overview ? overview.conv_context : null;
+  const injectCtx = typeof overview === 'object' && overview ? overview.inject_context : null;
+  // 2026-10-09 北京老陈裁定: 后端给什么前端显示什么 —— 空位就是 "" 或 0, 不转换不归一不设开关
+  const tokens = convCtx?.estimated_tokens ?? '';
+  const summary = injectCtx?.summary ?? '';
```

**改动 2/8** — `count` 改读嵌套 + 删 `hasTokens` 中转（L60-62）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -60,4 +60,4 @@
-  const hasTokens = ctxState === 'ok' || ctxState === 'truncated';
-  const count =
-    typeof overview === 'object' && overview ? overview.message_count : null;
+  // 2026-10-09 北京老陈裁定: 后端给什么显示什么 —— 空位 "" 直显为空, 不设 hasTokens 开关。
+  //   真值性即判据(number | '' 中 '' 唯一假值, TS 自动收窄, 无需类型转换函数)
+  const count = convCtx?.message_count ?? '';

**改动 3/8** — `injected` 改读嵌套 + 新增 `compressedText` / `injectFailed`（L66-78）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -66,13 +66,13 @@
   // 2026-10-04 小欧: 跨任务注入字段仅 injected_message_count>0 时显(多数任务为 0, 显示是噪声 YAGNI)。
-  //   2026-10-08 删 ratio 字段: 后端 injected_ratio 已下线, 压缩率改由 overview.compressed 直渲。
-  const injected =
-    typeof overview === 'object' && overview
-      ? {
-          count: overview.injected_message_count ?? 0,
-          tokens: overview.injected_estimated_tokens ?? 0,
-        }
-      : null;
-  // 2026-10-08 小欧 压缩率: 派生时收窄 union 类型, 不在 JSX 内直接访问(TS18047/TS2339);
-  //   仅压缩时产出, 未压缩返 null → 整段不显, 不用"1.0×"冒充"压缩了"
-  const compressInfo =
-    typeof overview === 'object' && overview && overview.compressed === true
-      ? { savedPct: overview.compress_saved_pct ?? 0 }
-      : null;
+  const injected = injectCtx
+    ? {
+        count: injectCtx.injected_message_count ?? '',
+        tokens: injectCtx.injected_estimated_tokens ?? '',
+      }
+    : null;
+  // 2026-10-08 北京老陈裁定: compressed 已是后端成品文字(含「第N个link任务, 」前缀),
+  //   前端直显; 失败态由文案判定, 不再靠 bool(§3.4)
+  const compressedText = injectCtx?.compressed ?? '';
+  const injectFailed = compressedText.includes('压缩失败');
```

**改动 4/8** — `metricLine` 内注入行改读成品文字（L94-99）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -94,6 +94,5 @@
-            {compressInfo && (
+            {compressedText && (
               <>
-                {' · 已压缩 '}
-                {compressInfo.savedPct.toFixed(1)}%
+                {' · '}
+                {compressedText}
               </>
             )}
```

**改动 5/8** — `metricLine` 拆 `injectPart` / `convPart`（L85-124 重组）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -85,39 +85,43 @@
-  const metricLine =
-    count != null || hasTokens ? (
-      <div>
-        {injected && injected.count > 0 && (
-          <div>
-            跨任务注入 {injected.count} 条 · 估算Token约{' '}
-            {injected.tokens.toLocaleString()} ({formatTokenK(injected.tokens)})
+  // 2026-10-08 北京老陈裁定: 两个标签各读一组(§3.1.1.8), 故 metricLine 拆 injectPart/convPart。
+  //   行内 metric 仍用两者组合; 占窗率/formatTokenK/警示行原样保留, 不得丢功能。
+  //   2026-10-09 北京老陈裁定: 空值直显 —— '' 真值性为假, 天然不渲染, 不写 != null(对 '' 恒真, 会误显)
+  const injectPart =
+    injected && injected.count ? (
+      <div>
+        跨任务注入 {injected.count} 条 · 估算Token约{' '}
+        {injected.tokens.toLocaleString()} ({formatTokenK(typeof injected.tokens === 'number' ? injected.tokens : null)})
+        {compressedText && (
+          <>
+            {' · '}
+            {compressedText}
+          </>
+        )}
+      </div>
+    ) : null;
+  // 2026-10-09 北京老陈裁定: 空值直显 —— count/tokens 为 "" 时整段不渲染, 不写 != null(对 "" 恒真会误显)
+  const convPart =
+    count || tokens ? (
+      <div>
+            {/* 2026-10-08 小欧 标签订正: 原 `装入历史对话 N 条`, 但 message_count 是 conversation_history
+                全量(含本轮 system/提问/工具调用), 注入105装入117 时用户会以为多出 12 条不知来路。 */}
+        {count ? (
+          <span title="上下文全部消息条数（含本轮提问与工具调用），非仅历史对话">
+            上下文 {count} 条
+          </span>
+        ) : null}
+        {count && tokens ? <span> · </span> : null}
+        {tokens ? <span>估算Token约 {formatTokenK(tokens)}</span> : null}
+            {/* 占窗率: 分子是 MessageBuilder 粗估 token, 与 TaskInfoBar 的 prompt token 不同口径,
+                故标注(估算)并在 title 里说明, 避免用户误当精确值。 */}
+        {usedPct != null ? (
+          <span
+            title={`按估算 token ${tokens} ÷ 窗口 ${contextWindow} 计算，非 LLM 实测 prompt`}
+          >
+            {' · 占窗率(估算) '}
+            {usedPct}%
+          </span>
+        ) : null}
+      </div>
+    ) : null;
+  const metricLine =
+    injectPart || convPart ? (
+      <div>
+        {injectPart}
+        {convPart}
       </div>
     ) : null;
```

**改动 6/8** — 卡片内容拆两个标签段（L160-165）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -160,12 +160,20 @@
       content={
         <>
           <div
             style={{ fontWeight: FontWeight.BOLD, color: Colors.TEXT.PRIMARY }}
           >
             历史上下文
           </div>
-          <div>{metricLine ?? ctx.text}</div>
+          <div>{injectPart ?? ctx.text}</div>
+          <div
+            style={{ fontWeight: FontWeight.BOLD, color: Colors.TEXT.PRIMARY }}
+          >
+            对话上下文
+          </div>
+          <div>{convPart ?? ctx.text}</div>
           {summary && (
```

**改动 7/10** — 摘要区显示条件 + 标题（L166、L188-190）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -166,1 +166,1 @@
-          {summary && (
+          {(summary || injectFailed) && (
@@ -188,2 +188,3 @@
               >
-                {compressInfo ? '已注入摘要' : '最近提问'}
+                {injectFailed ? '压缩失败' : '已注入摘要'}
               </div>
-              <div>{summary}</div>
+              {summary && <div>{summary}</div>}
             </div>
```

**改动 8/10** — `usedPct` 加 typeof 守卫（L81-84）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -81,4 +81,5 @@
  // 2026-10-04 小欧: 装入条数 + 估算 token + 占窗率 同行(北京老陈定); 占窗率=估算 token / 窗口, 窗口缺失则不显
-  const usedPct =
-    tokens != null && contextWindow
-      ? Math.round((tokens / contextWindow) * 100)
-      : null;
+  // 2026-10-09 北京老陈裁定: tokens 为 "" 时不得算 —— "" != null 恒真, ""/窗口=0 会误显占窗率 0%
+  const usedPct =
+    typeof tokens === 'number' && contextWindow
+      ? Math.round((tokens / contextWindow) * 100)
+      : null;
```

**改动 9/10** — 行内值去 `hasTokens`（L131）

```diff
--- a/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
+++ b/frontend/src/features/chat/components/taskinfo/ContextOverviewCard.tsx
@@ -131,1 +131,3 @@
-      value={hasTokens ? formatTokenK(tokens) : ctx.text}
+      // 2026-10-09 北京老陈裁定: 有数字显数字, 无数字显状态文案 —— 真值性即判据
+      value={tokens ? formatTokenK(tokens) : ctx.text}
```

**改动 10/10** — 截断警示行保留（L194-196，无改动，留作回归锚点）
### 6.5 `infoMaps.tsx`（4 处：图标 + 类型 import + 类型声明 + 判据）

**文件**：`frontend/src/features/chat/components/taskinfo/infoMaps.tsx`

**改动 1/3** — `EVENT_ICON_MAP` 新增 `context_compressed` 图标（L111-112）

```diff
--- a/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
+++ b/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
@@ -111,2 +111,3 @@
   // 2026-10-04 小欧: 历史对话裁剪事件(北京老陈令改名 context_trimmed, 与输出截断 truncated 区分), 复用警示图标
   context_trimmed: <WarningOutlined />,
+  // 2026-10-09 北京老陈令: 压缩事件图标, 与裁剪事件同级复用警示图标(压缩改变了历史原貌, 值得警示)
+  context_compressed: <WarningOutlined />,
```

**改动 2/3** — `ContextSource` 类型声明新字段（L75-84）

```diff
--- a/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
+++ b/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
@@ -28,6 +28,8 @@
 import type { ProcessEvent, TaskBadge } from '../../hooks/useTaskInfo';
+// 2026-10-09 小欧: ContextSource 改复用帧类型(DRY), 不再手写一套平铺形状
+import type { ContextOverviewFrame } from '@/types/sse';
 
 // ---------- BADGE_MAP（cancelled 与 idle 区分） ----------
```

```diff
--- a/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
+++ b/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
@@ -75,9 +77,9 @@
// 输入形态: overview 字符串 / overview 对象{summary,estimated_tokens,truncated}(均来自 history_context 帧)
 export interface ContextSource {
   overview?:
     | string
-    | {
-        summary?: string;
-        estimated_tokens?: number | null;
-        truncated?: boolean;
-      }
+    // 2026-10-09 小欧: 类型跟随帧结构改 —— 不改则 mapStatus 读 o.content/o.conv_context 报 TS2339。
+    //   测试喂旧形状会挂, 测试跟随系统改(北京老陈令: 测试迁就系统)
+    | ContextOverviewFrame
     | null;
 }
```

**改动 3/3** — `mapStatus` 判据改 `content`（L87-95）

```diff
--- a/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
+++ b/frontend/src/features/chat/components/taskinfo/infoMaps.tsx
@@ -87,11 +87,13 @@
   // 2026-10-07 小欧: 上下文数据只认 history_context 帧(overview), 不再回退 start.content
-  const summary = typeof o === 'string' ? o : (o?.summary ?? null);
-  const truncated =
-    typeof o === 'object' && o !== null ? o.truncated === true : false;
-  const hasTokens =
-    typeof o === 'object' && o !== null ? o.estimated_tokens != null : false;
+  // 2026-10-08 北京老陈裁定: 判据改 content —— 新结构下 summary 只在压缩成功时非空,
+  //   用它判态会让"独立任务,无历史上下文注入"(content 有值 summary 空)被误判 empty
+  const mode = typeof o === 'string' ? o : (o?.content ?? '');
+  const convCtx = typeof o === 'object' && o !== null ? o.conv_context : null;
+  const truncated = convCtx?.truncated === true;
+  // 2026-10-09 小欧: 空位 "" 必须判 false, 0 判 true —— Boolean("")=false 碰巧对但 Boolean(0)=false 是错的
+  const hasTokens = typeof convCtx?.estimated_tokens === 'number';
   if (truncated) return 'truncated';
-  if (summary) return hasTokens ? 'ok' : 'summary-only';
+  if (mode) return hasTokens ? 'ok' : 'summary-only';
```

---

### 6.6 `useTaskInfo.ts`（4 处）

**文件**：`frontend/src/features/chat/hooks/useTaskInfo.ts`

**改动 1/3** — 事件 kind 并入 `context_compressed`（L87-89）

```diff
--- a/frontend/src/features/chat/hooks/useTaskInfo.ts
+++ b/frontend/src/features/chat/hooks/useTaskInfo.ts
@@ -87,3 +87,6 @@
     // 2026-10-04 小欧: 历史对话裁剪事件(北京老陈令改名 context_trimmed): 原 truncated 一名三义
     //   (输出截断帧类型 / 位4 输出截断 / 本事件), 视觉上无法与 error 区分
     | 'context_trimmed';
+    // 2026-10-09 北京老陈令: 有压缩加一条压缩事件, 与裁剪事件同级(时间线只留首条, 见改动 2/3)
+    | 'context_compressed';
```

**改动 2/3** — 新增 `_compressedSeen` 首条守卫（L203-204）

```diff
--- a/frontend/src/features/chat/hooks/useTaskInfo.ts
+++ b/frontend/src/features/chat/hooks/useTaskInfo.ts
@@ -203,2 +203,5 @@
     // 2026-10-04 小欧: 历史对话裁剪只留首条事件(裁剪可连续多轮触发, 每轮一条会刷屏并挤掉有效事件, 事件列表仅存最近20条)
     let _trimSeen = false;
+    // 2026-10-09 北京老陈令: 压缩事件同理只留首条 —— inject_context 首帧定稿后不变,
+    //   不加守卫则每5轮水位帧重复一条
+    let _compressedSeen = false;
```

**改动 3/4** — `history_context` 分支加压缩事件（L286-296）

```diff
--- a/frontend/src/features/chat/hooks/useTaskInfo.ts
+++ b/frontend/src/features/chat/hooks/useTaskInfo.ts
@@ -286,10 +286,20 @@
         // 2026-10-04 小欧: 历史对话裁剪事件(北京老陈令) —— 只记本任务首条, 文本固定不用帧内摘要(摘要是最近一条对话内容, 与"已裁剪"无关会误导)
         case 'history_context':
-          if (s.truncated && !_trimSeen) {
+          if (s.conv_context?.truncated && !_trimSeen) {
             _trimSeen = true;
             processEvents.push({
               kind: 'context_trimmed',
               text: '历史对话已裁剪',
               time: s.timestamp,
             });
           }
+          // 2026-10-10 北京老陈令: 不拆 compressed 成品 —— 事件条件只用 summary 非空(有摘要⟺压缩成功)。
+          //   失败态不发事件(只在卡片标题行全文显示); 后缀空/无注入天然不触发
+          if (s.inject_context?.summary && !_compressedSeen) {
+            _compressedSeen = true;
+            processEvents.push({
+              kind: 'context_compressed',
+              text: s.inject_context.compressed || '历史已压缩',
+              time: s.timestamp,
+            });
+          }
           break;

**改动 4/4** — detail 分支 overview 取详情直给首帧（L181-190）

```diff
--- a/frontend/src/features/chat/hooks/useTaskInfo.ts
+++ b/frontend/src/features/chat/hooks/useTaskInfo.ts
@@ -181,9 +181,12 @@
         // 历史任务无实时 metaFrames 源：contextOverview/truncated 仅实时流产生，
         // 取实时 frames 会串味当前任务(2026-08-27 小欧 修复#5#6)。
-        overview: 
''
,
+        // 2026-10-10 北京老陈令[20]: 历史任务显示历史上下文 —— overview 取详情接口直给的首帧,
+        //   不从 steps 数组找(TaskInfoBar 传的是实时 steps, 历史任务时为空, find 永空)
+        overview: (() => {
+          const hc = detail.history_context_first;
+          return hc ? { content: hc.content ?? '', inject_context: hc.inject_context ?? undefined } : '';
+        })(),

---

### 6.7 契约测试（1 处）

**文件**：`frontend/src/tests/unit/sse-context-overview-frame-contract.test.ts`

**改动 1/1** — 真帧换新结构

```diff
--- a/frontend/src/tests/unit/sse-context-overview-frame-contract.test.ts
+++ b/frontend/src/tests/unit/sse-context-overview-frame-contract.test.ts
@@ -1,9 +1,11 @@
 // 契约测试: history_context 帧经 sseParser 透传后, 形状与后端一致 — 北京老陈 2026-10-08
 const RAW = {
   step: 0,
   type: 'history_context',
-  content: '上一轮的历史提问原文',
-  message_count: 12,
-  estimated_tokens: 3400,
-  truncated: false,
-  injected_message_count: 8,
-  injected_estimated_tokens: 2100,
-  compressed: false,
-  compress_saved_pct: 0,
+  content: '连续任务,注入历史上下文',
+  conv_context: { message_count: '', estimated_tokens: '', truncated: '' },
+  inject_context: {
+    injected_message_count: 8,
+    injected_estimated_tokens: 2100,
+    // 2026-10-10 小欧[20]: 未超窗无信息不挂光杆前缀, 全空(后端行为, 前端原样透传)
+    compressed: '',
+    summary: '',
+  },
 };
```

## 七、测试与验证

### 7.1 契约测试改造

**位置**：`tests/unit/sse-context-overview-frame-contract.test.ts`

现有真帧（`REAL_CONTEXT_OVERVIEW_FRAME`，L54-67）需换为新结构，并补三条断言：

| 断言 | 内容 |
|---|---|
| **首帧分工互斥** | 独立任务：`conv_context` 实填 + `inject_context` 四字段全空；link 任务：反之（守 §3.1.1 一）|
| **`N` 前缀存在** | link 任务 `compressed` 必以 `第N个link任务, ` 开头（守 §3.1.1 四）|
| **第 2 帧 inject 不变** | 第 2 帧的 `inject_context` 与首帧逐字段相等（守 §3.1.1 六）|
| **`summary` 独占约束** | 非压缩场景 `summary` 必须为空字符串（守 §3.5）|
| **状态文案不进 conv** | `content` 文字不得出现在注入 `conversation_history` 里（守 §3.3）|
| **压缩事件** | 压缩动作发生过（成功带率 / 失败）时时间线有且仅有一条 `context_compressed` 事件，文本 = 后端 `compressed` 成品；未超窗与无历史注入不触发（守 §3.4 四种情况）|
| **旧测试必挂项** | `taskinfo-info-maps.test.ts` 喂 `{summary:'摘要'}` → 新 `mapStatus` 因无 `content` 判 `empty`（原 `summary-only`）；`sse-...-contract.test.ts:101` 真帧判 `ok` → 新帧 conv 空判 `summary-only`。测试跟随系统改，不改系统迁就测试 |

### 7.2 验证命令

| 项 | 命令 |
|---|---|
| 后端单测 | `pytest`（backend 目录）|
| 前端类型（src）| `npx tsc -p tsconfig.json --noEmit` |
| 前端类型（e2e）| `npx tsc -p tsconfig.e2e.json --noEmit` |
| 契约测试 | `npx vitest run src/tests/unit/sse-context-overview-frame-contract.test.ts` |
| 规范 | `npm run check:full` |

---

## 八、实施顺序

| 阶段 | 内容 | 依赖 |
|---|---|---|
| 1 | §5.3 §5.4（初始化 + `start_step.py` 三处）| 无 |
| 2 | §5.1 §5.2（链内序号 `N`：`storage.py` 查询 → orchestrator 取数注入）| 无 |
| 3 | §5.5（`agent_telemetry.py` 6 处）| 阶段 1、2 |
| 4 | §6.1 §6.2 §6.3（类型定义 + parser 白名单）| 阶段 3（字段名须先定）|
| 5 | §6.4（卡片 7 改动 + 1 锚点）| 阶段 4 |
| 6 | §6.5 §6.6（图标 + `mapStatus` 判据 + 裁剪/压缩事件）| 阶段 5 |
| 7 | §6.7（契约测试 + 压缩事件断言）| 阶段 6 |


**顺序铁律**：后端字段名（阶段 3）必须先定，前端 parser 白名单（阶段 4）才能对齐；漏键会静默丢字段。

---

## 九、遗留问题

| 编号 | 问题 | 状态 |
|---|---|---|
| Q1 | `severity` 字段（`agent_telemetry.py:359`）本设计未纳入 `conv_context`/`inject_context`，继续作为 MetaStep 顶层 kwarg 透传 | 保持现状，待确认是否需归组 |
| Q2 | 首帧 link 任务的 `conv_context` 三字段留空，此时 `estimated_tokens` 无值，压缩率算式的分子取 conv 实况（`_build_inject_frame` 内现算，与帧内同口径）| 已解决 |
| Q4 | link 序号 `N` 每次运行现查链内任务数，链被外部改动（删任务）时 `N` 会变 | 观察，不影响单次运行 |
| Q5 | 已删除：`compressed` 文字反解方案已废（无双重解析），快照直接用数字算 | 已解决（§5.5 改动 8/9） |
| Q3 | `estimated_tokens` 为 MessageBuilder 粗估，与 TaskInfoBar 的 LLM 实测 prompt token 不同口径 | 沿用现状，前端已标"估算" |
