# -*- coding: utf-8 -*-
"""
task_state_store — running_tasks 数据存储

从 task_registry.py 拆出数据存储定义，打破 task_registry ↔ task_state_queries 循环导入。
_running_tasks 和 _running_tasks_lock 是全局单例，所有读写都通过此文件访问。

Author: 小健 - 2026-06-17
"""

import asyncio

_running_tasks_lock = asyncio.Lock()
_running_tasks: dict[str, dict] = {}