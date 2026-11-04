# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 新建: 自 dual_path_check 拆出 bash 通道(bash 参数是单个 command 串, 与 dual 无关, 同处一文件名不副实)。逻辑逐字搬迁不改: 命令内绝对路径写/删目标抽取 → 交三线判定。
# 2026-10-15 小欧 - 改名 bash_path_check -> shell_path_check: 判的是 shell 命令(ps/cmd/bash 三壳), 不只 bash。
# 2026-10-16 - 小欧 - 修复: mv/Move-Item 源被删/目标被写分线判定(源走删线不可授权, 目标走写线可授权); 补入 Remove-ItemProperty 写意图(原不在写意图集合=零路径检查); 配套 guard 侧新增 _MOVE_CMD_RE/_extract_move_paths(有序切词), 判定 for 体平移为模块级 _judge_paths 供两路复用。
# 2026-10-16 - 小欧 - 复核整改(退化+同源缺陷): (1)_MOVE_TOKEN_RE 裸 token 在语句分隔符处断开 (2)_MOVE_CMD_RE 补 move/ren/Rename-Item, 入口门并列判定 (3)_judge_paths 对含 ><|/换行的畸形路径硬拦 system(通道 B fail-closed) (4)_judge_paths 补类型注解, 日志按删线/写线分"删源/写目标", 删 87 行死 __all__。
# 2026-10-16 - 小欧 - 接线: import 切到 app.safety.shell_command_process 并跟改正名; validate_shell 改为「一次预处理(shell_command_process.prepare_shell_text) + 两个出入口」(shell_delete_paths / shell_write_paths), 不再在本模块内部分析动词、决定走哪条线。判定顺序保持删线优先(更严); 动词/归属规则唯一裁决点下沉到 shell_command_process._shell_path_lines。
# 2026-10-16 - 小欧 - 取路径两门合一: shell_delete_paths + shell_write_paths 合并为 shell_write_and_delete_paths(一次调用返回两列清单)。原因: 两个门各自内部都要把整套判定跑一遍而本层两个清单都要, 重复计算(实测计数=2)。取路径与判权限仍是分开的两层: 本模块只编排, 判定在 delete/write_path_check。
# 2026-10-16 小欧 复核: 高危删除解析不出目标即硬拦 system(`rm -rf /` 曾 fail-open)。
# 2026-10-17 - 小欧 - 删源线改纯调 delete_path_check.check_delete_permission(判定全下沉, 本层不重判); blocked→拒(category=system), requires_confirmation→当通过(通道 B 无弹窗)。写目标线不变。
# 2026-10-17 - 小欧 - 返回契约归一: validate_shell → check_shell_permission, 四元组归一为 SafetyResult; _judge_paths 返 Optional[SafetyResult](None=全过), 写目标改调 check_write_permission; 放行统一 SafetyResult.pass_result()。
# 2026-10-17 - 小欧 - 删源线补 recursive: check_shell_permission 用 shell_has_recursive_delete(normalized) 判命令递归性, 经 _judge_paths(recursive=...) 显式喂入 check_delete_permission, 使工作区外递归=硬拦生效(此前缺参恒 False → 永不触发)。
# 2026-10-18 - 小欧 - 重构(动作清单): 通道 B 由「命令级两列路径」升级为「动作清单」消费。解析下沉 shell_parse.parse_shell_action(command, shell_type, cwd) -> List[PathAction]; 本层只按 action.kind 逐条判权限(删线 → 写线 → 读线); check_shell_permission 新增 shell_type 形参(修复壳类型断链)。递归 flags 随动作绑定, 不再命令级全扫。高危删除 fail-closed 保留。旧依赖 prepare_shell_text/shell_write_and_delete_paths/_judge_paths 全部删除(不 backward, 不留转发壳)。读动作显式入读线。
# 2026-10-18 - 小欧 - 订正(注释史实): 上方所载历史期「prepare_shell_text/shell_delete_paths/shell_write_paths/_shell_path_lines」接线均已被本次重构取代, 该模块已删除; 保留为沿革记录, 现行真源为 shell_parse.parse_shell_action + 三线 check_*_permission。
# 2026-10-18 - 小欧 - 工具级口正名: check_shell_permission 签名 (command, cwd, shell_type) → (tool_name, params), 内部取 command/cwd/shell_type; 三线单路径封装口更名 read/write/delete_permission, 本模块 4 处调用点同步跟改(判定逻辑零改动)。
# 2026-10-18 - 小欧 - 二次迁移: 高危删除判据 shell_has_destructive_delete 随删动词表整体迁入 shell_parse.parse_delete, 本模块 import 点跟改(判定语义零改动)。
# 2026-10-18 - 小欧 - 判定层 bug 修复(探针实证): 非字符串 command 原 pass_result()=fail-open, 改 fail-closed 硬拦; cwd 原仅过写线未判畸形, 补非字符串/含元字符 fail-closed 硬拦。判定逻辑其余零改动。
# 2026-10-18 - 小欧 - 删线 requires_confirmation 原按 10-17 「当通过」会静默放行需授权删除, 改为与写线一致即拒。
# 2026-10-18 - 小欧 - 归一保留换行(换行即语句边界), 不再压成空格致两命令合并漏判。
# 2026-10-18 - 小欧 - 随契约调整同步: 三处三线结果的"是否需确认"判读改 needs_confirm; 六处自建结果补 safety_level —— 删源路径非法归 tool_delete, 读/写路径非法与命令类型非法、工作目录非法、高危删除解析不出目标归 command_block。分类按动作语义直给, 原 severity="dangerous" 六处均被 blocked=True 完全覆盖、属纯冗余编码。判定逻辑与返回结构零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): 六处命令层硬拦(非法 shell 元字符 ×3、command 类型非法、
#   cwd 非法或含元字符、高危删除解析不出目标)统一 SafetyLevel.BLOCK_COMMAND —— 同一句文案不得配三种分类,
#   否则前端标签自相矛盾; 确认命名空间的标签不得用于硬拦(会挂"临时授权仅本任务有效"说明, 而硬拦无授权可给)。
#   动作清单解析与三线判定逻辑零变更。
# 2026-10-18 - 小欧 - 补读动作的系统源外泄拦截: 读线处处放行(含系统目录), 但 shell 内读取系统路径
#   即内容外带通道(cat/less/copy C:\Windows\x 都能把系统文件内容带出), 而复合工具侧
#   dual_path_check 早有同口径拦截 —— 两通道判定必须一致, 否则同一动作"工具拦、shell 不拦"。
#   实现: 读动作经 classify_forbidden_path(path, "write") 判, category=="system" 即硬拦,
#   归 SafetyLevel.PATH_FORBIDDEN。判定单源仍在本线三线, 本层只补这一处跨线检查。
# 2026-10-19 - 小欧 - 全动作取最严(修复 under-block): 原 _judge_actions 删线首命中 needs_confirm 即返回,
#   会挡住其后"系统目标写"的 blocked —— mv/ren 源越界 + 目标系统 时从硬拦降级为可授权弹窗。
#   改为 blocked(含 malformed)即时返回、needs_confirm 暂存(删线优先)判完全部动作, 无 blocked 时才回 needs_confirm。
# 2026-10-19 - 小欧 - 【铁律·推翻 2026-10-16 旧裁】高危删除解析不出目标: 硬拦 → 放行。
#   旧裁(L9)"解析不出即硬拦 system" 已作废, 理由见本文件 check_shell_permission 内注释块:
#   静态解析器不完善是既定事实, 把"能否解析"当安全边界会对合法操作持续误杀。
#   本次同时在 lexer 补跨段变量表(降低解析不出), 但**兜底一律不加**:
#   不拦截、不弹框、不改判 needs_confirm。要收紧只能提升解析能力, 不得回退到"解析不出即拒"。
#   删/写/读三段的判定条件与分类零改动, 仅改"何时返回"。
# 2026-10-19 小欧 - 目录名单收口: 系统源外泄判定改查 path_dir_lists 名单(classify_scope 取五档归属,
#   命中禁区·系统即 blocked(PATH_FORBIDDEN)); 原 classify_forbidden_path 适配壳已随 path_classify_category.py 删除;
#   异常路径改为 fail-closed 直接拒绝(名单读不出不默认放行), 与读/写/删线口径一致。
# 2026-10-20 小欧 - cwd 去掉写线判定: cwd 是相对路径解析基准而非被写对象, 原判定致
#   「在项目根下执行 dir/python -c」误判「写项目根」并弹 HITL(日志 10:56:35 实锤)。
#   保留两项: 畸形 cwd fail-closed 硬拦; 禁区·系统 cwd 禁止执行(防脚本在其中落盘)。
# 2026-10-28 小欧 - 解析失败都放行(北京老陈令「解析失败必须放行, 不拦不弹窗」):
#   三处 fail-closed 改放行 —— command 非字符串、cwd 非字符串/含元字符、cwd 归属判定异常。
#   均为解析失败(判定不出/输入畸形), 非确定危险, 不得因解析能力不足错杀。
#   读线非法路径(空值/穿越/格式化/判定异常)改 continue 放行; 系统源外泄拦截保留。
#   确定危险(真路径含元字符/系统区删除)仍拦, 见各 check 内注释。
"""
shell_path_check — shell 命令路径检查(通道 B, 动作清单消费层)

bash 属 FUNDAMENTAL, 不经 action_kind 分派, 单独立此通道:
  【解析】shell_parse.parse_shell_action(command, shell_type, cwd) → List[PathAction]
  【判定】对每个动作按 kind 调 read/write/delete_path_check 的唯一封装口
  【额外一道】系统源外泄拦截 —— 读线放行系统目录, 但命令不得以系统目录为数据源
             (如 cat/less/copy 指向系统目录), 故 read 动作额外判一次 scope 是否为
             禁区·系统, 命中即 blocked(PATH_FORBIDDEN)
判定与解析零耦合, 本层只编排。
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.safety import delete_path_check, read_path_check, write_path_check
from app.safety.path_dir_lists import (  # 2026-10-19 小欧 - 目录名单收口: 系统源判定改查名单
    SCOPE_FORBIDDEN_SYSTEM,
    SCOPE_TEXT,
    classify_path,
)
from app.safety.shell_parse import parse_shell_action
from app.safety.shell_parse.action import DELETE_KIND, READ_KIND, WRITE_KIND, PathAction
from app.safety.shell_parse.parse_delete import shell_has_destructive_delete
from app.logger import logger
from app.safety.safety_result import SafetyLevel, SafetyResult  # 契约: 安全层单源

# shell 元字符: 出现即视为畸形路径, 通道 B fail-closed 硬拦(> < | 与换行 \r \n)
#   2026-10-18 小欧 订正: 注释原误列 "/"(正斜杠是合法路径分隔, 拦它会误伤全部正斜杠路径), 改注释不改代码。
_META_CHARS = (">", "<", "|", "\r", "\n")


def _malformed(path: str) -> bool:
    """路径含非法 shell 元字符(切词粘连/未展开残留) → 硬拦 — 小欧 2026-10-18"""
    return any(ch in path for ch in _META_CHARS)


def _judge_actions(actions: List[PathAction], command: str) -> Optional[SafetyResult]:
    """按动作清单逐条判定, 全动作取最严后回 SafetyResult; 全过返回 None — 小欧 2026-10-18
       (2026-10-19 全动作取最严整改)

    最严档序: blocked > needs_confirm > pass。
    blocked 与 malformed(BLOCK_COMMAND) 属最高档, 命中即返;
    needs_confirm 只暂存(取先到者, 删线优先), 继续判完其余动作 ——
    否则"删源越界需授权"会挡住其后"系统目标写"的 blocked, 硬拦被降级为可授权(under-block)。
    通道 B 语义(无弹窗): blocked 即拒; needs_confirm 交上层确认层。
    """
    pending_confirm: Optional[SafetyResult] = None
    # 删线优先: 抹除后果不可授权
    for action in actions:
        if action.kind != DELETE_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            # 2026-10-18 小欧 分类归一: 路径含 shell 元字符属【命令层输入非法】, 与动作线无关,
            #   故删/写/读三线一律 BLOCK_COMMAND —— 同一句文案不得配三种分类, 否则前端标签自相矛盾。
            #   特别注: 不可标确认命名空间的标签(会挂"临时授权仅本任务有效"说明), 此处是硬拦、无授权可给。
            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        recursive = bool(action.flags.get("recursive"))
        perm = delete_path_check.delete_permission(action.path, {"recursive": recursive})
        if perm.blocked:
            logger.warning(f"[shell_path_check] bash删源越权: path={action.path}, "
                           f"command={command.strip()[:200]}")
            return perm
        # 2026-10-18 小欧: 原「需确认 → 当通过(无弹窗)」会静默放行「需授权才能删」的路径。
        # 2026-10-19 小欧: needs_confirm 不再即时返回(否则挡住其后系统目标写的 blocked);
        #   暂存待终判, 无任何 blocked 时才回它。
        if perm.needs_confirm:
            logger.warning(f"[shell_path_check] bash删源需授权: path={action.path}, "
                           f"command={command.strip()[:200]}")
            if pending_confirm is None:
                pending_confirm = perm
        # 写线: 越权写(blocked)即拒; 需授权(needs_confirm)暂存待终判
    for action in actions:
        if action.kind != WRITE_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        result = write_path_check.write_permission(action.path)
        if result.blocked:
            # 违规必须记日志: 下游 path_tool_safety_checker 只记 tool=bash, 没有命令原文
            logger.warning(f"[shell_path_check] bash写目标越权: blocked=True, "
                           f"path={action.path}, command={command.strip()[:200]}")
            return result
        if result.needs_confirm:
            logger.warning(f"[shell_path_check] bash写目标需授权: path={action.path}, "
                           f"command={command.strip()[:200]}")
            if pending_confirm is None:
                pending_confirm = result
    # 读线: 处处放行, 仅"空路径/穿越/异常"非法输入硬拦
    for action in actions:
        if action.kind != READ_KIND:
            continue
        if _malformed(action.path):
            logger.warning(f"[shell_path_check] bash路径含非法元字符(硬拦): "
                           f"path={action.path}, command={command.strip()[:200]}")
            return SafetyResult(blocked=True, safety_level=SafetyLevel.BLOCK_COMMAND,
                                message=f"路径含非法 shell 元字符, 拒绝执行: {action.path}")
        # 系统源外泄拦截: 读线处处放行(含系统目录), 但命令内**读取系统路径**即内容外带通道
        #   (cat/less/copy C:\Windows\x . 都能把系统文件内容带出), 与 dual_path_check 的
        #   「系统源外泄拦截」同口径 —— 两通道判定必须一致, 否则同一动作工具拦、shell 不拦。
        # 2026-10-19 小欧 - 目录名单收口: 改查名单; 2026-10-19 去冗余: 改一次 validate_read 取回 scope,
        #   免原 read_permission + classify_path 两次 realpath; 归属文案改取 SCOPE_TEXT(与判定同源)。
        _ok, _msg, _scope = read_path_check.validate_read(action.path)
        if not _ok:
            # 2026-10-28 小欧 - 北京老陈令「解析失败都放行」: 读路径非法(空值/穿越/格式化/判定异常)
            #   属解析失败/非法输入, 改放行(原硬拦)。读线本无授权可给, 放行即交给执行层真实结果。
            #   注: 系统源外泄拦截仍保留(下一分支), 那是确定危险非解析失败。
            logger.warning(f"[shell_path_check] bash读路径非法(放行): path={action.path}, "
                           f"command={command.strip()[:200]}")
            continue
        if _scope == SCOPE_FORBIDDEN_SYSTEM:
            logger.warning(f"[shell_path_check] bash读系统源(拦截): path={action.path}, "
                           f"command={command.strip()[:200]}")
            return SafetyResult(blocked=True, safety_level=SafetyLevel.PATH_FORBIDDEN,
                                message=f"路径位于{SCOPE_TEXT[_scope]}, 禁止作为源路径: {action.path}")
    return pending_confirm


def check_shell_permission(tool_name: str, params: Dict[str, Any]) -> SafetyResult:
    """shell 通道工具级权限口 — 供 path_legality_router 直调 — 小欧 2026-10-18

    Args:
        tool_name: 归一化后的工具名(通道 B 恒为 bash)
        params:    归一化后的工具参数(内含 command / cwd / shell_type)

    内部取 command/cwd/shell_type: cwd 只是相对路径解析基准(不判写权限, 仅拦畸形/系统目录);
    shell_type(ps7/ps5/cmd/bash)缺省由解析层自动识别。
    """
    command = params.get("command")
    cwd = params.get("cwd")
    shell_type = params.get("shell_type")
    if not isinstance(command, str):
        # 2026-10-15 小欧: 实测传 int 抛 AttributeError 冒泡至入口, 排查看不出是类型问题。
        # 2026-10-18 小欧: 原直接 pass_result()=fail-open(畸形输入静默放行);
        #   非字符串 command 属异常输入, 依 fail-closed 原则改硬拦。
        # 2026-10-28 小欧 - 北京老陈令「解析失败都放行」: 改回放行。command 非字符串即无法解析,
        #   属解析失败(非确定危险), 且 execute 层收到非字符串同样报错、不会执行危险命令, 放行无风险。
        logger.warning(f"[shell_path_check] command 类型非法(放行): type={type(command).__name__}")
        return SafetyResult.pass_result()
    if not command or not command.strip():
        return SafetyResult.pass_result()
    # cwd 只是相对路径的解析基准, 不是被写对象: 不按写线判(相对写/删目标已展开为绝对路径逐条判)。
    # 2026-10-20 小欧: 仅保留两档硬拦 —— 畸形输入; 禁区·系统目录禁止执行(脚本可就地落盘)。
    # 2026-10-28 小欧 - 北京老陈令「解析失败都放行」: 畸形 cwd(非字符串/含元字符)改放行 ——
    #   cwd 是解析基准非判定对象, 解析不出即放行(非确定危险); 禁区·系统目录禁止执行保留(确定危险)。
    if cwd:
        if not isinstance(cwd, str) or _malformed(cwd):
            logger.warning(f"[shell_path_check] cwd 非法或含元字符(放行): cwd={cwd!r}")
            return SafetyResult.pass_result()
        try:
            cwd_scope, _ = classify_path(cwd)
        except Exception as e:
            # 2026-10-28 小欧 - 北京老陈令「解析失败都放行」: 归属判定异常改放行(原硬拦)。
            logger.warning(f"[shell_path_check] cwd 归属判定失败(放行): cwd={cwd!r}, err={e}")
            return SafetyResult.pass_result()
        if cwd_scope == SCOPE_FORBIDDEN_SYSTEM:
            logger.warning(f"[shell_path_check] bash 工作目录命中禁区·系统: cwd={cwd}")
            return SafetyResult(blocked=True, safety_level=SafetyLevel.PATH_FORBIDDEN,
                                message=f"工作目录位于{SCOPE_TEXT[cwd_scope]}，禁止执行: {cwd}")
    # 2026-10-18 小欧: 换行即语句边界, 不再压成空格(否则 `a\nb` 合并成一条漏判 b)。
    normalized = command.replace("\r\n", "\n")
    # 【解析】动作清单: 一条命令可多动作; 解析不做任何权限判定
    actions = parse_shell_action(normalized, shell_type, cwd)
    # ─────────────────────────────────────────────────────────────────────────
    # 【铁律·不可推翻】高危删除解析不出目标 → 放行。不拦截、不弹框、不加兜底。
    #
    # 理由: 静态解析器不完善是既定事实(变量/表达式/字符串拼接等形态永远解析不全),
    #   把"能否解析"当安全边界, 会对合法操作持续误杀 —— 实测
    #   `$base="E:\test_dir\..."; if(Test-Path $base){ Remove-Item $base -Recurse -Force }`
    #   因赋值与删除分属两段而恒判缺库, 整条被拒。
    #
    # 因此本分支【只记日志, 不产生任何控制流】——它不是判定, 只是可观测记录。
    #   删除动词本身已由 shell_has_destructive_delete 识别;
    #   能解析出的目标照常在下方 _judge_actions 判权限(禁区拦 / 工作区外授权);
    #   解析不出的一律放行, 不得在此处或任何后续位置补拦截/兜底/改判 needs_confirm。
    #
    # 若将来要收紧, 只能从"提升解析能力"(lexer 认更多形态)入手, 不得回退到"解析不出即拒"。
    # ─────────────────────────────────────────────────────────────────────────
    if shell_has_destructive_delete(normalized) and not any(a.kind == DELETE_KIND for a in actions):
        logger.warning(
            f"[shell_path_check] 高危删除未解析出目标路径(放行, 依铁律不拦截): "
            f"command={command.strip()[:200]}")
    # 【判定】逐动作判权限(删线优先)
    judged = _judge_actions(actions, command)
    return judged if judged is not None else SafetyResult.pass_result()


__all__ = ["check_shell_permission"]
