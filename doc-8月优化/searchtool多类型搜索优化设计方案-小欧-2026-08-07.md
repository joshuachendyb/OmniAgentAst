# searchtool 多类型搜索优化设计方案

**创建时间**: 2026-08-07 20:42:43
**编写人**: 小欧
**状态**: 待评审（北京老陈批准后实施）
**依据**: `backend/logs/app_2026-08-07.log` L41634-41734 + BM25 实测复现

## 一、问题背景

### 1.1 现象

2026-08-07 20:31:18，task001 任务（要求网络/文件/代码执行/系统管理/监控/office文档全覆盖验证）中，LLM 在 step2 并行发出 8 个工具调用：`timenow` + **7 次 searchtool**，每次只搜一个类型：

| # | query | 命中 | 注入分类 |
|---|-------|------|---------|
| 1 | 网络 搜索 http | 7个 | network |
| 2 | 系统 进程 任务 | 11个 | shell+win_registry+system |
| 3 | 文档读写 | 9个 | document+desktop |
| 4 | 数据分析 图表 | 15个 | dataanalysis |
| 5 | 数据库 SQL | 13个 | 冗余（dataanalysis 已加载） |
| 6 | 桌面 窗口 | 5个 | 冗余（desktop 已加载） |
| 7 | 时间 定时 | 11个 | timer |

结果：tools 19→63，全部分类注入成功，耗时 0.02s。**功能无错误，但存在 2 次冗余搜索**。

### 1.2 核心问题

searchtool 描述明确支持"一次搜索多个类型，命中几个分类就自动注入几个分类的整类工具"（`fundamental_register.py:50`），但 LLM 未使用该能力，而是**逐类型并行 7 次搜索**。

## 二、根因分析（双层根因）

### 2.1 根因1（直接）：examples 少样本引导

`fundamental_register.py:58-66` 的 `FUNDAMENTAL_TOOL_EXAMPLES["searchtool"]` 恰为 **7 条单类型示例**：

```python
"searchtool": [
    {"query": "文档 读写"},
    {"query": "数据分析 图表"},
    {"query": "数据库 SQL"},
    {"query": "网络 搜索 下载"},
    {"query": "系统 进程 注册表 任务"},
    {"query": "桌面 窗口"},
    {"query": "时间 定时"},
],
```

这些 examples 会随工具定义发给 LLM（`tool_description.py:43-44` `func_def["examples"] = meta.examples`）。**LLM 的 7 次 query 逐字复刻了这 7 条示例**（对比：'网络 搜索 http'≈'网络 搜索 下载'，'系统 进程 任务'≈'系统 进程 注册表 任务'，'文档读写'='文档 读写'）。示例中**没有任何一条多类型混合示例**，少样本引导 LLM 认为"每个类型搜一次"是标准做法。

### 2.2 根因2（深层）：BM25 混合搜索分类覆盖不全（实测验证）

即使 LLM 按描述发起一次多类型搜索，BM25 检索也会**漏掉部分分类**：

实测 `query='网络 系统 文档 数据分析 数据库 桌面 时间'`，当前算法返回仅 4 个分类：

```
matches: 10 categories: ['dataanalysis', 'fundamental', 'network', 'system']
```

**document / desktop / timer / win_registry / shell 全部被过滤**。

定位到真正的元凶是 **`TOOL_SEARCH_INER_RESULTS_TOP=10` 的截断**，而非 10% 相对阈值：
- 阈值过滤后的 `meaningful` 实际已包含 document/desktop/timer 等分类代表（分数 > threshold）
- 但 dataanalysis 占 4 个名额（9.22/8.80/6.31/4.84）+ fundamental 占 4 个名额（7.00/6.20/6.04/4.57），共 8/10 名额被两个分类霸占
- 低分分类（write_docx 3.17 / screen_capture 2.07 / which 2.20）排在 top10 之外被截断

**因果链**：LLM 无法预知 BM25 会漏分类 → 拆分搜索是它能保证全部分类注入的唯一稳妥策略 → 表现为 7 次冗余 searchtool。

## 三、优化方案（三堂会审定稿 v1.0）

### 3.1 方案总览

| # | 优化点 | 文件 | 目的 |
|---|--------|------|------|
| 优化1 | examples 精简为 4 条（2 多类型 + 2 单类型） | `fundamental_register.py` | 纠正少样本引导，让 LLM 知道可以一次搜索多个类型，同时保留单类型用法 |
| 优化2 | BM25 结果"分类级名额保底" | `tool_search.py` | 保证混合搜索时每个被搜到的分类至少 1 个工具入选，确保注入全部分类 |

**两优化配套实施**：优化1 引导 LLM 一次搜索；优化2 保证一次搜索真能注全。缺一不可（只有引导无能力=注不全，只有能力无引导=LLM 仍分开搜）。

### 3.2 优化1：examples 增加混合示例（落盘代码）

文件：`backend/app/tools/fundamental/fundamental_register.py`

**① 编辑历史**（`fundamental_register.py` 顶部 docstring 编辑历史清单，追加在 `【2026-08-05 小欧】...` 之后）：

