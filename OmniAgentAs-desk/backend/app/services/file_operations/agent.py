"""
ReAct Agent实现 (ReAct Agent Implementation)
实现Thought-Action-Observation循环的文件操作智能体
"""
import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.services.file_operations.tools import FileTools
from app.services.file_operations.prompts import FileOperationPrompts
from app.services.file_operations.session import get_session_service
from app.utils.logger import logger


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Step:
    """ReAct步骤"""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    message: str
    steps: List[Step]
    total_steps: int
    session_id: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ToolParser:
    """
    工具解析器
    
    解析LLM响应中的Thought-Action-ActionInput结构
    支持JSON格式和Markdown代码块格式
    """
    
    @staticmethod
    def parse_response(response: str) -> Dict[str, Any]:
        """
        解析LLM响应
        
        Args:
            response: LLM的原始响应文本
            
        Returns:
            解析后的字典，包含thought, action, action_input
            
        Raises:
            ValueError: 如果解析失败
        """
        # 首先尝试从JSON代码块中提取
        json_match = re.search(
            r'```(?:json)?\s*\n?(.*?)\n?```',
            response,
            re.DOTALL | re.IGNORECASE
        )
        
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # 尝试直接解析整个响应
            json_str = response.strip()
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            # 尝试从文本中提取结构
            parsed = ToolParser._extract_from_text(response)
            if not parsed:
                raise ValueError(f"Failed to parse response as JSON: {e}")
        
        # 验证必要字段
        if "thought" not in parsed:
            raise ValueError("Missing required field: 'thought'")
        
        if "action" not in parsed:
            raise ValueError("Missing required field: 'action'")
        
        if "action_input" not in parsed and "actionInput" not in parsed:
            # 如果没有action_input，尝试使用空字典
            parsed["action_input"] = {}
        elif "actionInput" in parsed:
            parsed["action_input"] = parsed.pop("actionInput")
        
        return {
            "thought": parsed["thought"],
            "action": parsed["action"],
            "action_input": parsed.get("action_input", {})
        }
    
    @staticmethod
    def _extract_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        从非结构化文本中提取关键信息
        
        用于处理LLM没有返回标准JSON格式的情况
        """
        result = {}
        
        # 尝试提取thought
        thought_patterns = [
            r'(?:thought|thinking|reasoning)["\']?\s*[:=]\s*["\']?(.*?)(?:["\']?\s*[,}\n]|action)',
            r'(?:I think|I need to|Let me|First,?|Next,?)\s*(.*?)(?:\n\n|\n[A-Z]|$)',
        ]
        
        for pattern in thought_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["thought"] = match.group(1).strip()
                break
        
        # 尝试提取action
        action_patterns = [
            r'(?:action)["\']?\s*[:=]\s*["\']?(\w+)["\']?',
            r'(?:use|call|execute)\s+(?:the\s+)?(\w+)\s+(?:tool|function)?',
        ]
        
        for pattern in action_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["action"] = match.group(1).strip().lower()
                break
        
        # 尝试提取action_input
        input_patterns = [
            r'(?:action_input|actionInput|input|parameters)["\']?\s*[:=]\s*({.*?})',
            r'(?:with|using)\s+parameters?\s*:?\s*({.*?})',
        ]
        
        for pattern in input_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    result["action_input"] = json.loads(match.group(1))
                except json.JSONDecodeError:
                    result["action_input"] = {}
                break
        
        if "action_input" not in result:
            result["action_input"] = {}
        
        # 只有在至少有thought和action时才返回
        if "thought" in result and "action" in result:
            return result
        
        return None


class ToolExecutor:
    """
    工具执行器
    
    负责执行解析后的工具调用，处理错误和结果格式化
    """
    
    def __init__(self, file_tools: FileTools):
        self.file_tools = file_tools
        self.available_tools = {
            "read_file": self.file_tools.read_file,
            "write_file": self.file_tools.write_file,
            "list_directory": self.file_tools.list_directory,
            "delete_file": self.file_tools.delete_file,
            "move_file": self.file_tools.move_file,
            "search_files": self.file_tools.search_files,
            "generate_report": self.file_tools.generate_report,
        }
    
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
        # 检查是否是特殊动作
        if action == "finish":
            return {
                "success": True,
                "result": {
                    "operation_type": "finish",
                    "message": action_input.get("result", "Task completed"),
                    "data": action_input
                }
            }
        
        # 检查工具是否可用
        if action not in self.available_tools:
            return {
                "success": False,
                "error": f"Unknown tool: {action}. Available tools: {list(self.available_tools.keys())}",
                "result": None
            }
        
        tool = self.available_tools[action]
        
        try:
            # 执行工具
            result = await tool(**action_input)
            
            # 格式化结果
            if isinstance(result, dict):
                if result.get("success", False):
                    return {
                        "success": True,
                        "result": result,
                        "message": result.get("message", f"Successfully executed {action}")
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", f"Failed to execute {action}"),
                        "result": result
                    }
            else:
                return {
                    "success": True,
                    "result": result,
                    "message": f"Successfully executed {action}"
                }
                
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "result": None
            }


class FileOperationAgent:
    """
    文件操作ReAct Agent
    
    实现完整的Thought-Action-Observation循环，
    管理文件操作会话和状态
    """
    
    def __init__(
        self,
        llm_client: Callable[..., Any],
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        session_id: Optional[str] = None
    ):
        """
        初始化Agent
        
        Args:
            llm_client: LLM客户端函数，接收message和history，返回response
            file_tools: 文件工具实例（可选，默认创建新实例）
            max_steps: 最大执行步数
            session_id: 会话ID（可选）
        """
        self.llm_client = llm_client
        self.max_steps = max_steps
        self.session_id = session_id
        
        # 初始化session服务（用于统一管理会话生命周期）
        self.session_service = get_session_service()
        
        # 【修复】标记session是否由本Agent创建（用于正确关闭）
        self._session_created_by_agent = False
        
        # 【修复】添加异步锁，确保并发安全
        self._lock = asyncio.Lock()
        
        # 初始化文件工具，确保session_id正确传递
        self.file_tools = file_tools or FileTools(session_id=session_id)
        
        self.parser = ToolParser()
        self.executor = ToolExecutor(self.file_tools)
        self.prompts = FileOperationPrompts()
        
        self.steps: List[Step] = []
        self.status = AgentStatus.IDLE
        self.conversation_history: List[Dict[str, str]] = []
        
        logger.info(f"FileOperationAgent initialized (session: {session_id})")
    
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        运行Agent完成任务
        
        【修复】使用锁保护确保并发安全
        【修复】每次run独立管理状态和session
        
        Args:
            task: 任务描述
            context: 额外上下文
            system_prompt: 自定义系统prompt（可选）
            
        Returns:
            Agent执行结果
        """
        # 【修复】使用锁确保同一时间只有一个run执行（并发安全）
        async with self._lock:
            return await self._run_internal(task, context, system_prompt)
    
    async def _run_internal(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        内部运行方法（已被锁保护）
        """
        # 【修复】重置状态，避免多次调用导致的状态污染
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        
        # 【修复】使用局部变量管理session，避免并发问题
        session_id = self.session_id
        session_created_by_this_run = False
        
        # 【修复】确保session已创建（统一管理会话生命周期）
        if not session_id:
            session_id = self.session_service.create_session(
                agent_id="file-operation-agent",
                task_description=task
            )
            session_created_by_this_run = True
            self._session_created_by_agent = True
            
            # 【修复】安全地更新FileTools的session_id
            if hasattr(self.file_tools, 'set_session'):
                self.file_tools.set_session(session_id)
            logger.info(f"Session created in run(): {session_id}")
        
        # 构建初始prompt
        sys_prompt = system_prompt or self.prompts.get_system_prompt()
        task_prompt = self.prompts.get_task_prompt(task, context)
        
        # 添加到对话历史
        self.conversation_history.append({"role": "system", "content": sys_prompt})
        self.conversation_history.append({"role": "user", "content": task_prompt})
        
        current_step = 0
        result = None
        
        try:
            while current_step < self.max_steps:
                current_step += 1
                
                # 1. Thought - 获取LLM响应
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                # 2. Action - 解析响应
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    # 添加错误观察，让LLM重试
                    self._add_observation_to_history(
                        f"Parse error: {e}. Please respond with valid JSON format."
                    )
                    continue
                
                # 创建步骤记录
                step = Step(
                    step_number=current_step,
                    thought=parsed["thought"],
                    action=parsed["action"],
                    action_input=parsed["action_input"]
                )
                
                logger.info(
                    f"Step {current_step}: {parsed['action']} - {parsed['thought'][:50]}..."
                )
                
                # 3. 检查是否完成
                if parsed["action"] == "finish":
                    step.observation = {
                        "success": True,
                        "result": parsed["action_input"]
                    }
                    self.steps.append(step)
                    self.status = AgentStatus.COMPLETED
                    
                    result = AgentResult(
                        success=True,
                        message="Task completed successfully",
                        steps=self.steps,
                        total_steps=current_step,
                        session_id=session_id,
                        final_result=parsed["action_input"]
                    )
                    return result
                
                # 4. Observation - 执行动作
                self.status = AgentStatus.EXECUTING
                observation = await self.executor.execute(
                    parsed["action"],
                    parsed["action_input"]
                )
                
                step.observation = observation
                self.steps.append(step)
                
                # 5. 添加观察结果到对话历史
                obs_text = self._format_observation(observation)
                self._add_observation_to_history(obs_text)
                
                self.status = AgentStatus.OBSERVING
            
            # 超过最大步数
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Exceeded maximum steps ({self.max_steps})",
                steps=self.steps,
                total_steps=current_step,
                session_id=session_id,
                error="Maximum steps exceeded"
            )
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                steps=self.steps,
                total_steps=current_step,
                session_id=session_id,
                error=str(e)
            )
            return result
            
        finally:
            # 【修复】只关闭由本次run创建的session
            if session_created_by_this_run and session_id and self.session_service:
                try:
                    success = result.success if result else False
                    self.session_service.complete_session(session_id, success=success)
                    logger.info(f"Session completed: {session_id} (success={success})")
                    # 重置标记
                    self._session_created_by_agent = False
                    self.session_id = None
                except Exception as e:
                    logger.error(f"Failed to complete session {session_id}: {e}")
    
    async def _get_llm_response(self) -> str:
        """获取LLM响应"""
        try:
            # 最后一条消息作为当前消息
            last_message = self.conversation_history[-1]["content"]
            # 前面的消息作为历史
            history_dicts = self.conversation_history[:-1]
            
            # 【修复】使用adapter将Dict列表转换为Message列表
            from app.services.file_operations.adapter import dict_list_to_messages
            history_messages = dict_list_to_messages(history_dicts)
            
            response = await self.llm_client(
                message=last_message,
                history=history_messages
            )
            
            # 添加到历史
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get("content", str(response))
            else:
                content = str(response)
            
            self.conversation_history.append({"role": "assistant", "content": content})
            return content
            
        except Exception as e:
            logger.error(f"LLM client error: {e}")
            raise
    
    def _add_observation_to_history(self, observation: str):
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
    
    def _format_observation(self, observation: Dict[str, Any]) -> str:
        """格式化观察结果为文本"""
        if observation.get("success", False):
            result = observation.get("result", {})
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        else:
            error = observation.get("error", "Unknown error")
            return f"Error: {error}"
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return [step.to_dict() for step in self.steps]
    
    async def rollback(self, step_number: Optional[int] = None) -> bool:
        """
        回滚操作
        
        Args:
            step_number: 要回滚到的步骤号（None表示回滚所有）
            
        Returns:
            是否成功
        """
        try:
            if not self.session_id:
                raise ValueError("Session ID is required for rollback")
            
            if step_number is None:
                # 回滚整个会话
                result = self.file_tools.safety.rollback_session(self.session_id)
                success = result.get("success", 0) > 0
            else:
                # 找到对应步骤的操作ID
                for step in self.steps:
                    if step.step_number == step_number:
                        # 这里需要从observation中提取operation_id
                        # 实际实现需要调整FileTools返回operation_id
                        observation = step.observation or {}
                        result_data = observation.get("result", {}) if isinstance(observation, dict) else {}
                        operation_id = result_data.get("operation_id")
                        if operation_id:
                            success = self.file_tools.safety.rollback_operation(operation_id)
                        else:
                            raise ValueError(f"No operation_id found for step {step_number}")
                        break
                else:
                    raise ValueError(f"Step {step_number} not found")
            
            self.status = AgentStatus.ROLLED_BACK
            return success
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
