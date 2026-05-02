#!/usr/bin/env python3
"""
修复 read_batch_file 内部函数的缩进
"""
file_path = r"D:\OmniAgentAs-desk\backend\app\services\tools\file\file_tools.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到第1757行并修复缩进
# _read_single 应该是 read_batch_file 的内部函数，需要8个空格
fixed_lines = []
for i, line in enumerate(lines):
    line_num = i + 1
    # 修复 1757-1786 行的缩进（_read_single 函数体）
    if 1757 <= line_num <= 1786:
        # 检查当前行的缩进
        if line.startswith('    async def _read_single'):
            # 应该是8个空格
            fixed_lines.append('        ' + line[4:])
        elif line.startswith('        ') and not line.startswith('            '):
            # 已经有8个空格的行，需要再加4个空格（变为12个）
            fixed_lines.append('    ' + line)
        elif line.strip() == '':
            fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# 写回文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("缩进修复完成")
