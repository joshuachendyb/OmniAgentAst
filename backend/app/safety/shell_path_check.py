# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 阶段六 新建: 自 dual_path_check 拆出 bash 通道(bash 参数是单个 command 串, 与 dual 无关, 同处一文件名不副实)。逻辑逐字搬迁不改: 命令内绝对路径写/删目标抽取 → 交三线判定。
# 2026-10-15 北京老陈裁定 - 改名 bash_path_check -> shell_path_check: 判的是 shell 命令(ps/cmd/bash 三壳), 不只 bash。
# 2026-10-16 - 小欧 - 洞2 修复: mv/Move-Item 源被删/目标被写分线判定(源走删线不可授权, 目标走写线可授权); 补入 Remove-ItemProperty 写意图(原不在 _WRITE_CMD_RE=零路径检查); 配套 guard 侧新增 _MOVE_CMD_RE/_extract_move_paths(有序切词), 判定 for 体平移为模块级 _judge_paths 供两路复用。
# 2026-10-16 - 小欧 - 三堂会审复核整改(P0 退化+同源洞): ①_MOVE_TOKEN_RE 裸 token 在语句分隔符处断开 ②_MOVE_CMD_RE 补 move/ren/Rename-Item, 入口门并列判定 ③_judge_paths 对含 ><|/换行的畸形路径硬拦 system(通道 B fail-closed) ④_judge_paths 补类型注解, 日志按删线/写线分"删源/写目标", 删 87 行死 __all__。
# 2026-10-16 - 小欧 - 第五章接线(A5): import 切到 app.safety.shell_command_process 并跟改正名; validate_shell 改为「一次预处理(shell_command_process.prepare_shell_text) + 两个出入口」(shell_delete_paths / shell_write_paths), 不再在本模块内部分析动词、决定走哪条线。判定顺序保持**删线优先**(=更严); 动词/归属规则唯一裁决点下沉到 shell_command_process._shell_path_lines。
# 2026-10-16 - 小欧 - 取路径两门合一(老陈裁定「可以合并在一起」): shell_delete_paths + shell_write_paths 合并为 shell_write_and_delete_paths(一次调用返回两列清单)。原因: 两个门各自内部都要把整套判定跑一遍而本层两个清单都要 → 白跑两遍(实测计数=2)。★「取路径」与「判权限」仍是分开的两层: 本模块只编排, 判定在 delete/write_path_check。
# 2026-10-16 小欧 三堂会审(老陈裁定接进本层): 高危删除解析不出目标即硬拦 system(`rm -rf /` 曾 fail-open)。
# 2026-10-17 - 小欧 - 第十章: 删源线改纯调 delete_path_check.check_delete_permission(判定全下沉, 本层不重判); blocked→拒(category=system), requires_confirmation→当通过(通道 B 无弹窗, 老陈裁定)。写目标线不变。
# 2026-10-17 - 小欧 - 返回契约归一: validate_shell → check_shell_permission, 四元组归一为 SafetyResult; _judge_paths 返 Optional[SafetyResult](None=全过), 写目标改调 check_write_permission; 放行统一 SafetyResult.pass_result()。
# 2026-10-17 - 小欧 - 删源线补 recursive: check_shell_permission 用 shell_has_recursive_delete(normalized) 判命令递归性, 经 _judge_paths(recursive=...) 显式喂入 check_delete_permission, 使 R6(工作区外递归=硬拦)生效(此前缺参恒 False → R6 永不触发)。
# 2026-10-18 - 小欧 - [38] 13.2 重构(动作清单): 通道 B 由「命令级两列路径」升级为「动作清单」消费。解析下沉 shell_parse.parse_shell_action(command, shell_type, cwd) -> List[PathAction]; 本层只按 action.kind 逐条判权限(删线优先取严 → 写线 → 读线); check_shell_permission 新增 shell_type 形参(修复 A1 壳断链)。递归 flags 随动作绑定(修 B5), 不再命令级全扫。fail-closed 高危删除兜底保留。旧依赖 prepare_shell_text/shell_write_and_delete_paths/_judge_paths 全部退场(禁 backward, 不留转发壳)。读动作显式入 8.1(修 B1)。
# 2026-10-18 - 小欧 - [38]§12.9 落地(工具级口正名): check_shell_permission 签名 (command, cwd, shell_type) → (tool_name, params), 内部取 command/cwd/shell_type;
#   三线单路径封装口更名 read/write/delete_permission, 本模块 4 处调用点同步跟改(判定逻辑零改动)。
# 2026-10-18 - 小欧 - [38] 13.2 二次迁移(老陈裁定): 高危删除兜底判据 shell_has_destructive_delete 随删动词表整体
#   迁入 shell_parse.parse_delete, 本模块 import 点跟改(判定语义零改动)。
"""
shell_path_check — shell 命令路径检查(通道 B, 动作清单消费层)

bash 属 FUNDAMENTAL, 不经 action_kind 分派, 单独立此通道:
  【解析】shell_parse.parse_shell_action(command, shell_type, cwd) → List[PathAction]
  【判定】对每个动作按 kind 调 read/write/delete_path_check 的唯一封装口
本层只编排判定, 不含任何解析逻辑(解析与判定零耦合, 概设 §13.2.3.1)。
"""

from typing import Any, Dict, List, Optional

