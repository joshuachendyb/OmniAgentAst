# -*- coding: utf-8 -*-
"""shell 命令静态处理单一真源 —— 权限入口侧的文本解析与目标抽取（零状态·零 I/O）

职责: 从一条 shell 命令里 **取路径清单与识别动作**，交给下游判权限。本模块**不判权限、不判危险等级**。
分层: 取路径(本模块) 与 判权限(delete_path_check / write_path_check) 严格分开，详见文档[36] 第七章。

关注点(按用途归类, 老陈 2026-10-16 裁定):
  一、只读白名单    —— SHELL_READONLY_PREFIXES / FAST_CHANNEL_FORBIDDEN / is_shell_readonly_whitelisted
  二、文本规范化    —— shell_normalize_command(拼接折叠/[char]解码) / shell_blank_out_quotes(引号涂空)
  三、越界与写意图  —— SHELL_OUTSIDE_TARGET_RE / SHELL_WRITE_INTENT_RE 等(供沙箱 F-B 预检与通道 B 入口门)
  四、路径与动作    —— shell_write_and_delete_paths(取删线/写线清单)
  五、工具分类      —— is_shell_tool
★自杀检查(杀进程防护)已于 2026-10-16 全部归并到 app/safety/shell_process_guard.py(老陈裁定),
  本模块不再持有任何杀进程相关的词表与判定函数。

位置: app/safety/。原居 app/tools/fundamental/shell_command_guard.py，2026-10-16 整文件下沉。
依赖方向: 仅 import fnmatch/re/typing + app.tools.tools_alias_mapper(契约与元数据, 合法)，
  **不再 import 任何 app.tools.fundamental / app.tools.validate**。

编辑历史:
2026-10-04 小欧 - 自 executor.py 迁入(原名 shell_readonly.py, 落 app/utils/), 内容未改, 行内署名保留。
2026-10-05 小欧 - 安全修复: FAST_CHANNEL_FORBIDDEN 补 $ ( ) 反引号 < 四类子表达式/命令替换/输入重定向载体
  (北京老陈裁定; 原缺口致 `echo $(Start-Process calc)` 等既过白名单又过 F-B 扫描, 直通真机执行任意命令)。
2026-10-05 小欧 - 补 \n \r: 换行符同为语句分隔符, 此前未禁致白名单可被绕过。
2026-10-08 小欧 - 新增不可隔离动词判定(事故驱动): UNCONTAINABLE_VERBS 词表 + has_uncontainable_intent /
  extract_kill_target_pids / is_process_kill_protected。根因: 沙箱预检是在宿主真跑一遍命令, 而 Job Object
  非硬墙拦不住子进程杀别的进程 → 词表漏 Stop-Process 时预检即真跑, 当场杀掉后端自身(E2E P9-03 实录)。
  收录标准= 现有 SHELL_DANGEROUS_PATTERNS 只到 MEDIUM(弹窗后仍进预检)拦不住者; HIGH 级不重复收录(DRY)。
2026-10-10 小欧 - 审计 P1-1 新增 normalize_for_intent: 词表命中前先折叠字符串拼接再去引号, 使
  & ('Stop'+'-Process') -Id 5 / $v='Stop'+'-Process'; & $v -Id 5 这类"字面量被 + 拆开"的形态可被查杀。
  归一只用于检测不用于执行, 只增不减(取严)。本项只覆盖拼接类, WMI/别名/CIM/Base64 仍需另行收词(未做)。
2026-10-10 小欧 - 审计 P1-3 新增按名杀目标提取(extract_kill_target_names 等): 补保护盾对
  `Get-Process python | Stop-Process -Force` 这类按名杀形态的盲区(原只抽显式 PID, 事故形态恒返空集)。
2026-10-10 小欧 09:55:09 - 位置与命名修正(北京老陈指出"代码名称确实要名副其实"):
  原 shell_readonly.py 名不副实(仅约 1/3 内容与 readonly 有关), 且落 utils 是为绕开一条并不存在的障碍
  ——"tools 禁 import safety"只单向禁止, safety→tools 合法, 故无需中转 utils。
  按 AGENTS.md 1.4「能复制就复制, 不重写」逐行合并未改业务逻辑, 仅调整文件位置与导入路径:
  ①位置 app/utils/ → app/tools/fundamental/(与其余 shell 代码同目录, 不散落)
  ②更名 shell_readonly.py → shell_static_guard.py(名副其实: 对 shell 命令做静态守卫判定)
  ③曾短暂拆为 shell_readonly/shell_danger/shell_normalize 三文件, 复核后判定属过度拆分
    (normalize_for_intent 只服务杀进程判定, 非独立可复用能力, 单独成文件违反 YAGNI), 故并回一处。
2026-10-10 小欧 10:30 猎杀 10 bug 全修(本地探针实证, 门级 verdict 逐条验证):
  ①归一 v2: [char]N 解码(_decode_char_codes, 至不动点) + 剥 ()[]{} 噪音 → 修 [char]拼接预检真跑;
    顺序解码→剥噪音→折叠→去引号; 逗号/分号不动(PID/多值分隔与语句分隔, 动不得)。
  ②动词层: .Terminate()/.Kill() 方法调用(_METHOD_KILL_RE, 只认调用点 `.X(`, 不认裸词 terminate) +
    Invoke-CimMethod(_CIM_KILL_RE) → 修 WMI/CIM 全链漏网; -EncodedCommand/-enc(_ENCODED_RE,
    不认单字母 -e)转 HITL(Base64 内容静态不可见, 用户同样无法有效确认, 属残留风险)。
  ③名提取: /FI IMAGENAME eq X、WMI where/Name=(前后向断言挡 hostname/filename)、pkill 实参(含 -f 模式,
    交 fnmatch, `.*` 天然全中) → 修 /FI、wmic、pkill -f; 名提取同步扫归一文(复用 P1-1 并集模式,
    不放宽 token 类) → 修引号名(`-Name "python"`/`/IM "x.exe"`/多值引号)。
  ④兜底 _unscoped_process_kill: 有杀意无目标(PID/名皆空)直接 blocked —— 管线裸杀、无参 taskkill、
    wmic 质量动作、无名方法杀/CIM、`kill %1`/`kill -9 $(…)` 之类; 有名/有 PID 走原口径,
    停服务动词(/ ?, --help, -WhatIf 让路; wmic 裸查询让路)不在此列; 只认引号之外的动词
    (`echo "kill"` 纯提及留 HITL, 不升 blocked)。— 小欧-2026-10-10
2026-10-16 - 小欧 - 文档[36] 第五章: 自 app/tools/fundamental/shell_command_guard.py 整文件下沉到
  app/safety/(文件级复制零漂移, AGENTS 1.4 能复制不重写), 按 3.5.5 正名 24 项符号;
  新增写删目标识别 8 个单一职责函数(ShellText / prepare_shell_text / shell_write_and_delete_paths 等);
  自杀检查按老陈裁定全部归并到 app/safety/shell_process_guard.py, 本模块不再持有杀进程词表与判定函数。
2026-10-16 小欧 - 三堂会审: 删 shell_blank_out_quotes 重复定义(两处一字不差, 后者覆盖前者致前者成死代码);
  删 danger/risk 两层随之失效的死 import(两层的"降级/引号判别式"已按老陈裁定删除)。

"""
import fnmatch
import os
import re
from typing import List, NamedTuple, Tuple

