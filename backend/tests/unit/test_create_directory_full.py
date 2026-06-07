#!/usr/bin/env python3
"""测试create_directory工具 - 完整功能测试"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_create_directory():
    """测试create_directory功能"""
    print("=== 测试create_directory功能 ===")
    
    temp_dir = tempfile.mkdtemp(prefix="test_create_dir_")
    print(f"临时目录: {temp_dir}")
    
    try:
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        tools = FileTools(task_id="test_session")
        
        # 测试1: 创建简单目录
        test_dir1 = Path(temp_dir) / "test_dir1"
        
        async def do_create1():
            return await tools.create_directory(
                dir_path=str(test_dir1),
                parents=True,
                exist_ok=True
            )
        
        result1 = asyncio.run(do_create1())
        
        if result1.get('status') == 'success' and test_dir1.exists():
            print(f"[OK] 测试1通过: 创建简单目录成功")
        else:
            print(f"[ERROR] 测试1失败: {result1}")
            return False
        
        # 测试2: 创建嵌套目录
        test_dir2 = Path(temp_dir) / "parent" / "child" / "grandchild"
        
        async def do_create2():
            return await tools.create_directory(
                dir_path=str(test_dir2),
                parents=True,
                exist_ok=True
            )
        
        result2 = asyncio.run(do_create2())
        
        if result2.get('status') == 'success' and test_dir2.exists():
            print(f"[OK] 测试2通过: 创建嵌套目录成功")
        else:
            print(f"[ERROR] 测试2失败: {result2}")
            return False
        
        # 测试3: 已存在目录
        async def do_create3():
            return await tools.create_directory(
                dir_path=str(test_dir1),
                parents=True,
                exist_ok=True
            )
        
        result3 = asyncio.run(do_create3())
        
        if result3.get('status') == 'success':
            print(f"[OK] 测试3通过: 已存在目录处理正确")
        else:
            print(f"[ERROR] 测试3失败: {result3}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            shutil.rmtree(temp_dir)
            print(f"[OK] 清理临时目录")
        except:
            pass


def main():
    print("=" * 60)
    print("开始测试create_directory工具")
    print("=" * 60)
    
    if test_create_directory():
        print("\n" + "=" * 60)
        print("[SUCCESS] 所有测试通过！create_directory工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("\n" + "=" * 60)
        print("[FAILED] 测试失败")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())