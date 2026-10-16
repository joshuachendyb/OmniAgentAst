# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 文档[35] 阶段六 新建: 自 multi_path_check 拆出 bash 通道。
#   bash 参数是单个 command 串, 与 multi(多路径参数)无关, 同处一文件名不副实。
#   逻辑逐字搬迁不改: 命令内绝对路径写/删目标抽取 → 交三线判定。
# 2026-10-15 北京老陈裁定 - 改名 shell_path_check -> shell_path_check: 判的是 shell 命令(ps/cmd/bash 三壳), 不只 bash。
# 2026-10-16 - 小欧 - [36] 洞2 修复: mv/Move-Item 源被删/目标被写分线判定(源走删线不可授权, 目标走写线可授权);
#   同时补入 Remove-ItemProperty 写意图(该动词原不在 _WRITE_CMD_RE, 命令连第一道门都进不去=零路径检查)。
#   配套 guard 侧新增 _MOVE_CMD_RE/_extract_move_paths(有序切词, 不用 _extract_abs_win_paths 因其位置序被打乱);
#   判定 for 体平移为模块级 _judge_paths(逻辑与留痕一字未改), 供两路复用。
# 2026-10-16 - 小欧 - 三堂会审复核整改(P0 退化+同源洞):
#   ①_MOVE_TOKEN_RE 裸 token 在语句分隔符处断开(与 _ABS_WIN_PATH_RES 同口径);
#   ②_MOVE_CMD_RE 补 move/ren/Rename-Item(均删源+写目标, 原连第一道门都进不去), 入口门并列判定;
#   ③_judge_paths 对含 ><|/换行的畸形路径硬拦 system(切词粘连兜底, 通道 B fail-closed);
#   ④_judge_paths 补类型注解; 日志按删线/写线分"删源/写目标"; 删 87 行死 __all__(所列三名已迁 multi_path_check)。
"""
shell_path_check — shell 命令路径检查(通道 B)

bash 属 FUNDAMENTAL, 不经 action_kind 分派, 单独立此通道:
从命令串里摘出绝对路径写/删目标, 逐个交读/写/删三线判定。

调用方: path_check_entry.validate_tool_path 特判 normal_name=="bash" 时调本模块。
"""

from typing import List, Optional, Tuple

from app.safety import delete_path_check, write_path_check
from app.logger import logger
from app.tools.fundamental.shell_command_guard import (
    _WRITE_CMD_RE,
    _DELETE_CMD_RE,
    _MOVE_CMD_RE,
    mask_quoted_spans,
    _resolve_env_fragment,
    _extract_abs_win_paths,
    _extract_move_paths,
)


def _judge_paths(paths: List[str], line, command: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """按指定线逐路径判定, 首个违规即回 (False, err, path, category); 全过回 (True, None, None, None)

    原 validate_shell 内的 for 体逐字搬出(判定/留痕/文案一字未改), 供删线与写线两路复用 — 小欧 2026-10-16
    2026-10-16 小欧 三堂会审加固: 含 shell 元字符(><|/换行)的畸形路径直接硬拦 category=system(永不授权)。
      根因: 切词粘连/`$env:` 未展开残留等形态在 line 内按前缀匹配会被放行, 通道 B 必须 fail-closed。
      `;`/`&` 是 Windows 合法文件名, 引号内可残留, 不在此拦(切词层已处理裸分隔符)。
    """
    for raw_path in paths:
        if any(c in raw_path for c in (">", "<", "|", "\r", "\n")):
            logger.warning(
                f"[shell_path_check] bash路径含非法元字符(硬拦): "
                f"path={raw_path}, command={command.strip()[:200]}"
            )
            return False, f"路径含非法 shell 元字符, 拒绝执行: {raw_path}", raw_path, "system"
        valid, err, category = (line.validate_delete(raw_path) if line is delete_path_check
                                else line.validate_write(raw_path))
        if valid:
            continue
        # 违规必须留痕: 下游 tool_safety_checker 只记 tool=bash, 没有命令原文,
        # 安全事件排查时"是哪个命令想写这个路径"查不到 —— 此处补全(小欧 2026-10-14)
        _kind = "删源" if line is delete_path_check else "写目标"
        logger.warning(
            f"[shell_path_check] bash{_kind}越权: category={category}, "
            f"path={raw_path}, command={command.strip()[:200]}"
        )
        return False, err, raw_path, category
    return True, None, None, None


def validate_shell(command: str, cwd: Optional[str] = None
                  ) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    if not isinstance(command, str):
        # 2026-10-15 小欧 - P1-15: 实测传 int 抛 AttributeError 冒泡至入口, 排查看不出是类型问题。
        return True, None, None, None
    if not command or not command.strip():
        return True, None, None, None
    # 2026-10-15 小欧 - 新发现B: cwd 决定相对路径的解析基准, 原完全不检查 ——
    #   `cd /d C:\Windows && echo x > a.txt` 里 a.txt 是相对路径, _extract_abs_win_paths 抽不到,
    #   等于绕过全部路径检查。cwd 按写线判(要在那里执行, 且相对写会落在那里)。
    if cwd:
        ok, err, cat = write_path_check.validate_write(cwd)
        if not ok:
            logger.warning(f"[shell_path_check] bash 工作目录越权: category={cat}, cwd={cwd}")
            return False, err, cwd, cat
    normalized = command.replace("\r\n", " ").replace("\n", " ")
    intent_src = mask_quoted_spans(normalized)
    # 2026-10-16 小欧 三堂会审补: move/ren/Rename-Item 不在 _WRITE_CMD_RE, 须并列进门
    #   (不进写表的原因见 guard 侧 _MOVE_CMD_RE 注释: move 是英文常用词, 防 F-B 误伤)。
    if (not _WRITE_CMD_RE.search(intent_src) and ">" not in intent_src
            and not _MOVE_CMD_RE.search(intent_src)):
        return True, None, None, None
    resolved = _resolve_env_fragment(normalized)
    # 2026-10-16 小欧 [36] 洞2: mv/Move-Item 源被删、目标被写, 后果不同必须分线。
    #   仅当「含移动动词且不含其他删动词」时拆分; 含 rm/del 时仍全走删线(更严, 不退化)。
    if _MOVE_CMD_RE.search(intent_src) and not _DELETE_CMD_RE.search(intent_src):
        _src, _dst = _extract_move_paths(resolved)
        _r = _judge_paths(_src, delete_path_check, command)
        return _r if not _r[0] else _judge_paths(_dst, write_path_check, command)
    # 2026-10-14 小欧 - 文档[33] 4.10-1: 命令含删动词时走删线而非写线。
    #   病根: _WRITE_CMD_RE 把删与写混一张表, 删系统禁区只被判「可授权的写」, 授权后等于放行删系统目录。
    line = delete_path_check if _DELETE_CMD_RE.search(intent_src) else write_path_check
    return _judge_paths(_extract_abs_win_paths(resolved), line, command)


__all__ = ["validate_shell"]
