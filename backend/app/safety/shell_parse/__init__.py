# -*- coding: utf-8 -*-
"""shell_parse — shell 命令解析包(动作级, 三壳分治, 零权限判定) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.5「模块与文件清单」落地。
  唯一对外入口 parse_shell_action(command, shell_type, cwd) -> List[PathAction]。
  解析与权限判定彻底分层: 本包一个权限判据都不做(R7)。

文件:
  action.py           数据契约 PathAction
  lexer.py            预处理/拆句/拆管道/分词/壳识别/路径归一
  parse_read.py       读解析(3 壳)
  parse_write.py      写解析(含重定向)
  parse_delete.py     删解析(含递归/强制开关)
  parse_move.py       搬移解析(源/目标分离)
  parse_shell_action.py  唯一入口
"""
from app.safety.shell_parse.action import PathAction
from app.safety.shell_parse import lexer
from app.safety.shell_parse.parse_shell_action import parse_shell_action

__all__ = ["PathAction", "lexer", "parse_shell_action"]