```python
【2026-08-07 小欧】searchtool examples精简为4条(2多类型+2单类型), 引导"一次搜索多个类型"并保留单类型用法
```

**② examples 落盘代码**（`FUNDAMENTAL_TOOL_EXAMPLES` 字典 `"searchtool"` 键，原 7 条单类型示例**精简为 4 条**：2 条多类型混合示例置前 + 2 条单类型示例置后）：

```python
FUNDAMENTAL_TOOL_EXAMPLES = {
    "searchtool": [
        {"query": "网络 文档 数据分析 系统 桌面 时间"},   # 多类型混合示例1 - 小欧 2026-08-07
        {"query": "数据库 SQL 注册表 定时"},             # 多类型混合示例2 - 小欧 2026-08-07
        {"query": "文档 读写"},                          # 单类型示例
        {"query": "桌面 窗口"},                          # 单类型示例
    ],
    # ... 其余工具( timenow/shell/sysinfo/notify ) examples 原样不动 ...
}
```

要点：
- 4 条示例 = **2 条多类型**（覆盖 8 类：网络/文档/数据分析/系统/桌面/时间/数据库/注册表/定时）+ **2 条单类型**（文档 读写、桌面 窗口，保留精准单类搜索示范）
- 多类型示例**置前**（LLM 对示例的采样通常偏向列表首部），引导一次搜索多个类型
- 混合示例使用与 schema docstring（`fundamental_schema.py:31-42`）一致的 8 个类型词，保持语义对齐
- 单类型示例保留（兼容精准单类需求场景，避免过度混合导致噪声）
- examples 经 `tool_description.py:43-44` 随工具定义原样发给 LLM

### 3.3 优化2：BM25 分类级名额保底（落盘代码）

文件：`backend/app/tools/fundamental/tool_search.py`

**① 编辑历史**（文件头编辑历史区追加 2 行）：

```python
# 2026-08-07 - 小欧 - searchtool结果选取增加"分类级名额保底"(_apply_category_floor):
#   修复多类型混合搜索时高分类霸占top10名额, 低分分类被挤出导致一次搜索注不全分类(实测7类型混合仅命中4类)
```

**② 新增私有 helper 函数**（放在 `_build_tool_search_llm_data` 之后、`searchtool` 主函数之前）：

```python
def _apply_category_floor(meaningful: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """分类级名额保底 — 小欧 2026-08-07

    多类型混合搜索时, dataanalysis/fundamental 等高分类霸占 top_n 名额,
    把 document/desktop/timer 等低分分类代表挤出 top10, 导致一次搜索注不全分类。
    本函数保证每个"已过阈值"的分类至少 1 个代表入选, 再按分数填充剩余名额。
    meaningful 必须已按 _score 降序排列(由调用方保证)。
    """
    if not meaningful:
        return []

    # 分类代表保底: 每分类最高分工具作为代表(meaningful 已降序, 首个即该分类最高分)
    cat_rep: Dict[str, Dict[str, Any]] = {}
    for r in meaningful:
        c = r.get("category", "")
        if c and c not in cat_rep:
            cat_rep[c] = r

    reps = sorted(cat_rep.values(), key=lambda x: x["_score"], reverse=True)
    rep_names = {r["name"] for r in reps}
    rest = [r for r in meaningful if r["name"] not in rep_names]
    return (reps + rest)[:top_n]
```

**③ searchtool() 主函数接入点**（替换原 `top_results = meaningful[:TOOL_SEARCH_INER_RESULTS_TOP]` 一行，该行位于阈值过滤之后）：

```python
    if scored and scored[0]["_score"] > 0:
        threshold = scored[0]["_score"] * 0.1
        meaningful = [r for r in scored if r["_score"] >= threshold]
    else:
        meaningful = []
    top_results = _apply_category_floor(meaningful, TOOL_SEARCH_INER_RESULTS_TOP)
```

逻辑说明：
- `meaningful` 保持原 10% 阈值过滤语义（过滤无关工具，不引入噪音）
- `_apply_category_floor` 只在"已过阈值"的结果上做**分类均衡**：先全放每分类代表（保证全分类注入），再填充剩余名额
- `top_results` 仍满足"结果最多返回10个工具"的既有契约（`TOOL_SEARCH_INER_RESULTS_TOP=10`）
- 无命中分支（`not meaningful`）在接入点之前已 return，本函数不改变空结果语义

**实测效果**（分类代表保底后）：

| query | 优化前分类覆盖 | 优化后分类覆盖 |
|-------|---------------|---------------|
| 网络 系统 文档 数据分析 数据库 桌面 时间 | 4类 | **10类全覆盖** |
| 网络 搜索 http 系统 进程 任务 文档读写 数据分析 图表 数据库 SQL 桌面 窗口 时间 定时 | 4类 | **10类全覆盖** |
| 桌面 窗口（单类型） | 2类 | 2类（分类集合一致，工具顺序一致） |
| 网络 搜索 http（单类型） | 3类 | 3类（分类集合一致，注入行为不变；工具内部顺序微调：file 代表 find 置前） |

