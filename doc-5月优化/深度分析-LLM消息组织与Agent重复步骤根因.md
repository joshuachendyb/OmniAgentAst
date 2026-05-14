# 深度分析 - LLM消息组织与Agent重复步骤根因

**创建时间**: 2026-05-14 09:57:22
**分析人**: 小健
**数据来源**: 
- `prompt_52+20260514_092540.json` — 系统Prompt日志
- `execution_steps_2026-5-14T09-33-22.json` — 前端导出执行步骤
- `base_react.py` — Agent核心循环
- `react_agent_mixin.py` — LLM消息组装

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-14 09:57:22 | 小健 | 初始版本 |

---

## 一、问题总览

一个查"WIFI的IP DNS和公网IP"的简单任务（需要3步：ipconfig + http_request查公网IP + 整理回答），实际执行了**56步、29轮LLM调用**，其中大量重复。

### 1.1 数据驱动的问题发现

| 度量 | 实际值 | 合理值 | 浪费倍数 |
|------|--------|--------|---------|
| LLM调用轮数 | 29轮 | 2-3轮 | **10倍** |
| 总执行步骤 | 56步 | 5-7步 | **8倍** |
| ipconfig /all执行次数 | 8次 | 1次 | **8倍** |
| api.ipify.org请求次数 | 6次 | 1次 | **6倍** |
| 总耗时 | ~240秒 | ~30秒 | **8倍** |
| 上下文浪费 | ~88%被工具列表占用 | 应≤20% | **4倍** |

### 1.2 从数据看证据

**证据1：ipconfig /all重复8次，内容完全一致（2574字符）**

在prompt log的"Prompt组装过程"中，ipconfig的输出出现了8次：
| 序号 | 时间戳 | 长度 | 来源 |
|------|--------|------|------|
| 1 | 09:26:11 | 2574 | Round 1主工具 |
| 2 | 09:27:19 | 2574 | Round 2 pending call |
| 3 | 09:27:25 | 2574 | Round 3独立调用 |
| 4 | 09:27:56 | 2574 | Round 4 pending call |
| 5 | 09:28:25 | 2574 | Round 6 pending call |
| 6 | 09:28:42 | 2574 | Round 7独立调用 |
| 7 | 09:42:? | 2574 | ... |
| 8 | 09:?:? | 2574 | ... |

每次输出的stdout完全一样（同一台机器、同一命令）。

**证据2：http_request到同一URL失败6次，错误信息完全相同**

`https://api.ipify.org?format=json` — 同样的URL、同样的错误信息"网络请求失败（重试3次后）"，反复执行6次（每次耗时~9秒）。

**证据3：每次LLM调用，工具列表(53K)重复注入，占比85-93%**

| LLM轮次 | 总消息大小 | 工具列表 | 工具列表占比 |
|---------|-----------|---------|------------|
| Round 1 | 57K | 53K | **93%** |
| Round 2 | 60K | 53K | **88%** |
| Round 3 | 63K | 53K | **84%** |
| Round 29 | ~100K | 53K | **53%** |

---

## 二、逐层根因分析

### 第一层：表象问题（从数据直接可见）

#### 问题1：工具列表53K每轮注入 — 全部12分类60+工具

**数据证据**：prompt log Round 2的消息摘要显示：
```
序号1: role=system, 长度=3489  (sys_prompt)
序号2: role=user, 长度=595     (task)
序号3: role=assistant, 长度=319 (LLM回复)
序号4: role=system, 长度=2574   (ipconfig observation)
序号5: role=system, 长度=53080  (工具列表!!!! 53K)
序号6: role=user, 长度=35       (error observation)
```

**代码定位**：`react_agent_mixin.py:282-284`
```python
try:
    tools_summary = self._get_tools_summary()
    summary_msg = {"role": "system", "content": f"【当前可用工具列表】\n{tools_summary}"}
    history_dicts = list(history_dicts) + [summary_msg]
```

`_get_tools_summary()` 调用 `get_all_tools_summary()`（registry.py:460-533），遍历12个分类的全部60+工具，对每个工具输出description。NetworkAgent只需要6个网络工具，但其他54个工具的description也被完整输出了。

**直接影响**：每轮LLM调用的消息中，53K/60K=88%内容是无用的工具列表。LLM的注意力被严重稀释，无法有效关注历史observation。

#### 问题2：observation无去重 — 相同结果重复追加

