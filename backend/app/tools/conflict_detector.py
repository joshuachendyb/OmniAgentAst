# -*- coding: utf-8 -*-
# 编辑历史: 2026-09-03 小欧 - 新建: 冲突检测三函数下沉，解耦 action_handler - 小欧-2026-09-03
# 编辑历史: 2026-09-04 小健 - 修正: 复用 trust._parse_paths，禁止重写简化退化 - 小健-2026-09-04
# 编辑历史: 2026-09-04 小健 - 修正: trust_utils已合并为trust.py，import路径同步更新 - 小健-2026-09-04
from typing import Dict, List
from app.tools.trust import _parse_paths

def _has_conflict(calls: List[Dict]) -> bool:
    """完整复制自 action_handler.py:590-621，复用 _parse_paths"""
    from collections import Counter
    names = [c.get("tool_name","") for c in calls]
    if len(names) != len(set(names)):
        cnt = Counter(names)
        if any(v >= 2 and ("edit" in k or "write" in k or "delete" in k) for k,v in cnt.items()):
            return True
    paths = {}
    for c in calls:
        for p in _parse_paths(c.get("tool_name",""), c.get("tool_params",{})):
            paths.setdefault(p, 0)
            paths[p] += 1
            if paths[p] >= 2:
                return True
    return False

def _partition_calls(calls: List[Dict]) -> List[List[Dict]]:
    """完整复制自 action_handler.py:623-655，复用 _parse_paths"""
    parent = list(range(len(calls)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a,b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for i in range(len(calls)):
        for j in range(i+1, len(calls)):
            pi = _parse_paths(calls[i].get("tool_name",""), calls[i].get("tool_params",{}))
            pj = _parse_paths(calls[j].get("tool_name",""), calls[j].get("tool_params",{}))
            if pi & pj or calls[i].get("tool_name")==calls[j].get("tool_name"):
                union(i,j)
    groups: Dict[int, List[Dict]] = {}
    for idx, c in enumerate(calls):
        r = find(idx)
        groups.setdefault(r, []).append(c)
    return list(groups.values())