> **三堂会审修正 v1.2（2026-08-07 小欧）**：单类型搜索"零退化"指**分类集合与注入行为不变**（功能零退化）。工具内部顺序在"分类代表置前"策略下可能微调（实测 Q4 中 `find`[file] 与 `httpget`[network] 顺序互换），但 matches 作为集合不变、注入分类不变、LLM 观察不受实质影响。文档原"结果与现状完全一致"表述修正为"分类集合与注入行为一致"。

### 3.4 设计要点说明

- **不修改分词/BM25 算法**：`_tokenize`、`_bm25_scores`、`_build_bm25` 均不动，只改结果选取逻辑（新增 1 个 helper + 改 1 行接入点），改动面最小，风险最低
- **不修改 10% 阈值**：阈值仍有效过滤无关工具；保底是在"已过阈值"的结果上做分类均衡，不引入噪音
- **零退化保证（功能级）**：单类型搜索的分类集合与注入行为不变（实测 Q3 桌面 窗口/工具顺序也一致；Q4 网络 搜索 http 分类集合一致，仅工具内部顺序微调——file 代表 find 置前，不影响注入与观察语义）
- **KISS-DIRECT**：无中间层、无注册表、无抽象，helper 单一函数 14 行 + 接入点 1 行
- **SRP**：分类保底逻辑抽成私有 helper 函数 `_apply_category_floor(meaningful, top_n)`，与 BM25 计算分离；helper 只做"分类均衡+截断"一件事
- **SLAP**：`searchtool()` 主函数保持同一抽象层——调用 helper 完成结果选取，不内联分类均衡细节
- **禁止backward**：不做新旧分支兼容，直接替换选取逻辑

## 四、回归验证计划

### 4.1 单元验证（BM25 覆盖）

| 用例 | 预期 |
|------|------|
| 多类型混合搜索（7类型） | 覆盖 ≥ 9 个分类 |
| 单类型搜索（桌面 窗口） | 结果与优化前一致 |
| 无命中搜索 | 返回空 matches + warning，不注入 |
| 纯符号搜索 | 返回空 matches + warning |

### 4.2 系统验证

- 现有测试 `backend/tests/tools/param_combination/` 全量跑，确认无回归
- 复现 20:31:18 场景：真实 LLM 请求"按任务书覆盖全部分类测试"，观察 LLM 是否用**一次多类型搜索**替代 7 次并行

### 4.3 关联逻辑检查

- `auto_inject_from_search`（`tool_executor.py:72-113`）：结果含多个分类 → 逐个 load_category，兼容多分类结果，无需改动
- `_format_searchtool_results`（`observation_formatter.py:1129`）：支持 matches 列表渲染，兼容
- `patch_search_desc`（`tool_cache_manager.py:63`）：搜索结果成功注入后更新 searchtool 描述"当前未加载分类"列表，兼容
- 并行执行路径（`action_handler.py:347-353`）：searchtool 无文件冲突，并行安全

## 五、实施清单

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | examples 增加混合示例 + 编辑历史 | `backend/app/tools/fundamental/fundamental_register.py` |
| 2 | 新增 `_apply_category_floor` helper + 接入 searchtool + 编辑历史 | `backend/app/tools/fundamental/tool_search.py` |
| 3 | 单测：混合/单类型/无命中/纯符号 4 场景 | `backend/tests/tools/param_combination/`（新增） |
| 4 | 全量回归测试 | pytest |
| 5 | 真实 LLM 复现验证（20:31:18 场景） | E2E |
| 6 | 更新测试回归记录文档 | `doc-测试与审查/测试回归记录.md` |
| 7 | 提交 + 按 AGENTS.md 打 tag 流程（用户确认后） | git |

## 六、版本历史

| 版本 | 时间 | 编写人 | 说明 |
|------|------|--------|------|
| v1.0 | 2026-08-07 20:42:43 | 小欧 | 初稿：记录 20:31:18 日志现象、双层根因分析（examples 少样本引导 + BM25 top10 截断漏分类）、双优化方案（examples 混合示例 + 分类级名额保底）及实测验证结论 |
| v1.1 | 2026-08-07 20:44:xx | 小欧 | 老陈指示"要准确的实施代码设计"：3.2/3.3 章节补充**准确落盘代码**（编辑历史格式、examples 完整代码块、`_apply_category_floor` helper 完整实现、searchtool 接入点精确行替换）、3.4 补充 SLAP 原则 |
| v1.2 | 2026-08-07 20:5x:xx | 小欧 | 三堂会审修正 2 处：①3.3"零退化"表述修正为"功能级零退化"（实测 Q4 单类型搜索工具内部顺序微调，分类集合与注入行为不变）；②3.2① 编辑历史格式改 `fundamental_register.py` 实际 docstring【】格式（原误引 tool_search 行注释格式） |
| v1.3 | 2026-08-07 20:5x:xx | 小欧 | 老陈指示"用例不要 7 个保留 4 个：两个多类型 2 个单类型"：3.1/3.2 的 searchtool examples 由原 7 条单类型 + 新增 1 混合 改为**精简 4 条**（2 多类型混合示例置前 + 2 单类型示例置后），保留 8 类关键词语义对齐 |
