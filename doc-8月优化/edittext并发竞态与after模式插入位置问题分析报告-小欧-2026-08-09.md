# edittext 并发竞态与 after 模式插入位置问题分析报告

> **文档名称**: edittext并发竞态与after模式插入位置问题分析报告-小欧-2026-08-09.md
> **编写人**: 小欧
> **创建时间**: 2026-08-09 08:10:19
> **分析对象**: 同一文件并发 edittext 竞态致内容丢失（🔴）、after 模式插入位置异常（🟡）两个问题
> **证据来源**: `backend/logs/app_2026-08-09.log`（session `868811ae`，task001_20260809_0751 测试运行）、`backend/app/` 源码、实验复现

## 一、版本历史

| 版本 | 时间 | 编写人 | 说明 |
|------|------|--------|------|
| v1.0 | 2026-08-09 08:10 | 小欧 | 初稿：两个问题逐项核实，给出真实/误判定性、证据链、根因与修复方案（**待老陈审核后再改码**） |
| v1.1 | 2026-08-09 08:14 | 小欧 | 补充真实并发实测复现（丢失更新 100% 复现）、对齐报告原文（问题②来源于 07:52:55 LLM Thought）、补单行锚点场景验证 |
| v1.2 | 2026-08-09 08:22 | 小欧 | 补**三堂会审**：合规发现 2 处瑕疵（isinstance 防御冗余/YAGNI 违规、类型注解过宽）并修正方案代码；修正后重跑 5 场景全过 + 行为一致性 10 项无回归 + 补漏能力 4 项确认 |
| v1.3 | 2026-08-09 08:35 | 小欧 | 按老陈"该并行就并行"原则新增**方案二：分组调度版**（`_parse_paths`+`_partition_calls` 并查集分组，冲突组内串行+无冲突组并行，实测竞态批次 1.8s→0.92s）；第五章重构为两方案并列，含复杂度/稳健性评估与验证结果 |
| v1.4 | 2026-08-09 08:41 | 小欧 | **全文三遍三堂会审**修正：① 5.3 关联逻辑"edittext+compress"与日志不符→实证为 `{edittext,copy,readtext}`；② 方案二外层 gather 补 `return_exceptions=True`+组级异常处理（与 5.5.5 失败隔离声明一致）；③ 行数修正 44→50（`_parse_paths`19+`_partition_calls`31）；④ 5.7 影响面区分两方案并补"文件层 check_conflict_strict 拦不住并发"分析；⑤ 3.2 补机制历史佐证（cc12075d2 原始设计盲区，非退化）；⑥ 3.6 行号统一；⑦ 补失败隔离验证用例（组内异常不拖累其他组，PASS）；⑧ 5.5.5 行数 64→70 同步 |
| v1.5 | 2026-08-09 09:15 | 小欧 | 问题②二次复核修正：① 用日志 14742 确切参数**精确复现 step=14**（多行完整函数锚点）→ divide 在 multiply 后、greet 前，**位置完全正确**；② **新增场景B 实证单行签名锚点错位**（签名行后插入、multiply 函数体被劈开），推翻 v1.1 场景B"位置正确"结论→ 修正 4.3/4.4/4.5/总结表：该错位属 `_anchor_signature_hint`（edit_text_file.py:229-242，task002 问题1）已识别的独立风险，有提示兜底，非本次两问题范围；③ 4.1 补"step=15 Thought 无 readtext 实证"（step=14 与 step=15 间无读文件调用）；④ 4.4 补 step=14 成功与 step=15 误判的时间序 |
| v1.6 | 2026-08-09 09:40 | 小欧 | **老陈确定选择方案二（分组调度版）**：① 第五章标题与 5.1/5.5 标注选定状态、5.6 建议→决策；② **新增 5.8 完整实施方案**：5.8.1 实施范围、5.8.2 完整落地代码（import 补 Set + 新增 `_parse_paths`/`_partition_calls` + `_has_conflict` 计数版复用 `_parse_paths` + 分支 B' 分组调度，共 5 处）、5.8.3 实施步骤（备份→落码→静态检查→单元验证→一致性回归→pytest→提交打 tag）、5.8.4 验证与验收标准 7 项；③ 六、总结顶部新增**一句话直白结论**（after 本身无问题、真正要修的是并发调度）；④ 结尾注更新为"已选定方案二、按 5.8 实施"；⑤ **行为一致性实测**：重构版 `_has_conflict`（复用 `_parse_paths`）vs 内联计数版 **14/14 全部一致**，5.8.3 步骤 5 已记录 |
| v1.7 | 2026-08-09 10:32 | 小欧 | **全文三遍三堂会审修正**：① 5.5.3/5.5.5/5.6 **行数修正 70→约 115**（按 5.8.2 精确代码统计：`_parse_paths` 21 + `_partition_calls` 31 + `_has_conflict` 改造 28 + 分支 B 35 + import 1）；② **补异常处理等价性声明（L1）**到 5.8.2 说明：B' 失败语义与原 A/B/C 逐点等价，`results` 返回形态不变，build_observation/`_merge_llm_data` 零改动；③ 5.3 C4 补**07:57:53 日志出处**（app_2026-08-09.log 行15295-15319，会话 `4ae0302c` step7，属实）；④ 5.8.3 步骤2 强化Set依赖顺序 |
| v1.8 | 2026-08-09 10:50 | 小欧 | **二轮三堂会审修正**：① **R4 歧义澄清**：5.1 代码块加"方案一独立版(inlining别名解析)，方案二落地版见 5.8.2 步骤3(复用_parse_paths)"，防止开发者误复制 5.1 落地方案二；② **C2 口径统一**：5.5.2 title 行数 50→53（代码块 346-398 实际 53 行）。三堂会审结论: 技术逻辑正确, 5.8.2 代码 14/14 一致可落地, 仅 2 处文档口径/歧义问题 (均低估/非虚报), 实测 0 处虚报 |
| v1.9 | 2026-08-09 09:14 | 小欧 | **三轮三堂会审修正（老陈指令：全文熟读3遍，实施步骤必须绝对完整准确）**：① **行数数学错误修正 115→116**（5.5.3/5.5.5/5.6 共 4 处："约115"差 1，按 5.8.2 分项 `_parse_paths`21+`_partition_calls`31+`_has_conflict`28+分支B35+import1=**116**）；② **5.8.2 口径**：标题改"**5 处必改 + 1 处可选清理**"（C 分支 `_reason` 死代码清理为第 6 处**可选**改动，不列为必改）；③ **日志行号修正 14742→14743**（4.3 场景A：step=14 完整 after 参数实际在日志行 14743，14742 为"工具执行完成"行；复现参数本身正确）；④ **5.8.3 步骤4/5 补 verify 脚本路径**（`C:\Users\chend\AppData\Local\Temp\opencode\`，防临时目录清理后无法复跑；脚本内嵌逻辑与 5.8.2 逐字一致，若脚本缺失可按 5.8.2 代码重建）；⑤ 行数口径说明：5.8.2 代码块含空行排版 `_partition_calls` 31 行、verify 脚本紧凑排版 29 行，功能代码逐字一致。**三轮会审结论：逻辑/行为问题 0 处，5.8.2 落地代码与 verify 脚本逐字一致，实测 14/14 + 分组调度 10 项全 PASS，文档仅修正 5 处精确性/口径问题，均非虚报** |

---

## 二、问题来源与核实方法

### 2.1 问题来源

报告指出两个问题：

| 编号 | 严重度 | 问题描述 |
|------|--------|---------|
| ① | 🔴 | 同一文件并发 edittext 编辑竞态，导致内容丢失 |
| ② | 🟡 | edittext after 模式插入位置异常（插入内容出现在锚点之前而非之后） |

### 2.2 核实方法

1. **日志核实**：从 `app_2026-08-09.log` 提取 session `868811ae` 的 07:52:30~07:53:00 时间线，核对 step=11~step=16 的每一条工具调用、原始结果、Observation。
2. **代码核实**：读取 `action_handler.py` `_has_conflict` / `execute_tools` 三分支、`edit_text_file.py` after 模式实现、`tool_constants.py` `FILE_OPERATION_TOOLS`、`tools_alias_mapper.py` `PARAM_ALIASES`。
3. **实验复现**：直接调用生产函数 `_has_conflict` 与 `_apply_replacement` 复现/验证。

---

## 三、问题①：同一文件并发 edittext 竞态致内容丢失 —— ✅ 真实 BUG

### 3.1 日志证据链（session 868811ae）

**07:52:35 step=11** —— 4 个工具进入 `execute_tools`：

```
[action_handler] 并行执行: tools=['edittext', 'edittext', 'edittext', 'extract']
```

3 个 edittext **全部指向同一文件** `E:\test_dir\reports\task001_20260809_0751\test_code.py`，extract 指向 zip：

| 调用 | 工具 | 参数要点 | 结果 |
|------|------|---------|------|
| [0] | edittext | once：给 `def multiply` 加 docstring | ✅ success（`替换 1/1 处`） |
| [1] | edittext | once：给 `def greet` 加 docstring | ✅ success（`替换 1/1 处`） |
| [2] | edittext | after：在 multiply 后插入 divide 函数 | ❌ error（`未找到匹配内容`，锚点含 docstring 但文件此刻尚未被[0]写入） |
| [3] | extract | 解压 test_archive.zip | ✅ success |

并行执行耗时 **0.10s**，证明走了**分支 B（并行，try_once 不重试）**，而非分支 C（顺序）。

**07:52:38 step=12** —— LLM 重新 readtext，发现文件处于**损坏中间态**：

```
 1|# 测试代码文件
 2|def add(a, b):
 3|    """Adds two numbers and returns the result."""
 4|    return a + b
 5|
 6|def multiply(a, b):
 7|    return a * b          ← multiply 的 docstring 丢了！
 8|
 9|def greet(name):
