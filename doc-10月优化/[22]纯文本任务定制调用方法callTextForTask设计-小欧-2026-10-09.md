# callTextForTask —— 纯文本任务的 provider 定制调用钩子设计

**编写人**: 小欧
**编写时间**: 2026-10-09 22:50
**版本**: v1.0（**待北京老陈审核，尚未实施**）
**依据**: `F:\agenttool\ZenFree-Test-20260923\Zen免费层测试与分析总结.md` v1.11（小欧 2026-09-23 桌面端抓包实测）
**适用范围**: 历史注入压缩摘要（`compaction/summary.py`）等**纯文本任务**的 LLM 调用

---

## 目录

一、背景与问题
二、门禁四条件（实测证据）
三、根因定位
四、方案设计
五、react 主循环零影响的论证
六、改动清单
七、代码 diff（供复审）
八、执行顺序与验收

---

## 一、背景与问题

### 1.1 现象

历史注入压缩阶段（`_compact_injected_history` → `generate_anchored_summary`）调用 LLM 产出六段锚定摘要。当 provider 为 `opencodeZen` 时，这个调用会失败。

### 1.2 诉求（北京老陈）

> 在历史注入压缩阶段，调用 provider 的时候，是 opencode 的模型时，不能简单调用，要用定制化的调用方式。

补充裁定四条：

1. **专门做一个模型调用方法**，细节写在函数里面
2. 方法名用 **`callTextForTask`**（provider 中立，不把provider 名写进方法名）
3. **细节对压缩摘要主过程隐藏，调用者透明** —— 摘要侧不得出现 provider 名、门禁、端点等细节
4. **对react 主流程一个字都不能改**（铁规）

### 1.3 前提

压缩摘要用**全局当前的 provider/model**（裁定：不另配模型）。所以方案必须在"全局是 zen"时生效，且对其它 provider 零影响。

---

## 二、门禁四条件（实测证据）

来源：`Zen免费层测试与分析总结.md` §10.1.1（2026-09-23 桌面端 1.18.31 经 mitmproxy 抓包 + 隔离重放）。**四条件缺一即 403 FreeTierError**：

| # | 位置 | 通过条件 |
|---|------|---------|
| 1 | 头 `User-Agent` | `opencode/<版本>` 且 **≥ 1.17.0** |
| 2 | 头 `x-opencode-session` | `ses_` + 12 位小写 hex + 14 位 base62（共 30 字符），**随机生成即可** |
| 3 | 体 `tools` | tools 数组**同时**含名为 `bash` 与 `read` 的 function（**二者必须都在**） |
| 4 | 体 `stream` | 必须为 **`true`** |

以下**不参与判定**（实测剥离）：`Authorization`、`x-opencode-client`/`-project`/`-request`、`tool_choice`、system 消息、messages 具体内容。

### 2.1 名称必须是精确的 bash / read（§10.1.4(1)）

| 情况 | 结果 |
|------|------|
| 两个名字都在 | 200 |
| 改 description / 调换顺序 / 附带其它 tool | 200（**只看名字**，schema 随意） |
| 只有其一，或叫 `shell`、`readtext` 等近义名 | **403** |
| `tools: []` 或无 `tools` 字段 | **403** |

### 2.2 两种端点的 tools 嵌套不同（§10.1.5，用错即 400）

| 端点 | 适用模型 | tools 格式 |
|------|---------|-----------|
| `/v1/chat/completions` | big-pickle / mimo / ling / nemotron | **双层** `{"type":"function","function":{name,…}}` |
| `/v1/responses` | **muse-\*** | **flat 单层** `{"type":"function","name":…}` |

---

## 三、根因定位

### 3.1 摘要的请求体里没有 tools，撞门禁第③条

```
compaction/summary.py:39   call_llm_with_fallback(agent=llm_agent, messages=feed, openai_tools=None)
   ↓ llm_call.py:90tool_choice = ... if openai_tools else None→ None
   ↓ client_sdk.py         request_stream(tools=None, tool_choice=None)
   ↓ client_sdk.py:33      if tools: body["tools"] = tools    → 无 tools 键
   ↓
  ✗ 门禁第③条不满足 → 403
```

### 3.2 为什么 FC 主循环没事，摘要有事

