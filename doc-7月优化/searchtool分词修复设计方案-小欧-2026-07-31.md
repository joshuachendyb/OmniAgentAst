# searchtool 分词修复（词不拆字）+ 无命中/纯符号注入修复设计方案

**创建时间**: 2026-07-31 19:55:47
**编写人**: 小欧
**版本**: v1.9
**状态**: 已实施并通过三堂会审（2026-08-05 小欧按 v1.8 方案落地 4 处改动，三堂会审通过，详见 v1.9）

## 版本历史
| 版本 | 时间 | 更新人 | 修改简介 |
|------|------|--------|---------|
| v1.0 | 2026-07-31 19:55:47 | 小欧 | 初稿：中文 bigram 保留修复方案 |
| v1.1 | 2026-07-31 20:03:12 | 小欧 | 三堂会审修正：①§四"追加 10 行"改为"追加 15 行"；②§3.4 示例效果标注"定时"提升效果为推断，并补充 bigram 实测结论（timer 1.94→1.95 排名未变）；③§3.5 补充注入行为确认（北京老陈）：matches≤10 工具收集分类注入整类 |
| v1.2 | 2026-07-31 20:10:55 | 小欧 | 北京老陈提问"无命中时给 LLM 看什么"，实证发现无命中 bug：max_score=0→threshold=0→全部工具过阈值→误导 LLM+错误注入。新增 §七 修复方案，同步更新 §四/§五/§六 |
| v1.3 | 2026-07-31 20:18:33 | 小欧 | 全文熟读 3 遍复查 + 实证：发现 §7 遗漏纯符号查询（`'?'`/`'？？？'`，token 为空）走 `not query_tokens` 分支仍返回全部工具并注入 6 类。§七 扩展覆盖该分支；修正 §六 风险评估不实描述；§3.3 标注推断；§四 精确化"替换 return tokens"；单字母英文查询（`'a'`/`'ab'`）实测 DF=0 同为无命中，已有修复覆盖 |
| v1.4 | 2026-07-31 20:19:09 | 小欧 | 全文复查发现 6 处不一致并修复：①标题扩为含 3 个修复；②§3.5"仅改动一个函数"改为"改动 3 处"；③§7.5 补纯符号 bug 关系；④§四 引用 §7.2→§7.3；⑤§二 补 §七 两个独立根因提示；⑥§五 第 5 条明确 matches 空时不注入 |
| v1.5 | 2026-07-31 20:21:53 | 小欧 | 第 3 遍复查再修正：①§七.3/§七.6.3 修复后 summary 统一"共 63 个工具"（`total_tools=len(all_tools)`，与 §七.4 示例一致，消除 total_tools=0 与示例不一致）；②§七.3 行号"183-185"精确为"第 183 行（if 条件处）"；③§七.6.2 行号"150-165"精确为"第 151 行起（`if not query_tokens:`）" |
| v1.6 | 2026-07-31 20:26:45 | 小欧 | 北京老陈批评：缺设计目标与设计原则。新增 §一 设计目标、§二 设计原则，原章节编号整体顺延（问题描述→三、根因→四、修复方案→五、变更总结→六、回归测试→七、风险评估→八、无命中bug→九），全部交叉引用同步更新 |
| v1.7 | 2026-07-31 20:33:20 | 小欧 | 北京老陈明确两个根本要求：①词不能拆开为字去匹配（G1 原则化）；②成功时给 LLM 的分类工具合计≤10 个；失败时正确告知 LLM 并给 hint。修正：G1 明确"词不拆字"；无命中/纯符号从 success 改为 warning + detail/hint（observation_formatter 仅 warning/error 显示 hint），同步 §六/§七/§八/§九 |
| v1.8 | 2026-07-31 20:44:43 | 小欧 | 三堂会审（合规+合理+相关逻辑）对照实际代码核实行号无误，但发现核心矛盾：§5.1 保留单字 token 与根本要求①"严禁拆单字碰撞"冲突。北京老陈裁决："关键词是单字就是单字，是多字就是多字"。据此修正：中文片段≥2 字**只生成 bigram（去单字）**、=1 字保留单字。同步更新 §一 G1、§二 P1、§五 5.1/5.2/5.3/5.4、§六、§七；§7.2/§7.6.3 等与去单字关联处复核 |
| v1.9 | 2026-08-05 12:42:38 | 小欧 | 实施完成：按 v1.8 方案落地 4 处改动（①_tokenize 中文≥2字只生成bigram去单字、=1字保留单字；②_build_tool_search_llm_data 增加 warning 分支；③searchtool 阈值无命中判断 scored[0]["_score"]>0 + 无命中返回空matches+warning；④空 token 分支不再返回全部 top10，返回空matches+warning）。修正 2 处行号引用：§六/§9.6.2"第 151 行"→"第 150 行"（修复前代码）；§9.3/§9.6.3"formatter:714-717"→"formatter:629-636"。验证：分词 15 项全过、搜索行为符合预期（无命中/纯符号→warning+空matches+hint）、现有测试 28 过 1 败（CACHE-007 断言"无命中返回全部工具"与修复目标冲突，北京老陈决策更新测试断言新行为，更新后 29 过 0 败）。三堂会审通过：①合规（SRP/DRY/KISS-DIRECT/SLAP/YAGNI/禁止backward+文件头3铁规+注释署名日期）；②合理（scored[0]即最高分、build_success承载warning完整llm_data、语料/查询共用_tokenize对齐、build_warning无detail/hint字段故用build_success）；③关联逻辑（auto_inject_from_search零注入/observation_formatter warning联动hint/is_success兼容warning/正常命中与error分支零回归） |