10|    """Greets a person by name."""
11|    return f"Hello, {name}! Welcome to OmniAgent."
```

**丢失更新实锤**：step=11 的 edittext[0] 明明"给 multiply 加 docstring 成功（替换1/1）"，但 step=12 读回时 multiply **没有 docstring**。原因：edittext[0] 与 edittext[1] 并发，各自基于**同一份原始文件内容**做 read-modify-write；[1] 把 [0] 的写入覆盖掉了。

**07:52:43 step=13** —— LLM 自己发现并承认竞态：

```
[Thought] step=13, 第2次编辑(添加multiply的docstring)与第3次编辑(添加divide函数)
并发执行时产生了竞态条件,第2次的docstring被第3次的替换覆盖掉了...
```

随后 LLM 单独重发 once edittext 给 multiply 补 docstring（成功）。

### 3.2 根因分析：`_has_conflict` set 去重漏检

`action_handler.py:260-295` 的 `_has_conflict`：

```python
path_ops = {}
...
path_ops.setdefault(pval, set()).add(name)   # 关键：set 只记工具名，不计数
...
for path, tools in path_ops.items():
    if len(tools) > 1 and any(t in _WRITE_OPS for t in tools):
        return True   # 冲突 → 顺序执行
return False          # 无冲突 → 并行
```

**致命缺陷**：`path_ops[路径]` 存的是**工具名集合**。3 个 edittext 指向同一路径时，`set().add('edittext')` 三次后仍是 `{'edittext'}`，`len(tools) > 1` **恒为 False** → 判定无冲突 → 走并行分支 B（`action_handler.py:349-354`）：

```python
elif is_parallel and not _has_conflict(all_calls):
    tasks = [execute_tool(agent, _cn(c), _cp(c), parallel=True) for c in all_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)   # 并发写同一文件