from app.tools.tools_alias_mapper import normalize_tool_name

# ══════════════════════════════════════════════════════════════════════
# 一、只读白名单: 可否免预检直放
# ══════════════════════════════════════════════════════════════════════
# —— 判定规则的真实代码落点(v1.18 按北京老陈要求全部代码化) ———
SHELL_READONLY_PREFIXES = ("get-", "ls", "cat", "type", "git status",
                     "echo", "pwd", "dir", "whoami", "hostname",
                     "git log", "git diff", "git show",
                     "python --version", "node --version", "node -v",
                     "npm --version", "npm ls",
                     "pip list", "pip show", "pip --version",
                     "docker ps", "docker images",
                     "tasklist", "ipconfig /all", "systeminfo", "netstat", "ver",
                     "test-path", "kubectl get")     # 4.1#4 只读白名单前缀(3.2.1 五项 + 毛病2精化二十一项) — 小欧-2026-09-18
    # 毛病2评审纪要(2026-09-18 小欧, 逐条过安全评审, 任意无拼接符后缀仍只读才准入):
    #   准入: git log/diff/show(纯展示); python/node --version(打印即退); npm --version/ls, pip list/show/--version(只读查询);
    #   docker ps/images(只读列表); tasklist/systeminfo/netstat/ver(系统只读展示); ipconfig /all(精确子命令, /flushdns等不匹配);
    #   test-path(纯测试); kubectl get(只读API, 与 read 读敏感文件同政策).
    #   否决: git branch(-D/-M可删分支); ipconfig裸前缀(/release//renew//flushdns可变更网络); gh/set/npm run/pip install/docker exec等(可写).
