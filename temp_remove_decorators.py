#!/usr/bin/env python3
"""
临时脚本：移除 file_tools.py 中的所有 @register_tool 装饰器
"""
import re

file_path = r"D:\OmniAgentAs-desk\backend\app\services\tools\file\file_tools.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 转换为字符串处理
content = ''.join(lines)

# 1. 移除空装饰器定义 (第165-175行)
# 找到空装饰器定义并移除
empty_decorator_pattern = r'# 空装饰器（已废弃.*?\ndef register_tool\([^)]+\):\s*\n\s*"""[^"]+"""\s*\n\s*def decorator\(func\):\s*\n\s*return func\s*\n\s*return decorator\s*\n'
content = re.sub(empty_decorator_pattern, '', content, flags=re.DOTALL)

# 2. 移除所有 @register_tool(...) 装饰器
# 找到 @register_tool( 开始，匹配到对应的 ) 结束
def remove_register_tool_decorator(content):
    """移除所有 @register_tool 装饰器"""
    result = []
    i = 0
    removed_count = 0
    
    while i < len(content):
        # 查找 @register_tool(
        if content[i:].startswith('@register_tool('):
            # 找到装饰器的开始
            start = i
            i += len('@register_tool(')
            
            # 使用括号匹配找到结束位置
            paren_count = 1
            while i < len(content) and paren_count > 0:
                if content[i] == '(':
                    paren_count += 1
                elif content[i] == ')':
                    paren_count -= 1
                i += 1
            
            # 跳过装饰器后的空白行
            while i < len(content) and content[i] in ' \t':
                i += 1
            # 跳过一个换行符
            if i < len(content) and content[i] == '\n':
                i += 1
            
            removed_count += 1
            print(f"移除装饰器 #{removed_count}: 行 ~{content[:start].count(chr(10))+1}")
        else:
            result.append(content[i])
            i += 1
    
    print(f"\n总共移除了 {removed_count} 个装饰器")
    return ''.join(result)

content = remove_register_tool_decorator(content)

# 3. 检查是否还需要 BaseModel 导入
# 检查是否还有其他地方使用 BaseModel（除了装饰器定义）
has_basemodel_usage = 'BaseModel' in content and ('from pydantic import BaseModel' in content or ': BaseModel' in content or '[BaseModel]' in content)
print(f"\nBaseModel 使用情况: {'仍在使用' if has_basemodel_usage else '未使用'}")

# 写回文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n文件已更新: {file_path}")
