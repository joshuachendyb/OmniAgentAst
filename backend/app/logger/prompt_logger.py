"""
Prompt 日志记录器 - 记录 Prompt 组装全过程

【功能】记录每次请求的 prompt 组装过程,便于调试和分析
【存放】backend/logs/prompt-logs/ 目录下,每次请求一个 JSON 文件
【格式】JSON 文件,可用文本编辑器查看

创建时间: 2026-03-24 18:30:00
作者: 小沈
版本: v1.1
更新说明: v1.1 小健 - 修复并发安全问题,使用线程局部存储
"""

import json
import contextvars
from app.utils.time_utils import now_str, timestamp_for_filename
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.utils.json_utils import safe_json_dumps
from app.services.chat.storage import get_user_message_id
from app.db import db
from app.utils.logger import logger


class PromptLogger:
    """Prompt 日志记录器 - 记录每次请求的 prompt 组装过程
    
    【并发安全】使用 contextvars,每个协程/请求独立的日志数据
    """
    
    def __init__(self):
        """初始化日志目录"""
        # 日志目录:backend/logs/prompt-logs/
        self.log_dir = Path(__file__).parent.parent.parent.parent / "logs" / "prompt-logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # contextvars - 每个协程独立的日志数据,避免 asyncio 协程间覆盖
        self._current_log: contextvars.ContextVar = contextvars.ContextVar('prompt_log', default=None)
    
    def _get_current_log(self) -> Optional[Dict[str, Any]]:
        """获取当前协程的日志数据"""
        return self._current_log.get()
    
    def _set_current_log(self, log_data: Optional[Dict[str, Any]]):
        """设置当前协程的日志数据"""
        self._current_log.set(log_data)
    
    def start_request(
        self,
        user_message: str,
        session_id: str,
    ) -> str:
        """
        开始记录一次请求 — AI消息ID由update_ai_message_id()设置
        
        Args:
            user_message: 用户消息内容
            session_id: 会话ID
        
        Returns:
            会话ID(用于标识本次请求)
        """
        timestamp = now_str()
        
        # 延迟导入: 避免循环导入
        user_message_id = get_user_message_id(session_id)
        if user_message_id is None:
            user_message_id = self._user_id_from_db(session_id)
        
        # 初始化日志数据 — AI消息ID由update_ai_message_id()设置,文件名在save()时生成
        current_log = {
            "基本信息": {
                "时间戳": timestamp,
                "会话ID": session_id,
                "用户消息ID": user_message_id,
                "AI消息ID": None,
                "用户消息": user_message,
                "状态": "处理中",
            },
            "Prompt组装过程": [],
            "LLM调用记录": []
        }
        
        # 保存到线程局部存储
        self._set_current_log(current_log)
        
        logger.info(f"[PromptLogger] 开始记录请求: session_id={session_id}")
        return session_id
    
    def _user_id_from_db(self, sid: str) -> Optional[int]:
        """P1修复: 改用db.get_conn() SDK+修复裸except"""
        try:
            with db.get_conn("chat") as conn:
                row = conn.execute(
                    "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                    (sid,)
                ).fetchone()
                return row[0] if row else None
        except Exception:
            return None


    def update_ai_message_id(self, ai_message_id: str):
        """拿到真实ai_message_id后更新日志数据 — 小欧 2026-06-23"""
        current_log = self._get_current_log()
        if not current_log:
            return
        current_log["基本信息"]["AI消息ID"] = ai_message_id

    def log_system_prompt(
        self,
        step_name: str,
        prompt_content: str,
        source: str = "",
        details: Optional[Dict[str, Any]] = None,
        round_number: int = 0
    ):
        """
        记录系统 Prompt 生成过程
        
        Args:
            step_name: 步骤名称(如:系统Prompt生成、中间层注入)
            prompt_content: Prompt 内容
            source: 来源说明(如:system_adapter.py)
            details: 额外详情
            round_number: LLM调用轮次 【2026-05-15 小健】
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
            "时间戳": now_str()
        }
        if round_number > 0:
            entry["轮次"] = round_number
        
        if details:
            entry["详情"] = details
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_task_prompt(
        self,
        task_content: str,
        context: Optional[Dict[str, Any]] = None,
        round_number: int = 0,
        source: str = "",
    ):
        """
        记录任务 Prompt
        
        Args:
            task_content: 任务 Prompt 内容
            context: 额外上下文
            round_number: LLM调用轮次 【2026-05-15 小健】
            source: 来源说明
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": "任务Prompt生成",
            "类型": "任务Prompt",
            "来源": source or "unknown",
            "内容": task_content,
            "内容长度": len(task_content),
            "时间戳": now_str()
        }
        if round_number > 0:
            entry["轮次"] = round_number
        
        if context:
            entry["上下文"] = context
        
        current_log["Prompt组装过程"].append(entry)
    
    def _summarize_messages(self, messages):
        """消息统计和摘要提取 — 小欧 2026-07-10 M-43"""
        message_stats = {}
        if not messages:
            messages = []
        for msg in messages:
            role = msg.get("role", "unknown")
            message_stats[role] = message_stats.get(role, 0) + 1
        message_summaries = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            raw = msg.get("content")
            content = str(raw) if raw is not None else ""
            summary = {
                "序号": i + 1,
                "角色": role,
                "内容长度": len(content),
                "内容摘要": content[:200] + "..." if len(content) > 200 else content
            }
            if role == "assistant" and msg.get("tool_calls"):
                tc_names = [tc.get("function", {}).get("name", "?") for tc in msg["tool_calls"]]
                summary["工具调用"] = tc_names
            message_summaries.append(summary)
        return message_stats, message_summaries

    def _summarize_tools(self, tools):
        """工具定义摘要提取 — 小欧 2026-07-10 M-43"""
        if not tools:
            return None
        tools_summary = []
        for t in tools:
            func = t.get("function", t)
            params = func.get("parameters", {})
            tool_info = {
                "名称": func.get("name", ""),
                "工具描述": func.get("description", ""),
                "Schema描述": params.get("description"),
            }
            if params:
                props = params.get("properties", {})
                required = set(params.get("required", []) or [])
                param_list = []
                for pname, pinfo in props.items():
                    param_list.append({
                        "参数名": pname,
                        "类型": pinfo.get("type", "any"),
                        "必填": pname in required,
                        "描述": pinfo.get("description", ""),
                        "枚举": pinfo.get("enum") if "enum" in pinfo else None,
                        "默认值": pinfo.get("default") if "default" in pinfo else None,
                    })
                tool_info["参数列表"] = param_list
            tools_summary.append(tool_info)
        return tools_summary

    def log_llm_call(
        self,
        round_number: int = 0,
        messages: List[Dict[str, str]] = None,
        model: str = "",
        provider: str = "",
        call_type: str = "tools",
        extra_params: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ):
        """
        记录 LLM 调用
        
        Args:
            round_number: 调用轮次
            messages: 发送给 LLM 的完整消息列表
            model: 模型名称
            provider: 提供商
            call_type: 调用类型(text/tools/response_format)
            extra_params: 额外参数
            tools: OpenAI tools 定义数组(完整 JSON Schema),2026-06-19 小欧新增
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        message_stats, message_summaries = self._summarize_messages(messages)
        tools_summary = self._summarize_tools(tools)

        entry = {
            "轮次": round_number,
            "调用类型": call_type,
            "模型": model,
            "提供商": provider,
            "消息统计": message_stats,
            "消息总数": len(messages),
            "消息摘要": message_summaries,
            "工具数量": len(tools) if tools else 0,
            "工具定义": tools_summary,
            "时间戳": now_str()
        }
        
        if extra_params:
            # 已经用工具数量和工具定义替代了原来的 tool_count
            extra_params.pop("tool_count", None)
            if extra_params:
                entry["额外参数"] = extra_params
        
        current_log["LLM调用记录"].append(entry)
    
    def log_llm_response(
        self,
        round_number: int = 0,
        response_content: str = "",
        response_type: str = "text",
        finish_reason: str = "",
        extra_info: Optional[Dict[str, Any]] = None,
        raw_response: str = "",
    ):
        """
        记录 LLM 返回结果
        
        Args:
            round_number: 调用轮次
            response_content: LLM返回的内容(截断版,便于预览)
            response_type: 返回类型(text/tools/thought/action_tool等)
            finish_reason: 结束原因
            extra_info: 额外信息
            raw_response: 原始响应(完整不截断)
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        if not isinstance(response_content, str):
            response_content = str(response_content) if response_content is not None else ""
        if not isinstance(raw_response, str):
            raw_response = str(raw_response) if raw_response is not None else ""

        timestamp = now_str()
        entry = {
            "轮次": round_number,
            "返回类型": response_type,
            "原始响应时间": timestamp,
            "解析结果": response_content,
            "原始响应": raw_response,
            "结束原因": finish_reason,
        }

        if extra_info:
            entry["额外信息"] = extra_info

        # 查找已有条目更新（不重复追加）— 北京老陈 2026-06-14 — 小欧 2026-07-10 C-08 修复
        for call_entry in reversed(current_log.get("LLM调用记录", [])):
            if call_entry.get("轮次") == round_number:
                call_entry["解析结果"] = response_content
                call_entry["原始响应时间"] = timestamp
                call_entry["原始响应"] = raw_response
                call_entry["返回类型"] = response_type
                call_entry["结束原因"] = finish_reason
                break
        else:
            current_log["LLM调用记录"].append(entry)

    def log_step_yield(self, step_dict: dict, round_number: int = 0):
        """记录每一步 yield 给前端的 JSON 数据 — 北京老陈 2026-06-14 — 小欧 2026-06-24 删除chunk跳过，所有step类型都记录"""
        current_log = self._get_current_log()
        if not current_log:
            return
        if "步骤产出" not in current_log:
            current_log["步骤产出"] = []
        current_log["步骤产出"].append({
            "轮次": round_number,
            "步骤": step_dict.get("step", 0),
            "步骤类型": step_dict.get("type", ""),
            "数据": step_dict,
            "时间戳": now_str(),
        })

    def log_observation(
        self,
        step_name: str,
        observation_content: str,
        tool_name: str = "",
        tool_params: Optional[Dict[str, Any]] = None,
        round_number: int = 0,
        raw_data: Any = None,
    ):
        """
        记录观察结果 Prompt
        
        Args:
            step_name: 步骤名称
            observation_content: 观察结果内容
            tool_name: 工具名称
            tool_params: 工具参数
            round_number: LLM调用轮次 【2026-05-15 小健】
            raw_data: 格式化前的原始data内容 【2026-07-08 小沈】
        """
        current_log = self._get_current_log()
        if not current_log:
            return
        
        entry = {
            "步骤": step_name,
            "类型": "观察结果Prompt",
            "来源": f"工具执行结果: {tool_name}" if tool_name else "工具执行结果",
            "内容长度": len(observation_content),
            "时间戳": now_str(),
        }
        if round_number > 0:
            entry["轮次"] = round_number
        
        if tool_params:
            entry["工具参数"] = tool_params
        
        entry["格式化内容:"] = observation_content
        if raw_data is not None:
            entry["原始的内容:"] = raw_data
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_tool_prompt(
        self,
        tool_name: str,
        prompt_content: str,
        source: str = "",
        round_number: int = 0
    ):
        """
        记录工具相关的 Prompt
        
        Args:
            tool_name: 工具名称
            prompt_content: Prompt 内容
            source: 来源说明
            round_number: LLM调用轮次 【2026-05-15 小健】
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
            "时间戳": now_str()
        }
        if round_number > 0:
            entry["轮次"] = round_number
        
        current_log["Prompt组装过程"].append(entry)
    
    def log_status(self, old_status: str, new_status: str, reason: str = ""):
        """记录Agent状态变化到prompt log — 小欧 2026-07-01"""
        current_log = self._get_current_log()
        if not current_log:
            return
        if "状态变化记录" not in current_log:
            current_log["状态变化记录"] = []
        entry = {
            "时间": now_str(),
            "旧状态": str(old_status),
            "新状态": str(new_status),
        }
        if reason:
            entry["原因"] = reason
        current_log["状态变化记录"].append(entry)

    def mark_completed(self):
        """标记请求已完成 — 小欧 2026-06-30"""
        current_log = self._get_current_log()
        if current_log:
            current_log["基本信息"]["状态"] = "已完成"

    def mark_error(self, error_msg: str):
        """标记请求异常终止 — 小欧 2026-06-30"""
        current_log = self._get_current_log()
        if current_log:
            current_log["基本信息"]["状态"] = "异常终止"
            current_log["基本信息"]["错误信息"] = error_msg

    def save(self):
        """保存日志到文件 — 文件名用ai_message_id生成 — 小欧 2026-06-23"""
        current_log = self._get_current_log()
        if not current_log:
            logger.warning("[PromptLogger] 保存失败:没有当前日志数据")
            return

        status = current_log["基本信息"].get("状态", "处理中")
        if status == "处理中":
            if current_log.get("LLM调用记录"):
                current_log["基本信息"]["状态"] = "已完成"
            else:
                current_log["基本信息"]["状态"] = "异常终止"

        # 从日志数据中取ai_message_id,生成最终文件名
        ai_id = current_log["基本信息"].get("AI消息ID")
        if ai_id:
            short_id = str(ai_id)[-6:]
        else:
            user_id = current_log["基本信息"].get("用户消息ID")
            short_id = str(user_id)[-6:] if user_id else "no_id"
        
        file_timestamp = timestamp_for_filename()
        filename = f"prompt_{short_id}+{file_timestamp}.json"
        log_file_path = self.log_dir / filename
        
        for retry in range(2):
            try:
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.write(safe_json_dumps(current_log, ensure_ascii=False, indent=2))
                logger.info(f"[PromptLogger] 日志已保存: {log_file_path}")
                return
            except Exception as e:
                if retry == 0:
                    logger.warning(f"[PromptLogger] 保存失败,重试: {e}")
                else:
                    logger.error(f"[PromptLogger] 保存失败: {e}")
    
    def get_current_log(self) -> Optional[Dict[str, Any]]:
        """获取当前日志数据"""
        return self._get_current_log()


# 全局实例
_prompt_logger = PromptLogger()


def get_prompt_logger() -> PromptLogger:
    """获取全局 PromptLogger 实例"""
    return _prompt_logger
