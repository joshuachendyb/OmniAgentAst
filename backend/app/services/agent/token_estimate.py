# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: chars→token 估算收口为唯一实现——refs.budget._tokens_of 与
#   compaction.prune._released_tokens 原各写一份同款单行(DRY 违反), 本轮 5 处调用点改本函数
#   — 小欧-2026-10-30
# 2026-10-30 小欧 落位说明: 与唯一真源 CHARS_PER_TOKEN 同域(services.agent), 引用域本就依赖
#   compaction_constants, 沿同一方向复用; 未放 app/utils 以免 utils 反向依赖 services — 小欧-2026-10-30

"""services.agent.token_estimate — 文本 chars→token 估算唯一实现

口径: token = len(content) / CHARS_PER_TOKEN(向下取整), 系数真源在
  services.agent.compaction_constants(2026-10-25 真实会话标定 2.25 字/token)。

不做的事(SRP): 不数「消息列表」的预算占用。MessageBuilder._estimate_tokens 估算的是
  含 tool_calls 结构开销的消息列表总量(_total_chars 口径), 与本函数输入不同, 不并入。
"""
from app.services.agent.compaction_constants import CHARS_PER_TOKEN


def estimate_tokens(content) -> int:
    """估算文本 content 的 token 数(整数, 向下取整); None/空 → 0。

    str() 兜底: 引用正文恒为 str, 但 compaction 的 tool 消息 content 可能已是非字符串
    历史脏值, 原 _released_tokens 用 str() 兜底, 此处保持同一鲁棒性。
    """
    return int(len(str(content or "")) / CHARS_PER_TOKEN)


__all__ = ["estimate_tokens"]
