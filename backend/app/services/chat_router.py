# -*- coding: utf-8 -*-
"""
Chat Router - 路由层

【第一阶段实现 - 2026-03-26 小沈】
【Stage 5 更新 - 2026-03-26】
【阶段6更新 - 2026-03-27】简化分发逻辑，统一调用 react_sse_wrapper

架构：
- 第一层：chat_router.py - 路由入口 + 6步完整流程
- 第二层：react_sse_wrapper.py - SSE 包装（本文件调用）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【6步流程】
步骤1: 预处理 (PreprocessingPipeline)
步骤2: 意图检测 (IntentRegistry)
步骤3: 初始化 (ai_service/next_step/running_tasks/current_execution_steps)
步骤4: 安全检测 (security_check)
步骤5: start步骤 (start_step)
步骤6: 调用 react_sse_wrapper（由第二层内部根据intent_type分发）

【阶段6修改】
- 步骤6改为调用 react_sse_wrapper.generate_sse_stream()
- 删除 _handle_file_operation 和 _handle_chat_operation 方法（已移至 react_sse_wrapper）
- intent_type 和 confidence 参数传递给 react_sse_wrapper

Author: 小沈 - 2026-03-26
"""

import json
import uuid
import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.preprocessing.pipeline import PreprocessingPipeline
from app.services.agent.file_react import FileReactAgent
from app.services import AIServiceFactory
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_step_counter
from app.chat_stream.error_handler import create_error_response
from app.services.agent.base_react import DEFAULT_MAX_STEPS
from app.services.tools.registry import ToolCategory


# 意图标签列表（用于 PreprocessingPipeline）
INTENT_LABELS = [c.value for c in ToolCategory] + ["chat"]

# 【修复 2026-04-30 小沈】CRSS置信度阈值：归一化评分 >= 此值认为意图可信
# CRSS评分经 1 - 2^(-raw) 归一化到 [0, 1)，0.3 对应原始分约 0.5
CRSS_CONFIDENCE_THRESHOLD = 0.3


# ================================================================================
# detect_intent_v2 - CRSS加权评分意图检测（设计文档v1.5 3.1.2节）
# 替代旧的 detect_intent_from_crss，返回 ToolCategory 枚举，支持多意图
# 使用词边界正则 + 加权评分，覆盖：SHELL/TIME/NETWORK/DESKTOP/ENV/SYSTEM/DATABASE/FILE
# 小沈 - 2026-04-30
# ================================================================================

import re


def _ascii_word_boundary_match(keyword: str, text: str) -> bool:
    """
    ASCII-only 词边界检查（解决Python 3中 \w 包含中文的问题）
    
    Python 3 的 \b 将中文字符视为 \w，导致 '运行npm' 中 \bnpm\b 失效。
    此函数只将 [a-zA-Z0-9_] 视为词字符，中文视为非词字符。
    
    Args:
        keyword: 关键词（如 'npm'）
        text: 被搜索的文本
        
    Returns:
        是否匹配
    """
    import re as _re
    # 用 ASCII-only 的 \w 构建自定义边界模式
    pattern = f'(?<![a-zA-Z0-9_]){_re.escape(keyword)}(?![a-zA-Z0-9_])'
    return bool(_re.search(pattern, text, _re.IGNORECASE))


