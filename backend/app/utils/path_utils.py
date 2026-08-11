
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 三堂会审复核落地(P2-1): 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
"""
path_utils — 路径处理工具

职责: Windows 长路径支持等路径相关公共函数
小欧 2026-08-11
"""
import os
from pathlib import Path


def to_win_long_path(path: Path) -> str:
    r"""Windows长路径 \\?\ 前缀, 绕过MAX_PATH(260)限制 — 小欧 2026-08-11
    仅NT系统生效; 已带前缀或非绝对路径保持原样。
    """
    if os.name != "nt":
        return str(path)
    s = str(path)
    if s.startswith("\\\\?\\") or not Path(s).is_absolute():
        return s
    return "\\\\?\\" + s
