"""
MCP文件操作工具集 (MCP File Operation Tools)
实现ReAct执行器所需的文件操作工具，包含完整的安全机制
"""
import os
import re
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from app.services.file_operations import (
    get_file_safety_service,
    get_session_service
)
from app.services.file_operations.safety import OperationType
from app.utils.visualization import get_visualizer
from app.utils.logger import logger


class FileTools:
    """
    文件操作工具类
    
    所有工具都集成文件安全机制：
    - 操作历史记录
    - 删除文件自动备份到回收站
    - 支持回滚操作
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.safety = get_file_safety_service()
        self.session = get_session_service()
        self.visualizer = get_visualizer()
        self.session_id = session_id
        self._sequence = 0
    
    def _get_next_sequence(self) -> int:
        """获取下一个操作序号"""
        self._sequence += 1
        return self._sequence
    
    def set_session(self, session_id: str):
        """设置当前会话ID"""
        self.session_id = session_id
        self._sequence = 0
    
    async def read_file(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
            offset: 起始行号（1-based）
            limit: 最大读取行数
            encoding: 文件编码
            
        Returns:
            文件内容和元数据
        """
        path = Path(file_path)
        
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "content": None
                }
            
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"Not a file: {file_path}",
                    "content": None
                }
            
            # 读取文件内容
            with open(path, 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            
            # 处理offset和limit
            if offset < 1:
                offset = 1
            start_idx = offset - 1
            end_idx = min(start_idx + limit, total_lines)
            
            selected_lines = lines[start_idx:end_idx]
            
            # 添加行号
            content = ""
            for i, line in enumerate(selected_lines, start=offset):
                content += f"{i}: {line}"
            
            # 检查是否有截断
            has_more = end_idx < total_lines
            
            return {
                "success": True,
                "content": content,
                "total_lines": total_lines,
                "start_line": offset,
                "end_line": end_idx,
                "has_more": has_more,
                "file_size": path.stat().st_size,
                "encoding": encoding
            }
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None
            }
    
    async def write_file(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """
        写入文件内容（自动创建目录）
        
        Args:
            file_path: 文件路径
            content: 文件内容
            encoding: 文件编码
            
        Returns:
            写入结果
        """
        if not self.session_id:
            return {
                "success": False,
                "error": "No active session",
                "operation_id": None
            }
        
        path = Path(file_path)
        
        try:
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.CREATE,
                destination_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 定义实际写入操作
            def do_write():
                with open(path, 'w', encoding=encoding) as f:
                    f.write(content)
                return True
            
            # 安全执行
            success = self.safety.execute_with_safety(
                operation_id=operation_id,
                operation_func=do_write
            )
            
            if success:
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "file_path": str(path),
                    "bytes_written": len(content.encode(encoding))
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to write file",
                    "operation_id": operation_id
                }
                
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": None
            }
    
    async def list_directory(
        self,
        dir_path: str,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        列出目录内容
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归列出
            
        Returns:
            目录内容列表
        """
        path = Path(dir_path)
        
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Directory not found: {dir_path}",
                    "entries": []
                }
            
            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"Not a directory: {dir_path}",
                    "entries": []
                }
            
            entries = []
            
            if recursive:
                for item in path.rglob("*"):
                    relative_path = item.relative_to(path)
                    entries.append({
                        "name": item.name,
                        "path": str(relative_path),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None
                    })
            else:
                for item in path.iterdir():
                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None
                    })
            
            # 排序：目录在前，文件在后，按名称排序
            entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
            return {
                "success": True,
                "entries": entries,
                "total_count": len(entries),
                "directory": str(path)
            }
            
        except Exception as e:
            logger.error(f"Failed to list directory {dir_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "entries": []
            }
    
    async def delete_file(
        self,
        file_path: str,
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        删除文件或目录（带回收站备份）
        
        Args:
            file_path: 文件/目录路径
            recursive: 是否递归删除目录
            
        Returns:
            删除结果
        """
        if not self.session_id:
            return {
                "success": False,
                "error": "No active session",
                "operation_id": None
            }
        
        path = Path(file_path)
        
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "operation_id": None
                }
            
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.DELETE,
                source_path=path,
                sequence_number=self._get_next_sequence()
            )
            
            # 定义删除操作
            def do_delete():
                if path.is_dir():
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        path.rmdir()
                else:
                    path.unlink()
                return True
            
            # 安全执行（会自动备份到回收站）
            success = self.safety.execute_with_safety(
                operation_id=operation_id,
                operation_func=do_delete
            )
            
            if success:
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "deleted_path": str(path),
                    "message": "File deleted (backup in recycle bin)"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to delete file",
                    "operation_id": operation_id
                }
                
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": None
            }
    
    async def move_file(
        self,
        source_path: str,
        destination_path: str
    ) -> Dict[str, Any]:
        """
        移动/重命名文件（带映射记录）
        
        Args:
            source_path: 源路径
            destination_path: 目标路径
            
        Returns:
            移动结果
        """
        if not self.session_id:
            return {
                "success": False,
                "error": "No active session",
                "operation_id": None
            }
        
        src = Path(source_path)
        dst = Path(destination_path)
        
        try:
            if not src.exists():
                return {
                    "success": False,
                    "error": f"Source not found: {source_path}",
                    "operation_id": None
                }
            
            # 记录操作
            operation_id = self.safety.record_operation(
                session_id=self.session_id,
                operation_type=OperationType.MOVE,
                source_path=src,
                destination_path=dst,
                sequence_number=self._get_next_sequence()
            )
            
            # 确保目标目录存在
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # 定义移动操作
            def do_move():
                shutil.move(str(src), str(dst))
                return True
            
            # 安全执行
            success = self.safety.execute_with_safety(
                operation_id=operation_id,
                operation_func=do_move
            )
            
            if success:
                return {
                    "success": True,
                    "operation_id": operation_id,
                    "source": str(src),
                    "destination": str(dst),
                    "message": f"Moved: {src.name} -> {dst}"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to move file",
                    "operation_id": operation_id
                }
                
        except Exception as e:
            logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "operation_id": None
            }
    
    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        use_regex: bool = False
    ) -> Dict[str, Any]:
        """
        搜索文件内容
        
        Args:
            pattern: 搜索内容
            path: 搜索路径
            file_pattern: 文件匹配模式
            use_regex: 是否使用正则表达式
            
        Returns:
            搜索结果
        """
        search_path = Path(path)
        results = []
        
        try:
            if not search_path.exists():
                return {
                    "success": False,
                    "error": f"Path not found: {path}",
                    "matches": []
                }
            
            # 编译正则表达式
            if use_regex:
                try:
                    regex = re.compile(pattern)
                except re.error as e:
                    return {
                        "success": False,
                        "error": f"Invalid regex pattern: {e}",
                        "matches": []
                    }
            
            # 搜索文件
            files_to_search = list(search_path.rglob(file_pattern))
            
            for file_path in files_to_search:
                if not file_path.is_file():
                    continue
                
                # 跳过二进制文件
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except:
                    continue
                
                matches = []
                
                if use_regex:
                    for match in regex.finditer(content):
                        # 获取上下文
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end]
                        
                        matches.append({
                            "start": match.start(),
                            "end": match.end(),
                            "matched": match.group(),
                            "context": context
                        })
                else:
                    # 简单字符串搜索
                    idx = content.find(pattern)
                    while idx != -1:
                        start = max(0, idx - 50)
                        end = min(len(content), idx + len(pattern) + 50)
                        context = content[start:end]
                        
                        matches.append({
                            "start": idx,
                            "end": idx + len(pattern),
                            "matched": pattern,
                            "context": context
                        })
                        
                        idx = content.find(pattern, idx + 1)
                
                if matches:
                    results.append({
                        "file": str(file_path.relative_to(search_path)),
                        "matches": matches,
                        "match_count": len(matches)
                    })
            
            # 按匹配数排序
            results.sort(key=lambda x: x["match_count"], reverse=True)
            
            return {
                "success": True,
                "pattern": pattern,
                "path": str(search_path),
                "files_searched": len(files_to_search),
                "files_matched": len(results),
                "total_matches": sum(r["match_count"] for r in results),
                "matches": results[:50]  # 限制结果数量
            }
            
        except Exception as e:
            logger.error(f"Failed to search files: {e}")
            return {
                "success": False,
                "error": str(e),
                "matches": []
            }
    
    async def generate_report(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        生成操作报告
        
        Args:
            output_dir: 报告输出目录
            
        Returns:
            报告生成结果
        """
        if not self.session_id:
            return {
                "success": False,
                "error": "No active session",
                "reports": {}
            }
        
        try:
            output_path = Path(output_dir) if output_dir else None
            reports = self.visualizer.generate_all_reports(self.session_id, output_path)
            
            # 转换为字符串路径
            report_paths = {k: str(v) for k, v in reports.items()}
            
            return {
                "success": True,
                "session_id": self.session_id,
                "reports": report_paths
            }
            
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return {
                "success": False,
                "error": str(e),
                "reports": {}
            }


# 工具函数导出
def get_file_tools(session_id: Optional[str] = None) -> FileTools:
    """获取文件工具实例"""
    return FileTools(session_id)
