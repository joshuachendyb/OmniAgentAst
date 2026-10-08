# -*- coding: utf-8 -*-
"""shell 只读白名单单源(纯函数), 沙箱闸与出池判定共用; 落 utils 因 tools 禁 import safety(架构边界)。
编辑历史: 2026-10-04 小欧 - 自 executor.py 迁入, 内容未改, 行内署名保留。
2026-10-05 小欧 - 安全修复: FAST_CHANNEL_FORBIDDEN 补 $ ( ) 反引号 < 四类子表达式/命令替换/输入重定向载体
  (北京老陈裁定; 原缺口致 `echo $(Start-Process calc)` 等既过白名单又过 F-B 扫描, 直通真机执行任意命令)。
2026-10-05 小欧 - 补 \n \r: 换行符同为语句分隔符, 此前未禁致白名单可被绕过。
2026-10-08 小欧 新增不可隔离动词判定(事故驱动): UNCONTAINABLE_VERBS 词表 + has_uncontainable_intent /
  extract_kill_target_pids / is_process_kill_protected 三函数。根因: 沙箱预检是在宿主真跑一遍命令, 而
  Job Object 非硬墙拦不住子进程杀别的进程 → 词表漏 Stop-Process 时预检即真跑, 当场杀掉后端自身(E2E P9-03 实录)。
  收录标准= 现有 SHELL_DANGEROUS_PATTERNS 只到 MEDIUM(弹窗后仍进预检)拦不住者; HIGH 级不重复收录(DRY)。— 小欧-2026-10-08"""
import re
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


# —— 不可隔离动词: 沙箱预检"真跑"时副作用必落宿主, 不得进预检 ————————————————————
# 2026-10-08 小欧 新增。收录标准= 副作用与 cwd 无关且现有词表只到 MEDIUM(弹窗后仍进预检)拦不住者;
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
# 2026-10-08 小欧 PID 目标提取三形态: Stop-Process -Id / taskkill /PID / kill [-9] PID; 按名与 pkill 返空集。
_PID_TARGET_RES = (
    re.compile(r"stop-process\s+(?:.*?\s)?-id\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"/pid\s+(\d+)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])kill\s+(?:-[\w]+\s+)*(\d+)", re.IGNORECASE),
)


def has_uncontainable_intent(command: str) -> bool:
    """命令是否含不可隔离动词(杀进程/停服务) — 小欧 2026-10-08

    适用: shell 沙箱预检前静态判定, 命中转 HITL 不得 run(预检在宿主真跑, 跑即防线自破)。
    排除: Stop-Computer/Format-Volume/shutdown 已是 HIGH 级, 安全检查阶段就 blocked, 收录即重复(DRY)。
    """
    return bool(_UNCONTAINABLE_RE.search(command or ""))


def extract_kill_target_pids(command: str) -> set:
    """命令显式指定的杀进程目标 PID 集合 — 小欧 2026-10-08

    覆盖 Stop-Process -Id a,b / taskkill /PID n / kill [-9] n; 按名与管线形态枚举不了, 返回空集。
    """
    pids = set()
    for rx in _PID_TARGET_RES:
        for m in rx.finditer(command or ""):
            pids.update(int(x) for x in re.split(r"[\s,]+", m.group(1)) if x.isdigit())
    return pids


def is_process_kill_protected(command: str, protected_pids: set) -> bool:
    """命令目标是否命中受保护 PID — 小欧 2026-10-08

    适用: 阻止杀宿主关键进程(后端自身/父进程/shell 池), 命中即 blocked。
    取值: protected_pids 由调用方注入(utils 禁 import tools, 组装归 safety 侧); 按名形态返 False。
    """
    if not protected_pids:
        return False
    return bool(extract_kill_target_pids(command) & set(protected_pids))


def is_readonly_whitelisted(command: str) -> bool:
    """4.1#4 只读白名单判定; 安全放行须先跑 _scan_command_danger_intent, 纯路由调用点不适用 — 小欧 2026-10-04"""
    lowered = command.strip().lower()
    if not lowered.startswith(READONLY_PREFIXES):                    # 3.2.1 与常量单源(消除双源双维护) — 小欧-2026-09-18
        return False
    return not any(op in command for op in FAST_CHANNEL_FORBIDDEN)