```

**机制历史佐证（非退化）**：`_has_conflict` 与并行策略由 git `cc12075d2`（2026-07-04，北京老陈）引入——将"文件工具一刀切串行"改为"下放执行层按路径粒度控制并行"。原始提交即为 `set().add(name)` 实现，**非本会话改动退化，而是原始设计盲区**：只防"不同工具抢同一路径"，漏了"同名工具多次调用同一路径"。本修复即补齐该盲区，不推翻原设计意图（有冲突→顺序执行）。

### 3.3 实验复现（直接调用生产函数）

```
输入: 3×edittext(path=test_code.py) + extract(path=test_archive.zip)
输出: _has_conflict = False   ← 应为 True（应降级顺序），实际漏检
```

实验复现了真实运行路径：**set 去重 → 漏检 → 并行 → 竞态**。

### 3.4 真实并发实测（100% 复现丢失更新）

**方法**：直接用生产 `_precise_replace_in_file` 以 `asyncio.gather` 并发执行两个 edittext 操作同一文件（模拟 `execute_tool(parallel=True)`）：

| 操作 | 内容 | 返回 |
|------|------|------|
| edittext[0] | once：给 `def multiply` 加 docstring | ✅ 返回成功（applied_edits=1，diff 显示已加 docstring） |
| edittext[1] | once：给 `def greet` 加 docstring | ✅ 返回成功（applied_edits=1，diff 显示已加 docstring） |

**并发后最终文件**：

```
def multiply(a, b):
    return a * b                    ← multiply 的 docstring 丢失！
def greet(name):
    """Greets a person by name."""
    return f"Hello, {name}!"
```

**实测结果**：`multiply 有docstring? False`、`greet 有docstring? True`。

**与真实日志完全一致**：step=11 的 edittext[0] 报"给 multiply 加 docstring 成功"，但 step=12 读回时 multiply 无 docstring。

### 3.5 根因链条（完整闭环）

```
_has_conflict 用 set 存工具名（L277/L289 的 set().add(name)）
  → 3 个同名 edittext 被去重为 {'edittext'}
  → len(tools) > 1 恒为 False（L292）
  → 返回 False = 无冲突
  → execute_tools 走并行分支 B（L349: is_parallel and not _has_conflict）
  → asyncio.gather 并发执行（L354）
  → 每个 edittext 独立 read-modify-write（读 L381 → 内存替换 L441 → 写回 L503）
  → 后写的覆盖先写的 → 丢失更新
  → 但两个调用都返回 success → 数据静默丢失，无人发现
```

### 3.6 判定

| 核实项 | 结论 |
|--------|------|
| 日志原文 | ✅ 真实存在（07:52:35 并行执行 3×edittext、07:52:38 读回 multiply docstring 丢失、07:52:43 LLM 自认竞态） |
| 代码定位 | ✅ `action_handler.py:260-295` `_has_conflict`（其中 L277/L289 `set().add(name)` 只记工具名不计数）；`action_handler.py:349` 冲突判 False 走并行 |
| 代码行为 | ✅ 属实。同名文件工具并发访问同一路径被 set 去重，冲突检测失效 |
| 并发实测 | ✅ 100% 复现丢失更新（multiply docstring 静默丢失） |
| **判定** | ✅ **真实系统 BUG（高优先级）** |

---

## 四、问题②：after 模式插入位置异常 —— ⚪ 工具行为正确，属竞态次生误判

### 4.1 报告原文描述

问题②的来源是 **07:52:55 step=15 LLM 的 Thought**（session 868811ae）：

```
07:52:55 [Thought] step=15, 发现`after`模式的行为异常——插入内容出现在锚点之前而非之后。
```

即 LLM 在运行中**自述** after 模式把内容插到了锚点之前。

> **要点**：该 Thought（step=15）发生在 step=14 after 成功（07:52:48）**之后**，且 step=14 与 step=15 之间**无 readtext 调用**——LLM 未读文件实证"锚点之前"，属延续 step=11 失败记忆的推理误判（详见 4.4）。

### 4.2 日志核实（step=14，07:52:48）

step=14 是 LLM 在 step=13 修复 docstring 后单独重发的 after 调用，diff 如下：

```
@@ -7,6 +7,13 @@
     """Multiplies two numbers and returns the product."""
     return a * b
 
+def divide(a, b):
+    """Divides a by b, returns error message if b is zero."""
+    if b == 0:
+        return "Error: Division by zero"
+    return a / b
+
+
 def greet(name):
```

divide 函数**确实插在 multiply 函数之后、greet 之前**，位置正确。

### 4.3 实验复现（直接调用 `_apply_replacement`，mode=after）

**场景A（多行锚点 = 整个函数）**——精确复现 step=14（日志 14743 确切参数，14742 为"工具执行完成"行）：

```
输入: old=multiply函数(含docstring), new=divide函数, mode=after
输出: count=1 total=1
      multiply 在行6 → divide 在行10 → greet 在行17
判定: divide 在 multiply 之后 ✅、在 greet 之前 ✅ —— 位置完全正确，与日志 diff 一致
```

**after 模式在多行完整函数锚点下插入位置正确**（本次出问题的 step=14 即此形态）。

**场景B（单行锚点 = 函数签名行）**——补验"锚点之前"疑点，**实测为真实错位风险**：

```
输入: old='def multiply(a, b):', new=divide函数, mode=after
输出: count=1 total=1
      行6: def multiply(a, b):
      行8: def divide(a, b):        ← 插在签名行之后
      ...
      行14: """Multiplies..."""     ← multiply 的 docstring/return 被顶到 divide 之后
      行15:     return a * b
