# -*- coding: utf-8 -*-
"""
预处理流水线模块

【2026-04-30 小沈修改】移除LLM分类器调用，改为纯文本预处理
意图检测已统一由 chat_router.route_with_fallback() 的两阶段逻辑处理
"""
from typing import Any, List
from app.utils.logger import logger


class PreprocessingPipeline:
    """用户输入预处理流水线（纯文本处理，不含LLM调用）"""

    async def process(
        self,
        user_input: str,
        intent_labels: List[str],
        session_id: str = ""
    ) -> dict[str, Any]:
        """
        预处理用户输入（纯文本处理，不含LLM）

        【2026-04-30 小沈修改】移除了IntentClassifier的LLM调用。
        意图检测已统一由 chat_router.route_with_fallback() 处理。

        Returns:
            dict: {original, corrected, errors, intent, confidence, all_intents}
        """
        session_tag = f"[session={session_id}]" if session_id else "[session=N/A]"

        # 基本文本清理（白名单+编码修复）
        corrected = user_input.strip()
        errors = []

        logger.info(
            f"[Preprocessing] {session_tag} - input: '{user_input}', "
            f"corrected: '{corrected}'"
        )

        return {
            "original": user_input,
            "corrected": corrected,
            "errors": errors,
            "intent": "unknown",
            "confidence": 0.0,
            "all_intents": {},
        }
