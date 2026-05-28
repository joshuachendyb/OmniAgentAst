# -*- coding: utf-8 -*-
"""
ToolStepMixin — 工具步骤编排混入类 — 小健 2026-05-24

将工具执行的编排逻辑从 base_react.py 中分离，
base_react.py 只保留 ReAct 循环（思考→决策→继续/退出），
本mixin负责：
- _execute_tool_step: 执行单个工具，构建action_tool+observation步骤
- _resolve_fc_context: FC协议上下文解析
- _ToolStepOutcome: 工具步骤产出数据结构

设计原则（SRP + SLAP）：
- ReAct循环（base_react.py）决定"什么时候执行工具"
- ToolStepMixin决定"怎么执行一次工具并构建步骤"
- tool_executor.py决定"怎么调用工具函数+重试"

迁移自: base_react.py 中的 _execute_tool_step / _resolve_fc_context / _ToolStepOutcome
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.agent.reasoning_steps import StepFactory
from app.services.agent.tool_result_formatter import build_execution_result_dict
from app.services.agent.agent_utils.message_utils import build_observation_text
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger


@dataclass
class _ToolStepOutcome:
    """单次工具执行的完整产出 — 小健 2026-05-24

    由 _execute_tool_step() 返回，供调用方做后续处理
    （return_direct判断、动态工具加载、pending编排等）。

    Attributes:
        execution_result: 工具原始返回值（dict）
        execution_result_dict: 经 build_execution_result_dict 统一化后的dict
        execution_time_ms: 执行耗时（毫秒）
        observation_text: 构建好的observation文本
        is_done: 是否应直接结束任务（return_direct=True且为主工具时）
        action_step_dict: action_tool步骤的yield dict（已emit）
        observation_step_dict: observation步骤的yield dict（已emit，但add_observation未执行）
        obs_inject_text: 需要注入conversation_history的observation文本（含前缀）
        obs_fc_context: 需要传入add_observation的fc_context
    """
    execution_result: Dict[str, Any]
    execution_result_dict: Dict[str, Any]
    execution_time_ms: int
    observation_text: str
    is_done: bool
    action_step_dict: Dict[str, Any]
    observation_step_dict: Dict[str, Any]
    obs_inject_text: str
    obs_fc_context: Optional[Dict[str, Any]]


class ToolStepMixin:
    """工具步骤编排混入类 — 小健 2026-05-24

    供 BaseAgent 子类混入，提供 _execute_tool_step 和 _resolve_fc_context。
    依赖宿主类的以下属性/方法（由BaseAgent提供）：
    - self._execute_tool(action, params) — 抽象方法，子类实现
    - self.message_builder — MessageBuilder实例
    - self.steps — 步骤历史列表
    - self.llm_call_count — LLM调用计数
    - self.task_id — 任务ID
    - self._emit_step(step) — 步骤记录+转dict
    - self._strategy — LLM策略名（text/tools）
    - self._last_fc_raw_response — FC原始响应对象
    """

    def _resolve_fc_context(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """解析FC协议上下文 — 小健 2026-05-24

        统一主工具(tool_calls按name匹配)的FC上下文构建。
        仅在tools策略下有效，text策略返回None。

        使用场景:
            主工具: fc_context = self._resolve_fc_context(tool_name)
            Pending工具: 不调用（pending走role:system注入）

        Args:
            tool_name: 工具名称，用于在tool_calls列表中匹配tool_call_id

        Returns:
            fc_context dict（含tool_call_id + tool_calls）或 None
        """
        if getattr(self, '_strategy', None) != "tools":
            return None
        _fc_resp = getattr(self, '_last_fc_raw_response', None)
        if not _fc_resp or not getattr(_fc_resp, 'tool_calls', None):
            return None
        for _tc in _fc_resp.tool_calls:
            _fn_name = getattr(_tc, 'function', None)
            if _fn_name and getattr(_fn_name, 'name', '') == tool_name:
                _tc_id = getattr(_tc, 'id', '')
                return {"tool_calls": _fc_resp.tool_calls, "tool_call_id": _tc_id}
            elif isinstance(_tc, dict) and _tc.get("function", {}).get("name", "") == tool_name:
                _tc_id = _tc.get("id", "")
                return {"tool_calls": _fc_resp.tool_calls, "tool_call_id": _tc_id}
        return None

    def _build_err_dict(error: Exception) -> Dict[str, Any]:
        """构建异常路径的错误结果字典
        
        小沈 2026-05-25 重构拆分
        YAGNI: retry_count/warning/attachment/next_actions 已删除
        """
        return {
            "code": -1,
            "status": "error",
            "summary": str(error),
            "data": None,
            "return_direct": False,
            "error_message": str(error),
        }
    
    def _build_tool_outcome(
        self,
        execution_result: Dict[str, Any],
        execution_result_dict: Dict[str, Any],
        execution_time_ms: int,
        step_count: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        is_primary: bool,
        observation_text: str,
        *,
        fc_context: Optional[Dict[str, Any]] = None,
    ) -> _ToolStepOutcome:
        """统一构建工具执行的完整产出
        
        小沈 2026-05-25 重构拆分
        """
        action_step = StepFactory.create_action_tool_step(
            step=step_count, tool_name=tool_name, tool_params=tool_params,
            execution_result=execution_result_dict,
            execution_time_ms=execution_time_ms,
        )
        action_step_dict = self._emit_step(action_step)
        
        prefix = "[并行] " if not is_primary else ""
        obs_inject_text = f"{prefix}{observation_text}"
        
        return_direct = execution_result.get("return_direct", False) and is_primary
        display_result = dict(execution_result)
        display_result['summary'] = execution_result.get('message', '')
        display_result.setdefault('error_message', '')
        
        observation_step = StepFactory.create_observation_step(
            step=step_count, tool_name=tool_name, tool_params=tool_params,
            execution_result=display_result,
            return_direct=return_direct,
        )
        observation_step_dict = self._emit_step(observation_step)
        is_done = return_direct and observation_step.is_done()
        
        return _ToolStepOutcome(
            execution_result=execution_result,
            execution_result_dict=execution_result_dict,
            execution_time_ms=execution_time_ms,
            observation_text=observation_text,
            is_done=is_done,
            action_step_dict=action_step_dict,
            observation_step_dict=observation_step_dict,
            obs_inject_text=obs_inject_text,
            obs_fc_context=fc_context,
        )
    
    async def _execute_tool_step(
        self,
        tool_name: str,
        tool_params: Dict[str, Any],
        step_count: int,
        *,
        is_primary: bool = True,
    ) -> _ToolStepOutcome:
        """执行单个工具调用，构建action_tool+observation步骤
        
        【小沈重构 2026-05-25】
        - 重构拆分：提取 _build_err_dict / _build_tool_outcome
        - 内联 YAGNI：display_summary 单次使用变量
        - 保持所有分支完整，功能不减少
        
        统一主工具和pending工具的执行逻辑，消除代码重复。
        主工具(is_primary=True): 支持return_direct
        Pending工具(is_primary=False): 跳过return_direct
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数
            step_count: 当前步骤序号
            is_primary: 是否为主工具（默认True）
        
        Returns:
            _ToolStepOutcome: 包含执行结果、步骤dict、observation注入信息
        """
        try:
            start_time = time.perf_counter()
            logger.info(f"[DEBUG_TOOL_PARAMS] before execute_tool: tool_name={tool_name}, tool_params={tool_params}")
            
            from app.services.context_vars import _current_task_id
            _current_task_id.set(self.task_id or "")
            
            execution_result = await self._execute_tool(tool_name, tool_params)
            if execution_result is None:
                execution_result = {"code": -1, "message": f"工具 {tool_name} 返回None", "data": None}
                logger.warning(f"[execute_tool] _execute_tool返回None: tool_name={tool_name}")
            
            execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            execution_result_dict = build_execution_result_dict(execution_result)
            
            observation_text = build_observation_text(
                execution_result, tool_name=tool_name, tool_params=tool_params
            )
            
            fc_context = self._resolve_fc_context(tool_name) if is_primary else None
            
            try:
                _p_logger = get_prompt_logger()
                _p_logger.log_observation(
                    step_name="工具执行结果",
                    observation_content=observation_text,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    round_number=self.llm_call_count
                )
            except Exception:
                pass
            
            return self._build_tool_outcome(
                execution_result, execution_result_dict, execution_time_ms,
                step_count, tool_name, tool_params, is_primary, observation_text,
                fc_context=fc_context,
            )
        
        except Exception as _exec_err:
            logger.warning(f"[ReAct] 工具 {tool_name} 执行异常: {_exec_err}")
            err_dict = self._build_err_dict(_exec_err)
            return self._build_tool_outcome(
                err_dict, err_dict, 0,
                step_count, tool_name, tool_params, is_primary,
                f"Observation: error - {str(_exec_err)}",
                fc_context=None,
            )