## 一、设计目标

> **两个根本要求（北京老陈 2026-07-31）**：
> ① **词不能拆开为字去匹配**——中文词组（如"定时/压缩/文件"）必须作为整体参与匹配，严禁拆成单字（'定'/'时'）去碰撞。**裁决：关键词是单字就是单字，是多字就是多字**（≥2 字中文片段生成 bigram、去单字；=1 字保留单字）；
> ② **成功时给 LLM 的分类工具合计 ≤10 个**；**失败时正确告知 LLM 并给 hint**。

| 目标 | 说明 | 验收标准 |
|------|------|---------|
| **G1 词不拆字**（根本要求①）| 中文词组作为整体参与 BM25 匹配。**北京老陈裁决（2026-07-31）：关键词是单字就是单字，是多字就是多字**——连续中文片段 ≥2 字只生成 bigram（不含单字 token）、=1 字保留单字 | `_tokenize("定时")→['定时']`（无 '定'/'时' 单字）；`_tokenize("电")→['电']`（单字保留）；`"定时"` 命中 timer 类描述中的 `'定时'` bigram，而非靠单字碰撞 |
| **G2 分类注入符合人类思维** | `searchtool` 成功时从 `matches` 收集分类注入整类给 LLM；无命中时不注入任何分类 | 命中→注入相关分类；无命中→零注入 |
| **G3 成功时注入 ≤10**（根本要求②）| `matches` 工具合计 ≤10 个（`TOOL_SEARCH_INER_RESULTS_TOP=10`），收集其分类注入 | `len(matches) ≤ 10` 恒成立 |
| **G4 无命中正确反馈 + hint**（根本要求②）| 完全无命中（`max_score=0`）不再报"匹配 63 个"，返回空 matches，exec_code=warning，**detail + hint 明确告知 LLM 换词重搜** | summary"未匹配到工具（共 63 个工具）"+ hint"建议更换关键词后重试" |
| **G5 纯符号查询正确反馈 + hint** | token 为空的纯符号/空分词查询不再返回全部工具 top10，exec_code=warning，**detail + hint** | `'?'`/`'？？？'` → 空 matches + hint |
| **G6 零回归** | 正常命中、英文查询、单中文关键词行为不变 | §七 回归测试全部通过 |

## 二、设计原则