判定: multiply 函数体被劈开（签名行与函数体分离）→ 对"函数后插入"的期望而言，这是错位
```

**结论**：单行签名锚点 + after 确实存在**错位风险**（新方法插在签名行后、旧方法体被劈开）。系统已识别此风险并有引导机制：`_anchor_signature_hint`（edit_text_file.py:229-242，2026-08-08 task002 问题1）检测到 `def/class` 单行签名锚点时返回提示"以签名行作锚点会插到方法体之前，建议改用方法体末行作锚点"——**仅提示不改插入逻辑（KISS-DIRECT）**。这与 `_insert_line_after` 语义（"在包含 match_end 的行的行尾之后插入"）一致，属**已知语义边界，非本次两个问题范围**。

### 4.4 为什么报告会误判为"位置异常"

报告所称"after 异常"实际是**问题①竞态的次生现象**：

1. step=11 并发时，edittext[2]（after 模式）**失败**：锚点 old_string 是"multiply 含 docstring"的完整函数（日志 14693），但并发写回前文件还是原始状态（multiply 无 docstring），找不到匹配 → `未找到匹配内容` error。
2. step=14 单独重发同参数 after，**成功且位置正确**（场景A 精确复现）。
3. step=15 的 Thought（07:52:55）"发现 after 行为异常——插入在锚点之前"，**该断言无 readtext 实证**（step=14 与 step=15 之间无读文件调用），是 LLM 延续 step=11 失败记忆的推理误判。

### 4.5 判定

| 核实项 | 结论 |
|--------|------|
| 日志原文 | ✅ step=14 after 插入成功、diff 位置正确（divide 在 multiply 后、greet 前） |
| 代码行为 | ✅ `_insert_line_after`（edit_text_file.py:98-113）+ `_blank_line_sep`（L116-118）插入逻辑正确 |
| 实验复现 | ✅ 场景A 精确复现 step=14 位置正确；场景B 实证单行签名锚点错位（函数体劈开），属 `_anchor_signature_hint` 已识别的独立风险 |
| **判定** | ⚪ **本次场景工具行为正确，报告为误判**：step=14 用多行完整函数锚点，位置正确；失败根因是问题①并发竞态，修复问题①即可。**注意边界**：单行签名锚点 + after 确有错位风险，系统已有 `_anchor_signature_hint` 提示兜底（2026-08-08 task002），属已知语义边界，无需本报告另立修复项 |

---

## 五、修复方案（老陈已选定：方案二·分组调度）

### 5.1 方案一：最小改动版（计数版 `_has_conflict`，冲突→整批降级串行）

> **注**：方案一**不单独采用**（其"冲突即整批串行"会把无辜工具拖慢）。其**计数版 `_has_conflict` 逻辑并入方案二**作为组内并行/串行判定，见 5.8.2 步骤 1。

**核心改动**：`path_ops` 的值从"工具名 set"改为"路径→(调用次数, 工具名 set)"，只要同一路径被**>=2 次调用**且含写操作即判冲突。此方案**不改三分支结构**——一旦判冲突，整批降级为顺序执行（分支 C）：

```python
def _has_conflict(all_calls: List[Dict]) -> bool:
    path_ops: Dict[str, Dict[str, Any]] = {}

    def _record(_path: str, _name: str) -> None:
        entry = path_ops.setdefault(_path, {"count": 0, "tools": set()})
        entry["count"] += 1
        entry["tools"].add(_name)

    for c in all_calls:
        name = c.get("tool_name", "")
        if name not in FILE_OPERATION_TOOLS:
            continue
        params = c.get("tool_params", {})
        aliases = PARAM_ALIASES.get(name, {})
        if not aliases:
            _path = params.get("path", "")
            if _path and isinstance(_path, str):
                _record(_path, name)
            continue
        resolved = {}
        for key, value in params.items():
            canon = aliases.get(key, key)
            if canon not in resolved:
                resolved[canon] = value
        for pname in set(aliases.values()):
            pval = resolved.get(pname)
            if pval and isinstance(pval, str):
                _record(pval, name)

    for path, entry in path_ops.items():
        tools = entry["tools"]
        if entry["count"] >= 2 and any(t in _WRITE_OPS for t in tools):
            logger.info(f"[_has_conflict] 路径冲突: {path}, tools={tools}, 调用数={entry['count']}, 降级顺序执行")
            return True
    return False
