"""
Prompt 日志记录器 - 记录 Prompt 组装全过程

【功能】记录每次请求的 prompt 组装过程，便于调试和分析
【存放】backend/logs/prompt-logs/ 目录下，每次请求一个 JSON 文件
【格式】JSON 文件，可用文本编辑器查看

创建时间: 2026-03-24 18:30:00
作者: 小沈
版本: v1.1
更新说明: v1.1 小健 - 修复并发安全问题，使用线程局部存储
"""

import json
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.utils.logger import logger


class PromptLogger:
    """Prompt 日志记录器 - 记录每次请求的 prompt 组装过程
    
    【并发安全】使用线程局部存储，每个线程/请求独立的日志数据
    """
    
    def __init__(self):
        """初始化日志目录"""
        # 日志目录：backend/logs/prompt-logs/
        self.log_dir = Path(__file__).parent.parent.parent / "logs" / "prompt-logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 线程局部存储 - 每个线程独立的日志数据
        self._local = threading.local()
    
    def _get_current_log(self) -> Optional[Dict[str, Any]]:
        """获取当前线程的日志数据"""
        return getattr(self._local, 'current_log', None)
    
    def _set_current_log(self, log_data: Optional[Dict[str, Any]]):
        """设置当前线程的日志数据"""
        self._local.current_log = log_data
    
    def _get_log_file_path(self) -> Optional[Path]:
        """获取当前线程的日志文件路径"""
        return getattr(self._local, 'log_file_path', None)
    
    def _set_log_file_path(self, path: Optional[Path]):
        """设置当前线程的日志文件路径"""
        self._local.log_file_path = path
    
    def start_request(
        self,
        user_message: str,
        user_message_id: str,
        session_id: str,
        ai_message_id: Optional[str] = None
    ) -> str:
        """
        开始记录一次请求
        
        Args:
            user_message: 用户消息内容
            user_message_id: 用户消息ID
            session_id: 会话ID
            ai_message_id: AI消息ID（可选，后续更新）
        
        Returns:
            日志文件路径
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成唯一文件名：prompt_时间戳_随机ID.json
        unique_id = str(uuid.uuid4())[:8]
        filename = f"prompt_{file_timestamp}_{unique_id}.json"
        log_file_path = self.log_dir / filename
        
        # 初始化日志数据
        current_log = {
            "基本信息": {
                "时间戳": timestamp,
                "会话ID": session_id,
                "用户消息ID": user_message_id,
                "AI消息ID": ai_message_id or "待生成",
                "用户消息": user_message,
                "日志文件": str(log_file_path)
            },
            "Prompt组装过程": [],
            "LLM调用记录": []
        }
        
        # 保存到线程局部存储
        self._set_current_log(current_log)
        self._set_log_file_path(log_file_path)
        
        logger.info(f"[PromptLogger] 开始记录请求: {log_file_path}")
        return str(log_file_path)
    
    def update_ai_message_id(self, ai_message_id: str):
        """更新 AI 消息 ID"""
        current_log = self._get_current_log()
        if current_log:
            current_log["基本信息"]["AI消息ID"] = ai_message_id
    
    def log_system_prompt(
        self,
        step_name: str,
        prompt_content: str,
        source: str = "",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        记录系统 Prompt 生成过程
        
        Args:
            step_name: 步骤名称（如：系统Prompt生成、中间层注入）
            prompt_content: Prompt 内容
            source: 来源说明（如：system_adapter.py）
            details: 额外详情
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": step_name,
            "类型": "系统Prompt",
            "来源": source,
            "内容": prompt_content,
            "内容长度": len(prompt_content),
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if details:
            entry["详情"] = details
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_task_prompt(
        self,
        task_content: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录任务 Prompt
        
        Args:
            task_content: 任务 Prompt 内容
            context: 额外上下文
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": "任务Prompt生成",
            "类型": "任务Prompt",
            "来源": "file_prompts.py:get_task_prompt()",
            "内容": task_content,
            "内容长度": len(task_content),
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if context:
            entry["上下文"] = context
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_llm_call(
        self,
        round_number: int,
        messages: List[Dict[str, str]],
        model: str,
        provider: str,
        call_type: str = "text",
        extra_params: Optional[Dict[str, Any]] = None
    ):
        """
        记录 LLM 调用
        
        Args:
            round_number: 调用轮次
            messages: 发送给 LLM 的完整消息列表
            model: 模型名称
            provider: 提供商
            call_type: 调用类型（text/tools/response_format）
            extra_params: 额外参数
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        # 计算消息统计
        message_stats = {}
        for msg in messages:
            role = msg.get("role", "unknown")
            message_stats[role] = message_stats.get(role, 0) + 1
        
        # 只记录消息摘要，避免内存问题
        message_summaries = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            message_summaries.append({
                "序号": i + 1,
                "角色": role,
                "内容长度": len(content),
                "内容摘要": content[:200] + "..." if len(content) > 200 else content
            })
        
        entry = {
            "轮次": round_number,
            "调用类型": call_type,
            "模型": model,
            "提供商": provider,
            "消息统计": message_stats,
            "消息总数": len(messages),
            "消息摘要": message_summaries,
            "完整消息列表": messages,  # 保留完整列表用于调试
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if extra_params:
            entry["额外参数"] = extra_params
        
        current_log["LLM调用记录"].append(entry)
    
    def log_llm_response(
        self,
        round_number: int,
        response_content: str,
        response_type: str = "text",
        finish_reason: str = "",
        extra_info: Optional[Dict[str, Any]] = None
    ):
        """
        记录 LLM 返回结果
        
        Args:
            round_number: 调用轮次
            response_content: LLM返回的内容
            response_type: 返回类型（text/tools/thought/action_tool等）
            finish_reason: 结束原因
            extra_info: 额外信息
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "轮次": round_number,
            "类型": "LLM返回",
            "返回类型": response_type,
            "内容": response_content[:500] if response_content else "",  # 截断避免日志过大
            "内容长度": len(response_content) if response_content else 0,
            "结束原因": finish_reason,
        }
        
        if extra_info:
            entry["额外信息"] = extra_info
        
        # 查找对应的LLM调用记录，更新其返回信息
        for call_entry in reversed(current_log.get("LLM调用记录", [])):
            if call_entry.get("轮次") == round_number:
                call_entry["返回内容"] = response_content[:1000] if response_content else ""
                call_entry["返回类型"] = response_type
                call_entry["结束原因"] = finish_reason
                break
        
        current_log["LLM调用记录"].append(entry)
    
    def log_observation(
        self,
        step_name: str,
        observation_content: str,
        tool_name: str = "",
        tool_params: Optional[Dict[str, Any]] = None
    ):
        """
        记录观察结果 Prompt
        
        Args:
            step_name: 步骤名称
            observation_content: 观察结果内容
            tool_name: 工具名称
            tool_params: 工具参数
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": step_name,
            "类型": "观察结果Prompt",
            "来源": f"工具执行结果: {tool_name}" if tool_name else "工具执行结果",
            "内容": observation_content,
            "内容长度": len(observation_content),
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if tool_params:
            entry["工具参数"] = tool_params
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_tool_prompt(
        self,
        tool_name: str,
        prompt_content: str,
        source: str = ""
    ):
        """
        记录工具相关的 Prompt
        
        Args:
            tool_name: 工具名称
            prompt_content: Prompt 内容
            source: 来源说明
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": f"工具Prompt: {tool_name}",
            "类型": "工具Prompt",
            "来源": source or f"工具: {tool_name}",
            "内容": prompt_content,
            "内容长度": len(prompt_content),
            "时间戳": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        current_log["Prompt组装过程"].append(entry)
    
    def save(self):
        """保存日志到文件"""
        current_log = self._get_current_log()
        log_file_path = self._get_log_file_path()
        
        if not current_log or not log_file_path:
            logger.warning("[PromptLogger] 保存失败：没有当前日志数据")
            return
        
        try:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(current_log, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[PromptLogger] 日志已保存: {log_file_path}")
        except Exception as e:
            logger.error(f"[PromptLogger] 保存失败: {e}")
    
    def get_current_log(self) -> Optional[Dict[str, Any]]:
        """获取当前日志数据"""
        return self._get_current_log()


# 全局实例
_prompt_logger = PromptLogger()


def get_prompt_logger() -> PromptLogger:
    """获取全局 PromptLogger 实例"""
    return _prompt_logger
