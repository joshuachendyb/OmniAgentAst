# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 去噪 refactor:
#   1. 移除非BM25路径 data 中
#     total_matched/total_tools 重复字段
#   2. BM25 路径同样移除(data/llm_data重复)
# 2026-07-25 - 小欧 - 截断治理: all_items[:10]/meaningful[:10] → TOOL_SEARCH_INER_RESULTS_TOP 命名常量
# 2026-07-28 - 北京老陈 - BM25查询token去重优化(ordered unique代替set)
# 2026-08-05 - 小欧 - 实施《searchtool分词修复设计方案 v1.8》(共4处改动):
#   1. _tokenize 中文片段分流: ≥2字只生成bigram去单字, =1字保留单字(词不拆字)
#   2. _build_tool_search_llm_data 增加 warning 分支(无命中/纯符号: detail+hint)
#   3. searchtool 阈值过滤增加无命中判断(scored[0]["_score"]>0), 无命中返回空matches+warning
#   4. searchtool 空token分支(纯符号)不再返回全部工具top10, 返回空matches+warning
# 2026-08-07 - 小欧 - searchtool结果选取增加"分类级名额保底"(_apply_category_floor):
#   修复多类型混合搜索时高分类霸占top10名额, 低分分类被挤出导致一次搜索注不全分类(实测7类型混合仅命中4类)
"""
searchtool — BM25 全文检索搜索工具
【2026-06-22 小健】从 fundamental_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import math
import time
from collections import Counter
from typing import Dict, Any, List, Tuple

from app.tools.registry import tool_registry
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_DOC_QUERY_EMPTY, TOOL_SEARCH_INER_RESULTS_TOP


def _tokenize(text: str) -> List[str]:
    """中英混合分词：中文按词组切分，英文按词切分，统一小写 — 小沈 2026-06-14
    小欧 2026-08-05 修复: 中文≥2字只生成bigram去单字; =1字保留单字(词不拆字)
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
                # 中文片段收尾: ≥2字生成bigram, =1字保留单字 — 小欧 2026-08-05
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
        # 中文片段收尾: ≥2字生成bigram, =1字保留单字 — 小欧 2026-08-05
        if len(chinese_buf) >= 2:
            for i in range(len(chinese_buf) - 1):
                tokens.append(chinese_buf[i] + chinese_buf[i + 1])
        else:
            tokens.append(chinese_buf[0])
    if buf:
        tokens.append("".join(buf))
    return tokens


def _build_bm25() -> Tuple[List[List[str]], List[str], float, Counter]:
    """从工具注册表构建 BM25 语料库 — 小沈 2026-06-14"""
    docs: List[List[str]] = []
    tool_names: List[str] = []
    for name, metadata in tool_registry._tools.items():
        text = " ".join([name] * 3) + " " + metadata.description
        docs.append(_tokenize(text))
        tool_names.append(name)

    N = len(docs)
    avgdl = sum(len(d) for d in docs) / max(N, 1)

    df: Counter = Counter()
    for doc in docs:
        for term in set(doc):
            df[term] += 1

    return docs, tool_names, avgdl, df


def _bm25_scores(
    query_tokens: List[str],
    docs: List[List[str]],
    avgdl: float,
    df: Counter,
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    """计算 BM25 分数（Okapi BM25） — 小沈 2026-06-14"""
    N = len(docs)
    if N == 0:
        return []

    doc_tfs = [Counter(d) for d in docs]
    scores = [0.0] * N

    unique_terms = []
    seen_terms = set()
    for term in query_tokens:
        if term not in seen_terms:
            seen_terms.add(term)
            unique_terms.append(term)
    for term in unique_terms:
        n = df.get(term, 0)
        if n == 0:
            continue
        idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
        for i in range(N):
            tf = doc_tfs[i].get(term, 0)
            if tf == 0:
                continue
            doc_len = len(docs[i])
            scores[i] += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avgdl))

    return scores