`opencodeZen.py:108` 和 `fundamental_register.py:15` 的注释都写"bash/read 真实工具由 fundamental_register 注册，FC 正常流程 `get_openai_tools` 已含"。**该说法在 2026-10-02 之后不准确**：

- `fundamental_register.py:5` 记着："shell 不叫 bash、删 bash 命名，实际注册名 shell"
- 真正让门禁通过的是**别名映射**：`tools_alias_mapper.py:359` `"shell": "bash"`、`:350` `"readtext": "read"`

FC 流程经 `get_openai_tools()` 走别名映射后，**对外暴露的名字**才是 `bash`/`read`；摘要传 `openai_tools=None`，**整条映射链路都绕过了**。

### 3.3 附带问题：muse-* 会把 messages 拍平（本次不处理）

`to_responses_body`（`opencodeZen.py:140-142`）把 messages 拍成单字符串，摘要 feed 的角色边界会全部丢失。**北京老陈裁定暂时不用 muse 模型，故不做任何规避**；将来若启用需重新评估。

---

## 四、方案设计

### 4.1 定位：adapter 钩子 + 各 provider 自行覆写

在 `ProviderAdapter` 基类加一个**默认不接管**的钩子；需要定制的 provider（如 `opencodeZen`）在自己的适配器里覆写它。摘要侧只管调，不问 provider 是谁。

```python
# base.py —— 默认实现恒不接管
@staticmethod
async def callTextForTask(client, messages) -> Optional[str]:
    """纯文本任务的定制化调用钩子 — 默认不接管, 返回 None 由调用方走通用路径"""
    return None
```

**provider 的区分靠多态覆写，不在函数体内做判断**：

```
summary.py（调用者，不含任何 provider 分支）
    ↓
adapter = get_provider_adapter(provider)      ← 按provider 挑实例(adapters/__init__.py:19 注册表)
    ↓
adapter.callTextForTask(client, feed)
    │
    ├─ 实例 = ProviderAdapter(默认)     → return None    → 摘要走原路径
    └─ 实例 = OpencodeZenAdapter(覆写)  → 真发请求        → zen 专用
```

`callTextForTask` 的函数体里**一行 provider 判断都没有**。它之所以是 zen 专用，只因为它定义在 `opencodeZen.py` 里。

若改成函数内 `if provider == "opencodeZen"`，则调用者也必须知道并传入 provider —— 裁定③"调用者透明"就废了，且provider 知识从 adapter 层泄漏到compaction 层。

**签名说明**：

- 不设 `**kw` —— 当前无任何调用方传额外参数，按 YAGNI 不预留口子；将来真有需要再加，届时 base 与覆写同步改
- 返回类型 base 为 `Optional[str]`（含"不接管"语义）、zen 为 `str`（永不返回 None），这是**协变收窄**，合法且表达更准 —— 不要为"统一"把 zen 改成 `Optional[str]`，那会丢掉"zen 一定接管"的信息

### 4.2 SRP：模块声明与实现必须一致

`base.py` 现声明的职责是"承载 **HTTP 接缝差异**与门禁 body/端点路由"，而既有 7 个钩子全是**纯变换**（无 I/O、可单测）。`callTextForTask` 是带 I/O 的调用编排，声明未覆盖。

**判定：这不是职责划分错误，是模块声明没覆盖新职责。** SRP 看的是"**一个引起变化的理由**"：

| | 引起变化的理由 | 是否同一个 |
|---|---|---|
| 既有 7 钩子 | provider 的 HTTP 约定变了 | ✅ |
| `callTextForTask` | provider 的**调用约定**变了（zen 门禁要求 body 带 tools） | ✅ 同源 |

**处置**：把 `base.py` 模块说明的职责从"HTTP 接缝差异"扩为"**provider 请求适配与调用约定差异**"，使声明与实现一致。这是**声明补全**，不改任何既有逻辑行。

> 备选方案（已否决）：把 `callTextForTask` 移到独立模块 —— 会让"哪个 provider 用哪种调用方式"的知识分裂到两处（adapter 注册表一处、分发逻辑一处），违反 DRY，且调用方要么 `hasattr` 探测（违反 DIP 依赖具体实现）、要么再import 第二个真源。留在 adapter 才是 OCP 的正确形态。

