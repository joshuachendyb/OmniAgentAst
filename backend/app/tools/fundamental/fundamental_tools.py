# -*- coding: utf-8 -*-
"""
Meta 工具实现 - tool_search (BM25 全文检索)
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【2026-05-17 小沈】新建
【2026-06-12 小沈】删除tool_help/pipeline(YAGNI,FC Schema已覆盖),仅保留tool_search
【2026-06-14 小欧】替换简单关键词评分为 BM25 全文检索，中英混合分词
"""

import math
from collections import Counter
from typing import Dict, Any, List, Tuple

from app.tools.registry import tool_registry
from app.utils.tool_result_formatter import (
    truncate_data_for_frontend,
)
from app.tools.tool_response import build_success, build_error


# ── 分词 ──────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """中英混合分词：中文按单字切分，英文按词切分，统一小写"""
    tokens: List[str] = []
    buf: List[str] = []
    for ch in text.lower():
        if '\u4e00' <= ch <= '\u9fff':
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            tokens.append(ch)
        elif ch == '_':
            # 下划线作为分词分隔符，把复合词拆分
            # 例如 "search_files" → ["search", "files"]
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


# ── BM25 核心 ─────────────────────────────────────────────────────

def _build_bm25() -> Tuple[List[List[str]], List[str], float, Counter]:
    """从工具注册表构建 BM25 语料库

    Returns:
        (tokenized_docs, tool_names, avgdl, df)
    """
    docs: List[List[str]] = []
    tool_names: List[str] = []
    for name, metadata in tool_registry._tools.items():
        # name 重复 3 次以提升名称匹配权重
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
    """计算 BM25 分数（Okapi BM25）"""
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


# ── 公开工具 ──────────────────────────────────────────────────────

def tool_search(query: str) -> Dict[str, Any]:
    """
    按关键词搜索匹配的工具列表（BM25 全文检索）。

    Args:
        query: 自然语言描述需求

    Returns:
        匹配的工具列表
    """
    if not query.strip():
        return build_error(ERR_DOC_QUERY_EMPTY, "搜索关键词不能为空", data={"query": query})

    all_tools = tool_registry._tools
    if not all_tools:
        data = truncate_data_for_frontend({
            "query": query,
            "matches": [],
            "total_matched": 0,
            "total_tools": 0,
        })
        return build_success(data, "系统暂无可用工具", llm_data={
            "query": query, "matches": [], "total_matched": 0,
        })

    query_tokens = _tokenize(query.strip())
    if not query_tokens:
        # 查询全是标点之类不可分词的内容 → 显示所有工具
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
        data = truncate_data_for_frontend({
            "query": query, "matches": top,
            "total_matched": len(all_items), "total_tools": len(all_tools),
        })
        return build_success(
            data, f"未解析出有效关键词，列出全部 {len(all_items)} 个工具",
            llm_data={
                "query": query,
                "matches": [{"name": r["name"], "category": r["category"]} for r in top],
                "total_matched": len(all_items),
            },
        )

    docs, tool_names, avgdl, df = _build_bm25()
    scores = _bm25_scores(query_tokens, docs, avgdl, df)

    # 组装结果
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

    data = truncate_data_for_frontend({
        "query": query,
        "matches": top_results,
        "total_matched": len(scored),
        "total_tools": len(all_tools),
    })

    llm_data = {
        "query": query,
        "matches": [{"name": r["name"], "category": r["category"]} for r in top_results[:10]],
        "total_matched": len(scored),
    }

    return build_success(
        data,
        f"找到 {len(scored)} 个相关工具，返回前 {len(top_results)} 个",
        llm_data=llm_data,
    )


__all__ = ["tool_search"]

from app.constants import ERR_DOC_QUERY_EMPTY
