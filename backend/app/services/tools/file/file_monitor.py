# -*- coding: utf-8 -*-
"""
file_monitor - 监控文件变化

功能：
- 监控文件或目录的变化事件（创建、修改、删除、重命名）
- 支持事件类型过滤
- 支持递归监控
- 支持自定义过滤条件
- 支持定时监控

Author: 小健 - 2026-04-19
"""

import asyncio
import time
import threading
import queue
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Callable
from datetime import datetime, timedelta


async def file_monitor_impl(
    directory: str,
    event_types: List[str] = None,
    recursive: bool = True,
    filters: Optional[Dict[str, Any]] = None,
    duration: Optional[int] = None,
    validate_path_func=None,
    safety_service=None,
    task_id: Optional[str] = None,
    record_operation_func=None,
    execute_with_safety_func=None,
    to_unified_format_func=None,
    get_next_sequence_func=None,
) -> Dict[str, Any]:
    """
    file_monitor工具的实现函数
    
    Args:
        directory: 监控目录路径
        event_types: 监控事件类型列表
        recursive: 是否递归监控子目录
        filters: 过滤条件字典
        duration: 监控持续时间（秒）
        validate_path_func: 路径验证函数
        safety_service: 安全服务
        task_id: 任务ID
        record_operation_func: 记录操作函数
        execute_with_safety_func: 安全执行函数
        to_unified_format_func: 统一格式转换函数
        get_next_sequence_func: 获取下一个序列号函数
    
    Returns:
        统一格式的结果字典
    """
    from app.services.safety.file.file_safety import OperationType
    
    # 设置默认事件类型
    if event_types is None:
        event_types = ["created", "modified", "deleted", "renamed"]
    
    # 验证路径
    is_valid, error_msg = validate_path_func(directory)
    if not is_valid:
        return to_unified_format_func({
            "success": False,
            "error": f"目录路径验证失败: {error_msg}",
            "operation_id": None
        }, "file_monitor")
    
    if not task_id:
        return to_unified_format_func({
            "success": False,
            "error": "No active task",
            "operation_id": None
        }, "file_monitor")
    
    dir_path = Path(directory)
    
    try:
        # 检查目录是否存在
        if not dir_path.exists():
            return to_unified_format_func({
                "success": False,
                "error": f"目录不存在: {directory}",
                "operation_id": None
            }, "file_monitor")
        
        if not dir_path.is_dir():
            return to_unified_format_func({
                "success": False,
                "error": f"路径不是目录: {directory}",
                "operation_id": None
            }, "file_monitor")
        
        # 记录操作
        operation_id = record_operation_func(
            task_id=task_id,
            operation_type=OperationType.MONITOR,
            source_path=dir_path,
            destination_path=None,
            sequence_number=get_next_sequence_func()
        )
        
        # 定义监控操作
        def _monitor_sync():
            try:
                # 初始化事件队列
                event_queue = queue.Queue()
                events_detected = []
                start_time = time.time()
                end_time = start_time + duration if duration else None
                
                # 获取初始文件状态
                initial_files = _get_files_in_directory(dir_path, recursive)
                
                # 监控循环
                while True:
                    # 检查是否超时
                    current_time = time.time()
                    if end_time and current_time >= end_time:
                        break
                    
                    # 获取当前文件状态
                    current_files = _get_files_in_directory(dir_path, recursive)
                    
                    # 检测文件变化
                    new_events = _detect_file_changes(
                        initial_files, 
                        current_files, 
                        event_types,
                        filters
                    )
                    
                    # 添加新事件到队列
                    for event in new_events:
                        event_queue.put(event)
                        events_detected.append(event)
                    
                    # 更新初始文件状态
                    initial_files = current_files
                    
                    # 检查是否有事件需要处理
                    if not event_queue.empty():
                        # 处理事件
                        while not event_queue.empty():
                            event = event_queue.get()
                            # 这里可以添加事件处理逻辑
                            # 例如：记录到数据库、发送通知等
                            pass
                    
                    # 等待一段时间再检查
                    time.sleep(1)  # 1秒检查一次
                
                # 构建监控结果
                monitoring_duration = time.time() - start_time
                
                return {
                    "directory": str(dir_path),
                    "event_types": event_types,
                    "recursive": recursive,
                    "filters": filters or {},
                    "duration": duration,
                    "actual_duration": monitoring_duration,
                    "events_count": len(events_detected),
                    "events": events_detected[:100],  # 限制返回的事件数量
                    "start_time": start_time,
                    "end_time": time.time()
                }
                
            except Exception as e:
                raise e
        
        # 执行监控操作
        result = await asyncio.to_thread(
            execute_with_safety_func,
            operation_id=operation_id,
            operation_func=_monitor_sync
        )
        
        if result:
            return to_unified_format_func({
                "success": True,
                "operation_id": operation_id,
                **result
            }, "file_monitor")
        else:
            return to_unified_format_func({
                "success": False,
                "error": "文件监控失败",
                "operation_id": operation_id
            }, "file_monitor")
            
    except Exception as e:
        return to_unified_format_func({
            "success": False,
            "error": str(e),
            "operation_id": None
        }, "file_monitor")