### 4.3 `callTextForTask` 函数内做两件事

| # | 做什么 | 解决 |
|---|--------|------|
| 1 | **带门禁 tools** 调 `client.request()` | 3.1 门禁第③条 |
| 2 | 取 `ChatResponse.content`，空或异常一律返 `""` | 零退化 |

**不做消息合成**（裁定：暂时不用 muse 模型）——见 7.3。
**不写重试**（裁定：系统是什么样就用什么样）——见 4.5。

### 4.4 为什么复用 `client.request()` 而不是裸 HTTP

调用链是两层，`agent.llm_client` 指向的是**上层**：

```
agent.llm_client = BaseAIService                ← agent 拿到的就是这个
    └─ self._llm_sdk = client_sdk.LLMClient    ← 真正发 HTTP 的一层
```

`stream_orchestrator.py:550` 把 `ai_service`（`BaseAIService` 实例）传作 `llm_client`。

**上层 `BaseAIService.request()` 已经包好了 zen 适配**，`callTextForTask` 拿到它就等于白拿：

| 能力 | 出处 |
|---|---|
| UA + session 头 | `client_sdk.py:312` `static_headers` |
| per-request 头 | `_adapt_request:351` |
| `stream:true` 强制 | `_adapt_request:346` `ensure_gate_body` |
| 端点路由（muse- → `/responses`） | `_adapt_request:347` `endpoint_for` |
| **tools 双层 → flat 自动转换** | `_adapt_request:350` `to_responses_body` |
| zen 强制流式 → 收集成非流式响应 | `client_sdk.py:386` `force_stream()` |

**所以本方法只需补第③条 tools，其余全部复用，不重复实现。**

⚠️ **返回值是 `ChatResponse` 对象**（`core.py:74-85`），不是 dict；且上层**失败时不抛异常**，错误塞进 `ChatResponse.error`。client_sdk 那一层返回的才是 dict（`_request_via_stream_collect:484`），已被上层消费掉。

### 4.5 重试：不在本方法内处理

`callTextForTask` **只调一次** `request()`，成功取文本、失败返 `""`，函数内不写任何重试。调用层自带什么就用什么。

与现状的差别只有一处：摘要现在经 `call_llm_with_fallback`，那一层还叠了 L2（`tuning.llm.response_retries`，默认 2）+ Text 降级。改走本方法后不再经过它。

**这个差别的实际影响**（按 `error_classifier.py:60-67` 的可重试判定逐场景核对）：

| 失败场景 | L1 是否重试 | 现状 | 本方案 | 判定 |
|---|---|---|---|---|
| **403**（门禁配方错） | 否（4xx 不在可重试集合） | L2 白跑 2 次 + Text 再跑 1 次，**3 次全废** | **1 次即失败** | **更快** |
| **5xx / 传输异常** | 是（`max_retries` 默认 3） | L1 耗尽后 L2 再来 2 轮 | L1 耗尽即止 | 少 2 轮，**轻微损失** |

403 场景是**改善**（`error_classifier` 注释本身写着"400/401/403 确定性失败，重发必再失败"，现状那 3 次纯属浪费）；持续 5xx 场景少 2 轮，由 L1 的 `max_retries=3` 兜底。

**取舍**：裁定"系统是什么样就什么样"，故不自建重试、不改通用层。若将来发现持续 5xx 下摘要成功率不够，那是通用 L1 的 `max_retries` 该调的问题，不在本方法解决。

### 4.6 对摘要无影响的既有行为

摘要纯产出文本、**不写库不改状态**，重复调用零副作用；`start_step.py:223/228` 在摘要前后各查 `check_cancelled`，取消检查不受本方案影响。

### 4.7 tool_choice：不传，取默认值 `auto`

`BaseAIService.request()` 签名默认 `tool_choice: str = "auto"`（`base_service.py:305`），不传即得该值。模型若真返回 tool_calls，`content` 为空 → 返 `""` → 零退化。

---

## 五、10 大规范逐条判定

### 5.1 日常编码 6 条

