# -*- coding: utf-8 -*-
filepath = r'D:\OmniAgentAs-desk\backend\app\services\tools\file\file_register.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换1: 添加overwrite参数
content = content.replace(
    '- destination_path：目标文件路径，即文件移动后的新路径\n\n【重要】如果目标位置已存在同名文件',
    '- destination_path：目标文件路径，即文件移动后的新路径\n- overwrite：目标已存在时是否覆盖（可选），默认false\n\n【重要】如果目标位置已存在同名文件且overwrite为false'
)

# 替换2: 添加示例
content = content.replace(
    '- 移动文件：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf"}\n- 重命名文件',
    '- 移动文件：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf"}\n- 覆盖移动：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf", "overwrite": true}\n- 重命名文件'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
