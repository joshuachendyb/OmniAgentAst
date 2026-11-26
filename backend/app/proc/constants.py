# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 进程域常量单点, 从 app/proc_host/__init__.py 迁入(域包升格后
#   __init__ 不再定义常量); 取值与协议语义零变化。
"""proc — 进程域常量单点(host / client / proc_io 共用)。

域内约定: 协议版本与超时上限只有一个真源, 宿主与客户端握手同源,
调用方不得各自写 600 这类魔法数(双语义是卡死诊断的对立面)。
"""
PROTO = 1

# 【使用对象】client.run 接收截止 / host._handle 槽位排队与 proc.wait / proc_io.run 的
#   timeout=None 兜底; 三处同源, 一处调参全局一致。
DEFAULT_TIMEOUT = 600.0

__all__ = ["PROTO", "DEFAULT_TIMEOUT"]