# 操作关键词定义（按ToolCategory分类）
INTENT_KEYWORDS: Dict[str, Dict] = {
    "SHELL": {
        "keywords": [
            # 危险命令已经在 DANGEROUS_COMMANDS 中，这里只添加执行类关键词
            r'\bnpm\b', r'\bpip\b', r'\bnode\b', r'\build\b', r'\brun\b',
            r'\bexec\b', r'\bexecute\b', r'\bgcc\b', r'\bg++\b', r'\bpython\b',
            r'\bgit\b', r'\bdocker\b', r'\bgradle\b', r'\bmvn\b', r'\bmake\b',
            '执行命令', '运行脚本', '终端', 'shell'
        ],
        "chinese_keywords": ['执行命令', '运行脚本', '终端']
    },
    "TIME": {
        "keywords": [
            r'\bdate\b', r'\btime\b', r'\bnow\b', r'\bclock\b',
            r'\bcalendar\b', r'\bschedule\b',
        ],
        "chinese_keywords": ['时间', '日期', '现在几点', '今天星期', '几月几号', '什么时候']
    },
    "NETWORK": {
        "keywords": [
            r'\bping\b', r'\bcurl\b', r'\bwget\b', r'\bssh\b', r'\btelnet\b',
            r'\bnc\b', r'\bnetcat\b', r'\bnmap\b', r'\bhttp\b', r'\bhttps\b',
            r'\bftp\b', r'\bsocket\b',
        ],
        "chinese_keywords": ['下载', '端口', '扫描', '网络', '请求', 'API']
    },
    "DESKTOP": {
        "keywords": [
            r'\bscreenshot\b', r'\bcapture\b',
            r'\bclick\b', r'\btype\b', r'\bpress\b', r'\bkey\b',
        ],
        "chinese_keywords": ['截图', '录屏', '点击', '输入', '按键', '键盘', '鼠标']
    },
    "ENV": {
        "keywords": [
            r'\bPATH\b', r'\bHOME\b', r'\bTEMP\b', r'\bTMP\b',
        ],
        "chinese_keywords": ['环境变量', 'PATH', '系统变量']
    },
    "SYSTEM": {
        "keywords": [
            r'\bcpu\b', r'\bmemory\b', r'\bram\b', r'\bdisk\b',
            r'\btasklist\b', r'\bprocess\b', r'\bservice\b',
        ],
        "chinese_keywords": ['系统信息', 'CPU', '内存', '进程', '服务', '磁盘', '系统配置']
    },
    "DATABASE": {
        "keywords": [
            r'\bselect\b', r'\binsert\b', r'\bupdate\b', r'\bdelete\b',
            r'\bcreate table\b', r'\bdrop\b', r'\balter\b', r'\bjoin\b',
            r'\bsql\b', r'\bdb\b', r'\bdatabase\b',
        ],
        "chinese_keywords": ['查询', 'SQL', '数据库', '表', '数据']
    },
}


def _compute_intent_scores(command: str) -> Dict[ToolCategory, float]:
    """
    CRSS加权评分：按匹配强度计算每个意图的置信度

    评分规则：
    - 中文关键词命中：+2.0/个（明确意图）
    - 英文正则命中：  +1.0/个（中度信号）
    - FILE操作关键词：+0.5/个（宽泛匹配）
    - 危险命令：      +3.0 基础分
    - 归一化： raw_score 经 1 - 2^(-score) 映射到 [0,1)

    Returns:
        Dict[ToolCategory, float] 置信度从高到低排序
    """
    if not command or not command.strip():
        return {}

    command_lower = command.lower().strip()
    raw_scores: Dict[ToolCategory, float] = {}

    # ===== 0. 危险命令 → SHELL 高分 =====
    from app.services.command_security import DANGEROUS_COMMANDS
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous.lower() in command_lower:
            logger.info(f"[CRSS Score] 危险命令 → SHELL +3.0: '{dangerous}'")
            raw_scores[ToolCategory.SHELL] = raw_scores.get(ToolCategory.SHELL, 0) + 3.0
            break

    # ===== 1. INTENT_KEYWORDS 分类匹配 =====
    category_map = {
        "SHELL": ToolCategory.SHELL,
        "TIME": ToolCategory.TIME,
        "NETWORK": ToolCategory.NETWORK,
        "DESKTOP": ToolCategory.DESKTOP,
        "ENV": ToolCategory.ENV,
        "SYSTEM": ToolCategory.SYSTEM,
        "DATABASE": ToolCategory.DATABASE,
    }

    for cat_name, cat_info in INTENT_KEYWORDS.items():
        cat_enum = category_map[cat_name]

        # 中文关键词：+2.0 每个
        for kw in cat_info.get("chinese_keywords", []):
            if kw in command_lower:
                logger.info(f"[CRSS Score] {cat_name} 中文关键词 +2.0: '{kw}'")
                raw_scores[cat_enum] = raw_scores.get(cat_enum, 0) + 2.0

        # 英文关键词：+1.0 每个（可能多个匹配）
        for pattern in cat_info.get("keywords", []):
            keyword = pattern.replace(r'\b', '')
            if _ascii_word_boundary_match(keyword, command_lower):
                logger.info(f"[CRSS Score] {cat_name} 英文关键词 +1.0: '{keyword}'")
                raw_scores[cat_enum] = raw_scores.get(cat_enum, 0) + 1.0

    # ===== 2. FILE 操作关键词 =====
    from app.services.command_security import OPERATION_WEIGHTS
    file_count = 0
    for op_type, config in OPERATION_WEIGHTS.items():
        for keyword in config.get('keywords', []):
            if keyword.lower() in command_lower:
                file_count += 1

    if file_count > 0:
        raw_scores[ToolCategory.FILE] = raw_scores.get(ToolCategory.FILE, 0) + file_count * 0.5
        logger.info(f"[CRSS Score] FILE 关键词 +{file_count * 0.5}: {file_count}个匹配")

    # ===== 3. 归一化 =====
    scores = {}
    for cat, raw in raw_scores.items():
        # 1 - 2^(-raw) 将 raw 映射到 [0, 1)
        adjusted = 1.0 - (2.0 ** (-raw))
        scores[cat] = round(adjusted, 4)

    # 按置信度从高到低排序
    return dict(sorted(scores.items(), key=lambda x: -x[1]))


