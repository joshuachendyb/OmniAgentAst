#!/usr/bin/env python3
"""
测试file_checksum工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、计算哈希、验证）
"""

import sys
import os
import tempfile
import shutil
import hashlib
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.file_checksum import file_checksum_impl
        print("[OK] file_checksum_impl导入成功")
    except Exception as e:
        print(f"[ERROR] file_checksum_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import FileChecksumInput
        print("[OK] FileChecksumInput导入成功")
    except Exception as e:
        print(f"[ERROR] FileChecksumInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import FileChecksumInput
        
        # 测试默认值
        input1 = FileChecksumInput(
            file_path="C:/test/file.txt"
        )
        assert input1.file_path == "C:/test/file.txt"
        assert input1.algorithm == "md5"
        assert input1.verify_hash is None
        assert input1.chunk_size == 65536
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = FileChecksumInput(
            file_path="C:/test/file.txt",
            algorithm="sha256",
            verify_hash="abc123",
            chunk_size=32768
        )
        assert input2.algorithm == "sha256"
        assert input2.verify_hash == "abc123"
        assert input2.chunk_size == 32768
        print("[OK] 自定义值测试通过")
        
        # 测试无效哈希算法
        try:
            input3 = FileChecksumInput(
                file_path="C:/test/file.txt",
                algorithm="invalid"
            )
            print("[ERROR] 无效哈希算法应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效哈希算法验证通过")
        
        # 测试无效分块大小
        try:
            input4 = FileChecksumInput(
                file_path="C:/test/file.txt",
                chunk_size=500  # 太小
            )
            print("[ERROR] 无效分块大小应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效分块大小验证通过")
        
        try:
            input5 = FileChecksumInput(
                file_path="C:/test/file.txt",
                chunk_size=2000000  # 太大
            )
            print("[ERROR] 无效分块大小应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效分块大小验证通过")
        
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
        from app.services.tools.file.file_checksum import file_checksum_impl
        import inspect
        
        sig = inspect.signature(file_checksum_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'file_path', 'algorithm', 'verify_hash', 'chunk_size',
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
    temp_dir = tempfile.mkdtemp(prefix="test_file_checksum_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试文件
        test_file = Path(temp_dir) / "test.txt"
        test_content = "Hello, World! This is a test file for checksum calculation."
        test_file.write_text(test_content, encoding='utf-8')
        
        print(f"[OK] 创建测试文件: {test_file}")
        print(f"    文件大小: {test_file.stat().st_size} 字节")
        
        # 计算预期的哈希值
        content_bytes = test_content.encode('utf-8')
        expected_md5 = hashlib.md5(content_bytes).hexdigest()
        expected_sha1 = hashlib.sha1(content_bytes).hexdigest()
        expected_sha256 = hashlib.sha256(content_bytes).hexdigest()
        expected_sha512 = hashlib.sha512(content_bytes).hexdigest()
        
        print(f"    预期MD5: {expected_md5}")
        print(f"    预期SHA1: {expected_sha1}")
        print(f"    预期SHA256: {expected_sha256}")
        print(f"    预期SHA512: {expected_sha512}")
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: MD5哈希计算
        print("\n--- 测试1: MD5哈希计算 ---")
        async def calculate_md5():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="md5"
            )
        
        result1 = asyncio.run(calculate_md5())
        if result1.get('status') == 'success':
            checksum_data = result1.get('data', {})
            actual_md5 = checksum_data.get('checksum', '')
            
            if actual_md5 == expected_md5:
                print(f"[OK] MD5哈希计算成功: {checksum_data.get('message')}")
                print(f"    计算MD5: {actual_md5}")
                print(f"    文件大小: {checksum_data.get('file_size')} 字节")
                print(f"    耗时: {checksum_data.get('elapsed_time', 0):.4f} 秒")
            else:
                print(f"[ERROR] MD5哈希不匹配: {actual_md5} vs {expected_md5}")
                return False
        else:
            print(f"[ERROR] MD5哈希计算失败: {result1}")
            return False
        
        # 测试2: SHA1哈希计算
        print("\n--- 测试2: SHA1哈希计算 ---")
        async def calculate_sha1():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="sha1"
            )
        
        result2 = asyncio.run(calculate_sha1())
        if result2.get('status') == 'success':
            checksum_data2 = result2.get('data', {})
            actual_sha1 = checksum_data2.get('checksum', '')
            
            if actual_sha1 == expected_sha1:
                print(f"[OK] SHA1哈希计算成功: {checksum_data2.get('message')}")
                print(f"    计算SHA1: {actual_sha1}")
            else:
                print(f"[ERROR] SHA1哈希不匹配: {actual_sha1} vs {expected_sha1}")
                return False
        else:
            print(f"[ERROR] SHA1哈希计算失败: {result2}")
            return False
        
        # 测试3: SHA256哈希计算
        print("\n--- 测试3: SHA256哈希计算 ---")
        async def calculate_sha256():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="sha256"
            )
        
        result3 = asyncio.run(calculate_sha256())
        if result3.get('status') == 'success':
            checksum_data3 = result3.get('data', {})
            actual_sha256 = checksum_data3.get('checksum', '')
            
            if actual_sha256 == expected_sha256:
                print(f"[OK] SHA256哈希计算成功: {checksum_data3.get('message')}")
                print(f"    计算SHA256: {actual_sha256}")
            else:
                print(f"[ERROR] SHA256哈希不匹配: {actual_sha256} vs {expected_sha256}")
                return False
        else:
            print(f"[ERROR] SHA256哈希计算失败: {result3}")
            return False
        
        # 测试4: SHA512哈希计算
        print("\n--- 测试4: SHA512哈希计算 ---")
        async def calculate_sha512():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="sha512"
            )
        
        result4 = asyncio.run(calculate_sha512())
        if result4.get('status') == 'success':
            checksum_data4 = result4.get('data', {})
            actual_sha512 = checksum_data4.get('checksum', '')
            
            if actual_sha512 == expected_sha512:
                print(f"[OK] SHA512哈希计算成功: {checksum_data4.get('message')}")
                print(f"    计算SHA512: {actual_sha512}")
            else:
                print(f"[ERROR] SHA512哈希不匹配: {actual_sha512} vs {expected_sha512}")
                return False
        else:
            print(f"[ERROR] SHA512哈希计算失败: {result4}")
            return False
        
        # 测试5: 哈希验证（正确哈希）
        print("\n--- 测试5: 哈希验证（正确哈希） ---")
        async def verify_correct_hash():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="md5",
                verify_hash=expected_md5
            )
        
        result5 = asyncio.run(verify_correct_hash())
        if result5.get('status') == 'success':
            verify_data = result5.get('data', {})
            verification_result = verify_data.get('verification_result')
            
            if verification_result:
                print(f"[OK] 哈希验证成功（正确哈希）: {result5.get('message')}")
                print(f"    验证状态: {verify_data.get('verification_status')}")
            else:
                print(f"[ERROR] 正确哈希应该验证通过: {verify_data}")
                return False
        else:
            print(f"[ERROR] 哈希验证失败: {result5}")
            return False
        
        # 测试6: 哈希验证（错误哈希）
        print("\n--- 测试6: 哈希验证（错误哈希） ---")
        wrong_hash = "1234567890abcdef1234567890abcdef"  # 错误的MD5哈希
        
        async def verify_wrong_hash():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="md5",
                verify_hash=wrong_hash
            )
        
        result6 = asyncio.run(verify_wrong_hash())
        if result6.get('status') == 'success':
            verify_data2 = result6.get('data', {})
            verification_result2 = verify_data2.get('verification_result')
            
            if not verification_result2:
                print(f"[OK] 哈希验证成功（错误哈希）: {result6.get('message')}")
                print(f"    验证状态: {verify_data2.get('verification_status')}")
                print(f"    预期哈希: {verify_data2.get('expected_hash')}")
                print(f"    实际哈希: {verify_data2.get('actual_hash')}")
            else:
                print(f"[ERROR] 错误哈希应该验证失败: {verify_data2}")
                return False
        else:
            print(f"[ERROR] 哈希验证失败: {result6}")
            return False
        
        # 测试7: 自定义分块大小
        print("\n--- 测试7: 自定义分块大小 ---")
        async def calculate_with_custom_chunk():
            return await tools.file_checksum(
                file_path=str(test_file),
                algorithm="md5",
                chunk_size=16384  # 16KB分块
            )
        
        result7 = asyncio.run(calculate_with_custom_chunk())
        if result7.get('status') == 'success':
            custom_data = result7.get('data', {})
            actual_md5_custom = custom_data.get('checksum', '')
            
            if actual_md5_custom == expected_md5:
                print(f"[OK] 自定义分块大小计算成功: {custom_data.get('message')}")
                print(f"    分块大小: {custom_data.get('chunk_size')} 字节")
                print(f"    计算MD5: {actual_md5_custom}")
            else:
                print(f"[ERROR] 自定义分块大小哈希不匹配: {actual_md5_custom} vs {expected_md5}")
                return False
        else:
            print(f"[ERROR] 自定义分块大小计算失败: {result7}")
            return False
        
        # 测试8: 大文件哈希计算（创建大文件）
        print("\n--- 测试8: 大文件哈希计算 ---")
        large_file = Path(temp_dir) / "large.bin"
        # 创建1MB的大文件
        chunk_size = 1024 * 1024  # 1MB
        with open(large_file, 'wb') as f:
            for i in range(1024):  # 写入1024个1KB块，总共1MB
                f.write(b'X' * 1024)
        
        print(f"[OK] 创建大文件: {large_file}")
        print(f"    文件大小: {large_file.stat().st_size} 字节")
        
        # 计算大文件的MD5
        async def calculate_large_file():
            return await tools.file_checksum(
                file_path=str(large_file),
                algorithm="md5",
                chunk_size=65536  # 64KB分块
            )
        
        result8 = asyncio.run(calculate_large_file())
        if result8.get('status') == 'success':
            large_data = result8.get('data', {})
            print(f"[OK] 大文件哈希计算成功: {large_data.get('message')}")
            print(f"    文件大小: {large_data.get('file_size')} 字节")
            print(f"    分块大小: {large_data.get('chunk_size')} 字节")
            print(f"    耗时: {large_data.get('elapsed_time', 0):.4f} 秒")
            print(f"    计算MD5: {large_data.get('checksum')}")
        else:
            print(f"[ERROR] 大文件哈希计算失败: {result8}")
            return False
        
        # 测试9: 不存在的文件
        print("\n--- 测试9: 不存在的文件 ---")
        non_existent_file = Path(temp_dir) / "non_existent.txt"
        
        async def calculate_nonexistent():
            return await tools.file_checksum(
                file_path=str(non_existent_file),
                algorithm="md5"
            )
        
        result9 = asyncio.run(calculate_nonexistent())
        if result9.get('status') == 'error':
            print(f"[OK] 不存在的文件处理正确: {result9.get('error')}")
        else:
            print(f"[ERROR] 不存在的文件应该返回错误: {result9}")
            return False
        
        # 测试10: 目录而不是文件
        print("\n--- 测试10: 目录而不是文件 ---")
        async def calculate_directory():
            return await tools.file_checksum(
                file_path=str(temp_dir),
                algorithm="md5"
            )
        
        result10 = asyncio.run(calculate_directory())
        if result10.get('status') == 'error':
            print(f"[OK] 目录处理正确: {result10.get('error')}")
        else:
            print(f"[ERROR] 目录应该返回错误: {result10}")
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
    print("开始测试file_checksum工具")
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
        print("[SUCCESS] 所有测试通过！file_checksum工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())