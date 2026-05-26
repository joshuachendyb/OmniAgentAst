# -*- coding: utf-8 -*-
"""
意图检测模块

阶段2: LLM语义分类器（设计文档 v1.5 §3.1.2）
使用 LLM（ollama cloud gemma3:4b）进行意图分类，返回完整置信度分布。
Author: 小沈 - 2026-03-27
Updated: 小沈 - 2026-05-23（七牛 deepseek-v3.1 → ollama cloud gemma3:4b，快37倍）

注意：意图分类的 LLM 调用独立于此文件，不与主流程的 BaseAIService 混淆

====================================================================
为什么使用 ollama cloud 的 gemma3:4b？
====================================================================
1. 意图分类是轻量级辅助功能，不需要大模型
2. gemma3:4b 实测 1.5s，比七牛 deepseek-v3.1（55.8s）快37倍
3. 独立配置可以避免意图分类失败时影响主聊天功能
4. 这样设计可以让意图分类的配置与主聊天配置解耦
====================================================================
"""

import json
import httpx
import os
from typing import Any, Optional, List, Dict

from app.constants import DEFAULT_LLM_TIMEOUT
from app.services.intents.crss_scorer import INTENT_NAMES




# ============== 配置加载 ==============
# 【修复 2026-04-20 小沈】意图分类器使用固定模型，不受用户切换AI影响

_DEFAULT_INTENT_MODEL = "gemma3:4b"
_DEFAULT_OLLAMA_API_BASE = "https://ollama.com/v1"
# 问题原因：之前从config读取qiniu.models[0]，切换AI会导致意图分类器模型变化

def _load_intent_config() -> dict:
    """从配置文件加载 ollama cloud API 配置（用于意图分类）"""
    import yaml
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(backend_dir))
    backend_dir = os.path.dirname(backend_dir)
    project_root = os.path.dirname(backend_dir)
    config_path = os.path.join(project_root, "config", "config.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        oc_config = config.get("ai", {}).get("ollamacloud", {})
        oc_models = oc_config.get("models", [])
        fallback_model = oc_models[0] if oc_models else _DEFAULT_INTENT_MODEL
        return {
            "api_base": oc_config.get("api_base", _DEFAULT_OLLAMA_API_BASE),
            "api_key": oc_config.get("api_key", ""),
            "model": oc_config.get("intent_model", fallback_model),
            "timeout": oc_config.get("timeout", DEFAULT_LLM_TIMEOUT)
        }
    except Exception:
        return {
            "api_base": _DEFAULT_OLLAMA_API_BASE,
            "api_key": "",
            "model": _DEFAULT_INTENT_MODEL,
            "timeout": DEFAULT_LLM_TIMEOUT
        }

INTENT_CLASSIFIER_CONFIG = _load_intent_config()

# ============== 意图定义 ==============
# 主意图类型从crss_scorer.INTENT_NAMES获取（单一来源）
# 描述文本在此维护（LLM prompt用自然语言，与crss_scorer的regex关键词不同）

_INTENT_DESCRIPTIONS = {
    "file": "文件操作，包括查看目录、浏览文件、打开磁盘(C盘/D盘/E盘)、打开文件夹、列出文件、读取/保存/删除/复制/移动文件等",
    "system": "系统操作，包括命令执行(npm/pip/git/docker)、时间日期、环境变量、系统信息(CPU/内存/磁盘/进程/服务)、代码执行等",
    "network": "网络操作，包括ping/curl/wget/ssh等网络工具、端口扫描、HTTP请求、API调用、下载文件、FTP操作等",
    "desktop": "桌面操作，包括截图、截屏、窗口管理、打开应用程序、模拟按键、鼠标点击等",
    "document": "文档读写和数据库，包括读取/创建/编辑docx、pdf、txt、md等文档文件、SQL查询、数据库操作等",
}

# 已合并的旧意图别名（保留向后兼容）
_INTENT_ALIASES = {
    "shell": "（已合并到system）命令执行操作",
    "meta": "（已合并到system）时间日期和元信息",
    "time": "（已合并到system）时间日期操作",
    "environment": "（已合并到system）环境变量操作",
    "env": "（已合并到system）环境变量操作",
    "database": "（已合并到document）数据库操作",
    "code_execution": "（已合并到system）代码执行操作",
}

_INTENT_DEFINITIONS = {
    name.lower(): _INTENT_DESCRIPTIONS.get(name.lower(), f"{name}操作")
    for name in INTENT_NAMES
}
_INTENT_DEFINITIONS.update(_INTENT_ALIASES)


def _extract_json_balanced(content: str) -> Optional[str]:
    """使用平衡花括号提取JSON字符串，正确处理嵌套JSON - 小健 2026-05-13"""
    start = content.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start:i + 1]
    return None


def _build_intent_prompt(text: str, labels: List[str]) -> str:
    """根据labels动态构建意图分类prompt"""
    definitions_lines = []
    for label in labels:
        if label in _INTENT_DEFINITIONS:
            definitions_lines.append(f"- {label}: {_INTENT_DEFINITIONS[label]}")

    definitions_str = "\n".join(definitions_lines)

    return f"""你是一个意图分类助手。需要完成两个任务：
1. 文本矫正：仅修正明显的错别字和标点错误。严禁纠正：专有名词、人名、地名、文件名、路径、技术术语、缩写、非中文词汇。如无法判断是否为错别字，保持原样。
2. 意图分类：分析用户意图，返回所有候选意图的置信度分布

意图定义：
{definitions_str}

用户输入：{text}

请输出JSON，不要其他内容：
{{"corrected": "矫正后的文本", "intent": "最佳意图标签", "confidence": 0.0-1.0, "all_intents": {{"意图标签1": 置信度, "意图标签2": 置信度, ...}}}}"""


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
        model: 模型名称（可选，默认用配置：gemma3:4b）

    Returns:
        {
            "corrected": "矫正后的文本",
            "intent": "最佳意图",
            "confidence": 0.95,
            "all_intents": {"file": 0.85, "chat": 0.10, "network": 0.05, ...}
        }
    """
    _api_key = api_key or INTENT_CLASSIFIER_CONFIG["api_key"]
    _api_base = api_base or INTENT_CLASSIFIER_CONFIG["api_base"]
    _model = model or INTENT_CLASSIFIER_CONFIG["model"]

    prompt = _build_intent_prompt(text, labels)

    try:
        _timeout = INTENT_CLASSIFIER_CONFIG.get("timeout", 90)  # 【修复 2026-04-30 小沈】用配置的timeout，默认90s
        async with httpx.AsyncClient(timeout=_timeout) as client:
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
                    "intent": "",
                    "confidence": 0.0,
                    "all_intents": {},
                    "error": f"API error: {response.status_code}"
                }

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            try:
                if "{" in content and "}" in content:
                    json_str = _extract_json_balanced(content)
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