def detect_intent_v2(command: str):
    """
    新版CRSS意图检测（设计文档 v1.5 3.1.2节）

    两阶段策略的阶段1: CRSS规则匹配
    - 使用加权评分计算各意图置信度
    - 返回 ToolCategory 枚举（不再是字符串）
    - 多候选支持

    Args:
        command: 用户输入的命令

    Returns:
        tuple: (primary_intent, candidates, confidence)
            - primary_intent: Optional[ToolCategory] 主意图（None表示无匹配）
            - candidates: List[ToolCategory] 所有候选意图（按置信度排序）
            - confidence: float 主意图置信度
    """
    if not command or not command.strip():
        return None, [], 0.0

    scores = _compute_intent_scores(command)

    if not scores:
        logger.info(f"[CRSS v2] 无匹配关键词 → None，等待LLM兜底")
        return None, [], 0.0

    sorted_items = list(scores.items())
    primary = sorted_items[0][0]
    candidates = [cat for cat, _ in sorted_items]
    confidence = sorted_items[0][1]

    logger.info(
        f"[CRSS v2] 加权评分结果 → primary={primary.value}, "
        f"confidence={confidence:.4f}, all={list(scores.keys())}"
    )
    return primary, candidates, confidence


# ================================================================================
# route_with_fallback - 两阶段意图路由（设计文档v1.5 3.1.2节）
# 阶段1: CRSS快速匹配 → 阶段2: LLM语义分类（兜底）
# 小沈 - 2026-04-30
# ================================================================================

async def route_with_fallback(user_input: str) -> Dict:
    """
    两阶段意图路由：CRSS快速匹配 + LLM兜底

    阶段1: 调用 detect_intent_v2 进行CRSS规则匹配
      - 匹配成功且唯一 → 直接返回，不调LLM
    阶段2: 无匹配或模糊匹配 → 调用 LLM 语义分类

    Args:
        user_input: 用户输入

    Returns:
        dict: {
            "intent": ToolCategory,       # 最终意图
            "candidates": List[ToolCategory],  # 所有候选
            "confidence": float,           # 置信度
            "original": str,               # 原始输入
            "corrected": str,              # 矫正后文本（LLM兜底时）
            "all_intents": dict,           # 所有意图置信度
            "source": str,                 # "crss" 或 "llm"
        }
    """
    # ===== 阶段1: CRSS快速匹配 =====
    primary, candidates, confidence = detect_intent_v2(user_input)

    result = {
        "intent": primary,
        "candidates": candidates,
        "confidence": confidence,
        "original": user_input,
        "corrected": user_input,
        "all_intents": {},
        "source": "crss",
    }

    # CRSS匹配成功（加权评分后有明确主意图）
    if primary is not None and confidence >= CRSS_CONFIDENCE_THRESHOLD:
        logger.info(
            f"[RouteFallback] CRSS阶段1 → intent={primary.value}, "
            f"conf={confidence}, candidates={[c.value for c in candidates]}"
        )
        return result

    # ===== 阶段2: LLM语义分类（兜底）=====
    logger.info(
        f"[RouteFallback] CRSS无匹配或模糊，进入LLM兜底阶段2. "
        f"primary={primary}, candidates={candidates}"
    )

    try:
        from app.services.preprocessing.intent_classifier import classify_intent

        # 准备提示标签（所有ToolCategory + chat）
        intent_labels = [c.value for c in ToolCategory] + ["chat"]

        llm_result = await classify_intent(user_input, intent_labels)

        intent_str = llm_result.get("intent", "chat")
        llm_confidence = float(llm_result.get("confidence", 0.5))

        # 将LLM返回的字符串转为ToolCategory
        intent_enum = None
        for cat in ToolCategory:
            if cat.value == intent_str:
                intent_enum = cat
                break

        result.update({
            "intent": intent_enum,
            "candidates": [intent_enum] if intent_enum else [],
            "confidence": llm_confidence,
            "corrected": llm_result.get("corrected", user_input),
            "all_intents": llm_result.get("all_intents", {}),
            "source": "llm",
        })

        logger.info(
            f"[RouteFallback] LLM阶段2 → intent={intent_str}({intent_enum}), "
            f"conf={llm_confidence}, corrected='{result['corrected']}'"
        )
    except Exception as e:
        logger.warning(f"[RouteFallback] LLM兜底失败: {e}，使用CRSS结果")
        # LLM失败时，保持CRSS结果

    return result


