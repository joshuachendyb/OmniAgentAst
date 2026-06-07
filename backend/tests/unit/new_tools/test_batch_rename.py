#!/usr/bin/env python3
"""
测试batch_rename工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、批量重命名、验证）
"""

import sys
import os
import tempfile
import shutil
import re
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.batch_rename import batch_rename_impl
        print("[OK] batch_rename_impl导入成功")
    except Exception as e:
        print(f"[ERROR] batch_rename_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import BatchRenameInput
        print("[OK] BatchRenameInput导入成功")
    except Exception as e:
        print(f"[ERROR] BatchRenameInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import BatchRenameInput
        
        # 测试默认值
        input1 = BatchRenameInput(
            directory="C:/test",
            pattern="*.txt",
            replacement="new_*.txt"
        )
        assert input1.directory == "C:/test"
        assert input1.pattern == "*.txt"
        assert input1.replacement == "new_*.txt"
        assert input1.recursive == False
        assert input1.preview == False
        assert input1.conflict_strategy == "skip"
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = BatchRenameInput(
            directory="C:/test",
            pattern="file_*.txt",
            replacement="new_*.txt",
            recursive=True,
            preview=True,
            conflict_strategy="overwrite"
        )
        assert input2.recursive == True
        assert input2.preview == True
        assert input2.conflict_strategy == "overwrite"
        print("[OK] 自定义值测试通过")
        
        # 测试无效冲突策略
        try:
            input3 = BatchRenameInput(
                directory="C:/test",
                pattern="*.txt",
                replacement="new_*.txt",
                conflict_strategy="invalid"
            )
            print("[ERROR] 无效冲突策略应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效冲突策略验证通过")
        
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
        from app.services.tools.file.batch_rename import batch_rename_impl
        import inspect
        
        sig = inspect.signature(batch_rename_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'directory', 'pattern', 'replacement', 'recursive', 'preview', 'conflict_strategy',
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
    temp_dir = tempfile.mkdtemp(prefix="test_batch_rename_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试文件
        test_files = [
            Path(temp_dir) / "file1.txt",
            Path(temp_dir) / "file2.txt",
            Path(temp_dir) / "file3.txt",
            Path(temp_dir) / "document.pdf",
            Path(temp_dir) / "image.jpg"
        ]
        
        for i, file_path in enumerate(test_files):
            file_path.write_text(f"Content of {file_path.name}", encoding='utf-8')
        
        print(f"[OK] 创建测试文件: {[f.name for f in test_files]}")
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: 预览模式重命名
        print("\n--- 测试1: 预览模式重命名 ---")
        async def preview_rename():
            return await tools.batch_rename(
                directory=str(temp_dir),
                pattern="file",  # 简单字符串替换：匹配"file"
                replacement="renamed",  # 替换为"renamed"
                preview=True
            )
        
        result1 = asyncio.run(preview_rename())
        if result1.get('status') == 'success':
            preview_data = result1.get('data', {})
            if preview_data.get('preview_mode'):
                print(f"[OK] 预览模式成功: {result1.get('summary')}")
                print(f"    总文件数: {preview_data.get('total_files')}")
                print(f"    重命名文件数: {preview_data.get('renamed_files')}")
                print(f"    跳过文件数: {preview_data.get('skipped_files')}")
                print(f"    失败文件数: {preview_data.get('failed_files')}")
            else:
                print(f"[ERROR] 预览模式应该返回预览数据: {result1}")
                return False
        else:
            print(f"[ERROR] 预览模式失败: {result1}")
            return False
        
        # 验证文件没有被实际重命名
        original_files = [f.name for f in test_files]
        current_files = [f.name for f in Path(temp_dir).iterdir() if f.is_file()]
        if set(original_files) == set(current_files):
            print("[OK] 预览模式没有实际重命名文件")
        else:
            print(f"[ERROR] 预览模式不应该重命名文件: {original_files} vs {current_files}")
            return False
        
        # 测试2: 实际重命名
        print("\n--- 测试2: 实际重命名 ---")
        async def actual_rename():
            return await tools.batch_rename(
                directory=str(temp_dir),
                pattern="file",  # 简单字符串替换：匹配"file"
                replacement="renamed",  # 替换为"renamed"
                preview=False,
                conflict_strategy="rename"  # 使用重命名策略避免冲突
            )
        
        result2 = asyncio.run(actual_rename())
        if result2.get('status') == 'success':
            rename_data = result2.get('data', {})
            if rename_data.get('renamed_files', 0) == 3:  # 应该重命名3个文件
                print(f"[OK] 实际重命名成功: {result2.get('summary')}")
                print(f"    重命名数量: {rename_data.get('renamed_files')}")
                print(f"    跳过数量: {rename_data.get('skipped_files')}")
                print(f"    失败数量: {rename_data.get('failed_files')}")
            else:
                print(f"[ERROR] 应该重命名3个文件: {rename_data}")
                return False
        else:
            print(f"[ERROR] 实际重命名失败: {result2}")
            return False
        
        # 验证文件被实际重命名（使用rename策略，文件会被重命名为renamed1.txt, renamed2.txt, renamed3.txt等）
        renamed_files = [f.name for f in Path(temp_dir).iterdir() if f.is_file()]
        # 检查是否有3个以renamed开头的.txt文件
        renamed_txt_files = [f for f in renamed_files if f.startswith('renamed') and f.endswith('.txt')]
        if len(renamed_txt_files) == 3:
            print(f"[OK] 文件已正确重命名: {renamed_txt_files}")
        else:
            print(f"[ERROR] 重命名后文件不匹配: 找到{len(renamed_txt_files)}个重命名文件，期望3个")
            print(f"    所有文件: {renamed_files}")
            return False
        
        # 测试3: 正则表达式重命名
        print("\n--- 测试3: 正则表达式重命名 ---")
        # 创建更多测试文件
        test_file4 = Path(temp_dir) / "test_001.txt"
        test_file5 = Path(temp_dir) / "test_002.txt"
        test_file4.write_text("Test file 001", encoding='utf-8')
        test_file5.write_text("Test file 002", encoding='utf-8')
        
        async def regex_rename():
            return await tools.batch_rename(
                directory=str(temp_dir),
                pattern=r"test_(\d+).txt",
                replacement=r"new_\1.txt",
                preview=False,
                conflict_strategy="skip"
            )
        
        result3 = asyncio.run(regex_rename())
        if result3.get('status') == 'success':
            regex_data = result3.get('data', {})
            if regex_data.get('renamed_files', 0) == 2:  # 应该重命名2个文件
                print(f"[OK] 正则表达式重命名成功: {result3.get('summary')}")
                print(f"    重命名数量: {regex_data.get('renamed_files')}")
            else:
                print(f"[ERROR] 应该重命名2个文件: {regex_data}")
                return False
        else:
            print(f"[ERROR] 正则表达式重命名失败: {result3}")
            return False
        
        # 验证正则表达式重命名
        final_files = [f.name for f in Path(temp_dir).iterdir() if f.is_file()]
        # 文件应该包括：renamed1.txt, renamed2.txt, renamed3.txt, document.pdf, image.jpg, new_001.txt, new_002.txt
        expected_final = ["renamed1.txt", "renamed2.txt", "renamed3.txt", 
                         "document.pdf", "image.jpg", "new_001.txt", "new_002.txt"]
        if set(final_files) == set(expected_final):
            print("[OK] 正则表达式重命名成功")
        else:
            print(f"[ERROR] 正则表达式重命名后文件不匹配: {final_files} vs {expected_final}")
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
    print("开始测试batch_rename工具")
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
        print("[SUCCESS] 所有测试通过！batch_rename工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())