**数据证据**：8次ipconfig /all，每次2574字符完全相同的stdout，都被`_add_observation_to_history()`追加到conversation_history中。

**代码定位**：`base_react.py:1159-1190`
```python
def _add_observation_to_history(self, observation: str) -> None:
    ...
    self.conversation_history.append({"role": "system", "content": observation})
    self._trim_history()
```

没有任何去重检查。相同内容的observation被重复追加8次，每次2574字符。

#### 问题3：error消息丢失具体原因 — LLM不知道为何失败

**数据证据**：`Observation: error - 网络请求失败（重试3次后）：`
没有URL、没有异常类型（timeout/DNS/connection refused）、没有异常详情。

**代码定位**：`base_react.py:832-838`
```python
else:
    observation_text = f"Observation: {exec_status} - {execution_result.get('summary', '')}"
```

`summary` 只包含"网络请求失败（重试3次后）"，execution_result的data中可能包含具体异常信息，但这里的observation_text没有提取。

#### 问题4：error observation不含URL

**数据证据**：LLM看到"网络请求失败"，但不知道是哪个URL、什么方法、什么参数。在Round 2消息列表中，第6条消息仅35字符：
`Observation: error - 网络请求失败（重试3次后）：`

URL和方法信息都在LLM自己的assistant回复中（第3条），但assistant回复只有319字符，且LLM需要自行关联。

---

### 第二层：结构性缺陷（代码层面）

#### 缺陷5：conversation_history[-1]角色翻转(system→user)

**代码路径**：`react_agent_mixin.py:272-273 + 327`
```python
last_message = self.conversation_history[-1]["content"]     # 取system角色的observation
history_dicts = self.conversation_history[:-1]
...
assembled_messages = list(history_dicts) + [{"role": "user", "content": last_message}]  # 强行改为user!
```

observation原本是`role="system"`，但被取content后重新包装成`role="user"`发给LLM。

**实际效果**：LLM Round 2的第6条消息：
```
role: "user"
content: "Observation: error - 网络请求失败（重试3次后）："
```

LLM收到一条"user"消息，内容是"网络请求失败"——语义混乱。LLM可能理解为"用户反馈说请求失败了"而非"工具执行的结果失败了"。

#### 缺陷6：pending_calls导致observation/assistant数量不对称

**代码路径**：`base_react.py:798, 857, 927-958`

主工具执行后：
```
第798行: conversation_history.append({"role": "assistant", "content": response})  ← +1 assistant
第857行: _add_observation_to_history(observation_text)                           ← +1 observation
```

pending_calls循环（第927-958行）：
```
第958行: _add_observation_to_history(...)  ← +1 observation（没有对应的assistant！）
```

**数据证据**：Round 2执行后有1个pending call，conversation_history变为：
```
[system, user, asst(R1), obs(R1_ipconfig), asst(R2), obs(R2_http_error), obs(R2_ipconfig_pending)]
```
3条assistant + 4条observation。assistant比observation少1条。

**直接影响**：下一轮LLM看到连续两条system角色observation（http_error后紧跟ipconfig），但没有对应的assistant消息说明"LLM决定在http_request失败后执行ipconfig"。LLM看不懂observation之间的关系。

#### 缺陷7：_trim_history不会裁剪pending_calls导致的连续observation

**代码定位**：`base_react.py:1026-1091`

_trim_history保留`role == "assistant"`或`content.startswith("Observation:")`的消息。当有pending_calls时，连续多条observation都被保留（每条2.5K），因为没有对应的assistant消息来打断。

---

### 第三层：系统性设计缺陷（架构层面）

#### 缺陷8：没有"已执行工具汇总"机制

系统没有任何机制告诉LLM"你已经执行过哪些工具、结果如何"。LLM必须从历史消息中自己回忆。

当_trim_history裁剪了中间observation后（第6轮之后），LLM可能完全忘记"我已经查过ipconfig了"，于是重新执行。

**缺少的设计**：
- 没有执行摘要（如`已执行工具: ipconfig→成功(含IP/DNS), nslookup→成功(公网IPv6)`）
- 没有去重提示（如`注意: ipconfig /all已在第1轮执行过，结果不变`）
- 没有失败抑制（如`注意: http_request到api.ipify.org已连续失败3次，建议换URL`）

#### 缺陷9：strategy_method值不匹配

