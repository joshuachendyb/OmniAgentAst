# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建：空转防御单一 owner，收口 action/answer 两文件 7 处 _consecutive_reasoning_only 直写（不变量照搬 answer_handler 注释：仅 reasoning-only 累加、余者归零）
"""reasoning_guard — reasoning-only 空转防御（计数单一写者）

作用对象是跨轮空转计数，与 message_builder 同属 LLM 交互层，平铺于 app/services/agent/。
base_agent.py:79 字段初始化保留（外部测试可能直读），本模块为唯一写者。 — 小健 2026-09-05
"""

REASONING_ONLY_MAX_ROUNDS = 3  # 小健 2026-09-05：从 answer_handler.py:62 迁移，逐字（连续容忍 3 轮，第 4 轮终止）


def note_progress(agent):
    """非 reasoning-only 进展：归零空转计数 — 小健 2026-09-05（收口 6 处归零直写）"""
    agent._consecutive_reasoning_only = 0


def note_reasoning_only(agent):
    """reasoning-only 一轮：累加；超限返回 True（调用方走终止分支） — 小健 2026-09-05（收口唯一 +=1）"""
    agent._consecutive_reasoning_only += 1
    return agent._consecutive_reasoning_only > REASONING_ONLY_MAX_ROUNDS