# -*- coding: utf-8 -*-
"""
classify_intent — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第118-201行
"""

import json
from typing import Any, Optional, List, Dict

from app.services.preprocessing.intent_classifier.load_intent_config import load_intent_config
from app.services.preprocessing.intent_classifier.build_intent_prompt import build_intent_prompt
from app.services.preprocessing.intent_classifier.extract_json_balanced import extract_json_balanced
from app.services.llm.client_sdk import create_llm_client

INTENT_CLASSIFIER_CONFIG = load_intent_config()


async def classify_intent(
    text: str,
    labels: List[str],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """拷贝自 intent_classifier.py 第118-201行"""
    _api_key = api_key or INTENT_CLASSIFIER_CONFIG["api_key"]
    _api_base = api_base or INTENT_CLASSIFIER_CONFIG["api_base"]
    _model = model or INTENT_CLASSIFIER_CONFIG["model"]

    prompt = build_intent_prompt(text, labels)

    try:
        _timeout = INTENT_CLASSIFIER_CONFIG.get("timeout", 90)
        client = create_llm_client(
            provider="openai",
            model=_model,
            api_key=_api_key,
            base_url=_api_base,
            timeout=_timeout,
        )
        try:
            data = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
        finally:
            await client.close()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        try:
            if "{" in content and "}" in content:
                json_str = extract_json_balanced(content)
                if json_str is None:
                    raise json.JSONDecodeError("未找到平衡花括号", content, 0)
                result = json.loads(json_str)
                all_intents = result.get("all_intents", {})
                if not isinstance(all_intents, dict) or len(all_intents) == 0:
                    all_intents = {result.get("intent", ""): float(result.get("confidence", 0.0))}
                return {
                    "corrected": result.get("corrected", text),
                    "intent": result.get("intent", ""),
                    "confidence": float(result.get("confidence", 0.0)),
                    "all_intents": all_intents,
                }
        except (json.JSONDecodeError, ValueError):
            pass

        return {
            "corrected": text,
            "intent": "",
            "confidence": 0.0,
            "all_intents": {},
            "error": "Failed to parse LLM response"
        }

    except Exception as e:
        return {
            "corrected": text,
            "intent": "",
            "confidence": 0.0,
            "all_intents": {},
            "error": str(e)
        }
