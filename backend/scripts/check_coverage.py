#!/usr/bin/env python
"""
测试覆盖检查工具 - 小沈

检查后端代码的测试覆盖情况，找出没有测试的功能。

使用方法：
python scripts/check_coverage.py
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Set

# 设置编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_all_modules(base_dir: Path) -> List[Path]:
    """获取所有Python模块文件"""
    modules = []
    for root, dirs, files in os.walk(base_dir):
        # 跳过测试目录和__pycache__
        if 'tests' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                modules.append(Path(root) / file)
    return modules


def get_all_test_files(test_dir: Path) -> List[Path]:
    """获取所有测试文件"""
    tests = []
    for root, dirs, files in os.walk(test_dir):
        for file in files:
            if file.startswith('test_') and file.endswith('.py'):
                tests.append(Path(root) / file)
    return tests


def check_module_tested(module: Path, test_files: List[Path]) -> bool:
    """检查模块是否有对应的测试"""
    module_name = module.stem
    for test_file in test_files:
        if module_name in test_file.stem:
            return True
    return False


def check_function_tested(module: Path, test_files: List[Path]) -> Set[str]:
    """检查模块中的函数是否有测试"""
    tested_functions = set()
    
    # 读取模块内容，提取函数名
    with open(module, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 简单提取函数名（以def开头的行）
    for line in content.split('\n'):
        if line.strip().startswith('def ') or line.strip().startswith('async def '):
            func_name = line.split('(')[0].split()[-1]
            if not func_name.startswith('_'):  # 跳过私有函数
                # 检查测试文件中是否有这个函数的测试
                for test_file in test_files:
                    try:
                        with open(test_file, 'r', encoding='utf-8') as tf:
                            test_content = tf.read()
                            if func_name in test_content:
                                tested_functions.add(func_name)
                                break
                    except:
                        pass
    
    return tested_functions


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent
    app_dir = base_dir / 'app'
    test_dir = base_dir / 'tests'
    
    print("=" * 60)
    print("后端代码测试覆盖检查 - 小沈")
    print("=" * 60)
    
    # 获取所有模块和测试文件
    modules = get_all_modules(app_dir)
    test_files = get_all_test_files(test_dir)
    
    print(f"\n找到 {len(modules)} 个模块文件")
    print(f"找到 {len(test_files)} 个测试文件")
    
    # 检查每个模块
    print("\n" + "=" * 60)
    print("模块测试覆盖检查")
    print("=" * 60)
    
    tested_modules = []
    untested_modules = []
    
    for module in modules:
        if check_module_tested(module, test_files):
            tested_modules.append(module)
        else:
            untested_modules.append(module)
    
    print(f"\n已测试模块: {len(tested_modules)}")
    for module in tested_modules:
        print(f"  ✅ {module.relative_to(app_dir)}")
    
    print(f"\n未测试模块: {len(untested_modules)}")
    for module in untested_modules:
        print(f"  ❌ {module.relative_to(app_dir)}")
    
    # 检查函数测试覆盖
    print("\n" + "=" * 60)
    print("函数测试覆盖检查")
    print("=" * 60)
    
    total_functions = 0
    tested_functions = 0
    
    for module in modules:
        # 统计模块中的函数
        with open(module, 'r', encoding='utf-8') as f:
            content = f.read()
        
        functions = []
        for line in content.split('\n'):
            if line.strip().startswith('def ') or line.strip().startswith('async def '):
                func_name = line.split('(')[0].split()[-1]
                if not func_name.startswith('_'):
                    functions.append(func_name)
        
        if functions:
            total_functions += len(functions)
            tested = check_function_tested(module, test_files)
            tested_functions += len(tested)
            
            if len(tested) < len(functions):
                print(f"\n{module.relative_to(app_dir)}:")
                for func in functions:
                    if func in tested:
                        print(f"  ✅ {func}")
                    else:
                        print(f"  ❌ {func}")
    
    # 总结
    print("\n" + "=" * 60)
    print("测试覆盖总结")
    print("=" * 60)
    
    module_coverage = len(tested_modules) / len(modules) * 100 if modules else 0
    function_coverage = tested_functions / total_functions * 100 if total_functions else 0
    
    print(f"\n模块覆盖率: {module_coverage:.1f}% ({len(tested_modules)}/{len(modules)})")
    print(f"函数覆盖率: {function_coverage:.1f}% ({tested_functions}/{total_functions})")
    
    if untested_modules:
        print(f"\n⚠️  警告: {len(untested_modules)} 个模块没有测试")
    
    if function_coverage < 80:
        print(f"\n⚠️  警告: 函数覆盖率低于80%")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