def _get_files_in_directory(directory: Path, recursive: bool) -> Dict[str, Dict[str, Any]]:
    """
    获取目录中的文件信息
    
    Args:
        directory: 目录路径
        recursive: 是否递归
    
    Returns:
        文件信息字典 {文件路径: {大小, 修改时间, 是否为目录}}
    """
    files = {}
    
    if recursive:
        paths = directory.rglob("*")
    else:
        paths = directory.iterdir()
    
    for path in paths:
        if path.is_file() or path.is_dir():
            try:
                stat = path.stat()
                files[str(path)] = {
                    "size": stat.st_size if path.is_file() else 0,
                    "mtime": stat.st_mtime,
                    "is_dir": path.is_dir(),
                    "path": str(path)
                }
            except (OSError, PermissionError):
                continue
    
    return files


def _detect_file_changes(
    old_files: Dict[str, Dict[str, Any]],
    new_files: Dict[str, Dict[str, Any]],
    event_types: List[str],
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    检测文件变化
    
    Args:
        old_files: 旧文件状态
        new_files: 新文件状态
        event_types: 要检测的事件类型
        filters: 过滤条件
    
    Returns:
        检测到的事件列表
    """
    events = []
    
    # 应用过滤条件
    def _apply_filters(file_info: Dict[str, Any]) -> bool:
        if not filters:
            return True
        
        # 文件类型过滤
        if "file_type" in filters:
            file_type = filters["file_type"]
            path = Path(file_info["path"])
            if not path.suffix.lower().endswith(file_type.lower()):
                return False
        
        # 文件大小过滤
        if "min_size" in filters and file_info["size"] < filters["min_size"]:
            return False
        if "max_size" in filters and file_info["size"] > filters["max_size"]:
            return False
        
        # 修改时间过滤
        if "modified_after" in filters:
            modified_after = filters["modified_after"]
            if isinstance(modified_after, (int, float)):
                # 时间戳
                if file_info["mtime"] < modified_after:
                    return False
            elif isinstance(modified_after, str):
                # 日期字符串，尝试解析
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(modified_after.replace('Z', '+00:00'))
                    if file_info["mtime"] < dt.timestamp():
                        return False
                except:
                    pass
        
        return True
    
    # 检测创建事件
    if "created" in event_types:
        for file_path, file_info in new_files.items():
            if file_path not in old_files and _apply_filters(file_info):
                events.append({
                    "event_type": "created",
                    "file_path": file_path,
                    "timestamp": time.time(),
                    "size": file_info["size"],
                    "is_directory": file_info["is_dir"]
                })
    
    # 检测删除事件
    if "deleted" in event_types:
        for file_path, file_info in old_files.items():
            if file_path not in new_files and _apply_filters(file_info):
                events.append({
                    "event_type": "deleted",
                    "file_path": file_path,
                    "timestamp": time.time(),
                    "size": file_info["size"],
                    "is_directory": file_info["is_dir"]
                })
    
    # 检测修改事件
    if "modified" in event_types:
        for file_path, new_info in new_files.items():
            if file_path in old_files:
                old_info = old_files[file_path]
                if (not new_info["is_dir"] and  # 目录修改时间变化频繁，不检测
                    new_info["mtime"] != old_info["mtime"] and
                    _apply_filters(new_info)):
                    events.append({
                        "event_type": "modified",
                        "file_path": file_path,
                        "timestamp": time.time(),
                        "old_size": old_info["size"],
                        "new_size": new_info["size"],
                        "old_mtime": old_info["mtime"],
                        "new_mtime": new_info["mtime"],
                        "is_directory": False
                    })
    
    # 检测重命名事件（简单实现：通过文件大小和修改时间匹配）
    if "renamed" in event_types:
        # 查找可能的重命名文件
        for old_path, old_info in old_files.items():
            if old_path not in new_files and not old_info["is_dir"]:
                # 查找具有相同大小和修改时间的新文件
                for new_path, new_info in new_files.items():
                    if (new_path not in old_files and
                        not new_info["is_dir"] and
                        new_info["size"] == old_info["size"] and
                        abs(new_info["mtime"] - old_info["mtime"]) < 1.0 and  # 1秒内
                        _apply_filters(new_info)):
                        events.append({
                            "event_type": "renamed",
                            "old_path": old_path,
                            "new_path": new_path,
                            "timestamp": time.time(),
                            "size": new_info["size"],
                            "is_directory": False
                        })
                        break
    
    return events


class FileMonitor:
    """文件监控器类（简化版本）"""
    
    def __init__(self, directory: str, recursive: bool = True):
        self.directory = Path(directory)
        self.recursive = recursive
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self.events = []
    
    def start(self, callback: Callable[[Dict[str, Any]], None]):
        """开始监控"""
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(callback,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop(self):
        """停止监控"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self, callback: Callable[[Dict[str, Any]], None]):
        """监控循环"""
        old_files = _get_files_in_directory(self.directory, self.recursive)
        
        while not self._stop_event.is_set():
            time.sleep(1)  # 每秒检查一次
            
            new_files = _get_files_in_directory(self.directory, self.recursive)
            
            # 检测变化
            events = _detect_file_changes(
                old_files, 
                new_files, 
                ["created", "modified", "deleted", "renamed"]
            )
            
            # 调用回调函数处理事件
            for event in events:
                callback(event)
                self.events.append(event)
            
            old_files = new_files
