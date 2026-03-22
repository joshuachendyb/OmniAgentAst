# -*- coding: utf-8 -*-
"""
Intent 模块 - 意图管理层

包含意图定义和分类功能
Author: 小沈 - 2026-03-22
"""

from .classifier import IntentClassifier
from .registry import Intent, IntentRegistry

__all__ = ["Intent", "IntentRegistry", "IntentClassifier"]
