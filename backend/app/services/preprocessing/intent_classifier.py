# -*- coding: utf-8 -*-
"""
意图检测模块

阶段2: LLM语义分类器（设计文档 v1.5 §3.1.2）
使用 LLM（七牛 deepseek-v3.1）进行意图分类，返回完整置信度分布。
Author: 小沈 - 2026-03-27
Updated: 小沈 - 2026-04-30（支持多意图置信度分布）

注意：意图分类的 LLM 调用独立于此文件，不与主流程的 BaseAIService 混淆

====================================================================
为什么硬编码使用七牛的 deepseek-v3.1？
====================================================================
1. 意图分类是一个轻量级的辅助功能，不需要使用主聊天的大模型
2. deepseek-v3.1 是一个性价比很高的模型，适合快速分类任务
3. 独立配置可以避免意图分类失败时影响主聊天功能
4. 这样设计可以让意图分类的配置与主聊天配置解耦
====================================================================
"""

import json
import httpx
import os
from typing import Any, Optional, List, Dict

# ============== 配置加载 ==============
# 【修复 2026-04-20 小沈】意图分类器使用固定模型，不受用户切换AI影响
# 问题原因：之前从config读取qiniu.models[0]，切换AI会导致意图分类器模型变化

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
            # 【修复】使用固定的deepseek-v3.1，不受切换AI影响
            "model": "deepseek-v3.1",
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

# ============== 意图定义（从labels动态生成）==============

_INTENT_DEFINITIONS = {
    "file": "文件操作，包括查看目录、浏览文件、打开磁盘(C盘/D盘/E盘)、打开文件夹、列出文件、读取/保存/删除/复制/移动文件等",
    "shell": "命令执行，包括运行npm/pip/git/docker等命令行工具、执行脚本、编译代码、运行程序等",
    "time": "时间日期，包括查询当前时间、格式化日期、计算时间差、设置定时器、时区转换、检查周末/假日等",
    "network": "网络操作，包括ping/curl/wget/ssh等网络工具、端口扫描、HTTP请求、API调用、下载文件、FTP操作等",
    "desktop": "桌面操作，包括截图、截屏、窗口管理、打开应用程序、模拟按键、鼠标点击等",
    "env": "环境变量，包括查看/设置PATH、HOME、TEMP等系统环境变量、系统变量配置等",
    "system": "系统信息，包括查询CPU/内存/磁盘/进程/服务等系统资源、系统配置查看等",
    "database": "数据库操作，包括SQL查询、select/insert/update/delete等数据库命令、表结构操作等",
    "chat": "普通对话，不涉及上述任何特定操作的日常聊天、问答、解释等",
}


def _build_intent_prompt(text: str, labels: List[str]) -> str:
    """根据labels动态构建意图分类prompt"""
    definitions_lines = []
    for label in labels:
        if label in _INTENT_DEFINITIONS:
            definitions_lines.append(f"- {label}: {_INTENT_DEFINITIONS[label]}")

    definitions_str = "\n".join(definitions_lines)

    return f"""你是一个文本处理助手。需要完成两个任务：
1. 文本矫正：修正错别字、标点、格式
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
        model: 模型名称（可选，默认用配置：deepseek-v3.1）

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
                    all_intents = result.get("all_intents", {})
                    if not isinstance(all_intents, dict) or len(all_intents) == 0:
                        all_intents = {result.get("intent", "chat"): float(result.get("confidence", 0.5))}
                    return {
                        "corrected": result.get("corrected", text),
                        "intent": result.get("intent", "chat"),
                        "confidence": float(result.get("confidence", 0.5)),
                        "all_intents": all_intents,
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