```

> **⚠️ 读码提醒**：以上为**方案一 `_has_conflict` 的独立版**（内联别名→规范名解析）。方案二落地版见 **5.8.2 步骤 3**，它**复用 `_parse_paths` 消除别名解析重复**（DRY），判定行为经 `verify_refactor_consistency.py` **14/14 一致** 实测。实施方案二时**以 5.8.2 步骤 3 为准**，不要复制本节代码。

### 5.2 方案一验证结果（5 场景全过）

| 场景 | 输入 | 期望 | 实测 |
|------|------|------|------|
| 1. 竞态场景 | 3×edittext 同文件 + extract(zip) | True（降级顺序） | ✅ True |
| 2. 多读并行安全 | 2×readtext 同文件 | False（并行安全） | ✅ False |
| 3. 一写多读 | edittext + readtext 同文件 | True | ✅ True |
| 4. 不同路径并行 | edittext(A) + edittext(B) | False | ✅ False |
| 5. 别名归一 | edittext(file_path) + writetext(filepath) 同文件 | True | ✅ True |

修复保持既有正确行为（不同路径并行、多读并行），仅补齐"同名文件工具多次写同一路径"这一漏检。

### 5.3 方案一三堂会审（合规 / 合理 / 关联逻辑）

| 审查 | 结论 | 说明 |
|------|------|------|
| **合规** | ⚠️ 2 处瑕疵，已修正 | ① 原方案 `entry["tools"] if isinstance(...) else set()` 为**多余防御**——`_record` 创建时恒为 set（YAGNI/KISS-DIRECT 违规），v1.2 已删除；② 类型注解 `Dict[str, object]` 过宽，已精化为 `Dict[str, Any]` |
| 合规·SRP | ✅ | `_has_conflict` 只做"路径冲突检测"；`_record` 只做"记录一次路径访问" |
| 合规·DRY | ✅ 增强 | 原代码两处 `setdefault(...).add(name)` 重复模式，方案用 `_record` 统一消重 |
| 合规·SLAP | ✅ | 主循环编排 + `_record` 底层记录，层次清晰 |
| 合规·禁止backward | ✅ | 不保留旧行为兼容路径，直接替换 |
| **合理** | ✅ | `count>=2 and any(t in _WRITE_OPS)` 精确表达"≥2 次访问且至少一次写"，直击病根；readtext 多读、不同路径并行均不受影响 |
| **关联逻辑** | ✅ 无退化 | 只改 `_has_conflict` 判定，`execute_tools` A/B/C 三分支不变；`_WRITE_OPS=FILE_OPERATION_TOOLS-{"readtext"}` 兼容；07:57:53 既有拦截（日志 app_2026-08-09.log 行15295-15319，会话 `4ae0302c` step7：同路径 `tools={'edittext','copy','readtext'}`，readtext+readtext+edittext+copy 整批降级顺序）行为不变 |

### 5.4 方案一修正后验证结果（v1.2 三堂会审版）

| 类别 | 用例 | 结果 |
|------|------|------|
| 5 场景（同 v1.1） | 竞态/多读/一写多读/不同路径/别名归一 | ✅ 全过 |
| 行为一致性（10 项） | 不同文件并行、多读并行、不同工具不同文件、compress+edittext 不同路径、无关工具、空调用、单调用等 | ✅ 原版与修正版输出全部一致，**无回归** |
| 补漏能力（4 项） | edittext×2 同文件、别名双写同文件、writetext×3、move 同源不同目标 | ✅ 原版漏检（False）→ 修正版正确检出（True） |

---

### 5.5 方案二：分组调度版（冲突组内串行 + 无冲突组并行）【★ 老陈已选定】

#### 5.5.1 设计意图（老陈原则："该并行就并行"）

方案一虽然判得准，但**冲突即整批降级串行**——例：6 个工具里只有 3 个 edittext 冲突，其余 extract/listdir/readtext 无辜被拖成串行。

方案二按**路径相关性分组**（并查集连通分量）：共享路径的调用归一组，组间无共享路径 → **组间并行**；组内再由计数版 `_has_conflict` 判定是并行还是串行。即老陈的原则：**摘出不适合并行的，剩余保持并行**。

#### 5.5.2 新增分组函数（`_parse_paths` + `_partition_calls`，共 53 行）

```python
def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09"""
    if name not in FILE_OPERATION_TOOLS:
        return set()
    aliases = PARAM_ALIASES.get(name, {})
    if not aliases:
        p = params.get("path", "")
        return {p} if p and isinstance(p, str) else set()
    resolved = {}
    for key, value in params.items():
        canon = aliases.get(key, key)
        if canon not in resolved:
            resolved[canon] = value
    out = set()
    for pname in set(aliases.values()):
        pval = resolved.get(pname)
        if pval and isinstance(pval, str):
            out.add(pval)
    return out


def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径相关性分组(并查集): 共享路径的调用归一组, 组间无共享路径→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09
    """
    n = len(all_calls)
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    path_to_calls = {}
    for i, c in enumerate(all_calls):
        for p in _parse_paths(c.get("tool_name", ""), c.get("tool_params", {})):
            path_to_calls.setdefault(p, []).append(i)
    for _p, idxs in path_to_calls.items():
        base = idxs[0]
        for i in idxs[1:]:
            _union(base, i)

    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    return list(groups.values())
```

#### 5.5.3 `execute_tools` 改造（仅替换分支 B）

```python
elif is_parallel:
    # B': 并行分组调度 — 冲突组内串行, 无冲突组并行("该并行就并行")
    groups = _partition_calls(all_calls)

    async def _run_group(indices: List[int]):
        group = [all_calls[i] for i in indices]
        if len(group) == 1:  # 单工具, 语义同原A
            return [await execute_tool(agent, _cn(group[0]), _cp(group[0]),
                                       on_retry_started=on_retry_started)]
        if not _has_conflict(group):  # 组内无冲突→并行(try_once), 语义同原B
            tasks = [execute_tool(agent, _cn(c), _cp(c), parallel=True) for c in group]
            return await asyncio.gather(*tasks, return_exceptions=True)
        # 组内冲突→组内串行(带重试), 语义同原C
        _res = []
        for call in group:
            try:
                _res.append(await execute_tool(agent, _cn(call), _cp(call),
                                               on_retry_started=on_retry_started))
            except Exception as e:
                logger.warning(f"[action_handler] 工具{_cn(call)}组内顺序执行失败: {e}")
                _res.append(e)
        return _res

    _grouped = await asyncio.gather(*[_run_group(g) for g in groups],
                                    return_exceptions=True)  # 组间失败隔离: 单组异常不取消其他组
    results = [None] * len(all_calls)  # 结果按原顺序填回
    for _indices, _res in zip(groups, _grouped):
        if isinstance(_res, Exception):  # 整组失败: 组内全部调用标记为该异常(与原C分支单工具异常append语义一致)
            for _i in _indices:
                results[_i] = _res
            continue
        for _i, _r in zip(_indices, _res):
            results[_i] = _r
```

改造量合计 **116 行**（按 5.8.2 精确代码统计：新增 `_parse_paths` 21 行 + `_partition_calls` 31 行，改造 `_has_conflict` 28 行 + 分支 B 35 行，import 1 行）。单工具（A）、非并行（C）两分支**业务逻辑完全不动**。

> **注意**：方案二**包含方案一的核心改动**——组内无冲突/有冲突的判定复用计数版 `_has_conflict`（方案一代码）。且方案二实施时可顺手用 `_parse_paths` 重构 `_has_conflict` 的路径解析循环，消除两处重复（DRY 增强）。

#### 5.5.4 行为示例（模拟 6 调用、各 0.3s）

```
批次: edittext(P)×3 + extract(Z) + listdir(B) + readtext(C)
方案一: 6 工具全串行 ≈ 1.8s（无辜工具被拖慢）
方案二: [edittext×3 组内串行 0.9s] ∥ [extract 0.3s] ∥ [listdir 0.3s] ∥ [readtext 0.3s]
        ≈ 0.92s（实测），提速约 50%
