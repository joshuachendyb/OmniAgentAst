# -*- coding: utf-8 -*-
"""
内容质量检测工具 - 自我指涉检测共享方法

【创建 2026-05-01 小沈 小健】
依据设计文档 v2.1 改进1/改进2的共享检测逻辑。

设计目的：
  工具层（file_tools.py write_file）和 agent 层（base_react.py Observation 阶段）
  使用同一套自我指涉检测逻辑，避免两处不一致导致漏检。

核心指标：
  - 主要因素(70%权重)：自我指涉检测率 > 60%
    （content 中描述 LLM 自身操作的句子占总句子的比例）
  - 辅助因素(30%权重)：content 极短(<50字符)时阈值降至 40%

按文件类型区分：
  - 代码类(.py/.js/.ts等)：需要中文占比 > 30% + 自我指涉检测率高
  - 文档类(.txt/.md/.doc等)：仅需自我指涉检测率高（文档可以全中文）
  - 其他类型：需要中文占比 > 70% + 自我指涉检测率高（保守策略）

Usage:
    from app.services.tools.content_quality import check_content_quality

    result = check_content_quality(
        content="已成功创建并写入第一章内容。现在需要继续创建第二章...",
        file_path="E:/下载/novel/chapter2.txt"
    )
    # result = {
    #     "is_thought_leak": True,
    #     "self_ref_rate": 1.0,
    #     "self_ref_threshold": 0.6,
    #     "chinese_ratio": 0.95,
    #     "file_type": "document",
    #     "warning": "内容疑似思维泄漏：写入内容中100%为自我指涉描述..."
    # }

Author: 小沈 - 2026-05-01
"""

import os
import re
from typing import Dict, Optional

# 自我指涉/完成性描述关键词（LLM在描述自己的操作/状态，而非真正的文件内容）
SELF_REF_KEYWORDS = [
    '已成功', '需要继续', '现在需要', '接下来将', '按照要求',
    '继续创建', '已完成', '已创建', '写入成功', '已经写入',
    '已成功创建', '内容已写入', '成功写入', '已成功写入',
    '现在应该', '接下来需要', '需要先', '然后需要',
]

# 代码类文件扩展名
CODE_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.go', '.c', '.cpp', '.rs', '.rb', '.swift', '.kt', '.scala'}

# 文档类文件扩展名
DOC_EXTENSIONS = {'.txt', '.md', '.doc', '.docx', '.csv', '.log', '.ini', '.cfg', '.yml', '.yaml', '.json', '.xml', '.html', '.htm', '.css', '.scss', '.less'}

# 自我指涉检测阈值
SELF_REF_THRESHOLD_NORMAL = 0.6    # 正常文本阈值
SELF_REF_THRESHOLD_SHORT = 0.4     # 极短文本(<50字符)阈值
SHORT_CONTENT_LENGTH = 50          # 极短文本判定长度


def _detect_self_ref_rate(content: str) -> float:
    """
    计算 content 的自我指涉检测率

    将 content 按标点拆分为句子，统计自我指涉句子占比。

    Args:
        content: 要检测的文本内容

    Returns:
        自我指涉检测率 (0.0 ~ 1.0)
    """
    sentences = re.split(r'[。！？\n！？.!?]', content)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = max(len(sentences), 1)

    self_ref_count = 0
    for sent in sentences:
        if any(kw in sent for kw in SELF_REF_KEYWORDS):
            self_ref_count += 1

    return self_ref_count / total_sentences


def _classify_file_type(file_path: str) -> str:
    """
    根据文件扩展名分类文件类型

    Args:
        file_path: 文件路径

    Returns:
        "code" | "document" | "other"
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext in CODE_EXTENSIONS:
        return "code"
    elif ext in DOC_EXTENSIONS:
        return "document"
    else:
        return "other"


def check_content_quality(
    content: str,
    file_path: str,
) -> Dict:
    """
    检测 write_file 的 content 是否存在思维泄漏。

    核心逻辑：
      1. 计算自我指涉检测率（句子级）
      2. 根据文件类型选择判定条件
      3. 返回检测结果

    Args:
        content:    要写入文件的 content 文本
        file_path:  目标文件路径（用于判断文件类型）

    Returns:
        {
            "is_thought_leak": bool,   # 是否判定为思维泄漏
            "self_ref_rate": float,    # 自我指涉检测率 (0~1)
            "self_ref_threshold": float,  # 实际使用的阈值
            "chinese_ratio": float,    # 中文字符占比 (0~1)
            "file_type": str,          # "code" | "document" | "other"
            "warning": str,            # 警告信息（空字符串表示无问题）
        }
    """
    result = {
        "is_thought_leak": False,
        "self_ref_rate": 0.0,
        "self_ref_threshold": SELF_REF_THRESHOLD_NORMAL,
        "chinese_ratio": 0.0,
        "file_type": "other",
        "warning": "",
    }

    if not content or not isinstance(content, str):
        return result

    # 计算中文字符占比
    chinese_chars = sum(1 for c in content if '一' <= c <= '鿿')
    chinese_ratio = chinese_chars / max(len(content), 1)
    result["chinese_ratio"] = chinese_ratio

    # 计算自我指涉检测率
    self_ref_rate = _detect_self_ref_rate(content)
    result["self_ref_rate"] = self_ref_rate

    # 确定阈值：极短文本降低阈值
    is_very_short = len(content) < SHORT_CONTENT_LENGTH
    threshold = SELF_REF_THRESHOLD_SHORT if is_very_short else SELF_REF_THRESHOLD_NORMAL
    result["self_ref_threshold"] = threshold

    is_high_self_ref = self_ref_rate >= threshold

    if not is_high_self_ref:
        # 自我指涉率低，无需进一步判断
        return result

    # 按文件类型判定
    file_type = _classify_file_type(file_path)
    result["file_type"] = file_type

    if file_type == "code":
        # 代码类：需要中文占比高 + 自我指涉检测率高
        if chinese_ratio > 0.3 and is_high_self_ref:
            result["is_thought_leak"] = True
            result["warning"] = (
                f"内容疑似思维泄漏：写入内容中{int(self_ref_rate*100)}%为自我指涉描述，"
                f"不是实际代码内容。请在content参数中传入实际代码而非思考过程。"
            )

    elif file_type == "document":
        # 文档类：仅需自我指涉检测率高（文档可以全中文）
        if is_high_self_ref:
            result["is_thought_leak"] = True
            result["warning"] = (
                f"内容疑似思维泄漏：写入内容中{int(self_ref_rate*100)}%为自我指涉描述"
                f"（如'已成功'、'需要继续'），疑似将思考过程当作文件内容写入。"
                f"请在content参数中传入实际的文件内容。"
            )

    else:
        # 其他文件类型：保守策略，需要中文占比高 + 自我指涉检测率高
        if chinese_ratio > 0.7 and is_high_self_ref:
            result["is_thought_leak"] = True
            result["warning"] = (
                f"内容疑似思维泄漏：写入内容中{int(self_ref_rate*100)}%为自我指涉描述，"
                f"不是实际的文件内容。请在content参数中传入实际内容。"
            )

    return result
