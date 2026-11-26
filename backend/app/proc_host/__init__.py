# -*- coding: utf-8 -*-
# 2026-11-26 - 小欧 - 进程宿主包: PROTO 协议版本单点(宿主/客户端共用), 见 [65] E1 方案。
#   宿主是独立进程(有生命周期), 不属 app/utils 无状态公用层(SLAP); 子模块:
#   host.py(宿主进程, 由 -m 或 --proc-host 拉起)、client.py(主进程侧薄代理)。
PROTO = 1

__all__ = ["PROTO"]