# ==================== FastAPI 路由定义 ====================

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式返回")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="温度参数")
    provider: Optional[str] = Field(default=None, description="前端指定的提供商")
    model: Optional[str] = Field(default=None, description="前端指定的模型")
    task_id: Optional[str] = Field(default=None, description="前端指定的任务ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")


@router.post("/chat/stream/v2")
async def chat_stream_v2(request: ChatRequest):
    """
    新版本流式API，使用 chat_router 进行意图路由

    【6步完整流程】
    步骤1: 预处理 (PreprocessingPipeline)
    步骤2: 意图检测 (IntentRegistry)
    步骤3: 初始化
    步骤4: 安全检测 (security_check)
    步骤5: start步骤 (start_step)
    步骤6: 分发到Agent
    """
    # 获取用户输入
    if not request.messages:
        error_response = create_error_response(
            error_type="invalid_request",
            error_message="消息列表不能为空"
        )
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=error_response,
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    
    # 获取配置 - 使用 AIServiceFactory 的统一逻辑
    from app.services import AIServiceFactory
    ai_service = AIServiceFactory.get_service()
    provider = ai_service.provider
    model = ai_service.model
    
    # session_id
    session_id = request.session_id or str(uuid.uuid4())
    
    # 创建 ChatRouter 实例
    chat_router = ChatRouter()
    
    # 创建 SSE 生成器
    async def generate():
        try:
            async for sse_data in chat_router.route(
                user_input=user_input,
                provider=provider,
                model=model,
                session_id=session_id,
                request=request,  # 传递原始请求用于获取 history
                ai_service=ai_service  # 【新增】传递已创建的 ai_service
            ):
                yield sse_data
        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(
                error_type="router_error",
                error_message=f"路由异常: {str(e)}"
            )
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== ChatRouter 服务层 ====================