def _build_tool_search_llm_data(exec_code: str, duration_ms: int, query: str,
                                 total_matched: int, total_tools: int,
                                 matches: list) -> dict:
    """tool_search的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"搜索工具失败:关键词为空",
            "action": {"tool": "searchtool", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_DOC_QUERY_EMPTY, "detail": "搜索关键词不能为空", "hint": "请输入有效的搜索关键词"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        # 无命中/纯符号: 正确告知LLM + hint, 避免误导LLM与错误注入 — 小欧 2026-08-05
        return {
            "summary": f"搜索 '{query}'未匹配到工具（共 {total_tools} 个工具）",
            "action": {"tool": "searchtool", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
            "status": {"exec_code": "warning", "message": "搜索完成-未找到匹配工具", "code": "",
                       "detail": "未找到与关键词匹配的工具", "hint": "建议更换关键词后重试，或直接描述你要完成的任务"},
            "duration_ms": duration_ms,
            "metrics": {"matched": {"value": 0, "text": "0个"}, "total": {"value": total_tools, "text": f"{total_tools}个"}},
        }
    return {
        "summary": f"搜索 '{query}'成功:匹配 {total_matched} 个（共 {total_tools} 个工具）",
        "action": {"tool": "searchtool", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"matched": {"value": total_matched, "text": f"{total_matched}个"}, "total": {"value": total_tools, "text": f"{total_tools}个"}},
    }


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


def searchtool(query: str) -> Dict[str, Any]:
    """按关键词搜索匹配的工具列表（BM25 全文检索） — 小健 2026-06-22 拆分独立文件
    小欧 2026-07-04 修复: 增加None/类型校验防止崩溃
    """
    t0 = time.perf_counter()
    if not isinstance(query, str) or not query.strip():
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_tool_search_llm_data("error", duration_ms, query, 0, 0, [])
        return build_error(data={}, llm_data=llm_data)

    all_tools = tool_registry._tools
    if not all_tools:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        data = {
            "matches": [],
        }
        llm_data = _build_tool_search_llm_data("success", duration_ms, query, 0, 0, [])
        return build_success(data=data, llm_data=llm_data)

    query_tokens = _tokenize(query.strip())
    if not query_tokens:
        # 纯符号/空分词(如 '?'/'？？？'/'___'): token为空无查询语义, 不再返回全部工具top10,
        # 返回空matches + warning(detail+hint), 不注入任何分类 — 小欧 2026-08-05
        duration_ms = int((time.perf_counter() - t0) * 1000)
        data = {
            "matches": [],
        }
        llm_data = _build_tool_search_llm_data("warning", duration_ms, query, 0, len(all_tools), [])
        return build_success(data=data, llm_data=llm_data)

    docs, tool_names, avgdl, df = _build_bm25()
    scores = _bm25_scores(query_tokens, docs, avgdl, df)

    scored: List[Dict[str, Any]] = []
    for i, name in enumerate(tool_names):
        metadata = all_tools.get(name)
        if not metadata:
            continue
        scored.append({
            "name": metadata.name,
            "category": metadata.category.value,
            "_score": round(scores[i], 4),
        })

    scored.sort(key=lambda x: x["_score"], reverse=True)
    # P1-1修复 2026-06-23 小欧: 相对阈值过滤,只保留分数>=最高分10%的结果
    # 2026-08-05 小欧 无命中修复: 完全无命中时max_score=0→threshold=0→全部工具过阈值,
    # 须先判"最高分>0"才计算阈值, 否则meaningful=[] (修复误报"匹配63个"并错误注入)
    if scored and scored[0]["_score"] > 0:
        threshold = scored[0]["_score"] * 0.1
        meaningful = [r for r in scored if r["_score"] >= threshold]
    else:
        meaningful = []
    top_results = _apply_category_floor(meaningful, TOOL_SEARCH_INER_RESULTS_TOP)

    if not meaningful:
        # 无命中: 空matches + warning(detail+hint), auto_inject_from_search见空直接return不注入 — 小欧 2026-08-05
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_tool_search_llm_data("warning", duration_ms, query, 0, len(all_tools), [])
        return build_success(data={"matches": []}, llm_data=llm_data)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    # =============================================================================
    # 数据设计：total_matched/total_tools 从 data 移除，通过 llm_data.metrics 传入 summary
    # summary 示例: "搜索 'xxx'，匹配 X 个工具（共 Y 个）"
    # — 小欧 2026-07-06 18:46:13
    # =============================================================================
    # data.matches已精简为仅name+category，LLM仅需知道"搜到了/没搜到"，
    # 工具详情感知由auto_inject_from_search自动注入整个分类 — 北京老陈 2026-06-26
    data = {
        "matches": [{"name": r["name"], "category": r["category"]} for r in top_results],
    }
    llm_data = _build_tool_search_llm_data("success", duration_ms, query, len(meaningful), len(all_tools),
                                             [{"name": r["name"], "category": r["category"]} for r in top_results])
    # ---- observation_formatter route -------------------------------------------
    # branch: #9 matches (searchtool subtype)
    # trigger: "matches" in data → ms[0] 含 "category" 键
    # handler: _format_searchtool_results(ms)
    # file:    observation_formatter.py:152-178
    # ------------------------------------------------------------------------------
    return build_success(data=data, llm_data=llm_data)


__all__ = ["searchtool"]