| 规范 | 判定 | 依据 |
|------|------|------|
| **SRP** 单一职责 | ✅ 合规（4.2 已修正声明） | 一个引起变化的理由 = provider 约定变化，与既有 7 钩子同源 |
| **DRY** 不重复 | ✅ | 门禁 tools、端点、flat 转换、重试全部复用既有实现，只补第③条 tools 一处 |
| **KISS-DIRECT** 简单直接 | ✅ | 调用侧只有一行 `await adapter.callTextForTask(...)`，无透传层、无工厂、无中间层 |
| **SLAP** 同一抽象层 | ✅ | 只做"发一次请求取文本"，不混入裁剪/装配/持久化 |
| **YAGNI** 不过度设计 | ✅ | 不设 `**kw`；不预留第二种provider 的参数位 |
| **禁止backward** | ✅ | 无兼容面：新钩子默认不接管，非 zen 走原路径，无旧形状回退代码 |

### 5.2 重构 4 条

| 规范 | 判定 | 依据 |
|------|------|------|
| **OCP** 开闭原则 | ✅ | 新增 provider 定制只需注册表加一行 + 自己的适配器覆写，`client_sdk`/`summary.py` 零改动 |
| **LSP** 里氏替换 | ✅ | 全仓仅 `OpencodeZenAdapter` 一个子类，必继承基类。返回值 `Optional[str]` → `str` 是协变收窄，合法 |
| **ISP** 接口隔离 | ✅ 不适用 | `ProviderAdapter` 早已是"被 `client_sdk` 内部按需调用"的实现细节，非外部消费者全量依赖的宽接口 |
| **复用优先** | ✅ | 无新公用函数；`GATE_STUBS` 复用既有注释常量（见 6.1），未造第二处真源 |

### 5.3 合理检查：是否为最优解

最优解本应是**改 `ensure_gate_body`，tools 为空时自动补门禁 tools** —— 只动 1 个文件 7 行，且所有 zen 调用都受益。但它违反"react 一个字不能变"的铁规，**被排除**。

铁规约束下三方案对比：

| 方案 | 改动量 | 调用者透明性 | 结论 |
|---|---|---|---|
| **本方案** adapter 钩子 | 3 文件 | ✅ 完整 | **约束下最优** |
| `summary.py` 内直接 `if provider==` | 1 文件 | ❌ provider 知识泄漏 | 代码更少但违背裁定③ |
| 传 `openai_tools=STUBS` | 1 文件 | ⚠️ 常量放哪都是妥协 | 最省，但把 provider 约定塞进业务层 |

### 5.4 关联检查：无退化、无遗漏

- compaction 目录经核实**只有 `summary.py:39` 一个 LLM 调用点**（两个摘要函数共用 `_extract_response_content`），改动覆盖完整
- react 侧 7 个钩子字节未变（见第六章）
- L2 丢失的实际影响已逐场景核对（见 4.5）

---

## 六、react 主循环零影响的论证

### 6.1 react 路径调用的钩子全集

`_adapt_request`（`client_sdk.py:342-351`）是 react 与摘要**唯一共用的汇合点**：

| 钩子 | 调用点 | 本次改动 |
|------|--------|---------|
| `static_headers` | `client_sdk.py:312` | **不改** |
| `per_request_headers` | `_adapt_request:351` | **不改** |
| `ensure_gate_body` | `_adapt_request:346` | **不改** |
| `endpoint_for` | `_adapt_request:347` | **不改** |
| `to_responses_body` | `_adapt_request:350` | **不改** |
| `error_message_map` | `_raise_http_error:364` | **不改** |
| `force_stream` | `request():386` | **不改** |

新增的 `callTextForTask` **不出现在以上任何一行**。

### 6.2 三项结构性验证

| 验证 | 方法 | 结果 |
|------|------|------|
| 无反射遍历 | 搜 `getattr(.*_adapter` / `dir(adapter)` / `vars(adapter)` | **零命中**，新方法不会被动态派发顺带触发 |
| 无第三方子类 | 搜 `class \w+\(ProviderAdapter` | **只有** `OpencodeZenAdapter`，base 无 `__all__` |
| 无命名冲突 | 搜 `callTextForTask`（限 `backend/app` 代码目录） | 代码侧零命中，设计可落 |

### 6.3 影响面

