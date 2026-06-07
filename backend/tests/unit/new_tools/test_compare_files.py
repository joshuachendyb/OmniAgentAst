#!/usr/bin/env python3
"""
测试compare_files工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、比较、验证）
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.compare_files import compare_files_impl
        print("[OK] compare_files_impl导入成功")
    except Exception as e:
        print(f"[ERROR] compare_files_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import CompareFilesInput
        print("[OK] CompareFilesInput导入成功")
    except Exception as e:
        print(f"[ERROR] CompareFilesInput导入失败: {e}")
        return False
    
    try:
        from app.services.tools.file.file_tools import FileTools
        print("[OK] FileTools导入成功")
    except Exception as e:
        print(f"[ERROR] FileTools导入失败: {e}")
        return False
    
    return True


def test_schema():
    """测试Schema"""
    print("\n=== 测试2: Schema测试 ===")
    
    try:
        from app.services.tools.file.file_schema import CompareFilesInput
        
        # 测试默认值
        input1 = CompareFilesInput(
            file_path1="C:/test/file1.txt",
            file_path2="C:/test/file2.txt"
        )
        assert input1.file_path1 == "C:/test/file1.txt"
        assert input1.file_path2 == "C:/test/file2.txt"
        assert input1.algorithm == "content"
        assert input1.chunk_size == 8192
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = CompareFilesInput(
            file_path1="C:/test/file1.txt",
            file_path2="C:/test/file2.txt",
            algorithm="size",
            chunk_size=16384
        )
        assert input2.algorithm == "size"
        assert input2.chunk_size == 16384
        print("[OK] 自定义值测试通过")
        
        # 测试无效比较算法
        try:
            input3 = CompareFilesInput(
                file_path1="C:/test/file1.txt",
                file_path2="C:/test/file2.txt",
                algorithm="invalid"
            )
            print("[ERROR] 无效比较算法应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效比较算法验证通过")
        
        return True
    except Exception as e:
        print(f"[ERROR] Schema测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_function_signature():
    """测试函数签名"""
    print("\n=== 测试3: 函数签名测试 ===")
    
    try:
        from app.services.tools.file.compare_files import compare_files_impl
        import inspect
        
        sig = inspect.signature(compare_files_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'file_path1', 'file_path2', 'algorithm', 'chunk_size',
            'validate_path_func', 'safety_service', 'session_id',
            'record_operation_func', 'execute_with_safety_func',
            'to_unified_format_func', 'get_next_sequence_func'
        ]
        
        for param in required_params:
            if param not in params:
                print(f"[ERROR] 缺少参数: {param}")
                return False
        
        print(f"[OK] 所有必需参数都存在: {len(required_params)}个")
        return True
    except Exception as e:
        print(f"[ERROR] 函数签名测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_actual_functionality():
    """测试实际功能"""
    print("\n=== 测试4: 实际功能测试 ===")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_compare_files_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试文件
        test_file1 = Path(temp_dir) / "file1.txt"
        test_file2 = Path(temp_dir) / "file2.txt"
        test_file3 = Path(temp_dir) / "file3.txt"
        
        # 文件1和文件2内容相同
        test_file1.write_text("Hello, World!", encoding='utf-8')
        test_file2.write_text("Hello, World!", encoding='utf-8')
        # 文件3内容不同
        test_file3.write_text("Hello, Python!", encoding='utf-8')
        
        print(f"[OK] 创建测试文件: {test_file1}, {test_file2}, {test_file3}")
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: 相同文件内容比较
        print("\n--- 测试1: 相同文件内容比较 ---")
        async def compare_same():
            return await tools.compare_files(
                file_path1=str(test_file1),
                file_path2=str(test_file2),
                algorithm="content"
            )
        
        result1 = asyncio.run(compare_same())
        if result1.get('status') == 'success':
            comparison_data = result1.get('data', {}).get('comparison', {})
            if comparison_data.get('identical'):
                print(f"[OK] 相同文件内容比较通过: {result1.get('summary')}")
                print(f"    文件大小匹配: {comparison_data.get('size_match')}")
                print(f"    修改时间匹配: {comparison_data.get('mtime_match')}")
                print(f"    内容相同: {comparison_data.get('content_match')}")
            else:
                print(f"[ERROR] 相同文件应该相等: {result1}")
                return False
        else:
            print(f"[ERROR] 相同文件比较失败: {result1}")
            return False
        
        # 测试2: 不同文件内容比较
        print("\n--- 测试2: 不同文件内容比较 ---")
        async def compare_different():
            return await tools.compare_files(
                file_path1=str(test_file1),
                file_path2=str(test_file3),
                algorithm="content"
            )
        
        result2 = asyncio.run(compare_different())
        if result2.get('status') == 'success':
            comparison_data = result2.get('data', {}).get('comparison', {})
            if not comparison_data.get('identical'):
                print(f"[OK] 不同文件内容比较通过: {result2.get('summary')}")
                print(f"    文件大小匹配: {comparison_data.get('size_match')}")
                print(f"    修改时间匹配: {comparison_data.get('mtime_match')}")
                print(f"    内容相同: {comparison_data.get('content_match')}")
            else:
                print(f"[ERROR] 不同文件应该不相等: {result2}")
                return False
        else:
            print(f"[ERROR] 不同文件比较失败: {result2}")
            return False
        
        # 测试3: 文件大小比较
        print("\n--- 测试3: 文件大小比较 ---")
        async def compare_size():
            return await tools.compare_files(
                file_path1=str(test_file1),
                file_path2=str(test_file2),
                algorithm="size"
            )
        
        result3 = asyncio.run(compare_size())
        if result3.get('status') == 'success':
            comparison_data = result3.get('data', {}).get('comparison', {})
            if comparison_data.get('size_match'):
                print(f"[OK] 文件大小比较通过: {result3.get('summary')}")
                print(f"    文件大小匹配: {comparison_data.get('size_match')}")
                print(f"    修改时间匹配: {comparison_data.get('mtime_match')}")
                print(f"    内容相同: {comparison_data.get('content_match')}")
            else:
                print(f"[ERROR] 相同大小文件应该相等: {result3}")
                return False
        else:
            print(f"[ERROR] 文件大小比较失败: {result3}")
            return False
        
        # 测试4: 修改时间比较
        print("\n--- 测试4: 修改时间比较 ---")
        async def compare_mtime():
            return await tools.compare_files(
                file_path1=str(test_file1),
                file_path2=str(test_file2),
                algorithm="mtime"
            )
        
        result4 = asyncio.run(compare_mtime())
        if result4.get('status') == 'success':
            print(f"[OK] 修改时间比较通过: {result4.get('data', {}).get('message')}")
        else:
            print(f"[ERROR] 修改时间比较失败: {result4}")
            return False
        
        return True
            
    except Exception as e:
        print(f"[ERROR] 功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
            print(f"[OK] 清理临时目录: {temp_dir}")
        except:
            pass


def main():
    """主测试函数"""
    print("=" * 60)
    print("开始测试compare_files工具")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_import),
        ("Schema测试", test_schema),
        ("函数签名测试", test_function_signature),
        ("实际功能测试", test_actual_functionality),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"\n[OK] {test_name} 通过")
            else:
                print(f"\n[ERROR] {test_name} 失败")
                all_passed = False
        except Exception as e:
            print(f"\n[ERROR] {test_name} 出错: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] 所有测试通过！compare_files工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())