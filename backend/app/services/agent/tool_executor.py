# -*- coding: utf-8 -*-
"""
工具执行器模块

负责执行解析后的工具调用，处理错误和结果格式化
Author: 小沈 - 2026-03-21
"""

from typing import Any, Callable, Dict

from app.utils.logger import logger


class ToolExecutor:
    """
    工具执行器
    
    负责执行解析后的工具调用，处理错误和结果格式化
    """
    
    def __init__(self, tools: Dict[str, Callable]):
        """
        初始化工具执行器
        
        Args:
            tools: 工具名称到工具函数的映射字典
        """
        self.available_tools = tools
    
    async def execute(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具调用
        
        Args:
            action: 工具名称
            action_input: 工具参数
        
        Returns:
            执行结果，包含success标志和结果数据
        """
        if action == "finish":
            return {
                "success": True,
                "result": {
                    "operation_type": "finish",
                    "message": action_input.get("result", "Task completed"),
                    "data": action_input
                }
            }
        
        if action not in self.available_tools:
            return {
                "success": False,
                "error": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                "result": None
            }
        
        tool = self.available_tools[action]
        
        try:
            normalized_input = self._normalize_params(action, action_input)
            result = await tool(**normalized_input)
            
            return self._format_result(result, action)
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {
                "status": "error",
                "summary": f"Execution error: {str(e)}",
                "data": None,
                "retry_count": 0
            }
    
    def _normalize_params(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        参数规范化：处理不同参数名
        
        Args:
            action: 工具名称
            action_input: 原始参数
        
        Returns:
            规范化后的参数
        """
        params = action_input.copy()
        
        if action in ["read_file", "write_file", "delete_file"]:
            if "path" in params and "file_path" not in params:
                params["file_path"] = params.pop("path")
            elif "path" in params and "file_path" in params:
                del params["path"]
        
        elif action == "list_directory":
            if "path" in params and "dir_path" not in params:
                params["dir_path"] = params.pop("path")
            elif "path" in params and "dir_path" in params:
                del params["path"]
        
        elif action == "move_file":
            if "source" in params and "source_path" not in params:
                params["source_path"] = params.pop("source")
            if "src" in params and "source_path" not in params:
                params["source_path"] = params.pop("src")
            
            if "destination" in params and "destination_path" not in params:
                params["destination_path"] = params.pop("destination")
            if "dest" in params and "destination_path" not in params:
                params["destination_path"] = params.pop("dest")
            if "target" in params and "destination_path" not in params:
                params["destination_path"] = params.pop("target")
        
        elif action == "search_files":
            if "path" not in params:
                params["path"] = "."
        
        elif action == "generate_report":
            if "output" in params and "output_dir" not in params:
                params["output_dir"] = params.pop("output")
        
        return params
    
    def _format_result(self, result: Any, action: str) -> Dict[str, Any]:
        """
        格式化工具执行结果
        
        Args:
            result: 原始执行结果
            action: 工具名称
        
        Returns:
            格式化后的结果
        """
        if isinstance(result, dict):
            if "status" in result and "summary" in result:
                return {
                    "status": result.get("status", "success"),
                    "summary": result.get("summary", ""),
                    "data": result.get("data"),
                    "retry_count": result.get("retry_count", 0)
                }
            elif result.get("success", False):
                return {
                    "status": "success",
                    "summary": result.get("message", f"Successfully executed {action}"),
                    "data": result,
                    "retry_count": 0
                }
            else:
                return {
                    "status": "error",
                    "summary": result.get("error", f"Failed to execute {action}"),
                    "data": result,
                    "retry_count": 0
                }
        else:
            return {
                "status": "success",
                "summary": f"Successfully executed {action}",
                "data": result,
                "retry_count": 0
            }