| 路径 | 影响 |
|------|------|
| react 主循环（FC/Text、流式、muse-、降级、重试） | **零**（7 钩子字节未变，新方法无人调用） |
| 非 zen provider 的摘要 | **零**（base 钩子返 `None`，走原路径） |
| zen 摘要 | 唯一受益方 |

这是**论证**不是实测，兑现要靠 8.2 的验收项。

---

## 七、改动清单

| 文件 | 改动 | 规模 | react 影响 |
|------|------|------|-----------|
| `app/llm/adapters/base.py` | ① 模块说明扩职责边界（4.2）② 新增 `callTextForTask` 钩子（返 `None`）③ 补 `Optional` 导入 | +18 −3 | 零 |
| `app/llm/adapters/opencodeZen.py` | ① 补 `logger` ② 恢复 `GATE_STUBS` 注释（`:74`）③ 覆写 `callTextForTask` | +50 −16 | 零 |
| `app/services/agent/compaction/summary.py` | `_extract_response_content` 先问适配器，返 `None` 则走现有路径 | +20 −1 | 零 |
| `tests/test_adapters.py` | 补用例（见 9.2） | +50 | — |

净增约 85 行，其中注释与 docstring 占约六成。

### 7.1 一处取舍：恢复 `GATE_STUBS` 注释，不另起常量

`opencodeZen.py:74` 已有一份标着"<留着以后面备用>"的 `GATE_STUBS`，内容正是 bash+read 双层格式。复用它可避免同用途双常量并存。

**第 12 行的 typing import 一个字符都不动** —— 原注释"仅注释块GATE_STUBS备用代码使用，取消注释时无需再加"对本次改动仍然成立（`GATE_STUBS` 用的就是已导入的 `List`）。**这样就满足铁规对该文件的字面要求。**

需要说清的是：`opencodeZen.py:9/:71` 那条历史注释"方案1 删了 stub 注入"，指的是 `ensure_gate_body` 里的 **missing 注入逻辑**（FC 流程自带真工具时确属死代码）；给**纯文本任务**用是另一回事，两者不冲突 —— 恢复时会在注释里写明这个区分。

### 7.2 provider 取值

按 `react_step.py:341` 的既有写法，优先任务级快照：

```python
_task_llm = getattr(agent, "_task_llm_model", None) or getattr(agent.llm_client, "llm_model", None)
adapter = get_provider_adapter(getattr(_task_llm, "provider", "") or "")
```

### 7.3 明确不做的事

| 不做 | 原因 |
|---|---|
| **消息合成** | 裁定：暂时不用 muse 模型，3.3 的拍平问题不成立 |
| **自建重试** | 裁定：系统是什么样就用什么样（4.5） |
| 改 `to_responses_body` | 它被 react 主循环共用，改动即破坏"零影响" |
| 改 6.1 表里那 7 个钩子 | 同上，全部保持字节不变 |
| 给 `httpx.AsyncClient` 加 `trust_env=False` | 影响全部 provider，非本方案范围 |
| 摘要改用别的模型 | 裁定：全局是哪个就用哪个 |

---

## 八、代码 diff（供复审）

> 计划中的完整改动，**尚未落盘**。

### 8.1 `backend/app/llm/adapters/base.py`

```diff
@@ -1,8 +1,9 @@
 # -*- coding: utf-8 -*-
 # 模块说明: provider 适配基类 — 默认行为==现状(仅 Authorization, 无动态头, body 原样, chat 端点)
 #   新 provider 特殊 HTTP 握手 = 继承本基类覆写对应钩子; 未覆写即完全默认(现状语义)。
-#   归属依据(北京老陈核查): 承载 HTTP 接缝差异与门禁 body/端点路由;
+#   归属依据(北京老陈核查): 承载 provider 的请求适配与调用约定差异 ——
+#   前者指 HTTP 接缝差异与门禁 body/端点路由(7 个纯变换钩子), 后者指纯文本任务的
+#   调用约定(callTextForTask, 带 I/O)。两者同源于"provider 约定变化", 故同处一基类。
 #   schema/reasoning/工具别名(#3/4/5)为全局层, 绝不 provider 化。
 # 编辑历史: 2026-09-23 小欧 新建
+# 编辑历史: 2026-10-09 小欧 加 callTextForTask 钩子(纯文本任务定制调用, 默认不接管) — 小欧-2026-10-09
 
-from typing import Dict
+from typing import Dict, Optional

@@ -44,4 +45,15 @@ class ProviderAdapter:
     @staticmethod
     def error_message_map() -> Dict[int, str]:
         """provider 特有错误码 → 用户友好消息 — 默认空(走全局 error_classifier)"""
         return {}
+
+    @staticmethod
+    async def callTextForTask(client, messages) -> Optional[str]:
+        """纯文本任务的定制化调用钩子 — 默认不接管, 返回 None 由调用方走通用路径
+
+        用途: 压缩摘要这类"不要工具、只要一段文本"的任务, 若某 provider 的调用约定与
+        通用路径不同, 由其适配器覆写本钩子接管。默认不接管故对既有链路零影响。
+        返回 None = 未接管, 调用方自行走通用路径; 本钩子绝不抛异常, 以免波及既有链路。
+        """
+        return None
```

