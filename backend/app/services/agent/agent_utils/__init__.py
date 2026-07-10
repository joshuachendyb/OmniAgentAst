# -*- coding: utf-8 -*-
"""
Agent层公共工具函数目录

【公共函数规范】
本目录是Agent层的公共utility模块,所有Agent层公共函数必须在此目录下定义。
禁止在业务代码中重复定义公共函数。
调用方统一从此处导入:from app.services.agent.agent_utils.xxx import yyy

目录结构:
- build_observation_text(来自 observation_formatter): 工具结果格式化
- fc_message_types.py: FC协议消息Pydantic模型

Author: 小沈 - 2026-05-28
更新: 小健 2026-06-17 删除tool_result_factory(三层→两层简化)
更新: 小欧 2026-07-10 message_utils.py合并入observation_formatter.py
"""

from app.services.agent.observation_formatter import (
    build_observation_text,
)

__all__ = [
    "build_observation_text",
]
