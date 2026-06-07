#!/usr/bin/env python3
"""
测试copy_file工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、复制、验证）
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.copy_file import copy_file_impl
        print("[OK] copy_file_impl导入成功")
    except Exception as e:
        print(f"[ERROR] copy_file_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import CopyFileInput
        print("[OK] CopyFileInput导入成功")
    except Exception as e:
        print(f"[ERROR] CopyFileInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import CopyFileInput
        
        # 测试默认值
        input1 = CopyFileInput(
            source_path="C:/test/file.txt",
            destination_path="D:/backup/file.txt"
        )
        assert input1.source_path == "C:/test/file.txt"
        assert input1.destination_path == "D:/backup/file.txt"
        assert input1.recursive == False
        assert input1.overwrite == False
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = CopyFileInput(
            source_path="C:/test/folder",
            destination_path="D:/backup/folder",
            recursive=True,
            overwrite=True
        )
        assert input2.recursive == True
        assert input2.overwrite == True
        print("[OK] 自定义值测试通过")
        
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
        from app.services.tools.file.copy_file import copy_file_impl
        import inspect
        
        sig = inspect.signature(copy_file_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'source_path', 'destination_path', 'recursive', 'overwrite',
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
    temp_dir = tempfile.mkdtemp(prefix="test_copy_file_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试文件
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Hello, World!", encoding='utf-8')
        print(f"[OK] 创建测试文件: {test_file}")
        
        # 测试复制
        dest_file = Path(temp_dir) / "backup" / "test.txt"
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 执行复制
        async def do_copy():
            return await tools.copy_file(
                source_path=str(test_file),
                destination_path=str(dest_file),
                recursive=False,
                overwrite=False
            )
        
        result = asyncio.run(do_copy())
        
        # 验证结果
        if result.get('status') == 'success':
            print(f"[OK] 复制成功: {result}")
            
            # 验证文件是否存在
            if dest_file.exists():
                content = dest_file.read_text(encoding='utf-8')
                if content == "Hello, World!":
                    print(f"[OK] 文件内容正确: {content}")
                    return True
                else:
                    print(f"[ERROR] 文件内容不正确: {content}")
                    return False
            else:
                print(f"[ERROR] 目标文件不存在: {dest_file}")
                return False
        else:
            print(f"[ERROR] 复制失败: {result}")
            return False
            
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
    print("开始测试copy_file工具")
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
        print("[SUCCESS] 所有测试通过！copy_file工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())