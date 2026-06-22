# -*- coding: utf-8 -*-
"""
tool_search — BM25 全文检索搜索工具
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
from app.constants import ERR_DOC_QUERY_EMPTY


def _tokenize(text: str) -> List[str]:
    """中英混合分词：中文按单字切分，英文按词切分，统一小写 — 小沈 2026-06-14"""
    tokens: List[str] = []
    buf: List[str] = []
    for ch in text.lower():
        if '\u4e00' <= ch <= '\u9fff':
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            tokens.append(ch)
        elif ch == '_':
            if buf:
                tokens.append("".join(buf))
                buf.clear()
        elif ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf.clear()
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

    for term in set(query_tokens):
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
            "summary": f"搜索失败: {query}",
            "action": {"tool": "tool_search", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_DOC_QUERY_EMPTY, "detail": "搜索关键词不能为空", "hint": "请输入有效的搜索关键词"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"搜索 '{query}'，匹配 {total_matched} 个工具（共 {total_tools} 个）",
        "action": {"tool": "tool_search", "tool_zh": "搜索工具", "target": query, "params": {"query": query}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"matched": {"value": total_matched, "text": f"{total_matched}个"}, "total": {"value": total_tools, "text": f"{total_tools}个"}},
    }


def tool_search(query: str) -> Dict[str, Any]:
    """按关键词搜索匹配的工具列表（BM25 全文检索） — 小健 2026-06-22 拆分独立文件"""
    t0 = time.perf_counter()
    if not query.strip():
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_tool_search_llm_data("error", duration_ms, query, 0, 0, [])
        return build_error(data={"error_detail": "搜索关键词不能为空", "params": {"query": query}}, llm_data=llm_data)

    all_tools = tool_registry._tools
    if not all_tools:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        data = {
            "query": query,
            "matches": [],
            "total_matched": 0,
            "total_tools": 0,
        }
        llm_data = _build_tool_search_llm_data("success", duration_ms, query, 0, 0, [])
        return build_success(data=data, llm_data=llm_data)

    query_tokens = _tokenize(query.strip())
    if not query_tokens:
        all_items = [
            {
                "name": m.name,
                "category": m.category.value,
                "description": m.description[:200],
                "score": 0,
            }
            for m in all_tools.values()
        ]
        all_items.sort(key=lambda x: x["name"])
        top = all_items[:10]
        duration_ms = int((time.perf_counter() - t0) * 1000)
        data = {
            "query": query, "matches": top,
            "total_matched": len(all_items), "total_tools": len(all_tools),
        }
        llm_data = _build_tool_search_llm_data("success", duration_ms, query, len(all_items), len(all_tools),
                                                 [{"name": r["name"], "category": r["category"]} for r in top])
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
            "description": metadata.description[:200],
            "score": round(scores[i], 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = [r for r in scored if r["score"] > 0][:10]

    duration_ms = int((time.perf_counter() - t0) * 1000)
    data = {
        "query": query,
        "matches": top_results,
        "total_matched": len(scored),
        "total_tools": len(all_tools),
    }
    llm_data = _build_tool_search_llm_data("success", duration_ms, query, len(scored), len(all_tools),
                                             [{"name": r["name"], "category": r["category"]} for r in top_results[:10]])
    return build_success(data=data, llm_data=llm_data)


__all__ = ["tool_search"]