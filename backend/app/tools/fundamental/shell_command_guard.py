# -*- coding: utf-8 -*-
"""shell 命令静态守卫（纯函数单源）—— 执行前的静态风险判定，沙箱闸与出池判定共用。

三类同域关注点合居一处（同属「这条 shell 命令静态看起来有什么风险」，故不拆分）：
  · 只读白名单判定    —— 可否免预检直放（READONLY_PREFIXES / FAST_CHANNEL_FORBIDDEN / is_readonly_whitelisted）
  · 命令规范化        —— 拼接折叠与去引号（normalize_for_intent，供下两者前置）
  · 杀进程防护        —— 不可隔离动词与受保护进程（UNCONTAINABLE_VERBS / is_process_kill_protected）

位置: app/tools/fundamental/，与 execute_shell_command.py / execute_shell_command_safety.py /
shell_engine.py 同目录（shell 代码同置，不散落 utils）。依赖方向由 tests/test_architecture_boundaries.py
强制守护: tools 禁 import services/safety, safety 禁 import services —— 本模块仅依赖 fnmatch/re,
且 safety→tools 属合法方向(先例: tool_safety_checker 一直 import execute_shell_command_safety)。

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
2026-10-14 小欧 - 文档[33] 4.11-A: 收编 executor 的 _is_shell_tool/_WRITE_CMD_RE 等 9 符号与 path_safe_check 的
  _extract_abs_win_paths/_ABS_WIN_PATH_RES, 新增删除动词正则 _DELETE_CMD_RE(供 4.10-1 判 mode=delete);
  _strip_quoted 改名 mask_quoted_spans 并还 _QUOTED_SPAN_RE 双源债
2026-10-16 小欧 - [36] 洞1+洞2 修复(文档[36]第三章审计结论, 就地最小增量, 未新建模块):
  ①洞1 写意图表补 Remove-ItemProperty —— 原表用 \b(?:Remove-Item|...)\b, 该动词因尾 \b 不成立
    而不在表内, 导致 `Remove-ItemProperty <受保护区>` 连 shell_path_check 第一道门都进不去
    = 该命令全程零路径检查(非"判错档", 是不检查)。补入后由 _DELETE_CMD_RE 送删线。
  ②洞2 移动类分线 —— 新增 _MOVE_CMD_RE / _MOVE_DEST_SWITCHES / _MOVE_TOKEN_RE /
    _ABS_PATH_HEAD_RE 与 _extract_move_paths(command) -> (源, 目标)。
    病根: mv/Move-Item 只在写表(_DELETE_CMD_RE 不含) → 源与目标同走写线 → 源在 non_system 区
    命中写线的临时授权分支(is_temp_authorized 放行) → 授权即把受保护根搬走。
    不用 _extract_abs_win_paths 取源: 它按"引号组 + 裸路径组"拼接返回, 位置序被打乱
    (实测 `mv C:\src.txt "E:\dst dir"` 返回 [目标, 源]), 按下标取源会判反;
    本函数按文本顺序切 token, 故位置可靠。
    -Destination/-dest 之后的路径判为目标, 其余为源; 无开关时首路径为源、其余为目标
    (PS 位置写法与 bash/cmd `mv src dst` 同形)。只认盘符绝对路径, 相对路径不抽(交沙箱预检)。
  实测效果(授权后同路径): 删线 validate_delete=False(仍拦) vs 写线 validate_write=True(放行) ——
    即授权不再使删除语义失效; 未授权时两线同为"需确认", 与改动前一致(无退化)。"""
import fnmatch
import os
import re
from typing import List, Tuple

from app.tools.tools_alias_mapper import normalize_tool_name

