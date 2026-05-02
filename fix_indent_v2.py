#!/usr/bin/env python3
"""
全面修复装饰器移除后的缩进问题
"""
import re

file_path = r"D:\OmniAgentAs-desk\backend\app\services\tools\file\file_tools.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 class FileTools: 的位置
in_class = False
fixed_count = 0

for i, line in enumerate(lines):
    if 'class FileTools:' in line:
        in_class = True
        class_indent = 0
        continue
    
    if in_class:
        # 检测是否是类方法（async def 或 def）
        # 在类中，方法应该有4个空格缩进
        if re.match(r'^        async def \w+\(', line):
            # 应该是 "    async def" (4个空格)
            lines[i] = line[4:]  # 移除多余的4个空格
            fixed_count += 1
            print(f"修复第 {i+1} 行: {lines[i].strip()[:50]}")
        elif re.match(r'^        def \w+\(', line):
            lines[i] = line[4:]
            fixed_count += 1
            print(f"修复第 {i+1} 行: {lines[i].strip()[:50]}")

print(f"\n总共修复了 {fixed_count} 行")

# 写回文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
