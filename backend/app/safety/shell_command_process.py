# -*- coding: utf-8 -*-
"""shell 命令静态处理单一真源 —— 文本规范化 / 只读白名单 / 沙箱宽表（零状态·零 I/O）

职责: 提供 shell 命令的**只读白名单、命令规范化、沙箱越界宽表**三类静态判据; **不判权限、不判危险等级、不做动作分线解析**。
分层: 文本原子/宽表(本模块) 与 动作解析(shell_parse) 与 判权限(read/write/delete_path_check) 三层严格分开(老陈 2026-10-16 裁定)。

关注点(按用途归类, 老陈 2026-10-16 裁定; 2026-10-18 收敛):
  一、只读白名单    —— SHELL_READONLY_PREFIXES / SHELL_FAST_CHANNEL_FORBIDDEN / is_shell_readonly_whitelisted
  二、文本规范化    —— shell_normalize_command(拼接折叠/[char]解码) / shell_blank_out_quotes(引号涂空)
  三、沙箱宽表/越界  —— SHELL_WRITE_INTENT_RE / SHELL_REDIRECT_RE / SHELL_OUTSIDE_TARGET_RE 等(供沙箱 F-B 预检)
  四、工具分类与文本 —— is_shell_tool / shell_registry_key_exists / shell_ps_literal_path / shell_resolve_env_fragment
★"动作分线"(动词表 SHELL_DELETE_RE/SHELL_WRITE_RE/SHELL_MOVE_RE + 递归/强制删除判据 + 路径抽取
  shell_extract_abs_win_paths)已于 2026-10-18 全部迁往 app/safety/shell_parse/ 包
  (文档[38] §13.1.2/§13.2.3.5/§13.2.3.8); 本模块收敛为**沙箱宽表 + 只读白名单 + 规范化函数**, 词表/原子零复制(DRY)。
★自杀检查(杀进程防护)已于 2026-10-16 全部归并到 app/safety/shell_process_guard.py(老陈裁定),
  本模块不再持有任何杀进程相关的词表与判定函数。

位置: app/safety/。原居 app/tools/fundamental/shell_command_guard.py，2026-10-16 整文件下沉。
依赖方向: 仅 import os/re + app.tools.tools_alias_mapper(契约与元数据, 合法)，
  **不再 import 任何 app.tools.fundamental / app.tools.validate**, 也不 import shell_parse(单向)。

编辑历史:
2026-10-04 小欧 - 自 executor.py 迁入(原名 shell_readonly.py, 落 app/utils/), 内容未改。
2026-10-05 小欧 - 安全修复: FAST_CHANNEL_FORBIDDEN 补 $ ( ) 反引号 < 四类子表达式/命令替换/输入重定向载体(北京老陈裁定; 原缺口致 echo $(Start-Process calc) 直通真机执行任意命令)。
2026-10-05 小欧 - 补 \n \r: 换行符同为语句分隔符, 此前未禁致白名单可被绕过。
2026-10-08 小欧 - 新增不可隔离动词判定(事故驱动): UNCONTAINABLE_VERBS + has_uncontainable_intent/extract_kill_target_pids/is_process_kill_protected(Job Object 非硬墙, 词表漏 Stop-Process 致预检真跑杀掉后端自身, E2E P9-03; 只收 HIGH 拦不住者不与 SHELL_DANGEROUS_PATTERNS 重复)。
2026-10-10 小欧 - 审计 P1-1: 新增 normalize_for_intent(命中前先折叠拼接再去引号, 查杀 'Stop'+'-Process' 被 + 拆开的形态; 只增不减取严)。
2026-10-10 小欧 - 审计 P1-3: 新增按名杀目标提取 extract_kill_target_names(补 Get-Process python|Stop-Process 按名杀盲区)。
2026-10-10 小欧 09:55:09 - 位置与命名修正: 位置 app/utils→app/tools/fundamental, 更名 shell_static_guard.py(名副其实); 曾短暂拆三文件复核判过度拆分(YAGNI)并回一处。
2026-10-10 小欧 10:30 - 猎杀 10 bug 全修(探针实证, 门级 verdict 逐条验证): ①归一 v2([char]N 解码至不动点+剥噪音, 顺序解码→剥→折叠→去引号, 逗号/分号不动) ②动词层(.Terminate/.Kill 方法调用+Invoke-CimMethod+ -EncodedCommand 转 HITL) ③名提取(/FI、wmic、pkill -f、引号名) ④兜底 _unscoped_process_kill(有杀意无目标直接 blocked, 停服务动词让路)。
2026-10-16 小欧 - 整文件下沉: 自 shell_command_guard.py 整文件下沉 app/safety/(文件级复制零漂移), 正名 24 项符号, 新增写删目标识别 8 单一职责函数; 自杀检查全部归并 shell_process_guard.py。
2026-10-16 小欧 - 三堂会审: 删 shell_blank_out_quotes 重复定义(后者覆盖前者成死代码)与 danger/risk 随之失效的死 import。
2026-10-17 小欧 - 拆 SHELL_DESTRUCTIVE_DELETE_RES 为递归类+强制类, 新增 shell_has_recursive_delete(只认递归开关, 不含 Force 单开关), 供 shell_path_check 喂 recursive 使 R6(工作区外递归硬拦)生效。
2026-10-18 小欧 - [38] 13.2 重构: 迁出"动作分线"段(ShellText/prepare_shell_text/shell_has_write_intent/_verb_flags/_collect_targets/_assign_to_lines/_shell_path_lines/shell_write_and_delete_paths/_extract_shell_move_paths 及其私有 regex)至 app/safety/shell_parse/ 包; 本模块收敛为**词表与文本原子单一真源**(SHELL_DELETE_RE/SHELL_WRITE_RE/SHELL_MOVE_RE/SHELL_WRITE_INTENT_RE 等 + shell_blank_out_quotes/shell_resolve_env_fragment/shell_extract_abs_win_paths 等), 供解析包复用。词表/原子零复制(DRY, 受 test_shell_regex_baseline 词面基线锁死)。
2026-10-18 小欧 - [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入 shell_parse/): 上一版留在本模块的**动作分线残件**再整体移出 ——
  SHELL_DELETE_RE/SHELL_RECURSIVE_DELETE_RES/SHELL_FORCE_DELETE_RES/SHELL_DESTRUCTIVE_DELETE_RES/shell_has_recursive_delete/shell_has_destructive_delete → shell_parse/parse_delete.py;
  SHELL_WRITE_RE(含 _SHELL_WRITE_VERBS) → shell_parse/parse_write.py; SHELL_MOVE_RE → shell_parse/parse_move.py;
  shell_extract_abs_win_paths(含 _SHELL_ABS_WIN_PATH_RES) → shell_parse/lexer.py。
  本模块只剩**沙箱宽表 + 只读白名单 + 规范化**: 删死 import(fnmatch/List), 不留任何转发壳(禁 backward)。
2026-10-18 小欧 - 三堂会审整改: SHELL_WRITE_INTENT_RE 沙箱宽表补 CMD 搬移/复制动词(Rename-Item/move/ren/
  copy/xcopy/robocopy)。原表仅收 PS 别名, 致 CMD `move`/`ren`/`copy` 的目标在 F-B 越界写扫描中被漏扫。

"""
import os
import re

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
# 病根: 宽表把删与写混一张表, 命令含删动词时判"写", 于是删系统禁区只被判
# 「可授权的写」而非「不可授权的删」——授权后等于放行删系统目录。故拆细表三张。
# ★宽表必须保留删动词: 沙箱 F-B 越界写扫描正是靠它才看得到
#   Remove-Item/del/rm 的目标, 移出即漏扫 = 安全退化。
# 2026-10-18 小欧 - 三堂会审补全(原表漏 CMD 搬移/复制动词): 补 Rename-Item/move/ren 与 copy/xcopy/robocopy。
#   原表只收 PS 别名(Move-Item/mi/mv、Copy-Item/cpi/cp), 致 CMD `move`/`ren`/`copy` 三类:
#   ① 沙箱 F-B 越界写扫描漏扫其目标(覆盖面静默缩水) ② 通道 B 早退门漏判。取严补全。
SHELL_WRITE_INTENT_RE = re.compile(
    r"\b(?:Remove-Item|Remove-ItemProperty|rm|ri|del|erase|rd|rmdir|Move-Item|mi|Rename-Item|move|ren|mv"
    r"|Copy-Item|cpi|cp|copy|xcopy|robocopy|New-Item|ni|Set-Content|Add-Content|ac|Out-File|Expand-Archive"
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

# ★ 2026-10-18 小欧 [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入 shell_parse/):
#   删/写/搬移动词表(SHELL_DELETE_RE/SHELL_WRITE_RE/SHELL_MOVE_RE)、递归/强制删除判据
#   (SHELL_RECURSIVE_DELETE_RES/SHELL_FORCE_DELETE_RES/SHELL_DESTRUCTIVE_DELETE_RES/
#    shell_has_recursive_delete/shell_has_destructive_delete)、路径抽取
#   (shell_extract_abs_win_paths/_SHELL_ABS_WIN_PATH_RES) 整体移出本模块, 归 shell_parse 包
#   (parse_delete / parse_write / parse_move / lexer)。本模块只留沙箱宽表/只读白名单/规范化, 不留转发壳。


def shell_blank_out_quotes(text: str) -> str:
    """引号内容涂成等长空格(保偏移)。用于判动词时把 'Select-String -Pattern "del"' 里的 del 排除。"""
    return _QUOTED_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)


# ══════════════════════════════════════════════════════════════════════
# 四、工具分类
# ══════════════════════════════════════════════════════════════════════
def is_shell_tool(tool_name: str) -> bool:
    """是否 shell 命令类工具(executor 预检按此分流 file_op / shell) — 小欧 2026-10-10

    迁自 executor.py:70。调用期依赖 normalize_tool_name 已在文件头显式导入,
    杜绝「import 通过但调用 NameError」。
    """
    _shell = frozenset({"bash"})  # 2026-10-02 小欧 - 随注册名改名
    return normalize_tool_name(tool_name) in _shell


def shell_resolve_env_fragment(fragment: str) -> str:
    """$env:VAR 片段展开为真实路径(`$env:TEMP\\a.txt` → `C:\\Temp\\a.txt`)。未知变量原样保留。"""
    def _sub(m):
        val = os.environ.get(m.group(1))
        return val if val is not None else m.group(0)
    return re.sub(r"\$env:([A-Za-z_][A-Za-z0-9_]*)", _sub, fragment or "")


def shell_ps_literal_path(p) -> str:
    """给 PowerShell -LiteralPath 用单引号包裹并转义内嵌单引号(`'` → `''`)。"""
    return "'" + str(p).replace("'", "''") + "'"


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
