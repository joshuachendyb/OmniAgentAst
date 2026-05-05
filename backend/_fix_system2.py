path = 'app/services/tools/system/system_register.py'
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
lines[64] = '    "service_list": "列出系统服务（Windows用sc/Linux用systemctl），支持按名称和状态（running/stopped）过滤，支持输出格式选择。适合查看服务状态、管理服务",\n'
lines[65] = '    "service_start": "启动指定系统服务（Windows用sc/Linux用systemctl），支持超时设置。适合启动停止的服务",\n'
with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('修复完成')
