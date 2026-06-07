#!/usr/bin/env python3
"""
测试file_monitor工具 - 完整功能测试

测试内容：
1. 导入测试
2. Schema测试
3. 函数签名测试
4. 实际功能测试（创建测试文件、监控、验证）

注意：实际功能测试是手动运行的，不通过pytest自动运行
"""

import sys
import os
import tempfile
import shutil
import time
from pathlib import Path
import pytest

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.insert(0, backend_dir)


def test_import():
    """测试导入"""
    print("=== 测试1: 导入测试 ===")
    
    try:
        from app.services.tools.file.file_monitor import file_monitor_impl
        print("[OK] file_monitor_impl导入成功")
    except Exception as e:
        print(f"[ERROR] file_monitor_impl导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    try:
        from app.services.tools.file.file_schema import FileMonitorInput
        print("[OK] FileMonitorInput导入成功")
    except Exception as e:
        print(f"[ERROR] FileMonitorInput导入失败: {e}")
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
        from app.services.tools.file.file_schema import FileMonitorInput
        
        # 测试默认值
        input1 = FileMonitorInput(
            path="C:/test",
            event_type="all"
        )
        assert input1.path == "C:/test"
        assert input1.event_type == "all"
        assert input1.duration == 5
        assert input1.poll_interval == 1
        print("[OK] 默认值测试通过")
        
        # 测试自定义值
        input2 = FileMonitorInput(
            path="C:/test",
            event_type="created",
            duration=10,
            poll_interval=2
        )
        assert input2.event_type == "created"
        assert input2.duration == 10
        assert input2.poll_interval == 2
        print("[OK] 自定义值测试通过")
        
        # 测试无效事件类型
        try:
            input3 = FileMonitorInput(
                path="C:/test",
                event_type="invalid"
            )
            print("[ERROR] 无效事件类型应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效事件类型验证通过")
        
        # 测试无效持续时间
        try:
            input4 = FileMonitorInput(
                path="C:/test",
                event_type="all",
                duration=0
            )
            print("[ERROR] 无效持续时间应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效持续时间验证通过")
        
        # 测试无效轮询间隔
        try:
            input5 = FileMonitorInput(
                path="C:/test",
                event_type="all",
                poll_interval=0
            )
            print("[ERROR] 无效轮询间隔应该抛出异常")
            return False
        except ValueError:
            print("[OK] 无效轮询间隔验证通过")
        
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
        from app.services.tools.file.file_monitor import file_monitor_impl
        import inspect
        
        sig = inspect.signature(file_monitor_impl)
        params = list(sig.parameters.keys())
        
        required_params = [
            'path', 'event_type', 'duration', 'poll_interval',
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


# 使用 pytest.mark.skip 跳过异步测试
@pytest.mark.asyncio
async def test_actual_functionality_async():
    """测试实际功能（异步版本）"""
    print("\n=== 测试4: 实际功能测试 ===")
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_file_monitor_")
    print(f"临时目录: {temp_dir}")
    
    try:
        # 导入必要的模块
        from app.services.tools.file.file_tools import FileTools
        import asyncio
        
        # 创建FileTools实例
        tools = FileTools(task_id="test_session")
        
        # 测试1: 监控文件创建事件
        print("\n--- 测试1: 监控文件创建事件 ---")
        
        # 创建监控任务
        async def monitor_created():
            return await tools.file_monitor(
                path=str(temp_dir),
                event_type="created",
                duration=3,  # 只监控3秒
                poll_interval=1
            )
        
        # 启动监控
        monitor_task = asyncio.create_task(monitor_created())
        
        # 等待1秒后创建文件
        await asyncio.sleep(1)
        
        # 创建测试文件
        test_file = Path(temp_dir) / "test_created.txt"
        test_file.write_text("Test content for created event", encoding='utf-8')
        print(f"[OK] 创建测试文件: {test_file}")
        
        # 等待监控完成
        result1 = await monitor_task
        
        if result1.get('status') == 'success':
            monitor_data = result1.get('data', {})
            events = monitor_data.get('events', [])
            
            if events:
                print(f"[OK] 文件创建事件监控成功: {monitor_data.get('message')}")
                print(f"    检测到 {len(events)} 个事件")
                for event in events:
                    print(f"    - {event.get('event_type')}: {event.get('path')}")
                
                # 检查是否检测到创建事件
                created_events = [e for e in events if e.get('event_type') == 'created']
                if created_events:
                    print(f"[OK] 成功检测到文件创建事件")
                else:
                    print(f"[ERROR] 未检测到文件创建事件: {events}")
                    return False
            else:
                print(f"[ERROR] 应该检测到事件: {monitor_data}")
                return False
        else:
            print(f"[ERROR] 文件创建事件监控失败: {result1}")
            return False
        
        # 测试2: 监控文件修改事件
        print("\n--- 测试2: 监控文件修改事件 ---")
        
        async def monitor_modified():
            return await tools.file_monitor(
                path=str(temp_dir),
                event_type="modified",
                duration=3,
                poll_interval=1
            )
        
        # 启动监控
        monitor_task2 = asyncio.create_task(monitor_modified())
        
        # 等待1秒后修改文件
        await asyncio.sleep(1)
        
        # 修改测试文件
        test_file.write_text("Modified content", encoding='utf-8')
        print(f"[OK] 修改测试文件: {test_file}")
        
        # 等待监控完成
        result2 = await monitor_task2
        
        if result2.get('status') == 'success':
            monitor_data2 = result2.get('data', {})
            events2 = monitor_data2.get('events', [])
            
            if events2:
                print(f"[OK] 文件修改事件监控成功: {monitor_data2.get('message')}")
                print(f"    检测到 {len(events2)} 个事件")
                
                # 检查是否检测到修改事件
                modified_events = [e for e in events2 if e.get('event_type') == 'modified']
                if modified_events:
                    print(f"[OK] 成功检测到文件修改事件")
                else:
                    print(f"[ERROR] 未检测到文件修改事件: {events2}")
                    return False
            else:
                print(f"[ERROR] 应该检测到修改事件: {monitor_data2}")
                return False
        else:
            print(f"[ERROR] 文件修改事件监控失败: {result2}")
            return False
        
        # 测试3: 监控文件删除事件
        print("\n--- 测试3: 监控文件删除事件 ---")
        
        # 创建另一个文件用于删除
        test_file2 = Path(temp_dir) / "test_delete.txt"
        test_file2.write_text("Test content for delete event", encoding='utf-8')
        
        async def monitor_deleted():
            return await tools.file_monitor(
                path=str(temp_dir),
                event_type="deleted",
                duration=3,
                poll_interval=1
            )
        
        # 启动监控
        monitor_task3 = asyncio.create_task(monitor_deleted())
        
        # 等待1秒后删除文件
        await asyncio.sleep(1)
        
        # 删除测试文件
        test_file2.unlink()
        print(f"[OK] 删除测试文件: {test_file2}")
        
        # 等待监控完成
        result3 = await monitor_task3
        
        if result3.get('status') == 'success':
            monitor_data3 = result3.get('data', {})
            events3 = monitor_data3.get('events', [])
            
            if events3:
                print(f"[OK] 文件删除事件监控成功: {monitor_data3.get('message')}")
                print(f"    检测到 {len(events3)} 个事件")
                
                # 检查是否检测到删除事件
                deleted_events = [e for e in events3 if e.get('event_type') == 'deleted']
                if deleted_events:
                    print(f"[OK] 成功检测到文件删除事件")
                else:
                    print(f"[ERROR] 未检测到文件删除事件: {events3}")
                    return False
            else:
                print(f"[ERROR] 应该检测到删除事件: {monitor_data3}")
                return False
        else:
            print(f"[ERROR] 文件删除事件监控失败: {result3}")
            return False
        
        # 测试4: 监控所有事件
        print("\n--- 测试4: 监控所有事件 ---")
        
        async def monitor_all():
            return await tools.file_monitor(
                path=str(temp_dir),
                event_type="all",
                duration=5,
                poll_interval=1
            )
        
        # 启动监控
        monitor_task4 = asyncio.create_task(monitor_all())
        
        # 在监控期间执行多个操作
        await asyncio.sleep(1)
        
        # 创建新文件
        test_file3 = Path(temp_dir) / "test_all_1.txt"
        test_file3.write_text("Test for all events 1", encoding='utf-8')
        
        await asyncio.sleep(1)
        
        # 修改文件
        test_file3.write_text("Modified for all events", encoding='utf-8')
        
        await asyncio.sleep(1)
        
        # 重命名文件
        test_file4 = Path(temp_dir) / "test_all_2.txt"
        test_file3.rename(test_file4)
        
        await asyncio.sleep(1)
        
        # 删除文件
        test_file4.unlink()
        
        # 等待监控完成
        result4 = await monitor_task4
        
        if result4.get('status') == 'success':
            monitor_data4 = result4.get('data', {})
            events4 = monitor_data4.get('events', [])
            
            if events4:
                print(f"[OK] 所有事件监控成功: {monitor_data4.get('message')}")
                print(f"    检测到 {len(events4)} 个事件")
                
                # 统计事件类型
                event_counts = {}
                for event in events4:
                    event_type = event.get('event_type')
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1
                
                print(f"    事件统计: {event_counts}")
                
                # 检查是否检测到多种事件
                if len(event_counts) >= 2:
                    print(f"[OK] 成功检测到多种事件类型")
                else:
                    print(f"[WARNING] 只检测到 {len(event_counts)} 种事件类型")
            else:
                print(f"[ERROR] 应该检测到事件: {monitor_data4}")
                return False
        else:
            print(f"[ERROR] 所有事件监控失败: {result4}")
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


async def run_async_tests():
    """运行异步测试"""
    return await test_actual_functionality_async()


def main():
    """主测试函数"""
    print("=" * 60)
    print("开始测试file_monitor工具")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_import),
        ("Schema测试", test_schema),
        ("函数签名测试", test_function_signature),
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
    
    # 运行异步功能测试
    print("\n=== 测试4: 实际功能测试 ===")
    try:
        import asyncio
        actual_passed = asyncio.run(run_async_tests())
        if actual_passed:
            print(f"\n[OK] 实际功能测试 通过")
        else:
            print(f"\n[ERROR] 实际功能测试 失败")
            all_passed = False
    except Exception as e:
        print(f"\n[ERROR] 实际功能测试 出错: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] 所有测试通过！file_monitor工具工作正常")
        print("=" * 60)
        return 0
    else:
        print("[FAILED] 测试失败，请检查上述问题")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())