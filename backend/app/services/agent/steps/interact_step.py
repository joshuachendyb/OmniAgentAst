# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-19 小欧 - 新建 interact_step: 通用双向交互事件(agent↔用户)的 step 载体,
#   承载 interaction_id/kind/event/payload 四字段(content 走基类 get_content);
#   question 为第一个使用者, 框架不认识任何 tool 的特殊语义(全在 payload) — 小欧-2026-11-19
# 2026-11-19 小欧 - 字段精简: phase+outcome 合并为单一 event(ask/answered/cancelled/expired),
#   event 为叶子语义, 一条消息说清"发生了什么"; 具体结果值在 payload — 小欧-2026-11-19

from typing import Any, Dict, Optional

from .base import ReasoningStep


class InteractStep(ReasoningStep):
    """通用双向交互事件 step — agent 与用户的交互(问询/确认/选择...), 有来有往可多轮。

    字段契约(框架级, 不认识任何 tool 特殊语义):
      - interaction_id: 交互标识; 同 id=多轮关联, 不同 id=独立交互(调用方决定, 框架不预设)
      - kind: 交互种类(question/confirm/...), 各 tool 自填
      - event: 这条消息发生了什么(ask=发起 / answered=成功响应 / cancelled=放弃 / expired=超时),
        四态通用; 各 tool 的具体结果值(如 confirm 的 rejected)放 payload
      - payload: 各 tool 特殊内容(questions/backend_timeout/具体结果...), 完全开放, 框架零解释

    question 是第一个使用者(见 question_gateway); 后续交互 tool 复用本 step, 只填自己的 kind/payload。
    """

    TYPE: str = "interact"

    def __init__(
        self,
        step: int,
        *,
        interaction_id: str,
        kind: str,
        event: str,
        content: str = "",
        payload: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._interaction_id = interaction_id
        self._kind = kind
        self._event = event
        self._content = content
        self._payload = payload or {}

    def get_content(self) -> str:
        """人可读文案(事件列表显示)"""
        return self._content

    @property
    def interaction_id(self) -> str:
        return self._interaction_id

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def event(self) -> str:
        return self._event

    @property
    def payload(self) -> Dict[str, Any]:
        return self._payload

    def _extra_fields(self) -> Dict[str, Any]:
        """序列化: 交互字段下发前端(SSE); payload 仅有值时输出, 避免空字段噪声"""
        result: Dict[str, Any] = {
            "interaction_id": self._interaction_id,
            "kind": self._kind,
            "event": self._event,
        }
        if self._payload:
            result["payload"] = self._payload
        return result