from app.safety import delete_path_check, read_path_check, write_path_check
from app.safety.shell_parse import parse_shell_action
from app.safety.shell_parse.action import DELETE_KIND, READ_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse.parse_delete import shell_has_destructive_delete
from app.logger import logger
from app.tools.tool_types import SafetyResult  # 2026-10-17 小欧 - 本通道返回类型

# shell 元字符: 出现即视为畸形路径, 通道 B fail-closed 硬拦(> < | 与换行 \r \n)
#   2026-10-18 小欧 三堂会审: 注释原误列 "/"(正斜杠是合法路径分隔, 拦它会误伤全部正斜杠路径), 订正注释不改代码。
_META_CHARS = (">", "<", "|", "\r", "\n")


def _malformed(path: str) -> bool:
    """路径含非法 shell 元字符(切词粘连/未展开残留) → 硬拦 — 小欧 2026-10-18"""
    return any(ch in path for ch in _META_CHARS)


def _judge_actions(actions: List[PathAction], command: str) -> Optional[SafetyResult]:
    """按动作清单逐条判定, 首个违规即回 SafetyResult; 全过返回 None — 小欧 2026-10-18

    顺序即优先级: 删线优先(抹除不可授权 → 更严) → 写线 → 读线。
    通道 B 语义(无弹窗): delete 的 blocked 即拒; write 的 blocked/requires_confirmation 即拒;
      read 仅非法输入 blocked。requires_confirmation(删线)当通过(老陈裁定)。
    """
    # 删线优先: 抹除后果不可授权
    for action in actions:
        if action.kind != DELETE_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            return SafetyResult(blocked=True, severity="dangerous",
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        recursive = bool(action.flags.get("recursive"))
        perm = delete_path_check.delete_permission(action.path, {"recursive": recursive})
        if perm.blocked:
            logger.warning(f"[shell_path_check] bash删源越权: path={action.path}, "
                           f"command={command.strip()[:200]}")
            return perm
        # requires_confirmation → 当通过(通道 B 无弹窗)
    # 写线: 越权写(blocked)或需授权(requires_confirmation)即拒
    for action in actions:
        if action.kind != WRITE_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            return SafetyResult(blocked=True, severity="dangerous",
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        result = write_path_check.write_permission(action.path)
        if not (result.blocked or result.requires_confirmation):
            continue
        # 违规必须留痕: 下游 path_tool_safety_checker 只记 tool=bash, 没有命令原文
        logger.warning(f"[shell_path_check] bash写目标越权: blocked={result.blocked}, "
                       f"path={action.path}, command={command.strip()[:200]}")
        return result
    # 读线: 处处放行, 仅"空路径/穿越/异常"非法输入硬拦
    for action in actions:
        if action.kind != READ_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            return SafetyResult(blocked=True, severity="dangerous",
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        result = read_path_check.read_permission(action.path)
        if result.blocked:
            logger.warning(f"[shell_path_check] bash读路径非法: path={action.path}, "
                           f"command={command.strip()[:200]}")
            return result
    return None


def check_shell_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """shell 通道工具级权限口 — 供 path_legality_router [8] 直调 — 小欧 2026-10-18

    Args:
        tool_name: 归一化后的工具名(通道 B 恒为 bash)
        params:    归一化后的工具参数(内含 command / cwd / shell_type)

    内部取 command/cwd/shell_type: cwd 决定相对路径解析基准(其本身按写线判);
    shell_type(ps7/ps5/cmd/bash)缺省由解析层自动识别。
    """
    command = params.get("command")
    cwd = params.get("cwd")
    shell_type = params.get("shell_type")
    if not isinstance(command, str):
        # 2026-10-15 小欧 - P1-15: 实测传 int 抛 AttributeError 冒泡至入口, 排查看不出是类型问题。
        return SafetyResult.pass_result()
    if not command or not command.strip():
        return SafetyResult.pass_result()
    # cwd 决定相对路径的解析基准, 原完全不检查 —— 相对写会落在那里, 本身按写线判。
    if cwd:
        result = write_path_check.write_permission(cwd)
        if result.blocked or result.requires_confirmation:
            logger.warning(f"[shell_path_check] bash 工作目录越权: blocked={result.blocked}, cwd={cwd}")
            return result
    normalized = command.replace("\r\n", " ").replace("\n", " ")
    # 【解析】动作清单: 一条命令可多动作; 解析不做任何权限判定
    actions = parse_shell_action(normalized, shell_type, cwd)
    # fail-closed 兜底: 高危删除(递归/强制)若解析不出删目标(如 `rm -rf /`), 一律硬拦
    #   ★刻意用 normalized(换行转空格): 正则不跨行; 只看原始字面, 不用涂空文本(涂空会漏引号内危险体)
    if shell_has_destructive_delete(normalized) and not any(a.kind == DELETE_KIND for a in actions):
        logger.warning(
            f"[shell_path_check] 高危删除命令无法解析目标路径(硬拦): command={command.strip()[:200]}")
        return SafetyResult(blocked=True, severity="dangerous",
                            message="高危删除命令无法解析目标路径，拒绝执行: " + command.strip()[:120])
    # 【判定】逐动作判权限(删线优先取严)
    judged = _judge_actions(actions, command)
    return judged if judged is not None else SafetyResult.pass_result()


__all__ = ["check_shell_permission"]
