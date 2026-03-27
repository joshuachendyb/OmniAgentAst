# -*- coding: utf-8 -*-
"""
意图检测模块

使用 LLM（七牛 deepseek-v3.1）进行意图分类
Author: 小沈 - 2026-03-27

注意：意图分类的 LLM 调用独立于此文件，不与主流程的 BaseAIService 混淆
"""

import json
import httpx
import os
from typing import Any, Optional, List, Dict

# ============== 配置加载 ==============

def _load_qiniu_config() -> dict:
    """从配置文件加载七牛 API 配置"""
    import yaml
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(backend_dir))
    backend_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(backend_dir)
    config_path = os.path.join(project_root, "config", "config.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        qiniu_config = config.get("ai", {}).get("qiniu", {})
        return {
            "api_base": qiniu_config.get("api_base", "https://api.qnaigc.com/v1"),
            "api_key": qiniu_config.get("api_key", ""),
            "model": qiniu_config.get("models", ["deepseek-v3.1"])[0],
            "timeout": qiniu_config.get("timeout", 90)
        }
    except Exception:
        return {
            "api_base": "https://api.qnaigc.com/v1",
            "api_key": "",
            "model": "deepseek-v3.1",
            "timeout": 90
        }

INTENT_CLASSIFIER_CONFIG = _load_qiniu_config()


# ============== 意图分类函数 ==============

async def classify_intent(
    text: str,
    labels: List[str],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用 LLM 同时进行文本矫正和意图分类（独立函数，不依赖 BaseAIService）
    
    Args:
        text: 用户输入文本
        labels: 候选意图标签列表，如 ["file", "network", "chat"]
        api_key: API 密钥（可选，默认从配置文件读取）
        api_base: API 地址（可选，默认从配置文件读取）
        model: 模型名称（可选，默认用配置：deepseek-v3.1）
    
    Returns:
        {
            "corrected": "矫正后的文本",
            "intent": "最佳意图",
            "confidence": 0.95,
            "all_intents": {"file": 0.95, "chat": 0.05}
        }
    """
    _api_key = api_key or INTENT_CLASSIFIER_CONFIG["api_key"]
    _api_base = api_base or INTENT_CLASSIFIER_CONFIG["api_base"]
    _model = model or INTENT_CLASSIFIER_CONFIG["model"]
    
    # 同时进行文本矫正和意图分类
    prompt = f"""你是一个文本处理助手。需要完成两个任务：
1. 文本矫正：修正错别字、标点、格式
2. 意图分类：严格按照下面的定义选择意图

意图定义：
- file: 文件操作，包括查看目录、浏览文件、打开磁盘(C盘/D盘/E盘)、打开文件夹、列出文件、读取/保存/删除/复制/移动文件等
- network: 网络操作，包括下载、HTTP请求、API调用、爬虫、抓取网页等
- desktop: 桌面操作，包括截图、截屏、窗口管理、打开应用程序(非文件管理器)、桌面快捷操作等
- chat: 聊天对话，不涉及上述操作的普通对话

用户输入：{text}

直接返回JSON，不要其他内容：
{{"corrected": "矫正后的文本", "intent": "选中的意图标签", "confidence": 0.0-1.0}}"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": _model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1
                }
            )
            
            if response.status_code != 200:
                return {
                    "corrected": text,
                    "intent": "chat",
                    "confidence": 0.5,
                    "all_intents": {},
                    "error": f"API error: {response.status_code}"
                }
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            try:
                if "{" in content and "}" in content:
                    json_str = content[content.find("{"):content.rfind("}")+1]
                    result = json.loads(json_str)
                    return {
                        "corrected": result.get("corrected", text),
                        "intent": result.get("intent", "chat"),
                        "confidence": float(result.get("confidence", 0.5)),
                        "all_intents": {result.get("intent", "chat"): float(result.get("confidence", 0.5))}
                    }
            except (json.JSONDecodeError, ValueError):
                pass
            
            return {
                "corrected": text,
                "intent": "chat",
                "confidence": 0.5,
                "all_intents": {},
                "error": "Failed to parse LLM response"
            }
            
    except Exception as e:
        return {
            "corrected": text,
            "intent": "chat",
            "confidence": 0.5,
            "all_intents": {},
            "error": str(e)
        }


# ============== 意图分类器类 ==============

class IntentClassifier:
    """意图分类器 - 异步版本（同时处理文本矫正和意图分类）"""

    def __init__(self) -> None:
        pass

    async def classify(self, text: str, labels: List[str]) -> Dict[str, Any]:
        """
        异步意图分类（使用 LLM，同时进行文本矫正）
        
        Args:
            text: 用户输入文本
            labels: 候选意图标签列表
        
        Returns:
            {
                corrected: 矫正后的文本,
                intent: 最佳意图,
                confidence: 置信度,
                all_intents: 所有意图及置信度字典
            }
        """
        if not text or not labels:
            return {"corrected": text, "intent": "unknown", "confidence": 0.0, "all_intents": {}}
        
        return await classify_intent(text, labels)

    async def classify_with_llm_async(
        self, 
        text: str, 
        labels: List[str]
    ) -> Dict[str, Any]:
        """使用 LLM 进行意图分类（异步方法，同时文本矫正）"""
        return await classify_intent(text, labels)