SHELL_FAST_CHANNEL_FORBIDDEN = ("|", ";", "&", ">", ">>", "$", "(", ")", "`", "<", "\n", "\r")
    # 2026-10-05 小欧 安全修复(北京老陈裁定): 补 $ ( ) 反引号 < 四类载体——原缺口使
    #   `echo $(Start-Process calc)`/`echo $(net user hacker pass /add)`/`echo `whoami` 既过白名单
    #   (只查前缀)又过 F-B 扫描(词表仅含写动词+重定向), 最终直通真机无沙箱。
# 误拒含括号的合法只读命令可接受(转沙箱预检仍能执行), 漏放是真机执行, 取严。 — 小欧 2026-10-05


# ══════════════════════════════════════════════════════════════════════
# 二、命令规范化: 判危险前先把"拼出来的动词"还原(2026-10-10 审计 P1-1)
# ══════════════════════════════════════════════════════════════════════
# 审计实证的绕过: & ('Stop'+'-Process') -Id 5 / $v='Stop'+'-Process'; & $v -Id 5
#   字面量被 + 拆开, _UNCONTAINABLE_RE 查不到连续词, 判定放行 → 预检在宿主真跑 → 后端自杀。
# 本函数只服务"检测", 不服务"执行": 归一只可能让词更易命中、不会让已命中的词消失, 故只增不减(取严)。
# 折叠 '+' 必须先于去引号: 'Stop'+'-Process' → 'Stop'-'Process' → Stop-Process。
_CONCAT_PART = r"'[^']*'|\"[^\"]*\"|[A-Za-z0-9_.-]+"
_CONCAT_RE = re.compile(r"(" + _CONCAT_PART + r")\s*\+\s*(" + _CONCAT_PART + r")")
# 2026-10-10 小欧 猎杀#3([char]拼接): & ([char]83+[char]116+[char]111+[char]112)-Process -Id 5 ——
#   _CONCAT_PART 不认方括号致零折叠, 且括号隔断动词((Stop)-Process 查不到连续词) → 全链漏网预检真跑。
#   解法: 先把 [char]N(十进制)还原为字符, 再剥 ()[]{} 四种噪音括号, 然后走原有折叠。
#   只剥括号(检测专用取严); 逗号/分号不动(逗号是 PID/多值分隔, 分号是语句分隔, 动不得)。
_CHAR_RE = re.compile(r"\[char\]\s*(\d+)", re.IGNORECASE)
_NOISE_RE = re.compile(r"[(){}\[\]]")
# 引号 span: 只认单/双引号整段(给 shell_blank_out_quotes 涂空用)
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _decode_char_codes(text: str) -> str:
    """[char]83 → S(十进制; 十六进制 0x 形态暂不覆盖, 见残留)。至不动点(连写嵌套一次消不净)。"""
    prev = None
    while prev != text:
        prev = text
        text = _CHAR_RE.sub(lambda m: chr(int(m.group(1)) & 0x10FFFF), text)
    return text


def shell_normalize_command(command: str) -> str:
    """把字符串拼接折叠、去引号, 使 'Stop'+'-Process' 还原为 Stop-Process — 小欧 2026-10-10

    适用: 仅供静态危险判定前置归一(词表命中前置), 结果不用于执行。
    循环折叠至不动点: 'a'+'b'+'c' 三段拼接一次只能合两段, 单趟必漏。
    2026-10-10 小欧 补: [char]N 解码 + 括号噪音剥离(猎杀#3)。顺序: 解码 → 剥噪音 → 折叠 → 去引号。
    """
    text = _decode_char_codes(command or "")
    text = _NOISE_RE.sub("", text)           # 剥括号噪音: (Stop)-Process → Stop-Process
    prev = None
    while prev != text:                      # 每趟至少消掉一个 '+', 必然收敛(不动点退出)
        prev = text
        text = _CONCAT_RE.sub(r"\1\2", text)
    return text.replace("'", "").replace('"', "")


