
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 小欧 统一TaskID: 删除_tracked_task_id, create_task传入self.task_id
# 2026-07-17 小欧 新增_consecutive_reasoning_only字段(空转检测防御: reasoning-only分支累加, 调工具/正常answer/真空/error/未知/action空名归零)
# 2026-07-22 小欧 max_context_chars→max_context_tokens 构造传参同步
# 2026-07-22 小欧 新增 accumulated_usage 字段(累积消耗统计: 逐次LLM调用累加, FinalStep终态输出)
# 2026-08-05 小欧 修复BUG1/2(三堂会审通过): init_tools按实际加载结果重建_loaded_categories(消除initial_categories=None失配); load_category改为单一权威(同时写_tools_dict与_loaded_categories,空实现返回False), _loaded_categories仅含真正加载实现的分类
# 2026-08-12 小欧 A6: ToolLoader 独立为 tool_loader.py; 删除 tool_registry/ToolCategory 导入与 ToolLoader 类定义; __init__ 不再初始化工具状态(改由 UniversalAgent.__init__ 驱动)
# 2026-08-14 小欧 修正注释名不副实: _create_cancelled_chunk docstring 中"stream_parser函数"改为"core.py 的 create_cancelled_chunk"(实际调用名)
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-17 - 小健 - 门限基准唯一化(北京老陈驱动): MessageBuilder 改默认构造, 移除 get_config().get_max_context_tokens() 传参(该配置方法已删); max_context_tokens 运行时由 agent_runner 用 llm_service.context_limit 覆盖
# 2026-08-18 - 小欧 - §10.4.4 P3(error全仅SSE): 新增 _last_error: Optional[tuple]=None(step_emitter.emit 统一出口记录, 守卫读此填充 final)
# 2026-08-18 - 小欧 - §10.4.4 P6(usage剔step_json): 新增 _usage_events: List[Dict]=[](--每轮usage明细, agent_runner终态insert_token读)
# 2026-08-20 - 小欧 - 11.1 token 四层同构: 新增 task_accumulated_tokens/session_accumulated_tokens/chain_accumulated_tokens 三字段初始化({prompt/completion/total}=0), 跨轮/跨任务保持不重置, 供 react_cycle 内存态累计与 SSE/FinalStep/日志输出
# 2026-08-20 - 小欧 - 11.2-B start_time 透传: run_react_cycle 增 start_time 参数并透传 _run(同源起点, stream_orchestrator→agent_runner→此处), 调方不传时保持 None 行为不变
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.5: _create_cancelled_chunk 改传
#   create_cancelled_chunk(self.llm_client.llm_model)(入参归一 ModelRef); 顺修既有假数据缺陷——
#   原 getattr(self,'model','unknown') 中 BaseAgent 本无 model 属性恒落 'unknown'
# 2026-08-23 - 小欧 - 三轮三堂会审修复: ①P2 删 _ALLOWED_KWARGS={'model','provider','api_base','api_key'}
#   白名单——kwargs 散装覆写 agent 裸属性构成绕过 ModelRef 归一的暗道, 且全仓无调用方传参(死代码);
#   ②P1 新增 _task_llm_model 任务级快照(构造时 L2 已生效), 供 react_cycle/telemetry 全程读快照,
#   根治"单例被并发还原后记录到他人模型"竞态
# 2026-08-23 - 小欧 - 注释卫生勘误: 行内注缩进噪声修正 + 两处日期笔误 08-22→08-23(无任何逻辑变更)
"""
Agent 核心基类 — 类骨架

遵循 SRP: 只保留 BaseAgent 类定义、__init__、抽象方法、Hook、委托方法
run_react_cycle / initialize_run_state → 独立文件

Author: 小沈 - 2026-03-25
P3-12: 删除run_react_cycle纯委托，改为混合类方式 — 小沈 2026-06-09
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.services.agent.status_table import AgentStatus
from app.services.agent.steps import ReasoningStep

from app.config import get_config
from app.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.message_builder import MessageBuilder

from app.services.agent.step_emitter import StepEmitter
from app.services.agent.react_loop import run_react_cycle as _run


class BaseAgent(ABC):
    """Agent 核心基类 — 小沈 2026-03-25
    三堂会审修复(P2·小欧 2026-08-23): 删 _ALLOWED_KWARGS={'model','provider','api_base','api_key'} 白名单——
    它把裸 model/provider 设为 agent 属性, 构成绕过 ModelRef 归一的暗道(命名铁律违反), 且全仓无调用方传参(死代码)"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
        **kwargs
    ):
        # 原 AgentInitializer._init_llm — 归一后模型身份唯一入口 llm_client.llm_model, 不再接受散装 kwargs 覆写
        self.llm_client = llm_client
        # 三堂会审修复(P1·小欧 2026-08-23): 任务级模型身份快照——构造时(L2 sessionModel 已生效)定格,
        #   防共享单例被并发任务覆盖/还原后, 本任务后续轮次 on_llm_call/finalize 记录到他人模型
        self._task_llm_model = getattr(llm_client, "llm_model", None)

        if max_steps is None:
            max_steps = get_config().get_max_steps()

        # 原 AgentInitializer._init_state
        self.task_id = task_id
        self.max_steps = max_steps
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._last_error: Optional[tuple] = None  # 2026-08-18 - 小欧 - P3 error全仅SSE: step_emitter.emit统一出口记录(error_type,error_message), 守卫读此填充final
        self._usage_events: List[Dict] = []  # 2026-08-18 - 小欧 - P6 usage剔step_json: 每轮emit时append明细, agent_runner终态insert_token改读此处
        self._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - 连续reasoning-only计数(空转检测): reasoning-only分支累加, 调工具/正常answer/真空归零, 达上限终止
        self.accumulated_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}  # 2026-07-22 - 小欧 - 累积消耗统计: 逐次LLM调用累加, FinalStep终态输出
        # 11.1 token 四层同构：任务级/会话级/链级实时累计(跨轮/跨任务保持, 不在 initialize_run_state 重置) — 小欧 2026-08-20
        self.task_accumulated_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.session_accumulated_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.chain_accumulated_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # 原 AgentInitializer._init_messages
        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder()

        # 工具相关状态(_tools_dict/_tool_loader/_retry_engine/_loaded_categories)
        # A6(2026-08-12): 由子类 UniversalAgent.__init__ 驱动 tool_loader 初始化, 抽象基类不依赖工具注册表

        # 原 AgentInitializer._init_task_tracking
        self._task_tracker = None
        try:
            from app.services.task import get_tracker
            tracker = get_tracker()
            # 统一任务ID: SSE task_id 为全场唯一标识, tracker 不再自编号 — 北京老陈/小欧 2026-07-16
            tracker.create_task(
                task_id=self.task_id,
                agent_id=self.__class__.__name__,
                description="",
            )
            self._task_tracker = tracker
        except Exception as _e:
            logger.debug(f"[TaskTracker] 创建任务失败: {_e}")

        self._step_emitter = StepEmitter(self)

    def record_operation(self, operation_type: str, *, status: Optional[str] = None, **kwargs):
        self._step_emitter.record_operation(operation_type, status=status, **kwargs)

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: ReAct循环开始前 — 子类可override"""
        pass

    def _on_before_loop(self, sys_prompt: str, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: 构建sys_prompt后,循环开始前 — 子类可override"""
        pass

    def _on_after_loop(self):
        """生命周期Hook: ReAct循环结束后 — 子类可override"""
        pass

    # set_failed/set_completed/set_cancelled 方法已删除，统一使用 status_table.py 中的函数
    # chendyg 2026-07-01: 删除这三个方法，强制使用 status_table.set_failed/set_completed/set_cancelled

    def _create_cancelled_chunk(self):
        """创建取消chunk — 直接使用 core.py 的 create_cancelled_chunk 函数 — 小欧 2026-08-14
         【修复P2-6】移除对llm_client私有方法的依赖 — 北京老陈 2026-06-13
         【2026-08-22 小欧】归一报告v1.25 6.5: 入参改 chunk_model: ModelRef; 顺修既有假数据缺陷
           (原 getattr(self,'model','unknown') 中 BaseAgent 本无 model 属性, 恒落 'unknown')
        """
        from app.llm.core import create_cancelled_chunk
        return create_cancelled_chunk(self.llm_client.llm_model)

    async def run_react_cycle(self, task, context=None, max_steps=None, task_id=None, start_time=None):
        """直接从模块导入 — 小沈 2026-06-09 替代纯委托
        2026-08-20 - 小欧 - 11.2-B 增 start_time 透传(同源起点, stream_orchestrator→agent_runner→此处)"""
        async for event in _run(self, task, context, max_steps, task_id, start_time):
            yield event

