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
            # 【修复 2026-04-01 小沈】统一返回格式
            # 之前：返回success字段，与普通工具返回的status字段不一致
            # 修复：改为返回status字段，与_format_result保持一致
            # 影响：base_react.py第226行execution_result.get("status", "success")能正确获取
            return {
                "status": "success",
                "summary": "Task completed",
                "result": {
                    "operation_type": "finish",
                    "message": action_input.get("result", "Task completed"),
                    "data": action_input
                },
                "data": action_input.get("result"),
                "retry_count": 0
            }
        
        if action not in self.available_tools:
            return {
                "status": "error",
                "summary": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                "data": None,
                "retry_count": 0
            }
        
        tool = self.available_tools[action]
        
        try:
            normalized_input = self._normalize_params(action, action_input)
            
            # 【小沈修复 2026-04-13】验证必需参数
            import inspect
            sig = inspect.signature(tool)
            required_params = [
                p.name for p in sig.parameters.values()
                if p.default == inspect.Parameter.empty and p.name != 'self'
            ]
            missing = [p for p in required_params if p not in normalized_input]
            if missing:
                logger.warning(f"[参数验证] action={action} 缺少必需参数: {missing}")
                return {
                    "status": "error",
                    "summary": f"Missing required parameter(s): {', '.join(missing)}",
                    "data": None,
                    "retry_count": 0
                }
            
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
        
        【2026-03-24 小沈修改】
        采用方案3：删除参数映射代码，添加日志监控
        如果LLM返回非标准参数名，记录日志但不自动转换
        根据日志数据分析是否可以完全删除此逻辑
        
        Args:
            action: 工具名称
            action_input: 原始参数
        
        Returns:
            规范化后的参数
        """
        params = action_input.copy()
        
        # 定义每个工具的标准参数名
        STANDARD_PARAMS = {
            "read_file": ["file_path", "offset", "limit", "encoding"],
            "write_file": ["file_path", "content", "encoding"],
            "delete_file": ["file_path", "recursive"],
            "list_directory": ["dir_path", "recursive", "max_depth"],
            "move_file": ["source_path", "destination_path"],
            # 【修复 2026-04-11】用 page_token 替换 after（与 file_tools.py 第1164行保持一致）
            # 【修复 2026-04-11】移除 max_results（已删除，与 file_tools.py 保持一致）
            "search_files": ["file_pattern", "path", "recursive", "max_depth", "page_token"],
            "search_file_content": ["pattern", "path", "file_pattern", "recursive"],
            "generate_report": ["output_dir"],
        }
        
        # 检查是否有非标准参数名
        if action in STANDARD_PARAMS:
            standard = STANDARD_PARAMS[action]
            for key in list(params.keys()):
                if key not in standard:
                    # 参数值截断，避免日志过长
                    val = params[key]
                    val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                    logger.warning(
                        f"[参数监控] LLM返回非标准参数名: action={action}, "
                        f"param={key}={val_str}, 期望参数={standard}"
                    )
        
        # 参数由LLM返回，tool_executor不做默认设置
        
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