def is_shell_readonly_whitelisted(command: str) -> bool:
    """只读白名单判定 — 小欧 2026-10-04

    安全放行须先跑 executor._scan_command_danger_intent, 纯路由调用点不适用。
    """
    lowered = command.strip().lower()
    if not lowered.startswith(SHELL_READONLY_PREFIXES):    # 与常量单源(消除双源双维护) — 小欧-2026-09-18
        return False
    return not any(op in command for op in SHELL_FAST_CHANNEL_FORBIDDEN)


# ══════════════════════════════════════════════════════════════════════
# 三、越界目标与写意图（供沙箱 F-B 预检 + 通道 B 入口门）
# ══════════════════════════════════════════════════════════════════════
# 病根(文档[33] 错点4): 宽表把删与写混一张表, 命令含删动词时判"写", 于是删系统禁区只被判
# 「可授权的写」而非「不可授权的删」——授权后等于放行删系统目录。故拆细表三张。
# ★宽表必须保留删动词(文档[36] 3.10.3-D1): 沙箱 F-B 越界写扫描正是靠它才看得到
#   Remove-Item/del/rm 的目标, 移出即漏扫 = 安全退化。
SHELL_WRITE_INTENT_RE = re.compile(
    r"\b(?:Remove-Item|Remove-ItemProperty|rm|ri|del|erase|rd|rmdir|Move-Item|mi|Copy-Item|cpi|cp|mv"
    r"|New-Item|ni|Set-Content|Add-Content|ac|Out-File|Expand-Archive"
    r"|reg(?:\.exe)?(?=\s|$)|setx|regedit(?:\.exe)?(?=\s|$))\b",
    re.IGNORECASE)
SHELL_REDIRECT_RE = re.compile(r">>?\s*\"?([^\"\r\n<>|;]+)")   # v1.21 Z1: 重定向目标提取(> 与 >> 同权)
SHELL_OUTSIDE_TARGET_RE = re.compile(
    r"(?:"
    r"\b[a-z]:[\\/]"                 # 绝对盘符 C:\ D:\ / C:/ D:/ (正斜杠亦属越界写, 防逃逸)
    r"|\\\\[\w.\-]+\\"               # UNC \\host\share\
    r"|\bhk(?:lm|cu|cr|u|cc):[\\/]"  # 注册表驱动器 HKLM:/HKCU: 等
    r"|\$env:[\w]+[\\/]"             # $env:XXX\ 展开(解析前形态)
    r"|[\"']?~[\\/]"                 # ~ 家目录展开
    r")", re.IGNORECASE)
SHELL_SANDBOX_SELF_RE = re.compile(r"omniagent_sandbox", re.IGNORECASE)   # N7 carve-out 标识
SHELL_REGISTRY_SYSTEM_VERBS = frozenset({"reg", "reg.exe", "regedit", "regedit.exe", "setx"})

SHELL_DELETE_RE = re.compile(
    r"(?<![a-z0-9_-])(?:Remove-Item|Remove-ItemProperty|del|erase|rd|rmdir|ri|rm)(?![a-z0-9_-])",
    re.IGNORECASE)

# 2026-10-16 老陈裁定(第④层收编): 原在 shell_command_risk.py 的 10 条"删除类"规则移到这里 ——
#   理由: rm/del/Remove-Item/rd/rmdir 是**文件删除命令**, 属路径判定, 危险层与中风险层不许含路径规则。
#   这些是"删除动词 + 特定开关组合"(递归/强制/s 开关), 比普通删除更危险:
#     · 唯一消费方 shell_path_check 用它做 fail-closed 兜底(见 shell_has_destructive_delete docstring)
#   ★2026-10-16 三堂会审: 删死代码 _TEMP_SAFE_PATTERNS + shell_is_temp_cleanup(原随规则一并移来,
#     但全仓零调用 —— 即"建了不接", 与老陈反对的画蛇添足同型)。高危删除解析不出目标即硬拦,
#     不再做"临时目录降级"那套豁免。
SHELL_DESTRUCTIVE_DELETE_RES = (
    # PS: Remove-Item/rm/del + Recurse + Force
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bRecurse\b.*\bForce\b", re.IGNORECASE),
    # PS: Remove-Item/rm + Recurse(排除显式 -Recurse:$false)
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\bRecurse\b(?!:\$false\b))", re.IGNORECASE),
    # PS 字母flag: rm -rf(等价于 -Recurse -Force)
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR][fF]\b", re.IGNORECASE),
    # PS 字母flag 分离形态: rm -r -f
    re.compile(r"(?:Remove-Item|rm|ri|erase|del)\s+.*?-[rR]\b.*?-[fF]\b", re.IGNORECASE),
    # CMD: del /s(递归删文件)
    re.compile(r"\bdel\b.*?/s\b", re.IGNORECASE),
    # CMD: rd /s(递归删目录)
    re.compile(r"\brd\b.*?/s\b", re.IGNORECASE),
    # CMD: rmdir /s(递归删目录)
    re.compile(r"\brmdir\b.*?/s\b", re.IGNORECASE),
    # bash: rm -rf /(递归删根路径)
    re.compile(r"\brm\b.*?-rf\s+/", re.IGNORECASE),
    # PS: Remove-Item/rm + Force(强制删除文件, 原 MEDIUM)
    re.compile(r"(?:Remove-Item|rm|del|ri|erase)\s+.*\bForce\b", re.IGNORECASE),
    # CMD: del /f(强制删除文件, 原 MEDIUM)
    re.compile(r"\bdel\b.*?/f\b", re.IGNORECASE),
)