# ══════════════════════════════════════════════════════════════════════
# 一、只读白名单: 可否免预检直放
# ══════════════════════════════════════════════════════════════════════
# —— 判定规则的真实代码落点(v1.18 按北京老陈要求全部代码化) ———
READONLY_PREFIXES = ("get-", "ls", "cat", "type", "git status",
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
FAST_CHANNEL_FORBIDDEN = ("|", ";", "&", ">", ">>", "$", "(", ")", "`", "<", "\n", "\r")
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


def _decode_char_codes(text: str) -> str:
    """[char]83 → S(十进制; 十六进制 0x 形态暂不覆盖, 见残留)。至不动点(连写嵌套一次消不净)。"""
    prev = None
    while prev != text:
        prev = text
        text = _CHAR_RE.sub(lambda m: chr(int(m.group(1)) & 0x10FFFF), text)
    return text


def normalize_for_intent(command: str) -> str:
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


# ══════════════════════════════════════════════════════════════════════
# 三、杀进程防护: 不可隔离动词 + 受保护进程(2026-10-08 事故驱动)
# ══════════════════════════════════════════════════════════════════════
# —— 不可隔离动词: 沙箱预检"真跑"时副作用必落宿主, 不得进预检 ————————————————————
# 收录标准= 副作用与 cwd 无关且现有词表只到 MEDIUM(弹窗后仍进预检)拦不住者;
#   HIGH 项(Stop-Computer/Format-Volume/shutdown)预检前就 blocked, 不重复收录(DRY)。
UNCONTAINABLE_VERBS = (
    "stop-process", "taskkill", "wmic process",     # 杀进程(任意形态: -Id/-Name/管线/按镜像名)
    "stop-service", "restart-service",              # 停服务(现有词表只有 sc/net, 漏 Stop-Service)
    "pkill", "killall", "kill",                     # bash 侧杀进程(现有 \bkill\b 匹配不到 pkill)
)
# 2026-10-08 小欧 前后向断言用 [a-z0-9_-] 字符类而非 \b: \b 会让 kill 命中 "killall"/"taskkill" 内部。
_UNCONTAINABLE_RE = re.compile(
    r"(?<![a-z0-9_-])(?:" + "|".join(re.escape(v) for v in UNCONTAINABLE_VERBS) + r")(?![a-z0-9_-])",
    re.IGNORECASE)
# 2026-10-10 小欧 猎杀#1#2(WMI/CIM 方法杀): Get-WmiObject … $_.Terminate() / Get-CimInstance … Invoke-CimMethod ——
#   动词表(Stop-Process/taskkill/…/kill)与 43 条(无 Get-WmiObject/CIM 口径)全链漏网 → 预检真跑。
#   口径: 只认方法调用点 `.Terminate(`/`.Kill(` 与 cmdlet 名 Invoke-CimMethod, 不认裸词 terminate
#   (正文"terminate the loop"类误伤面大, 取严也要有边)。Get-WmiObject 裸查询(无 Terminate)不认, 它只是读。
_METHOD_KILL_RE = re.compile(r"\.\s*(terminate|kill)\s*\(", re.IGNORECASE)
_CIM_KILL_RE = re.compile(r"(?<![a-z0-9_-])invoke-cimmethod(?![a-z0-9_-])", re.IGNORECASE)
# 2026-10-10 小欧 猎杀#4(Base64): -EncodedCommand(PS 为 UTF-16LE 的 base64)内容静态不可见, 全链零规则。
#   取严: 见到即转 HITL(用户面对 base64 同样无法有效确认, 属残留风险, 不冒充已解决)。
#   口径: 只认 -EncodedCommand / -enc 全词; -e 单字母不认(撞 -ErrorAction 类, 误伤面大)。
_ENCODED_RE = re.compile(r"(?<![a-z0-9_-])-(?:encodedcommand|enc)\b", re.IGNORECASE)
# 2026-10-08 小欧 PID 目标提取三形态: Stop-Process -Id / taskkill /PID / kill [-9] PID; 按名与 pkill 返空集。
_PID_TARGET_RES = (
    re.compile(r"stop-process\W*(?:[\w-]+\s+)*-id\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"/pid\s+(\d+)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])kill\s+(?:-[\w]+\s+)*(\d+)", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#7(/FI): taskkill /FI "PID eq 123" —— 无 /PID 开关, 旧口径零提取。
    re.compile(r"(?<![a-z0-9_-])\bpid\s+eq\s+(\d+)", re.IGNORECASE),
)

