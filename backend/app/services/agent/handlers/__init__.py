# -*- coding: utf-8 -*-
"""
handlers — ReAct循环业务处理器

从react_cycle.py拆分，每个处理器职责单一

Author: 小沈 - 2026-06-09
"""
from .action_handler import handle_action
from .handle_answer import handle_answer  # 2026-09-05 小健：answer_handler改名handle_answer(10.3第一阶段)，老名消亡不留垫片

__all__ = [
    "handle_action",
    "handle_answer",
]