### 8.2 `backend/app/llm/adapters/opencodeZen.py`

**（a）补 logger**

```diff
@@ -11,6 +11,9 @@
 import os
 import time
 from typing import Dict, List  # List: 仅注释块GATE_STUBS备用代码使用, 取消注释时无需再加 — 北京老陈 2026-09-24
+import logging
+
+logger = logging.getLogger(__name__)
```

> 第 12 行 typing import **一个字符都不动**。

**（b）恢复 `GATE_STUBS`**

```diff
@@ -71,19 +71,21 @@
 # 2026-09-24 北京老陈 方案1: 删stub注入逻辑, ensure_gate_body只保留stream:true强制
 # bash/read真实工具由fundamental_register注册, 正常FC流程get_openai_tools已含
 # <留着以后面备用>
-# GATE_STUBS: List[Dict] = [
-#     {"type": "function", "function": {
-#         "name": "bash", "description": "Executes a given command.",
-#         "parameters": {"type": "object",
-#                        "properties": {"command": {"type": "string"}},
-#                        "required": ["command"]}}},
-#     {"type": "function", "function": {
-#         "name": "read", "description": "Read a file.",
-#         "parameters": {"type": "object",
-#                        "properties": {"filePath": {"type": "string"}},
-#                        "required": ["filePath"]}}},
-# ]
-# <留着以后面备用>
+# 2026-10-09 小欧 恢复(北京老陈裁定): 上面"方案1 删 stub 注入"删的是 ensure_gate_body 里的
+#   missing 注入逻辑 —— FC 流程自带真工具时它确是死代码。纯文本任务(压缩摘要)不经
+#   get_openai_tools, 无真工具可依, 必须靠本常量过门禁第③条(ZenFree-Test §10.1.1)。
+#   场景不同故不矛盾。门禁只认 function.name 精确为 bash/read(§10.1.4(1) 近义名一律403)。
+GATE_STUBS: List[Dict] = [
+    {"type": "function", "function": {
+        "name": "bash", "description": "Executes a given command.",
+        "parameters": {"type": "object",
+                       "properties": {"command": {"type": "string"}},
+                       "required": ["command"]}}},
+    {"type": "function", "function": {
+        "name": "read", "description": "Read a file.",
+        "parameters": {"type": "object",
+                       "properties": {"filePath": {"type": "string"}},
+                       "required": ["filePath"]}}},
+]
```

**（c）覆写 `callTextForTask`**