def shell_has_destructive_delete(command: str) -> bool:
    r"""这条命令是不是高危删除(递归/强制/带开关) — 小欧 2026-10-16（[36] 第七章）

    干什么用: 供 shell_path_check.validate_shell 做 **fail-closed 兜底** ——
              高危删除若**解析不出任何删路径**(如 `rm -rf /`, 路径提取只认 Windows 绝对路径),
              说明无从判权限, 一律硬拦 system。**判据成立才拒, 不是"高危即拒"**。
              ★2026-10-16 三堂会审订正: 原 docstring 写"高危删除需用户确认而非直接拒"与实际用法不符
                (实际只用于"解析不出目标→硬拦"这一条; 解析得出时走 delete_path_check 正常判权限)。
    口径    : 只认"删除动词 + 递归/强制/s 开关"组合; 普通 `rm C:\x` 不算(走普通删线)。
    """
    return any(rx.search(command or "") for rx in SHELL_DESTRUCTIVE_DELETE_RES)


SHELL_MOVE_RE = re.compile(r"(?<![a-z0-9_-])(?:Move-Item|Rename-Item|move|ren|mi|mv)(?![a-z0-9_-])", re.IGNORECASE)
# 细表三 纯写动词: 有意裁剪——move 族归 SHELL_MOVE_RE(源删/目标写); del 族 8 个归 SHELL_DELETE_RE
# (在宽表里保留, 见上)。重定向 > 与 >> 不在本表: 目标恒为文件, 由 shell_write_and_delete_paths 单列覆盖。
_SHELL_WRITE_VERBS = (r"(?:Copy-Item|cp|cpi|New-Item|ni|Set-Content|Add-Content|ac|Out-File"
                      r"|Expand-Archive|reg(?:\.exe)?(?=\s|$)|setx|regedit(?:\.exe)?(?=\s|$))")
SHELL_WRITE_RE = re.compile(r"\b" + _SHELL_WRITE_VERBS + r"\b", re.IGNORECASE)

_MOVE_DEST_SWITCHES = frozenset({"-destination", "-dest", "-newname"})   # 其后路径=目标
# 2026-10-16 小欧 三堂会审修(P0 退化): 裸 token 必须在语句分隔符处断开, 与 _SHELL_ABS_WIN_PATH_RES 同口径
_MOVE_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s"\'<>|;&]+')
_ABS_PATH_HEAD_RE = re.compile(r'^[a-zA-Z]:[\\/]')          # 只认盘符绝对路径
_SHELL_ABS_WIN_PATH_RES = [
    # 引号区先完整取出(两条): 只在**确实位于引号内**时才允许空格, 故用
    #   「非引号字符 + 引号内任意字符」的组合匹配, 避免把裸路径间的空格也当成路径的一部分
    #   (实测 `C:\a C:\b` 曾被吞成 'C:\a C:\b' 一个路径)。
    re.compile(r'"[a-zA-Z]:\\[^"]*"'),          # 双引号内反斜杠盘符路径
    re.compile(r'"[a-zA-Z]:/[^"]*"'),           # 双引号内正斜杠盘符路径(C:/ 同属越界写, 防逃逸)
    re.compile(r"'[a-zA-Z]:\\[^']*'"),          # 单引号内盘符路径
    # 裸路径(引号外): 遇空白或分隔符即止; 反斜杠与正斜杠盘符同认
    re.compile(r"[a-zA-Z]:[\\/][^\s\"'<>|;,)&]+"),
]


