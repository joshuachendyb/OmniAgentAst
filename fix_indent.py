#!/usr/bin/env python3
"""
修复装饰器移除后的缩进问题
"""
import re

file_path = r"D:\OmniAgentAs-desk\backend\app\services\tools\file\file_tools.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复模式：在类方法中，async def 前面应该有4个空格缩进
# 匹配: "\n        async def xxx(\n        self," -> "\n    async def xxx(\n        self,"
pattern = r'\n        async def (\w+)\(\n        self,'
replacement = r'\n    async def \1(\n        self,'
content = re.sub(pattern, replacement, content)

# 写回文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("缩进修复完成")
