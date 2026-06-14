"""
测试日志标记工具

用于在 app.log 中注入结构化测试标记,便于后续验证对比分析。

用法:
    from app.utils.test_marker import mark_test_round
    
    mark_test_round(1, 3, "test_steps.py::test_meta_step_create")
    # → app.log 输出: [TEST] Round 1/3 — test_steps.py::test_meta_step_create

创建时间: 2026-06-13
编写人: 小沈
"""

from app.utils.logger import logger


def mark_test_round(round_num: int, total_rounds: int, description: str = ""):
    """
    标记测试轮次,在 app.log 中输出 [TEST] 结构化日志

    Args:
        round_num: 当前轮次 (1-based)
        total_rounds: 总轮次
        description: 本轮测试描述,如"test_steps.py 全量"
    """
    tag = f"[TEST] Round {round_num}/{total_rounds}"
    if description:
        tag += f" — {description}"
    logger.info(tag)