```diff
@@ -158,3 +160,36 @@ class OpencodeZenAdapter(ProviderAdapter):
         return {
             403: "Opencode Zen 免费层准入失败: 请检查 UA/session 头注入(适配层)或改用付费 key",
             426: "Opencode Zen 要求客户端升级(UpgradeRequired)",
         }
+
+    @staticmethod
+    async def callTextForTask(client, messages) -> str:
+        """纯文本任务的定制化调用 — opencode Zen 免费层实现 — 小欧 2026-10-09
+
+        【为什么需要它】压缩摘要走 call_llm_with_fallback(openai_tools=None), 请求体里没有 tools 键,
+        而门禁第③条要求 tools 同含 bash/read(ZenFree-Test §10.1.1) → 403。
+        FC 主循环之所以没事: 经 get_openai_tools() 走 tools_alias_mapper 别名映射, 对外名恰为
+        bash(shell→bash)/read(readtext→read); 摘要 openai_tools=None 整条映射链路都绕过了。
+
+        【门禁四条件在本方法内的分工】
+          ① UA≥1.17.0    ② 合法 session 头→ 客户端构造期 static_headers 已保证
+          ③ body tools 含 bash/read              → 【本方法负责】GATE_STUBS
+          ④ stream:true                        → ensure_gate_body 已强制
+          muse-* 走 /responses 需 flat tools     → to_responses_body 已自动转换
+        故本方法只补第③条, 其余全部复用 BaseAIService/client_sdk 既有机制, 不重复实现。
+
+        【provider 区分】不在本函数内判断 —— 本方法定义在 opencodeZen.py 即代表 zen 专用,
+        由 get_provider_adapter 挑实例实现分发(见 4.1)。
+
+        【重试】本方法只调一次, 不写重试。调用层(BaseAIService)自带什么就用什么。
+
+        【返回值】client 是 BaseAIService(上层), 其 request() 返回 ChatResponse 对象(core.py:74)
+        而非 dict, 且失败不抛异常、错误塞在 .error 里 —— 故取 .content, 不碰 .get("choices")。
+
+        【tool_choice】不传, 取 BaseAIService.request() 默认 "auto"。模型若真返回 tool_calls,
+        content 为空 → 返回 "", 零退化。
+        """
+        try:
+            _resp = await client.request(messages=messages, tools=GATE_STUBS)
+        except Exception as e:   # 上层已吞掉 HTTP 错误, 此处兜非 HTTP 异常
+            logger.warning(f"[callTextForTask] zen 纯文本调用异常({type(e).__name__}: {e}), 返回空串零退化")
+            return ""
+        if getattr(_resp, "error", None):
+            logger.warning(f"[callTextForTask] zen 纯文本调用失败({_resp.error}), 返回空串零退化")
+            return ""
+        return str(getattr(_resp, "content", "") or "").strip()
```

### 8.3 `backend/app/services/agent/compaction/summary.py`

```diff
@@ -32,17 +32,29 @@
 async def _extract_response_content(llm_agent, feed: List[Dict]) -> str:
-    """取 LLM 最终正文; error/action 返回空串, 交调用方装原历史(零退化) — 小欧 2026-10-10"""
+    """取 LLM 最终正文; error/action 返回空串, 交调用方装原历史(零退化) — 小欧 2026-10-10
+
+    2026-10-09 小欧: 先问适配器要不要接管本次纯文本调用(裁定"细节对摘要主过程隐藏、
+    调用者透明" —— 故此处不提任何 provider 名, 也不写门禁/端点细节, 那些全在适配器内):
+      - 接管(返回 str)   → 直接用, 由适配器按该 provider 的约定发起
+      - 不接管(返回 None) → 走下方既有 call_llm_with_fallback, **行为与改动前完全一致**
+    """
+    from app.llm.adapters import get_provider_adapter
+
+    try:
+        _lc = getattr(llm_agent, "llm_client", None)
+        # 任务级模型快照优先(同 react_step.py:341 写法); 摘要用全局当前模型, 不另配
+        _tl = getattr(llm_agent, "_task_llm_model", None) or getattr(_lc, "llm_model", None)
+        _adapter = get_provider_adapter(getattr(_tl, "provider", "") or "")
+        _txt = await _adapter.callTextForTask(_lc, feed)
+        if _txt is not None:
+            return _txt
+    except Exception as e:
+        # 定制路径自身异常不得影响主链, 落回通用路径
+        logger.warning(f"[compaction.summary] 定制调用钩子异常, 回落通用路径: {type(e).__name__}: {e}")
+
     from app.services.agent.llm_call import call_llm_with_fallback  # 2026-09-05 小健 8.5拆分: llm_stream→llm_call改名
 
     content = ""
     async for item in call_llm_with_fallback(agent=llm_agent, messages=feed, openai_tools=None):
         _p = getattr(item, "payload", None)
         if _p is not None and isinstance(_p, dict) and _p.get("type") == "answer":
             c = str(_p.get("content") or "").strip()
             if c:
                 content = c
     return content
```

**透明度检查**（裁定③）：