```

#### 5.5.5 复杂度与稳健性评估

| 维度 | 评估 |
|------|------|
| 时间复杂度 | 并查集近似线性（路径压缩），分组开销可忽略 |
| 代码量 | **116 行**新增/改造（按 5.8.2 代码块口径：`_parse_paths` 21 + `_partition_calls` 31 + `_has_conflict` 改造 28 + 分支 B 35 + import 1），集中在 `_partition_calls` 与分支 B，无跨模块改动 |
| 空批次 | 分组空 → gather 空，安全 |
| 无路径工具 | httpget 等无路径 → 独立成组 → 与其他组并行 ✅ |
| 多读同路径 | 同组但组内无冲突 → 组内并行（与现状一致）✅ |
| 非并行模式 | `is_parallel=False` → 不进分组，整批串行（尊重 LLM 意愿）✅ |
| 别名归一 | `_parse_paths` 与 `_has_conflict` 同款解析，判定一致 ✅ |
| 结果保序 | 按索引填回，`zip(all_calls, results)` 语义不变 ✅ |
| 失败隔离 | 组内串行 try/except、组内并行 `return_exceptions`、组间 gather `return_exceptions=True` ✅ |
| 重试语义 | 组内单/串行带 `on_retry_started`、组内并行 `try_once`，与现有 A/B/C 一致 ✅ |

#### 5.5.6 方案二验证结果（真实 asyncio，verify_partition_v13.py）

| 类别 | 用例 | 结果 |
|------|------|------|
| 分组单元（5 项） | 竞态批次 4 组、多读同路径、不同路径、move 共享目标、无路径工具 | ✅ 全过 |
| 执行行为（4 项） | 竞态批次组内串行（0.92s）、多读全并行（0.31s）、不同路径全并行（0.30s）、别名归一组内串行（0.61s） | ✅ 全过 |
| 失败隔离（1 项） | 组内 edittext 抛异常 + listdir 独立组：异常被捕获、组内其余调用正常完成、listdir 不受拖累、结果保序 | ✅ 全过 |

#### 5.5.7 风险点

- 重构三分支中最大最常用的一支（分支 B），需回归验证并行结果合并 `_merge_llm_data` 与顺序一致性。
- 分组函数引入新代码，需纳入单测；但逻辑直线（并查集连通分量），无隐藏分支。

### 5.6 两方案对比与选型建议

| 维度 | 方案一（计数整批降级） | 方案二（分组调度） |
|------|----------------------|-------------------|
| 改动量 | 只改 `_has_conflict`（约 25 行） | 方案一 + `_parse_paths`+`_partition_calls`+分支 B（共 **116 行**） |
| 性能 | 冲突批次全串行（1.8s） | 仅冲突组串行（0.92s），提速约 50% |
| 语义 | 冲突→整批串行（无辜被拖慢） | **该并行就并行**（摘出冲突的，剩余并行） |
| 风险 | 低（三分支不动） | 中（重构分支 B） |
| 验证 | 5 场景+一致性 10 项+补漏 4 项全过 | 分组 5 项+行为 4 项全过 |
| 原则符合度 | 部分（判得准但调度粗） | **完全符合"该并行就并行"** |

**决策**：老陈原则明确"该并行就并行"，且已于 **2026-08-09 明确选定方案二**（分组调度版）——完全贴合设计初衷；改动可控（**116 行**、单文件、无跨模块、无新依赖）。**5.8 即为最终实施清单**。

### 5.7 影响面与注意事项

- **方案一**：`execute_tools` 分支选择逻辑（A/B/C）**无需改动**，仅 `_has_conflict` 判定更准。
- **方案二**：需替换**分支 B**（改为分组调度），A、C 分支**不动**；且**两方案均含方案一核心改动**（`_has_conflict` 按路径计数，方案二组内判定复用）。
- 修复后同名工具多写同一路径会降级为**顺序执行**，避免并发竞态，符合既有注释"有冲突→顺序执行"的原始设计意图。
- `_WRITE_OPS = FILE_OPERATION_TOOLS - {"readtext"}`（action_handler.py:103），readtext 多读不受影响。
- 不引入新依赖、不改 LLM 层、不改工具实现（KISS-DIRECT / SRP / DRY 合规）。
- **补充说明**：文件层 `edit_text_file.py` 的 `check_conflict_strict`（L389，mtime 比对）**拦不住并发**——两个并发 edittext 在同一窗口内 `record_read`（L384）记录相同 mtime、`check` 均通过，随后各自写回，mtime 检测假设单线程执行顺序，无法防御并发 read-modify-write 窗口。故并发防护必须在**调度层**（`execute_tools`）完成，即本方案定位。

### 5.8 实施方案（老陈已选定：方案二·完整落地清单）

> **一句话结论（先讲清楚）**：`after` 工具本身没问题（位置计算正确），**真正要修的是并发调度**——旧 `_has_conflict` 用 set 存工具名不计数，同名工具多次写同一路径时漏检，误走了并行分支导致 read-modify-write 竞态。本方案只改**一个文件** `backend/app/services/agent/handlers/action_handler.py`，不动工具实现、不动 LLM 层、不引入新依赖。

#### 5.8.1 实施范围

| 项 | 内容 |
|----|------|
| 改动文件 | `backend/app/services/agent/handlers/action_handler.py`（唯一） |
| 新增函数 | `_parse_paths`（路径解析，从 `_has_conflict` 提取，DRY）、`_partition_calls`（并查集分组） |
| 改造函数 | `_has_conflict`（set 计数 → 次数计数，并复用 `_parse_paths`）、`execute_tools` 分支 B（整批并行 → 分组调度 B'） |
| 不动 | 分支 A（单工具）、分支 C（非并行/顺序）、工具实现、`edit_text_file.py`、LLM 层 |
| 前置 | `git` 工作区干净；改前先 `git diff` 留档，实施后按铁规打 tag 前先写 `version.txt` |

#### 5.8.2 完整代码改动（5 处必改 + 1 处可选清理，可直接落地）

**步骤 1：import 补 `Set`**（action_handler.py 第 68 行）

```python
from typing import Dict, List, Any, Optional, Set
```

**步骤 2：新增 `_parse_paths`**（放在 `_has_conflict` 定义之前，模块级）

```python
def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09
    从旧 _has_conflict 的路径解析循环提取, 供 _has_conflict/_partition_calls 共用(DRY)
    """
    if name not in FILE_OPERATION_TOOLS:
        return set()
    aliases = PARAM_ALIASES.get(name, {})
    if not aliases:
        p = params.get("path", "")
        return {p} if p and isinstance(p, str) else set()
    resolved = {}
    for key, value in params.items():
        canon = aliases.get(key, key)
        if canon not in resolved:
            resolved[canon] = value
    out = set()
    for pname in set(aliases.values()):
        pval = resolved.get(pname)
        if pval and isinstance(pval, str):
            out.add(pval)
    return out
```

**步骤 3：改造 `_has_conflict` 为计数版**（替换原函数，保留签名与调用方兼容）

```python
def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测文件路径冲突 — 北京老陈 2026-07-04 初版; 小欧 2026-08-09 计数版
    冲突：同一路径被>=2次调用访问, 且至少一个是写操作
    有冲突→顺序执行, 无冲突→并行
    [2026-08-09 小欧] BUG修复: 旧实现用 set 存工具名不计数, 同名工具多次写
    同一路径漏检(3×edittext 同文件)→误走并行→read-modify-write 竞态致内容丢失。
    改为 path→(调用次数, 工具名set), 复用 _parse_paths 解析(与 _partition_calls 一致, DRY)。
    """
    path_ops: Dict[str, Dict[str, Any]] = {}

    def _record(_path: str, _name: str) -> None:
        entry = path_ops.setdefault(_path, {"count": 0, "tools": set()})
        entry["count"] += 1
        entry["tools"].add(_name)

    for c in all_calls:
        name = c.get("tool_name", "")
        if name not in FILE_OPERATION_TOOLS:
            continue
        for _path in _parse_paths(name, c.get("tool_params", {})):
            _record(_path, name)

    for path, entry in path_ops.items():
        tools = entry["tools"]
        if entry["count"] >= 2 and any(t in _WRITE_OPS for t in tools):
            logger.info(f"[_has_conflict] 路径冲突: {path}, tools={tools}, 调用数={entry['count']}, 降级顺序执行")
            return True
    return False