class ChatRouter:
    """
    聊天路由器 - 根据意图类型分发到对应的执行层
    """

    def __init__(self) -> None:
        self.preprocessing = PreprocessingPipeline()

    async def route(
        self,
        user_input: str,
        provider: str,
        model: str,
        session_id: str,
        request: Optional[ChatRequest] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        ai_service: Optional[Any] = None  # 【新增】接收外部传入的 ai_service
    ) -> AsyncGenerator[str, None]:
        """
        根据用户意图路由到对应的执行层

        【6步完整流程】

        Args:
            user_input: 用户输入
            model: 模型名称
            provider: 提供商
            session_id: 会话ID
            request: 原始请求（用于获取history）
            context: 额外上下文
            system_prompt: 自定义系统提示
            max_steps: 最大步数

        Yields:
            SSE 格式字符串
        """
        # ===== 步骤1: 预处理 =====
        # 【修改 2026-04-30 小沈】意图检测使用两阶段 route_with_fallback
        # 预处理只做纯文本处理，意图检测在步骤2
        # 【修复 2026-04-30 小沈】移除废弃的 intent_labels 参数和死变量 intent_result
        await self.preprocessing.process(
            user_input=user_input,
            session_id=session_id
        )
        
        # ===== 步骤2: 意图检测（两阶段：CRSS + LLM兜底）=====
        # 【修改 2026-04-30 小沈】使用两阶段意图路由
        # 阶段1：CRSS规则快速匹配 → 阶段2：LLM语义分类（兜底）
        intent_info = await route_with_fallback(user_input)
        intent_type_value = intent_info["intent"]
        confidence = intent_info["confidence"]
        
        # 【新增 2026-04-30 小沈】从 intent_info 提取 candidates 列表
        candidates_values = intent_info.get("candidates", [])
        candidates_list = [c.value for c in candidates_values if c]  # 【修复 2026-04-30 小沈】简化：if c 已过滤None，else "" 不可达
        
        # 将ToolCategory转为字符串（与下游generate_sse_stream接口兼容）
        intent_type = intent_type_value.value if intent_type_value else "chat"
        
        logger.info(
            f"[ChatRouter] 两阶段意图检测 → intent_type={intent_type}({intent_type_value}), "
            f"confidence={confidence:.4f}, source={intent_info['source']}, "
            f"candidates={candidates_list}, "
            f"original='{user_input}', corrected='{intent_info['corrected']}'"
        )
        
        # ===== 步骤3: 初始化 =====
        # task_id: 任务ID
        task_id = str(uuid.uuid4())
        
        # ai_service: AI服务实例（优先使用传入的，复用而非重建）
        if ai_service is None:
            ai_service = AIServiceFactory.get_service_for_model(provider, model)
            logger.info(f"[ChatRouter] route() 自行创建 ai_service")
        else:
            logger.info(f"[ChatRouter] route() 复用传入的 ai_service")
        
        # next_step: 步骤计数器（使用统一函数）
        next_step = create_step_counter()
        
        # current_execution_steps: 执行步骤列表
        current_execution_steps: List[Dict] = []
        
        # 【问题1修复】使用 react_sse_wrapper 模块级全局变量，确保 cancel_task 能找到任务
        from app.services.react_sse_wrapper import running_tasks, running_tasks_lock
        # 运行期间保持引用，防止被垃圾回收
        _running_tasks_ref = running_tasks
        _running_tasks_lock_ref = running_tasks_lock
        
        # ===== 步骤4: 安全检测 =====
        from app.services.command_security import check_command_safety
        security_check_result = check_command_safety(user_input)
        
        # 如果被阻止，记录警告但继续执行
        if security_check_result.get('blocked', False):
            logger.warning(
                f"[ChatRouter] Security check blocked: "
                f"risk={security_check_result.get('risk')}, "
                f"user_input={user_input[:50]}"
            )
        
        # ===== 步骤5: start步骤 =====
        from app.chat_stream.start_step import send_start_step
        
        # 包装 yield 函数
        def yield_sse(data: dict):
            return f"data: {json.dumps(data)}\n\n"
        
        try:
            start_data = await send_start_step(
                ai_service=ai_service,
                task_id=task_id,
                next_step=next_step,
                user_message=user_input,
                security_check_result=security_check_result,
                current_execution_steps=current_execution_steps,
                session_id=session_id,
                yield_func=yield_sse
            )
            # 将 start_data yield 给前端（和 chat2.py 保持一致）
            yield f"data: {json.dumps(start_data)}\n\n"
        except Exception as e:
            logger.error(f"[ChatRouter] send_start_step failed: {e}", exc_info=True)
            yield create_error_response(
                error_type="start_failed",
                error_message=f"start步骤失败: {str(e)}"
            )
            return
        
        # ===== 步骤6: 根据意图类型分发 =====
        # 简单对话（chat 且 confidence >= 0.3）：在 router 里调用 chat_stream_query
        # 动作意图（file/network/desktop 或 confidence < 0.3）：调用 react_sse_wrapper
        
        # display_name 用于 chat_stream_query
        display_name = f"{ai_service.provider} ({ai_service.model})"
        
        if intent_type == "chat" and confidence >= 0.3:
            # 简单对话：直接调用 chat_stream_query
            logger.info(f"[ChatRouter] 简单对话意图，分发到 chat_stream_query")
            async for event in self._handle_chat_operation(
                request=request,
                user_input=user_input,
                ai_service=ai_service,
                task_id=task_id,
                session_id=session_id,
                current_execution_steps=current_execution_steps,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                next_step=next_step,
                display_name=display_name
            ):
                yield event
        else:
            # 动作意图：调用 react_sse_wrapper 处理
            logger.info(f"[ChatRouter] 动作意图 (type={intent_type}, conf={confidence:.2f}, candidates={candidates_list})，分发到 react_sse_wrapper")
            from app.services.react_sse_wrapper import generate_sse_stream
            
            # 准备 messages 列表
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            async for event in generate_sse_stream(
                messages=messages,
                intent_type=intent_type,
                confidence=confidence,
                candidates=candidates_list,  # 【新增 2026-04-30 小沈】传递候选意图列表
                provider=provider,
                model=model,
                task_id=task_id,
                session_id=session_id,
                ai_service=ai_service,
                next_step=next_step,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                current_execution_steps=current_execution_steps
            ):
                yield event

    async def _handle_chat_operation(
        self,
        request: Optional[ChatRequest],
        user_input: str,
        ai_service: Any,
        task_id: str,
        session_id: str,
        current_execution_steps: List[Dict],
        running_tasks: Dict[str, Any],
        running_tasks_lock: asyncio.Lock,
        next_step: Callable,
        display_name: str
    ) -> AsyncGenerator[str, None]:
        """处理简单对话意图"""
        try:
            from app.chat_stream.chat_stream_query import chat_stream_query
            
            # 修复：如果 request 为 None，创建一个只包含当前消息的请求对象
            if request is None:
                request = ChatRequest(
                    messages=[ChatMessage(role="user", content=user_input)],
                    session_id=session_id
                )
            
            # 准备 chat_stream_query 需要的参数
            llm_call_count = 0
            current_content = ""
            last_is_reasoning = None
            last_message = user_input
            
            # 包装 save_execution_steps_to_db 函数
            from app.chat_stream.message_saver import save_execution_steps_to_db
            async def wrapped_save_steps(execution_steps, content=None):
                await save_execution_steps_to_db(session_id, execution_steps, content)
            
            # 包装 add_step_and_save 函数
            from app.chat_stream.message_saver import add_step_and_save
            async def wrapped_add_step(step, content=None):
                await add_step_and_save(current_execution_steps, step, session_id, content)
            
            async for event in chat_stream_query(
                request=request,
                ai_service=ai_service,
                task_id=task_id,
                llm_call_count=llm_call_count,
                current_execution_steps=current_execution_steps,
                current_content=current_content,
                last_is_reasoning=last_is_reasoning,
                last_message=last_message,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                next_step=next_step,
                display_name=display_name,
                session_id=session_id,
                save_execution_steps_to_db=wrapped_save_steps,
                add_step_and_save=wrapped_add_step
            ):
                yield event
                
        except Exception as e:
            logger.error(f"[ChatRouter] Chat operation failed: {e}", exc_info=True)
            yield self._create_error_sse(
                error_type="router_error",
                error_message=f"对话执行失败: {str(e)}",
                step=next_step()
            )

    def _create_error_sse(self, error_type: str, error_message: str, step: int) -> str:
        """创建错误 SSE 响应"""
        return create_error_response(
            error_type=error_type,
            error_message=error_message,
            step=step
        )


