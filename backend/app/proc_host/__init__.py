# -*- coding: utf-8 -*-
# 2026-11-26 - 小欧 - 进程宿主包: PROTO 协议版本单点(宿主/客户端共用)。
#   宿主是独立进程(有生命周期), 不属 app/utils 无状态公用层(SLAP); 子模块:
#   host.py(宿主进程, 由 -m 或 --proc-host 拉起)、client.py(主进程侧薄代理)。
# 2026-11-26 - 小欧 - DEFAULT_TIMEOUT 单点: 宿主路径不表达"无限等待"(客户端接收截止
#   必须有限), timeout=None 一律按此上限; client/host/proc_io 同源, 不留双语义。
PROTO = 1
DEFAULT_TIMEOUT = 600.0

__all__ = ["PROTO", "DEFAULT_TIMEOUT"]