def shell_blank_out_quotes(text: str) -> str:
    """引号内容涂成等长空格(保偏移)。用于判动词时把 'Select-String -Pattern "del"' 里的 del 排除。"""
    return _QUOTED_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)


# ══════════════════════════════════════════════════════════════════════
# 四、路径抽取与工具分类
# ══════════════════════════════════════════════════════════════════════
def is_shell_tool(tool_name: str) -> bool:
    """是否 shell 命令类工具(executor 预检按此分流 file_op / shell) — 小欧 2026-10-10

    迁自 executor.py:70（文档[33] 4.11-A）。调用期依赖 normalize_tool_name 已在文件头显式导入,
    杜绝「import 通过但调用 NameError」。
    """
    _shell = frozenset({"bash"})  # 2026-10-02 小欧 - 随注册名改名
    return normalize_tool_name(tool_name) in _shell


def _extract_shell_move_paths(command: str) -> Tuple[List[str], List[str]]:
    """移动类命令按参数位置拆「源(被删)」与「目标(被写)」 — 小欧 2026-10-16（[36] 洞2）

    为什么不用 shell_extract_abs_win_paths 取源: 它按"引号组 + 裸路径组"拼接返回, 位置序被打乱
    (实测 `mv C:\src.txt "E:\dst dir"` 返回 [目标, 源]), 按下标取源会判反;
    本函数按文本顺序切 token, 故位置可靠。
    -Destination/-dest 之后的路径判为目标, 其余为源; 无开关时首路径为源、其余为目标
    (PS 位置写法与 bash/cmd `mv src dst` 同形)。只认盘符绝对路径, 相对路径不抽(交沙箱预检)。
    """
    tokens = [t.strip("\"'") for t in _MOVE_TOKEN_RE.findall(command or "")]
    paths = [(i, t) for i, t in enumerate(tokens) if _ABS_PATH_HEAD_RE.match(t)]
    if not paths:
        return [], []
    dest_idx = next((i for i, t in enumerate(tokens)
                     if t.lower() in _MOVE_DEST_SWITCHES), None)
    if dest_idx is None:
        return [paths[0][1]], [p for _, p in paths[1:]]
    src = [p for i, p in paths if i < dest_idx]
    dst = [p for i, p in paths if i > dest_idx]
    return (src or [p for _, p in paths]), dst


def shell_resolve_env_fragment(fragment: str) -> str:
    """$env:VAR 片段展开为真实路径(`$env:TEMP\\a.txt` → `C:\\Temp\\a.txt`)。未知变量原样保留。"""
    def _sub(m):
        val = os.environ.get(m.group(1))
        return val if val is not None else m.group(0)
    return re.sub(r"\$env:([A-Za-z_][A-Za-z0-9_]*)", _sub, fragment or "")


def shell_ps_literal_path(p) -> str:
    """给 PowerShell -LiteralPath 用单引号包裹并转义内嵌单引号(`'` → `''`)。"""
    return "'" + str(p).replace("'", "''") + "'"


def shell_extract_abs_win_paths(text: str) -> List[str]:
    """抽取命令中的全部绝对路径 — 小欧 2026-10-14

    引号区先完整取出(含首尾引号, 取出后剥掉), 裸路径**只在引号区之外**扫描:
    否则同一段引号路径会被裸正则再截断成 `E:\\my`(实测误拦已授权目录 `E:\\my proj`,
    且 failed_path 报错路径)。裸路径不得跨空白, 否则 `C:\\a C:\\b` 会被吞成一个路径。
    去重保序。
    """
    quoted: List[str] = [m.strip("\"'")
                        for rx in _SHELL_ABS_WIN_PATH_RES[:3] for m in rx.findall(text)]
    bare = _SHELL_ABS_WIN_PATH_RES[3].findall(shell_blank_out_quotes(text))
    found: List[str] = []
    for p in quoted + bare:
        p = p.strip().rstrip("\\")
        if p and p.lower() not in [x.lower() for x in found]:
            found.append(p)
    return found


def shell_registry_key_exists(reg_path: str) -> bool:
    """registry 静态分析(2.4 局限明示): winreg 标准库只读探测键存在性, 不做任何写/删。

    2026-10-16 W6: 根键名归一去冒号——兼容 `HKLM:\\Software`(PowerShell 冒号形态)与 `HKLM\\Software`(reg.exe 形态)。
    """
    try:
        import winreg
    except ImportError:
        return False
    parts = reg_path.replace("/", "\\").split("\\")
    root_map = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER,
                "HKCR": winreg.HKEY_CLASSES_ROOT, "HKU": winreg.HKEY_USERS,
                "HKCC": winreg.HKEY_CURRENT_CONFIG}
    root = root_map.get(parts[0].upper().rstrip(":"))
    if root is None or len(parts) < 2:
        return False
    try:
        with winreg.OpenKey(root, parts[1].lstrip("\\")):
            return True
    except OSError:
        return False