```

**步骤 4：新增 `_partition_calls`**（并查集分组，放在 `_has_conflict` 之后）

```python
def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径相关性分组(并查集连通分量): 共享路径的调用归一组, 组间无共享路径→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09
    """
    n = len(all_calls)
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    path_to_calls = {}
    for i, c in enumerate(all_calls):
        for p in _parse_paths(c.get("tool_name", ""), c.get("tool_params", {})):
            path_to_calls.setdefault(p, []).append(i)
    for _p, idxs in path_to_calls.items():
        base = idxs[0]
        for i in idxs[1:]:
            _union(base, i)

    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    return list(groups.values())
```

**步骤 5：改造 `execute_tools` 分支 B**（`elif is_parallel and not _has_conflict(all_calls):` → `elif is_parallel:` 分组调度；A、C 分支不动）

```python
        elif is_parallel:
            # B': 并行分组调度 — 冲突组内串行, 无冲突组并行("该并行就并行") — 小欧 2026-08-09
            _names = [_cn(c) for c in all_calls]
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 分组并行执行: tools={_names}")
            groups = _partition_calls(all_calls)

            async def _run_group(indices: List[int]):
                group = [all_calls[i] for i in indices]
                if len(group) == 1:  # 单工具, 语义同原A
                    return [await execute_tool(agent, _cn(group[0]), _cp(group[0]),
                                               on_retry_started=on_retry_started)]
                if not _has_conflict(group):  # 组内无冲突→并行(try_once), 语义同原B
                    tasks = [execute_tool(agent, _cn(c), _cp(c), parallel=True) for c in group]
                    return await asyncio.gather(*tasks, return_exceptions=True)
                # 组内冲突→组内串行(带重试), 语义同原C
                _res = []
                for call in group:
                    try:
                        _res.append(await execute_tool(agent, _cn(call), _cp(call),
                                                       on_retry_started=on_retry_started))
                    except Exception as e:
                        logger.warning(f"[action_handler] 工具{_cn(call)}组内顺序执行失败: {e}")
                        _res.append(e)
                return _res

            _grouped = await asyncio.gather(*[_run_group(g) for g in groups],
                                            return_exceptions=True)  # 组间失败隔离: 单组异常不取消其他组
            results = [None] * len(all_calls)  # 结果按原顺序填回
            for _indices, _res in zip(groups, _grouped):
                if isinstance(_res, Exception):  # 整组失败: 组内全部标记为该异常(与原C单工具异常append语义一致)
                    for _i in _indices:
                        results[_i] = _res
                    continue
                for _i, _r in zip(_indices, _res):
                    results[_i] = _r
```

> 原 `elif is_parallel and not _has_conflict(all_calls):` 中"有冲突则落入 C 整批串行"的逻辑，改为进入 B' 后**分组处理**：有冲突的组串行、无冲突的组并行，C 分支保留给 `is_parallel=False`。
>
> **顺手清理（KISS-DIRECT，第 6 处·可选）**：进入 B' 后 C 分支只可能由 `is_parallel=False` 触发，其 `_reason = "非并行模式" if not is_parallel else "文件路径冲突"` 中的 `"文件路径冲突"` 分支成为**永假死代码**，实施时建议改为 `_reason = "非并行模式"`（或直接去掉三元表达式）。**此项为可选**——不改不影响功能与验收标准（C 分支仅在 `is_parallel=False` 时触发，日志文案仍正确），仅消除死代码（KISS-DIRECT）。
>
> **异常处理等价性（L1）**：B' 的失败语义与原分支**逐点等价**——① 组内冲突→组内串行，`try/except Exception as e` 后 `_res.append(e)`，与原 C 分支逐工具处理的产物**相同**；② 组内无冲突→组内并行，`asyncio.gather(return_exceptions=True)`，与原 B 分支一致；③ 外围 `asyncio.gather(*[_run_group(g)...], return_exceptions=True)` 只兜底 `_run_group` 自身异常（如 `_has_conflict` 崩溃），此时整组标记为该异常，语义与原 C 分支"该调用失败"一致。**不改变 `results` 列表（含 Exception 元素）的返回形态**，`build_observation`/`_merge_llm_data` 零改动。

#### 5.8.3 实施步骤

1. **备份**：实施前确认 `git status` 干净；如需留档先 `git stash` 或记下当前 commit。
2. **落码（必须按序）**：严格按照 5.8.2 的 1→2→3→4→5 顺序执行。**步骤 2 的 `_parse_paths -> Set[str]` 依赖步骤 1 补的 `Set` import**，若跳过步骤 1 会 NameError；步骤 3 的 `_has_conflict` 又依赖步骤 2 的 `_parse_paths`。故 5 处不可乱序。
3. **静态检查**：`python -m py_compile backend/app/services/agent/handlers/action_handler.py` 无语法错误。
4. **单元验证**：运行 `verify_partition_v13.py`（分组单元 5 项 + 执行行为 4 项 + 失败隔离 1 项，内嵌计数版 `_has_conflict` 与生产逻辑一致，见 5.5.6）。**脚本路径**：`C:\Users\chend\AppData\Local\Temp\opencode\verify_partition_v13.py`（临时目录，若已清理可按 5.8.2 代码重建——其内嵌 `_parse_paths`/`_partition_calls`/`_has_conflict`/B' 逻辑与 5.8.2 逐字一致）。运行：`E:\Appsw\python31311\python.exe -X utf8 <脚本路径>`（cwd 为 `backend/`）。
5. **行为一致性回归**：重跑"原版 vs 新版 `_has_conflict`"对比（竞态/多读/一写多读/不同路径/别名归一 5 场景 + 无关工具/空调用/单调用等 10 项），输出必须一致。**脚本路径**：`C:\Users\chend\AppData\Local\Temp\opencode\verify_refactor_consistency.py`（同步骤 4 的运行方式，若缺失可按其 14 个 CASE 重建）。
   - **已在设计期实测**：重构版（复用 `_parse_paths`）vs 内联计数版 **14/14 全部一致**（verify_refactor_consistency.py，含 move 同源不同目标、edittext+copy+readtext 07:57:53 批次等），重构不改变判定行为。
6. **全量回归**：`backend/` 目录跑 `pytest -x --tb=short`（既有测试不得出现回归失败）。
7. **提交**：按铁规 `git commit`（标题含文件名+签名+日期）；打 tag 前在 `version.txt` 头部插入本次变更说明。

#### 5.8.4 验证与验收标准

| # | 验收项 | 标准 |
|---|--------|------|
| 1 | 竞态批次（3×edittext 同文件 + extract/listdir/readtext） | edittext×3 **组内串行**，其余与组**并行**；总耗时 ≈0.92s（对照旧 1.8s），**内容不再丢失** |
| 2 | 多读同路径（readtext×2） | 组内无冲突 → 仍并行（与现状一致） |
| 3 | 不同路径（edittext A + edittext B） | 分属两组 → 并行（与现状一致） |
| 4 | 别名归一（file_path / filepath 同路径） | 归一组且组内串行（计数版检出） |
| 5 | 失败隔离（组内异常 + 独立组） | 组内异常被捕获不中断组内其余；独立组不受拖累；**结果保序** |
| 6 | 全量回归 | `pytest` 全过 |
| 7 | 无回归行为 | 多读并行、不同路径并行、非并行模式整批串行、单工具直执行均与旧版一致 |

---

## 六、总结

> **最直白的结论（给老陈）**：`after` 这个简单功能**本身没有问题**（它只会按锚点行后插入，位置分毫不差）。真正的问题出在**并发调度**：多个编辑同时改同一个文件时互相覆盖。那次测试里 `after` 只是被并发拖累报错，被误说成"插错位置"。**所以只修并发调度逻辑（`_has_conflict` + 分组调度）即可，`after` 一行都不用改。**

| 问题 | 判定 | 根因 | 处置 |
|------|------|------|------|
| ① 并发 edittext 竞态致内容丢失 | ✅ **真实 BUG（高）** | `_has_conflict` 用 set 存工具名不计数，同名工具多写同一路径漏检 → 走并行分支 → read-modify-write 丢失更新 | 修复 `_has_conflict` 按路径计数（方案一/方案二均含，见五） |
| ② after 模式插入位置异常 | ⚪ **本次场景工具行为正确，报告误判**（step=14 多行锚点位置正确，精确复现）；边界：单行签名锚点确有错位风险，`_anchor_signature_hint` 已提示兜底（task002 已知项） | step=11 并发竞态导致 after 调用失败，LLM 延续失败记忆推理误判（step=15 无 readtext 实证） | 修复问题①后自然消失，无需单独改码；签名行锚点风险已有提示机制，不另立修复项 |

> **注**：本报告已完成研究核实与两套修复方案设计验证。**老陈已于 2026-08-09 选定方案二（分组调度版）**，完整落地清单见 **5.8**。代码**尚未修改**，按 5.8.3 实施步骤执行。