| 原则 | 说明 |
|------|------|
| **P1 词不拆字** | 中文片段按长度分流：**≥2 字只生成 bigram（去单字 token）**，=1 字保留单字；英文/数字按词切分不受影响。查询与语料（`_build_bm25`）共用同一 `_tokenize`，保证 query token 与 doc token 对齐 |
| **P2 根因修复，非症状治理** | 改动均落在根因处：分词（`_tokenize`）、无命中阈值判断、纯符号空 token 分支；不动排序/截断/注入逻辑。三个根因彼此独立（见 §四/§九） |
| **P3 通解，非特例** | 不针对"文件 压缩 定时"单个 case 设计，方案通用于所有查询类型 |
| **P4 最小改动（KISS-DIRECT）** | 共 4 处改动、均在 `tool_search.py`；逻辑内联，无新函数/新字段/新常量 |
| **P5 注入逻辑零改动** | `auto_inject_from_search` 不改，保持北京老陈确认的行为：matches≤10 工具收集分类注入整类 |
| **P6 失败必有 hint** | 无命中/纯符号等失败场景，exec_code=warning，detail 说明原因、hint 给出行动建议（换关键词重搜），确保 LLM 收到可执行指引 |
| **P7 实证验证** | 所有效果区分实测/推断；实施后必须跑 §七 回归测试确认，推断项待实跑 |

## 三、问题描述

`searchtool` 用 `_tokenize` 对中文按单字切分，丢失词组语义。例：

```
query = "定时"
_tokenize → ['定', '时']

timer_set 描述 "设置一个定时器"
_tokenize → ['设', '置', '一', '个', '定', '时', '器']
```

BM25 只能靠单字 `'定'` 和 `'时'` 分别匹配，TF×IDF 得分远低于 `"定时"` 作为词组完整匹配时的得分。结果：弱匹配分类被强匹配分类（如 file）垄断，top 10 截断后丢失。

## 四、根因

`_tokenize`（`tool_search.py:27-49`）对中文**按单字逐字切分**，没有保留相邻字组成的词组。

所有下游问题（top 10 截断、单分类垄断、timer 类丢失）都是这个根因的连锁反应。

> **另有两个独立根因**，非分词引发，见 §九：①阈值过滤 max_score=0 时 threshold=0 全放行（§9.2）；②纯符号查询 token 为空时返回全部工具（§9.6.2）。

## 五、修复方案：中文 Bigram 保留

### 5.1 改动

将 `_tokenize` 中的中文处理改为**按片段长度分流**：连续中文片段 ≥2 字只生成相邻二元组（bigram）、去单字；=1 字保留单字（北京老陈裁决："单字就是单字，多字就是多字"）。英文/数字/下划线路径零改动：

```python
def _tokenize(text: str) -> List[str]:
    """中英混合分词：中文按词组切分，英文按词切分，统一小写 — 小沈 2026-06-14
    小欧 2026-07-31 修复: 中文≥2字只生成bigram去单字;=1字保留单字(词不拆字)
    """
    tokens: List[str] = []
    buf: List[str] = []
    chinese_buf: List[str] = []
    for ch in text.lower():
        if '\u4e00' <= ch <= '\u9fff':
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            chinese_buf.append(ch)
        else:
            if chinese_buf:
                # 中文片段收尾: ≥2字生成bigram, =1字保留单字 — 小欧 2026-07-31
                if len(chinese_buf) >= 2:
                    for i in range(len(chinese_buf) - 1):
                        tokens.append(chinese_buf[i] + chinese_buf[i + 1])
                else:
                    tokens.append(chinese_buf[0])
                chinese_buf.clear()
            if ch == '_':
                if buf:
                    tokens.append("".join(buf))
                    buf.clear()
            elif ch.isalnum():
                buf.append(ch)
            else:
                if buf:
                    tokens.append("".join(buf))
                    buf.clear()
    if chinese_buf:
        if len(chinese_buf) >= 2:
            for i in range(len(chinese_buf) - 1):
                tokens.append(chinese_buf[i] + chinese_buf[i + 1])
        else:
            tokens.append(chinese_buf[0])
    if buf:
        tokens.append("".join(buf))
    return tokens
```