# ══════════════════════════════════════════════════════════════════════
# 五、写删目标识别（2026-10-16 小欧 文档[36] 第五章新增）
# ══════════════════════════════════════════════════════════════════════
# 动词表分两层: 宽表答「改不改动东西」(通道 B 入口门 + 沙箱 F-B 两个消费方),
#               细表三张答「改动是什么后果」, 供归属分类分线: 删(move 源)/写(move 目标·重定向)。
# 公共工序只到文本预处理一级(换行归一 → 引号涂空 → $env: 展开), prepare_shell_text 一次产出、三判据共用。
# 路径抽取不复用: move 源/目标需位置序走 _extract_shell_move_paths 有序切词;
#               其余走 shell_extract_abs_win_paths(它按引号组+裸路径组拼接, 位置序被打乱)。
# 函数化(老陈裁定「不拆模块, 但必须函数化」): 本节 8 个单一职责函数
#     决策层  _verb_flags / shell_has_write_intent
#     工序层  prepare_shell_text / _collect_targets
#     策略层  _assign_to_lines / _shell_path_lines / _dedup_keep_order
#     出入口  shell_write_and_delete_paths(一次返回两列清单)


class ShellText(NamedTuple):
    """一条命令的两种用途文本 — 小欧 2026-10-16（[36] 5.3.3）

    用不可变产物而非让各出入口各跑一遍预处理: 编排层跑一次, 三个判据共用同一份文本(KISS-DIRECT)。
    """
    extract_src: str   # 抽取用: 换行归一 + $env: 展开的原文 —— 抽路径要保住含空格完整路径
    intent_src: str    # 判意图用: 换行归一 + 引号内容涂成等长空格


def prepare_shell_text(command: str) -> ShellText:
    """预处理只跑这一次 — 小欧 2026-10-16（[36] 5.3.3）

    抽取用文本先展开 $env: —— 否则 `$env:TEMP\\a.txt` 形态抽不到盘符路径(现网既有语义, 不改);
    判意图用文本把引号涂成等长空格 —— 保偏移, 防 `Select-String -Pattern "del"` 误判。
    """
    normalized = (command or "").replace("\r\n", " ").replace("\n", " ")
    return ShellText(shell_resolve_env_fragment(normalized), shell_blank_out_quotes(normalized))


def _dedup_keep_order(paths: List[str]) -> List[str]:
    """去重且保序(同一路径在 move 源与删动词目标中各出现一次, 只判一次) — 小欧 2026-10-16"""
    seen = set()
    out = []
    for p in paths:
        key = (p or "").lower()
        if p and key not in seen:
            seen.add(key)
            out.append(p)
    return out


def shell_has_write_intent(text: ShellText) -> bool:
    """这条 shell 命令会不会改动东西 — 小欧 2026-10-16（[36] 5.3.3）

    通道 B 入口门判据 —— 只读命令整条放行, 不打扰用户(HITL 零打扰)。
    不判权限、不判危险等级、不抽路径 —— 它只答有/无。
    """
    return bool(SHELL_WRITE_INTENT_RE.search(text.intent_src)) or ">" in text.intent_src


def _verb_flags(intent_src: str) -> Tuple[bool, bool, bool]:
    """判三类动作在这条命令里有没有 —— 只出开关, 不抽路径 — 小欧 2026-10-16（[36] 5.3.3）

    决策层: 把"要不要走哪条线"从"抽什么路径"里拆开, 谁也不该在别处重新匹配一遍动词(DRY)。
    返回    : (del_hit, write_hit, move_hit)
    """
    return (bool(SHELL_DELETE_RE.search(intent_src)),
            bool(SHELL_WRITE_RE.search(intent_src)) or ">" in intent_src,
            bool(SHELL_MOVE_RE.search(intent_src)))