**代码定位**：`strategy_selector.py:58-62` vs `react_agent_mixin.py:346`

strategy_selector返回`method="prompt"`，但react_agent_mixin.py检查的是：
```python
if strategy_method == "text":              # "prompt" != "text" → 不匹配
elif strategy_method == "response_format":  # 匹配
elif strategy_method == "tools":            # 匹配
```

**直接影响**：当strategy_method="prompt"时，schema注入分支跳过，最终兜底到text_strategy。prompt模式下LLM缺少工具参数参考。

#### 缺陷10：_build_alternative_tools_hint的替代建议南辕北辙

**代码定位**：`base_react.py:986-1024`

当http_request失败时，推荐的替代工具是：`download_file`、`fetch_webpage`、`search_web`。但这些工具都不能获取公网IP。

LLM被引导去尝试fetch_webpage到api.ipify.org（也失败），然后回到http_request——死循环。

**正确做法**：替代建议应该是"换一个URL"而非"换一种工具"。

#### 缺陷11：没有"同一工具连续失败"的抑制机制

系统没有任何计数器跟踪工具连续失败次数。LLM Round 2失败后，Round 3又调用同样的URL，Round 4再调用——6次全部失败。

---

## 三、问题关联图

```
工具列表53K每轮注入(缺陷1)
    ↓
LLM上下文窗口被浪费85-93%
    ↓
LLM无法有效阅读历史observation
    ↓ (叠加缺陷2: 不提供"已执行汇总")
LLM忘记已执行过ipconfig /all
    ↓ (叠加缺陷6: pending_calls造成历史断裂)
LLM看不懂连续observation的关系
    ↓
LLM重复执行ipconfig（第1次已有全部数据）
LLM重复调用api.ipify.org（不记得已失败过）
    ↓ (叠加缺陷5: 错误消息没URL没原因)
LLM不知道为什么失败，怀疑是临时故障
    ↓
继续重试同一URL，死循环
    ↓ (叠加缺陷10: 替代建议不靠谱)
尝试fetch_webpage同样失败，回到http_request
    ↓
最终: 56步/29轮LLM调用，8倍浪费
```

---

## 四、优化方向建议

### P0-必须修复（直接影响核心效率）

| # | 问题 | 优化方向 | 预期效果 |
|---|------|---------|---------|
| 1 | 工具列表53K每轮注入 | `get_all_tools_summary`加`category_filter`，只显示当前分类工具 | 53K→~3K，节省94% |
| 2 | observation去重 | `_add_observation_to_history`检查与上一条是否相同 | 消除重复ipconfig |
| 3 | 工具列表合并到system prompt | 在`_build_system_prompt`中一次注入，不再每轮追加独立消息 | 每轮省53K |

### P1-重要修复

| # | 问题 | 优化方向 | 预期效果 |
|---|------|---------|---------|
| 4 | error消息缺URL和原因 | observation_text追加URL+异常类型+异常详情 | LLM知道为何失败 |
| 5 | 失败工具抑制 | 跟踪工具连续失败次数，≥3次追加系统警告 | 避免死循环重试 |
| 6 | 替代建议改进 | 对http_request失败，建议不同URL，而非不同工具 | 引导到正确方向 |

### P2-结构性优化

| # | 问题 | 优化方向 | 预期效果 |
|---|------|---------|---------|
| 7 | pending_calls缺assistant | 每个pending call前追加一条简短的assistant消息 | 历史语义完整 |
| 8 | 角色翻转(system→user) | observation作为单独字段传入，不与user角色混用 | 语义清晰 |
| 9 | strategy_method匹配 | "prompt"→"text"映射修复 | schema正确注入 |
| 10 | 已执行工具汇总 | 每轮注入"已执行工具汇总"列表 | LLM知道自己做过什么 |

---

## 五、预估效果

仅修复P0(问题1+2+3)后：

| 度量 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| 每轮LLM消息大小 | 57K-100K | 7K-50K | **减少50-93%** |
| ipconfig重复次数 | 8次 | 1次 | **减少87%** |
| api.ipify.org重试次数 | 6次 | 1-2次 | **减少67-83%** |
| 总LLM调用轮数 | 29轮 | 2-5轮 | **减少83-93%** |
| 总执行时间 | ~240秒 | ~30-60秒 | **减少75-87%** |

---

**更新时间**: 2026-05-14 09:57:22
