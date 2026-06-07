#!/usr/bin/env python3
"""
测试compress_files工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、压缩、验证）
"""

import sys
import os
import tempfile
import shutil
import zipfile
import tarfile
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.compress_files import compress_files_impl
        print("[OK] compress_files_impl导入成功")
    except Exception as e:
        print(f"[ERROR] compress_files_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import CompressFilesInput
        print("[OK] CompressFilesInput导入成功")
    except Exception as e:
        print(f"[ERROR] CompressFilesInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import CompressFilesInput
        
        # 测试默认值
        input1 = CompressFilesInput(
            source_path="C:/test",
            destination_path="C:/test.zip"
        )
        assert input1.source_path == "C:/test"
        assert input1.destination_path == "C:/test.zip"
        assert input1.format == "zip"
        assert input1.compression_level == 6
        assert input1.password is None
        assert input1.split_size is None
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = CompressFilesInput(
            source_path="C:/test",
            destination_path="C:/test.tar.gz",
            format="tar.gz",
            compression_level=9,
            password="secret123",
            split_size=1024*1024  # 1MB
        )
        assert input2.format == "tar.gz"
        assert input2.compression_level == 9
        assert input2.password == "secret123"
        assert input2.split_size == 1024*1024
        print("[OK] 自定义值测试通过")
        
        # 测试无效压缩格式
        try:
            input3 = CompressFilesInput(
                source_path="C:/test",
                destination_path="C:/test.rar",
                format="rar"
            )
            print("[ERROR] 无效压缩格式应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效压缩格式验证通过")
        
        # 测试无效压缩级别
        try:
            input4 = CompressFilesInput(
                source_path="C:/test",
                destination_path="C:/test.zip",
                compression_level=10
            )
            print("[ERROR] 无效压缩级别应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效压缩级别验证通过")
        
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
        from app.services.tools.file.compress_files import compress_files_impl
        import inspect
        
        sig = inspect.signature(compress_files_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'source_path', 'destination_path', 'format', 'compression_level', 'password', 'split_size',
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
    temp_dir = tempfile.mkdtemp(prefix="test_compress_files_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试文件和目录结构
        test_dir = Path(temp_dir) / "test_data"
        test_dir.mkdir()
        
        # 创建测试文件
        test_files = [
            test_dir / "file1.txt",
            test_dir / "file2.txt",
            test_dir / "subdir" / "file3.txt",
            test_dir / "subdir" / "nested" / "file4.txt"
        ]
        
        # 创建目录结构
        (test_dir / "subdir" / "nested").mkdir(parents=True)
        
        # 写入文件内容
        for i, file_path in enumerate(test_files):
            file_path.write_text(f"Content of file {i+1}", encoding='utf-8')
        
        print(f"[OK] 创建测试目录结构: {test_dir}")
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: ZIP压缩
        print("\n--- 测试1: ZIP压缩 ---")
        zip_output = Path(temp_dir) / "test.zip"
        
        async def compress_zip():
            return await tools.compress_files(
                source_path=str(test_dir),
                destination_path=str(zip_output),
                format="zip",
                compression_level=6
            )
        
        result1 = asyncio.run(compress_zip())
        if result1.get('status') == 'success':
            zip_data = result1.get('data', {})
            if zip_data.get('compressed_size', 0) > 0:
                print(f"[OK] ZIP压缩成功: {zip_data.get('message')}")
                print(f"    压缩文件: {zip_data.get('destination_path')}")
                print(f"    压缩大小: {zip_data.get('compressed_size')} 字节")
                print(f"    原始大小: {zip_data.get('original_size')} 字节")
                print(f"    压缩率: {zip_data.get('compression_ratio', 0):.2f}%")
            else:
                print(f"[ERROR] ZIP压缩应该返回压缩大小: {zip_data}")
                return False
        else:
            print(f"[ERROR] ZIP压缩失败: {result1}")
            return False
        
        # 验证ZIP文件
        if zip_output.exists():
            print("[OK] ZIP文件已创建")
            # 检查ZIP文件内容
            try:
                with zipfile.ZipFile(zip_output, 'r') as zipf:
                    file_list = zipf.namelist()
                    print(f"[OK] ZIP文件包含 {len(file_list)} 个文件")
                    for file in file_list:
                        print(f"    - {file}")
            except Exception as e:
                print(f"[ERROR] 无法读取ZIP文件: {e}")
                return False
        else:
            print(f"[ERROR] ZIP文件未创建: {zip_output}")
            return False
        
        # 测试2: TAR.GZ压缩
        print("\n--- 测试2: TAR.GZ压缩 ---")
        tar_output = Path(temp_dir) / "test.tar.gz"
        
        async def compress_tar_gz():
            return await tools.compress_files(
                source_path=str(test_dir),
                destination_path=str(tar_output),
                format="tar.gz",
                compression_level=9
            )
        
        result2 = asyncio.run(compress_tar_gz())
        if result2.get('status') == 'success':
            tar_data = result2.get('data', {})
            if tar_data.get('compressed_size', 0) > 0:
                print(f"[OK] TAR.GZ压缩成功: {tar_data.get('message')}")
                print(f"    压缩文件: {tar_data.get('destination_path')}")
                print(f"    压缩大小: {tar_data.get('compressed_size')} 字节")
            else:
                print(f"[ERROR] TAR.GZ压缩应该返回压缩大小: {tar_data}")
                return False
        else:
            print(f"[ERROR] TAR.GZ压缩失败: {result2}")
            return False
        
        # 验证TAR.GZ文件
        if tar_output.exists():
            print("[OK] TAR.GZ文件已创建")
            # 检查TAR.GZ文件内容
            try:
                with tarfile.open(tar_output, 'r:gz') as tarf:
                    file_list = tarf.getnames()
                    print(f"[OK] TAR.GZ文件包含 {len(file_list)} 个文件")
                    for file in file_list[:5]:  # 只显示前5个文件
                        print(f"    - {file}")
            except Exception as e:
                print(f"[ERROR] 无法读取TAR.GZ文件: {e}")
                return False
        else:
            print(f"[ERROR] TAR.GZ文件未创建: {tar_output}")
            return False
        
        # 测试3: 单个文件压缩
        print("\n--- 测试3: 单个文件压缩 ---")
        single_file = test_dir / "file1.txt"
        single_zip = Path(temp_dir) / "single.zip"
        
        async def compress_single():
            return await tools.compress_files(
                source_path=str(single_file),
                destination_path=str(single_zip),
                format="zip"
            )
        
        result3 = asyncio.run(compress_single())
        if result3.get('status') == 'success':
            single_data = result3.get('data', {})
            if single_data.get('compressed_size', 0) > 0:
                print(f"[OK] 单个文件压缩成功: {single_data.get('message')}")
                print(f"    压缩文件: {single_data.get('destination_path')}")
            else:
                print(f"[ERROR] 单个文件压缩应该返回压缩大小: {single_data}")
                return False
        else:
            print(f"[ERROR] 单个文件压缩失败: {result3}")
            return False
        
        # 验证单个文件压缩
        if single_zip.exists():
            print("[OK] 单个文件ZIP已创建")
        else:
            print(f"[ERROR] 单个文件ZIP未创建: {single_zip}")
            return False
        
        # 测试4: 带密码的ZIP压缩
        print("\n--- 测试4: 带密码的ZIP压缩 ---")
        password_zip = Path(temp_dir) / "password.zip"
        
        async def compress_with_password():
            return await tools.compress_files(
                source_path=str(test_dir),
                destination_path=str(password_zip),
                format="zip",
                password="testpassword123"
            )
        
        result4 = asyncio.run(compress_with_password())
        if result4.get('status') == 'success':
            password_data = result4.get('data', {})
            if password_data.get('compressed_size', 0) > 0:
                print(f"[OK] 带密码ZIP压缩成功: {password_data.get('message')}")
                print(f"    压缩文件: {password_data.get('destination_path')}")
            else:
                print(f"[ERROR] 带密码ZIP压缩应该返回压缩大小: {password_data}")
                return False
        else:
            print(f"[ERROR] 带密码ZIP压缩失败: {result4}")
            return False
        
        # 验证带密码的ZIP文件
        if password_zip.exists():
            print("[OK] 带密码ZIP文件已创建")
        else:
            print(f"[ERROR] 带密码ZIP文件未创建: {password_zip}")
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
    print("开始测试compress_files工具")
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
        print("[SUCCESS] 所有测试通过！compress_files工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())