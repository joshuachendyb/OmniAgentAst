# -*- coding: utf-8 -*-
"""shell 只读白名单单源(纯函数), 沙箱闸与出池判定共用; 落 utils 因 tools 禁 import safety(架构边界)。
编辑历史: 2026-10-04 小欧 - 自 executor.py 迁入, 内容未改, 行内署名保留。
2026-10-05 小欧 - 安全修复: FAST_CHANNEL_FORBIDDEN 补 $ ( ) 反引号 < 四类子表达式/命令替换/输入重定向载体
  (北京老陈裁定; 原缺口致 `echo $(Start-Process calc)` 等既过白名单又过 F-B 扫描, 直通真机执行任意命令)。"""
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
FAST_CHANNEL_FORBIDDEN = ("|", ";", "&", ">", ">>", "$", "(", ")", "`", "<")
    # 2026-10-05 小欧 安全修复(北京老陈裁定): 补 $ ( ) 反引号 < 四类载体——原缺口使
    #   `echo $(Start-Process calc)`/`echo $(net user hacker pass /add)`/`echo `whoami` 既过白名单
    #   (只查前缀)又过 F-B 扫描(词表仅含写动词+重定向), 最终直通真机无沙箱。
    #   误拒含括号的合法只读命令可接受(转沙箱预检仍能执行), 漏放是真机执行, 取严。 — 小欧 2026-10-05


def is_readonly_whitelisted(command: str) -> bool:
    """4.1#4 只读白名单判定; 安全放行须先跑 _scan_command_write_intent, 纯路由调用点不适用 — 小欧 2026-10-04"""
    lowered = command.strip().lower()
    if not lowered.startswith(READONLY_PREFIXES):                    # 3.2.1 与常量单源(消除双源双维护) — 小欧-2026-09-18
        return False
    return not any(op in command for op in FAST_CHANNEL_FORBIDDEN)
