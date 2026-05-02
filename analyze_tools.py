#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计Omni系统所有工具数量 - 小健 2026-05-03
"""
import os
import re
from pathlib import Path

def count_tools_in_register(file_path: Path) -> int:
    """统计一个register文件中的工具数量"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计 register_tool 调用
        register_calls = len(re.findall(r'register_tool\(', content))
        
        # 统计 tool_methods 字典中的条目
        tool_methods_pattern = r'tool_methods\s*=\s*\{([^}]+)\}'
        methods_match = re.search(tool_methods_pattern, content, re.DOTALL)
        if methods_match:
            methods_text = methods_match.group(1)
            method_count = len(re.findall(r'\w+":\s*lambda', methods_text))
            print(f"  - {file_path.name}: register_tool={register_calls}, tool_methods={method_count}")
            return max(register_calls, method_count)
        else:
            print(f"  - {file_path.name}: register_tool={register_calls}")
            return register_calls
    except Exception as e:
        print(f"  错误读取 {file_path}: {e}")
        return 0

def main():
    project_root = Path("D:/OmniAgentAs-desk")
    tools_dir = project_root / "backend" / "app" / "services" / "tools"
    
    if not tools_dir.exists():
        print(f"目录不存在: {tools_dir}")
        return
    
    tool_counts = {}
    total_tools = 0
    
    print("=== 分析工具注册文件 ===")
    
    # 查找所有注册文件
    register_files = list(tools_dir.glob("**/*_register.py"))
    
    for reg_file in sorted(register_files):
        category = reg_file.parent.name
        tool_count = count_tools_in_register(reg_file)
        tool_counts[category] = tool_count
        total_tools += tool_count
    
    print("\n=== 工具分类统计 ===")
    for category, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{category.upper():<15} {count:>3} 个工具")
    
    print(f"\n=== 总计 ===\n{total_tools} 个工具")
    
    # 统计测试文件
    test_dir = project_root / "backend" / "tests"
    test_files = list(test_dir.glob("**/*.py"))
    
    print(f"\n=== 测试文件统计 ===")
    print(f"测试文件总数: {len(test_files)}")
    
    # 检查测试覆盖率
    test_tool_coverage = {}
    for category in tool_counts.keys():
        test_patterns = [
            test_dir / f"test_{category}_tools.py",
            test_dir / category / f"test_{category}_tools.py",
            test_dir / f"test_{category}_*.py"
        ]
        
        found_tests = []
        for pattern in test_patterns:
            if pattern.is_file():
                found_tests.append(str(pattern.relative_to(project_root)))
        
        if found_tests:
            test_tool_coverage[category] = True
        else:
            test_tool_coverage[category] = False
    
    print(f"\n=== 测试覆盖情况 ===")
    covered = sum(1 for covered in test_tool_coverage.values() if covered)
    total_categories = len(test_tool_coverage)
    print(f"工具类别总数: {total_categories}")
    print(f"有测试的类别: {covered}")
    print(f"测试覆盖率: {covered/total_categories*100:.1f}%")
    
    print(f"\n=== 无测试覆盖的类别 ===")
    for category, covered in test_tool_coverage.items():
        if not covered:
            print(f"  - {category}")
    
    return tool_counts

if __name__ == "__main__":
    tool_counts = main()