效果：
```
"定时"    → ['定时']
"压缩"    → ['压缩']
"文件"    → ['文件']
"定时器"  → ['定时', '时器']
"电"      → ['电']        （单字保留）
"定时 文件" → ['定时', '文件']
```

英文不受影响（无连续中文字符，bigram 分支不触发）。

### 5.2 为什么这是通解

| 查询类型 | 旧行为 | 新行为 |
|---------|--------|--------|
| 双字中文关键词（如"压缩"）| 单字 `'压'`/`'缩'` 匹配，file 类强相关 | `'压缩'` bigram 精准匹配含"压缩"的工具，无单字碰撞 |
| 单字中文关键词（如"电"）| 单字 `'电'` 匹配 | 单字 `'电'` 保留（"单字就是单字"），行为不变 |
| 多类型关键词（如"定时 文件"）| 各自单字碰撞，分类边界模糊 | `'定时'` 和 `'文件'` 分别作为 bigram 精准命中各自分类 |
| 三字以上中文（如"定时器"）| 单字 `'定'/'时'/'器'` 碰撞 | `['定时', '时器']` bigram，无单字碰撞 |
| 英文关键词（如"http request"）| 不受影响 | 不受影响（无中文） |
| 混合中英文（如"文件 http"）| 中文单字 + 英文按词 | 中文 bigram + 英文按词，各不干扰 |

### 5.3 语料影响（推断，待实跑验证）

去单字方案下，纯中文描述（N 字）分词从 N 个单字 token 变为 N-1 个 bigram token，**token 数量基本持平**（200 字 → 约 199 个 bigram）。63 个工具、语料总量仍为 KB 级。变化在于 token 类型：单字→bigram，DF 统计口径改变，**BM25 打分分布会变**（已列入 §八 风险）。**非"增加 1.5-2 倍"（v1.8 修正：那是混合方案的估算，去单字后不适用）**。

### 5.4 示例效果（推断，待实跑验证）

| query | 旧（单字分词） | 新（bigram 去单字） |
|-------|---------------|-------------------|
| `"定时"` | timer 匹配靠 `'定'`+`'时'` 单字，BM25 正常（实测 timer 1.94 第 1） | timer 匹配 `"定时"` bigram（`_tokenize('定时')=['定时']`），**不再依赖单字碰撞**（**推断**，排名待实跑） |
| `"文件 压缩 定时"` | file 垄断 top 10，timer 排第 29 被挤出 | file 工具仍强相关，`"定时"` bigram 匹配 timer 类工具；**单字碰撞消失**，timer 排名变化（**推断**，能否进 top10 待实跑确认） |
| `"网络 搜索 http 请求"` | 各词单字碰撞 | `"网络"`/`"搜索"` bigram 精准匹配 network 类（**推断**） |

> **实测补充（v1.1，混合方案时测）**：在 `"文件 压缩 定时"` 上做过 bigram 实验（当时为"单字+bigram"混合），timer 得分 1.94→1.95，仅小幅提升，排名未变。根因是 file 类工具数量多（14 个）、描述中"压缩"相关词密集，BM25 多词累加分数绝对值高。**v1.8 去单字方案需重新实测**：单字碰撞消失后 file 类相关度如何变化待验证。若 timer 仍进不了 top10，需要额外评估（见 §八 风险与缓解）。

### 5.5 无新字段、无新逻辑

- `auto_inject_from_search` 不改，从 `matches` 收集分类
- `searchtool` 返回结构不变（`matches` 仍为 top 10 个工具，`TOOL_SEARCH_INER_RESULTS_TOP=10`）
- **注入行为确认（北京老陈 2026-07-31）**：`searchtool` 成功时，从 `matches`（合计 ≤10 个工具）收集所属分类，注入该分类整类工具给 LLM。此行为保持不变，本方案不改注入逻辑
- 改动点共 4 处：`_tokenize` 中文片段分流（≥2 字 bigram 去单字、=1 字保留）、`_build_tool_search_llm_data`（warning 分支）、`searchtool` 阈值判断（无命中）、`searchtool` 空 token 分支（纯符号），详见 §六

