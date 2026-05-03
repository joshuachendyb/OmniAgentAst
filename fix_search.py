# -*- coding: utf-8 -*-
filepath = r'D:\OmniAgentAs-desk\backend\app\services\tools\file\file_register.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 添加page_token参数到search_files
old = '''- sortBy：排序方式，可选name/size/mtime

【重要】递归搜索所有子目录，返回所有匹配的文件完整路径

使用示例：
- 搜索所有 Python 文件：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.py"}
- 搜索并排除 node_modules：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.js", "excludePatterns": ["node_modules"]}'''

new = '''- sortBy：排序方式，可选name/size/mtime
- page_token：分页令牌（可选），用于获取后续结果

【重要】递归搜索所有子目录，返回所有匹配的文件完整路径

使用示例：
- 搜索所有 Python 文件：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.py"}
- 搜索并排除 node_modules：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.js", "excludePatterns": ["node_modules"]}'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated successfully')
else:
    print('Not found')
