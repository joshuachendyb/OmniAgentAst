# -*- coding: utf-8 -*-
"""
通用TextStrategy兜底Agent — 小沈 2026-05-25 / 小欧 2026-05-28 从 react_sse_wrapper.py 提取

当 AgentFactory.create 失败时的回退 Agent，直接使用 LLM 文本策略。
"""

from app.services.agent.base_react import BaseAgent


class GenericReactAgent(BaseAgent):
    """通用TextStrategy兜底Agent - 小沈 2026-05-25

    使用场景:
        - _run_sse_stream中AgentFactory.create失败时回退
        - 需要直接使用LLM文本策略的场景

    使用示例:
        strategy = TextStrategy()
        agent = GenericReactAgent(llm_client, task_id, strategy)
    """

    def __init__(self, llm_client, task_id, strategy, **kwargs):
        BaseAgent.__init__(
            self,
            llm_client=llm_client, task_id=task_id, tool_category=None, **kwargs
        )
        self._strategy = strategy

    async def _get_llm_response(self) -> str:
        self.llm_call_count += 1
        if not self._strategy:
            return ""
        last_msg = self.conversation_history[-1]["content"] if self.conversation_history else ""
        history = self.conversation_history[:-1] if len(self.conversation_history) > 1 else []
        return await self._strategy.call(
            llm_client=self.llm_client, message=last_msg,
            history_dicts=history, conversation_history=self.conversation_history,
        )

    def _get_system_prompt(self):
        return "你是一个有用的AI助手，直接回答用户的问题。"

    def _get_task_prompt(self, task, context=None):
        return task