# —— 按名杀目标提取(2026-10-10 小欧 新增, 审计 P1-3): 补保护盾对真实事故形态的盲区 ————————
# E2E P9-03 事故命令 `Get-Process python | Stop-Process -Force` 是按名杀, _PID_TARGET_RES 只认 -Id,
# 抽出恒为空集 → 原保护盾对事故形态贡献为 0。四个形态: -Name / Get-Process 管道 / taskkill /IM / killall。
# 组装(受保护进程名从哪来)仍归 safety 侧 tool_safety_checker._protected_process_names, 本模块只出纯函数。
_NAME_TOKEN = r"[\w.*?+-]+(?:\.exe)?"
_KILL_NAME_RES = (
    re.compile(r"(?<![a-z0-9_-])-name\s+(" + _NAME_TOKEN + r"(?:\s*,\s*" + _NAME_TOKEN + r")*)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])/im\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])killall\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#7(/FI): taskkill /FI "IMAGENAME eq X" —— 无 /IM 无 /PID, 旧口径零提取 → 仅HITL。
    re.compile(r"(?<![a-z0-9_-])imagename\s+eq\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#8(wmic/WMI 名): `wmic process where name='x' [call terminate|delete]` /
    #   WMI -Filter "name='x'" / CIM -Query "…WHERE Name='x'" —— 名在过滤子句里, 旧口径零提取。
    #   前后向断言挡 hostname/filename("…name" 前是 word 字符则不认)。
    re.compile(r"(?<![a-z0-9_-])name\s*=\s*['\"]?(" + _NAME_TOKEN + r")['\"]?", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#10(pkill): `pkill [-9] [-f] <模式>` 实参即目标模式, 旧口径零提取。
    #   交 _name_matches 走 fnmatch(模式串与受保护名双向匹配; `.*` 天然全中)。首字符禁 `-`(挡 -9/-f 本身被当成名)。
    re.compile(r"(?<![a-z0-9_-])pkill\s+(?:-[\w]+\s+)*(?:-f\s+)?([A-Za-z0-9_.?*][\w.*?+-]*(?:\.exe)?)",
               re.IGNORECASE),
)


def _strip_quotes(s: str) -> str:
    """去首尾引号(名提取的引号在归一文里已无, 此函数只处理原文残留) — 小欧 2026-10-10"""
    return (s or "").strip().strip("\"'")


def extract_kill_target_names(command: str) -> set:
    """按名杀的进程名目标集合(逗号多值已拆开) — 小欧 2026-10-10

    适用: 供 is_process_kill_protected 补按名口径; 按名形态抽不出 PID(extract_kill_target_pids 返空集),
    只靠 PID 的保护盾会漏。归一化(.exe 去尾 + casefold + 通配)在 _name_matches 内做, 此处只出原样名。
    2026-10-10 小欧 补(猎杀#5#6: 引号名 `-Name "python"` / `/IM "x.exe"` / `-Name 'a','b'` 原文零提取):
      同步扫归一文(归一已去引号), 复用 P1-1 并集模式; 不放宽 token 类(动 token 类会放宽原文口径, 不如并集干净)。
    """
    names = set()
    if has_uncontainable_intent(command):
        for text in {command or "", normalize_for_intent(command)}:
            for rx in _KILL_NAME_RES:
                for m in rx.finditer(text):
                    names.update(_strip_quotes(n) for n in re.split(r"\s*,\s*", m.group(1)))
            names.update(extract_kill_target_names_from_pipeline(text))
    return {n for n in names if n}


def extract_kill_target_names_from_pipeline(command: str) -> set:
    """`Get-Process <名> | Stop-Process` 管道形态的目标名 — 小欧 2026-10-10

    独立成函数: 该形态不经 -Name 参数, 但正是 P9-03 事故原形, 不抽则保护盾对事故形态依旧为 0。
    """
    out = set()
    for m in re.finditer(r"(?<![a-z0-9_-])get-process\s+((?![\s|;&]*\|)[\w.*?-]+(?:\.exe)?)",
                         command or "", re.IGNORECASE):
        out.add(m.group(1).strip().strip("\"'"))
    return {n for n in out if n}


def has_uncontainable_intent(command: str) -> bool:
    """命令是否含不可隔离动词(杀进程/停服务) — 小欧 2026-10-08

    适用: shell 沙箱预检前静态判定, 命中转 HITL 不得 run(预检在宿主真跑, 跑即防线自破)。
    排除: Stop-Computer/Format-Volume/shutdown 已是 HIGH 级, 安全检查阶段就 blocked, 收录即重复(DRY)。
    2026-10-10 小欧 补: 原文与归一文取并集(拼接还原的 'Stop'+'-Process' 原文查不到, 归一后查得到)。
    2026-10-10 小欧 补(猎杀#1#2#4): .Terminate()/.Kill() 方法调用、Invoke-CimMethod、-EncodedCommand
      同视为不可隔离意图(前两者全链漏网预检真跑; Base64 内容不可见, 转 HITL 为残留风险)。
    """
    if not command:
        return False
    norm = normalize_for_intent(command)
    return (bool(_UNCONTAINABLE_RE.search(command)) or bool(_UNCONTAINABLE_RE.search(norm))
            or bool(_METHOD_KILL_RE.search(command)) or bool(_CIM_KILL_RE.search(command))
            or bool(_ENCODED_RE.search(command)))


def extract_kill_target_pids(command: str) -> set:
    """命令显式指定的杀进程目标 PID 集合 — 小欧 2026-10-08

    覆盖 Stop-Process -Id a,b / taskkill /PID n / kill [-9] n; 按名与管线形态枚举不了, 返回空集。
    2026-10-10 小欧 补: 同样取原文与归一文并集, 覆盖 & ('Stop-Process') -Id n 这类带引号形态。
    """
    pids = set()
    for text in {command or "", normalize_for_intent(command)}:
        for rx in _PID_TARGET_RES:
            for m in rx.finditer(text):
                pids.update(int(x) for x in re.split(r"[\s,]+", m.group(1)) if x.isdigit())
    return pids


def _name_matches(target: str, protected_names: set) -> bool:
    """杀进程目标名是否命中受保护进程名 — 小欧 2026-10-10

    口径: 统一去 .exe 后缀 + casefold(PowerShell -Name 用无后缀名, taskkill /IM 用带后缀镜像名);
    含通配符走 fnmatch(PowerShell -Name python* / pkill -f 支持通配)。
    """
    norm = lambda s: (s or "").strip().casefold().removesuffix(".exe")
    tgt = norm(target)
    if not tgt:
        return False
    for name in protected_names or ():
        pname = norm(name)
        if not pname:
            continue
        if fnmatch.fnmatch(pname, tgt) or fnmatch.fnmatch(tgt, pname):
            return True
    return False


def is_process_kill_protected(command: str, protected_pids: set, protected_names: set = None) -> bool:
    """命令目标是否命中受保护进程 — 小欧 2026-10-08

    适用: 阻止杀宿主关键进程(后端自身/父进程/shell 池), 命中即 blocked。
    取值: protected_pids/protected_names 均由调用方注入(组装归 safety 侧 tool_safety_checker, 见 8.4)。
    2026-10-10 小欧 增按名匹配(审计 P1-3): 事故命令 `Get-Process python | Stop-Process -Force`
      属按名杀, 原实现只抽显式 PID 恒返空集, 保护盾对真实事故形态贡献为 0;
      补 protected_names 后该形态才拦得住。签名新增第三参(可选, 不传则退化为仅 PID 口径)。
    2026-10-10 小欧 增无目标兜底(猎杀#9): 见 _unscoped_process_kill。
    """
    if not command:
        return False
    if protected_pids and (extract_kill_target_pids(command) & set(protected_pids)):
        return True
    if _unscoped_process_kill(command):
        return True
    if not protected_names:
        return False
    return any(_name_matches(target, protected_names)
               for target in extract_kill_target_names(command))


_PROCESS_KILL_VERBS = (
    "stop-process", "taskkill", "wmic process",     # PS/CMD 侧(停服务动词不在此列)
    "pkill", "killall", "kill",                     # bash 侧
)
_PROCESS_KILL_VERB_RE = re.compile(
    r"(?<![a-z0-9_-])(?:" + "|".join(re.escape(v) for v in _PROCESS_KILL_VERBS) + r")(?![a-z0-9_-])",
    re.IGNORECASE)
# 管线进杀器: `… | Stop-Process/taskkill/kill…`(有名/有PID 的走正常口径, 这里只管裸的)
_PIPE_KILL_RE = re.compile(r"\|\s*(?:stop-process|taskkill|pkill|killall|kill)\b", re.IGNORECASE)
# 求助与演习开关: /?、--help、-WhatIf —— 这些形状不杀生, 兜底必须让路
_HELPISH_RE = re.compile(r"/\?|--help|(?<![a-z0-9_-])-h\b|-whatif\b", re.IGNORECASE)
# 引号 span: 兜底只认引号之外的动词 —— `echo "kill"` 纯提及必须留在 HITL, 不许升 blocked(取严但可确认)。
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def mask_quoted_spans(text: str) -> str:
    """把引号片段替换为**等长空格**(保偏移, 便于同段文本做两种判断) —— 小欧 2026-10-14

    迁自 path_safe_check._strip_quoted（文档[33] 4.11-A）。**改名消歧**：本文件既有
    _strip_quotes(:175) 是「去首尾引号」, 与本函数「引号段整体遮蔽」语义不同, 近似名并存必误用。
    顺带还 _QUOTED_SPAN_RE 双源债(原两处各编译一份, 字面顺序相反语义等价), 现单一真源在本文件。
    """
    return _QUOTED_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)


def _wmic_mass_action(text: str) -> bool:
    """wmic process 配 delete / call terminate 即质量动作(裸 `wmic process [get …]` 查询不在此列)。"""
    return (bool(re.search(r"(?<![a-z0-9_-])wmic\s+process\b", text, re.IGNORECASE))
            and bool(re.search(r"(?<![a-z0-9_-])(?:delete|call\s+terminate)\b", text, re.IGNORECASE)))


def _unscoped_process_kill(command: str) -> bool:
    """无目标杀进程形 → True(直接 blocked)。2026-10-10 小欧 猎杀#9 —

    病根: 管线裸杀(`Get-Process | Stop-Process`)、无参 taskkill、wmic 质量动作、
    `kill %1`、`kill -9 $(…)` 等静态抽不出任何目标(PID/名皆空), 用户面对弹窗同样
    枚举不出目标, 确认无意义; 且目标集合无上界(含后端自身可能)。
    边界:
      · 有名/有 PID(无论是否受保护)走原口径, 不由此函数拦截(HITL 由上游定);
      · 停服务动词(Stop-Service/Restart-Service)不在此列 —— `Stop-Service x` 的 x 即目标, 作用域明确;
      · 求助与演习(/ ?, --help, -WhatIf)让路, 不拦;
      · wmic 裸查询(`wmic process [get …]`)让路, 只拦配 delete/call terminate 的质量动作。
    """
    text = command or ""
    if _HELPISH_RE.search(text):
        return False
    bare = _QUOTED_SPAN_RE.sub("", text)   # 兜底只认引号之外的动词(`echo "kill"` 留 HITL)
    if not (_PROCESS_KILL_VERB_RE.search(bare) or _METHOD_KILL_RE.search(bare)
            or _CIM_KILL_RE.search(bare)):
        return False
    if extract_kill_target_pids(command) or extract_kill_target_names(command):
        return False                                            # 有目标 → 走原口径
    if _PIPE_KILL_RE.search(bare):
        return True                                             # 管线裸杀
    if re.search(r"(?<![a-z0-9_-])taskkill\b", bare, re.IGNORECASE):
        # 无 /IM /PID /FI, 或 /FI 抽不出目标(如 STATUS 全杀) —— 到此目标恒空, 皆无界质量动作
        return True
    if _wmic_mass_action(bare):
        return True                                             # wmic 质量动作
    if _METHOD_KILL_RE.search(bare) or _CIM_KILL_RE.search(bare):
        return True                                             # 方法杀/CIM 无名 → 无界
    if re.search(r"(?<![a-z0-9_-])(?:stop-process|pkill|killall|kill)\b", bare, re.IGNORECASE):
        return True                                             # 裸杀器(`kill %1`/`kill -9 $(…)` 之类)
    return False


# ══════════════════════════════════════════════════════════════════════
# 四、白名单判定入口
# ══════════════════════════════════════════════════════════════════════
def is_readonly_whitelisted(command: str) -> bool:
    """4.1#4 只读白名单判定; 安全放行须先跑 _scan_command_danger_intent, 纯路由调用点不适用 — 小欧 2026-10-04"""
    lowered = command.strip().lower()
    if not lowered.startswith(READONLY_PREFIXES):                    # 3.2.1 与常量单源(消除双源双维护) — 小欧-2026-09-18
        return False
    return not any(op in command for op in FAST_CHANNEL_FORBIDDEN)


# ══════════════════════════════════════════════════════════════════════
# 五、shell/Windows 命令文本处理与工具分类（文档[33] 4.11-A 收编）
# ══════════════════════════════════════════════════════════════════════
# 落点判据(文档[33] 4.19): 本节符号属「工具分类知识 / 命令文本解析」, 与本文件既有
# is_readonly_whitelisted / has_uncontainable_intent 同域, 故收编于此而非新建文件(YAGNI)。
# 逐字复制自原属地, 只改归属不改逻辑(AGENTS 1.4)。

# —— 工具分类判定 ——
def _is_shell_tool(tool_name: str) -> bool:
    """shell 类判定以注册表真实工具名为准(v1.25 F4 回归修正): execute_shell_command 注册名'bash'且
    category=FUNDAMENTAL, 不能仅凭ToolCategory.SHELL判定(该枚举已于2026-10-02删除, 仅剩which也归SYSTEM);
    显式列 shell 执行类归一名, 新增须同步加入本集合

    迁自 executor.py:70（文档[33] 4.11-A）。调用期依赖 normalize_tool_name 已在文件头显式导入,
    杜绝「import 通过但调用 NameError」。
    """
    _shell = frozenset({"bash"})  # 2026-10-02 小欧 - 随注册名改名; 原 executeshellcommand/executeshellcommandsafety 为从未注册的死项, 一并清
    return normalize_tool_name(tool_name) in _shell


# —— F-B 写意图扫描器(真实实现, 补重定向与词表): 只判越界写意图, 不判危险等级 ——
_WRITE_CMD_RE = re.compile(
    r"\b(?:Remove-Item|Remove-ItemProperty|rm|ri|del|erase|rd|rmdir|Move-Item|mi|Copy-Item|cpi|cp|mv"
    r"|New-Item|ni|Set-Content|Add-Content|ac|Out-File|Expand-Archive"
    r"|reg(?:\.exe)?(?=\s|$)|setx|regedit(?:\.exe)?(?=\s|$))\b",
    re.IGNORECASE)
# v1.23 V-A: reg/regedit 的边界由 (?=\s|$) 前瞻断言(不消耗字符)——原 (?:\s|$) 会把尾随空格
# 吃进 group(0)("reg " ∉ _REGISTRY_SYSTEM_VERBS), 致 v1.22 W1 注册表特判永不命中、红洞未堵。
# 前瞻后 group(0)="reg" 干净可查集合; 双空格场景亦因 lookahead 不消费而照常命中。
_REDIRECT_RE = re.compile(r">>?\s*\"?([^\"\r\n<>|;]+)")   # v1.21 Z1: 重定向目标提取(> 与 >> 同权)
_OUTSIDE_TARGET_RE = re.compile(
    r"(?:"
    r"\b[a-z]:[\\/]"                 # 绝对盘符 C:\ D:\ / C:/ D:/ (正斜杠亦属越界写, 防逃逸)
    r"|\\\\[\w.\-]+\\"               # UNC \\host\share\
    r"|\bhk(?:lm|cu|cr|u|cc):[\\/]"  # 注册表驱动器 HKLM:/HKCU: 等
    r"|\$env:[\w]+[\\/]"             # $env:XXX\ 展开(解析前形态)
    r"|[\"']?~[\\/]"                 # ~ 家目录展开
    r")", re.IGNORECASE)
_SANDBOX_SELF_RE = re.compile(r"omniagent_sandbox", re.IGNORECASE)   # N7 carve-out 标识
_REGISTRY_SYSTEM_VERBS = frozenset({"reg", "reg.exe", "regedit", "regedit.exe", "setx"})
# v1.22 W1: 注册表/系统配置写动词命中即拦——命令行写法目标多为无冒号 `HKLM\...`,
# 不匹配带冒号的 _OUTSIDE_TARGET_RE; 且 Job Object 完全不隔离注册表/环境变量,
# 沙箱内真实执行=真写系统。与 G1/2.4「registry 类只静态分析不动态执行」同哲学, 无需看目标形态。

# —— 删除动词正则(文档[33] 4.11-A-3 新增, 供 4.10-1 判 mode="delete")——
# 病根(文档[33] 错点4): _WRITE_CMD_RE 把删与写混在一张表, 命令含删动词时 mode 仍为 "write",
# 于是删系统禁区只被判「可授权的写」而非「不可授权的删」——授权后等于放行删系统目录。
# 与 _WRITE_CMD_RE 并列而非替换(后者仍需覆盖写/搬/注册表)。
_DELETE_CMD_RE = re.compile(
    r"(?<![a-z0-9_-])(?:Remove-Item|Remove-ItemProperty|del|erase|rd|rmdir|ri|rm)(?![a-z0-9_-])",
    re.IGNORECASE)

# —— 移动类动词(2026-10-16 小欧 [36] 洞2) ——
# 病根: mv/Move-Item 只在写表(L388), _DELETE_CMD_RE 不含它 → 整条命令走写线 →
#   源路径若在 non_system 区, _check_known_risks 走 grant_temp_auth 可授权 → 授权即把受保护根搬走。
# 处置: 移动类命令按参数位置拆「源(被删)/目标(被写)」, 源走删线、目标走写线。
#   尾 (?![a-z0-9_-]) 与 _DELETE_CMD_RE 同款, 故 Move-ItemProperty 不会被 Move-Item 误命中。
# 2026-10-16 小欧 三堂会审补: cmd 内建 move / ren(+别名 Rename-Item) 与 mv 同语义(删源+写目标),
#   且三者皆不在 _WRITE_CMD_RE, 连第一道门都进不去(=零路径检查)。只进本移动表, 不进 _WRITE_CMD_RE
#   (move 是英文常用词, 进写表会在 F-B 目标窗口扫描与 echo 类命令中误伤; 本表仅在通道 B 入口门处并列判定)。
_MOVE_CMD_RE = re.compile(r"(?<![a-z0-9_-])(?:Move-Item|Rename-Item|move|ren|mi|mv)(?![a-z0-9_-])",
                          re.IGNORECASE)
_MOVE_DEST_SWITCHES = frozenset({"-destination", "-dest", "-newname"})   # 其后路径=目标
# 2026-10-16 小欧 三堂会审修(P0 退化): 裸 token 必须在语句分隔符处断开, 与 _ABS_WIN_PATH_RES 同口径
#   (原 \S+ 把 `a.txt>C:\Windows\evil.log` 粘成一个 token, 当源走删线后畸形串被直接放行=写目标逃逸);
#   引号段仍整体保留(含空格/&/; 的合法路径名不受损)。
_MOVE_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s"\'<>|;&]+')
_ABS_PATH_HEAD_RE = re.compile(r'^[a-zA-Z]:[\\/]')          # 只认盘符绝对路径(与 _ABS_WIN_PATH_RES 同口径)


def _extract_move_paths(command: str) -> Tuple[List[str], List[str]]:
    """移动类命令按参数位置拆「源(被删)」与「目标(被写)」 — 小欧 2026-10-16（[36] 洞2）

    为什么不复用 _extract_abs_win_paths: 它按「引号组 + 裸路径组」拼接返回, 位置序被打乱
    (实测 `mv C:\\src.txt "E:\\dst dir"` 返回 [目标, 源]), 按下标取源会判反。
    本函数按文本顺序切 token, 故位置可靠。
    分派: 有 -Destination/-dest → 其后路径=目标、其余=源；无 → 首个路径=源、其余=目标
    (PS 位置写法与 bash/cmd `mv src dst` 同形)。只认盘符绝对路径, 相对路径不抽(交沙箱预检)。
    """
    tokens = [t.strip("\"'") for t in _MOVE_TOKEN_RE.findall(command)]
    paths: List[Tuple[int, str]] = []
    dest_idx: List[int] = []
    for i, t in enumerate(tokens):
        if _ABS_PATH_HEAD_RE.match(t):
            paths.append((i, t))
        elif t.lower() in _MOVE_DEST_SWITCHES:
            dest_idx.append(i)
    if dest_idx:
        cut = min(dest_idx)
        return ([p for i, p in paths if i < cut], [p for i, p in paths if i > cut])
    if paths:
        return [paths[0][1]], [p for _, p in paths[1:]]
    return [], []


def _resolve_env_fragment(fragment: str) -> str:
    """目标窗口内 $env:XXX → 实际值(FP3 豁免判定前先展开, 防 $env:TEMP 逃过盘符正则)"""
    return re.sub(r"\$env:(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), fragment,
                  flags=re.IGNORECASE)


def _ps_literal_path(p) -> str:
    """PowerShell -LiteralPath 字面量引号: 单引号包裹, 内部单引号转义为 '' (防路径含 ' 时命令行断裂)"""
    return "'" + str(p).replace("'", "''") + "'"


# —— bash 命令里的绝对路径抽取(迁自 path_safe_check:436-459, 见 4.11-A-2)——
# 引号包裹的取完整(含空格路径), 裸路径取到空白/引号/重定向/管道/连接符为止
_ABS_WIN_PATH_RES = (
    re.compile(r'"([a-zA-Z]:[\\/][^"]+)"'),      # 双引号
    re.compile(r"'([a-zA-Z]:[\\/][^']+)'"),      # 单引号
    re.compile(r'([a-zA-Z]:[\\/][^\s"\'<>|;&)]*)'),  # 裸路径
)


def _extract_abs_win_paths(text: str) -> List[str]:
    """抽取命令中的全部绝对路径 — 小欧 2026-10-14

    引号区先完整取出, 裸路径**只在引号区之外**扫描: 否则同一段引号路径会被裸正则再截断成
    `E:\\my`(实测误拦已授权目录 `E:\\my proj`, 且 failed_path 报错路径)。
    去重保序。

    迁自 path_safe_check.py:444（文档[33] 4.11-A-2）。调用 mask_quoted_spans 不复制正则。
    """
    quoted: List[str] = [m for rx in _ABS_WIN_PATH_RES[:2] for m in rx.findall(text)]
    bare = _ABS_WIN_PATH_RES[2].findall(mask_quoted_spans(text))
    found: List[str] = []
    for p in quoted + bare:
        p = p.strip().rstrip("\\")
        if p and p.lower() not in [x.lower() for x in found]:
            found.append(p)
    return found


def _registry_key_exists(reg_path: str) -> bool:
    """registry 静态分析(2.4 局限明示): winreg 标准库只读探测键存在性, 不做任何写/删。
    v1.22 W6: 根键名归一去冒号——兼容 `HKLM:\\Software`(PowerShell 冒号形态)与 `HKLM\\Software`(reg.exe 形态)。

    迁自 executor.py:417（文档[33] 4.11-A-2），与 _is_shell_tool 同域故同归本文件。
    """
    import winreg
    root_map = {"HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER, "HKCU": winreg.HKEY_CURRENT_USER}
    parts = reg_path.replace("/", "\\").split("\\", 1)
    root = root_map.get(parts[0].upper().rstrip(":"))
    if root is None or len(parts) < 2:
        return False
    try:
        with winreg.OpenKey(root, parts[1].lstrip("\\")):
            return True
    except OSError:
        return False
