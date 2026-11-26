# -*- coding: utf-8 -*-
# 2026-11-26 - 小欧 - 进程域包: 集中宿主进程与配套进程设施(IO/闸门/Job/控制台/线程池/树杀)。
#   有生命周期的宿主与无状态的公用函数同处一域但分文件, 外部只认 app.proc.* 一处;
#   常量单点在 constants.py, 本文件只做 re-export, 不导入任何子模块(防循环导入)。
from app.proc.constants import DEFAULT_TIMEOUT, PROTO

__all__ = ["PROTO", "DEFAULT_TIMEOUT"]
