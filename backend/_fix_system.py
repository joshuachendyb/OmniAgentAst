import sys
path = 'app/services/tools/system/system_register.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
lines[57] = '    "get_system_info": "获取系统完整信息，包括操作系统、CPU、内存、磁盘、网络接口等硬件和系统配置信息。适合查看系统配置、诊断系统问题",\n'
lines[58] = '    "net_connections": "获取网络连接列表，支持按类型（TCP/UDP）、状态（ESTABLISHED/LISTEN）、端口过滤，可获取关联进程信息，支持DNS解析控制。适合查看网络连接、排查端口占用",\n'
lines[59] = '    "event_log": "获取系统事件日志（Windows事件查看器/Linux syslog），支持按级别、来源、时间范围过滤。适合查看系统错误、诊断问题、审计日志",\n'
lines[60] = '    "list_processes": "列出系统所有进程，支持按filter_name/filter_pid过滤，可按CPU/内存占用排序。适合查看进程状态、找资源占用高的进程",\n'
lines[61] = '    "kill_process": "终止指定进程(pid必填)，支持优雅终止（SIGTERM）和强制终止（SIGKILL），支持超时设置(timeout)。需谨慎使用。适合结束卡死进程、释放资源",\n'
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('修复完成')
