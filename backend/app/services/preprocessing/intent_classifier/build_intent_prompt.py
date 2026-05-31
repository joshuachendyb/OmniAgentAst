# -*- coding: utf-8 -*-
"""
build_intent_prompt — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第59-113行
"""

from typing import List, Dict

from app.services.intents.intent_mapper import get_aliases_for_intent, IntentType

_INTENT_DESCRIPTIONS = {
    "file": "文件操作，包括查看目录、浏览文件、打开磁盘(C盘/D盘/E盘)、打开文件夹、列出文件、读取/保存/删除/复制/移动文件等",
    "system": "系统操作，包括命令执行(npm/pip/git/docker)、时间日期、环境变量、系统信息(CPU/内存/磁盘/进程/服务)、代码执行等",
    "network": "网络操作，包括ping/curl/wget/ssh等网络工具、端口扫描、HTTP请求、API调用、下载文件、FTP操作等",
    "desktop": "桌面操作，包括截图、截屏、窗口管理、打开应用程序、模拟按键、鼠标点击等",
    "document": "文档读写和数据库，包括读取/创建/编辑docx、pdf、txt、md等文档文件、SQL查询、数据库操作等",
}

_INTENT_DEFINITIONS = {}
for intent_type in IntentType:
    intent_name = intent_type.value
    _INTENT_DEFINITIONS[intent_name] = _INTENT_DESCRIPTIONS.get(intent_name, f"{intent_name}操作")
    for alias in get_aliases_for_intent(intent_type):
        _INTENT_DEFINITIONS[alias] = f"（已合并到{intent_name}）" + _INTENT_DESCRIPTIONS.get(intent_name, f"{intent_name}操作")


def build_intent_prompt(text: str, labels: List[str]) -> str:
    """拷贝自 intent_classifier.py 第94-113行"""
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
