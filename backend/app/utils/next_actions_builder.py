# -*- coding: utf-8 -*-
"""
next_actions_builder — 构建"下一步推荐操作"列表

从 tool_result_formatter.py 移出，SRP: 构建操作建议 vs 格式化结果
Author: 小欧 - 2026-06-08
"""


def build_next_actions(actions: list) -> list:
    """构建next_actions列表,§11.3 P15返回值自解释规范 小沈-2026-05-19

    每个action格式: (tool, description, when[, params])
    - tool: 推荐调用的工具名(str)
    - description: 人类可读说明(str)
    - when: 触发条件(str)
    - params: 建议参数(dict, 可选)

    用法:
        na = build_next_actions([
            ("analyze_data", "对这些数据进行统计分析", "需要统计平均值、最大值、最小值时"),
            ("filter_data", "筛选特定条件的数据", "需要按条件过滤时", {"column": "age"}),
        ])
        return {"code": "SUCCESS", "data": {...}, "message": "...", "next_actions": na}
    """
    result = []
    for item in actions:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        entry = {
            "tool": item[0],
            "description": item[1],
            "when": item[2],
        }
        if len(item) >= 4 and isinstance(item[3], dict):
            entry["params"] = item[3]
        result.append(entry)
    return result


__all__ = ["build_next_actions"]
