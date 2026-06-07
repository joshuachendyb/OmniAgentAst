#!/usr/bin/env python3
"""
测试file_statistics工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、统计、验证）
"""

import sys
import os
import tempfile
import shutil
import json
from pathlib import Path

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.file_statistics import file_statistics_impl
        print("[OK] file_statistics_impl导入成功")
    except Exception as e:
        print(f"[ERROR] file_statistics_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import FileStatisticsInput
        print("[OK] FileStatisticsInput导入成功")
    except Exception as e:
        print(f"[ERROR] FileStatisticsInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import FileStatisticsInput
        
        # 测试默认值
        input1 = FileStatisticsInput(
            directory="C:/test"
        )
        assert input1.directory == "C:/test"
        assert input1.recursive == True
        assert input1.max_depth == 100000
        assert input1.filters is None
        assert input1.output_format == "json"
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = FileStatisticsInput(
            directory="C:/test",
            recursive=False,
            max_depth=5,
            filters={"file_type": ".txt", "min_size": 1024},
            output_format="csv"
        )
        assert input2.recursive == False
        assert input2.max_depth == 5
        assert input2.filters == {"file_type": ".txt", "min_size": 1024}
        assert input2.output_format == "csv"
        print("[OK] 自定义值测试通过")
        
        # 测试无效输出格式
        try:
            input3 = FileStatisticsInput(
                directory="C:/test",
                output_format="invalid"
            )
            print("[ERROR] 无效输出格式应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效输出格式验证通过")
        
        # 测试无效最大深度
        try:
            input4 = FileStatisticsInput(
                directory="C:/test",
                max_depth=0
            )
            print("[ERROR] 无效最大深度应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效最大深度验证通过")
        
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
        from app.services.tools.file.file_statistics import file_statistics_impl
        import inspect
        
        sig = inspect.signature(file_statistics_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'directory', 'recursive', 'max_depth', 'filters', 'output_format',
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
    temp_dir = tempfile.mkdtemp(prefix="test_file_statistics_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 创建测试目录结构
        test_dir = Path(temp_dir) / "test_data"
        test_dir.mkdir()
        
        # 创建不同大小和类型的测试文件
        test_files = [
            (test_dir / "small.txt", 500, ".txt"),  # 500字节
            (test_dir / "medium.txt", 50000, ".txt"),  # 50KB
            (test_dir / "large.txt", 2000000, ".txt"),  # 2MB
            (test_dir / "document.pdf", 100000, ".pdf"),  # 100KB
            (test_dir / "image.jpg", 1500000, ".jpg"),  # 1.5MB
            (test_dir / "code.py", 2000, ".py"),  # 2KB
            (test_dir / "data.csv", 50000, ".csv"),  # 50KB
        ]
        
        # 创建子目录和文件
        subdir = test_dir / "subdir"
        subdir.mkdir()
        test_files.append((subdir / "nested.txt", 1000, ".txt"))  # 1KB
        
        # 创建文件
        for file_path, size, ext in test_files:
            # 创建父目录（如果不存在）
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # 写入指定大小的内容
            content = "X" * size
            file_path.write_text(content, encoding='utf-8')
        
        print(f"[OK] 创建测试目录结构: {test_dir}")
        print(f"    创建了 {len(test_files)} 个测试文件")
        
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: JSON格式统计
        print("\n--- 测试1: JSON格式统计 ---")
        async def statistics_json():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                output_format="json"
            )
        
        result1 = asyncio.run(statistics_json())
        if result1.get('status') == 'success':
            stats_data = result1.get('data', {})
            if stats_data.get('total_files', 0) == len(test_files):
                print(f"[OK] JSON格式统计成功: {stats_data.get('message')}")
                print(f"    总文件数: {stats_data.get('total_files')}")
                print(f"    总大小: {stats_data.get('total_size')} 字节")
                print(f"    文件类型分布: {stats_data.get('file_types', {})}")
                
                # 验证输出格式
                output = stats_data.get('output', '')
                if output and output.startswith('{'):
                    print("[OK] JSON输出格式正确")
                else:
                    print(f"[ERROR] JSON输出格式不正确: {output[:100]}")
                    return False
            else:
                print(f"[ERROR] 文件数量不匹配: {stats_data.get('total_files')} vs {len(test_files)}")
                return False
        else:
            print(f"[ERROR] JSON格式统计失败: {result1}")
            return False
        
        # 测试2: CSV格式统计
        print("\n--- 测试2: CSV格式统计 ---")
        async def statistics_csv():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                output_format="csv"
            )
        
        result2 = asyncio.run(statistics_csv())
        if result2.get('status') == 'success':
            stats_data2 = result2.get('data', {})
            if stats_data2.get('total_files', 0) == len(test_files):
                print(f"[OK] CSV格式统计成功: {stats_data2.get('message')}")
                print(f"    总文件数: {stats_data2.get('total_files')}")
                
                # 验证输出格式
                output = stats_data2.get('output', '')
                if output and '统计项,值' in output:
                    print("[OK] CSV输出格式正确")
                else:
                    print(f"[ERROR] CSV输出格式不正确: {output[:100]}")
                    return False
            else:
                print(f"[ERROR] 文件数量不匹配: {stats_data2.get('total_files')} vs {len(test_files)}")
                return False
        else:
            print(f"[ERROR] CSV格式统计失败: {result2}")
            return False
        
        # 测试3: 文本格式统计
        print("\n--- 测试3: 文本格式统计 ---")
        async def statistics_text():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                output_format="text"
            )
        
        result3 = asyncio.run(statistics_text())
        if result3.get('status') == 'success':
            stats_data3 = result3.get('data', {})
            if stats_data3.get('total_files', 0) == len(test_files):
                print(f"[OK] 文本格式统计成功: {stats_data3.get('message')}")
                print(f"    总文件数: {stats_data3.get('total_files')}")
                
                # 验证输出格式
                output = stats_data3.get('output', '')
                if output and '目录统计:' in output:
                    print("[OK] 文本输出格式正确")
                else:
                    print(f"[ERROR] 文本输出格式不正确: {output[:100]}")
                    return False
            else:
                print(f"[ERROR] 文件数量不匹配: {stats_data3.get('total_files')} vs {len(test_files)}")
                return False
        else:
            print(f"[ERROR] 文本格式统计失败: {result3}")
            return False
        
        # 测试4: 非递归统计
        print("\n--- 测试4: 非递归统计 ---")
        async def statistics_non_recursive():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=False,
                output_format="json"
            )
        
        result4 = asyncio.run(statistics_non_recursive())
        if result4.get('status') == 'success':
            stats_data4 = result4.get('data', {})
            # 非递归应该只统计根目录下的文件（不包括子目录）
            root_files = [f for f in test_files if f[0].parent == test_dir]
            if stats_data4.get('total_files', 0) == len(root_files):
                print(f"[OK] 非递归统计成功: {stats_data4.get('message')}")
                print(f"    根目录文件数: {stats_data4.get('total_files')} (应该是 {len(root_files)})")
            else:
                print(f"[ERROR] 非递归文件数量不匹配: {stats_data4.get('total_files')} vs {len(root_files)}")
                return False
        else:
            print(f"[ERROR] 非递归统计失败: {result4}")
            return False
        
        # 测试5: 带过滤条件的统计
        print("\n--- 测试5: 带过滤条件的统计 ---")
        async def statistics_with_filter():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                filters={"file_type": ".txt"},
                output_format="json"
            )
        
        result5 = asyncio.run(statistics_with_filter())
        if result5.get('status') == 'success':
            stats_data5 = result5.get('data', {})
            # 只统计.txt文件
            txt_files = [f for f in test_files if f[2] == '.txt']
            if stats_data5.get('total_files', 0) == len(txt_files):
                print(f"[OK] 带过滤条件统计成功: {stats_data5.get('message')}")
                print(f"    .txt文件数: {stats_data5.get('total_files')} (应该是 {len(txt_files)})")
                
                # 验证文件类型分布
                file_types = stats_data5.get('file_types', {})
                if '.txt' in file_types and file_types['.txt'] == len(txt_files):
                    print("[OK] 文件类型过滤正确")
                else:
                    print(f"[ERROR] 文件类型过滤不正确: {file_types}")
                    return False
            else:
                print(f"[ERROR] 过滤后文件数量不匹配: {stats_data5.get('total_files')} vs {len(txt_files)}")
                return False
        else:
            print(f"[ERROR] 带过滤条件统计失败: {result5}")
            return False
        
        # 测试6: 带大小过滤的统计
        print("\n--- 测试6: 带大小过滤的统计 ---")
        async def statistics_with_size_filter():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                filters={"min_size": 100000},  # 只统计大于100KB的文件
                output_format="json"
            )
        
        result6 = asyncio.run(statistics_with_size_filter())
        if result6.get('status') == 'success':
            stats_data6 = result6.get('data', {})
            # 只统计大于100KB的文件
            large_files = [f for f in test_files if f[1] >= 100000]
            if stats_data6.get('total_files', 0) == len(large_files):
                print(f"[OK] 带大小过滤统计成功: {stats_data6.get('message')}")
                print(f"    大于100KB文件数: {stats_data6.get('total_files')} (应该是 {len(large_files)})")
            else:
                print(f"[ERROR] 大小过滤后文件数量不匹配: {stats_data6.get('total_files')} vs {len(large_files)}")
                return False
        else:
            print(f"[ERROR] 带大小过滤统计失败: {result6}")
            return False
        
        # 测试7: 限制最大深度
        print("\n--- 测试7: 限制最大深度 ---")
        async def statistics_with_depth():
            return await tools.file_statistics(
                directory=str(test_dir),
                recursive=True,
                max_depth=0,  # 只统计根目录
                output_format="json"
            )
        
        result7 = asyncio.run(statistics_with_depth())
        if result7.get('status') == 'success':
            stats_data7 = result7.get('data', {})
            # 深度为0应该只统计根目录
            root_files = [f for f in test_files if f[0].parent == test_dir]
            if stats_data7.get('total_files', 0) == len(root_files):
                print(f"[OK] 限制深度统计成功: {stats_data7.get('message')}")
                print(f"    深度0文件数: {stats_data7.get('total_files')} (应该是 {len(root_files)})")
            else:
                print(f"[ERROR] 限制深度后文件数量不匹配: {stats_data7.get('total_files')} vs {len(root_files)}")
                return False
        else:
            print(f"[ERROR] 限制深度统计失败: {result7}")
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
    print("开始测试file_statistics工具")
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
        print("[SUCCESS] 所有测试通过！file_statistics工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())