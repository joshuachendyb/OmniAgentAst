#!/usr/bin/env python3
"""测试copy_file工具"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_import():
    """测试导入"""
    print("=== 测试导入 ===")
    
    try:
        from app.services.tools.file.copy_file import copy_file_impl
        print("[OK] copy_file_impl导入成功")
    except Exception as e:
        print(f"[ERROR] copy_file_impl导入失败: {e}")
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
    print("\n=== 测试Schema ===")
    
    try:
        from app.services.tools.file.file_schema import CopyFileInput
        
        # 测试默认值
        input_data = CopyFileInput(
            source_path="C:/test/file.txt",
            destination_path="D:/backup/file.txt"
        )
        print(f"[OK] CopyFileInput创建成功")
        print(f"  - source_path: {input_data.source_path}")
        print(f"  - destination_path: {input_data.destination_path}")
        print(f"  - recursive: {input_data.recursive} (默认: False)")
        print(f"  - overwrite: {input_data.overwrite} (默认: False)")
        
        # 测试自定义值
        input_data2 = CopyFileInput(
            source_path="C:/test/folder",
            destination_path="D:/backup/folder",
            recursive=True,
            overwrite=True
        )
        print(f"[OK] CopyFileInput自定义值创建成功")
        print(f"  - recursive: {input_data2.recursive}")
        print(f"  - overwrite: {input_data2.overwrite}")
        
        return True
    except Exception as e:
        print(f"[ERROR] Schema测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_function_signature():
    """测试函数签名"""
    print("\n=== 测试函数签名 ===")
    
    try:
        from app.services.tools.file.copy_file import copy_file_impl
        import inspect
        
        sig = inspect.signature(copy_file_impl)
        params = list(sig.parameters.keys())
        
        print(f"[OK] copy_file_impl参数: {params}")
        
        # 检查必需参数
        required_params = [
            'source_path', 'destination_path', 'recursive', 'overwrite',
            'validate_path_func', 'safety_service', 'session_id',
            'record_operation_func', 'execute_with_safety_func',
            'to_unified_format_func', 'get_next_sequence_func'
        ]
        
        for param in required_params:
            if param in params:
                print(f"  [OK] {param}")
            else:
                print(f"  [ERROR] 缺少参数: {param}")
                return False
        
        return True
    except Exception as e:
        print(f"[ERROR] 函数签名测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始测试copy_file工具...\n")
    
    tests = [
        ("导入测试", test_import),
        ("Schema测试", test_schema),
        ("函数签名测试", test_function_signature),
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"[OK] {test_name} 通过\n")
            else:
                print(f"[ERROR] {test_name} 失败\n")
                all_passed = False
        except Exception as e:
            print(f"[ERROR] {test_name} 出错: {e}\n")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    if all_passed:
        print("[SUCCESS] 所有测试通过！")
        print("\ncopy_file工具已正确集成到系统中：")
        print("1. 独立文件: backend/app/services/tools/file/copy_file.py")
        print("2. Schema定义: backend/app/services/tools/file/file_schema.py")
        print("3. 工具注册: backend/app/services/tools/file/file_tools.py")
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())