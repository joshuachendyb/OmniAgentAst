#!/usr/bin/env python3
"""
运行所有新文件工具的单元测试

这个脚本会依次运行所有新文件工具的测试，并汇总结果。
"""

import sys
import os
import subprocess
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 测试文件列表
TEST_FILES = [
    "test_compare_files.py",
    "test_batch_rename.py",
    "test_compress_files.py",
    "test_file_monitor.py",
    "test_file_statistics.py",
    "test_file_checksum.py"
]

def run_test(test_file):
    """运行单个测试文件"""
    print(f"\n{'='*80}")
    print(f"运行测试: {test_file}")
    print(f"{'='*80}")
    
    test_path = os.path.join(os.path.dirname(__file__), test_file)
    
    # 检查文件是否存在
    if not os.path.exists(test_path):
        print(f"[ERROR] 测试文件不存在: {test_path}")
        return False
    
    try:
        # 运行测试
        start_time = time.time()
        result = subprocess.run([sys.executable, test_path], 
                              capture_output=True, 
                              text=True,
                              cwd=os.path.dirname(__file__))
        end_time = time.time()
        
        # 输出测试结果
        print(result.stdout)
        if result.stderr:
            print(f"[STDERR] {result.stderr}")
        
        elapsed_time = end_time - start_time
        print(f"测试用时: {elapsed_time:.2f} 秒")
        
        if result.returncode == 0:
            print(f"[SUCCESS] {test_file} 测试通过")
            return True
        else:
            print(f"[FAILED] {test_file} 测试失败 (返回码: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"[ERROR] 运行测试时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 80)
    print("开始运行所有新文件工具的单元测试")
    print("=" * 80)
    
    # 检查测试文件是否存在
    missing_tests = []
    for test_file in TEST_FILES:
        test_path = os.path.join(os.path.dirname(__file__), test_file)
        if not os.path.exists(test_path):
            missing_tests.append(test_file)
    
    if missing_tests:
        print(f"[WARNING] 以下测试文件不存在: {missing_tests}")
        print("请先创建这些测试文件。")
        return 1
    
    # 运行所有测试
    results = {}
    total_passed = 0
    total_failed = 0
    
    for test_file in TEST_FILES:
        passed = run_test(test_file)
        results[test_file] = passed
        if passed:
            total_passed += 1
        else:
            total_failed += 1
    
    # 输出汇总结果
    print(f"\n{'='*80}")
    print("测试结果汇总")
    print(f"{'='*80}")
    
    for test_file, passed in results.items():
        status = "通过" if passed else "失败"
        print(f"{test_file:30} : {status}")
    
    print(f"\n总计: {len(TEST_FILES)} 个测试")
    print(f"通过: {total_passed}")
    print(f"失败: {total_failed}")
    
    if total_failed == 0:
        print(f"\n{'='*80}")
        print("[SUCCESS] 所有测试通过！所有新文件工具工作正常")
        print(f"{'='*80}")
        return 0
    else:
        print(f"\n{'='*80}")
        print(f"[FAILED] {total_failed} 个测试失败，请检查上述问题")
        print(f"{'='*80}")
        return 1

if __name__ == "__main__":
    sys.exit(main())