def _collect_targets(extract_src: str, move_hit: bool) -> Tuple[List[str], List[str]]:
    """把移动类的源/目标抽出来 —— 只做抽取工序, 不做归属决策 — 小欧 2026-10-16（[36] 5.3.3）

    工序层: 必须走有序切词(保位置序), 与无序的 shell_extract_abs_win_paths 不能混用。
    """
    return _extract_shell_move_paths(extract_src) if move_hit else ([], [])


def _assign_to_lines(delete_line: List[str], write_line: List[str]) -> Tuple[List[str], List[str]]:
    """交集取严: 同一条路径既被删线提又被写线提, 只归删线 — 小欧 2026-10-16（[36] 5.3.3）

    策略层(规则⑤)。缺这一步会让同一路径在两线各判一次, 失败路径取决于代码顺序 = 行为不确定。
    保序: 一律用列表推导过滤, 不用 sorted(会打乱命令里出现的先后, 而失败路径要报给用户)。
    """
    both = {p.lower() for p in delete_line} & {p.lower() for p in write_line}
    if not both:
        return delete_line, write_line
    return ([p for p in delete_line if p.lower() in both]
            + [p for p in delete_line if p.lower() not in both],
            [p for p in write_line if p.lower() not in both])


def _shell_path_lines(text: ShellText) -> Tuple[List[str], List[str]]:
    """写删目标归属分类 —— 编排层, 返回 (删线路径, 写线路径) — 小欧 2026-10-16（[36] 5.3.3）

    归属规则五条, 顺序即优先级:
      ① 移动动词的【源参数】→ 删线(从原位抹掉, 与 del 同级)
      ② 移动动词的【目标参数】→ 写线(可任务级授权)
      ③ 删除动词命令里的绝对路径 → 删线
      ④ 纯写动词命令里、或重定向 > / >> 的绝对路径 → 写线
      ⑤ **交集取严**: 同一条路径既被删线提又被写线提 → 只归删线, 从写线剔除。

    ★落码时发现的第 7 处设计缺陷: abs_paths 不带"属于哪个动词"的信息, 混合命令无法按动词分线。
    处置(取严, 不引新抽象): 删写动词**同时命中**时 abs_paths 一律归删线, 写线只收 move 目标。
    理由: 误把写路径归删线 = 更严(安全), 反向则是放宽(危险); 且与搬迁前实码行为一致 = 零退化。

    只编排, 不含逻辑(SLAP/KISS-DIRECT):
      决策 → _verb_flags  工序 → _collect_targets + 一次 shell_extract_abs_win_paths  策略 → _assign_to_lines
    """
    del_hit, write_hit, move_hit = _verb_flags(text.intent_src)
    if not (del_hit or write_hit or move_hit):
        return [], []                                   # 纯读命令: 两口皆空, 不做无用抽取
    abs_paths: List[str] = (shell_extract_abs_win_paths(text.extract_src)
                            if (del_hit or write_hit) else [])
    move_src, move_dst = _collect_targets(text.extract_src, move_hit)
    if del_hit and not write_hit:
        delete_line, write_line = move_src + abs_paths, move_dst      # 规则①③
    elif write_hit and not del_hit:
        delete_line, write_line = move_src, move_dst + abs_paths      # 规则②④
    else:
        delete_line, write_line = move_src + abs_paths, move_dst      # 删写同现: 取严归删线
    return _assign_to_lines(_dedup_keep_order(delete_line),
                            _dedup_keep_order(write_line))


def shell_write_and_delete_paths(text: ShellText) -> Tuple[List[str], List[str]]:
    """取一条 shell 命令的 (删线路径清单, 写线路径清单) — 小欧 2026-10-16（[36] 5.3.3）

    干什么用: shell 路径检查(通道 B)的唯一取路径入口 —— 本函数**只取路径, 不判权限**。
              两个清单分别交 delete_path_check.validate_delete / write_path_check.validate_write 判权限。

    为什么是一个函数返回两列, 而不是"删线一个门、写线一个门"(北京老陈 2026-10-16 裁定):
      拆分版下两个门各自内部都要把整套判定跑一遍(扫动词 → 抽路径 → 切 move 参数 → 分线 → 去重),
      而调用方**两个清单都要** → 同一套判定白跑两遍(实测计数确认 = 2 次)。

    契约: 返回去重保序的盘符绝对路径; 相对路径 / UNC / ~ / 未展开的 $env: 形态一律不抽
          (交沙箱预检 SHELL_OUTSIDE_TARGET_RE 覆盖)。结论由下游 path_classify_category.classify_forbidden_path 出。
    """
    return _shell_path_lines(text)