# 便捷函数：创建 router 实例
def create_chat_router() -> ChatRouter:
    """创建 ChatRouter 实例"""
    return ChatRouter()


# ============================================================================
# 任务控制 API 端点（附录7.1）
# 从 react_sse_wrapper 导入任务控制函数
# ============================================================================
from app.services.react_sse_wrapper import (
    cancel_task as wrapper_cancel_task,
    pause_task as wrapper_pause_task,
    resume_task as wrapper_resume_task,
)

task_router = APIRouter()


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    取消任务
    """
    logger.info(f"[TaskControl] 取消任务: task_id={task_id}")
    result = await wrapper_cancel_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    暂停任务
    """
    logger.info(f"[TaskControl] 暂停任务: task_id={task_id}")
    result = await wrapper_pause_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    恢复任务
    """
    logger.info(f"[TaskControl] 恢复任务: task_id={task_id}")
    result = await wrapper_resume_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/confirm")
async def confirm_operation(request: Request):
    """
    用户确认继续操作
    """
    body = await request.json()
    task_id = body.get("task_id")
    confirmed = body.get("confirmed", True)
    
    logger.info(f"[TaskControl] 用户确认: task_id={task_id}, confirmed={confirmed}")
    
    # TODO: 实现用户确认逻辑
    return {
        "success": True,
        "message": "确认已收到"
    }
