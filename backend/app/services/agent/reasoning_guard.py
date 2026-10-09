# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建：空转防御单一 owner，收口 action/answer 两文件 7 处 _consecutive_reasoning_only 直写（不变量照搬 answer_handler 注释：仅 reasoning-only 累加、余者归零）
# 2026-10-09 小欧 北京老陈裁定：reasoning-only 检测到即注入 user 警告，替代原 assistant 推理回灌 — 见 notify_stagnation
"""reasoning_guard — reasoning-only 空转防御（计数单一写者）

作用对象是跨轮空转计数，与 message_builder 同属 LLM 交互层，平铺于 app/services/agent/。
base_agent.py:79 字段初始化保留（外部测试可能直读），本模块为唯一写者。 — 小健 2026-09-05
"""
import logging

logger = logging.getLogger(__name__)

REASONING_ONLY_MAX_ROUNDS = 3  # 小健 2026-09-05：从 answer_handler.py:62 迁移，逐字（连续容忍 3 轮，第 4 轮终止）

STAGNATION_WARNING = (
    "<system-reminder>\n"
    "上一次你只是重复推理而没有采取行动, 下一次响应必须采取行动或者回答\n"
    "</system-reminder>"
)


def note_progress(agent):
    """非 reasoning-only 进展：归零空转计数 — 小健 2026-09-05（收口 6 处归零直写）"""
    agent._consecutive_reasoning_only = 0


def note_reasoning_only(agent):
    """reasoning-only 一轮：累加；超限返回 True（调用方走终止分支） — 小健 2026-09-05（收口唯一 +=1）"""
    agent._consecutive_reasoning_only += 1
    return agent._consecutive_reasoning_only > REASONING_ONLY_MAX_ROUNDS


def notify_stagnation(agent):
    """reasoning-only 检测到即注入 user 警告 — 小欧 2026-10-09（北京老陈裁定）

    替代原 assistant 推理回灌（handle_answer.py:182-188）。删回灌的两个理由：
      ① 模型看不到两条推理 —— 回灌消息带 _temp_ 标记，每轮发送后即被清除（message_builder.py:335-338），
         故模型永远只收到自己上一轮那一条，无法对比是否在重复；
      ② 单条推理可达 20K 字符，回灌既挤占上下文，又可能反向诱导模型继续思考。
    不挂 _temp_：警告常驻上下文，空转期间反复提醒，直到模型采取行动。
    """
    _task = ""
    for _m in agent.message_builder.conversation_history:
        if _m.get("role") == "user":
            _task = _m.get("content") or ""
            break
    agent.message_builder.conversation_history.append({
        "role": "user",
        "content": f"{_task}\n{STAGNATION_WARNING}" if _task else STAGNATION_WARNING,
    })
    logger.warning(
        f"[reasoning_guard] 连续{agent._consecutive_reasoning_only}轮reasoning-only无进展, 已注入user警告"
    )