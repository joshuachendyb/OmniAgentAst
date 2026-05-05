# -*- coding: utf-8 -*-
"""List all registered tools"""
import sys
sys.path.insert(0, '.')

# Import to trigger registration
import app.services.tools.file.file_tools
import app.tools.time_tools

from app.services.tools.file.file_tools import get_registered_tools as get_file_tools
from app.tools.time_tools import get_registered_tools as get_time_tools

file_tools = get_file_tools()
time_tools = get_time_tools()

print("=" * 60)
print("文档第6章定义的Tool vs 实际已实现的Tool")
print("=" * 60)

print("\n【1类：文件操作（工具1-19）】")
print("文档定义19个，实际已注册: {}个".format(len(file_tools)))
print("已注册工具列表:")
for t in file_tools:
    print(f"  - {t['name']}")

print("\n【5类：时间/日期（工具26-27）】")
print("文档定义2个(26-get_current_time, 27-calculate_date)")
print("实际注册了9个:")
for t in time_tools:
    print(f"  - {t['name']}")

print("\n" + "=" * 60)
print(f"总计：文档定义46个LLM Tool，已实现 {len(file_tools) + len(time_tools)} 个")
print("=" * 60)