| 位置 | 是否泄漏 zen 细节 |
|---|---|
| `_extract_response_content` 正文 | ❌ 无 provider 名、无门禁、无端点、无 tools |
| 该函数 docstring | ❌ 未提 provider 名 |
| 调用点写法 | 一行 `await _adapter.callTextForTask(_lc, feed)`，与 provider 无关 |
| 回落路径 | 完全未改 |

---

## 九、执行顺序与验收

### 9.1 执行顺序

1. `base.py`：扩模块说明职责边界 + 加钩子 + 补 `Optional` 导入
2. `opencodeZen.py`：补 logger、恢复 `GATE_STUBS`、覆写 `callTextForTask`
3. `summary.py`：接线（钩子优先，`None` 回落，异常也回落）
4. 补 `test_adapters.py` 用例
5. 跑 9.2 验收项
6. 出实际 diff 复审后再决定是否提交

### 9.2 测试与验收

追加到 `tests/test_adapters.py`（该文件已有 30+ 个 adapter 用例，风格一致）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | base 不接管 | `ProviderAdapter.callTextForTask(...) is None` |
| 2 | 门禁 tools 名精确 | 传入 tools 的 `function.name` 恰为 `{"bash","read"}`，**非** `shell`/`readtext` |
| 3 | 双层格式 | chat 端 tools 为 `{"type":"function","function":{…}}` 双层 |
| 4 | 调用透传 | 假 client 捕获 `request()` 实参，断言收到 `tools` |
| 5 | tool_choice 未传 | 假 client 断言 `tool_choice` 取默认 `"auto"` |
| 6 | 成功取文本 | 返回 `ChatResponse.content` |
| 7 | 空content 返空串 | content 为空 → `""`（上层零退化） |
| 8 | 工具调用被忽略 | 仅返 tool_calls 无 content → `""` |
| 9 | error 字段转空串 | `ChatResponse.error` 非空 → `""` 并记日志 |
| 10 | 异常不外泄 | client 抛异常 → `""` |
| 11 | 消息原样透传 | 断言传入 `request()` 的 `messages` **就是原 feed**，未被改造 |
| 12 | GATE_STUBS 过 flat 转换 | 把 `GATE_STUBS` 喂 `to_responses_body`，断言 flat 化后名字仍为 `bash`/`read` |

> 用例 12 说明：`ensure_gate_body`（stream:true 强制）与 `to_responses_body`（双层→flat）**已在 `test_adapters.py` 有直接单测**（现有 L140/156/163/169/185），本次只需补一条衔接断言，**不需要也不该**用假 client 去断言最终 body —— 假 client 走不到 `client_sdk` 内部。

**零影响验收**（必须全绿才可宣称兑现第六章的论证）：

| # | 验收项 | 为什么是它 |
|---|--------|-----------|
| 1 | `tests/test_adapters.py` | 全仓**仅 2 个**测试直接 import adapter，本文件覆盖 7 个钩子本身 |
| 2 | `tests/test_client_sdk_adapter.py` | 覆盖 `_adapt_request` 汇合点与 `BaseAIService`/client_sdk 协作 |
| 3 | `tests/test_react_cycle_split_regression.py` | react 单步主链回归 |
| 4 | `tests/test_fc_fallback.py` | FC 降级链路，确保适配层改动不影响降级 |
| 5 | `tests/test_llm_retry_visibility.py` | L1/L2 重试可见性 |

执行命令：

```
pytest tests/test_adapters.py tests/test_client_sdk_adapter.py tests/test_react_cycle_split_regression.py tests/test_fc_fallback.py tests/test_llm_retry_visibility.py -q
```

**功能验收**：zen 真实摘要跑通，产出非空、六段格式命中。

---

**变更历史**:
- v1.0 (2026-10-09 22:50 小欧) 按北京老陈四条裁定重写：① 方法名 `callTextForTask`（provider 中立）；② 详解多态分发（provider 区分不在函数内）；③ SRP 按10 大规范处理 —— 补全 `base.py` 模块声明的职责边界；④ 删 `**kw`（YAGNI）；⑤ 验收项点명 5 个可执行文件；⑥ 用例 12 改为可执行形态。
- 备注：本文档上一版本因用 PowerShell 批量替换导致 UTF-8 编码损坏（AGENTS.md 明令禁止该操作），已重写。