## 六、变更总结

| 改动文件 | 改动位置 | 改动内容 |
|---------|---------|---------|
| `app/tools/fundamental/tool_search.py` | `_tokenize` 中文处理逻辑（原第 27-49 行）| 中文处理改为片段分流：≥2 字生成相邻 bigram（去单字）、=1 字保留单字；英文/数字/下划线路径不变。新增 `chinese_buf` 累积与两处 flush（循环内非中文分支 + 循环末尾），`return tokens` 不变 |
| `app/tools/fundamental/tool_search.py` | `_build_tool_search_llm_data`（第 109-127 行）| 增加 warning 分支：无命中/纯符号时 exec_code=warning，带 detail + hint（根本要求②：失败正确告知 LLM） |
| `app/tools/fundamental/tool_search.py` | `searchtool` 阈值过滤（第 183 行 if 条件处）| 增加"无命中即空"判断：`scored[0]["_score"] > 0` 才计算阈值，否则 `meaningful=[]`，并走 warning 分支（修复无命中 bug，见 §9.3） |
| `app/tools/fundamental/tool_search.py` | `searchtool` 空 token 分支（第 150 行起 `if not query_tokens:`）| 纯符号/空分词查询不再返回全部工具 top10，改为返回空 matches + warning + hint（修复纯符号注入 bug，见 §9.6） |

无新增常量、无新字段、无新函数（bigram 去单字逻辑内联在 `_tokenize` 中，无命中判断内联在 `searchtool` 中，warning 分支内联在 `_build_tool_search_llm_data` 中）。

## 七、回归测试要点

1. `query='定时'` → timer 分类仍命中，且 `_tokenize('定时')=['定时']`（无 '定'/'时' 单字 token）✅
2. `query='压缩'` → `_tokenize('压缩')=['压缩']`，file 类仍 top 10 命中（分数可能变化，需确认相关性不退化）✅
3. `query='网络 搜索 http 请求'` → 多分类命中 ✅
4. 英文查询（`httpget` 等）分数不变 ✅
5. `query='电'`（单字中文）→ `_tokenize('电')=['电']`，单字保留，行为与旧版一致 ✅
6. `auto_inject_from_search` 从 `matches` 收集分类，行为不变；无命中/纯符号时 `matches=[]` → 不注入任何分类 ✅
7. 无新增字段/常量向后兼容 ✅
8. `query='asdfghjklqwerty'`（无命中）→ matches 为空，summary"未匹配到工具"，exec_code=warning，detail+hint 存在，不注入任何分类 ✅
9. `query='zxcvbnm'`（无命中）→ 同上 ✅
10. `query='?'`（纯符号，token 为空）→ matches 为空，exec_code=warning，detail+hint 存在，不注入任何分类 ✅
11. `query='？？？'`（纯符号）→ 同上 ✅
12. `query='a'`（单字母英文，DF=0 无命中）→ matches 为空，exec_code=warning，detail+hint 存在，不注入分类 ✅

