# -*- coding: utf-8 -*-
filepath = r'D:\OmniAgentAs-desk\backend\app\services\tools\file\file_register.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''"move_file": """移动或重命名文件。

使用场景：
- 当用户需要将文件移动到另一个目录时使用
- 当用户想要重命名文件时使用
- 当用户需要整理文件结构时使用

参数说明：
- source_path：源文件路径，即要移动的文件当前路径
- destination_path：目标文件路径，即文件移动后的新路径

【重要】如果目标位置已存在同名文件，操作会失败

使用示例：
- 移动文件：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf"}
- 重命名文件：{"source_path": "D:/documents/old_name.txt", "destination_path": "D:/documents/new_name.txt"}"""'''

new = '''"move_file": """移动或重命名文件。

使用场景：
- 当用户需要将文件移动到另一个目录时使用
- 当用户想要重命名文件时使用
- 当用户需要整理文件结构时使用

参数说明：
- source_path：源文件路径，即要移动的文件当前路径
- destination_path：目标文件路径，即文件移动后的新路径
- overwrite：目标已存在时是否覆盖（可选），默认false

【重要】如果目标位置已存在同名文件且overwrite为false，操作会失败

使用示例：
- 移动文件：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf"}
- 覆盖移动：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf", "overwrite": true}
- 重命名文件：{"source_path": "D:/documents/old_name.txt", "destination_path": "D:/documents/new_name.txt"}"""'''

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Updated successfully')
else:
    print('Not found')