## 八、风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| Bigram 改变 BM25 打分分布 | 中 | 大多数查询分数更精准，回归测试覆盖主要场景 |
| 跨词 bigram（如 `件压` 在 `文件压缩` 中）| 低 | 连续中文片段生成的相邻 bigram 含跨词对（如 `文件压缩`→`文件,件压,压缩`），`件压` 在描述中也极少出现，对 DF 影响极小 |
| 语料 token 类型变化（单字→bigram）| 低 | 纯中文描述 N 字 → N-1 bigram，token 数量持平，语料总量仍 KB 级，无性能影响；DF 统计口径变化已由"Bigram 改变打分分布"行覆盖 |
| **去单字后弱匹配能力下降** | **中** | **单字 token 消失后，原本靠单字冗余匹配的弱相关工具（如"压缩"靠 '压'/'缩' 命中多类）将收窄到仅 bigram 命中。需回归实测：①"文件 压缩 定时"下 timer 排名；②单字查询（如"电"）行为不变。若弱分类因此丢失，需报告北京老陈决策（提高 TopK 或分类配额）** |
| **Bigram 提升不足，弱分类仍进不了 top10** | **中高** | **实测 timer 1.94→1.95 排名未变（v1.1 混合方案实测）。v1.8 去单字后需重新实测。若 timer 仍被 `[:10]` 挤出，需启用备选方案：相对阈值过滤后、截断前的分类配额均衡（见 v1.0 废弃方案《searchtool分类配额均衡设计方案》思想，已删档可重写），或提高 `TOOL_SEARCH_INER_RESULTS_TOP`。实施后必须先跑 §七 回归测试确认，不行则报告北京老陈决策** |
| **无命中/纯符号修复边界**：空查询 `query=' '`（纯空格）| 低 | 实测 `query.strip()` 后为空 → 走 `not isinstance(query,str) or not query.strip()` 提前返回 error（tool_search.py:135-138），LLM 获"搜索失败:关键词为空"，行为合理，不受本方案影响 |
| **无命中/纯符号修复边界**：`query='?'`（token 为空）、`query='a'`（DF=0）| 低 | 全部归入"无命中/空分词"统一处理：返回空 matches + warning + hint，不注入分类，LLM 换关键词重搜。实测 `'a'`/`'ab'` DF=0 均为无命中，与 `'asdfghjklqwerty'` 行为一致。§七 回归测试已覆盖 |

## 九、无命中 bug 修复方案

### 9.1 问题（北京老陈驱动发现）

`searchtool` 对完全无命中的查询（如 `'asdfghjklqwerty'`、`'zxcvbnm'`）**报"匹配 63 个"并注入无关分类**，实测：

```
观察: 搜索 'asdfghjklqwerty'成功:匹配 63 个（共 63 个工具）
详情:
  readtext [file]
  writetext [file]
  readmedia [file]
  ...
```

`meaningful[:10]` 全部是 file 类工具 → `auto_inject_from_search` 把 file 整类注入给 LLM。**完全不符合人类思维习惯**：正常人搜不到东西，应得"匹配 0 个/无结果"并提示换关键词，而非错误注入。

### 9.2 根因

`tool_search.py:183` 阈值过滤（仅改第 183 行 if 条件）：

```python
if scored:
    threshold = scored[0]["_score"] * 0.1   # 无命中时最高分=0 → threshold=0
    meaningful = [r for r in scored if r["_score"] >= threshold]  # 0>=0 恒真 → 全部工具过阈值
else:
    meaningful = []
```

无命中时所有工具 `_score=0`，`max_score=0` → `threshold=0` → **63 个工具全部满足 `>= 0`** → `meaningful[:10]` 取前 10 个（恰好全是 file 类）→ summary 报"匹配 63 个"。

### 9.3 修复

**改动 1**：`tool_search.py:183` 增加"最高分>0 才算有命中"判断：

```python
if scored and scored[0]["_score"] > 0:
    threshold = scored[0]["_score"] * 0.1
    meaningful = [r for r in scored if r["_score"] >= threshold]
else:
    meaningful = []
```

**改动 2**：`_build_tool_search_llm_data`（tool_search.py:109-127）增加 warning 分支，无命中时 exec_code=warning、带 detail + hint（**根本要求②：失败正确告知 LLM 并给 hint**）：

```python
if exec_code == "warning":
    return {
        "summary": f"搜索 '{query}'未匹配到工具（共 {total_tools} 个工具）",
        "action": {"tool": "searchtool", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
        "status": {"exec_code": "warning", "message": "搜索完成-未找到匹配工具", "code": "",
                   "detail": "未找到与关键词匹配的工具", "hint": "建议更换关键词后重试，或直接描述你要完成的任务"},
        "duration_ms": duration_ms,
        "metrics": {"matched": {"value": 0, "text": "0个"}, "total": {"value": total_tools, "text": f"{total_tools}个"}},
    }
```

**改动 3**：`searchtool` 无命中时（`meaningful=[]`）改为调用 warning 分支：

```python
if not meaningful:
    duration_ms = int((time.perf_counter() - t0) * 1000)
    llm_data = _build_tool_search_llm_data("warning", duration_ms, query, 0, len(all_tools), [])
    return build_success(data={"matches": []}, llm_data=llm_data)
```

无命中时 `meaningful=[]` → `matches=[]` → `auto_inject_from_search` 见空 matches 直接 return（tool_executor.py:80）→ **不注入任何分类**；exec_code=warning → observation_formatter 显示 hint（formatter:629-636）。

### 9.4 修复后 LLM 观察结果

```
工具执行: 搜索工具 调用工具-searchtool,处理对象-asdfghjklqwerty - 执行结果: 完成-[有警告]
观察: 搜索完成-未找到匹配工具 - 搜索 'asdfghjklqwerty'未匹配到工具（共 63 个工具）
⚠ 警告: 未找到与关键词匹配的工具
建议: 建议更换关键词后重试，或直接描述你要完成的任务
```

（warning + hint 明确告知 LLM，不注入分类，换词重搜——符合人类思维习惯）

### 9.5 与分词修复的关系

- 三个 bug 彼此独立、无依赖：分词 bug 在 `_tokenize`；无命中 bug 与纯符号 bug 均在 `searchtool` 主函数（阈值过滤 / 空 token 分支）
- 一并实施：四处改动均在 `tool_search.py`，同一次回归测试覆盖
- 互补关系：分词修复保证中文词组语义（词不拆字）；无命中/纯符号修复兜底"搜不到/纯符号"场景，避免误导 LLM 与错误注入——两者独立、并行生效

### 9.6 纯符号查询 bug（全文复查补充）

#### 9.6.1 问题

`query='?'`、`query='？？？'` 等**纯符号查询** `_tokenize` 后 token 为空，实测仍返回全部 63 个工具 top10 并注入 6 个分类：

```
观察: 搜索 '?'成功:匹配 63 个（共 63 个工具）
详情:
  analyze_data [dataanalysis]
  calendar [timer]
  clipboard_control [desktop]
  ...
```

与 §9.1 无命中 bug 同类：误导 LLM + 错误注入无关分类。

#### 9.6.2 根因

`tool_search.py:150-165` 的 `if not query_tokens:` 分支（第 150 行起），token 为空时**直接返回全部工具 top10**（按名称排序），summary 报"匹配 63 个"。

#### 9.6.3 修复

将空 token 分支改为返回空 matches + warning（与无命中一致，执行 §9.3 改动 2 的 warning 分支）：

```python
if not query_tokens:
    duration_ms = int((time.perf_counter() - t0) * 1000)
    data = {
        "matches": [],
    }
    llm_data = _build_tool_search_llm_data("warning", duration_ms, query, 0, len(all_tools), [])
    return build_success(data=data, llm_data=llm_data)
```

- `total_matched=0, total_tools=63` → summary"搜索 '?'未匹配到工具（共 63 个工具）"
- `matches=[]` → `auto_inject_from_search` 见空 matches 直接 return，**不注入任何分类**
- **exec_code=warning + detail + hint** → observation_formatter 显示"⚠ 警告"与"建议"（formatter:629-636），LLM 获明确指引（**根本要求②**）
- 原"返回全部工具 top10"路径删除（该路径无查询语义，纯误导）

#### 9.6.4 单字母英文查询说明

实测 `'a'`/`'ab'`：token 非空（`['a']`/`['ab']`），但 DF=0（无工具名/描述含该独立 token）→ `max_score=0` → 走 §9.3 无命中修复，返回空 matches + warning/hint。**单字母英文查询已被 §9.3 覆盖，无需额外处理**。

**编写人**: 小欧 2026-07-31
